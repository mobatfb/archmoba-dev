<?php
declare(strict_types=1);
define('SW_APP',true);
require __DIR__.'/app.php';
require __DIR__.'/panel.php';
if (!$https && !$local) { http_response_code(400); render_message('Conexión segura requerida','Abre la dirección de tu sitio mediante HTTPS. No se necesita la privacidad del directorio de cPanel.');exit; }
$page=$_GET['page']??'sorteos';if(!is_string($page)||!in_array($page,['sorteos','participantes','ganadores','ingresos','cuenta'],true))$page='sorteos';
try { db();one('SELECT id,must_change_password FROM admins LIMIT 1');one('SELECT bucket FROM login_limits LIMIT 1');one('SELECT mime FROM raffle_photos LIMIT 1');$u=current_admin(); }
catch(Throwable $e){error_log('SORTEOWEB: '.get_class($e).' '.$e->getCode());http_response_code(503);render_message('Configura tu base de datos','Revisa config.php e importa actualizar_bd.sql en tu base existente desde phpMyAdmin. Comprueba que PDO MySQL esté habilitado.');exit;}
if($_SERVER['REQUEST_METHOD']==='POST'){
    verify_csrf();$action=$_POST['action']??'';
    try {
        if($action==='login'&&!$u)login();
        if(!$u)throw new DomainException('Inicia sesión.');
        if($action==='logout'){logout_session();go();}
        if($action==='change_password')change_password($u);
        if((int)$u['must_change_password']===1)throw new DomainException('Cambia primero la contraseña temporal.');
        match($action){'save_raffle'=>save_raffle($u),'activate','finish','delete_raffle'=>raffle_transition($u,$action),'save_participant'=>save_participant($u),'delete_participant'=>delete_participant($u),default=>throw new DomainException('Operación inválida.')};
    } catch(DomainException $e){flash($e->getMessage(),'error');}
    catch(Throwable $e){error_log('SORTEOWEB: '.get_class($e).' '.$e->getCode());flash('No se pudo completar la operación. Comprueba la configuración y los registros.','error');}
    $rid=$_POST['raffle_id']??null;$rid=valid_id($rid)?$rid:null;go($u&&$u['must_change_password']?'cuenta':$page,$page==='participantes'&&$rid?['id'=>$rid]:[]);
}
if(!$u){render_login();exit;}
if((int)$u['must_change_password']===1)$page='cuenta';
try { if(isset($_GET['photo'])){if((int)$u['must_change_password']===1){http_response_code(403);exit;}serve_photo();}render_panel($u,$page); }
catch(Throwable $e){error_log('SORTEOWEB: '.get_class($e).' '.$e->getCode());http_response_code(500);render_message('No se pudo cargar el panel','Verifica que se haya importado actualizar_bd.sql.');}
