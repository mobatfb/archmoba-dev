<?php
require_once __DIR__ . '/../../lib/sga_supletorios.php';
exigirLogin();

// El rol activo del subadministrador se respeta al escoger el periodo.
$periodosTodos = $conexion->query('SELECT id,nombre,estado,anio_inicio,fecha_fin FROM periodos_academicos ORDER BY anio_inicio DESC,id DESC')->fetch_all(MYSQLI_ASSOC);
$periodos = [];
foreach ($periodosTodos as $pItem) {
    if (sgaSupPuedeVerPeriodo((int)$pItem['id'])) $periodos[] = $pItem;
}
$periodoActual = periodoActivo();
$solicitado = isset($_GET['periodo_id']);
if ($solicitado && (!ctype_digit((string)$_GET['periodo_id']) || (int)$_GET['periodo_id'] < 1)) {
    http_response_code(400); exit('El período solicitado no es válido.');
}
$periodoId = $solicitado ? (int)$_GET['periodo_id'] : (int)($periodoActual['id'] ?? 0);
$idsPermitidos = array_map('intval', array_column($periodos, 'id'));
if (!$solicitado && !in_array($periodoId, $idsPermitidos, true)) {
    $periodoId = $idsPermitidos[0] ?? 0;
}
if ($solicitado && !in_array($periodoId, $idsPermitidos, true)) {
    http_response_code(403); exit('No tienes acceso al periodo académico seleccionado.');
}
$periodoSeleccionado = null;
foreach ($periodos as $item) {
    if ((int)$item['id'] === $periodoId) { $periodoSeleccionado = $item; break; }
}
$cerrado = $periodoSeleccionado && $periodoSeleccionado['estado'] === 'cerrado';
$esAdminSup = esAdminAcademico();
$config = $periodoId ? obtenerConfiguracion($periodoId) : [
    'ponderacion_aportes' => .70, 'ponderacion_sumativa' => .30,
    'nota_aprobacion' => 7.00, 'nota_min_supletorio' => 4.00,
];

$ofertaId = max(0, (int)($_GET['oferta_id'] ?? 0));
$busqueda = trim((string)($_GET['q'] ?? ''));
$busqueda = substr($busqueda, 0, 100);
$filtrarOfertas = (string)($_GET['ver'] ?? 'casos');
if (!in_array($filtrarOfertas, ['casos','pendientes','todas'], true)) $filtrarOfertas = 'casos';
$filtrarEstudiantes = (string)($_GET['estado'] ?? 'casos');
if (!in_array($filtrarEstudiantes, ['casos','pendientes','registrados','todos'], true)) $filtrarEstudiantes = 'casos';

