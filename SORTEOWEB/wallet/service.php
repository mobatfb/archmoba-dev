<?php
declare(strict_types=1);
if (!defined('SW_APP') || !SW_PUBLIC) { http_response_code(404); exit; }
function wallet_config(): array {
    $file=__DIR__.'/config.local.php';
    $c=is_file($file)?require $file:[];
    return is_array($c)?$c:[];
}
function wallet_settings_valid(array $c): bool {
    $url=$c['base_url']??'';$p=is_string($url)?parse_url($url):false;
    return is_array($p)&&($p['scheme']??'')==='https'&&!empty($p['host'])&&!isset($p['user'],$p['pass'])&&!isset($p['user'])&&!isset($p['pass'])&&!isset($p['query'])&&!isset($p['fragment'])
        &&is_string($c['token']??null)&&trim($c['token'])!==''&&!preg_match('/[\r\n]/',$c['token'])
        &&is_string($c['store_id']??null)&&trim($c['store_id'])!==''
        &&function_exists('curl_init');
}
function wallet_ready(): bool {
    static $ready;
    if($ready!==null)return $ready;
    try{one('SELECT id FROM wallet_movements LIMIT 1');one('SELECT id FROM wallet_recharges LIMIT 1');return $ready=true;}catch(Throwable $e){error_log('SORTEOWEB wallet: migracion pendiente o BD no disponible');return $ready=false;}
}
// Keep real payments off until the complete purchase/refund/reconciliation workflow is released.
// Merchant configuration alone must not enable a partially implemented wallet.
const SW_WALLET_LIVE_RELEASE=false;
function wallet_payments_enabled(): bool {
    $c=wallet_config();return SW_WALLET_LIVE_RELEASE&&wallet_ready()&&($c['enabled']??false)===true&&($c['merchant_authorized']??false)===true&&wallet_settings_valid($c);
}
function wallet_totals(int $uid): array {
    $r=one("SELECT COALESCE(SUM(CASE WHEN direction='in' THEN amount_cents ELSE 0 END),0) AS incoming, COALESCE(SUM(CASE WHEN direction='out' THEN amount_cents ELSE 0 END),0) AS outgoing FROM wallet_movements WHERE user_id=?",[$uid]);
    $in=(int)($r['incoming']??0);$out=(int)($r['outgoing']??0);return ['incoming'=>$in,'outgoing'=>$out,'balance'=>$in-$out];
}
function wallet_amount(mixed $value,array $c): int {
    if(!is_string($value)||!preg_match('/^[0-9]{1,6}(?:[.,][0-9]{1,2})?$/D',$value))throw new DomainException('Introduce un monto válido con máximo dos decimales.');
    $parts=explode('.',str_replace(',','.',$value),2);$n=(int)$parts[0]*100+(int)str_pad($parts[1]??'',2,'0');
    $min=max(100,(int)($c['min_cents']??100));$max=min(100000,(int)($c['max_cents']??5000));
    if($n<$min||$n>$max)throw new DomainException('El monto debe estar entre '.money($min).' y '.money($max).'.');return $n;
}
function wallet_recharge_status(string $state): string {return ['preparing'=>'En preparación','pending'=>'Pendiente de pago','review'=>'Por conciliar','approved'=>'Acreditada','canceled'=>'Cancelada','failed'=>'No completada'][$state]??'Por revisar';}
