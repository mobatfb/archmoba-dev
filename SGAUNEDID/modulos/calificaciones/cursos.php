<?php
/**
 * SGA UNEDID - Calificaciones: primero aulas para la administracion;
 * luego asignaturas y docente responsable del aula escogida.
 * El docente conserva el listado directo de sus materias.
 */
require_once __DIR__.'/../../lib/funciones.php';
require_once __DIR__.'/../../lib/calificaciones_cards.php';
exigirLogin();
$p = periodoActivo();
$pid = (int)($p['id'] ?? 0);
if (!$pid || (!esAdminAcademico() && !esDocenteOperativo($pid))) {
    http_response_code(403);
    die('No tienes acceso a las calificaciones del periodo activo.');
}

$admin = esAdminAcademico();
$uid = (int)$_SESSION['usuario_id'];
$aulas = [];
$asignaturasPorAula = [];
$docentesPorAula = [];
$aulaSeleccionada = null;
$asignaturas = [];
$rows = [];

if ($admin) {
    // La funcion oficial respeta las jornadas del subadministrador y el filtro
    // de jornada activo. Al administrador principal no le aplica restriccion.
    $filtro = filtroJornadasSQL($pid, 'a');
    $sqlAulas = "SELECT ap.id aula_periodo_id, ap.evaluacion_cualitativa_parametros modo_parametros, a.nivel, a.nombre aula, a.paralelo,
                       COALESCE(j.nombre, 'Sin jornada') jornada, p.nombre periodo,
                       (SELECT COUNT(*) FROM matriculas m
                        WHERE m.aula_periodo_id=ap.id AND m.estado='activo') estudiantes
                FROM aulas_periodo ap
                JOIN aulas a ON a.id=ap.aula_id
                LEFT JOIN jornadas j ON j.id=a.jornada_id
                JOIN periodos_academicos p ON p.id=ap.periodo_id
                WHERE ap.periodo_id=? AND ap.activo=1 AND a.activo=1"
                .$filtro.
                " ORDER BY COALESCE(j.orden,32767), a.orden, a.nivel, a.nombre,
                           a.paralelo, a.id";
    $stmt = $conexion->prepare($sqlAulas);
    $stmt->bind_param('i', $pid);
    $stmt->execute();
    $aulas = $stmt->get_result()->fetch_all(MYSQLI_ASSOC);
    $stmt->close();

    // La lista de asignaturas incluye tambien las seleccionadas para un aula
    // que todavia no tienen profesor. Para datos antiguos, contempla ofertas
    // activas sin fila en la tabla de seleccion; no revive selecciones retiradas.
    $sqlAsignaturas = "SELECT sel.aula_periodo_id,
                              s.id asignatura_id, s.nombre asignatura,
                              CASE WHEN o.evaluacion_parametros_historica=1 THEN 0 ELSE s.solo_visor_comportamiento END solo_visor_comportamiento,COALESCE(o.evaluacion_parametros_historica,0) evaluacion_cualitativa_parametros,
                              o.id oferta_id, o.docente_id,
                              TRIM(CONCAT(COALESCE(u.apellidos,''),' ',COALESCE(u.nombres,''))) docente
                       FROM (
                           SELECT t.aula_periodo_id, t.asignatura_id
                           FROM aula_asignaturas_seleccionadas t
                           WHERE t.seleccionada=1
                           UNION
                           SELECT ofa.aula_periodo_id, ofa.asignatura_id
                           FROM ofertas_academicas ofa
                           WHERE ofa.activo=1 AND NOT EXISTS (
                               SELECT 1 FROM aula_asignaturas_seleccionadas t2
                               WHERE t2.aula_periodo_id=ofa.aula_periodo_id
                                 AND t2.asignatura_id=ofa.asignatura_id
                           )
                       ) sel
                       JOIN aulas_periodo ap ON ap.id=sel.aula_periodo_id
                       JOIN aulas a ON a.id=ap.aula_id
                       JOIN asignaturas s ON s.id=sel.asignatura_id
                       JOIN areas ar ON ar.id=s.area_id
                       LEFT JOIN ofertas_academicas o ON o.aula_periodo_id=sel.aula_periodo_id
                                   AND o.asignatura_id=sel.asignatura_id AND o.activo=1
                       LEFT JOIN usuarios u ON u.id=o.docente_id
                       WHERE ap.periodo_id=? AND ap.activo=1 AND a.activo=1 AND ap.evaluacion_cualitativa_parametros=0
                         AND COALESCE(s.codigo,'')<>'SGA_PARAM_AULA_INTERNO' AND COALESCE(o.evaluacion_aula,0)=0
                         AND NOT EXISTS (SELECT 1 FROM ofertas_academicas h WHERE h.aula_periodo_id=ap.id AND h.asignatura_id=s.id AND h.evaluacion_aula=1)
                         AND s.archivado_en IS NULL AND ar.archivado_en IS NULL"
                         .$filtro.
                       " ORDER BY ar.orden, s.nombre, s.id";
    $stmt = $conexion->prepare($sqlAsignaturas);
    $stmt->bind_param('i', $pid);
    $stmt->execute();
    foreach ($stmt->get_result()->fetch_all(MYSQLI_ASSOC) as $fila) {
        $apId = (int)$fila['aula_periodo_id'];
        $asignaturasPorAula[$apId][] = $fila;
        if ((int)($fila['docente_id'] ?? 0) > 0) {
            $docentesPorAula[$apId][(int)$fila['docente_id']] = true;
        }
    }
    $stmt->close();

    // Aulas por parámetros: una sola tarjeta, incluso cuando todavía no hay docente.
    $sqlParam="SELECT ap.id aula_periodo_id, o.id oferta_id,o.asignatura_id,o.docente_id,
        'Evaluación cualitativa del aula' asignatura,0 solo_visor_comportamiento,1 evaluacion_cualitativa_parametros,
        TRIM(CONCAT(COALESCE(u.apellidos,''),' ',COALESCE(u.nombres,''))) docente
        FROM aulas_periodo ap JOIN aulas a ON a.id=ap.aula_id
        LEFT JOIN ofertas_academicas o ON o.aula_periodo_id=ap.id AND o.evaluacion_aula=1 AND o.activo=1
        LEFT JOIN usuarios u ON u.id=o.docente_id
        WHERE ap.periodo_id=? AND ap.activo=1 AND a.activo=1 AND ap.evaluacion_cualitativa_parametros=1".$filtro;
    $stmt=$conexion->prepare($sqlParam);$stmt->bind_param('i',$pid);sgaEjecutar($stmt,'consultar aulas por parámetros');
    foreach($stmt->get_result()->fetch_all(MYSQLI_ASSOC) as $fila){
        $id=(int)$fila['aula_periodo_id'];$asignaturasPorAula[$id]=[$fila];
        if((int)($fila['docente_id']??0)>0)$docentesPorAula[$id][(int)$fila['docente_id']]=true;
    }
    $stmt->close();
    // El aula pedida se valida contra la lista previamente filtrada en servidor.
    // Cambiar manualmente la URL no revela aulas de otras jornadas.
    $bruto = $_GET['aula_periodo_id'] ?? '';
    if ($bruto !== '') {
        if (!is_string($bruto) || preg_match('/^[1-9][0-9]*$/D', $bruto) !== 1) {
            http_response_code(400);
            die('Identificador de aula no valido.');
        }
        $solicitada = (int)$bruto;
        foreach ($aulas as $aula) {
            if ((int)$aula['aula_periodo_id'] === $solicitada) {
                $aulaSeleccionada = $aula;
                $asignaturas = $asignaturasPorAula[$solicitada] ?? [];
                break;
            }
        }
        if ($aulaSeleccionada === null) {
            http_response_code(403);
            die('El aula seleccionada no pertenece a las jornadas autorizadas.');
        }
    }
} else {
    // Vista docente: se mantiene la seleccion directa por asignatura.
    $sql = "SELECT o.id,ap.id aula_periodo_id,a.nivel,a.nombre aula,a.paralelo,
                   CASE WHEN o.evaluacion_aula=1 THEN 'Evaluación cualitativa del aula' ELSE s.nombre END asignatura,CASE WHEN o.evaluacion_aula=1 OR o.evaluacion_parametros_historica=1 THEN 0 ELSE s.solo_visor_comportamiento END solo_visor_comportamiento,(o.evaluacion_aula=1 OR o.evaluacion_parametros_historica=1) evaluacion_cualitativa_parametros,p.nombre periodo,
                   (SELECT COUNT(*) FROM matriculas m WHERE m.aula_periodo_id=ap.id
                    AND m.estado='activo') estudiantes
            FROM ofertas_academicas o
            JOIN aulas_periodo ap ON ap.id=o.aula_periodo_id
            JOIN aulas a ON a.id=ap.aula_id
            JOIN asignaturas s ON s.id=o.asignatura_id
            JOIN areas ar ON ar.id=s.area_id
            JOIN periodos_academicos p ON p.id=ap.periodo_id
            WHERE ap.periodo_id=? AND ap.activo=1 AND o.activo=1
              AND s.archivado_en IS NULL AND ar.archivado_en IS NULL
              AND (ap.evaluacion_cualitativa_parametros=0 OR o.evaluacion_aula=1) AND o.docente_id=?";
    $sql .= filtroJornadasSQL($pid, 'a');
    $sql .= ' ORDER BY a.id ASC, s.nombre ASC';
    $stmt = $conexion->prepare($sql);
    $stmt->bind_param('ii', $pid, $uid);
    $stmt->execute();
    $rows = $stmt->get_result()->fetch_all(MYSQLI_ASSOC);
    $stmt->close();
}