$ofertas = [];
$detalle = [];
$cuentas = ['asignaturas'=>0, 'casos'=>0, 'pendientes'=>0, 'registrados'=>0, 'aprobados'=>0];
if ($periodoId) {
    $sql = "SELECT o.id oferta_id, ap.id aula_periodo_id,
       a.nivel, a.nombre aula, a.paralelo, a.resultados_cualitativos, j.nombre jornada,
       s.nombre asignatura, s.codigo asignatura_codigo, s.usa_literal_especial,
       du.nombres docente_nombres, du.apellidos docente_apellidos,
       m.id matricula_id, m.numero_lista,
       eu.cedula estudiante_cedula, eu.nombres estudiante_nombres, eu.apellidos estudiante_apellidos,
       ct1.nota_final t1, ct2.nota_final t2, ct3.nota_final t3,
       nf.examen_supletorio
     FROM ofertas_academicas o
     JOIN aulas_periodo ap ON ap.id=o.aula_periodo_id
     JOIN aulas a ON a.id=ap.aula_id
     LEFT JOIN jornadas j ON j.id=a.jornada_id
     JOIN asignaturas s ON s.id=o.asignatura_id
     JOIN areas ar ON ar.id=s.area_id
     JOIN usuarios du ON du.id=o.docente_id
     LEFT JOIN matriculas m ON m.aula_periodo_id=ap.id AND m.estado='activo'
     LEFT JOIN usuarios eu ON eu.id=m.estudiante_id
     LEFT JOIN calificaciones_trimestre ct1 ON ct1.matricula_id=m.id AND ct1.oferta_id=o.id AND ct1.trimestre=1
     LEFT JOIN calificaciones_trimestre ct2 ON ct2.matricula_id=m.id AND ct2.oferta_id=o.id AND ct2.trimestre=2
     LEFT JOIN calificaciones_trimestre ct3 ON ct3.matricula_id=m.id AND ct3.oferta_id=o.id AND ct3.trimestre=3
     LEFT JOIN notas_finales nf ON nf.matricula_id=m.id AND nf.oferta_id=o.id
     WHERE ap.periodo_id=? AND ap.activo=1 AND o.activo=1 AND s.solo_visor_comportamiento=0 AND ap.evaluacion_cualitativa_parametros=0 AND o.evaluacion_aula=0 AND o.evaluacion_parametros_historica=0 AND s.archivado_en IS NULL AND ar.archivado_en IS NULL";
    if (!$esAdminSup) $sql .= ' AND o.docente_id=?';
    $sql .= filtroJornadasSQL($periodoId, 'a');
    $sql .= ' ORDER BY COALESCE(j.orden,9999),COALESCE(a.orden,9999),a.nombre,a.paralelo,s.nombre,o.id,COALESCE(m.numero_lista,9999),eu.apellidos,eu.nombres';
    $stmt = $conexion->prepare($sql);
    if (!$stmt) {http_response_code(500); exit('No se pudo consultar las asignaturas.');}
    if ($esAdminSup) $stmt->bind_param('i', $periodoId);
    else {
        $uid = (int)$_SESSION['usuario_id'];
        $stmt->bind_param('ii', $periodoId, $uid);
    }
    sgaEjecutar($stmt, 'consultar asignaturas para supletorios');
    $rows = $stmt->get_result();
    while ($row = $rows->fetch_assoc()) {
        $oid = (int)$row['oferta_id'];
        if (!isset($ofertas[$oid])) {
            $ofertas[$oid] = [
                'id' => $oid, 'asignatura' => $row['asignatura'],
                'aula_periodo_id' => (int)$row['aula_periodo_id'],
                'nivel' => $row['nivel'], 'aula' => $row['aula'],
                'paralelo' => $row['paralelo'], 'jornada' => $row['jornada'] ?? '',
                'docente' => trim($row['docente_apellidos'].' '.$row['docente_nombres']),
                'especial' => (bool)$row['usa_literal_especial'],
                'resultados_cualitativos' => (bool)$row['resultados_cualitativos'],
                'matriculados' => 0, 'casos' => 0, 'pendientes' => 0,
                'registrados' => 0, 'aprobados' => 0, 'incompletos' => 0,
            ];
        }
        if ((int)($row['matricula_id'] ?? 0) <= 0) continue;
        $ofertas[$oid]['matriculados']++;
        $estado = sgaSupCalcularEstado($row, $config);
        if (!$estado['completo']) $ofertas[$oid]['incompletos']++;
        if ($estado['aplica']) {
            $ofertas[$oid]['casos']++;
            if (!$estado['registrado']) $ofertas[$oid]['pendientes']++;
            else {
                $ofertas[$oid]['registrados']++;
                if ($estado['estado'] === 'aprobado') $ofertas[$oid]['aprobados']++;
            }
        }
        if ($oid === $ofertaId) $detalle[] = ['datos'=>$row, 'estado'=>$estado];
    }
    $stmt->close();
    $cuentas['asignaturas'] = count($ofertas);
    foreach ($ofertas as $o) {
        foreach (['casos','pendientes','registrados','aprobados'] as $clave) $cuentas[$clave] += $o[$clave];
    }
}
if ($ofertaId && !isset($ofertas[$ofertaId])) {
    http_response_code(403); exit('La asignatura solicitada no está disponible para tu usuario o periodo.');
}
if ($ofertaId && !puedeGestionarOferta($ofertaId)) {
    http_response_code(403); exit('No tienes autorización para esta asignatura.');
}

