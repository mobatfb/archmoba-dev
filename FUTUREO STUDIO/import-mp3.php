<?php
declare(strict_types=1);
// FUTUREO STUDIO v0.1.20 - authenticated, chunked MP3 import.
if (!defined('FUTUREO_RECORDINGS')) { http_response_code(404); exit; }
const FUTUREO_MP3_MAX = 25 * 1048576;
// Check two consecutive MPEG Layer III frames, not merely the file extension or ID3 tag.
function mp3Frame(string $h): ?array {
    if(strlen($h)<4)return null;
    $a=ord($h[0]);$b=ord($h[1]);$c=ord($h[2]);$d=ord($h[3]);
    if($a!==255||($b&224)!==224||(($b>>1)&3)!==1||($d&3)===2)return null;
    $version=($b>>3)&3;$br=$c>>4;$sr=($c>>2)&3;
    if($version===1||$br===0||$br===15||$sr===3)return null;
    $rates=[44100,48000,32000];$rate=intdiv($rates[$sr],$version===3?1:($version===2?2:4));
    $bitrates=$version===3?[0,32,40,48,56,64,80,96,112,128,160,192,224,256,320]:[0,8,16,24,32,40,48,56,64,80,96,112,128,144,160];
    $length=intdiv(($version===3?144000:72000)*$bitrates[$br],$rate)+(($c>>1)&1);
    return $length>=4?[$length,$rate,$version]:null;
}
function validMp3(string $file,int $size): bool {
    $fp=@fopen($file,'rb');if(!$fp)return false;
    $head=fread($fp,10);$offset=0;
    if(is_string($head)&&strlen($head)===10&&substr($head,0,3)==='ID3'){
        for($i=6;$i<10;$i++)if(ord($head[$i])&128){fclose($fp);return false;}
        $offset=10;for($i=6;$i<10;$i++)$offset+=(ord($head[$i])&127)<<(7*(9-$i));
        if(ord($head[3])===4&&(ord($head[5])&16))$offset+=10;
    }
    if($offset+8>$size||fseek($fp,$offset)!==0){fclose($fp);return false;}
    $data=fread($fp,min($size-$offset,65536));fclose($fp);
    if(!is_string($data))return false;
    $n=strlen($data);
    for($i=0;$i+4<=$n;$i++){
        if($data[$i]!=="\xff")continue;
        $a=mp3Frame(substr($data,$i,4));if($a===null||$i+$a[0]+4>$n)continue;
        $b=mp3Frame(substr($data,$i+$a[0],4));
        if($b!==null&&$a[1]===$b[1]&&$a[2]===$b[2]&&$offset+$i+$a[0]+$b[0]<=$size)return true;
    }
    return false;
}
function mp3ClipPeaks(array $item): array {
    $peaks=$item['source_peaks']??[];
    if(!is_array($peaks)||!count($peaks))return [];
    $n=count($peaks);$full=max(1,(int)($item['source_duration_ms']??$item['duration_ms']??1));
    $start=max(0,(int)($item['source_offset_ms']??0));
    $len=max(0,(int)($item['clip_duration_ms']??$item['duration_ms']??0));
    if(!$len||$start>=$full)return [];
    $a=min($n-1,(int)floor($start/$full*$n));$b=min($n,max($a+1,(int)ceil(($start+$len)/$full*$n)));
    return array_values(array_slice($peaks,$a,$b-$a));
}
function handleMp3(string $action,string $path,string $folder,string $dir): void {
    $id=$_POST['recording_id']??'';
    if(!is_string($id)||!preg_match('/\A[a-f0-9]{24}\z/',$id))fail('Identificador MP3 inválido.');
    if(!ensureDir($folder)||!ensureDir($dir)||is_link($dir.'/.lock'))fail('No se puede escribir en assets del proyecto.',500);
    $lock=@fopen($dir.'/.lock','c+b');if(!$lock||!flock($lock,LOCK_EX))fail('No se pudo bloquear el proyecto.',500);
    $data=readProject($path);$items=savedRecordings($data);
    $part=$dir.'/.mp3_'.$id.'.part';
    if(is_link($part))fail('Archivo temporal no válido.',500);
    foreach($items as $item){if($item['id']!==$id)continue;
        if($action==='mp3_cancel')reply(['ok'=>true,'cancelled'=>false]);
        if($action==='mp3_finish'&&$item['mime']==='audio/mpeg'&&is_file($dir.'/'.$item['file'])&&!is_link($dir.'/'.$item['file']))reply(['ok'=>true,'recording'=>$item]);
        fail('Identificador ya utilizado.',409);
    }
    if($action==='mp3_cancel'){if(is_file($part)&&!@unlink($part))fail('No se pudo quitar el temporal.',500);reply(['ok'=>true,'cancelled'=>true]);}
    $total=filter_var($_POST['total_bytes']??null,FILTER_VALIDATE_INT);
    if($total===false||$total<1||$total>FUTUREO_MP3_MAX)fail('El MP3 supera el límite de 25 MB o está vacío.',413);
    if(count($items)>=500)fail('El proyecto alcanzó el límite de 500 clips.',409);
    clearstatcache(true,$part);$received=is_file($part)?filesize($part):0;
    if($received===false||$received>$total)fail('Temporal MP3 incompatible.',409);
    if($action==='mp3_chunk'){
        $offset=filter_var($_POST['offset']??null,FILTER_VALIDATE_INT);$f=$_FILES['pcm']??null;
        if($offset===false||$offset<0||!is_array($f)||($f['error']??null)!==UPLOAD_ERR_OK||!is_string($f['tmp_name']??null)||!is_uploaded_file($f['tmp_name']))fail('Fragmento MP3 inválido.');
        $len=filesize($f['tmp_name']);if($len===false||$len<1||$len>min(1048576,maxUpload())||$offset+$len>$total)fail('Tamaño de fragmento MP3 inválido.',413);
        if($offset>$received)fail('Falta un fragmento anterior.',409);
        if($offset===0&&!is_file($part)){
            // Remove only abandoned upload temporaries, never saved audio assets.
            foreach(glob($dir.'/.mp3_*.part')?:[] as $old)if(!is_link($old)&&is_file($old)&&preg_match('/\A\.mp3_[a-f0-9]{24}\.part\z/',basename($old))&&filemtime($old)<time()-86400)@unlink($old);
            $fp=@fopen($part,'xb');
        }else $fp=@fopen($part,'r+b');
        if(!$fp)fail('No se pudo abrir el temporal MP3.',500);
        @chmod($part,0640);$chunk=file_get_contents($f['tmp_name']);
        if(!is_string($chunk)||strlen($chunk)!==$len){fclose($fp);fail('No se pudo leer el fragmento.',500);}
        if($offset<$received){
            if($offset+$len>$received||fseek($fp,$offset)!==0||fread($fp,$len)!==$chunk){fclose($fp);fail('El fragmento no coincide con el temporal.',409);}
        }else{
            if(fseek($fp,$offset)!==0||fwrite($fp,$chunk)!==$len||!fflush($fp)){@ftruncate($fp,$received);fclose($fp);fail('No se pudo guardar el fragmento MP3.',500);}
            $received+=$len;
        }
        if(function_exists('fsync'))@fsync($fp);fclose($fp);
        reply(['ok'=>true,'received'=>$received]);
    }
    if($action!=='mp3_finish')fail('Acción MP3 no permitida.',405);
    if($received!==$total||!is_file($part))fail('La carga MP3 está incompleta.',409);
    $track=filter_var($_POST['track']??null,FILTER_VALIDATE_INT);
    $start=filter_var($_POST['start_ms']??null,FILTER_VALIDATE_INT);
    $duration=filter_var($_POST['duration_ms']??null,FILTER_VALIDATE_INT);
    if($track===false||$track<1||$track>4||$start===false||$start<0||$start>600000||$duration===false||$duration<1||$duration>600000)fail('Pista, posición o duración inválida.');
    if(!validMp3($part,$total))fail('El archivo no contiene audio MP3 válido.',415);
    $raw=$_POST['peaks']??'';
    if(!is_string($raw)||strlen($raw)>16000)fail('Forma de onda inválida.');
    $peaks=json_decode($raw,true);
    if(!is_array($peaks)||count($peaks)<1||count($peaks)>720)fail('Forma de onda inválida.');
    $clean=[];foreach($peaks as $v){if(!is_int($v)&&!is_float($v))fail('Forma de onda inválida.');if(!is_finite((float)$v)||$v<0||$v>1)fail('Forma de onda inválida.');$clean[]=round((float)$v,3);}
    $original=$_POST['original_name']??'Audio.mp3';
    if(!is_string($original)||!preg_match('//u',$original))$original='Audio.mp3';
    $original=basename(str_replace('\\','/',$original));$original=preg_replace('/[\x00-\x1f\x7f]/u','',$original)??'';
    if($original===''||strlen($original)>240)$original='Audio.mp3';
    $filename='audio_'.date('Ymd_His').'_'.$id.'.mp3';$target=$dir.'/'.$filename;
    if(file_exists($target)||is_link($target)||!@rename($part,$target))fail('No se pudo guardar el MP3 en assets.',500);
    $item=['id'=>$id,'file'=>$filename,'path'=>'assets/'.$filename,'original_name'=>$original,'mime'=>'audio/mpeg','size'=>$total,'created_at'=>date(DATE_ATOM),'duration_ms'=>$duration,'source_duration_ms'=>$duration,'source_peaks'=>$clean,'track'=>$track,'start_ms'=>$start,'status'=>'saved'];
    if(!isset($data['content'])||!is_array($data['content']))$data['content']=[];
    if(!isset($data['content']['recordings'])||!is_array($data['content']['recordings']))$data['content']['recordings']=[];
    $data['content']['recordings'][]=$item;$data['module']='audio';$data['updated_at']=date(DATE_ATOM);
    $json=json_encode($data,JSON_PRETTY_PRINT|JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);$draft=@tempnam(dirname($path),'.fprj-');
    if($draft===false||$json===false||@file_put_contents($draft,$json."\n")!==strlen($json)+1||!@chmod($draft,0640)||!@rename($draft,$path)){
        if($draft!==false)@unlink($draft);@rename($target,$part);fail('No se pudo actualizar el FPRJ.',500);
    }
    flock($lock,LOCK_UN);fclose($lock);reply(['ok'=>true,'recording'=>$item],201);
}
