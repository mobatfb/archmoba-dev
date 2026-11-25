<?php
declare(strict_types=1);
if(!defined('SW_APP')){http_response_code(404);exit;}
require_once __DIR__.'/generator.php';
function draw_key(): string {
    if(!function_exists('sodium_crypto_secretbox'))throw new DomainException('Habilita Sodium en la versión PHP del sitio.');
    $env=getenv('SW_EVIDENCE_KEY');$file=__DIR__.'/config.local.php';
    if($env!==false){$hex=$env;}else{
        clearstatcache(true,$file);
        if(!is_file($file)||!is_readable($file))throw new DomainException('No se encontró la clave privada de evidencia. Si ya tienes sorteos con evidencia, restaura la clave original.');
        $c=require $file;$hex=is_array($c)?($c['key_hex']??''):'';
    }
    if(!is_string($hex)||!preg_match('/^[a-fA-F0-9]{64}$/D',$hex)||count(array_unique(str_split(strtolower($hex))))<8)throw new DomainException('La clave privada de evidencia no es válida. No se reemplazó.');
    return hex2bin($hex);
}
// Only an authenticated activation may initialize a missing key, never a reveal.
function draw_prepare_key(): void {
    if(!function_exists('sodium_crypto_secretbox'))throw new DomainException('Habilita Sodium en la versión PHP del sitio.');
    $file=__DIR__.'/config.local.php';clearstatcache(true,$file);
    if(getenv('SW_EVIDENCE_KEY')!==false||file_exists($file)||is_link($file)){draw_key();return;}
    // No automatic recovery: a new key cannot decrypt any previous commitment.
    if(one('SELECT raffle_id FROM raffle_evidence WHERE sealed_result IS NOT NULL LIMIT 1 FOR UPDATE')){
        clearstatcache(true,$file);
        if(getenv('SW_EVIDENCE_KEY')!==false||is_file($file)){draw_key();return;}
        throw new DomainException('Falta la clave privada original y ya existen sorteos con evidencia. Restaura config.local.php desde tu respaldo.');
    }
    $bytes="<?php\nif(!defined('SW_APP')){http_response_code(404);exit;}\nreturn ['key_hex'=>'".bin2hex(random_bytes(32))."'];\n";
    // Exclusive creation: never truncate, replace or rotate an existing key.
    $mask=umask(0077);try{$f=@fopen($file,'x');}finally{umask($mask);}
    if($f===false){
        clearstatcache(true,$file);
        if(getenv('SW_EVIDENCE_KEY')!==false||is_file($file)){draw_key();return;}
        throw new DomainException('No se pudo crear la clave privada. PHP necesita permiso de escritura en evidence/.');
    }
    try{
        if(!@chmod($file,0600)||fwrite($f,$bytes)!==strlen($bytes)||!fflush($f))throw new DomainException('No se pudo guardar la clave privada. Revisa los permisos del hosting.');
    }finally{fclose($f);}
    draw_key();
}
function draw_seal(array $data): string {$key=draw_key();$nonce=random_bytes(SODIUM_CRYPTO_SECRETBOX_NONCEBYTES);return $nonce.sodium_crypto_secretbox(json_encode($data,JSON_THROW_ON_ERROR),$nonce,$key);}
function draw_unseal(string $sealed): array {$key=draw_key();$n=SODIUM_CRYPTO_SECRETBOX_NONCEBYTES;$plain=sodium_crypto_secretbox_open(substr($sealed,$n),substr($sealed,0,$n),$key);if($plain===false)throw new DomainException('No se pudo verificar la evidencia protegida.');return json_decode($plain,true,512,JSON_THROW_ON_ERROR);}
function draw_create(array $r): void {
    if((int)$r['draw_version']!==1||!in_array($r['close_mode'],['fecha','capacidad'],true)||($r['close_mode']==='fecha'&&(empty($r['closes_at'])||(int)$r['closes_at']<=time()))||($r['close_mode']==='capacidad'&&((int)$r['participation_limit']<1||($r['participation_mode']==='exclusivo'&&(int)$r['participation_limit']!==(int)$r['total'])))||($r['type']==='dinero'||$r['participation_mode']==='compartido')&&(int)$r['prize_cents']<1)throw new DomainException('Edita el borrador y configura el premio y la condición de cierre válida.');
    if(one('SELECT raffle_id FROM raffle_evidence WHERE raffle_id=? FOR UPDATE',[$r['id']])||one('SELECT id FROM participants WHERE raffle_id=? LIMIT 1 FOR UPDATE',[$r['id']]))throw new DomainException('El borrador ya tiene evidencia o participantes.');
    draw_prepare_key();$number=random_int(1,(int)$r['total']);$password=bin2hex(random_bytes(24));
    $rules=['version'=>1,'raffle_id'=>$r['id'],'title'=>$r['title'],'mode'=>$r['participation_mode'],'type'=>$r['type'],'total'=>(int)$r['total'],'price_cents'=>(int)$r['price_cents'],'prize_cents'=>$r['prize_cents']===null?null:(int)$r['prize_cents'],'close_mode'=>$r['close_mode'],'participation_limit'=>$r['participation_limit']===null?null:(int)$r['participation_limit'],'closes_at'=>$r['closes_at']===null?null:(int)$r['closes_at'],'no_winner_policy'=>'refund-review-no-redraw','exclusive_incomplete_policy'=>'refund-review','policy'=>'preselected-random-int-v1'];
    $zip=draw_zip($rules,$number,$password);$sha=hash('sha256',$zip);
    $sealed=draw_seal(['id'=>$r['id'],'number'=>$number,'password'=>$password,'sha256'=>$sha,'rules'=>$rules]);
    query('INSERT INTO raffle_evidence(raffle_id,filename,storage_key,sha256,size_bytes,created_at,published_at,archive,sealed_result) VALUES(?,?,?,?,?,NOW(),NOW(),?,?)',[$r['id'],'resultado-'.$r['id'].'.zip',bin2hex(random_bytes(24)),$sha,strlen($zip),$zip,$sealed]);
}
function draw_due(array $r,int $paid,?int $now=null): bool {
    if($r['close_mode']==='capacidad')return (int)$r['participation_limit']>0&&$paid>=(int)$r['participation_limit'];
    return $r['close_mode']==='fecha'&&$r['closes_at']!==null&&(int)$r['closes_at']<=($now??time());
}
function draw_money_photo(): never {
    session_write_close();header('Content-Type: image/svg+xml; charset=UTF-8');header('X-Content-Type-Options: nosniff');header("Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'; sandbox");readfile(dirname(__DIR__).'/assets/premio-dinero.svg');exit;
}
function draw_close_label(array $r): string {
    if(($r['close_mode']??null)==='capacidad')return 'Al alcanzar '.number_format((int)$r['participation_limit']).' participaciones pagadas';
    if(($r['close_mode']??null)==='fecha'&&!empty($r['closes_at']))return 'El '.(new DateTimeImmutable('@'.(int)$r['closes_at']))->setTimezone(new DateTimeZone('America/Guayaquil'))->format('d/m/Y H:i').' (Ecuador)';
    return 'Reglas originales';
}
function draw_share(int $cents,int $count,int $i): int {if($count<1||$i<0||$i>=$count||$cents<0)throw new InvalidArgumentException('Reparto inválido');return intdiv($cents,$count)+($i<$cents%$count?1:0);}
// Caller must hold the raffle row lock in the SAME transaction as ticket writes.
function draw_finish_locked(array $r): bool {
    if($r['status']!=='activo'||(int)$r['draw_version']!==1)return false;
    $id=$r['id'];$paid=(int)(one("SELECT COUNT(*) AS n FROM participants WHERE raffle_id=? AND payment='pagado'",[$id])['n']??0);
    if(!draw_due($r,$paid))return false;
    if($r['close_mode']==='capacidad'&&$paid!==(int)$r['participation_limit'])throw new DomainException('La capacidad registrada no coincide con la condición publicada. Requiere conciliación.');
    $e=one('SELECT sha256,archive,sealed_result FROM raffle_evidence WHERE raffle_id=? FOR UPDATE',[$id]);
    if(!$e||!is_string($e['archive'])||!is_string($e['sealed_result'])||!hash_equals($e['sha256'],hash('sha256',$e['archive'])))throw new DomainException('La evidencia original no está disponible o no coincide. No se cerró el sorteo.');
    $d=draw_unseal($e['sealed_result']);$number=$d['number']??null;
    $rules=$d['rules']??[];
    if(($d['id']??null)!==$id||($d['sha256']??null)!==$e['sha256']||!is_int($number)||$number<1||$number>(int)$r['total']||!is_string($d['password']??null)||($rules['title']??null)!==$r['title']||($rules['mode']??null)!==$r['participation_mode']||($rules['total']??null)!==(int)$r['total']||($rules['price_cents']??null)!==(int)$r['price_cents']||($rules['close_mode']??null)!==$r['close_mode']||($rules['participation_limit']??null)!==($r['participation_limit']===null?null:(int)$r['participation_limit'])||($rules['closes_at']??null)!==($r['closes_at']===null?null:(int)$r['closes_at'])||($rules['type']??null)!==$r['type']||($rules['prize_cents']??null)!==($r['prize_cents']===null?null:(int)$r['prize_cents']))throw new DomainException('Las reglas no coinciden con el compromiso original.');
    $w=all("SELECT id FROM participants WHERE raffle_id=? AND number=? AND payment='pagado' ORDER BY id",[$id,$number]);
    $eligible=($r['participation_mode']==='compartido'||$paid===(int)$r['total'])&&count($w)>0;
    if($eligible){
        query('INSERT INTO winners(raffle_id,winning_number,participant_id,revealed_at) VALUES(?,?,?,NOW())',[$id,$number,count($w)===1?$w[0]['id']:null]);
        $physical=$r['type']==='producto'&&count($w)===1;
        foreach($w as $i=>$p){$amount=$physical?null:draw_share((int)$r['prize_cents'],count($w),$i);query('INSERT INTO prize_awards(raffle_id,participant_id,winning_number,prize_type,amount_cents) VALUES(?,?,?,?,?)',[$id,$p['id'],$number,$physical?'producto':'dinero',$amount]);}
    }else{
        $reason=$r['participation_mode']==='exclusivo'?'venta_incompleta':'sin_compradores_del_numero';
        query("INSERT INTO raffle_refund_reviews(raffle_id,participant_id,amount_cents,reason) SELECT raffle_id,id,?,? FROM participants WHERE raffle_id=? AND payment='pagado'",[(int)$r['price_cents'],$reason,$id]);
    }
    query('UPDATE raffle_evidence SET revealed_number=?,revealed_password=? WHERE raffle_id=?',[$number,$d['password'],$id]);
    query("UPDATE raffles SET status='finalizado',draw_outcome=?,finalized_at=NOW(),updated_at=NOW() WHERE id=?",[$eligible?'premiado':'devolucion_pendiente',$id]);
    query("INSERT INTO audit_events(admin_id,entity_type,entity_id,action,details) VALUES(NULL,'evidence',?,'update',?)",[$id,json_encode(['event'=>'draw_reveal','sha256'=>$e['sha256'],'outcome'=>$eligible?'premiado':'devolucion_pendiente'],JSON_THROW_ON_ERROR)]);
    return true;
}
function draw_process_due(): int {
    $closed=0;foreach(all("SELECT id FROM raffles WHERE status='activo' AND draw_version=1 AND ((close_mode='fecha' AND closes_at<=?) OR (close_mode='capacidad' AND participation_limit<=(SELECT COUNT(*) FROM participants p WHERE p.raffle_id=raffles.id AND p.payment='pagado'))) ORDER BY id LIMIT 50",[time()]) as $row){try{$closed+=(int)tx(function()use($row){$r=one('SELECT * FROM raffles WHERE id=? FOR UPDATE',[$row['id']]);return $r?draw_finish_locked($r):false;});}catch(Throwable $e){error_log('SORTEOWEB cierre: '.get_class($e).' '.$e->getCode());}}return $closed;
}