$ofertasVisibles = [];
foreach ($ofertas as $o) {
    if ($filtrarOfertas === 'casos' && !$o['casos']) continue;
    if ($filtrarOfertas === 'pendientes' && !$o['pendientes']) continue;
    if ($busqueda !== '' && stripos(implode(' ', [$o['asignatura'],$o['nivel'],$o['aula'],$o['paralelo'],$o['jornada'],$o['docente']]), $busqueda) === false) continue;
    $ofertasVisibles[] = $o;
}
if ($ofertaId) {
    $detalle = array_values(array_filter($detalle, static function(array $fila) use ($filtrarEstudiantes): bool {
        $est = $fila['estado'];
        if ($filtrarEstudiantes === 'todos') return true;
        if ($filtrarEstudiantes === 'casos') return $est['aplica'];
        if ($filtrarEstudiantes === 'pendientes') return $est['aplica'] && !$est['registrado'];
        return $est['aplica'] && $est['registrado'];
    }));
}

$tituloPagina = 'Supletorios';
$subtituloPagina = 'Evaluación supletoria de cierre anual, consolidada por asignatura y paralelo.';
$sgaEstilosSupletorios = true;
$csrf = sgaSupCsrf();
require __DIR__.'/../../partials/header.php';
?>
<?php if (!$periodos): ?>
<div class="notice">No hay períodos académicos disponibles para consultar supletorios.</div>
<?php else: ?>
<div class="sga-sup-topline">
    <div class="sga-sup-description">
        <strong>Control anual de supletorios</strong>
        <span>Se detectan a partir del promedio de los tres trimestres. Las notas originales no se reemplazan.</span>
    </div>
    <?php if ($ofertaId): ?>
    <a class="btn btn-secondary btn-sm" href="<?=e(url('modulos/supletorios/index.php?periodo_id='.$periodoId))?>">Volver a asignaturas</a>
    <?php endif; ?>
</div>
<?php if ($cerrado): ?>
<div class="notice" role="status"><strong>Período cerrado · solo consulta.</strong> No se pueden registrar, editar ni eliminar supletorios.</div>
<?php endif; ?>
<div class="sga-sup-metrics" aria-label="Resumen del período">
    <span><strong><?=$cuentas['asignaturas']?></strong> asignaturas</span>
    <span><strong><?=$cuentas['casos']?></strong> casos detectados</span>
    <span><strong><?=$cuentas['pendientes']?></strong> pendientes</span>
    <span><strong><?=$cuentas['registrados']?></strong> evaluados</span>
    <span><strong><?=$cuentas['aprobados']?></strong> aprobados</span>
</div>
<div class="sga-sup-tools">
    <form method="get" action="<?=e(url('modulos/supletorios/index.php'))?>" class="sga-sup-filter">
        <label>Período
            <select name="periodo_id" id="sga-sup-periodo" onchange="this.form.submit()">
                <?php foreach ($periodos as $p): ?>
                <option value="<?=(int)$p['id']?>" <?=(int)$p['id']===$periodoId?'selected':''?>><?=e($p['nombre'].' · '.$p['estado'])?></option>
                <?php endforeach; ?>
            </select>
        </label>
        <label>Buscar asignatura o aula
            <input type="search" name="q" value="<?=e($busqueda)?>" placeholder="Nombre, aula o docente">
        </label>
        <label>Mostrar
            <select name="ver">
                <option value="casos" <?=$filtrarOfertas==='casos'?'selected':''?>>Con supletorios</option>
                <option value="pendientes" <?=$filtrarOfertas==='pendientes'?'selected':''?>>Solo pendientes</option>
                <option value="todas" <?=$filtrarOfertas==='todas'?'selected':''?>>Todas las asignaturas</option>
            </select>
        </label>
        <button class="btn btn-primary" type="submit">Buscar</button>
    </form>
