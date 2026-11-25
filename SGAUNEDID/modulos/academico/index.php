<?php
/**
 * SGA UNEDID - Gestion academica (parche V1.6.9).
 * Habilitacion individual o multiple de aulas para un periodo, con filtro de
 * jornadas, orden academico y validacion de permisos en el servidor.
 */
require_once __DIR__.'/../../lib/funciones.php';
exigirAdminAcademico();

$activo = periodoActivo();
$periodoId = (int)($_GET['periodo_id'] ?? ($_POST['periodo_id'] ?? ($activo['id'] ?? 0)));
$periodoId = periodoInicialSubadmin(
    $periodoId,
    isset($_GET['periodo_id']) || isset($_POST['periodo_id']) ? 1 : 0
);
if ($periodoId > 0) {
    exigirAccesoPeriodo($periodoId);
} elseif (esSubadmin()) {
    http_response_code(403);
    die('No existe un periodo autorizado.');
}

if (empty($_SESSION['csrf_habilitar_aulas_periodo'])) {
    $_SESSION['csrf_habilitar_aulas_periodo'] = bin2hex(random_bytes(24));
}
$csrfAulas = (string)$_SESSION['csrf_habilitar_aulas_periodo'];

// Se consulta solo el catalogo visible para este usuario y este periodo.
// Para un subadministrador tambien se respeta la jornada que selecciono
// previamente en el menu lateral.
$aulas = $conexion->query(
    'SELECT a.*,j.nombre jornada FROM aulas a '
    .'JOIN jornadas j ON j.id=a.jornada_id AND j.activo=1 '
    .'WHERE a.activo=1'.filtroJornadasSQL($periodoId, 'a')
    .' ORDER BY j.orden ASC,a.orden ASC,a.nivel ASC,a.nombre ASC,a.paralelo ASC,a.id ASC'
)->fetch_all(MYSQLI_ASSOC);

$jornadasDisponibles = [];
foreach ($aulas as $aula) {
    $jid = (int)($aula['jornada_id'] ?? 0);
    if ($jid > 0 && !isset($jornadasDisponibles[$jid])) {
        $jornadasDisponibles[$jid] = (string)($aula['jornada'] ?? ('Jornada '.$jid));
    }
}

// El filtro es exclusivamente visual; nunca habilita permisos nuevos.
$filtroBruto = $_SERVER['REQUEST_METHOD'] === 'POST'
    ? ($_POST['filtro_jornada'] ?? '0')
    : '0'; // Selector combinado: mostrar todas las jornadas académicas.
$filtroSintaxisValida = is_scalar($filtroBruto)
    && preg_match('/^(0|[1-9][0-9]*)$/D', (string)$filtroBruto) === 1;
$filtroSolicitado = $filtroSintaxisValida ? (int)$filtroBruto : -1;
$filtroAutorizado = $filtroSintaxisValida
    && ($filtroSolicitado === 0 || isset($jornadasDisponibles[$filtroSolicitado]));
$filtroJornada = $filtroAutorizado ? $filtroSolicitado : 0;

