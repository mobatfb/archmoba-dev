<?php
declare(strict_types=1);
if (!defined('SW_APP') || !SW_PUBLIC) { http_response_code(404); exit; }
require_once __DIR__.'/service.php';
// Server-side integration with PayPhone's redirect button. No card data enters SORTEOWEB.
// This adapter is staged, not available for real charges in release 1.1.6.
function payphone_api(array $cfg,string $method,array $payload): array {
    if(!wallet_settings_valid($cfg))throw new RuntimeException('PayPhone config unavailable');
    $paths=['prepare'=>'/api/button/Prepare','confirm'=>'/api/button/V2/Confirm'];
    if(!isset($paths[$method]))throw new LogicException('Unsupported payment method');
    $curl=curl_init('https://pay.payphonetodoesposible.com'.$paths[$method]);
    if($curl===false)throw new RuntimeException('PayPhone initialization failed');
    try{
        curl_setopt_array($curl,[CURLOPT_POST=>true,CURLOPT_POSTFIELDS=>json_encode($payload,JSON_THROW_ON_ERROR),CURLOPT_RETURNTRANSFER=>true,CURLOPT_FOLLOWLOCATION=>false,CURLOPT_CONNECTTIMEOUT=>5,CURLOPT_TIMEOUT=>15,CURLOPT_SSL_VERIFYPEER=>true,CURLOPT_SSL_VERIFYHOST=>2,CURLOPT_HTTPHEADER=>['Authorization: Bearer '.$cfg['token'],'Content-Type: application/json','Accept: application/json']]);
        $body=curl_exec($curl);$status=(int)curl_getinfo($curl,CURLINFO_HTTP_CODE);
        if(!is_string($body)||$status<200||$status>=300)throw new RuntimeException('PayPhone request not confirmed');
        $data=json_decode($body,true,512,JSON_THROW_ON_ERROR);if(!is_array($data))throw new RuntimeException('Invalid payment response');return $data;
    }finally{curl_close($curl);}
}
function payphone_checkout_url(mixed $url): string {
    if(!is_string($url)||preg_match('/[\x00-\x20\x7f]/',$url))throw new RuntimeException('Invalid PayPhone URL');$p=parse_url($url);
    if(!is_array($p)||($p['scheme']??'')!=='https'||strtolower($p['host']??'')!=='pay.payphonetodoesposible.com'||isset($p['user'])||isset($p['pass'])||isset($p['port'])||!in_array($p['path']??'',['/PayPhone/Index','/Anonymous/Index'],true))throw new RuntimeException('Invalid PayPhone redirect');
    return $url;
}
function payphone_prepare(array $u,mixed $amount): never {
    if(!wallet_payments_enabled())throw new DomainException('Las recargas por PayPhone aún no están habilitadas. No se realizó ningún cobro.');
    $c=wallet_config();$n=wallet_amount($amount,$c);$id=bin2hex(random_bytes(12));
    tx(function()use($u,$n,$id){
        $owner=one('SELECT id FROM users WHERE id=? AND active=1 AND profile_complete=1 FOR UPDATE',[$u['id']]);if(!$owner)throw new DomainException('Completa tu perfil para continuar.');
        $recent=one("SELECT COUNT(*) AS n FROM wallet_recharges WHERE user_id=? AND created_at>=NOW()-INTERVAL 15 MINUTE",[$u['id']]);if((int)$recent['n']>=3)throw new DomainException('Tienes varias solicitudes recientes. Revisa tus transacciones antes de volver a intentar.');
        query('INSERT INTO wallet_recharges(id,user_id,amount_cents) VALUES(?,?,?)',[$id,$u['id'],$n]);
    });
    $base=rtrim($c['base_url'],'/').'/index.php';
    try{
        // Tax treatment must be validated for the merchant before enabling real payments.
        $data=payphone_api($c,'prepare',['amount'=>$n,'amountWithoutTax'=>$n,'amountWithTax'=>0,'tax'=>0,'service'=>0,'tip'=>0,'currency'=>'USD','clientTransactionId'=>$id,'storeId'=>$c['store_id'],'reference'=>'Recarga SORTEOWEB '.$id,'responseUrl'=>$base.'?view=payphone_return','cancellationUrl'=>$base.'?view=account&tab=transacciones']);
        $url=payphone_checkout_url($data['payWithPayPhone']??null);$pid=$data['paymentId']??null;
        if(!is_string($pid)||$pid===''||strlen($pid)>128)throw new RuntimeException('Invalid payment identifier');
        query("UPDATE wallet_recharges SET state='pending',payment_id=? WHERE id=? AND state='preparing'",[$pid,$id]);
        session_write_close();header('Location: '.$url,true,303);exit;
    }catch(Throwable $e){query("UPDATE wallet_recharges SET state='review' WHERE id=? AND state='preparing'",[$id]);error_log('SORTEOWEB PayPhone: preparar pendiente de revision '.$id);throw new DomainException('No se pudo preparar el pago. Revisa las transacciones antes de intentar otra recarga.');}
}
function payphone_validate_confirmation(array $r,array $reply,int $pid): string {
    if(($reply['clientTransactionId']??null)!==$r['id']||!isset($reply['transactionId'])||(string)$reply['transactionId']!==(string)$pid||($reply['currency']??null)!=='USD'||!isset($reply['amount'])||!is_int($reply['amount'])||$reply['amount']!==(int)$r['amount_cents'])return 'review';
    if(($reply['statusCode']??null)===3&&($reply['transactionStatus']??null)==='Approved')return 'approved';
    if(($reply['statusCode']??null)===2&&($reply['transactionStatus']??null)==='Canceled')return 'canceled';return 'review';
}
function payphone_confirm(string $id,int $pid): string {
    $c=wallet_config();if(!SW_WALLET_LIVE_RELEASE||!wallet_settings_valid($c))throw new DomainException('La confirmación de recargas todavía no está habilitada.');
    if(!valid_id($id)||$pid<1)throw new DomainException('Identificador de pago inválido.');
    // Persist the provider identifier before contacting PayPhone, for reconciliation after timeout/crash.
    $prior=tx(function()use($id,$pid){
        $r=one('SELECT * FROM wallet_recharges WHERE id=? FOR UPDATE',[$id]);
        if(!$r||!in_array($r['state'],['pending','review','approved','canceled'],true)||($r['provider_tx_id']!==null&&(string)$r['provider_tx_id']!==(string)$pid))throw new DomainException('No se encontró la solicitud de recarga.');
        if(in_array($r['state'],['approved','canceled'],true))return $r['state'];
        query('UPDATE wallet_recharges SET provider_tx_id=? WHERE id=?',[$pid,$id]);return null;
    });if($prior!==null)return $prior;
    // Serialize confirmations. The ledger and the approved status commit atomically.
    // A network failure is not a decline; keep it in review, never create fictitious credit.
    return tx(function()use($c,$id,$pid){
        $r=one('SELECT * FROM wallet_recharges WHERE id=? FOR UPDATE',[$id]);
        if(in_array($r['state'],['approved','canceled'],true))return $r['state'];
        try{$reply=payphone_api($c,'confirm',['id'=>$pid,'clientTxId'=>$id]);$state=payphone_validate_confirmation($r,$reply,$pid);}catch(Throwable $e){$state='review';error_log('SORTEOWEB PayPhone: confirmacion pendiente de revision '.$id);}
        if($state==='approved'){
            query("INSERT INTO wallet_movements(user_id,direction,amount_cents,concept,reference,recharge_id) VALUES(?,'in',?,'Recarga PayPhone',?,?)",[$r['user_id'],$r['amount_cents'],'payphone:'.$id,$id]);
            query("UPDATE wallet_recharges SET state='approved',confirmed_at=NOW() WHERE id=?",[$id]);
        }else query('UPDATE wallet_recharges SET state=? WHERE id=?',[$state,$id]);
        return $state;
    });
}
function payphone_return(): never {
    // The provider redirects via GET; confirmation uses the stored request, not the session or URL amount.
    if($_SERVER['REQUEST_METHOD']!=='GET'){http_response_code(405);exit;}
    $id=$_GET['clientTransactionId']??null;$pid=filter_var($_GET['id']??null,FILTER_VALIDATE_INT,['options'=>['min_range'=>1]]);
    try{
        if(!valid_id($id)||$pid===false)throw new DomainException('No se recibió una referencia válida de PayPhone.');
        payphone_confirm($id,$pid);
    }catch(Throwable $e){error_log('SORTEOWEB PayPhone: retorno no conciliado');}
    // Do not expose another account's payment result or balance via callback.
    pub_go('account',['tab'=>'transacciones']);
}
