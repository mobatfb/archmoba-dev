<?php
declare(strict_types=1);
// Included only by the authenticated recordings endpoint. No standalone access.
if (!defined('FUTUREO_RECORDINGS')) { http_response_code(404); exit; }
function waveHeader(int $rate, int $bytes): string {
    return 'RIFF'.pack('V',36+$bytes).'WAVEfmt '.pack('VvvVVvv',16,1,1,$rate,$rate*2,2,16).'data'.pack('V',$bytes);
}
function storeProject(string $path, array $data): void {
    $data['updated_at'] = date(DATE_ATOM);
    $json=json_encode($data,JSON_PRETTY_PRINT|JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);
    $tmp=@tempnam(dirname($path),'.fprj-');
    if ($tmp===false || $json===false || @file_put_contents($tmp,$json."\n")!==strlen($json)+1 || !@chmod($tmp,0640) || !@rename($tmp,$path)) {
        if ($tmp!==false) @unlink($tmp);
        fail('No se pudo actualizar el proyecto.',500);
    }
}
function waveSize(string $media): int {
    clearstatcache(true,$media);
    $n=@filesize($media);
    return $n===false?0:max(0,($n-44)&~1);
}
function waveInfo(array $item,string $dir): array {
    if (($item['mime']??'')==='audio/wav' && isset($item['sample_rate'])) {
        $rate=(int)$item['sample_rate'];
        if ($rate>=8000 && $rate<=192000) {
            $bytes=waveSize($dir.'/'.$item['file']);
            $item['pcm_bytes']=$bytes;
            $item['size']=$bytes+44;
            $item['duration_ms']=(int)round($bytes/$rate/2*1000);
        }
    }
    return $item;
}
function handleStream(string $action,string $path,string $folder,string $dir): void {
    $id=$_POST['recording_id']??'';
    if (!is_string($id)||!preg_match('/\A[a-f0-9]{24}\z/',$id)) fail('Identificador inválido.');
    if (!ensureDir($folder)||!ensureDir($dir)||is_link($dir.'/.lock')) fail('No se puede escribir en assets del proyecto.',500);
    $lock=@fopen($dir.'/.lock','c+b');
    if (!$lock||!flock($lock,LOCK_EX)) fail('No se pudo bloquear el proyecto.',500);
    $data=readProject($path);
    if (!isset($data['content'])||!is_array($data['content'])) $data['content']=[];
    $items=savedRecordings($data);
    $index=null;
    foreach($items as $i=>$item) if($item['id']===$id){$index=$i;break;}
    if ($action==='stream_start' && $index===null) {
        $rate=filter_var($_POST['sample_rate']??null,FILTER_VALIDATE_INT);
        $track=filter_var($_POST['track']??1,FILTER_VALIDATE_INT);
        $start=filter_var($_POST['start_ms']??0,FILTER_VALIDATE_INT);
        if ($rate===false||$rate<8000||$rate>192000) fail('Frecuencia de audio inválida.');
        if ($track===false||$track<1||$track>4) fail('Pista inválida.');
        if ($start===false||$start<0||$start>600000) fail('Posición inicial inválida.');
        if (count($items)>=500) fail('El proyecto alcanzó el límite de grabaciones.',409);
        $filename='voz_'.date('Ymd_His').'_'.$id.'.wav';
        $media=$dir.'/'.$filename;
        $fp=@fopen($media,'xb');
        if (!$fp) fail('No se pudo crear el audio en assets.',500);
        $ok=fwrite($fp,waveHeader($rate,0))===44 && fflush($fp);
        fclose($fp);
        if (!$ok) { @unlink($media); fail('No se pudo escribir el audio.',500); }
        @chmod($media,0640);
        $item=['id'=>$id,'file'=>$filename,'path'=>'assets/'.$filename,'mime'=>'audio/wav','sample_rate'=>$rate,'channels'=>1,'bits'=>16,'size'=>44,'created_at'=>date(DATE_ATOM),'duration_ms'=>0,'status'=>'recording','track'=>(int)$track,'start_ms'=>(int)$start];
        $items[]=$item;$data['content']['recordings']=$items;$data['module']='audio';
        storeProject($path,$data);
        flock($lock,LOCK_UN);fclose($lock);reply(['ok'=>true,'recording'=>$item,'pcm_bytes'=>0],201);
    }
    if ($index===null) fail('Grabación no encontrada.',404);
    $item=$items[$index];
    $rate=(int)($item['sample_rate']??0);
    if ($item['mime']!=='audio/wav'||$rate<8000||$rate>192000) fail('Grabación no compatible.',409);
    $media=$dir.'/'.$item['file'];
    if (is_link($media)||!is_file($media)) fail('Archivo de audio no encontrado.',404);
    $bytes=waveSize($media);
    if ($action==='stream_start') {
        if ((string)$rate!==(string)($_POST['sample_rate']??'')) fail('Frecuencia incompatible.',409);
    } elseif ($action==='stream_chunk') {
        $off=filter_var($_POST['offset']??null,FILTER_VALIDATE_INT);
        $upload=$_FILES['pcm']??null;
        if ($off===false||$off<0||$off%2||!is_array($upload)||($upload['error']??null)!==UPLOAD_ERR_OK||!is_string($upload['tmp_name']??null)||!is_uploaded_file($upload['tmp_name'])) fail('Fragmento inválido.');
        $chunk=@file_get_contents($upload['tmp_name']);
        if (!is_string($chunk)||strlen($chunk)<2||strlen($chunk)%2||strlen($chunk)>min(1048576,maxUpload())) fail('Tamaño de fragmento no permitido.',413);
        $len=strlen($chunk);
        if ($off+$len>$rate*2*600) fail('Límite de 10 minutos por toma.',413);
        $fp=@fopen($media,'r+b');
        if (!$fp) fail('No se pudo abrir el audio.',500);
        if ($off<$bytes) {
            // An HTTP response may have been lost. Verify exact bytes, do not duplicate.
            if ($off+$len>$bytes||fseek($fp,44+$off)!==0||fread($fp,$len)!==$chunk) { fclose($fp); fail('El fragmento no coincide con el audio guardado.',409); }
        } else {
            if ($off!==$bytes||($item['status']??'')==='saved') { fclose($fp); fail('Secuencia de grabación no válida.',409); }
            if (fseek($fp,44+$bytes)!==0||fwrite($fp,$chunk)!==$len) {
                @ftruncate($fp,44+$bytes); fclose($fp); fail('No se pudo escribir el fragmento.',500);
            }
            $bytes+=$len;
        }
        // A valid WAV header is kept on disk throughout the recording.
        if (fseek($fp,0)!==0||fwrite($fp,waveHeader($rate,$bytes))!==44||!fflush($fp)) { fclose($fp);fail('No se pudo actualizar la cabecera WAV.',500); }
        if (function_exists('fsync')) @fsync($fp);
        fclose($fp);
        // Update FPRJ periodically (and on stop), while actual WAV bytes are committed every chunk.
        if ($bytes-(int)($item['pcm_bytes']??0)>=$rate*2*5) {
            $item=waveInfo($item,$dir);$items[$index]=$item;$data['content']['recordings']=$items;storeProject($path,$data);
        }
    } elseif ($action==='stream_finish') {
        $off=filter_var($_POST['offset']??null,FILTER_VALIDATE_INT);
        if ($off===false||$off!==$bytes) fail('Quedan fragmentos pendientes de guardar.',409);
        $fp=@fopen($media,'r+b');
        if (!$fp||fwrite($fp,waveHeader($rate,$bytes))!==44||!fflush($fp)) fail('No se pudo finalizar el audio.',500);
        if (function_exists('fsync')) @fsync($fp);
        fclose($fp);
        $item=waveInfo($item,$dir);$item['status']='saved';$items[$index]=$item;$data['content']['recordings']=$items;storeProject($path,$data);
    } else fail('Acción no permitida.',405);
    $item=waveInfo($item,$dir);
    flock($lock,LOCK_UN);fclose($lock);
    reply(['ok'=>true,'recording'=>$item,'pcm_bytes'=>$bytes]);
}
function waveformPeaks(string $media,int $bytes): array {
    $fp=@fopen($media,'rb');if(!$fp||$bytes<2) {if($fp)fclose($fp);return [];}
    $samples=intdiv($bytes,2);$bins=min(720,max(1,(int)ceil($samples/1200)));$out=[];
    // Bounded representative samples per bin; live waveform uses every recorded sample.
    for($i=0;$i<$bins;$i++){
        $a=(int)floor($i*$samples/$bins);$b=(int)floor(($i+1)*$samples/$bins);
        $peak=0;$window=min(192,max(1,$b-$a));
        for($j=0;$j<3;$j++){
            $pos=$a+(int)floor(max(0,$b-$a-$window)*$j/2);
            if(fseek($fp,44+$pos*2)!==0)continue;
            $buf=fread($fp,$window*2);if(!is_string($buf)||strlen($buf)<2)continue;
            foreach(unpack('v*',substr($buf,0,strlen($buf)&~1))?:[] as $v){$v=$v>=32768?$v-65536:$v;$peak=max($peak,abs($v));}
        }
        $out[]=round($peak/32768,3);
    }
    fclose($fp);return $out;
}
