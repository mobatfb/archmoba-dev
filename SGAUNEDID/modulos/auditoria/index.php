<?php
require_once __DIR__.'/../../lib/funciones.php';
exigirSuperadmin();

$accion=trim($_GET['accion']??'');
$modulo=trim($_GET['modulo']??'');
$resultado=trim($_GET['resultado']??'');
$desde=trim($_GET['desde']??'');
$hasta=trim($_GET['hasta']??'');
$q=trim($_GET['q']??'');
$ver=(int)($_GET['ver']??0);

$detalleEvento=null;
if($ver){
  $stmt=$conexion->prepare("SELECT a.*,CONCAT(ua.apellidos,' ',ua.nombres) actor_nombre,ua.cedula actor_cedula,CONCAT(uf.apellidos,' ',uf.nombres) afectado_nombre,uf.cedula afectado_cedula FROM auditoria_actividades a LEFT JOIN usuarios ua ON ua.id=a.usuario_actor_id LEFT JOIN usuarios uf ON uf.id=a.usuario_afectado_id WHERE a.id=? LIMIT 1");
  $stmt->bind_param('i',$ver);$stmt->execute();$detalleEvento=$stmt->get_result()->fetch_assoc();$stmt->close();
}

$where=[];$params=[];$types='';
if($accion!==''){$where[]='a.accion=?';$params[]=$accion;$types.='s';}
if($modulo!==''){$where[]='a.modulo=?';$params[]=$modulo;$types.='s';}
if(in_array($resultado,['exito','fallo'],true)){$where[]='a.resultado=?';$params[]=$resultado;$types.='s';}
if($desde!==''){$where[]='a.fecha_actividad>=?';$params[]=$desde.' 00:00:00';$types.='s';}
if($hasta!==''){$where[]='a.fecha_actividad<=?';$params[]=$hasta.' 23:59:59.999999';$types.='s';}
if($q!==''){
  $where[]="(a.detalle LIKE ? OR a.entidad_id LIKE ? OR a.ip_remota LIKE ? OR a.ip_publica LIKE ? OR ua.cedula LIKE ? OR ua.apellidos LIKE ? OR ua.nombres LIKE ? OR uf.cedula LIKE ? OR uf.apellidos LIKE ? OR uf.nombres LIKE ?)";
  $like='%'.$q.'%'; for($i=0;$i<10;$i++){$params[]=$like;$types.='s';}
}
$sql="SELECT a.*,CONCAT(ua.apellidos,' ',ua.nombres) actor_nombre,ua.cedula actor_cedula,CONCAT(uf.apellidos,' ',uf.nombres) afectado_nombre,uf.cedula afectado_cedula FROM auditoria_actividades a LEFT JOIN usuarios ua ON ua.id=a.usuario_actor_id LEFT JOIN usuarios uf ON uf.id=a.usuario_afectado_id";
if($where)$sql.=' WHERE '.implode(' AND ',$where);
$sql.=' ORDER BY a.fecha_actividad DESC,a.id DESC LIMIT 500';
$stmt=$conexion->prepare($sql);
if($params){$refs=[];foreach($params as $k=>&$v)$refs[$k]=&$v;array_unshift($refs,$types);call_user_func_array([$stmt,'bind_param'],$refs);}
$stmt->execute();$rows=$stmt->get_result()->fetch_all(MYSQLI_ASSOC);$stmt->close();
$acciones=$conexion->query('SELECT DISTINCT accion FROM auditoria_actividades ORDER BY accion')->fetch_all(MYSQLI_ASSOC);
$modulos=$conexion->query('SELECT DISTINCT modulo FROM auditoria_actividades ORDER BY modulo')->fetch_all(MYSQLI_ASSOC);

function jsonBonitoAud($s): string {
  if($s===null||$s==='')return '';
  $d=json_decode($s,true);if(json_last_error()===JSON_ERROR_NONE)return json_encode($d,JSON_PRETTY_PRINT|JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);
  return (string)$s;
}
$tituloPagina='Auditoría de actividades';
$subtituloPagina='Trazabilidad de operaciones sensibles, accesos, cambios académicos y acciones administrativas.';
require __DIR__.'/../../partials/header.php';
?>
<div class="alert info"><strong>Registro inmutable:</strong> la Auditoría es el único módulo administrativo sin opciones de editar, eliminar o desactivar. Esto preserva la trazabilidad de las acciones realizadas en el sistema.</div>
<section class="card">
  <form method="get" class="form-grid">
    <label>Buscar<input name="q" value="<?=e($q)?>" placeholder="Usuario, cédula, detalle, IP..."></label>
    <label>Acción<select name="accion"><option value="">Todas</option><?php foreach($acciones as $a):?><option value="<?=e($a['accion'])?>" <?=$accion===$a['accion']?'selected':''?>><?=e($a['accion'])?></option><?php endforeach;?></select></label>
    <label>Módulo<select name="modulo"><option value="">Todos</option><?php foreach($modulos as $m):?><option value="<?=e($m['modulo'])?>" <?=$modulo===$m['modulo']?'selected':''?>><?=e($m['modulo'])?></option><?php endforeach;?></select></label>
    <label>Resultado<select name="resultado"><option value="">Todos</option><option value="exito" <?=$resultado==='exito'?'selected':''?>>Éxito</option><option value="fallo" <?=$resultado==='fallo'?'selected':''?>>Fallo</option></select></label>
    <label>Desde<input type="date" name="desde" value="<?=e($desde)?>"></label>
    <label>Hasta<input type="date" name="hasta" value="<?=e($hasta)?>"></label>
    <div class="form-actions"><button class="btn btn-primary">Filtrar</button><a class="btn btn-secondary" href="<?=e(url('modulos/auditoria/index.php'))?>">Limpiar</a></div>
  </form>