$aulasFiltradas = [];
foreach ($aulas as $aula) {
    $jid = (int)($aula['jornada_id'] ?? 0);
    // La jornada es obligatoria para nuevas habilitaciones academicas.
    if ($jid <= 0) continue;
    if ($filtroJornada !== 0 && $jid !== $filtroJornada) continue;
    $aulasFiltradas[(int)$aula['id']] = $aula;
}

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $accion = (string)($_POST['accion'] ?? 'habilitar');
    try {
        if(!hash_equals($csrfAulas,(string)($_POST['csrf']??'')))
            throw new RuntimeException('Formulario académico caducado. Recarga la página.');
        sgaAsegurarPeriodoEditable($periodoId);
        if ($accion === 'habilitar_lote') {
            if (!is_string($_POST['csrf'] ?? null) || !hash_equals($csrfAulas, $_POST['csrf'])) {
                throw new RuntimeException('La sesión del formulario ha caducado. Actualiza la pagina e intenta nuevamente.');
            }
            if (!$filtroAutorizado) {
                throw new RuntimeException('La jornada seleccionada no está disponible para tu cuenta.');
            }
            $idsBrutos = $_POST['aula_ids'] ?? [];
            if (!is_array($idsBrutos) || !$idsBrutos || count($idsBrutos) > 500) {
                throw new RuntimeException('Selecciona entre 1 y 500 aulas para habilitar.');
            }
            $ids = [];
            foreach ($idsBrutos as $dato) {
                if (!is_scalar($dato) || preg_match('/^[1-9][0-9]*$/D', (string)$dato) !== 1) {
                    throw new RuntimeException('Hay una selección de aula no válida.');
                }
                $id = (int)$dato;
                if ($id < 1 || !isset($aulasFiltradas[$id])) {
                    throw new RuntimeException('Una de las aulas no pertenece a la jornada elegida o no está autorizada.');
                }
                $ids[$id] = $id;
            }
            if (!$ids) throw new RuntimeException('Selecciona al menos un aula.');
            foreach ($ids as $aulaId) {
                // Segunda barrera de permisos: nunca confiar solo en el filtro del formulario.
                exigirAccesoAula($aulaId, $periodoId);
            }
        }

        if (!$conexion->begin_transaction()) {
            throw new RuntimeException('No se pudo iniciar la transaccion.');
        }

        if ($accion === 'habilitar_lote') {
            $consulta = $conexion->prepare('SELECT id,activo FROM aulas_periodo WHERE periodo_id=? AND aula_id=? LIMIT 1');
            $actualiza = $conexion->prepare('UPDATE aulas_periodo SET activo=1 WHERE id=?');
            $inserta = $conexion->prepare('INSERT INTO aulas_periodo(periodo_id,aula_id,activo,evaluacion_cualitativa_parametros) SELECT ?,id,1,evaluacion_cualitativa_parametros FROM aulas WHERE id=?');
            if (!$consulta || !$actualiza || !$inserta) {
                throw new RuntimeException('No se pudieron preparar las consultas de habilitacion.');
            }
            $nuevas = 0;
            $reactivadas = 0;
            $yaActivas = 0;
            foreach ($ids as $aulaId) {
                $consulta->bind_param('ii', $periodoId, $aulaId);
                sgaEjecutar($consulta, 'consultar el estado del aula');
                $resultado = $consulta->get_result();
                $prev = $resultado->fetch_assoc();
                $resultado->free();

                if ($prev && (int)$prev['activo'] === 1) {
                    $yaActivas++;
                    continue; // No duplicar habilitaciones, ni registrar auditorias innecesarias.
                }

                if ($prev) {
                    $apId = (int)$prev['id'];
                    $actualiza->bind_param('i', $apId);
                    sgaEjecutar($actualiza, 'reactivar el aula');
                    $tipoAuditoria = 'UPDATE';
                    $detalle = 'Aula reactivada para el periodo mediante seleccion multiple.';
                    $reactivadas++;
                } else {
                    $inserta->bind_param('ii', $periodoId, $aulaId);
                    sgaEjecutar($inserta, 'habilitar el aula');
                    $apId = (int)$conexion->insert_id;
                    $tipoAuditoria = 'CREATE';
                    $detalle = 'Aula habilitada para el periodo mediante seleccion multiple.';
                    $nuevas++;
                }
                sgaAuditoriaObligatoria(
                    $tipoAuditoria, 'Gestión académica', 'aula_periodo', $apId,
                    $detalle, null, $prev,
                    ['periodo_id'=>$periodoId,'aula_id'=>$aulaId,'activo'=>1],
                    'exito', null, null, 'advertencia'
                );
            }
            $consulta->close();
            $actualiza->close();
            $inserta->close();
            flash('success', 'Habilitación completada: '.$nuevas.' nueva(s), '
                .$reactivadas.' reactivada(s) y '.$yaActivas.' que ya estaban activas.');

        } elseif ($accion === 'habilitar') {
            // Compatibilidad con formularios anteriores de un solo aula.
            $aulaId = (int)($_POST['aula_id'] ?? 0);
            if (!$periodoId || !$aulaId) throw new Exception('Selecciona periodo y aula.');
            exigirAccesoAula($aulaId, $periodoId);
            $stmt = $conexion->prepare('SELECT id,activo FROM aulas_periodo WHERE periodo_id=? AND aula_id=? LIMIT 1');
            $stmt->bind_param('ii', $periodoId, $aulaId);
            $stmt->execute();
            $prev = $stmt->get_result()->fetch_assoc();
            $stmt->close();
            if ($prev) {
                $apIdAud = (int)$prev['id'];
                $stmt = $conexion->prepare('UPDATE aulas_periodo SET activo=1 WHERE id=?');
                $stmt->bind_param('i', $apIdAud);
                sgaEjecutar($stmt, 'reactivar el aula');
                $stmt->close();
                $accionAud = 'UPDATE';
                $detalle = 'Aula reactivada para el periodo.';
            } else {
                $stmt = $conexion->prepare('INSERT INTO aulas_periodo(periodo_id,aula_id,activo,evaluacion_cualitativa_parametros) SELECT ?,id,1,evaluacion_cualitativa_parametros FROM aulas WHERE id=?');
                $stmt->bind_param('ii', $periodoId, $aulaId);
                sgaEjecutar($stmt, 'habilitar el aula');
                $apIdAud = (int)$conexion->insert_id;
                $stmt->close();
                $accionAud = 'CREATE';
                $detalle = 'Aula habilitada para el periodo.';
            }
            sgaAuditoriaObligatoria($accionAud, 'Gestión académica', 'aula_periodo', $apIdAud,
                $detalle, null, $prev,
                ['periodo_id'=>$periodoId,'aula_id'=>$aulaId,'activo'=>1],
                'exito', null, null, 'advertencia');
            flash('success', $detalle);

        } elseif ($accion === 'toggle') {
            $id = (int)$_POST['id'];
            exigirAccesoAulaPeriodo($id);
            $stmt = $conexion->prepare('SELECT id,periodo_id,aula_id,activo FROM aulas_periodo WHERE id=? AND periodo_id=? LIMIT 1');
            $stmt->bind_param('ii', $id, $periodoId);
            $stmt->execute();
            $antes = $stmt->get_result()->fetch_assoc();
            $stmt->close();
            if (!$antes) throw new Exception('Aula del periodo no encontrada.');
            $nuevo = (int)$antes['activo'] ? 0 : 1;
            $stmt = $conexion->prepare('UPDATE aulas_periodo SET activo=? WHERE id=?');
            $stmt->bind_param('ii', $nuevo, $id);
            sgaEjecutar($stmt, 'cambiar el estado del aula');
            $stmt->close();
            $despues = $antes;
            $despues['activo'] = $nuevo;
            sgaAuditoriaObligatoria('UPDATE', 'Gestión académica', 'aula_periodo', $id,
                $nuevo ? 'Aula del periodo activada.' : 'Aula del periodo desactivada.',
                null, $antes, $despues, 'exito', null, null, 'advertencia');
            flash('success', $nuevo ? 'Aula activada para el periodo.' : 'Aula desactivada para el periodo.');

        } elseif ($accion === 'eliminar') {
            $id = (int)$_POST['id'];
            exigirAccesoAulaPeriodo($id);
            $stmt = $conexion->prepare('SELECT id,periodo_id,aula_id,activo FROM aulas_periodo WHERE id=? AND periodo_id=? LIMIT 1');
            $stmt->bind_param('ii', $id, $periodoId);
            $stmt->execute();
            $antes = $stmt->get_result()->fetch_assoc();
            $stmt->close();
            if (!$antes) throw new Exception('Aula del periodo no encontrada.');
            $stmt = $conexion->prepare('SELECT '
                .'(SELECT COUNT(*) FROM matriculas WHERE aula_periodo_id=?)+'
                .'(SELECT COUNT(*) FROM ofertas_academicas WHERE aula_periodo_id=?)+'
                .'(SELECT COUNT(*) FROM eleccion_aulas WHERE aula_periodo_id=?) c');
            $stmt->bind_param('iii', $id, $id, $id);
            $stmt->execute();
            $dep = (int)$stmt->get_result()->fetch_assoc()['c'];
            $stmt->close();
            if ($dep > 0) {
                throw new Exception('Esta aula del periodo ya tiene matriculas, asignaturas o participacion electoral. Desactivala en lugar de eliminarla.');
            }
            $stmt = $conexion->prepare('DELETE FROM aulas_periodo WHERE id=?');
            $stmt->bind_param('i', $id);
            sgaEjecutar($stmt, 'eliminar el aula del periodo');
            $stmt->close();
            sgaAuditoriaObligatoria('DELETE', 'Gestión académica', 'aula_periodo', $id,
                'Aula del periodo sin historial eliminada.', null, $antes, null,
                'exito', null, null, 'critica');
            flash('success', 'Aula eliminada del periodo.');
        } else {
            throw new RuntimeException('Accion de aula no reconocida.');
        }

        if (!$conexion->commit()) {
            throw new RuntimeException('No se pudieron confirmar los cambios del aula.');
        }
    } catch (Throwable $e) {
        try { $conexion->rollback(); } catch (Throwable $ignorar) {}
        flash('error', $e->getMessage());
    }
    redir('modulos/academico/index.php?periodo_id='.$periodoId
        .($filtroJornada > 0 ? '&jornada='.$filtroJornada : ''));
}