$tituloPagina = 'Modulo de calificaciones';
$subtituloPagina = $admin
    ? ($aulaSeleccionada ? 'Asignaturas y docentes responsables del aula seleccionada.'
                         : 'Selecciona un aula para consultar sus asignaturas y docentes.')
    : 'Selecciona Calificar para abrir el registro de notas de tu asignatura.';
require __DIR__.'/../../partials/header.php';
?>
<?php if (!$admin): ?>
  <?php if (!$rows): ?>
    <div class="card empty">No tienes asignaturas activas para calificar en este periodo.</div>
  <?php else: ?>
    <div class="grid cols-2 subject-card-grid teacher-grade-grid">
      <?php foreach ($rows as $o) tarjetaAsignaturaCalificaciones($o, true); ?>
    </div>
  <?php endif; ?>
<?php else: ?>
<style>
.sga-cal-aulas{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:13px}
.sga-cal-aula{display:flex;flex-direction:column;gap:10px;height:100%;border:1px solid #d9e5f1;border-radius:13px;padding:16px;background:#fff;transition:border-color .15s,box-shadow .15s}
.sga-cal-aula:hover,.sga-cal-aula:focus-visible{border-color:#2171bf;box-shadow:0 4px 15px rgba(15,67,125,.12)}
.sga-cal-aula h2{font-size:17px;line-height:1.3;color:#153b69;margin:0}
.sga-cal-aula .jornada{color:#526b86;font-size:12px;font-weight:700}
.sga-cal-aula .stats{display:flex;gap:6px;flex-wrap:wrap;margin-top:auto}
.sga-cal-aula .stats span{padding:5px 7px;border-radius:6px;background:#edf3fa;font-size:11px;color:#294967}
.sga-cal-aula .abrir{color:#125d9e;font-weight:750;font-size:12px}
.sga-cal-toolbar{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;margin:0 0 16px}
.sga-cal-buscar{display:block;flex:1 1 260px;max-width:420px}
.sga-cal-buscar input{margin-top:5px}
.sga-cal-resumen{font-size:13px;color:#576d83}
.sga-cal-encabezado{display:flex;align-items:flex-start;justify-content:space-between;gap:14px;flex-wrap:wrap;margin:0 0 16px}
.sga-cal-encabezado h2{margin:0 0 5px;font-size:21px;color:#153b69}
.sga-cal-encabezado p{margin:0;color:#5d7188;font-size:13px}
.sga-cal-docente{display:flex;align-items:flex-start;gap:6px;font-size:13px;line-height:1.35;color:#153b69;font-weight:650}
.sga-cal-docente .sin-docente{color:#a33b35}
.sga-cal-asignatura-vacia{padding:20px 16px}
.sga-cal-aula-enlace[hidden]{display:none!important}
@media(max-width:1150px){.sga-cal-aulas{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:730px){.sga-cal-aulas{grid-template-columns:minmax(0,1fr)}.sga-cal-encabezado h2{font-size:18px}}
</style>
  <?php if ($aulaSeleccionada === null): ?>
    <div class="sga-cal-toolbar">
      <label class="sga-cal-buscar">Buscar aula o jornada
        <input type="search" id="sga-cal-busqueda" placeholder="Ej.: Noveno, Vespertina, 9EGB" autocomplete="off">
      </label>
      <span class="sga-cal-resumen"><?=count($aulas)?> aulas habilitadas en <?=e($p['nombre'] ?? '')?></span>
    </div>
    <?php if (!$aulas): ?>
      <div class="card empty">No hay aulas habilitadas para el periodo o la jornada seleccionada.</div>
    <?php else: ?>
      <div class="sga-cal-aulas" id="sga-cal-lista-aulas">
      <?php foreach ($aulas as $a):
        $id = (int)$a['aula_periodo_id'];
        $materias = count($asignaturasPorAula[$id] ?? []);
        $docentes = count($docentesPorAula[$id] ?? []);
        $nombreAula = trim((string)$a['aula'].' '.(string)$a['paralelo']);
        $busqueda = $a['nivel'].' '.$nombreAula.' '.$a['jornada'];
      ?>
        <a class="sga-cal-aula-enlace" data-busqueda="<?=e($busqueda)?>" href="<?=e(url('modulos/calificaciones/cursos.php?aula_periodo_id='.$id))?>">
          <article class="sga-cal-aula">
            <h2><?=e($nombreAula)?></h2>
            <div class="jornada"><?=e($a['nivel'])?> · <?=e($a['jornada'])?></div>
            <div class="stats">
              <span><?=(int)$a['estudiantes']?> estudiantes</span>
              <span><?=!empty($a['modo_parametros'])?'Por parámetros':$materias.' asignaturas'?></span>
              <span><?=$docentes?> docentes</span>
            </div>
            <span class="abrir"><?=!empty($a['modo_parametros'])?'Ver evaluación':'Ver asignaturas'?> →</span>
          </article>
        </a>
      <?php endforeach; ?>
      </div>
      <p class="mini-note" id="sga-cal-sin-resultados" hidden>No se encontraron aulas con ese texto.</p>
      <script>
      (() => {
        const campo=document.getElementById('sga-cal-busqueda');
        const enlaces=Array.from(document.querySelectorAll('.sga-cal-aula-enlace'));
        const aviso=document.getElementById('sga-cal-sin-resultados');
        if(!campo)return;
        campo.addEventListener('input', () => {
          const normalizar=s=>s.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
          const filtro=normalizar(campo.value.trim());
          let visibles=0;
          enlaces.forEach(enlace=>{
            const ver=normalizar(enlace.dataset.busqueda||'').includes(filtro);
            enlace.hidden=!ver;
            if(ver)visibles++;
          });
          aviso.hidden=visibles!==0;
        });
      })();
      </script>
    <?php endif; ?>
  <?php else:
    $idAula = (int)$aulaSeleccionada['aula_periodo_id'];
    $nombreAula = trim((string)$aulaSeleccionada['aula'].' '.(string)$aulaSeleccionada['paralelo']);
  ?>
    <section class="sga-cal-encabezado">
      <div>
        <h2><?=e($nombreAula)?> · <?=e($aulaSeleccionada['nivel'])?></h2>
        <p><?=e($aulaSeleccionada['jornada'])?> · <?=e($aulaSeleccionada['periodo'])?> ·
           <?=(int)$aulaSeleccionada['estudiantes']?> estudiantes ·
           <?=!empty($aulaSeleccionada['modo_parametros'])?'Evaluación por parámetros':count($asignaturas).' asignaturas'?> ·
           <?=count($docentesPorAula[$idAula] ?? [])?> docentes</p>
      </div>
      <a class="btn btn-secondary" href="<?=e(url('modulos/calificaciones/cursos.php'))?>">← Volver a aulas</a>
    </section>
    <?php if (!$asignaturas): ?>
      <div class="card empty">Esta aula todavía no tiene asignaturas seleccionadas.
        <div style="margin-top:12px"><a class="btn btn-primary" href="<?=e(url('modulos/academico/aula.php?id='.$idAula))?>">Configurar asignaturas</a></div>
      </div>
    <?php else: ?>
      <div class="grid cols-2 subject-card-grid">
      <?php foreach ($asignaturas as $asig):
        $oid = (int)($asig['oferta_id'] ?? 0);
        $esComportamiento = (int)$asig['solo_visor_comportamiento'] === 1;
        $esParametros = !empty($asig['evaluacion_cualitativa_parametros']);
        $nombreDocente = trim((string)($asig['docente'] ?? ''));
      ?>
        <article class="card course-card course-card-actions-left">
          <nav class="course-card-buttons" aria-label="Acciones para <?=e($asig['asignatura'])?>">
          <?php if ($oid > 0): ?>
            <?php if ($esComportamiento): ?>
              <a class="btn btn-primary" href="<?=e(url('modulos/calificaciones/comportamiento.php?oferta_id='.$oid))?>">Calificar comportamiento</a>
            <?php elseif ($esParametros): ?>
              <a class="btn btn-primary" href="<?=e(url('modulos/calificaciones/parametros.php?oferta_id='.$oid))?>">Calificar parámetros</a>
            <?php else: ?>
              <a class="btn btn-primary" href="<?=e(url('modulos/calificaciones/index.php?oferta_id='.$oid))?>">Calificaciones</a>
            <?php endif; ?>
            <a class="btn btn-success" href="<?=e(url('modulos/asistencia/registro.php?oferta_id='.$oid))?>">Asistencia</a>
            <a class="btn btn-secondary" href="<?=e(url('modulos/academico/lista.php?oferta_id='.$oid))?>">Lista</a>
            <?php if (!$esComportamiento && !$esParametros): ?>
              <a class="btn btn-secondary" href="<?=e(url('modulos/calificaciones/finales.php?oferta_id='.$oid))?>">Finales</a>
            <?php endif; ?>
          <?php else: ?>
            <a class="btn btn-secondary" href="<?=e(url('modulos/academico/aula.php?id='.$idAula))?>">Asignar docente</a>
          <?php endif; ?>
          </nav>
          <div class="course-card-info">
            <h2 class="title"><?=e($asig['asignatura'])?></h2>
            <div class="sga-cal-docente">
              <span>Docente:</span>
              <?php if ($oid > 0 && $nombreDocente !== ''): ?>
                <span><?=e($nombreDocente)?></span>
              <?php else: ?>
                <span class="sin-docente">Sin docente asignado</span>
              <?php endif; ?>
            </div>
            <?php if ($esComportamiento): ?>
              <span class="tag">Asignatura de comportamiento</span>
            <?php elseif ($esParametros): ?>
              <span class="tag">Evaluación cualitativa por parámetros</span>
            <?php endif; ?>
            <div class="stat-row"><span class="tag"><?=(int)$aulaSeleccionada['estudiantes']?> estudiantes</span></div>
          </div>
        </article>
      <?php endforeach; ?>
      </div>
    <?php endif; ?>
  <?php endif; ?>
<?php endif; ?>
<?php require __DIR__.'/../../partials/footer.php'; ?>
