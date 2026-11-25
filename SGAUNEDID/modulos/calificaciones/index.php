<?php
require_once __DIR__.'/../../lib/funciones.php';
exigirLogin();
$oid=(int)($_GET['oferta_id']??0);
$trim=max(1,min(3,(int)($_GET['trimestre']??1)));
if (!$oid || !puedeGestionarOferta($oid)) { http_response_code(403); die('No tienes acceso a esta asignatura.'); }
$o=ofertaDetalle($oid);
if($o && !empty($o['aula_evaluacion_parametros']) && empty($o['evaluacion_aula']) && empty($o['evaluacion_cualitativa_parametros'])){http_response_code(403);die('El aula se evalúa por parámetros.');}
if($o && !empty($o['solo_visor_comportamiento'])) {
    redir('modulos/calificaciones/comportamiento.php?oferta_id='.$oid.'&trimestre='.$trim);
}
if($o && !empty($o['evaluacion_cualitativa_parametros'])) {
    redir('modulos/calificaciones/parametros.php?oferta_id='.$oid.'&trimestre='.$trim);
}
if (!$o) { http_response_code(404); die('Asignatura no encontrada.'); }
$soloLectura=($o['periodo_estado']??'')==='cerrado';
$config=obtenerConfiguracion((int)$o['periodo_id']);
$estado=obtenerEstadoAportes($oid,$trim);
$apid=(int)$o['aula_periodo_id'];
if (empty($_SESSION['csrf_calificaciones'])) $_SESSION['csrf_calificaciones']=bin2hex(random_bytes(24));
$csrf=$_SESSION['csrf_calificaciones'];
$stmt=$conexion->prepare("SELECT ct.*,m.id AS matricula_id,m.numero_lista,u.cedula,u.apellidos,u.nombres
  FROM matriculas m JOIN usuarios u ON u.id=m.estudiante_id
  LEFT JOIN calificaciones_trimestre ct ON ct.matricula_id=m.id AND ct.oferta_id=? AND ct.trimestre=?
  WHERE m.aula_periodo_id=? AND m.estado='activo'
  ORDER BY COALESCE(m.numero_lista,9999),u.apellidos,u.nombres");
$stmt->bind_param('iii',$oid,$trim,$apid);$stmt->execute();$rows=$stmt->get_result()->fetch_all(MYSQLI_ASSOC);$stmt->close();
function inNota(array $r,string $c):string {
    global $soloLectura;
    $mid=(int)($r['matricula_id']??0);
    $v=array_key_exists($c,$r)?$r[$c]:null;
    return '<input form="form-calificaciones" type="number" min="0" max="10" step="0.01"'
      .' data-field="'.e($c).'" aria-label="'.e(str_replace('_',' ',$c)).'"'
      .' name="notas['.$mid.']['.e($c).']" value="'.e(valorInput($v)).'"'.($soloLectura?' disabled':'').'>';
}
function apCelda(array $r,string $c,array $e):string {
    if(!aporteActivo($e,$c)) return '<span class="lock-cell" title="Aporte no utilizado">🔒</span>';
    if(!array_key_exists($c,$r)||$r[$c]===null||$r[$c]==='') $r[$c]=0.00;
    return inNota($r,$c);
}
function apHead(string $lab,string $c,array $e,int $oid,int $trim):string {
    global $soloLectura;
    $activo=aporteActivo($e,$c);
    if($soloLectura)return '<span title="Periodo cerrado: solo lectura">'.e($lab).' '.($activo?'✓':'🔒').'</span>';
    return '<div>'.e($lab).'<form method="post" action="'.e(url('modulos/calificaciones/cambiar_aporte.php')).'">'
      .'<input type="hidden" name="oferta_id" value="'.$oid.'">'
      .'<input type="hidden" name="trimestre" value="'.$trim.'">'
      .'<input type="hidden" name="campo" value="'.e($c).'">'
      .'<input type="hidden" name="activo" value="'.($activo?0:1).'">'
      .'<button class="lock-btn" title="'.($activo?'Bloquear':'Habilitar').'" aria-label="'.($activo?'Bloquear ':'Habilitar ').e($c).'">'.($activo?'🔓':'🔒').'</button></form></div>';
}
function gradeCell(array $r,string $campo,bool $resaltar=false,bool $fuerte=false):string {
    $n=(float)($r[$campo]??0);
    $class=$resaltar?($n<7?'grade-low':'grade-good'):'';
    $txt=fmt($n);
    return '<span data-grade="'.e($campo).'" class="'.$class.'">'.($fuerte?'<strong>':'').$txt.($fuerte?'</strong>':'').'</span>';
}
$tituloPagina='Calificaciones · '.$o['asignatura'];
$subtituloPagina=$o['nivel'].' · '.$o['aula'].' '.$o['paralelo'].' · '.$o['periodo'];
require __DIR__.'/../../partials/header.php';
?>
<?php if($soloLectura):?><div class="notice" role="status"><strong>Período cerrado · solo consulta.</strong> Las calificaciones guardadas permanecen visibles, pero no se pueden modificar, importar ni eliminar.</div><?php endif;?>
<div class="toolbar grade-toolbar">
  <div class="actions"><?php for($i=1;$i<=3;$i++):?>
    <a class="btn <?=$i===$trim?'btn-primary':'btn-secondary'?>" href="?oferta_id=<?=$oid?>&amp;trimestre=<?=$i?>"><?=$i?>.° trimestre</a>
  <?php endfor;?></div>
  <div class="actions">
    <a class="btn btn-secondary" href="<?=e(url('modulos/calificaciones/cursos.php'))?>">Asignaturas</a>
    <a class="btn btn-secondary" href="<?=e(url('modulos/calificaciones/finales.php?oferta_id='.$oid))?>">Finales</a>
    <a class="btn btn-secondary" href="<?=e(url('modulos/academico/lista.php?oferta_id='.$oid))?>">Lista</a>
    <a class="btn btn-success" href="<?=e(url('modulos/calificaciones/reporte_excel.php?oferta_id='.$oid))?>">Reporte Excel</a>
    <?php if(!$soloLectura):?><a class="btn btn-primary" href="<?=e(url('modulos/calificaciones/importar.php?oferta_id='.$oid.'&trimestre='.$trim))?>">Importar notas Excel</a><?php endif;?>
  </div>
</div>
<?php if(!empty($o['aula_resultados_cualitativos'])):?><div class="notice"><strong>Resultados cualitativos A+ a E-.</strong> Se ingresan notas numéricas; la letra se actualiza con la escala vigente. <details><summary>Consultar escala de equivalencias</summary><div style="display:flex;gap:12px;flex-wrap:wrap;padding:8px 0"><?php foreach(sgaEscalaResultadosCualitativos() as $nivel):?><span class="tag"><?=e($nivel['letra'])?>: <?=e(sgaRangoResultadoCualitativo($nivel['min']/100))?></span><?php endforeach;?></div><small>Notas registradas inferiores a 1,00: E-. Sin registro: pendiente.</small></details></div><?php endif;?>
<?php if(!$rows):?>
<div class="card empty">No hay estudiantes matriculados en este paralelo.</div>
<?php else:?>
<form id="form-calificaciones" method="post" action="<?=e(url('modulos/calificaciones/guardar.php'))?>">
  <input type="hidden" name="csrf" value="<?=e($csrf)?>">
  <input type="hidden" name="oferta_id" value="<?=$oid?>">
  <input type="hidden" name="trimestre" value="<?=$trim?>">
</form>
<div class="grade-workspace" id="grade-workspace" aria-label="Libro de calificaciones">
<div class="matrix-wrap grade-matrix-wrap" id="grade-matrix-wrap" role="region" aria-label="Tabla de calificaciones con desplazamiento horizontal" tabindex="0"
     data-escala-cualitativa="<?=e(json_encode(sgaEscalaResultadosCualitativos()))?>" data-pond-ap="<?=e((string)$config['ponderacion_aportes'])?>" data-pond-sum="<?=e((string)$config['ponderacion_sumativa'])?>">
<table class="matrix" id="grade-matrix">
<thead>
<tr><th class="dark frozen-number" rowspan="3">No.</th><th class="dark student frozen-student" rowspan="3">Estudiante</th>
    <th class="cyan" colspan="24">APORTES</th><th class="dark" colspan="2">PROM. APORTES</th>
    <th class="cyan" colspan="4">EVALUACIÓN SUMATIVA</th><th class="dark" colspan="2">PROM. PROYECTO</th>
    <th class="dark" colspan="2">FINAL</th><th class="dark" rowspan="3">GESTIÓN</th></tr>
<tr><th colspan="6">DEBERES</th><th colspan="6">TAREAS</th><th colspan="6">LECCIONES</th><th colspan="6">TRABAJO EN GRUPO</th>
    <th rowspan="2">/10</th><th rowspan="2"><?=round($config['ponderacion_aportes']*100)?>%</th>
    <th colspan="3">APORTE DISCIPLINAR</th><th>PRODUCTO FINAL</th>
    <th colspan="2">PONDERACIÓN SUMATIVA</th><th rowspan="2">NOTA</th><th rowspan="2">CUAL.</th></tr>
<tr>
<?php foreach([['deber','DEB'],['tarea','TAR'],['leccion','LEC'],['grupo','GRU']] as [$pre,$lab]):?>
    <th><?=apHead('AP1',$pre.'_ap1',$estado,$oid,$trim)?></th>
    <th><?=apHead('AP2',$pre.'_ap2',$estado,$oid,$trim)?></th>
    <th><?=apHead('AP3',$pre.'_ap3',$estado,$oid,$trim)?></th>
    <th>Prom.</th><th>Ref.</th><th>Prom. aporte</th>
<?php endforeach;?>
    <th>Nota disciplinar</th><th>Trabajo de refuerzo</th><th>Promedio disciplinar</th>
    <th>Nota producto final</th><th>Promedio</th><th>Ponderado <?=round($config['ponderacion_sumativa']*100)?>%</th>
</tr>
</thead>
<tbody>
<?php foreach($rows as $i=>$r):$mid=(int)$r['matricula_id'];$historico=esSumativaHistorica($r);?>
<tr data-matricula-id="<?=$mid?>" data-historico="<?=$historico?'1':'0'?>" data-pond-historico="<?=e((string)($r['ponderado_sumativa']??0))?>" data-prom-historico="<?=e((string)($r['promedio_proyecto']??0))?>" data-especial="<?=(int)($o['usa_literal_especial']??0)?>" data-resultados-cualitativos="<?=(int)($o['aula_resultados_cualitativos']??0)?>">
<td class="frozen-number"><?=e($r['numero_lista']?:($i+1))?></td>
<td class="student frozen-student"><strong><?=e($r['apellidos'].' '.$r['nombres'])?></strong><br><span class="muted"><?=e($r['cedula'])?></span><span class="grade-pending" hidden>Sin guardar</span></td>
<?php foreach(['deber','tarea','leccion','grupo'] as $pre):?>
    <td><?=apCelda($r,$pre.'_ap1',$estado)?></td><td><?=apCelda($r,$pre.'_ap2',$estado)?></td><td><?=apCelda($r,$pre.'_ap3',$estado)?></td>
    <td><?=gradeCell($r,$pre.'_promedio',true)?></td>
    <td><?=inNota($r,$pre.'_refuerzo')?></td>
    <td><?=gradeCell($r,$pre.'_promedio_aporte',true)?></td>
<?php endforeach;?>
<td><?=gradeCell($r,'promedio_aportes')?></td>
<td><?=gradeCell($r,'ponderado_aportes',false,true)?></td>
<td><?=inNota($r,'nota_disciplinar')?></td>
<td><?=inNota($r,'trabajo_refuerzo_disciplinar')?></td>
<td><?=gradeCell($r,'promedio_disciplinar')?></td>
<td><?=inNota($r,'nota_producto_final')?></td>
<td><?=gradeCell($r,'promedio_proyecto')?><?php if($historico):?><span class="grade-history" title="Se conserva la nota histórica si no se agregan nuevos componentes sumativos">Histórico</span><?php endif;?></td>
<td><?=gradeCell($r,'ponderado_sumativa',false,true)?></td>
<td><?=gradeCell($r,'nota_final',true,true)?></td>
<td><span data-grade="cualitativo"><?=e(isset($r['nota_final']) ? (!empty($o['aula_resultados_cualitativos']) ? sgaLetraResultadoCualitativo((float)$r['nota_final']) : cualitativo((float)$r['nota_final'],$o['asignatura'],!empty($o['usa_literal_especial']))) : '')?></span></td>
<td><div class="matrix-manage">
  <button class="btn btn-sm btn-primary" form="form-calificaciones" type="submit" name="guardar_matricula_id" value="<?=$mid?>" <?=$soloLectura?'disabled':''?>>Guardar</button>
  <form method="post" action="<?=e(url('modulos/calificaciones/eliminar_trimestre.php'))?>">
    <input type="hidden" name="csrf" value="<?=e($csrf)?>">
    <input type="hidden" name="oferta_id" value="<?=$oid?>">
    <input type="hidden" name="trimestre" value="<?=$trim?>">
    <input type="hidden" name="matricula_id" value="<?=$mid?>">
    <button class="btn btn-sm btn-danger" type="submit" <?=$soloLectura?'disabled':''?> data-confirm="¿Eliminar las calificaciones guardadas de este estudiante en el trimestre?">Limpiar</button>
  </form>
</div></td>
</tr>
<?php endforeach;?>
</tbody>
</table>
</div>
</div><!-- Fin de grade-workspace: scroll horizontal nativo y columnas fijas -->
<div class="savebar grade-savebar" id="grade-savebar">
  <span class="mini-note">Los promedios se actualizan al escribir. Guarda las notas para que queden registradas.</span>
  <div class="actions">
    <form id="form-limpiar-todo" method="post" action="<?=e(url('modulos/calificaciones/eliminar_todo.php'))?>">
      <input type="hidden" name="csrf" value="<?=e($csrf)?>">
      <input type="hidden" name="oferta_id" value="<?=$oid?>">
      <input type="hidden" name="trimestre" value="<?=$trim?>">
      <input type="hidden" name="confirmacion" id="confirmacion-limpiar-todo" value="">
      <button class="btn btn-danger" type="submit" id="btn-limpiar-todo" <?=$soloLectura?'disabled':''?>>Limpiar todo</button>
    </form>
    <button type="submit" form="form-calificaciones" class="btn btn-primary" <?=$soloLectura?'disabled':''?>>Guardar todo y recalcular</button>
  </div>
</div>
<script src="<?=e(url('assets/js/calificaciones.js'))?>?v=20261124-6" defer></script>
<?php endif;?>
<?php require __DIR__.'/../../partials/footer.php';?>
