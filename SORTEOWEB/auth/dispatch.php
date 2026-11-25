<?php
declare(strict_types=1);
if (!defined('SW_APP') || !SW_PUBLIC) { http_response_code(404); exit; }
require __DIR__.'/otp.php';
$view=$_GET['view']??'home';if(!is_string($view)||!in_array($view,['home','login','verify','profile','account','photo','payphone_return','ticket_status','evidence','evidence_zip','results'],true))$view='home';
if(!$https&&!$local){http_response_code(400);pub_head('Conexión segura requerida');echo '<main class="public-wrap">';pub_message('Abre la página mediante HTTPS para proteger tu acceso.','error');echo '</main>';pub_footer();exit;}
try {
    if($view==='photo'){public_photo();}
    if($view==='payphone_return'){require_once dirname(__DIR__).'/wallet/payphone.php';payphone_return();}
    if($view==='evidence_zip'){require_once dirname(__DIR__).'/evidence/public.php';draw_download();}
    $lastSeen=$_SESSION['public_seen']??null;
    $u=public_user();
    if($view==='ticket_status'){if($u&&is_int($lastSeen))$_SESSION['public_seen']=$lastSeen;require_once dirname(__DIR__).'/usuario/tickets.php';ticket_status_response($u);}
    if($_SERVER['REQUEST_METHOD']==='POST'){
        pub_csrf();$action=$_POST['action']??'';$target=$view;
        try {
            if($action==='otp_send'&&!$u){$target='login';$email=normalize_email($_POST['email']??null);otp_issue($email);pub_flash('Código enviado. Revisa tu correo y la carpeta de spam.');pub_go('verify');}
            if($action==='otp_resend'&&!$u){$target='verify';$email=otp_session_email();if(!$email)pub_go('login');otp_issue($email);pub_flash('Enviamos un nuevo código. El anterior dejó de ser válido.');pub_go('verify');}
            if($action==='otp_verify'&&!$u){$target='verify';$email=otp_session_email();if(!$email)pub_go('login');$id=otp_verify($email,$_SESSION['otp_challenge'],$_POST['code']??null);if(!$id)throw new DomainException('Código incorrecto, caducado o límite de intentos alcanzado. Solicita otro si es necesario.');session_regenerate_id(true);$_SESSION=['public_user_id'=>$id,'public_seen'=>time()];$user=public_user();if(!$user)throw new DomainException('No se pudo iniciar la sesión.');pub_go(profile_complete($user)?'account':'profile');}
            if($action==='otp_cancel'&&!$u){unset($_SESSION['otp_email'],$_SESSION['otp_challenge'],$_SESSION['otp_sent_at']);pub_go('login');}
            if($action==='profile_save'&&$u){$target='profile';$first=field('first_names',120);$last=field('last_names',120);if(!preg_match('/[\p{L}]/u',$first)||!preg_match('/[\p{L}]/u',$last)||preg_match('/[\p{C}]/u',$first.$last))throw new DomainException('Introduce nombres y apellidos válidos.');query('UPDATE users SET first_names=?,last_names=?,profile_complete=1 WHERE id=? AND active=1',[$first,$last,$u['id']]);pub_flash('Perfil actualizado correctamente.');pub_go('account');}
            if($action==='wallet_recharge'&&$u&&profile_complete($u)){$target='account';require_once dirname(__DIR__).'/wallet/payphone.php';try{payphone_prepare($u,$_POST['amount']??null);}catch(DomainException $e){pub_flash($e->getMessage(),'error');pub_go('account',['tab'=>'recargar']);}}
            if($action==='public_logout'&&$u){$_SESSION=[];session_regenerate_id(true);pub_go();}
            throw new DomainException('Operación no válida.');
        } catch(DomainException $e){pub_flash($e->getMessage(),'error');pub_go($target==='photo'?'home':$target);}
        catch(Throwable $e){error_log('SORTEOWEB público: '.get_class($e).' '.$e->getCode());pub_flash('No se pudo completar la solicitud. Inténtalo de nuevo más tarde.','error');pub_go($target==='photo'?'home':$target);}
    }
    if(in_array($view,['home','account','results','evidence'],true))draw_process_due();
    if($view==='evidence'||$view==='results'){require_once dirname(__DIR__).'/evidence/public.php';draw_public_page($u,$view);exit;}
    if($u&&!profile_complete($u)&&$view!=='profile')pub_go('profile');
    if($view==='home'){$raffles=active_raffles();require dirname(__DIR__).'/landing/index.php';exit;}
    if($view==='login'){if($u)pub_go('account');require __DIR__.'/login.php';exit;}
    if($view==='verify'){if($u)pub_go('account');$email=otp_session_email();if(!$email)pub_go('login');require __DIR__.'/verify.php';exit;}
    if(!$u)pub_go('login');
    if($view==='profile'){require dirname(__DIR__).'/usuario/modules/perfil.php';exit;}
    require dirname(__DIR__).'/usuario/index.php';
} catch(Throwable $e){error_log('SORTEOWEB público: '.get_class($e).' '.$e->getCode());http_response_code(503);pub_head('Servicio no disponible');echo '<main class="public-wrap">';pub_message('El servicio no está disponible en este momento. Inténtalo de nuevo más tarde.','error');echo '<a href="index.php">Volver al inicio</a></main>';pub_footer();}
