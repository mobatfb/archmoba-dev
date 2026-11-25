<?php
declare(strict_types=1);
if(!defined('SW_APP')){http_response_code(404);exit;}
// Common private disk cache for both public and authorized administrative requests.
const SW_PHOTO_SIZES=['thumb'=>480,'medium'=>1000,'original'=>0];
const SW_PHOTO_CACHE_REV='1';
function photo_version(string $filename): string {return substr(hash('sha256',SW_PHOTO_CACHE_REV.'|'.$filename),0,24);}
function photo_size(mixed $size): string {return is_string($size)&&isset(SW_PHOTO_SIZES[$size])?$size:'original';}
function photo_mime(string $ext): string {return ['jpg'=>'image/jpeg','png'=>'image/png','webp'=>'image/webp'][$ext]??'';}
function photo_ext(string $mime): string {return ['image/jpeg'=>'jpg','image/png'=>'png','image/webp'=>'webp'][$mime]??'';}
function photo_cache_root(): ?string {
    $dir=dirname(__DIR__).'/storage/photo-cache';
    if(!is_dir($dir)&&!@mkdir($dir,0700,true)&&!is_dir($dir))return null;
    return is_writable($dir)?$dir:null;
}
function photo_cache_key(string $id,array $meta,string $size): string {return hash('sha256',SW_PHOTO_CACHE_REV.'|'.$id.'|'.$meta['filename'].'|'.$meta['mime'].'|'.$size);}
function photo_cached(string $dir,string $key): ?array {
    foreach(['webp','jpg','png'] as $ext){$p=$dir.'/'.$key.'.'.$ext;if(is_file($p)&&($n=@filesize($p))>0&&$n<=5242880)return ['path'=>$p,'mime'=>photo_mime($ext),'length'=>$n];}
    return null;
}
function photo_cache_put(?string $dir,string $key,string $bytes,string $mime): array {
    $result=['bytes'=>$bytes,'mime'=>$mime,'length'=>strlen($bytes)];$ext=photo_ext($mime);
    if($dir===null||$ext===''||$bytes===''||strlen($bytes)>5242880)return $result;
    $tmp=@tempnam($dir,'tmp-');if($tmp===false)return $result;
    try{if(@chmod($tmp,0600)&&@file_put_contents($tmp,$bytes)===strlen($bytes)&&@rename($tmp,$dir.'/'.$key.'.'.$ext))return ['path'=>$dir.'/'.$key.'.'.$ext,'mime'=>$mime,'length'=>strlen($bytes)];}finally{if(is_file($tmp))@unlink($tmp);}
    return $result;
}
function photo_read(array $p): ?array {
    $bytes=$p['content'];$mime=$p['mime'];
    if($bytes===null&&preg_match('/^[a-f0-9]{24,64}\.(jpg|jpeg|png|webp)$/D',$p['filename'])){
        $path=dirname(__DIR__).'/storage/uploads/'.$p['filename'];if(is_file($path)&&filesize($path)<=5242880){$bytes=file_get_contents($path);$mime=(new finfo(FILEINFO_MIME_TYPE))->file($path);}
    }
    return is_string($bytes)&&strlen($bytes)>0&&strlen($bytes)<=5242880&&photo_ext((string)$mime)!==''?['bytes'=>$bytes,'mime'=>$mime,'length'=>strlen($bytes)]:null;
}
function photo_memory_limit(): int {
    $s=trim((string)ini_get('memory_limit'));if($s==='-1')return PHP_INT_MAX;
    $n=(int)$s;return $n*match(strtolower(substr($s,-1))){'g'=>1073741824,'m'=>1048576,'k'=>1024,default=>1};
}
function photo_resize(string $bytes,int $max): ?array {
    if(!function_exists('imagecreatefromstring')||!function_exists('imagewebp'))return null;
    $info=@getimagesizefromstring($bytes);if(!$info||$info[0]<1||$info[1]<1)return null;
    [$w,$h]=$info;$scale=min(1,$max/max($w,$h));$nw=max(1,(int)round($w*$scale));$nh=max(1,(int)round($h*$scale));
    // Guard against oversized/decompression-heavy uploads on small shared-hosting workers.
    if($w>8000||$h>8000||$w*$h>24000000||($w*$h*10+$nw*$nh*8+16777216)>photo_memory_limit()-memory_get_usage(true))return null;
    $src=@imagecreatefromstring($bytes);if(!$src)return null;
    $dst=null;
    try{
        // Preserve JPEG EXIF orientation where supported; use a private temporary stream.
        if(($info['mime']??'')==='image/jpeg'&&function_exists('exif_read_data')){
            $f=tmpfile();if($f!==false){try{if(fwrite($f,$bytes)===strlen($bytes)){rewind($f);$ex=@exif_read_data($f);$orientation=(int)($ex['Orientation']??1);if(in_array($orientation,[2,4,5,7],true))imageflip($src,in_array($orientation,[2,5,7],true)?IMG_FLIP_HORIZONTAL:IMG_FLIP_VERTICAL);$angle=match($orientation){3=>180,5,8=>90,6,7=>-90,default=>0};if($angle){$rot=@imagerotate($src,$angle,0);if($rot){imagedestroy($src);$src=$rot;}}}}finally{fclose($f);}}
        }
        $w=imagesx($src);$h=imagesy($src);$scale=min(1,$max/max($w,$h));$nw=max(1,(int)round($w*$scale));$nh=max(1,(int)round($h*$scale));
        $dst=imagecreatetruecolor($nw,$nh);if(!$dst)return null;
        imagealphablending($dst,false);imagesavealpha($dst,true);imagefill($dst,0,0,imagecolorallocatealpha($dst,0,0,0,127));
        if(!imagecopyresampled($dst,$src,0,0,0,0,$nw,$nh,$w,$h))return null;
        ob_start();try{$ok=@imagewebp($dst,null,$max<=480?76:83);$out=ob_get_contents();}finally{ob_end_clean();}
        if(!$ok||!is_string($out)||strlen($out)<12||substr($out,0,4)!=='RIFF'||substr($out,8,4)!=='WEBP')return null;
        // Keep an already smaller original when it fits the requested dimensions.
        if(max($info[0],$info[1])<=$max&&strlen($bytes)<=strlen($out)&&photo_ext((string)$info['mime'])!=='')return ['bytes'=>$bytes,'mime'=>$info['mime']];
        return ['bytes'=>$out,'mime'=>'image/webp'];
    }catch(Throwable $e){return null;}finally{if($dst)imagedestroy($dst);imagedestroy($src);}
}
function photo_response(array $file,bool $public,bool $versioned,bool $optimized): never {
    $etag='"'.(isset($file['path'])?hash_file('sha256',$file['path']):hash('sha256',$file['bytes'])).'"';
    header('Content-Type: '.$file['mime']);header('X-Content-Type-Options: nosniff');
    // Never cache private admin content in shared proxies. Old unversioned URLs revalidate.
    header('Cache-Control: '.($public&&$versioned&&$optimized?'private, max-age=86400, immutable':'private, no-cache'));
    header('ETag: '.$etag);header_remove('Pragma');header_remove('Expires');
    $tags=array_map('trim',explode(',',(string)($_SERVER['HTTP_IF_NONE_MATCH']??'')));
    if(in_array($etag,$tags,true)||in_array('W/'.$etag,$tags,true)||in_array('*',$tags,true)){http_response_code(304);exit;}
    header('Content-Length: '.$file['length']);if(($_SERVER['REQUEST_METHOD']??'GET')!=='HEAD'){if(isset($file['path']))readfile($file['path']);else echo $file['bytes'];}exit;
}
function photo_serve(string $id,int $slot,bool $public): never {
    if(!in_array($_SERVER['REQUEST_METHOD']??'GET',['GET','HEAD'],true)){http_response_code(405);exit;}
    // Check current authorization/status and filename BEFORE using any disk cache.
    $where=$public?" AND r.status='activo'":'';
    $meta=one('SELECT f.filename,f.mime FROM raffle_photos f JOIN raffles r ON r.id=f.raffle_id WHERE f.raffle_id=? AND f.slot=?'.$where,[$id,$slot]);
    if(!$meta){http_response_code(404);exit;}
    $version=$_GET['v']??null;$versioned=is_string($version)&&hash_equals(photo_version($meta['filename']),$version);
    if($version!==null&&!$versioned){http_response_code(404);exit;}
    $size=photo_size($_GET['size']??null);session_write_close();
    $dir=photo_cache_root();$key=photo_cache_key($id,$meta,$size);$originalKey=photo_cache_key($id,$meta,'original');
    if($dir!==null&&($hit=photo_cached($dir,$key)))photo_response($hit,$public,$versioned,true);
    // A per-original lock serializes generation across all image sizes and requests.
    $lock=$dir!==null?@fopen($dir.'/'.$originalKey.'.lock','c'):false;
    $file=null;$optimized=$size==='original';
    try{
        if($lock!==false)flock($lock,LOCK_EX);
        if($dir!==null&&($hit=photo_cached($dir,$key))){$file=$hit;$optimized=true;}
        else{
            $original=$dir!==null?photo_cached($dir,$originalKey):null;
            if(!$original){
                $row=one('SELECT f.filename,f.mime,f.content FROM raffle_photos f JOIN raffles r ON r.id=f.raffle_id WHERE f.raffle_id=? AND f.slot=? AND f.filename=?'.$where,[$id,$slot,$meta['filename']]);
                if($row&&($read=photo_read($row)))$original=photo_cache_put($dir,$originalKey,$read['bytes'],$read['mime']);
            }
            if($original){$file=$original;
                if($size!=='original'){$bytes=$original['bytes']??@file_get_contents($original['path']);$small=is_string($bytes)?photo_resize($bytes,SW_PHOTO_SIZES[$size]):null;if($small){$file=photo_cache_put($dir,$key,$small['bytes'],$small['mime']);$optimized=true;}}
            }
        }
    }finally{if($lock!==false){flock($lock,LOCK_UN);fclose($lock);}}
    if(!$file){http_response_code(404);exit;}photo_response($file,$public,$versioned,$optimized);
}