</div>
<?php if (!$ofertasVisibles): ?>
<div class="sga-sup-empty">No se encontraron asignaturas para el filtro seleccionado. Si aún faltan calificaciones, consulta <strong>Todas las asignaturas</strong>.</div>
<?php else: ?>
<div class="table-wrap sga-sup-table-wrap">
    <table class="table sga-sup-table">
        <thead><tr><th>Asignatura</th><th>Aula / Jornada</th><?php if ($esAdminSup): ?><th>Docente</th><?php endif; ?><th>Matriculados</th><th>Pendientes</th><th>Evaluados</th><th>Acción</th></tr></thead>
        <tbody>
        <?php foreach ($ofertasVisibles as $o): ?>
        <tr class="<?=$ofertaId===$o['id']?'sga-sup-row-selected':''?>">
            <td data-label="Asignatura"><strong><?=e($o['asignatura'])?></strong></td>
            <td data-label="Aula / Jornada"><?=e(trim($o['nivel'].' · '.$o['aula'].' '.$o['paralelo']))?><span class="sga-sup-secondary"><?=e($o['jornada'] ?: 'Jornada sin especificar')?></span></td>
            <?php if ($esAdminSup): ?><td data-label="Docente"><?=e($o['docente'])?></td><?php endif; ?>
            <td data-label="Matriculados"><?= (int)$o['matriculados'] ?></td>
            <td data-label="Pendientes"><span class="sga-sup-num <?=$o['pendientes']?'sga-sup-num-warn':''?>"><?=(int)$o['pendientes']?></span></td>
            <td data-label="Evaluados"><?= (int)$o['registrados'] ?></td>
            <td data-label="Acción"><a class="btn btn-sm <?=$ofertaId===$o['id']?'btn-secondary':'btn-primary'?>" href="<?=e(url('modulos/supletorios/index.php?periodo_id='.$periodoId.'&oferta_id='.$o['id'].'&estado=casos#sga-sup-estudiantes'))?>">Ver estudiantes</a></td>
        </tr>
        <?php endforeach; ?>
        </tbody>
    </table>
</div>
<?php endif; ?>

