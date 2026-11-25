<?php
declare(strict_types=1);
if (!defined('SW_APP') || !SW_PUBLIC) { http_response_code(404); exit; }
require_once __DIR__.'/photos.php';
require_once dirname(__DIR__).'/evidence/service.php';
require_once dirname(__DIR__).'/evidence/conditions.php';
function pub_url(string $view='home',array $params=[]): string { return 'index.php'.($view==='home'&&!$params?'':'?'.http_build_query(['view'=>$view]+$params)); }
function pub_go(string $view='home',array $params=[]): never { header('Location: '.pub_url($view,$params),true,303);exit; }
function pub_flash(string $msg,string $kind='success'): void { $_SESSION['public_flash']=[$msg,$kind]; }
function pub_notice(): void { $f=$_SESSION['public_flash']??null;unset($_SESSION['public_flash']);if($f)pub_message($f[0],$f[1]); }
function pub_message(string $msg,string $kind='info'): void { $kind=in_array($kind,['success','error','warning','info'],true)?$kind:'info'; ?>
<div class="pub-notice <?=h($kind)?>" role="<?=$kind==='error'?'alert':'status'?>"><span><?=h($msg)?></span><button type="button" data-dismiss aria-label="Cerrar mensaje">×</button></div><?php }
function pub_csrf(): void { $v=$_POST['csrf']??null;if(!is_string($v)||!hash_equals(token(),$v)){http_response_code(403);pub_head('Solicitud inválida');echo '<main class="public-wrap">';pub_message('Recarga la página e inténtalo de nuevo.','error');echo '<a href="index.php">Volver al inicio</a></main>';pub_footer();exit;} }
function public_user(): ?array { $id=$_SESSION['public_user_id']??null;if(!is_int($id)||$id<1)return null;if(time()-(int)($_SESSION['public_seen']??0)>1800){$_SESSION=[];session_regenerate_id(true);return null;}$u=one('SELECT id,email,first_names,last_names,profile_complete FROM users WHERE id=? AND active=1',[$id]);if(!$u){$_SESSION=[];session_regenerate_id(true);return null;}$_SESSION['public_seen']=time();return $u; }
function profile_complete(array $u): bool { return (int)$u['profile_complete']===1 && trim($u['first_names'])!=='' && trim($u['last_names'])!==''; }
function active_raffles(): array { $rows=all("SELECT r.id,r.title,r.description,r.type,r.total,r.price_cents,r.draw_version,r.participation_mode,r.prize_cents,r.close_mode,r.participation_limit,r.closes_at,(SELECT COUNT(DISTINCT number) FROM participants p WHERE p.raffle_id=r.id) AS distinct_count,(SELECT COUNT(DISTINCT number) FROM participants p WHERE p.raffle_id=r.id AND p.payment='pagado') AS paid_distinct_count,(SELECT COUNT(*) FROM participants p WHERE p.raffle_id=r.id) AS registered_count,(SELECT COUNT(*) FROM participants p WHERE p.raffle_id=r.id AND p.payment='pagado') AS paid_count,CASE WHEN r.type='dinero' AND r.draw_version=1 THEN '1' ELSE (SELECT GROUP_CONCAT(f.slot ORDER BY f.slot) FROM raffle_photos f WHERE f.raffle_id=r.id AND f.slot BETWEEN 1 AND 3) END AS photo_slots,(SELECT GROUP_CONCAT(CONCAT(f.slot,':',f.filename) ORDER BY f.slot SEPARATOR ',') FROM raffle_photos f WHERE f.raffle_id=r.id AND f.slot BETWEEN 1 AND 3) AS photo_versions FROM raffles r WHERE r.status='activo' AND (r.closes_at IS NULL OR r.closes_at>?) ORDER BY r.created_at DESC,r.id DESC",[time()]);foreach($rows as &$r){$slots=array_values(array_filter(explode(',',(string)$r['photo_slots']),fn($n)=>in_array($n,['1','2','3'],true)));$r['photo_slot']=$slots? (int)$slots[0]:null;$r['photo_tokens']=[];foreach(explode(',',(string)$r['photo_versions']) as $entry){$pair=explode(':',$entry,2);if(count($pair)===2&&in_array($pair[0],['1','2','3'],true))$r['photo_tokens'][(int)$pair[0]]=photo_version($pair[1]);}}unset($r);return $rows; }
function public_photo(): never {
    $id=$_GET['id']??null;$slot=filter_var($_GET['slot']??null,FILTER_VALIDATE_INT);
    if(!valid_id($id)||!in_array($slot,[1,2,3],true)){http_response_code(404);exit;}
    if($slot===1&&one("SELECT id FROM raffles WHERE id=? AND type='dinero' AND draw_version=1 AND status='activo'",[$id]))draw_money_photo();
    photo_serve($id,$slot,true);
}
function pub_photo_url(array $r,?int $slot=null,string $size='medium'): string {
    if($r['type']==='dinero'&&(int)$r['draw_version']===1)return 'assets/premio-dinero.svg';
    $slot=$slot??(int)$r['photo_slot'];$params=['id'=>$r['id'],'slot'=>$slot,'size'=>photo_size($size)];
    if(isset($r['photo_tokens'][$slot]))$params['v']=$r['photo_tokens'][$slot];
    return pub_url('photo',$params);
}
