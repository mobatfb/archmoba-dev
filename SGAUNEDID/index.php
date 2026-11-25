<?php
require_once __DIR__.'/lib/funciones.php';
if(!empty($_SESSION['usuario_id'])) redir('dashboard.php');
$error='';
if($_SERVER['REQUEST_METHOD']==='POST'){
  $cedula=trim($_POST['cedula']??'');$clave=(string)($_POST['clave']??'');
  $stmt=$conexion->prepare('SELECT id,cedula,nombres,apellidos,clave,activo FROM usuarios WHERE cedula=? LIMIT 1');$stmt->bind_param('s',$cedula);$stmt->execute();$u=$stmt->get_result()->fetch_assoc();$stmt->close();
  if($u && (int)$u['activo']===1 && password_verify($clave,$u['clave'])){
    session_regenerate_id(true);
    $_SESSION['usuario_id']=(int)$u['id'];
    // Un nuevo ingreso comienza siempre en el rol predeterminado.
    // La función rolOperativoActual() prioriza Subadministrador en cuentas duales.
    unset($_SESSION['rol_operativo'], $_SESSION['rol_operativo_periodo']);
    registrarAuditoria('LOGIN','Autenticación','sesion',null,'Inicio de sesión exitoso.',(int)$u['id'],null,['cedula'=>$u['cedula']],'exito',(int)$u['id'],null,'info');
    redir('dashboard.php');
  }
  registrarAuditoria('LOGIN_FALLIDO','Autenticación','sesion',null,'Intento de inicio de sesión fallido para la cédula '.($cedula!==''?$cedula:'(vacía)').'.',$u?(int)$u['id']:null,null,['cedula'=>$cedula,'motivo'=>$u&&!(int)$u['activo']?'usuario_inactivo':'credenciales_invalidas'],'fallo',null,null,'advertencia');
  $error='Credenciales incorrectas o usuario inactivo.';
}
?><!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Ingreso · Sistema de Gestión Académica UNEDID</title><link rel="icon" type="image/jpeg" href="<?=e(url('assets/img/logo.jpeg'))?>?v=20261111"><link rel="stylesheet" href="<?=e(url('assets/css/app.css'))?>?v=<?=(int)filemtime(__DIR__.'/assets/css/app.css')?>"><style>body{display:grid;place-items:center;min-height:100vh;background:linear-gradient(135deg,#071d3b,#0d4f9d)}.login{width:min(430px,92vw);background:#fff;border-radius:20px;padding:30px}.login-logo{display:flex;align-items:center;gap:12px;margin-bottom:24px}.login-logo img{width:55px;height:55px;border-radius:13px;object-fit:cover}.login h1{margin:0}.login p{color:#66758a}.login form{display:grid;gap:14px}.login .btn{padding:12px}.sga-forgot-link{display:block;text-align:center;color:#0b4c91;font-size:14px;font-weight:700;text-decoration:none;padding:5px 0}.sga-forgot-link:hover,.sga-forgot-link:focus{text-decoration:underline}</style></head><body><div class="login"><div class="login-logo"><img src="<?=e(url('assets/img/logo.jpeg'))?>" alt="Logo"><div><h1>Sistema de Gestión Académica UNEDID</h1><p style="margin:3px 0 0">Unidad Educativa de Iniciación y Desarrollo Deportivo del Azuay</p></div></div><?php if($error):?><div class="alert error"><?=e($error)?></div><?php endif;?><form method="post"><label>Cédula<input name="cedula" autocomplete="username" required autofocus></label><label>Contraseña<input type="password" name="clave" autocomplete="current-password" required></label><button class="btn btn-primary" type="submit">Ingresar</button><a href="<?=e(url('recuperar_clave.php'))?>" class="sga-forgot-link">¿Olvidaste tu contraseña?</a></form></div><script src="<?=e(url('assets/js/password-eye.js'))?>?v=<?=(int)filemtime(__DIR__.'/assets/js/password-eye.js')?>"></script></body></html>
