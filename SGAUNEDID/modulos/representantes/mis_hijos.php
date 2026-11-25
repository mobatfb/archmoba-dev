<?php
/** Portal de consulta exclusiva del representante. Nunca permite asignar hijos. */
require_once __DIR__.'/../../lib/sga_representantes.php';
exigirLogin();
if (!esRepresentanteOperativo()) {http_response_code(403);die('Este portal requiere el rol Representante.');}
$uid=(int)$_SESSION['usuario_id'];
$p=periodoActivo();$pid=(int)($p['id']??0);
$hijos=[];
if($pid){
    $s=$conexion->prepare("SELECT DISTINCT u.id,u.cedula,u.apellidos,u.nombres,
        CONCAT(a.nivel,' ',a.nombre,' ',a.paralelo) aula,a.resultados_cualitativos,ap.evaluacion_cualitativa_parametros
        FROM sga_representantes_estudiantes re
        JOIN usuarios u ON u.id=re.estudiante_id AND u.activo=1
        JOIN matriculas m ON m.estudiante_id=u.id AND m.estado='activo'
        JOIN aulas_periodo ap ON ap.id=m.aula_periodo_id AND ap.activo=1
        JOIN aulas a ON a.id=ap.aula_id
        WHERE re.representante_id=? AND re.activo=1 AND ap.periodo_id=?
        ORDER BY u.apellidos,u.nombres");
    $s->bind_param('ii',$uid,$pid);$s->execute();$hijos=$s->get_result()->fetch_all(MYSQLI_ASSOC);$s->close();
}
$elegidoId=(int)($_GET['estudiante_id']??0);
$elegido=null;
foreach($hijos as $h){if((int)$h['id']===$elegidoId){$elegido=$h;break;}}
if($elegidoId && !$elegido){http_response_code(403);die('El estudiante no está vinculado a tu cuenta.');}
$notas=[];$evals=[];$asistencias=['presente'=>0,'ausente'=>0,'atraso'=>0,'justificado'=>0];$novedades=[];
if($elegido){
    // Unicamente matriculas del estudiante dentro del periodo activo.
    $s=$conexion->prepare("SELECT s.nombre asignatura,s.usa_literal_especial,
        MAX(CASE WHEN ct.trimestre=1 THEN ct.nota_final ELSE NULL END) trimestre_1,
        MAX(CASE WHEN ct.trimestre=2 THEN ct.nota_final ELSE NULL END) trimestre_2,
        MAX(CASE WHEN ct.trimestre=3 THEN ct.nota_final ELSE NULL END) trimestre_3,
        MAX(nf.examen_supletorio) examen_supletorio
        FROM matriculas m JOIN aulas_periodo ap ON ap.id=m.aula_periodo_id AND ap.activo=1
        JOIN ofertas_academicas o ON o.aula_periodo_id=ap.id AND o.activo=1 AND o.evaluacion_aula=0 AND o.evaluacion_parametros_historica=0
        JOIN asignaturas s ON s.id=o.asignatura_id AND s.solo_visor_comportamiento=0
        LEFT JOIN calificaciones_trimestre ct ON ct.matricula_id=m.id AND ct.oferta_id=o.id
        LEFT JOIN notas_finales nf ON nf.matricula_id=m.id AND nf.oferta_id=o.id
        WHERE m.estudiante_id=? AND ap.periodo_id=? AND m.estado='activo'
        GROUP BY o.id,s.nombre,s.usa_literal_especial ORDER BY s.nombre");
    $s->bind_param('ii',$elegidoId,$pid);$s->execute();$notas=$s->get_result()->fetch_all(MYSQLI_ASSOC);$s->close();
    $resultadosAula=!empty($elegido['resultados_cualitativos']);
    if($resultadosAula)$configResultados=obtenerConfiguracion($pid);
    $s=$conexion->prepare("SELECT o.id oferta_id,m.id matricula_id FROM matriculas m JOIN aulas_periodo ap ON ap.id=m.aula_periodo_id AND ap.activo=1 JOIN ofertas_academicas o ON o.aula_periodo_id=ap.id AND o.activo=1 AND (o.evaluacion_aula=1 OR o.evaluacion_parametros_historica=1) WHERE m.estudiante_id=? AND ap.periodo_id=? AND m.estado='activo'");
    $s->bind_param('ii',$elegidoId,$pid);sgaEjecutar($s,'consultar evaluación del estudiante');$evals=$s->get_result()->fetch_all(MYSQLI_ASSOC);$s->close();
    $s=$conexion->prepare("SELECT ad.estado,COUNT(*) cantidad FROM asistencia_detalle ad
        JOIN matriculas m ON m.id=ad.matricula_id AND m.estado='activo'
        JOIN aulas_periodo ap ON ap.id=m.aula_periodo_id AND ap.activo=1
        JOIN asistencia_sesiones ses ON ses.id=ad.sesion_id
        JOIN ofertas_academicas o ON o.id=ses.oferta_id AND o.aula_periodo_id=ap.id
        WHERE m.estudiante_id=? AND ap.periodo_id=? GROUP BY ad.estado");
    $s->bind_param('ii',$elegidoId,$pid);$s->execute();
    foreach($s->get_result()->fetch_all(MYSQLI_ASSOC) as $r){$k=(string)$r['estado'];if(isset($asistencias[$k]))$asistencias[$k]=(int)$r['cantidad'];}
    $s->close();
    $s=$conexion->prepare("SELECT n.tipo,n.asunto,n.detalle,n.creada_en FROM sga_representantes_novedades n
        WHERE n.estudiante_id=? AND n.periodo_id=?
        AND n.creada_en >= (SELECT re.creado_en FROM sga_representantes_estudiantes re WHERE re.estudiante_id=n.estudiante_id AND re.representante_id=$uid AND re.activo=1 LIMIT 1)
        ORDER BY n.id DESC LIMIT 20");
    $s->bind_param('ii',$elegidoId,$pid);$s->execute();$novedades=$s->get_result()->fetch_all(MYSQLI_ASSOC);$s->close();
}
$tituloPagina='Mis hijos';$subtituloPagina='Consulta privada de los estudiantes asociados a tu cuenta en el período activo.';
require __DIR__.'/../../partials/header.php';
?>
<?php if(!$pid):?><div class="notice">No existe un período académico activo.</div><?php endif;?>
<section class="card"><h2>Estudiantes vinculados</h2>
<?php if(!$hijos):?><p class="muted">Aún no hay estudiantes matriculados vinculados a tu cuenta. Solicita a la administración que verifique la relación familiar.</p>
<?php else: ?><div class="grid cols-2">
<?php foreach($hijos as $h):?><a class="card course-card" style="display:block" href="<?=e(url('modulos/representantes/mis_hijos.php?estudiante_id='.(int)$h['id']))?>"><div class="title"><?=e($h['apellidos'].' '.$h['nombres'])?></div><div class="meta"><?=e($h['aula'])?> · <?=e($h['cedula'])?></div><div class="mini-note">Consultar seguimiento académico</div></a><?php endforeach;?>
</div><?php endif;?></section>
<?php if($elegido):?>
<h2 class="section-title">Seguimiento de <?=e($elegido['nombres'].' '.$elegido['apellidos'])?></h2>
<div class="grid cols-4">
<?php foreach(['presente'=>'Presentes','ausente'=>'Ausencias','atraso'=>'Atrasos','justificado'=>'Justificados'] as $estado=>$nombre):?><div class="card metric"><span><?=e($nombre)?></span><strong><?=(int)$asistencias[$estado]?></strong></div><?php endforeach;?>
</div><p class="mini-note">La asistencia se cuenta por registro de asignatura y fecha, no por días calendario.</p>
<?php foreach($evals as $ev)sgaParametrosResumenConsulta($conexion,(int)$ev['oferta_id'],(int)$ev['matricula_id']);?>
<?php if(!empty($elegido['evaluacion_cualitativa_parametros']) && !$evals):?><div class="card empty">La evaluación del aula está pendiente de asignación.</div><?php endif;?>
<?php if(empty($elegido['evaluacion_cualitativa_parametros'])):?>
<section class="card" style="margin-top:18px"><h2>Calificaciones registradas</h2>
<div class="table-wrap"><table class="table"><thead><tr><th>Asignatura</th><th>1.º trimestre</th><th>2.º trimestre</th><th>3.º trimestre</th><?php if($resultadosAula):?><th>Promedio anual</th><th>Resultado final</th><?php endif;?></tr></thead><tbody>
<?php foreach($notas as $n):?><tr><td><?=e($n['asignatura'])?></td>
<?php foreach(['trimestre_1','trimestre_2','trimestre_3'] as $t):?><td><?=($n[$t]===null)?'Pendiente':e(!empty($elegido['resultados_cualitativos'])?sgaNotaResultadoParaConsulta((float)$n[$t],true):notaFinalVisible((float)$n[$t],!empty($n['usa_literal_especial'])))?></td><?php endforeach;?><?php if($resultadosAula): $num=static fn($v)=>$v===null?null:(float)$v; $final=calcularFinalAnual($num($n['trimestre_1']),$num($n['trimestre_2']),$num($n['trimestre_3']),$num($n['examen_supletorio']),$configResultados);?><td><?=e(sgaNotaResultadoParaConsulta($final['promedio_tres'],true))?></td><td><?=e(sgaNotaResultadoParaConsulta($final['promedio_final'],true))?></td><?php endif;?></tr><?php endforeach;?>
<?php if(!$notas):?><tr><td colspan="<?=$resultadosAula?6:4?>">No hay calificaciones disponibles.</td></tr><?php endif;?></tbody></table></div></section>
<?php endif;?>
<section class="card" style="margin-top:18px"><h2>Comunicados y novedades</h2>
<?php if(!$novedades):?><p class="muted">No se han registrado novedades en el período activo.</p><?php endif;?>
<?php foreach($novedades as $n):?><article style="padding:12px 0;border-bottom:1px solid #dce4ed"><div class="mini-note"><?=e($n['creada_en'])?> · <?=e($n['tipo'])?></div><strong><?=e($n['asunto'])?></strong><p style="white-space:pre-wrap"><?=e($n['detalle'])?></p></article><?php endforeach;?></section>
<?php endif;?>
<?php require __DIR__.'/../../partials/footer.php'; ?>
