<?php
require_once __DIR__.'/../../lib/funciones.php';
exigirLogin();
$oid=(int)($_GET['oferta_id']??0);
if(!$oid || !puedeGestionarOferta($oid)){http_response_code(403);die('No tienes acceso a esta asignación.');}
$o=ofertaDetalle($oid); $soloLectura=$o && ($o['periodo_estado']??'')==='cerrado'; if(!$o){http_response_code(404);die('Asignación inexistente.');}
$fecha=trim($_GET['fecha']??date('Y-m-d'));
$d=DateTime::createFromFormat('Y-m-d',$fecha);
if(!$d || $d->format('Y-m-d')!==$fecha) $fecha=date('Y-m-d');
$stmt=$conexion->prepare("SELECT s.id,s.tema,s.observaciones,s.creado_en,s.actualizado_en,
       CONCAT(u.apellidos,' ',u.nombres) registrado_por,
       (SELECT COUNT(*) FROM asistencia_detalle adx WHERE adx.sesion_id=s.id) registros_guardados
       FROM asistencia_sesiones s
       JOIN usuarios u ON u.id=s.registrado_por
       WHERE s.oferta_id=? AND s.fecha=? LIMIT 1");
$stmt->bind_param('is',$oid,$fecha);$stmt->execute();$sesion=$stmt->get_result()->fetch_assoc()?:null;$stmt->close();
$sid=(int)($sesion['id']??0);$apid=(int)$o['aula_periodo_id'];
$stmt=$conexion->prepare("SELECT m.id matricula_id,m.numero_lista,u.cedula,u.apellidos,u.nombres,
       ad.estado,ad.observacion
       FROM matriculas m JOIN usuarios u ON u.id=m.estudiante_id
       LEFT JOIN asistencia_detalle ad ON ad.matricula_id=m.id AND ad.sesion_id=?
       WHERE m.aula_periodo_id=? AND m.estado='activo'
       ORDER BY COALESCE(m.numero_lista,9999),u.apellidos,u.nombres");
$stmt->bind_param('ii',$sid,$apid);$stmt->execute();$rows=$stmt->get_result()->fetch_all(MYSQLI_ASSOC);$stmt->close();
$tituloPagina='Asistencia · '.$o['asignatura'];
$subtituloPagina=$o['nivel'].' · '.$o['aula'].' '.$o['paralelo'].' · '.$o['periodo'];
require __DIR__.'/../../partials/header.php';
$fechaBonita=date('d/m/Y',strtotime($fecha));
$esActualizacion=$sesion && !empty($sesion['actualizado_en']) && $sesion['actualizado_en']!==$sesion['creado_en'];
?>
<?php if($soloLectura):?><div class="notice" role="status"><strong>Período cerrado · solo consulta.</strong> Puedes revisar y descargar asistencias anteriores, pero no registrar ni modificar asistencias.</div><?php endif;?>
<?php if($sesion):?>
<div class="alert success" style="display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap">
  <div>
    <strong>✓ Asistencia ya registrada para el <?=e($fechaBonita)?></strong><br>
    <span>Esta jornada ya está guardada. Los datos que ves corresponden al registro existente y cualquier cambio se guardará como actualización.</span>
  </div>
  <div style="text-align:right">
    <span class="badge good"><?=$esActualizacion?'Actualizada':'Guardada'?></span>
    <div class="mini-note" style="margin-top:5px">Por <?=e($sesion['registrado_por'])?> · <?=e(date('d/m/Y H:i',strtotime($sesion['actualizado_en'])))?> · <?=(int)$sesion['registros_guardados']?> registros</div>
  </div>
</div>
<?php else:?>
<div class="notice" style="margin-bottom:16px">
  <strong>⚠ Asistencia pendiente para el <?=e($fechaBonita)?></strong><br>
  Todavía no existe un registro guardado para esta fecha. Los estudiantes aparecen inicialmente como <strong>Presente</strong>, pero esos valores no quedan registrados hasta pulsar <strong>Guardar asistencia</strong>.
</div>
<?php endif;?>
<div class="toolbar">
  <div class="actions"><a class="btn btn-secondary" href="<?=e(url('modulos/asistencia/index.php'))?>">Volver</a><a class="btn btn-secondary" href="<?=e(url('modulos/asistencia/historial.php?oferta_id='.$oid))?>">Historial</a><?php if(esAdminAcademico()):?><a class="btn btn-primary" href="<?=e(url('modulos/reportes/asistencia.php?'.http_build_query(['periodo_id'=>(int)$o['periodo_id'],'aula_periodo_id'=>$apid])))?>">Reporte consolidado</a><?php else:?><a class="btn btn-primary" href="<?=e(url('modulos/asistencia/descargar_por_fechas.php?oferta_id='.$oid))?>">Descargar asistencia por fechas</a><?php endif;?><?php if($sesion):?><a class="btn btn-success" href="<?=e(url('modulos/asistencia/reporte_excel.php?oferta_id='.$oid.'&fecha='.$fecha))?>">Descargar Excel</a><?php else:?><button class="btn btn-secondary" type="button" disabled title="Guarda primero la asistencia de esta fecha para exportarla">Excel (guardar primero)</button><?php endif;?></div>
  <form method="get" class="actions" style="align-items:end"><input type="hidden" name="oferta_id" value="<?=$oid?>"><label>Fecha<input type="date" name="fecha" value="<?=e($fecha)?>"></label><button class="btn btn-secondary" type="submit">Cargar fecha</button></form>
</div>
<form method="post" action="<?=e(url('modulos/asistencia/guardar.php'))?>" id="attendance-form">
<input type="hidden" name="oferta_id" value="<?=$oid?>"><input type="hidden" name="fecha" value="<?=e($fecha)?>">
<div class="card" style="margin-bottom:14px">
  <div class="form-grid cols-2">
    <label>Tema o actividad de la clase<input name="tema" <?=$soloLectura?'disabled':''?> maxlength="255" value="<?=e($sesion['tema']??'')?>" placeholder="Opcional"></label>
    <label>Observación general<input name="observaciones" <?=$soloLectura?'disabled':''?> maxlength="500" value="<?=e($sesion['observaciones']??'')?>" placeholder="Opcional"></label>
  </div>
  <div class="actions" style="margin-top:12px">
    <button class="btn btn-secondary attendance-all" type="button" <?=$soloLectura?'disabled':''?> data-status="presente">Todos presentes</button>
    <button class="btn btn-secondary attendance-all" type="button" <?=$soloLectura?'disabled':''?> data-status="ausente">Todos ausentes</button>
  </div>
</div>
<?php if(!$rows):?><div class="card empty">No hay estudiantes matriculados activamente en este paralelo.</div><?php else:?>
<div class="table-wrap"><table class="table table-responsive-cards"><thead><tr><th>No.</th><th>Cédula</th><th>Estudiante</th><th>Estado</th><th>Observación</th></tr></thead><tbody>
<?php foreach($rows as $r):$estado=$r['estado']?:'presente';?>
<tr><td><?=e($r['numero_lista']??'')?></td><td><?=e($r['cedula'])?></td><td><strong><?=e($r['apellidos'].' '.$r['nombres'])?></strong></td>
<td><select class="attendance-status" <?=$soloLectura?'disabled':''?> name="asistencia[<?= (int)$r['matricula_id']?>]">
<option value="presente" <?=$estado==='presente'?'selected':''?>>Presente</option>
<option value="ausente" <?=$estado==='ausente'?'selected':''?>>Ausente</option>
<option value="atraso" <?=$estado==='atraso'?'selected':''?>>Atraso</option>
<option value="justificado" <?=$estado==='justificado'?'selected':''?>>Justificado</option>
</select></td>
<td><input name="observacion[<?= (int)$r['matricula_id']?>]" <?=$soloLectura?'disabled':''?> maxlength="255" value="<?=e($r['observacion']??'')?>" placeholder="Opcional"></td></tr>
<?php endforeach;?>
</tbody></table></div>
<?php if(!$soloLectura):?>
<div class="card" style="margin:12px 0">
<label style="display:flex;align-items:flex-start;gap:10px"><input type="checkbox" name="notificar_representantes" value="1" checked style="width:auto;min-width:18px;margin-top:4px">
  <span><strong>Avisar a los representantes sobre nuevas ausencias y atrasos</strong>
  <small style="display:block">Se preparará un correo independiente para cada representante vinculado. Las asistencias ya notificadas no se enviarán otra vez al guardar sin cambios.</small></span>
</label></div>
<?php endif;?>
<div class="savebar"><div class="mini-note"><?=count($rows)?> estudiantes · Fecha: <?=e($fecha)?> · <strong><?=$sesion?'Registro existente':'Sin guardar todavía'?></strong></div><button class="btn btn-success" type="submit" <?=$soloLectura?'disabled':''?>><?=$sesion?'Actualizar asistencia':'Guardar asistencia'?></button></div>
<?php endif;?>
</form>
<script>
document.querySelectorAll('.attendance-all').forEach(function(btn){btn.addEventListener('click',function(){document.querySelectorAll('.attendance-status').forEach(function(sel){sel.value=btn.dataset.status;});});});
</script>
<?php require __DIR__.'/../../partials/footer.php';?>