<?php if ($ofertaId): $seleccionada=$ofertas[$ofertaId]; ?>
<section class="sga-sup-detail" id="sga-sup-estudiantes">
    <div class="sga-sup-detail-header">
        <div>
            <h2><?=e($seleccionada['asignatura'])?></h2>
            <p><?=e($seleccionada['nivel'].' · '.$seleccionada['aula'].' '.$seleccionada['paralelo'].' · '.$seleccionada['jornada'])?> <span aria-hidden="true">·</span> <?=(int)$seleccionada['casos']?> casos</p>
        </div>
        <div class="sga-sup-detail-actions">
            <a class="btn btn-secondary btn-sm" href="<?=e(url('modulos/calificaciones/finales.php?oferta_id='.$ofertaId))?>">Ver consolidado final</a>
        </div>
    </div>
    <form method="get" action="<?=e(url('modulos/supletorios/index.php'))?>" class="sga-sup-state-form">
        <input type="hidden" name="periodo_id" value="<?=$periodoId?>">
        <input type="hidden" name="oferta_id" value="<?=$ofertaId?>">
        <label for="sga-sup-estado">Mostrar estudiantes</label>
        <select name="estado" id="sga-sup-estado" onchange="this.form.submit()">
            <option value="casos" <?=$filtrarEstudiantes==='casos'?'selected':''?>>Todos con supletorio</option>
            <option value="pendientes" <?=$filtrarEstudiantes==='pendientes'?'selected':''?>>Pendientes de rendir</option>
            <option value="registrados" <?=$filtrarEstudiantes==='registrados'?'selected':''?>>Con nota registrada</option>
            <option value="todos" <?=$filtrarEstudiantes==='todos'?'selected':''?>>Todos los matriculados</option>
        </select>
        <noscript><button class="btn btn-secondary btn-sm">Aplicar</button></noscript>
    </form>
    <?php if (!$detalle): ?>
    <div class="sga-sup-empty">No hay estudiantes en esta asignatura con el estado seleccionado. Puedes cambiar el filtro para consultar otras situaciones.</div>
    <?php else: ?>
    <div class="table-wrap sga-sup-table-wrap">
        <table class="table sga-sup-table sga-sup-student-table">
            <thead><tr><th>No.</th><th>Estudiante</th><th>T1</th><th>T2</th><th>T3</th><th>Prom. anual</th><th>Supletorio</th><th>Nota final</th><th>Situación</th><th>Acciones</th></tr></thead>
            <tbody>
            <?php foreach($detalle as $i => $item):
                $r=$item['datos'];$est=$item['estado'];$fin=$est['resultado'];
                $nombre=trim($r['estudiante_apellidos'].' '.$r['estudiante_nombres']);
                $estadoN=$est['estado'];
                $mostrarResultado=static fn($nota)=>$nota===null?'—':sgaNotaResultadoParaConsulta((float)$nota,!empty($r['resultados_cualitativos']));
                $labels=['pendiente'=>'Pendiente','aprobado'=>'Aprobado','no_aprobado'=>'No aprobado','incompleto'=>'Faltan notas','no_aplica'=>'No requiere','revisar'=>'Revisar nota'];
            ?>
            <tr>
                <td data-label="No."><?=e($r['numero_lista']?:($i+1))?></td>
                <td data-label="Estudiante"><strong><?=e($nombre)?></strong><span class="sga-sup-secondary"><?=e($r['estudiante_cedula'])?></span></td>
                <td data-label="T1" title="<?=e($est['t1']===null?'':fmt($est['t1']))?>"><?=e($mostrarResultado($est['t1']))?></td>
                <td data-label="T2"><?=e($mostrarResultado($est['t2']))?></td>
                <td data-label="T3"><?=e($mostrarResultado($est['t3']))?></td>
                <td data-label="Prom. anual"><strong><?=e($mostrarResultado($fin['promedio_tres']))?></strong></td>
                <td data-label="Supletorio"><?=e($mostrarResultado($est['supletorio']))?></td>
                <td data-label="Nota final"><strong><?=e($mostrarResultado($fin['promedio_final']))?></strong></td>
                <td data-label="Situación"><span class="sga-sup-status sga-sup-status-<?=e($estadoN)?>"><?=e($labels[$estadoN]??$estadoN)?></span></td>
                <td data-label="Acciones">
                    <div class="sga-sup-row-actions">
                        <?php if (!$cerrado && $est['aplica']): ?>
                        <button type="button" class="btn btn-sm <?=$est['registrado']?'btn-secondary':'btn-primary'?>"
                            data-sga-sup-editar
                            data-matricula="<?=(int)$r['matricula_id']?>"
                            data-estudiante="<?=e($nombre)?>"
                            data-t1="<?=e($est['t1']===null?'':fmt($est['t1']))?>"
                            data-t2="<?=e($est['t2']===null?'':fmt($est['t2']))?>"
                            data-t3="<?=e($est['t3']===null?'':fmt($est['t3']))?>"
                            data-promedio="<?=e(fmt($fin['promedio_tres']))?>"
                            data-anterior="<?=e($est['supletorio']===null?'':fmt($est['supletorio']))?>"
                            data-aprobado="<?=e(fmt($config['nota_aprobacion']))?>"><?=$est['registrado']?'Editar':'Registrar'?></button>
                        <?php endif; ?>
                        <?php if (!$cerrado && $est['supletorio']!==null): ?>
                        <form method="post" action="<?=e(url('modulos/supletorios/eliminar.php'))?>" class="sga-sup-inline-form">
                            <input type="hidden" name="csrf" value="<?=e($csrf)?>">
                            <input type="hidden" name="oferta_id" value="<?=$ofertaId?>">
                            <input type="hidden" name="matricula_id" value="<?=(int)$r['matricula_id']?>">
                            <button class="btn btn-danger btn-sm" type="submit" data-confirm="¿Quitar la nota de supletorio de <?=e($nombre)?>? Las calificaciones trimestrales no se borrarán.">Quitar nota</button>
                        </form>
                        <?php endif; ?>
                        <?php if ($cerrado || (!$est['aplica'] && $est['supletorio']===null)): ?>
                        <span class="sga-sup-secondary">—</span>
                        <?php endif; ?>
                    </div>
                </td>
            </tr>
            <?php endforeach; ?>
            </tbody>
        </table>
    </div>
    <?php endif; ?>
