<?php
declare(strict_types=1);
if (!defined('SW_APP') || SW_PUBLIC) { http_response_code(404); exit; }
function go(string $page='sorteos',array $params=[]): never { header('Location: index.php?'.http_build_query(['page'=>$page]+$params),true,303);exit; }
function verify_csrf(): void { $v=$_POST['csrf']??null;if(!is_string($v)||!hash_equals(token(),$v)){http_response_code(403);render_message('Solicitud inválida','Recarga la página e inténtalo de nuevo.');exit;} }
function flash(string $message,string $kind='success'): void { $_SESSION['flash']=[$message,$kind]; }
function integer(string $key,int $min,int $max): int { $v=filter_var($_POST[$key]??null,FILTER_VALIDATE_INT,['options'=>['min_range'=>$min,'max_range'=>$max]]);if($v===false)throw new DomainException('Número inválido: '.$key);return $v; }
function price_cents(string $v): int { if(!preg_match('/^(?:0|[1-9][0-9]{0,6})(?:[.,][0-9]{1,2})?$/D',$v))throw new DomainException('Ingresa un valor monetario válido.');$p=explode('.',str_replace(',','.',$v));$n=(int)$p[0]*100+(int)str_pad($p[1]??'',2,'0');if($n<1||$n>100000000)throw new DomainException('El valor debe estar entre $0,01 y $1.000.000,00.');return $n; }
function money_input(int|string $c): string { return number_format(((int)$c)/100,2,'.',''); }
function chip(string $s): string { return '<span class="status '.h($s).'">'.h(state_name($s)).'</span>'; }
function logout_session(): void { $_SESSION=[];session_regenerate_id(true); }
function current_admin(): ?array { $id=(int)($_SESSION['admin_id']??0);if(!$id)return null;if(time()-(int)($_SESSION['last_seen']??0)>1800){logout_session();return null;}$a=one('SELECT id,username,must_change_password FROM admins WHERE id=? AND active=1',[$id]);if(!$a){logout_session();return null;}$_SESSION['last_seen']=time();return $a; }
function record_id(string $key,bool $allow_new=false): string { $id=$_POST[$key]??null;if($allow_new&&$id==='0')return '';if(!valid_id($id))throw new DomainException('Registro inválido.');return $id; }
function audit(array $u,string $action,?string $id,string $detail='',?string $participant=null): void {
    $type=$action==='password_change'?'admin':($participant!==null?'participant':'raffle');
    $op=in_array($action,['delete_raffle','participant_delete'],true)?'delete':(in_array($action,['raffle_create','participant_create'],true)?'create':'update');
    $entity=$participant??$id??(string)$u['id'];
    query('INSERT INTO audit_events(admin_id,entity_type,entity_id,action,details) VALUES(?,?,?,?,?)',[$u['id'],$type,$entity,$op,json_encode(['event'=>$action,'raffle_id'=>$id,'detail'=>$detail],JSON_THROW_ON_ERROR|JSON_UNESCAPED_UNICODE)]);
}
function consume_login_attempt(string $username): bool {
    $ip=$_SERVER['REMOTE_ADDR']??'unknown';$limits=[hash('sha256','ip:'.$ip)=>25,hash('sha256','pair:'.$ip.':'.strtolower($username))=>5];ksort($limits);$now=time();
    return tx(function()use($limits,$now){$allowed=true;foreach($limits as $key=>$max){query('INSERT INTO login_limits(bucket,window_start,attempts) VALUES(?,?,0) ON DUPLICATE KEY UPDATE bucket=bucket',[$key,$now]);$r=one('SELECT window_start,attempts FROM login_limits WHERE bucket=? FOR UPDATE',[$key]);$expired=$now-(int)$r['window_start']>=900;$n=$expired?0:(int)$r['attempts'];if($n>=$max)$allowed=false;else query('UPDATE login_limits SET window_start=?,attempts=? WHERE bucket=?',[$expired?$now:$r['window_start'],$n+1,$key]);}return $allowed;});
}
function login(): void { $username=field('username',120);$password=$_POST['password']??'';if(!is_string($password)||$password===''||strlen($password)>256)throw new DomainException('Usuario o contraseña incorrectos.');if(!consume_login_attempt($username))throw new DomainException('Demasiados intentos. Intenta nuevamente en 15 minutos.');$a=one('SELECT * FROM admins WHERE username=? AND active=1',[$username]);$hash=$a['password_hash']??'$2y$12$9P9t8Dqm36bXL0VCk.9tJ.qteChR3MW/lM.ovtO98yV5f2yihxILi';$valid=password_verify($password,$hash);if(!$a||!$valid)throw new DomainException('Usuario o contraseña incorrectos.');session_regenerate_id(true);$_SESSION=['admin_id'=>(int)$a['id'],'last_seen'=>time()];flash('Sesión iniciada.');go(); }
function change_password(array $u): void { $old=$_POST['current_password']??'';$new=$_POST['new_password']??'';$repeat=$_POST['confirm_password']??'';if(!is_string($old)||!is_string($new)||!is_string($repeat)||strlen($old)>256)throw new DomainException('Contraseña inválida.');if($new!==$repeat||strlen($new)<12||strlen($new)>72||!preg_match('/[A-Z]/',$new)||!preg_match('/[a-z]/',$new)||!preg_match('/[0-9]/',$new)||!preg_match('/[^a-zA-Z0-9]/',$new))throw new DomainException('Usa 12 a 72 caracteres, mayúsculas, minúsculas, número y símbolo.');tx(function()use($u,$old,$new){$a=one('SELECT password_hash FROM admins WHERE id=? FOR UPDATE',[$u['id']]);if(!$a||!password_verify($old,$a['password_hash']))throw new DomainException('La contraseña actual no coincide.');query('UPDATE admins SET password_hash=?,must_change_password=0 WHERE id=?',[password_hash($new,PASSWORD_DEFAULT),$u['id']]);audit($u,'password_change',null);});session_regenerate_id(true);flash('Contraseña actualizada.');go(); }
function raffle_lock(string $id): array { $r=one('SELECT r.*,r.total AS ticket_count,r.price_cents AS ticket_price_cents FROM raffles r WHERE id=? FOR UPDATE',[$id]);if(!$r)throw new DomainException('Sorteo no encontrado.');return $r; }
function load_photos(): array { $images=[];for($i=1;$i<=3;$i++){ $f=$_FILES['photo'.$i]??null;if(!$f||$f['error']===UPLOAD_ERR_NO_FILE)continue;if($f['error']!==UPLOAD_ERR_OK||!is_uploaded_file($f['tmp_name'])||$f['size']>2097152)throw new DomainException('Cada fotografía debe pesar máximo 2 MB.');$mime=(new finfo(FILEINFO_MIME_TYPE))->file($f['tmp_name']);$size=@getimagesize($f['tmp_name']);if(!in_array($mime,['image/jpeg','image/png','image/webp'],true)||!$size||$size[0]>8000||$size[1]>8000)throw new DomainException('Solo fotografías JPG, PNG o WebP válidas (máximo 8000 px por lado).');$bytes=file_get_contents($f['tmp_name']);if($bytes===false)throw new DomainException('No se pudo leer la fotografía.');$images[$i]=[$mime,$bytes];}return $images; }
function save_raffle(array $u): void {
    $id=record_id('raffle_id',true);$title=field('title',180);$desc=field('description',10000,false);$type=field('type',10);
    if(!in_array($type,['producto','dinero'],true))throw new DomainException('Tipo de sorteo inválido.');
    $total=integer('ticket_count',1,1000000);$price=price_cents(field('price',15));$photos=load_photos();
    tx(function()use($u,$id,$title,$desc,$type,$total,$price,$photos){
        $new=$id==='';
        if(!$new){$r=raffle_lock($id);if($r['status']!=='borrador')throw new DomainException('Solo se editan sorteos en borrador.');
            if(one('SELECT raffle_id FROM raffle_evidence WHERE raffle_id=?',[$id]))throw new DomainException('No se pueden cambiar las condiciones de un sorteo con evidencia registrada.');
            if(one('SELECT id FROM participants WHERE raffle_id=? LIMIT 1',[$id]))throw new DomainException('No se puede editar un sorteo con boletos registrados.');
            query('UPDATE raffles SET title=?,description=?,type=?,total=?,price_cents=?,updated_at=NOW() WHERE id=?',[$title,$desc,$type,$total,$price,$id]);
        }else{$id=bin2hex(random_bytes(12));query('INSERT INTO raffles(id,title,description,type,total,price_cents,created_at,updated_at) VALUES(?,?,?,?,?,?,NOW(),NOW())',[$id,$title,$desc,$type,$total,$price]);}
        for($i=1;$i<=3;$i++){
            if(isset($_POST['remove_photo'.$i])&&!isset($photos[$i]))query('DELETE FROM raffle_photos WHERE raffle_id=? AND slot=?',[$id,$i]);
            if(isset($photos[$i])){[$mime,$content]=$photos[$i];$filename=bin2hex(random_bytes(16)).'.'.(['image/jpeg'=>'jpg','image/png'=>'png','image/webp'=>'webp'][$mime]);
                query('INSERT INTO raffle_photos(raffle_id,slot,filename,mime,content) VALUES(?,?,?,?,?) ON DUPLICATE KEY UPDATE filename=VALUES(filename),mime=VALUES(mime),content=VALUES(content)',[$id,$i,$filename,$mime,$content]);}
        }
        audit($u,$new?'raffle_create':'raffle_save',$id);
    });flash('Sorteo guardado.');go();
}
function raffle_transition(array $u,string $action): void {
    $id=record_id('raffle_id');tx(function()use($u,$action,$id){$r=raffle_lock($id);
        if($action==='activate'&&$r['status']==='borrador')query("UPDATE raffles SET status='activo',updated_at=NOW() WHERE id=?",[$id]);
        elseif($action==='finish'&&$r['status']==='activo')query("UPDATE raffles SET status='finalizado',finalized_at=NOW(),updated_at=NOW() WHERE id=?",[$id]);
        elseif($action==='delete_raffle'&&$r['status']==='borrador'){
            if(one('SELECT id FROM participants WHERE raffle_id=? LIMIT 1',[$id])||one('SELECT raffle_id FROM raffle_evidence WHERE raffle_id=?',[$id]))throw new DomainException('El sorteo conserva registros relacionados y no se puede eliminar.');
            query('DELETE FROM raffles WHERE id=?',[$id]);
        }else throw new DomainException('Cambio de estado no permitido.');audit($u,$action,$id);
    });flash('Sorteo actualizado.');go();
}
function save_participant(array $u): void {
    $rid=record_id('raffle_id');$pid=record_id('participant_id',true);$number=integer('ticket_number',1,1000000);$name=field('name',180);$email=field('email',254,false);$phone=field('phone',50,false);$pay=field('payment_status',10);$link=isset($_POST['link_user'])&&$_POST['link_user']==='1';
    if(($email!==''&&!filter_var($email,FILTER_VALIDATE_EMAIL))||!in_array($pay,['pendiente','pagado'],true))throw new DomainException('Correo o estado de pago inválido.');
    tx(function()use($u,$rid,$pid,$number,$name,$email,$phone,$pay,$link){$r=raffle_lock($rid);if($r['status']!=='activo')throw new DomainException('El sorteo debe estar activo.');if($number>(int)$r['total'])throw new DomainException('Número fuera del rango de boletos.');
        $p=$pid!==''?one('SELECT * FROM participants WHERE id=? AND raffle_id=? FOR UPDATE',[$pid,$rid]):null;
        if($pid!==''&&!$p)throw new DomainException('Participante no encontrado.');
        if($p&&$p['payment']==='pagado'&&($pay!=='pagado'||$number!==(int)$p['number']))throw new DomainException('Un boleto pagado no puede cambiar de número ni volver a pendiente.');
        if(one('SELECT id FROM participants WHERE raffle_id=? AND number=? AND id<>?',[$rid,$number,$pid]))throw new DomainException('Ese número ya está registrado.');
        $uid=$p['user_id']??null;
        if($uid!==null){$account=one('SELECT email FROM users WHERE id=?',[$uid]);if(!$account||strtolower($email)!==$account['email'])throw new DomainException('No se puede cambiar el correo de un boleto ya vinculado a una cuenta.');}
        elseif($link){$account=one('SELECT id FROM users WHERE email=? AND active=1 AND profile_complete=1',[strtolower($email)]);if(!$account)throw new DomainException('El correo debe pertenecer a una cuenta verificada con perfil completo.');$uid=$account['id'];}
        if($p)query('UPDATE participants SET number=?,name=?,email=?,phone=?,payment=?,user_id=?,updated_at=NOW() WHERE id=? AND raffle_id=?',[$number,$name,$email,$phone,$pay,$uid,$pid,$rid]);
        else{$pid=bin2hex(random_bytes(12));query('INSERT INTO participants(id,raffle_id,number,name,email,phone,payment,user_id,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,NOW(),NOW())',[$pid,$rid,$number,$name,$email,$phone,$pay,$uid]);}
        audit($u,$p?'participant_save':'participant_create',$rid,'Boleto '.$number.'; '.$pay,$pid);
    });flash('Participante guardado.');go('participantes',['id'=>$rid]);
}
function delete_participant(array $u): void {
    $rid=record_id('raffle_id');$pid=record_id('participant_id');tx(function()use($u,$rid,$pid){$r=raffle_lock($rid);$p=one('SELECT * FROM participants WHERE id=? AND raffle_id=? FOR UPDATE',[$pid,$rid]);
        if($r['status']!=='activo'||!$p||$p['payment']!=='pendiente')throw new DomainException('Solo puedes liberar boletos pendientes de sorteos activos.');
        query('DELETE FROM participants WHERE id=? AND raffle_id=?',[$pid,$rid]);audit($u,'participant_delete',$rid,'Boleto '.$p['number'],$pid);
    });flash('Boleto liberado.');go('participantes',['id'=>$rid]);
}
function raffle_list(?string $status=null): array {
    $sql="SELECT r.*,r.total AS ticket_count,r.price_cents AS ticket_price_cents,COALESCE(p.registered,0) registered,COALESCE(p.paid,0) paid,COALESCE(p.paid,0)*r.price_cents AS income,COALESCE(p.pending,0)*r.price_cents AS pending_income,(SELECT MIN(slot) FROM raffle_photos f WHERE f.raffle_id=r.id) first_photo FROM raffles r LEFT JOIN (SELECT raffle_id,COUNT(*) registered,SUM(payment='pagado') paid,SUM(payment='pendiente') pending FROM participants GROUP BY raffle_id) p ON r.id=p.raffle_id";
    return all($sql.($status?' WHERE r.status=?':'').' ORDER BY r.created_at DESC,r.id DESC',$status?[$status]:[]);
}
function serve_photo(): never {
    $id=$_GET['photo']??null;$slot=filter_var($_GET['slot']??null,FILTER_VALIDATE_INT);if(!valid_id($id)||!in_array($slot,[1,2,3],true)){http_response_code(404);exit;}
    $p=one('SELECT filename,mime,content FROM raffle_photos WHERE raffle_id=? AND slot=?',[$id,$slot]);if(!$p){http_response_code(404);exit;}
    $mime=$p['mime'];$bytes=$p['content'];
    if($bytes===null && preg_match('/^[a-f0-9]{24,64}\.(jpg|jpeg|png|webp)$/D',$p['filename'])){
        $path=dirname(__DIR__).'/storage/uploads/'.$p['filename'];if(is_file($path)&&filesize($path)<=5242880){$mime=(new finfo(FILEINFO_MIME_TYPE))->file($path);$bytes=file_get_contents($path);}
    }
    if(!is_string($bytes)||!in_array($mime,['image/jpeg','image/png','image/webp'],true)){http_response_code(404);exit;}
    session_write_close();header('Content-Type: '.$mime);header('Content-Length: '.strlen($bytes));echo $bytes;exit;
}
