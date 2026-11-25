<?php
declare(strict_types=1);
if (!defined('SW_APP') || !SW_PUBLIC) { http_response_code(404); exit; }
const OTP_TTL=300;
const OTP_COOLDOWN=60;
const OTP_MAX_TRIES=5;
function otp_secret(): string { static $key;if($key===null){$env=getenv('SW_OTP_SECRET');$cfg=is_file(__DIR__.'/config.local.php')?require __DIR__.'/config.local.php':[];$hex=$env!==false?$env:($cfg['otp_secret']??'');if(!is_string($hex)||!preg_match('/^[a-fA-F0-9]{64}$/D',$hex)||count(array_unique(str_split(strtolower($hex))))<8)throw new RuntimeException('OTP secret missing');$key=hex2bin($hex);}return $key; }
function normalize_email(mixed $email): string { if(!is_string($email))throw new DomainException('Ingresa un correo electrónico válido.');$email=strtolower(trim($email));if(strlen($email)>254||!filter_var($email,FILTER_VALIDATE_EMAIL)||!preg_match('/^[\x21-\x7e]+$/D',$email))throw new DomainException('Ingresa un correo electrónico válido.');return $email; }
function otp_mac(string $email,string $challenge,string $code): string { return hash_hmac('sha256','otp|'.$email.'|'.$challenge.'|'.$code,otp_secret()); }
function otp_bucket(string $type,string $v): string { return hash_hmac('sha256',$type.'|'.$v,otp_secret()); }
// Called inside a transaction. Lock both buckets in stable order before consuming quota.
// Return seconds until quota is available; zero means the request was accepted.
function otp_rate_wait(string $kind,string $email,int $now,bool $consume=true): int {
    $limits=$kind==='send'?[3,20]:[15,60];
    $b=[otp_bucket($kind.':email',$email)=>$limits[0],otp_bucket($kind.':ip',$_SERVER['REMOTE_ADDR']??'unknown')=>$limits[1]];
    ksort($b);$rows=[];$wait=0;
    foreach($b as $bucket=>$max){
        query('INSERT IGNORE INTO auth_attempts(bucket,window_start,attempts) VALUES(?,?,0)',[$bucket,$now]);
        $r=one('SELECT window_start,attempts FROM auth_attempts WHERE bucket=? FOR UPDATE',[$bucket]);
        $start=(int)$r['window_start'];$n=(int)$r['attempts'];
        if($now-$start>=900){$start=$now;$n=0;}
        if($n>=$max)$wait=max($wait,1,$start+900-$now);
        $rows[$bucket]=[$start,$n];
    }
    if($wait>0)return $wait;
    if($consume)foreach($rows as $bucket=>[$start,$n])query('UPDATE auth_attempts SET window_start=?,attempts=? WHERE bucket=?',[$start,$n+1,$bucket]);
    return 0;
}
function otp_rate(string $kind,string $email,int $now): bool { return otp_rate_wait($kind,$email,$now)===0; }
function otp_issue(string $email): void {
    otp_secret();
    require_once dirname(__DIR__).'/mail/mailer.php';
    // A missing or invalid mail configuration is not a send attempt.
    try{$mail=mail_settings();}catch(Throwable $e){error_log('SORTEOWEB OTP: configuración de correo incompleta o inválida');throw new DomainException('No podemos enviar el código en este momento. Inténtalo más tarde o contacta con el equipo de soporte.');}
    $challenge=bin2hex(random_bytes(32));$code=str_pad((string)random_int(0,999999),6,'0',STR_PAD_LEFT);$mac=otp_mac($email,$challenge,$code);
    $result=tx(function()use($email,$challenge,$mac){
        // Check the rate limit without consuming it before creating an OTP row.
        $now=time();$wait=otp_rate_wait('send',$email,$now,false);
        if($wait>0)return ['wait'=>$wait,'kind'=>'limit'];
        query('INSERT IGNORE INTO auth_otp(email,challenge_id,code_mac,sent_at,expires_at,attempts,used_at) VALUES(?,?,?,?,?,0,NULL)',[$email,str_repeat('0',64),str_repeat('0',64),0,0]);
        $row=one('SELECT sent_at FROM auth_otp WHERE email=? FOR UPDATE',[$email]);$now=time();
        $cooldown=max(0,OTP_COOLDOWN-($now-(int)$row['sent_at']));
        // Rejected cooldown requests do not consume either rate-limit bucket.
        if($cooldown>0)return ['wait'=>$cooldown,'kind'=>'cooldown'];
        // The transaction still owns both rate-limit locks.
        $wait=otp_rate_wait('send',$email,$now);
        if($wait>0)return ['wait'=>$wait,'kind'=>'limit'];
        query('UPDATE auth_otp SET challenge_id=?,code_mac=?,sent_at=?,expires_at=?,attempts=0,used_at=NULL WHERE email=?',[$challenge,$mac,$now,$now+OTP_TTL,$email]);
        return ['wait'=>0,'sent_at'=>$now];
    });
    if($result['wait']>0){
        $wait=$result['wait'];$minutes=intdiv($wait,60);$seconds=$wait%60;
        $duration=$minutes>0?$minutes.' min '.$seconds.' s':$seconds.' s';
        throw new DomainException($result['kind']==='cooldown'?'Puedes solicitar otro código en '.$duration.'. Si ya lo solicitaste, revisa tu correo y spam.':'Alcanzaste el límite de solicitudes de códigos. Intenta nuevamente en '.$duration.'.');
    }
    $now=$result['sent_at'];$sent=false;
    try{send_otp_mail($email,$code,$mail);$sent=true;}catch(Throwable $e){error_log('SORTEOWEB OTP: fallo de transporte de correo');}finally{unset($code);}
    if(!$sent){
        // Keep the quota and cooldown for actual transport attempts, even on failure.
        query('UPDATE auth_otp SET used_at=?,code_mac=? WHERE email=? AND challenge_id=?',[time(),str_repeat('0',64),$email,$challenge]);
        if(otp_session_email()===$email)$_SESSION['otp_sent_at']=$now;
    }
    try{query('INSERT INTO mail_logs(email_digest,purpose,status) VALUES(?,?,?)',[otp_bucket('log',$email),'login_otp',$sent?'sent':'failed']);}catch(Throwable $e){error_log('SORTEOWEB OTP: fallo de bitácora');}
    if(!$sent)throw new DomainException('No se pudo enviar el código. Inténtalo de nuevo después de 60 segundos. Si el problema continúa, contacta con el equipo de soporte.');
    $_SESSION['otp_email']=$email;$_SESSION['otp_challenge']=$challenge;$_SESSION['otp_sent_at']=$now;
}
function otp_verify(string $email,string $challenge,mixed $code): ?int {
    if(!is_string($code)||!preg_match('/^[0-9]{6}$/D',$code))throw new DomainException('Introduce los seis dígitos del código.');$now=time();$mac=otp_mac($email,$challenge,$code);
    return tx(function()use($email,$challenge,$now,$mac){if(!otp_rate('verify',$email,$now))return null;$r=one('SELECT * FROM auth_otp WHERE email=? FOR UPDATE',[$email]);if(!$r||!hash_equals($r['challenge_id'],$challenge)||$r['used_at']!==null||$now>=(int)$r['expires_at']||(int)$r['attempts']>=OTP_MAX_TRIES)return null;if(!hash_equals($r['code_mac'],$mac)){query('UPDATE auth_otp SET attempts=attempts+1 WHERE email=?',[$email]);return null;}
        query('UPDATE auth_otp SET used_at=?,code_mac=? WHERE email=?',[$now,str_repeat('0',64),$email]);query('INSERT INTO users(email,verified_at) VALUES(?,NOW()) ON DUPLICATE KEY UPDATE verified_at=VALUES(verified_at)',[$email]);$u=one('SELECT id,active FROM users WHERE email=? FOR UPDATE',[$email]);return $u&&(int)$u['active']===1?(int)$u['id']:null;});
}
function otp_session_email(): ?string { $e=$_SESSION['otp_email']??null;$c=$_SESSION['otp_challenge']??null;return is_string($e)&&is_string($c)&&preg_match('/^[a-f0-9]{64}$/D',$c)?$e:null; }
