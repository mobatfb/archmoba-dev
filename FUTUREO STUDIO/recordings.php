<?php
declare(strict_types=1);
// FUTUREO STUDIO v0.1.22 - authenticated audio storage and history.
date_default_timezone_set('America/Guayaquil');
require_once __DIR__ . '/projects.php';
header('X-Content-Type-Options: nosniff');
header('Cache-Control: no-store');
header('Referrer-Policy: same-origin');
function reply(array $data, int $status = 200): void {
    http_response_code($status);
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode($data, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}
function fail(string $message, int $status = 400): void { reply(['ok'=>false,'error'=>$message], $status); }
function iniBytes(string $value): int {
    $value = trim($value);
    if ($value === '' || $value === '-1' || $value === '0') return PHP_INT_MAX;
    $unit = strtolower(substr($value,-1));
    return (int) ((float)$value * (['k'=>1024,'m'=>1048576,'g'=>1073741824][$unit] ?? 1));
}
function maxUpload(): int {
    return max(0,min(25*1048576,iniBytes((string)ini_get('upload_max_filesize')),iniBytes((string)ini_get('post_max_size'))-65536));
}
function readProject(string $path): array {
    $data = json_decode((string) @file_get_contents($path), true);
    if (!is_array($data) || ($data['format'] ?? null) !== 'FPRJ') fail('El proyecto no es válido.',422);
    return $data;
}
function savedRecordings(array $data): array {
    $items = $data['content']['recordings'] ?? [];
    return is_array($items) ? array_values(array_filter($items, static function($r){
        return is_array($r) && isset($r['id'],$r['file'],$r['mime']) && is_string($r['id']) && preg_match('/\A[a-f0-9]{24}\z/',$r['id']) && is_string($r['file']) && ((preg_match('/\Avoz_[0-9_]+_[a-f0-9]{24}\.(webm|ogg|m4a|wav)\z/',$r['file']) && in_array($r['mime'],['audio/webm','audio/ogg','audio/mp4','audio/wav'],true)) || (preg_match('/\Aaudio_[0-9_]+_[a-f0-9]{24}\.mp3\z/',$r['file']) && $r['mime']==='audio/mpeg'));
    })) : [];
}
function detectAudio(string $tmp): ?array {
    $h = @file_get_contents($tmp,false,null,0,64);
    if (!is_string($h)) return null;
    if (substr($h,0,4) === "\x1a\x45\xdf\xa3" && strpos($h,'webm') !== false) return ['webm','audio/webm'];
    if (substr($h,0,4) === 'OggS' && (strpos($h,'OpusHead') !== false || strpos($h,'vorbis') !== false)) return ['ogg','audio/ogg'];
    if (strlen($h) >= 12 && substr($h,4,4) === 'ftyp') return ['m4a','audio/mp4'];
    return null;
}
function ensureDir(string $dir): bool {
    if (is_link($dir)) return false;
    if (!is_dir($dir) && !@mkdir($dir,0750,true) && !is_dir($dir)) return false;
    return !is_link($dir) && is_writable($dir);
}
ini_set('session.use_strict_mode','1');
session_name('FUTUREOSTUDIO');
$cookiePath = rtrim(str_replace('\\','/',dirname($_SERVER['SCRIPT_NAME'] ?? '/recordings.php')),'/') . '/';
session_set_cookie_params(['lifetime'=>0,'path'=>$cookiePath,'secure'=>!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off','httponly'=>true,'samesite'=>'Lax']);
session_start();
if (empty($_SESSION['admin'])) { session_write_close(); fail('Inicia sesión nuevamente.',401); }
$method = $_SERVER['REQUEST_METHOD'] ?? 'GET';
$csrf = $_SESSION['csrf'] ?? '';
session_write_close();
if (!in_array($method,['GET','HEAD','POST'],true)) fail('Método no permitido.',405);
if ($method === 'POST') {
    if (empty($_POST) && empty($_FILES) && (int)($_SERVER['CONTENT_LENGTH'] ?? 0)>0) fail('La grabación supera el límite de carga del hosting.',413);
    $token = $_POST['csrf'] ?? '';
    if (!is_string($token) || !is_string($csrf) || $csrf === '' || !hash_equals($csrf,$token)) fail('Solicitud no válida. Recarga el proyecto.',403);
}
$name = $method === 'POST' ? ($_POST['project'] ?? '') : ($_GET['project'] ?? '');
if (!is_string($name) || strlen($name)>160 || !preg_match('/\A[A-Za-z0-9_-]+\.fprj\z/i',$name)) fail('Proyecto inválido.',400);
$root = __DIR__.'/proyectos';
$path = projectPath($root,$name);
if ($path === null) fail('Proyecto no encontrado.',404);
$folder = projectFolder($root,$name);
$dir = $folder.'/assets';
if (is_link($folder) || is_link($dir)) fail('Carpeta de audio no válida.',500);
$action = $method === 'POST' ? ($_POST['action'] ?? '') : ($_GET['action'] ?? 'list');
define('FUTUREO_RECORDINGS',true);
require_once __DIR__.'/stream.php';
require_once __DIR__.'/track-fx.php';
require_once __DIR__.'/import-mp3.php';
require_once __DIR__.'/clip-history.php';
if ($method === 'POST' && in_array($action,['undo_clip','redo_clip'],true)) handleClipHistory($action,$path,$folder,$dir);
if ($method === 'POST' && in_array($action,['mp3_chunk','mp3_finish','mp3_cancel'],true)) handleMp3($action,$path,$folder,$dir);
if ($method === 'POST' && $action === 'save_track_fx') saveTrackFx($path,$folder,$dir);
if ($method === 'POST' && $action === 'save_fx_preset') saveFxPreset($root);
if ($method === 'GET' && $action === 'fx_presets') reply(['ok'=>true,'presets'=>presetLibrary($root)]);
if ($method === 'POST' && in_array($action,['stream_start','stream_chunk','stream_finish'],true)) handleStream($action,$path,$folder,$dir);
// Non-destructive edits: each segment references the same immutable source audio.
if ($method === 'POST' && in_array($action,['split_clip','delete_clip'],true)) {
    $id=$_POST['recording_id']??'';
    if (!is_string($id)||!preg_match('/\A[a-f0-9]{24}\z/',$id)) fail('Clip inválido.');
    if (!ensureDir($folder)||!ensureDir($dir)||is_link($dir.'/.lock')) fail('No se puede escribir en el proyecto.',500);
    $lock=@fopen($dir.'/.lock','c+b');
    if (!$lock||!flock($lock,LOCK_EX)) fail('No se pudo bloquear el proyecto.',500);
    $data=readProject($path); $items=savedRecordings($data); $before=$data['content']['recordings']??[];
    $offsets=[1=>0,2=>0,3=>0,4=>0]; $target=null; $normalized=[];
    foreach($items as $item){
        $t=(int)($item['track']??1); if($t<1||$t>4)$t=1;
        $item['track']=$t; $info=waveInfo($item,$dir);
        if(!isset($item['start_ms'])||!is_numeric($item['start_ms'])||(float)$item['start_ms']<0){
            $item['start_ms']=$offsets[$t]; $offsets[$t]+=max(0,(int)($info['duration_ms']??0));
        }else $item['start_ms']=(int)$item['start_ms'];
        $normalized[$item['id']]=$item;
        if($item['id']===$id)$target=$item;
    }
    // Deletion is idempotent; a lost response can safely be retried.
    if($target===null){if($action==='delete_clip')reply(['ok'=>true,'deleted'=>$id,'history'=>historyInfo($data)]);fail('Clip no encontrado.',404);}
    $segments=[];
    if($action==='split_clip'){
        $media=$dir.'/'.$target['file'];
        if(!is_file($media)||is_link($media))fail('Audio no encontrado.',404);
        $info=waveInfo($target,$dir); $len=(int)($info['duration_ms']??0);
        $cut=filter_var($_POST['cut_ms']??null,FILTER_VALIDATE_INT);
        $rightId=$_POST['right_id']??'';
        if(!is_string($rightId)||!preg_match('/\A[a-f0-9]{24}\z/',$rightId)||isset($normalized[$rightId]))fail('Identificador de corte inválido.',409);
        if($cut===false||$cut<1||$cut>=$len)fail('El corte debe estar dentro del clip.',422);
        if(count($items)>=500)fail('El proyecto alcanzó el límite de 500 clips.',409);
        $source=max(0,(int)($target['source_offset_ms']??0));
        $left=$target; $left['source_offset_ms']=$source; $left['clip_duration_ms']=$cut; $left['duration_ms']=$cut; $left['status']='saved';
        $right=$target; $right['id']=$rightId; $right['source_offset_ms']=$source+$cut; $right['clip_duration_ms']=$len-$cut; $right['duration_ms']=$len-$cut; $right['start_ms']=$target['start_ms']+$cut; $right['status']='saved';
        $segments=[$left,$right];
    }
    $out=[];
    foreach($data['content']['recordings']??[] as $original){
        $key=is_array($original)?($original['id']??null):null;
        if($key===$id){foreach($segments as $segment)$out[]=$segment;continue;}
        $out[]=is_string($key)&&isset($normalized[$key])?$normalized[$key]:$original;
    }
    $data['content']['recordings']=$out; historyPush($data,$before,$action==='split_clip'?'Dividir clip':'Borrar clip'); storeProject($path,$data);
    flock($lock,LOCK_UN); fclose($lock);
    if($action==='delete_clip')reply(['ok'=>true,'deleted'=>$id,'history'=>historyInfo($data)]);
    reply(['ok'=>true,'recordings'=>array_map(static function($r)use($dir){return waveInfo($r,$dir);},$segments),'history'=>historyInfo($data)]);
}
// Move only clip metadata. Audio bytes are never rewritten or moved.
if ($method === 'POST' && $action === 'move_clip') {
    $id = $_POST['recording_id'] ?? '';
    $track = filter_var($_POST['track'] ?? null,FILTER_VALIDATE_INT);
    $start = filter_var($_POST['start_ms'] ?? null,FILTER_VALIDATE_INT);
    if (!is_string($id) || !preg_match('/\A[a-f0-9]{24}\z/',$id) || $track===false || $track<1 || $track>4 || $start===false || $start<0 || $start>600000) fail('Posición o pista inválida.');
    if (!ensureDir($folder) || !ensureDir($dir) || is_link($dir.'/.lock')) fail('No se puede escribir en el proyecto.',500);
    $lock=@fopen($dir.'/.lock','c+b');
    if (!$lock || !flock($lock,LOCK_EX)) fail('No se pudo bloquear el proyecto.',500);
    $data=readProject($path);
    $items=savedRecordings($data);
    $before=$data['content']['recordings']??[];
    $target=null;
    foreach($items as $i=>$item) if($item['id']===$id){$target=$i;break;}
    if ($target===null) fail('Grabación no encontrada.',404);
    $media=$dir.'/'.$items[$target]['file'];
    if (!is_file($media) || is_link($media)) fail('Audio no encontrado.',404);
    // Preserve the displayed positions of earlier, pre-multitrack recordings.
    $offsets=[1=>0,2=>0,3=>0,4=>0];
    foreach($items as $i=>$item){
        $t=(int)($item['track']??1); if($t<1||$t>4)$t=1;
        $item['track']=$t;
        if(!isset($item['start_ms'])||!is_numeric($item['start_ms'])||(float)$item['start_ms']<0){
            $item['start_ms']=$offsets[$t];
            $info=waveInfo($item,$dir); $offsets[$t]+=max(0,(int)($info['duration_ms']??0));
        } else $item['start_ms']=(int)$item['start_ms'];
        $items[$i]=$item;
    }
    $items[$target]['track']=(int)$track;
    $items[$target]['start_ms']=(int)$start;
    // Keep unrelated or future-format recording entries intact.
    foreach($data['content']['recordings'] as $k=>$original){
        if(!is_array($original))continue;
        foreach($items as $normalized){
            if(($original['id']??null)===$normalized['id']){
                $data['content']['recordings'][$k]['track']=$normalized['track'];
                $data['content']['recordings'][$k]['start_ms']=$normalized['start_ms'];
                break;
            }
        }
    }
    historyPush($data,$before,'Mover clip');
    storeProject($path,$data);
    $item=waveInfo($items[$target],$dir);
    flock($lock,LOCK_UN);fclose($lock);
    reply(['ok'=>true,'recording'=>$item,'history'=>historyInfo($data)]);
}
if ($method === 'POST' && $action === 'save') {
    $file = $_FILES['audio'] ?? null;
    if (!is_array($file) || !isset($file['error'],$file['tmp_name'],$file['size']) || is_array($file['error']) || is_array($file['tmp_name']) || is_array($file['size'])) fail('No se recibió el audio.');
    if ($file['error'] !== UPLOAD_ERR_OK) fail(in_array($file['error'],[UPLOAD_ERR_INI_SIZE,UPLOAD_ERR_FORM_SIZE],true)?'El audio supera el límite de carga del hosting.':'No se pudo recibir el audio.',413);
    $tmp = $file['tmp_name']; $size = (int)$file['size'];
    if (!is_string($tmp) || !is_uploaded_file($tmp) || $size < 1 || $size > maxUpload()) fail('Tamaño de audio no permitido.',413);
    $format = detectAudio($tmp);
    if ($format === null) fail('Formato no admitido. Usa WebM, Ogg o M4A.',415);
    if (!ensureDir($folder) || !ensureDir($dir)) fail('El hosting no permite escribir en assets del proyecto.',500);
    $lockPath = $dir.'/.lock';
    if (is_link($lockPath)) fail('Bloqueo no válido.',500);
    $lock = @fopen($lockPath,'c+b');
    if (!$lock || !flock($lock,LOCK_EX)) fail('No se pudo bloquear el proyecto.',500);
    $data = readProject($path);
    if (!isset($data['content']) || !is_array($data['content'])) $data['content'] = [];
    $items = savedRecordings($data);
    $before=$data['content']['recordings']??[];
    $id = $_POST['recording_id'] ?? '';
    if (!is_string($id) || !preg_match('/\A[a-f0-9]{24}\z/',$id)) fail('Identificador de grabación inválido.');
    foreach ($items as $existing) {
        if ($existing['id'] === $id && is_file($dir.'/'.$existing['file']) && !is_link($dir.'/'.$existing['file'])) {
            flock($lock,LOCK_UN); fclose($lock); reply(['ok'=>true,'recording'=>$existing,'history'=>historyInfo($data)]);
        }
    }
    if (count($items) >= 500) fail('El proyecto alcanzó el límite de 500 grabaciones.',409);
    $filename = 'voz_'.date('Ymd_His').'_'.$id.'.'.$format[0];
    $target = $dir.'/'.$filename;
    if (!move_uploaded_file($tmp,$target)) fail('No se pudo guardar el audio en el hosting.',500);
    @chmod($target,0640);
    $duration = filter_var($_POST['duration_ms'] ?? 0,FILTER_VALIDATE_INT);
    $track = filter_var($_POST['track'] ?? 1, FILTER_VALIDATE_INT);
    $start = filter_var($_POST['start_ms'] ?? 0, FILTER_VALIDATE_INT);
    $item = ['id'=>$id,'file'=>$filename,'path'=>'assets/'.$filename,'mime'=>$format[1],'size'=>$size,'created_at'=>date(DATE_ATOM),'duration_ms'=>max(0,min(600000,(int)$duration)),'track'=>($track !== false && $track >= 1 && $track <= 4 ? (int)$track : 1),'start_ms'=>max(0,min(600000,(int)$start))];
    $items[] = $item;
    $data['content']['recordings'] = $items;
    historyPush($data,$before,'Añadir grabación');
    $data['updated_at'] = date(DATE_ATOM);
    $json = json_encode($data,JSON_PRETTY_PRINT|JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);
    $draft = @tempnam(dirname($path),'.fprj-');
    $ok = $draft !== false && $json !== false && @file_put_contents($draft,$json."\n") === strlen($json)+1 && @chmod($draft,0644) && @rename($draft,$path);
    if (!$ok) {
        if ($draft !== false) @unlink($draft);
        @unlink($target); flock($lock,LOCK_UN); fclose($lock);
        fail('No se pudo actualizar el archivo FPRJ. La grabación sigue disponible para reintentar.',500);
    }
    flock($lock,LOCK_UN); fclose($lock);
    reply(['ok'=>true,'recording'=>$item,'history'=>historyInfo($data)],201);
}
if ($method === 'POST') fail('Acción no permitida.',405);
$projectData=readProject($path);
$items = savedRecordings($projectData);
if ($action === 'list' && $method === 'GET') {
    $items = array_values(array_filter($items,static function($r) use ($dir){return is_file($dir.'/'.$r['file']) && !is_link($dir.'/'.$r['file']);}));
    reply(['ok'=>true,'recordings'=>array_map(static function($r) use ($dir){return waveInfo($r,$dir);},$items),'max_bytes'=>maxUpload(),'max_mp3_bytes'=>FUTUREO_MP3_MAX,'track_fx'=>savedFx($projectData),'tempo_bpm'=>savedTempo($projectData),'history'=>historyInfo($projectData)]);
}
if (!in_array($action,['play','waveform'],true)) fail('Acción no permitida.',405);
$id = $_GET['id'] ?? '';
$item = null;
foreach ($items as $r) if ($r['id'] === $id) { $item=$r; break; }
if ($item === null) fail('Grabación no encontrada.',404);
$media = $dir.'/'.$item['file'];
if (!is_file($media) || is_link($media)) fail('Audio no encontrado.',404);
if ($action==='waveform') {
    if ($method!=='GET') reply(['ok'=>true,'peaks'=>[]]);
    if ($item['mime']==='audio/mpeg') reply(['ok'=>true,'peaks'=>mp3ClipPeaks($item)]);
    if ($item['mime']!=='audio/wav') reply(['ok'=>true,'peaks'=>[]]);
    $bytes=waveSize($media); $offset=0;
    if(isset($item['clip_duration_ms'])){
        $rate=(int)($item['sample_rate']??0);
        if($rate<8000||$rate>192000)reply(['ok'=>true,'peaks'=>[]]);
        $offset=min($bytes,(int)round(max(0,(int)($item['source_offset_ms']??0))*$rate/1000)*2);
        $bytes=min($bytes-$offset,(int)round(max(0,(int)$item['clip_duration_ms'])*$rate/1000)*2);
    }
    reply(['ok'=>true,'peaks'=>waveformPeaks($media,$bytes,$offset)]);
}
clearstatcache(true,$media);
$length = filesize($media);
if ($length === false || $length === 0 || ($item['mime']==='audio/wav' && $length<=44)) fail('El archivo de audio no contiene muestras guardadas.',404);
// Binary audio must not be compressed or prefixed with PHP output.
@ini_set('zlib.output_compression','0');
while(ob_get_level()>0){if(!@ob_end_clean())break;}
header_remove('Content-Encoding');
$start = 0; $end = $length-1;
$range = $_SERVER['HTTP_RANGE'] ?? '';
if ($range !== '') {
    if (!preg_match('/\Abytes=(\d*)-(\d*)\z/',$range,$m) || ($m[1] === '' && $m[2] === '')) { header('Content-Range: bytes */'.$length); http_response_code(416); exit; }
    if ($m[1] === '') { $n=(int)$m[2]; if ($n<1) { header('Content-Range: bytes */'.$length); http_response_code(416); exit; } $start=max(0,$length-$n); }
    else { $start=(int)$m[1]; if ($m[2] !== '') $end=min($end,(int)$m[2]); }
    if ($start>$end || $start>=$length) { header('Content-Range: bytes */'.$length); http_response_code(416); exit; }
    http_response_code(206); header('Content-Range: bytes '.$start.'-'.$end.'/'.$length);
}
header('Content-Type: '.$item['mime']);
header('Cache-Control: private, no-store, no-transform');
header('Accept-Ranges: bytes');
header('Content-Disposition: inline; filename="'.$item['file'].'"');
header('Content-Length: '.($end-$start+1));
if ($method === 'HEAD') exit;
$fp = fopen($media,'rb'); if (!$fp) exit;
fseek($fp,$start); $remaining=$end-$start+1;
while ($remaining>0 && !feof($fp) && !connection_aborted()) { $chunk=fread($fp,min(65536,$remaining)); if ($chunk===false || $chunk==='') break; echo $chunk; $remaining-=strlen($chunk); }
fclose($fp);
