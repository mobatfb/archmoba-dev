<?php
/** Cambio entre perfiles operativos existentes, sin otorgar permisos. */
require_once __DIR__.'/../../lib/funciones.php';
exigirLogin();
if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    header('Allow: POST');
    http_response_code(405);
    die('Método no permitido.');
}
if (empty($_SESSION['csrf_cambio_rol'])
    || !hash_equals((string)$_SESSION['csrf_cambio_rol'],(string)($_POST['csrf']??''))) {
    http_response_code(403);
    die('Formulario inválido.');
}
$p=periodoActivo();
$pid=(int)($p['id']??0);
$disponibles=rolesOperativosDisponibles();
if (count($disponibles)<2) {
    http_response_code(403);
    die('Tu cuenta no tiene varios perfiles habilitados para alternar.');
}
$rol=(string)($_POST['rol']??'');
if (!in_array($rol,$disponibles,true)) {
    http_response_code(403);
    die('El perfil solicitado no está asignado a tu cuenta.');
}
$anterior=rolOperativoActual();
if ($rol!==$anterior) {
    // Evita reutilizar la sesión anterior con otro conjunto de permisos.
    session_regenerate_id(true);
    $_SESSION['rol_operativo']=$rol;
    $_SESSION['rol_operativo_periodo']=$pid;
    $_SESSION['csrf_cambio_rol']=bin2hex(random_bytes(24));
    registrarAuditoria('SWITCH_ROLE','Autenticación','sesion',null,
        'Cambio de rol operativo sin modificar roles asignados.',
        (int)$_SESSION['usuario_id'],['rol'=>$anterior],['rol'=>$rol,'periodo_id'=>$pid],
        'exito',(int)$_SESSION['usuario_id'],null,'info');
    $nombres=['subadmin'=>'Subadministrador','docente'=>'Docente','representante'=>'Representante',
              'estudiante'=>'Estudiante','superadmin'=>'Administrador'];
    flash('success','Ahora estás trabajando como '.($nombres[$rol]??$rol).'.');
}
redir('dashboard.php');
