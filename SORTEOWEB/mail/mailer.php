<?php
declare(strict_types=1);
if (!defined('SW_APP') || !SW_PUBLIC) { http_response_code(404); exit; }
require_once __DIR__.'/templates/otp.php';
function mail_settings(): array { $file=__DIR__.'/config.local.php';if(!is_file($file))throw new RuntimeException('Mail not configured');$c=require $file;if(!is_array($c)||!filter_var($c['from_email']??'',FILTER_VALIDATE_EMAIL)||preg_match('/[\r\n]/',(string)($c['from_email']??'')))throw new RuntimeException('Mail config invalid');return $c; }
function smtp_read($s,array $expected): string { $reply='';for($i=0;$i<80;$i++){ $line=fgets($s,4096);if($line===false)throw new RuntimeException('SMTP response failed');$reply.=$line;if(preg_match('/^([0-9]{3}) /',$line,$m)){if(!in_array((int)$m[1],$expected,true))throw new RuntimeException('SMTP rejected request');return $reply;} }throw new RuntimeException('SMTP response too long'); }
function smtp_write($s,string $line): void { $n=strlen($line);$pos=0;while($pos<$n){$w=fwrite($s,substr($line,$pos));if($w===false||$w===0)throw new RuntimeException('SMTP write failed');$pos+=$w;} }
function smtp_cmd($s,string $cmd,array $expected): string { smtp_write($s,$cmd."\r\n");return smtp_read($s,$expected); }
function smtp_send(array $c,string $to,string $subject,string $headers,string $body): void {
    $host=(string)($c['smtp_host']??'');$port=(int)($c['smtp_port']??0);$security=$c['smtp_security']??'';$user=(string)($c['smtp_user']??'');$pass=(string)($c['smtp_password']??'');
    if(!preg_match('/^[a-zA-Z0-9.-]+$/D',$host)||$port<1||$port>65535||!in_array($security,['tls','starttls'],true)||$user===''||$pass==='')throw new RuntimeException('SMTP config invalid');
    $ctx=stream_context_create(['ssl'=>['verify_peer'=>true,'verify_peer_name'=>true,'peer_name'=>$host,'allow_self_signed'=>false,'SNI_enabled'=>true]]);
    $s=@stream_socket_client(($security==='tls'?'tls://':'tcp://').$host.':'.$port,$errno,$err,12,STREAM_CLIENT_CONNECT,$ctx);if(!$s)throw new RuntimeException('SMTP connection failed');stream_set_timeout($s,12);
    try {smtp_read($s,[220]);smtp_cmd($s,'EHLO sorteoweb.local',[250]);if($security==='starttls'){smtp_cmd($s,'STARTTLS',[220]);if(!stream_socket_enable_crypto($s,true,STREAM_CRYPTO_METHOD_TLS_CLIENT))throw new RuntimeException('SMTP TLS failed');smtp_cmd($s,'EHLO sorteoweb.local',[250]);}
        smtp_cmd($s,'AUTH LOGIN',[334]);smtp_cmd($s,base64_encode($user),[334]);smtp_cmd($s,base64_encode($pass),[235]);smtp_cmd($s,'MAIL FROM:<'.$c['from_email'].'>',[250]);smtp_cmd($s,'RCPT TO:<'.$to.'>',[250,251]);smtp_cmd($s,'DATA',[354]);
        $raw='To: '.$to."\r\n".'Subject: '.$subject."\r\n".$headers."\r\n\r\n".$body;$raw=preg_replace('/\r\n|\r|\n/',"\r\n",$raw);$raw=preg_replace('/(?m)^\./','..',$raw);smtp_write($s,rtrim($raw,"\r\n")."\r\n.\r\n");smtp_read($s,[250]);try{smtp_cmd($s,'QUIT',[221]);}catch(Throwable $ignored){}
    }finally{fclose($s);}
}
function send_otp_mail(string $to,string $code): void {
    $c=mail_settings();[$subject,$plain,$html]=otp_template($code);$boundary='sw_'.bin2hex(random_bytes(18));$name=(string)($c['from_name']??'SORTEOWEB');$name='=?UTF-8?B?'.base64_encode($name).'?=';
    $headers='From: '.$name.' <'.$c['from_email'].">\r\nDate: ".date(DATE_RFC2822)."\r\nMIME-Version: 1.0\r\nContent-Type: multipart/alternative; boundary=\"".$boundary.'"';
    $body='--'.$boundary."\r\nContent-Type: text/plain; charset=UTF-8\r\nContent-Transfer-Encoding: base64\r\n\r\n".chunk_split(base64_encode($plain)).'--'.$boundary."\r\nContent-Type: text/html; charset=UTF-8\r\nContent-Transfer-Encoding: base64\r\n\r\n".chunk_split(base64_encode($html)).'--'.$boundary."--\r\n";
    if(($c['transport']??'')==='smtp'){smtp_send($c,$to,$subject,$headers,$body);return;}
    if(($c['transport']??'')!=='mail'||!function_exists('mail')||!@mail($to,$subject,$body,$headers))throw new RuntimeException('PHP mail failed');
}
