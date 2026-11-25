<?php
require_once __DIR__.'/../../lib/funciones.php';
require_once __DIR__.'/../../lib/comportamiento_trimestres.php';
exigirLogin();
$p=periodoActivo();$pid=(int)($p['id']??0);
if(!$pid||!esEstudianteOperativo($pid)){http_response_code(403);die('No tienes matrícula como estudiante en el periodo activo.');}
$uid=(int)$_SESSION['usuario_id'];
$stmt=$conexion->prepare("SELECT m.id matricula_id,m.aula_periodo_id,a.nivel,a.nombre aula,a.paralelo,a.resultados_cualitativos,ap.evaluacion_cualitativa_parametros FROM matriculas m JOIN aulas_periodo ap ON ap.id=m.aula_periodo_id JOIN aulas a ON a.id=ap.aula_id WHERE m.estudiante_id=? AND ap.periodo_id=? AND m.estado='activo' LIMIT 1");
$stmt->bind_param('ii',$uid,$pid);$stmt->execute();$m=$stmt->get_result()->fetch_assoc();$stmt->close();
$rows=[];$evals=[];$promedioGeneral=null;$comportamiento=[1=>null,2=>null,3=>null];
if($m){
  $apid=(int)$m['aula_periodo_id'];$mid=(int)$m['matricula_id'];$config=obtenerConfiguracion($pid);
  $stmt=$conexion->prepare("SELECT o.id,(o.evaluacion_aula=1 OR o.evaluacion_parametros_historica=1) por_parametros,s.nombre asignatura,s.usa_literal_especial,s.solo_visor_comportamiento,
    c1.nota_final t1,c2.nota_final t2,c3.nota_final t3,nf.examen_supletorio,
    c1.id t1_id,c2.id t2_id,c3.id t3_id,cb1.literal comp_t1,cb2.literal comp_t2,cb3.literal comp_t3
    FROM ofertas_academicas o
    JOIN asignaturas s ON s.id=o.asignatura_id
    LEFT JOIN calificaciones_trimestre c1 ON c1.oferta_id=o.id AND c1.matricula_id=? AND c1.trimestre=1
    LEFT JOIN calificaciones_trimestre c2 ON c2.oferta_id=o.id AND c2.matricula_id=? AND c2.trimestre=2
    LEFT JOIN calificaciones_trimestre c3 ON c3.oferta_id=o.id AND c3.matricula_id=? AND c3.trimestre=3
    LEFT JOIN notas_finales nf ON nf.oferta_id=o.id AND nf.matricula_id=?
    LEFT JOIN calificaciones_comportamiento_trimestre cb1 ON cb1.oferta_id=o.id AND cb1.matricula_id=? AND cb1.trimestre=1
    LEFT JOIN calificaciones_comportamiento_trimestre cb2 ON cb2.oferta_id=o.id AND cb2.matricula_id=? AND cb2.trimestre=2
    LEFT JOIN calificaciones_comportamiento_trimestre cb3 ON cb3.oferta_id=o.id AND cb3.matricula_id=? AND cb3.trimestre=3
    WHERE o.aula_periodo_id=? AND o.activo=1 ORDER BY s.nombre");
  $stmt->bind_param('iiiiiiii',$mid,$mid,$mid,$mid,$mid,$mid,$mid,$apid);$stmt->execute();$data=$stmt->get_result()->fetch_all(MYSQLI_ASSOC);$stmt->close();
  $suma=0;$n=0;
  foreach($data as $r){
    if(!empty($r['por_parametros'])){$evals[]=$r;continue;}
    $t1=$r['t1']===null?null:(float)$r['t1'];
    $t2=$r['t2']===null?null:(float)$r['t2'];
    $t3=$r['t3']===null?null:(float)$r['t3'];
    $fin=calcularFinalAnual($t1,$t2,$t3,$r['examen_supletorio']===null?null:(float)$r['examen_supletorio'],$config);
    $r['t1']=$t1;$r['t2']=$t2;$r['t3']=$t3;$r['final']=$fin;$rows[]=$r;
    if(!empty($r['solo_visor_comportamiento'])) {
        if(!isset($comportamientoOrigen)) {
            $comportamientoOrigen=(int)$r['id'];
            $comportamiento[1]=$r['comp_t1'];
            $comportamiento[2]=$r['comp_t2'];
            $comportamiento[3]=$r['comp_t3'];
        }
        continue; // No participa en el promedio academico de otras materias.
    }
    if($fin['trimestres_completos']){$suma+=(float)(!empty($m['resultados_cualitativos'])?$fin['promedio_final']:$fin['promedio_tres']);$n++;}
  }
  $materiasAcademicas=count(array_filter($data,static fn($r)=>empty($r['solo_visor_comportamiento']) && empty($r['por_parametros'])));
  $promedioGeneral=$n>0 && $n===$materiasAcademicas?truncar2($suma/$n):null;
}
$tituloPagina='Mis calificaciones';
$subtituloPagina=$m?($m['nivel'].' · '.$m['aula'].' '.$m['paralelo'].' · '.$p['nombre']):$p['nombre'];
require __DIR__.'/../../partials/header.php';
?>
<?php if(!$m):?>
<div class="card empty">No se encontró una matrícula activa.</div>
<?php else:?>
<?php foreach($evals as $ev)sgaParametrosResumenConsulta($conexion,(int)$ev['id'],$mid);?>
<?php if(!empty($m['evaluacion_cualitativa_parametros']) && !$evals):?><div class="card empty">La evaluación del aula está pendiente de asignación.</div><?php endif;?>
<?php if(empty($m['evaluacion_cualitativa_parametros'])):?>
<div class="grid cols-3" style="margin-bottom:16px">
  <div class="card metric"><span>Asignaturas</span><strong><?=count($rows)?></strong></div>
  <div class="card metric"><span>Promedio general del periodo</span><strong><?= $promedioGeneral===null?'En curso':e(!empty($m['resultados_cualitativos'])?sgaLetraResultadoCualitativo((float)$promedioGeneral):fmt($promedioGeneral)) ?></strong></div>
  <div class="card metric"><span>Periodo académico</span><strong style="font-size:22px"><?=e($p['nombre'])?></strong></div>
</div>
<?php if(isset($comportamientoOrigen)):?>
<section class="card" style="margin-bottom:16px">
  <strong>Comportamiento del período</strong>
  <div class="stat-row" style="margin-top:10px;gap:12px">
    <?php for($t=1;$t<=3;$t++):?>
      <span class="tag"><?=$t?>.° trimestre: <strong><?=e($comportamiento[$t]??'Sin calificar')?></strong></span>
    <?php endfor;?>
    <?php $comportamientoFinal=sgaComportamientoFinal($comportamiento[1],$comportamiento[2],$comportamiento[3]); ?>
    <span class="tag">Final: <strong><?=e($comportamientoFinal??'Pendiente')?></strong></span>
  </div>
</section>
<?php endif;?>
<div class="table-wrap"><table class="table"><thead><tr><th>Asignatura</th><th>1.° trimestre</th><th>2.° trimestre</th><th>3.° trimestre</th><th>Promedio total</th><th>Nota final</th><th>Estado</th></tr></thead><tbody>
<?php if(!$rows):?><tr><td colspan="7" class="empty">Todavía no hay asignaturas asignadas a tu paralelo.</td></tr><?php endif;?>
<?php foreach($rows as $r): if(!empty($r['solo_visor_comportamiento'])) continue; $f=$r['final'];?>
<tr>
  <td><strong><?=e($r['asignatura'])?></strong></td>
  <td><?=$r['t1']===null?'—':e(!empty($m['resultados_cualitativos'])?sgaNotaResultadoParaConsulta((float)$r['t1'],true):notaFinalVisible($r['t1'],!empty($r['usa_literal_especial'])))?></td><td><?=$r['t2']===null?'—':e(!empty($m['resultados_cualitativos'])?sgaNotaResultadoParaConsulta((float)$r['t2'],true):notaFinalVisible($r['t2'],!empty($r['usa_literal_especial'])))?></td><td><?=$r['t3']===null?'—':e(!empty($m['resultados_cualitativos'])?sgaNotaResultadoParaConsulta((float)$r['t3'],true):notaFinalVisible($r['t3'],!empty($r['usa_literal_especial'])))?></td>
  <td><strong title="<?=e($f['promedio_tres']===null?'Pendiente':(!empty($m['resultados_cualitativos'])?'Resultado cualitativo':'Promedio sobre 10: '.fmt($f['promedio_tres'])))?>"><?= $f['promedio_tres']===null?'—':e(!empty($m['resultados_cualitativos'])?sgaNotaResultadoParaConsulta((float)$f['promedio_tres'],true):notaFinalVisible((float)$f['promedio_tres'],!empty($r['usa_literal_especial']))) ?></strong></td>
  <td><strong title="<?=e($f['promedio_final']===null?'Pendiente':(!empty($m['resultados_cualitativos'])?'Resultado cualitativo':'Nota final sobre 10: '.fmt($f['promedio_final'])))?>"><?= $f['promedio_final']===null?'—':e(!empty($m['resultados_cualitativos'])?sgaNotaResultadoParaConsulta((float)$f['promedio_final'],true):notaFinalVisible((float)$f['promedio_final'],!empty($r['usa_literal_especial']))) ?></strong></td>
  <td><span class="badge <?=$f['observacion']==='APROBADO'?'good':($f['observacion']==='REPROBADO'?'bad':'warn')?>"><?=e($f['observacion']?:'EN CURSO')?></span></td>
</tr>
<?php endforeach;?>
</tbody></table></div>
<?php endif;?>
<?php endif;?>
<?php require __DIR__.'/../../partials/footer.php';?>
