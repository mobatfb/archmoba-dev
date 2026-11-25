<?php
require_once __DIR__.'/lib/funciones.php';
$uid=!empty($_SESSION['usuario_id'])?(int)$_SESSION['usuario_id']:null;
if($uid){registrarAuditoria('LOGOUT','Autenticación','sesion',null,'Cierre de sesión.',null,null,null,'exito',$uid,null,'info');}
$_SESSION=[];
if(ini_get('session.use_cookies')){
  $p=session_get_cookie_params();
  setcookie(session_name(),'',time()-42000,$p['path'],$p['domain'],$p['secure'],$p['httponly']);
}
session_destroy();
header('Location: '.url('index.php'));exit;