$periodos = $conexion->query(
    'SELECT * FROM periodos_academicos '
    .'ORDER BY anio_inicio DESC'
)->fetch_all(MYSQLI_ASSOC);

$filas = [];
if ($periodoId) {
    $stmt = $conexion->prepare(
        "SELECT ap.id,ap.aula_id,ap.activo,ap.evaluacion_cualitativa_parametros,a.nivel,a.nombre,a.paralelo,j.nombre jornada,p.nombre periodo,"
        ."(SELECT COUNT(*) FROM matriculas m WHERE m.aula_periodo_id=ap.id AND m.estado='activo') estudiantes,"
        // Una asignatura cuenta si fue seleccionada para el aula, aunque
        // todavia no tenga docente. Se incluyen ofertas antiguas activas,
        // tal como hace el listado de asignaturas en aula.php.
         ."CASE WHEN ap.evaluacion_cualitativa_parametros=1 THEN 0 ELSE (SELECT COUNT(*) FROM asignaturas s "
        ."JOIN areas ar ON ar.id=s.area_id "
        ."WHERE s.activo=1 AND ar.activo=1 "
        ."AND (EXISTS (SELECT 1 FROM aula_asignaturas_seleccionadas sel "
        ."WHERE sel.aula_periodo_id=ap.id AND sel.asignatura_id=s.id AND sel.seleccionada=1) "
        ."OR EXISTS (SELECT 1 FROM ofertas_academicas oa "
        ."WHERE oa.aula_periodo_id=ap.id AND oa.asignatura_id=s.id AND oa.activo=1))) END asignaturas,"
        // Un docente con varias materias del mismo paralelo cuenta una vez.
        ."(SELECT COUNT(DISTINCT od.docente_id) FROM ofertas_academicas od "
        ."JOIN asignaturas sd ON sd.id=od.asignatura_id "
        ."JOIN areas ard ON ard.id=sd.area_id "
        ."WHERE od.aula_periodo_id=ap.id AND od.activo=1 AND (od.evaluacion_aula=1 OR (sd.activo=1 AND ard.activo=1))) docentes "
        .'FROM aulas_periodo ap JOIN aulas a ON a.id=ap.aula_id '
        .'LEFT JOIN jornadas j ON j.id=a.jornada_id '
        .'JOIN periodos_academicos p ON p.id=ap.periodo_id '
        .'WHERE ap.periodo_id=?'.filtroJornadasSQL($periodoId, 'a')
        .' ORDER BY COALESCE(j.orden,32767) ASC,a.orden ASC,a.nivel ASC,a.nombre ASC,a.paralelo ASC,a.id ASC'
    );
    $stmt->bind_param('i', $periodoId);
    $stmt->execute();
    $filas = $stmt->get_result()->fetch_all(MYSQLI_ASSOC);
    $stmt->close();
}

