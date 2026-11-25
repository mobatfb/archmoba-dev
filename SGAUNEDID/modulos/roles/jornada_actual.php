<?php
/** Selección de jornada autorizada. Nunca amplía los permisos del subadministrador. */
require_once __DIR__.'/../../lib/funciones.php';
exigirLogin();
if (!esSubadmin() || esSuperadmin()) {http_response_code(403);die('Acceso restringido al subadministrador.');}
if (($_SERVER['REQUEST_METHOD']??'')!=='POST' || !isset($_SESSION['csrf_jornada_vista']) ||
    !hash_equals((string)$_SESSION['csrf_jornada_vista'],(string)($_POST['csrf']??''))) {
    http_response_code(403);die('Formulario inválido.');
}
$periodo=periodoActivo();$pid=(int)($periodo['id']??0);
if($pid<=0){http_response_code(403);die('No hay período académico activo.');}
$permitidas=jornadasPermitidasPeriodo($pid);
if(!$permitidas){http_response_code(403);die('No tienes jornadas asignadas para este período.');}
$id=filter_var($_POST['jornada_id']??null,FILTER_VALIDATE_INT);
if($id===false || $id===null || ($id===0 && count($permitidas)<2) ||
   ($id!==0 && !in_array($id,$permitidas,true))) {
    http_response_code(403);die('No tienes permiso para seleccionar esa jornada.');
}
$_SESSION['jornada_vista_periodos'][$pid]=$id;
flash('success',$id>0?'Jornada autorizada seleccionada.':'Mostrando únicamente tus jornadas asignadas.');
redir('dashboard.php');