</section>
<?php endif; ?>
<details class="sga-sup-help">
    <summary>¿Cuándo corresponde un examen supletorio?</summary>
    <p>Es una evaluación de <strong>cierre del año lectivo</strong>, no de cada trimestre. El sistema necesita las tres notas trimestrales y utiliza la configuración de aprobación del período (mínimo para supletorio: <strong><?=fmt($config['nota_min_supletorio'])?></strong>; nota de aprobación: <strong><?=fmt($config['nota_aprobacion'])?></strong>). La calificación original se conserva.</p>
    <p>Cuando se aprueba el supletorio, la nota final de la asignatura se fija en <?=fmt($config['nota_aprobacion'])?>. Si no se aprueba, se mantiene el promedio anual y se muestra el resultado académico correspondiente. Verifica las disposiciones aplicables a cada nivel educativo antes de cerrar el período.</p>
</details>
<?php endif; ?>

<?php if ($ofertaId && !$cerrado && $periodoId): ?>
<dialog class="sga-sup-dialog" id="sga-sup-modal" data-escala-cualitativa="<?=e(json_encode(sgaEscalaResultadosCualitativos()))?>" data-resultados-cualitativos="<?=!empty($seleccionada['resultados_cualitativos'])?1:0?>" aria-labelledby="sga-sup-modal-titulo" aria-describedby="sga-sup-modal-descripcion">
    <div class="sga-sup-dialog-head">
        <div>
            <h2 id="sga-sup-modal-titulo">Registrar supletorio</h2>
            <p id="sga-sup-modal-descripcion">Registra la calificación del examen final de recuperación.</p>
        </div>
        <button type="button" class="sga-sup-close" data-sga-sup-cerrar aria-label="Cerrar ventana">&times;</button>
    </div>
    <div class="sga-sup-dialog-body">
        <p class="sga-sup-student-name" id="sga-sup-modal-estudiante"></p>
        <div class="sga-sup-notes" aria-label="Calificaciones originales">
            <span>T1 <strong id="sga-sup-modal-t1">—</strong></span>
            <span>T2 <strong id="sga-sup-modal-t2">—</strong></span>
            <span>T3 <strong id="sga-sup-modal-t3">—</strong></span>
            <span>Promedio anual <strong id="sga-sup-modal-anual">—</strong></span>
        </div>
        <form method="post" action="<?=e(url('modulos/supletorios/guardar.php'))?>" id="sga-sup-modal-form">
            <input type="hidden" name="csrf" value="<?=e($csrf)?>">
            <input type="hidden" name="oferta_id" value="<?=$ofertaId?>">
            <input type="hidden" name="matricula_id" id="sga-sup-matricula" value="">
            <label for="sga-sup-nota">Nota del examen supletorio (/10)
                <input type="number" id="sga-sup-nota" name="nota" min="0.01" max="10" step="0.01" inputmode="decimal" placeholder="Ej.: 8.50" required>
            </label>
            <p class="sga-sup-feedback" id="sga-sup-feedback" role="status">La nota final se actualizará al guardar, sin modificar los trimestres.</p>
            <div class="sga-sup-dialog-actions">
                <button type="button" class="btn btn-secondary" data-sga-sup-cerrar>Cancelar</button>
                <button type="submit" class="btn btn-primary">Guardar supletorio</button>
            </div>
        </form>
    </div>
</dialog>
<script src="<?=e(url('assets/js/sga_supletorios.js'))?>?v=20261124-6" defer></script>
<?php endif; ?>
<?php require __DIR__ . '/../../partials/footer.php'; ?>