</section>

<?php if($detalleEvento):?>
<section class="card" style="margin-top:16px">
  <div class="toolbar"><div><h2 style="margin:0">Evento #<?=e($detalleEvento['id'])?></h2><p class="muted" style="margin:5px 0 0"><?=e($detalleEvento['fecha_actividad'])?> · Grupo <?=e($detalleEvento['grupo_evento']??'')?></p></div><a class="btn btn-secondary" href="<?=e(url('modulos/auditoria/index.php'))?>">Cerrar detalle</a></div>
  <div class="grid cols-3">
    <div><strong>Actor</strong><p><?=e(($detalleEvento['actor_nombre']?:'No autenticado').($detalleEvento['actor_cedula']?' · '.$detalleEvento['actor_cedula']:''))?></p></div>
    <div><strong>Usuario afectado</strong><p><?=e(($detalleEvento['afectado_nombre']?:'—').($detalleEvento['afectado_cedula']?' · '.$detalleEvento['afectado_cedula']:''))?></p></div>
    <div><strong>Acción</strong><p><?=e($detalleEvento['accion'].' · '.$detalleEvento['modulo'].' · '.$detalleEvento['entidad'])?></p></div>
    <div><strong>IP remota</strong><p><?=e($detalleEvento['ip_remota']??'—')?></p></div>
    <div><strong>IP pública detectada</strong><p><?=e($detalleEvento['ip_publica']??'No disponible')?><?php if($detalleEvento['ip_fuente']):?> <span class="badge"><?=e($detalleEvento['ip_fuente'])?></span><?php endif;?></p></div>
    <div><strong>Resultado</strong><p><span class="badge <?=$detalleEvento['resultado']==='exito'?'good':'bad'?>"><?=e(strtoupper($detalleEvento['resultado']))?></span> <span class="badge"><?=e($detalleEvento['criticidad'])?></span></p></div>
  </div>
  <p><strong>Detalle:</strong> <?=e($detalleEvento['detalle'])?></p>
  <p class="mini-note"><strong>Ruta:</strong> <?=e($detalleEvento['metodo_http'].' '.$detalleEvento['ruta'])?><br><strong>User-Agent:</strong> <?=e($detalleEvento['user_agent']??'')?><br><strong>X-Forwarded-For:</strong> <?=e($detalleEvento['ip_forwarded']??'—')?></p>
  <div class="grid cols-2">
    <div><h3>Antes</h3><pre class="audit-json"><?=e(jsonBonitoAud($detalleEvento['datos_antes']))?></pre></div>
    <div><h3>Después</h3><pre class="audit-json"><?=e(jsonBonitoAud($detalleEvento['datos_despues']))?></pre></div>
  </div>
</section>
<?php endif;?>

<h2 class="section-title">Registros <span class="badge"><?=count($rows)?> mostrados</span></h2>
<div class="table-wrap"><table class="table table-responsive-cards"><thead><tr><th>Fecha</th><th>Actor</th><th>Acción</th><th>Detalle</th><th>Afectado</th><th>IP</th><th>Resultado</th><th></th></tr></thead><tbody>
<?php if(!$rows):?><tr><td colspan="8" class="empty">No hay registros con estos filtros.</td></tr><?php endif;?>
<?php foreach($rows as $r):?><tr>
<td style="white-space:nowrap"><?=e($r['fecha_actividad'])?></td>
<td><strong><?=e($r['actor_nombre']?:'No autenticado')?></strong><br><span class="mini-note"><?=e($r['actor_cedula']??'')?></span></td>
<td><span class="badge"><?=e($r['accion'])?></span><br><span class="mini-note"><?=e($r['modulo'])?></span></td>
<td style="min-width:260px"><?=e($r['detalle'])?><br><span class="mini-note"><?=e($r['entidad'].($r['entidad_id']!==null?' #'.$r['entidad_id']:''))?></span></td>
<td><?=e($r['afectado_nombre']?:'—')?><?php if($r['afectado_cedula']):?><br><span class="mini-note"><?=e($r['afectado_cedula'])?></span><?php endif;?></td>
<td><?=e($r['ip_publica']?:($r['ip_remota']?:'—'))?><?php if($r['ip_publica']&&$r['ip_remota']!==$r['ip_publica']):?><br><span class="mini-note">Servidor: <?=e($r['ip_remota'])?></span><?php endif;?></td>
<td><span class="badge <?=$r['resultado']==='exito'?'good':'bad'?>"><?=e($r['resultado'])?></span></td>
<td><a class="btn btn-sm btn-secondary" href="?<?=e(http_build_query(array_merge($_GET,['ver'=>$r['id']])))?>">Ver</a></td>
</tr><?php endforeach;?></tbody></table></div>
<?php require __DIR__.'/../../partials/footer.php';?>
