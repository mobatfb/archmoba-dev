<?php
require_once __DIR__.'/../../lib/funciones.php';
exigirLogin();
$oid=(int)($_GET['oferta_id']??0);
if(!$oid||!puedeGestionarOferta($oid)){http_response_code(403);die('No tienes acceso a esta asignatura.');}
$o=ofertaDetalle($oid);
if(!$o){http_response_code(404);die('Asignatura no encontrada.');}
if(!empty($o['evaluacion_cualitativa_parametros'])) {
    redir('modulos/calificaciones/parametros.php?oferta_id='.$oid.'&vista=resumen');
}
if(!empty($o['aula_evaluacion_parametros'])){http_response_code(403);die('El aula se evalúa por parámetros.');}
$config=obtenerConfiguracion((int)$o['periodo_id']);$apid=(int)$o['aula_periodo_id'];
$cerrado=($o['periodo_estado']??'')==='cerrado';
$stmt=$conexion->prepare("SELECT m.id matricula_id,m.numero_lista,u.cedula,u.apellidos,u.nombres,
 c1.nota_final t1,c2.nota_final t2,c3.nota_final t3,nf.examen_supletorio
 FROM matriculas m JOIN usuarios u ON u.id=m.estudiante_id
 LEFT JOIN calificaciones_trimestre c1 ON c1.matricula_id=m.id AND c1.oferta_id=? AND c1.trimestre=1
 LEFT JOIN calificaciones_trimestre c2 ON c2.matricula_id=m.id AND c2.oferta_id=? AND c2.trimestre=2
 LEFT JOIN calificaciones_trimestre c3 ON c3.matricula_id=m.id AND c3.oferta_id=? AND c3.trimestre=3
 LEFT JOIN notas_finales nf ON nf.matricula_id=m.id AND nf.oferta_id=?
 WHERE m.aula_periodo_id=? AND m.estado='activo'
 ORDER BY COALESCE(m.numero_lista,9999),u.apellidos,u.nombres");
$stmt->bind_param('iiiii',$oid,$oid,$oid,$oid,$apid);sgaEjecutar($stmt,'consultar el consolidado final');
$rows=$stmt->get_result()->fetch_all(MYSQLI_ASSOC);$stmt->close();
$tituloPagina='Finales · '.$o['asignatura'];
$subtituloPagina=$o['nivel'].' · '.$o['aula'].' '.$o['paralelo'].' · '.$o['periodo'];
require __DIR__.'/../../partials/header.php';
?>
<div class="actions" style="margin-bottom:14px"><a class="btn btn-secondary" href="<?=e(url('modulos/calificaciones/index.php?oferta_id='.$oid))?>">Volver a trimestres</a><a class="btn btn-success" href="<?=e(url('modulos/calificaciones/reporte_excel.php?oferta_id='.$oid))?>">Reporte Excel</a></div>
<?php if($cerrado):?><div class="notice" role="status">Este período está cerrado. Sus calificaciones son de solo lectura.</div><?php endif;?>
<?php if(!$rows):?><div class="card empty">No hay estudiantes matriculados.</div><?php else:?>
<form method="post" action="<?=e(url('modulos/calificaciones/guardar_supletorio.php'))?>">
<input type="hidden" name="oferta_id" value="<?=$oid?>">
<div class="table-wrap"><table class="table final-table"><thead><tr><th>No.</th><th>Estudiante</th><th>T1</th><th>T2</th><th>T3</th><th>Prom. 3 trim.</th><th>Supletorio</th><th>Prom. final</th><th>Observación</th><th>Gestión</th></tr></thead><tbody>
<?php foreach($rows as $i=>$r):
  $t1=$r['t1']===null?null:(float)$r['t1'];
  $t2=$r['t2']===null?null:(float)$r['t2'];
  $t3=$r['t3']===null?null:(float)$r['t3'];
  $esComportamiento=!empty($o['solo_visor_comportamiento']);
  $sup=$esComportamiento?null:($r['examen_supletorio']===null?null:(float)$r['examen_supletorio']);
  $fin=calcularFinalAnual($t1,$t2,$t3,$sup,$config);
  $completo=$fin['trimestres_completos'];
  $aplica=!$esComportamiento && $completo && $fin['promedio_tres']>=(float)$config['nota_min_supletorio'] && $fin['promedio_tres']<(float)$config['nota_aprobacion'];
  $especial=!empty($o['usa_literal_especial']);
  $mostrar=static function(?float $nota) use ($especial,$o):string {
      if($nota===null)return '—';
      if(!empty($o['aula_resultados_cualitativos']))return sgaNotaResultadoParaConsulta($nota,true);
      return notaFinalVisible($nota,$especial,true);
  };
?>
<tr>
<td><?=e($r['numero_lista']?:($i+1))?></td>
<td><strong><?=e($r['apellidos'].' '.$r['nombres'])?></strong><br><span class="muted"><?=e($r['cedula'])?></span></td>
<td><?=$mostrar($t1)?></td><td><?=$mostrar($t2)?></td><td><?=$mostrar($t3)?></td>
<td><strong><?=$mostrar($fin['promedio_tres'])?></strong></td>
<td><?php if($aplica&&!$cerrado):?><input type="number" min="0.01" max="10" step="0.01" name="supletorio[<?=(int)$r['matricula_id']?>]" value="<?=e(valorInput($sup))?>" aria-label="Nota de supletorio para <?=e($r['apellidos'].' '.$r['nombres'])?>"><?php if(!empty($o['aula_resultados_cualitativos']) && $sup!==null):?> <strong><?=e(sgaLetraResultadoCualitativo($sup))?></strong><?php endif;?><?php else:?><span class="muted"><?=!$completo?'Pendiente de trimestres':($aplica?($sup===null?'Sin registrar':(!empty($o['aula_resultados_cualitativos'])?sgaLetraResultadoCualitativo($sup):fmt($sup))):'No aplica')?></span><?php endif;?></td>
<td><strong><?=$mostrar($fin['promedio_final'])?></strong></td>
<td><span class="badge <?=$fin['observacion']==='APROBADO'?'good':($fin['observacion']==='REPROBADO'?'bad':'warn')?>"><?=e($fin['observacion'])?></span></td>
<td><?php if($sup!==null&&!$cerrado&&!$esComportamiento):?><button class="btn btn-sm btn-danger" type="submit" formaction="<?=e(url('modulos/calificaciones/eliminar_supletorio.php'))?>" name="matricula_id" value="<?=(int)$r['matricula_id']?>" data-confirm="¿Eliminar la nota de supletorio?">Eliminar supletorio</button><?php else:?><span class="muted">—</span><?php endif;?></td>
</tr>
<?php endforeach;?></tbody></table></div>
<?php if(!$cerrado && empty($o['solo_visor_comportamiento'])):?><div class="savebar"><span class="mini-note">Solo se admiten supletorios cuando los tres trimestres están registrados y el promedio anual está entre <?=fmt($config['nota_min_supletorio'])?> y <?=fmt($config['nota_aprobacion'])?> (sin incluir el límite superior). Los vacíos no se modifican.</span><button class="btn btn-primary" type="submit">Guardar supletorios</button></div><?php endif;?>
</form>
<?php endif;?>
<?php require __DIR__.'/../../partials/footer.php';?>
