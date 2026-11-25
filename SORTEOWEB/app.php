<?php
declare(strict_types=1);
const STORE = __DIR__ . '/storage';
const STATES = ['borrador' => 'Borrador', 'activo' => 'Activo', 'finalizado' => 'Finalizado'];
const TYPES = ['producto' => 'Producto', 'dinero' => 'Dinero'];
const PAYMENTS = ['pendiente' => 'Pendiente', 'pagado' => 'Pagado'];
class InputError extends RuntimeException {}
function h(mixed $v): string { return htmlspecialchars((string)$v, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8'); }
function field(string $k, string $default = ''): string { return is_string($_POST[$k] ?? null) ? trim($_POST[$k]) : $default; }
function q(string $k, string $default = ''): string { return is_string($_GET[$k] ?? null) ? $_GET[$k] : $default; }
function now(): string { return date('c'); }
function uid(): string { return bin2hex(random_bytes(12)); }
function empty_data(): array { return ['raffles'=>[], 'participants'=>[]]; }
function store_init(): void {
    foreach ([STORE, STORE.'/uploads'] as $dir) if (!is_dir($dir) && !mkdir($dir, 0770, true) && !is_dir($dir)) throw new RuntimeException('No se pudo crear el almacenamiento local.');
}
require_once __DIR__.'/db_mysql.php';
function raffle(array $data, string $id): array {
    if (!isset($data['raffles'][$id])) throw new InputError('El sorteo no existe.');
    return $data['raffles'][$id];
}
function people(array $data, string $id): array { return array_values(array_filter($data['participants'], static fn($p)=>$p['raffle_id']===$id)); }
function stats(array $data, array $r): array {
    $ps = people($data, $r['id']); $paid = count(array_filter($ps, static fn($p)=>$p['payment']==='pagado'));
    return ['count'=>count($ps), 'paid'=>$paid, 'pending'=>count($ps)-$paid, 'income'=>$paid*$r['price_cents'], 'pending_income'=>(count($ps)-$paid)*$r['price_cents']];
}
function money(int $cents): string { return '$'.number_format($cents/100, 2, '.', ','); }
function ticket(int $n, int $total): string { return str_pad((string)$n, max(3, strlen((string)$total)), '0', STR_PAD_LEFT); }
function date_label(string $s): string { return date('d/m/Y H:i', strtotime($s)); }
function link_to(string $page='sorteos', array $params=[]): string { return 'index.php?'.http_build_query(['page'=>$page]+$params); }
function redirect_to(string $page, array $params=[]): never { header('Location: '.link_to($page,$params), true,303); exit; }
function flash(string $type, string $message): void { $_SESSION['flash']=['type'=>$type, 'message'=>$message]; }
function required_text(string $key, string $label, int $max): string {
    $s=field($key); if ($s==='' || strlen($s)>$max) throw new InputError("$label es obligatorio (máximo $max bytes)."); return $s;
}
function optional_text(string $key, string $label, int $max): string {
    $s=field($key); if (strlen($s)>$max) throw new InputError("$label excede el máximo permitido."); return $s;
}
function positive_int(string $value, int $max, string $label): int {
    if (!preg_match('/^[0-9]{1,9}$/D',$value) || (int)$value<1 || (int)$value>$max) throw new InputError("$label debe estar entre 1 y $max."); return (int)$value;
}
function parse_price(string $s): int {
    $s=str_replace(',', '.', $s);
    if (!preg_match('/^\d{1,6}(?:\.\d{1,2})?$/D',$s)) throw new InputError('Valor del boleto inválido (máximo 999999,99; hasta dos decimales).');
    $parts=explode('.', $s); return (int)$parts[0]*100+(int)str_pad($parts[1]??'', 2, '0');
}
function upload_photo(string $key): ?string {
    $f=$_FILES[$key]??null;
    if ($f===null || ($f['error']??null)===UPLOAD_ERR_NO_FILE) return null;
    if (!is_array($f) || ($f['error']??null)!==UPLOAD_ERR_OK || !is_string($f['tmp_name']??null)) throw new InputError('No se pudo cargar una foto. Revisa el límite de carga de PHP.');
    if (($f['size']??0)<1 || $f['size']>5*1024*1024 || !is_uploaded_file($f['tmp_name'])) throw new InputError('Cada foto debe pesar hasta 5 MB.');
    $mime=(new finfo(FILEINFO_MIME_TYPE))->file($f['tmp_name']);
    $ext=['image/jpeg'=>'jpg','image/png'=>'png','image/webp'=>'webp'][$mime]??null;
    $size=@getimagesize($f['tmp_name']);
    if (!$ext || !$size || $size[0]<1 || $size[1]<1 || $size[0]>10000 || $size[1]>10000 || ($size['mime']??'')!==$mime) throw new InputError('Solo se aceptan fotos JPG, PNG o WEBP válidas, de hasta 10000 px por lado.');
    $name=uid().'.'.$ext;
    if (!move_uploaded_file($f['tmp_name'], STORE.'/uploads/'.$name)) throw new RuntimeException('No se pudo guardar la foto.');
    return $name;
}
function remove_photo(?string $name): void { if ($name && preg_match('/^[a-f0-9]{24}\.(jpg|png|webp)$/D',$name)) @unlink(STORE.'/uploads/'.$name); }
function handle_image(): never {
    $name=q('image'); if (!preg_match('/^[a-f0-9]{24}\.(jpg|png|webp)$/D',$name,$m)) { http_response_code(404); exit; }
    $path=STORE.'/uploads/'.$name; if (!is_file($path)) { http_response_code(404); exit; }
    header('Content-Type: '.['jpg'=>'image/jpeg','png'=>'image/png','webp'=>'image/webp'][$m[1]]);
    header('X-Content-Type-Options: nosniff'); header('Cache-Control: private, max-age=86400'); header('Content-Length: '.filesize($path)); readfile($path); exit;
}
function demo_data(array &$d): void {
    if ($d['raffles'] || $d['participants']) throw new InputError('Solo puedes cargar ejemplos cuando el sistema está vacío.');
    $examples=[['Sorteo de una consola','Consola de videojuegos para el ganador. Sorteo de demostración.','producto',100,250,'activo'], ['Premio en efectivo','Premio en efectivo de demostración.','dinero',500,100,'borrador'], ['Sorteo de audífonos','Sorteo de prueba finalizado.','producto',50,150,'finalizado']];
    foreach ($examples as $i=>$x) {
        $id=uid(); $d['raffles'][$id]=['id'=>$id,'title'=>$x[0],'description'=>$x[1],'type'=>$x[2],'total'=>$x[3],'price_cents'=>$x[4],'status'=>$x[5],'photos'=>[null,null,null],'created_at'=>now(),'updated_at'=>now(),'finalized_at'=>$x[5]==='finalizado'?now():null];
        if ($i===1) continue;
        foreach ([['Ana Ejemplo',7,'pagado'],['Carlos Ejemplo',15,'pagado'],['Lucía Ejemplo',22,'pendiente']] as $j=>$p) {
            if ($i===2 && $j===2) continue;
            $pid=uid(); $d['participants'][$pid]=['id'=>$pid,'raffle_id'=>$id,'name'=>$p[0],'email'=>'','phone'=>'','number'=>$p[1],'payment'=>$p[2],'created_at'=>now(),'updated_at'=>now()];
        }
    }
}
function process_post(): never {
    if (!hash_equals($_SESSION['csrf'], field('csrf'))) { http_response_code(403); exit('Solicitud inválida. Recarga la página.'); }
    $action=field('action'); $rid=field('raffle_id'); $pid=field('participant_id');
    $page=in_array($action,['save_participant','delete_participant'],true)?'participantes':'sorteos';
    $params=$page==='participantes' && $rid!==''?['id'=>$rid]:[];
    $newPhotos=[]; $oldPhotos=[];
    try {
        db(function(array &$d) use ($action,$rid,$pid,&$newPhotos,&$oldPhotos) {
            switch($action) {
                case 'demo': demo_data($d); break;
                case 'save_raffle':
                    $old=$rid!==''?raffle($d,$rid):null;
                    if ($old && $old['status']==='finalizado') throw new InputError('Un sorteo finalizado no puede modificarse.');
                    $title=required_text('title','Título',180); $description=required_text('description','Descripción',5000);
                    $type=field('type'); if (!isset(TYPES[$type])) throw new InputError('Tipo de sorteo inválido.');
                    $total=positive_int(field('total'),1000000,'Número de boletos'); $price=parse_price(field('price'));
                    $status=field('status','borrador'); if (!in_array($status,['borrador','activo'],true)) throw new InputError('Estado inválido.');
                    if ($old && $old['status']==='activo' && $status!=='activo') throw new InputError('Un sorteo activo no puede volver a borrador.');
                    if ($old && count(people($d,$rid))>0 && ($total!==$old['total'] || $price!==$old['price_cents'] || $type!==$old['type'])) throw new InputError('Con participantes registrados no puedes modificar el número, valor de boletos ni el tipo.');
                    $photos=$old['photos']??[null,null,null];
                    for ($i=0;$i<3;$i++) {
                        $photo=upload_photo('photo_'.$i);
                        if ($photo!==null) { $newPhotos[]=$photo; if ($photos[$i]) $oldPhotos[]=$photos[$i]; $photos[$i]=$photo; }
                        elseif (field('remove_'.$i)==='1' && $photos[$i]) { $oldPhotos[]=$photos[$i]; $photos[$i]=null; }
                    }
                    $id=$old['id']??uid();
                    $d['raffles'][$id]=['id'=>$id,'title'=>$title,'description'=>$description,'type'=>$type,'total'=>$total,'price_cents'=>$price,'status'=>$status,'photos'=>$photos,'created_at'=>$old['created_at']??now(),'updated_at'=>now(),'finalized_at'=>null];
                    break;
                case 'activate_raffle':
                    $r=raffle($d,$rid); if ($r['status']!=='borrador') throw new InputError('Solo se pueden activar borradores.');
                    $d['raffles'][$rid]['status']='activo'; $d['raffles'][$rid]['updated_at']=now(); break;
                case 'finish_raffle':
                    $r=raffle($d,$rid); if ($r['status']!=='activo') throw new InputError('Solo se pueden finalizar sorteos activos.');
                    $d['raffles'][$rid]['status']='finalizado'; $d['raffles'][$rid]['updated_at']=now(); $d['raffles'][$rid]['finalized_at']=now(); break;
                case 'delete_raffle':
                    $r=raffle($d,$rid); if ($r['status']!=='borrador' || people($d,$rid)) throw new InputError('Solo puedes eliminar borradores sin participantes.');
                    $oldPhotos=array_merge($oldPhotos,array_filter($r['photos'])); unset($d['raffles'][$rid]); break;
                case 'save_participant':
                    $r=raffle($d,$rid); if ($r['status']!=='activo') throw new InputError('Solo puedes registrar o editar participantes en sorteos activos.');
                    $old=$pid!==''?($d['participants'][$pid]??null):null;
                    if ($pid!=='' && (!$old || $old['raffle_id']!==$rid)) throw new InputError('Participante no encontrado.');
                    $name=required_text('name','Nombre',180); $email=optional_text('email','Correo',254); $phone=optional_text('phone','Teléfono',50);
                    if ($email!=='' && !filter_var($email,FILTER_VALIDATE_EMAIL)) throw new InputError('Correo electrónico inválido.');
                    $number=positive_int(field('number'),$r['total'],'Número de boleto'); $payment=field('payment','pendiente');
                    if (!isset(PAYMENTS[$payment])) throw new InputError('Estado de pago inválido.');
                    foreach (people($d,$rid) as $p) if ($p['number']===$number && $p['id']!==$pid) throw new InputError('Este número ya está registrado en el sorteo.');
                    $id=$old['id']??uid(); $d['participants'][$id]=['id'=>$id,'raffle_id'=>$rid,'name'=>$name,'email'=>$email,'phone'=>$phone,'number'=>$number,'payment'=>$payment,'created_at'=>$old['created_at']??now(),'updated_at'=>now()]; break;
                case 'delete_participant':
                    $r=raffle($d,$rid); $p=$d['participants'][$pid]??null;
                    if ($r['status']!=='activo' || !$p || $p['raffle_id']!==$rid) throw new InputError('No se puede eliminar esta participación.');
                    if ($p['payment']==='pagado') throw new InputError('No se puede eliminar un boleto pagado. Cambia el estado de pago solo si corresponde a una corrección real.');
                    unset($d['participants'][$pid]); break;
                default: throw new InputError('Acción no reconocida.');
            }
        },true);
        foreach ($oldPhotos as $name) remove_photo($name);
        flash('success', match($action) {'demo'=>'Datos de ejemplo cargados.', 'save_raffle'=>$rid?'Sorteo actualizado.':'Sorteo creado correctamente.', 'activate_raffle'=>'Sorteo activado.', 'finish_raffle'=>'Sorteo finalizado. Sus registros quedaron bloqueados.', 'delete_raffle'=>'Borrador eliminado.', 'save_participant'=>$pid?'Participación actualizada.':'Participante registrado.', 'delete_participant'=>'Participación eliminada.', default=>'Cambios guardados.'});
    } catch (InputError $e) { foreach ($newPhotos as $name) remove_photo($name); flash('error',$e->getMessage()); }
      catch (Throwable $e) { foreach ($newPhotos as $name) remove_photo($name); error_log((string)$e); flash('error','No se pudo completar la operación. Revisa el registro de PHP.'); }
    redirect_to($page,$params);
}