$estadoAulas = [];
foreach ($filas as $fila) $estadoAulas[(int)$fila['aula_id']] = (int)$fila['activo'];

$soloLectura = false;
foreach ($periodos as $periodoDato) {
    if ((int)$periodoDato['id'] === $periodoId) {
        $soloLectura = $periodoDato['estado'] === 'cerrado';
        break;
    }
}

$tituloPagina = 'Gestión académica';
$subtituloPagina = 'Habilita aulas por período y administra matrículas, asignaturas y docentes con control de estado.';
require __DIR__.'/../../partials/header.php';
?>
<style>
/* Una unica fila de controles; si no cabe, se adapta sin desbordarse. */
.sga-aulas-fila-unica{display:flex;align-items:flex-end;gap:12px;flex-wrap:wrap;margin:12px 0 2px;min-width:0}
.sga-aulas-periodo-toolbar{flex:1 1 230px;min-width:180px;margin:0}
.sga-aulas-periodo-toolbar label{display:flex;flex-direction:column;width:100%;max-width:none}
.sga-aulas-periodo-toolbar select{width:100%;min-width:0}
#sga-habilitar-aulas-lote{flex:2 1 450px;min-width:380px;margin:0}
.sga-aulas-fila-unica>.notice{flex:2 1 450px;min-width:0;margin:0}
/* El menu flota sobre el contenido. No aumenta la altura de la tarjeta. */
.sga-aulas-habilitar-card{position:relative;z-index:1;overflow:visible}
.sga-aulas-habilitar-card:has(.sga-aulas-picker[open]){z-index:90}
.sga-aulas-compact-row{display:grid;grid-template-columns:minmax(0,1fr) max-content;align-items:end;gap:10px;margin:0;min-width:0}
.sga-aulas-picker{position:relative;min-width:0;width:100%;max-width:none;color:#234363}
.sga-aulas-picker[open]{z-index:100}
.sga-aulas-picker>summary{box-sizing:border-box;list-style:none;display:flex;align-items:center;justify-content:space-between;gap:12px;min-height:41px;width:100%;border:1px solid #cfd9e5;border-radius:8px;background:#fff;padding:8px 12px;color:#17365f;font-size:13px;font-weight:700;cursor:pointer;user-select:none}
.sga-aulas-picker>summary::-webkit-details-marker{display:none}
.sga-aulas-picker>summary::after{content:'';display:block;width:8px;height:8px;flex:0 0 8px;border-right:2px solid #41617f;border-bottom:2px solid #41617f;transform:rotate(45deg);transition:transform .15s ease}
.sga-aulas-picker[open]>summary{border-color:#508bc8;background:#f7fbff}
.sga-aulas-picker[open]>summary::after{transform:rotate(225deg)}
.sga-aulas-picker>summary:focus-visible{outline:2px solid #1c6ab8;outline-offset:2px}
.sga-aulas-picker-label{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.sga-aulas-picker-panel{position:absolute;top:calc(100% + 5px);left:0;z-index:1100;box-sizing:border-box;width:min(525px,calc(100vw - 42px));max-height:min(65vh,470px);overflow-y:auto;overscroll-behavior:contain;padding:11px;border:1px solid #b9cee5;border-radius:11px;background:#fff;box-shadow:0 18px 45px rgba(8,36,72,.23)}
.sga-aulas-picker.sga-aulas-abre-arriba>.sga-aulas-picker-panel{top:auto;bottom:calc(100% + 5px)}
.sga-aulas-seleccion-barra{display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap;border-bottom:1px solid #e1e9f2;padding-bottom:10px;margin-bottom:8px}
.sga-aulas-seleccionar-todas,.sga-aulas-jornada-label{display:flex!important;flex-direction:row!important;align-items:center;gap:9px;margin:0!important;cursor:pointer;font-size:12px;color:#17365f}
.sga-aulas-seleccionar-todas{font-weight:750}
.sga-aulas-seleccionar-todas input,.sga-aulas-jornada-label input,.sga-aulas-seleccion-item input{width:16px!important;height:16px!important;flex:0 0 16px;margin:0;accent-color:#1255a2;cursor:pointer}
.sga-aulas-jornada{border:1px solid #e0e8f2;border-radius:9px;margin:8px 0;padding:8px;background:#fbfdff}
.sga-aulas-jornada-label{padding:4px 2px 8px!important;font-weight:750}
.sga-aulas-jornada-label strong{font-size:12px;letter-spacing:.02em;color:#123b71}
.sga-aulas-jornada-label small{font-size:10px;color:#667c96;font-weight:600;margin-left:auto}
.sga-aulas-seleccion-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px}
.sga-aulas-seleccion-item{display:flex!important;flex-direction:row!important;align-items:center;gap:7px;min-width:0;border:1px solid #d8e1ed;border-radius:8px;padding:7px 8px;margin:0!important;cursor:pointer;font-size:12px;background:#fff}
.sga-aulas-seleccion-item:hover{border-color:#81addc;background:#f8fbff}
.sga-aulas-seleccion-item:has(input:checked){background:#edf5ff;border-color:#3272b5}
.sga-aulas-seleccion-item-text{display:block;min-width:0;flex:1}
.sga-aulas-seleccion-item-text strong{display:block;color:#17365f;font-size:12px;line-height:1.3}
.sga-aulas-seleccion-item-text small{display:block;margin-top:2px;font-size:10px;color:#60718a;line-height:1.3}
.sga-aulas-seleccion-item .badge{align-self:center;white-space:nowrap;font-size:9px;padding:3px 5px}
.sga-aulas-picker-note{margin:9px 0 0!important;color:#61738a;font-size:11px;line-height:1.4}
.sga-aulas-compact-row>.btn{min-height:41px;white-space:nowrap}
@media(max-width:630px){
  .sga-aulas-fila-unica{gap:10px}
  .sga-aulas-periodo-toolbar,#sga-habilitar-aulas-lote{flex:1 1 100%;min-width:0}
  .sga-aulas-compact-row{grid-template-columns:minmax(0,1fr)}
  .sga-aulas-picker{max-width:100%;min-width:0}
  .sga-aulas-seleccion-grid{grid-template-columns:1fr}
  .sga-aulas-compact-row>.btn{width:100%}
}
</style>
<?php if ($soloLectura): ?>
<div class="notice" role="status"><strong>Período cerrado · solo lectura.</strong> Puedes abrir las aulas para consultar registros anteriores, pero no modificarlas.</div>
<?php endif; ?>
<section class="card sga-aulas-habilitar-card">
  <h2 style="margin:0 0 5px">Habilitar aulas en el período</h2>
  <p class="mini-note" style="margin:0">Selecciona una jornada completa, varias jornadas o aulas individuales desde un único desplegable.</p>
  <div class="sga-aulas-fila-unica">
  <form method="get" class="sga-aulas-periodo-toolbar" id="sga-aulas-filtros">
    <label>Período
      <select name="periodo_id" onchange="this.form.submit()">
        <?php foreach ($periodos as $p): ?>
        <option value="<?=(int)$p['id']?>" <?=(int)$p['id']===$periodoId?'selected':''?>><?=e($p['nombre'].' · '.$p['estado'])?></option>
        <?php endforeach; ?>
      </select>
    </label>
    <noscript><button class="btn btn-secondary" type="submit">Aplicar período</button></noscript>
  </form>
  <?php if (!$aulasFiltradas): ?>
    <div class="notice" role="status">No hay aulas activas con jornada asignada. Puedes configurarlas en Aulas y paralelos.</div>
  <?php else: ?>
    <form method="post" id="sga-habilitar-aulas-lote">
      <input type="hidden" name="accion" value="habilitar_lote">
      <input type="hidden" name="periodo_id" value="<?=$periodoId?>">
      <input type="hidden" name="filtro_jornada" value="0">
      <input type="hidden" name="csrf" value="<?=e($csrfAulas)?>">
      <div class="sga-aulas-compact-row">
        <details class="sga-aulas-picker" id="sga-aulas-picker">
          <summary aria-label="Seleccionar jornadas y aulas para habilitar">
            <span class="sga-aulas-picker-label" id="sga-aulas-resumen" aria-live="polite">Seleccionar jornadas y aulas</span>
          </summary>
          <div class="sga-aulas-picker-panel" id="sga-aulas-panel">
            <div class="sga-aulas-seleccion-barra">
              <label class="sga-aulas-seleccionar-todas" for="sga-aulas-marcar-todas">
                <input type="checkbox" id="sga-aulas-marcar-todas">
                <span>Todas las aulas</span>
              </label>
              <span class="mini-note" id="sga-aulas-contador" aria-live="polite">0 de <?=count($aulasFiltradas)?> seleccionadas</span>
            </div>
            <div role="group" aria-label="Seleccionar por jornada o por aula">
              <?php foreach ($jornadasDisponibles as $jid=>$nombreJornada):
                  $aulasDeJornada = array_filter($aulasFiltradas, static function($a) use ($jid) {
                      return (int)($a['jornada_id'] ?? 0) === (int)$jid;
                  });
                  if (!$aulasDeJornada) continue;
              ?>
                <div class="sga-aulas-jornada" data-jornada="<?=(int)$jid?>">
                  <label class="sga-aulas-jornada-label">
                    <input type="checkbox" class="sga-aulas-check-jornada" aria-label="Seleccionar todas las aulas de <?=e($nombreJornada)?>">
                    <strong><?=e($nombreJornada)?></strong>
                    <small class="sga-aulas-grupo-contador">0 / <?=count($aulasDeJornada)?> aulas</small>
                  </label>
                  <div class="sga-aulas-seleccion-grid" role="group" aria-label="Aulas de <?=e($nombreJornada)?>">
                    <?php foreach ($aulasDeJornada as $a):
                        $estado = $estadoAulas[(int)$a['id']] ?? null;
                    ?>
                      <label class="sga-aulas-seleccion-item">
                        <input type="checkbox" name="aula_ids[]" value="<?=(int)$a['id']?>" aria-label="<?=e('Seleccionar '.$a['nivel'].' '.$a['nombre'].' '.$a['paralelo'].' - '.$a['jornada'])?>">
                        <span class="sga-aulas-seleccion-item-text">
                          <strong><?=e($a['nivel'].' · '.$a['nombre'].' '.$a['paralelo'])?></strong>
                        </span>
                        <?php if ($estado === 1): ?>
                        <span class="badge good">Habilitada</span>
                        <?php elseif ($estado === 0): ?>
                        <span class="badge warn">Inactiva</span>
                        <?php else: ?>
                        <span class="badge">Pendiente</span>
                        <?php endif; ?>
                      </label>
                    <?php endforeach; ?>
                  </div>
                </div>
              <?php endforeach; ?>
            </div>
            <p class="sga-aulas-picker-note">Las casillas de cada jornada seleccionan todos sus paralelos. Puedes desmarcar aulas específicas. El menú flota sobre la página y no la desplaza.</p>
          </div>
        </details>
        <button class="btn btn-primary" type="submit" id="sga-aulas-habilitar-lote" data-confirm="¿Habilitar o reactivar las aulas seleccionadas en este período?">Habilitar seleccionadas</button>
      </div>
    </form>
  <?php endif; ?>
  </div>
</section>

<h2 class="section-title">Aulas del período</h2>
<link rel="stylesheet" href="<?=e(url('assets/css/sga_listas_compactas_v1614.css'))?>">
<style>
/* Dar cabida a las tres métricas sin desbordar en pantallas pequeñas. */
.sga-listas-fila--academico .sga-listas-metricas{flex:0 1 270px;min-width:180px;gap:5px 12px}
@media(max-width:610px){.sga-listas-fila--academico .sga-listas-metricas{flex:1 1 100%;min-width:0}}
</style>

<?php if (!$filas): ?>
  <div class="card empty">Aún no hay aulas habilitadas en este período.</div>
<?php else: ?>
  <div class="sga-listas-compactas" role="list" aria-label="Aulas habilitadas en el período">
    <?php foreach ($filas as $f): ?>
    <article class="sga-listas-fila sga-listas-fila--academico" role="listitem">
      <div class="sga-listas-identidad">
        <strong class="sga-listas-titulo"><?=e($f['nombre'].' '.$f['paralelo'])?></strong>
        <span class="sga-listas-subtitulo"><?=e($f['nivel'].' · '.($f['jornada']??'Sin jornada'))?></span>
      </div>
      <div class="sga-listas-metricas" aria-label="Datos del aula">
        <span class="sga-listas-metrica"><strong><?=(int)$f['estudiantes']?></strong> <?=(int)$f['estudiantes']===1?'estudiante':'estudiantes'?></span>
        <span class="sga-listas-metrica"><?php if(!empty($f['evaluacion_cualitativa_parametros'])):?>Por parámetros<?php else:?><strong><?=(int)$f['asignaturas']?></strong> <?=(int)$f['asignaturas']===1?'asignatura':'asignaturas'?><?php endif;?></span>
        <span class="sga-listas-metrica"><strong><?=(int)$f['docentes']?></strong> <?=(int)$f['docentes']===1?'docente':'docentes'?></span>
      </div>
      <div class="sga-listas-estado"><span class="badge <?=$f['activo']?'good':'bad'?>"><?=$f['activo']?'Activa':'Inactiva'?></span></div>
      <div class="sga-listas-acciones" aria-label="Acciones para <?=e($f['nombre'].' '.$f['paralelo'])?>">
        <a class="btn btn-primary btn-sm" href="<?=e(url('modulos/academico/aula.php?id='.(int)$f['id']))?>">Administrar aula</a>
        <form method="post">
          <input type="hidden" name="csrf" value="<?=e($csrfAulas)?>">
          <input type="hidden" name="accion" value="toggle">
          <input type="hidden" name="periodo_id" value="<?=$periodoId?>">
          <input type="hidden" name="filtro_jornada" value="<?=$filtroJornada?>">
          <input type="hidden" name="id" value="<?=(int)$f['id']?>">
          <button class="btn btn-sm <?=$f['activo']?'btn-secondary':'btn-success'?>" data-confirm="¿Cambiar el estado de esta aula en el periodo?"><?=$f['activo']?'Desactivar':'Activar'?></button>
        </form>
        <form method="post">
          <input type="hidden" name="csrf" value="<?=e($csrfAulas)?>">
          <input type="hidden" name="accion" value="eliminar">
          <input type="hidden" name="periodo_id" value="<?=$periodoId?>">
          <input type="hidden" name="filtro_jornada" value="<?=$filtroJornada?>">
          <input type="hidden" name="id" value="<?=(int)$f['id']?>">
          <button class="btn btn-danger btn-sm" data-confirm="Solo se eliminara si no tiene matriculas, asignaturas ni datos electorales. ¿Continuar?">Eliminar</button>
        </form>
      </div>
    </article>
    <?php endforeach; ?>
  </div>
<?php endif; ?>
<script>
(function(){
  'use strict';
  const form = document.getElementById('sga-habilitar-aulas-lote');
  if (!form) return;
  const picker = document.getElementById('sga-aulas-picker');
  const panel = document.getElementById('sga-aulas-panel');
  const items = Array.from(form.querySelectorAll('input[name="aula_ids[]"]'));
  const master = document.getElementById('sga-aulas-marcar-todas');
  const counter = document.getElementById('sga-aulas-contador');
  const submit = document.getElementById('sga-aulas-habilitar-lote');
  const resumen = document.getElementById('sga-aulas-resumen');
  const grupos = Array.from(form.querySelectorAll('.sga-aulas-jornada')).map(el => ({
    el,
    casilla: el.querySelector('.sga-aulas-check-jornada'),
    contador: el.querySelector('.sga-aulas-grupo-contador'),
    items: Array.from(el.querySelectorAll('input[name="aula_ids[]"]')),
    nombre: el.querySelector('strong').textContent.trim()
  }));

  function actualizar(){
    const elegidas = items.filter(c => c.checked);
    const n = elegidas.length;
    master.checked = n === items.length && items.length > 0;
    master.indeterminate = n > 0 && n < items.length;
    counter.textContent = n+' de '+items.length+' seleccionada'+(n===1?'':'s');
    for (const g of grupos) {
      const cantidad = g.items.filter(c => c.checked).length;
      g.casilla.checked = cantidad === g.items.length && g.items.length > 0;
      g.casilla.indeterminate = cantidad > 0 && cantidad < g.items.length;
      g.contador.textContent = cantidad+' / '+g.items.length+' aulas';
    }
    if (n === 0) resumen.textContent = 'Seleccionar jornadas y aulas';
    else if (n === items.length) resumen.textContent = 'Todas las aulas ('+n+')';
    else if (n === 1) resumen.textContent = elegidas[0].closest('label').querySelector('strong').textContent.trim();
    else {
      const completo = grupos.find(g => g.items.length === n && g.items.every(c => c.checked));
      resumen.textContent = completo ? (completo.nombre+' · '+n+' aulas') : (n+' aulas seleccionadas');
    }
    submit.disabled = n < 1 || n > 500;
    submit.title = n > 500 ? 'Selecciona un máximo de 500 aulas' : '';
  }

  master.addEventListener('change', () => {
    items.forEach(c => { c.checked = master.checked; });
    actualizar();
  });
  grupos.forEach(g => g.casilla.addEventListener('change', () => {
    g.items.forEach(c => { c.checked = g.casilla.checked; });
    actualizar();
  }));
  items.forEach(c => c.addEventListener('change', actualizar));

  // Ajustar arriba o abajo de la cabecera sin modificar la altura del padre.
  function posicionarFlotante(){
    if (!picker.open) return;
    const rect = picker.getBoundingClientRect();
    const abajo = Math.max(0, window.innerHeight - rect.bottom - 12);
    const arriba = Math.max(0, rect.top - 12);
    const abrirArriba = abajo < 240 && arriba > abajo;
    picker.classList.toggle('sga-aulas-abre-arriba', abrirArriba);
    const espacio = abrirArriba ? arriba : abajo;
    panel.style.maxHeight = Math.max(100, Math.min(470, espacio))+'px';
  }
  picker.addEventListener('toggle', () => {
    if (picker.open) posicionarFlotante();
    else picker.classList.remove('sga-aulas-abre-arriba');
  });
  window.addEventListener('resize', posicionarFlotante);
  window.addEventListener('scroll', posicionarFlotante, {passive:true});
  document.addEventListener('pointerdown', ev => {
    if (picker.open && !picker.contains(ev.target)) picker.open = false;
  });
  document.addEventListener('keydown', ev => {
    if (ev.key === 'Escape' && picker.open) {
      picker.open = false;
      picker.querySelector('summary').focus();
    }
  });
  actualizar();
})();
</script>
<?php if ($soloLectura): ?>
<script>
(function(){
  document.querySelectorAll('main form[method="post"] input:not([type="hidden"]), main form[method="post"] select, main form[method="post"] button')
    .forEach(function(control){control.disabled = true;});
})();
</script>
<?php endif; ?>
<?php require __DIR__.'/../../partials/footer.php'; ?>
