<?php
declare(strict_types=1);
if (!defined('VE_VERSION')) { http_response_code(404); exit; }

// Store avatars outside the web root, isolated per installation and stable user ID.
function profile_directory(bool $create=false): ?string {
    $documentRoot=$_SERVER['DOCUMENT_ROOT']??'';
    if (!is_string($documentRoot) || $documentRoot==='') return null;
    $doc=realpath($documentRoot);
    $app=realpath(dirname(__DIR__));
    if (!$doc || !$app || $doc==='/' || !is_dir($doc)) return null;
    $public=$doc;
    for ($p=$doc; $p!==dirname($p); $p=dirname($p)) {
        if (in_array(strtolower(basename($p)),['public_html','httpdocs','htdocs','www','wwwroot'],true)) $public=$p;
    }
    $base=dirname($public);
    if ($base==='/' || $base===$public) return null;
    $root=$base.'/.virtualeduc_private';
    $dir=$root.'/profiles-'.hash('sha256',$app);
    if ($dir===$app || str_starts_with($dir.'/',$app.'/') || str_starts_with($dir.'/',$public.'/')) return null;
    foreach ([$root,$dir] as $path) {
        if (is_link($path)) return null;
        if ($create && !is_dir($path) && !@mkdir($path,0700) && !is_dir($path)) return null;
        if (!is_dir($path) || realpath($path)!==$path) return null;
        if ($create) @chmod($path,0700);
        clearstatcache(true,$path);
        $mode=fileperms($path);
        if ($mode===false || ($mode & 0077)!==0) return null;
    }
    return $dir;
}
function profile_path(array $u,bool $create=false): ?string {
    $id=(string)($u['id']??'');
    if (!preg_match('/\A[1-9][0-9]{0,19}\z/D',$id)) return null;
    $dir=profile_directory($create);
    return $dir===null?null:$dir.'/'.$id.'.png';
}
function profile_has_photo(array $u): bool {
    $path=profile_path($u);
    return $path!==null && !is_link($path) && is_file($path) && is_readable($path);
}
function profile_initials(array $u): string {
    $out='';
    foreach ([$u['last_names']??'',$u['first_names']??$u['name']??''] as $part) {
        if (preg_match('/\p{L}/u',(string)$part,$m)) $out.=$m[0];
    }
    return $out===''?'U':(function_exists('mb_strtoupper')?mb_strtoupper($out,'UTF-8'):strtoupper($out));
}
function profile_avatar(array $u,string $class): void {
    if (profile_has_photo($u)) { ?><img class="<?=h($class)?>" src="?profile_photo=1" alt="Foto de perfil"><?php }
    else { ?><span class="<?=h($class)?>" aria-label="Iniciales del usuario"><?=h(profile_initials($u))?></span><?php }
}
function serve_profile_photo(?array $u): never {
    require_role($u,'admin','subadmin','teacher','student');
    if (($_SERVER['REQUEST_METHOD']??'GET')!=='GET') { header('Allow: GET'); http_response_code(405); exit; }
    if (in_array($_SERVER['HTTP_SEC_FETCH_SITE']??'',['cross-site','same-site'],true)) { http_response_code(403); exit; }
    $path=profile_path($u);
    if (!$path || !profile_has_photo($u) || !($fp=@fopen($path,'rb'))) { http_response_code(404); exit; }
    $stat=fstat($fp);
    if (!$stat || $stat['size']<1 || $stat['size']>100000) { fclose($fp); http_response_code(404); exit; }
    session_write_close();
    header('Content-Type: image/png');
    header('Content-Disposition: inline; filename="perfil.png"');
    header('Cache-Control: private, no-store, max-age=0');
    header('Cross-Origin-Resource-Policy: same-origin');
    header('Content-Length: '.$stat['size']);
    fpassthru($fp); fclose($fp); exit;
}
function profile_convert(string $source,string $target): void {
    if (!extension_loaded('gd')) throw new DomainException('El hosting necesita la extensión GD de PHP para procesar fotos.');
    $info=@getimagesize($source);
    if (!$info || !in_array($info[2],[IMAGETYPE_JPEG,IMAGETYPE_PNG,IMAGETYPE_GIF,IMAGETYPE_WEBP],true)) throw new DomainException('Selecciona una imagen JPG, PNG, GIF o WebP válida.');
    if ($info[0]<1 || $info[1]<1 || $info[0]>5000 || $info[1]>5000 || $info[0]*$info[1]>12000000) throw new DomainException('La foto debe tener hasta 12 megapíxeles y máximo 5000 píxeles por lado.');
    $raw=file_get_contents($source);
    $image=$raw===false?false:@imagecreatefromstring($raw);
    unset($raw);
    if (!$image) throw new DomainException('No se pudo procesar el formato de imagen.');
    try {
        if ($info[2]===IMAGETYPE_JPEG && function_exists('exif_read_data')) {
            $exif=@exif_read_data($source); $o=(int)($exif['Orientation']??1);
            if (in_array($o,[2,5,7],true)) imageflip($image,IMG_FLIP_HORIZONTAL);
            if ($o===4) imageflip($image,IMG_FLIP_VERTICAL);
            $angle=[3=>180,5=>90,6=>270,7=>270,8=>90][$o]??0;
            if ($angle) { $rotated=imagerotate($image,$angle,0); if ($rotated) { imagedestroy($image); $image=$rotated; } }
        }
        $w=imagesx($image); $h=imagesy($image); $side=min($w,$h);
        $out=imagecreatetruecolor(120,120);
        if (!$out) throw new DomainException('No se pudo preparar la foto.');
        try {
            imagealphablending($out,false); imagesavealpha($out,true);
            imagefill($out,0,0,imagecolorallocatealpha($out,0,0,0,127));
            if (!imagecopyresampled($out,$image,0,0,(int)(($w-$side)/2),(int)(($h-$side)/2),120,120,$side,$side) || !imagepng($out,$target,7)) throw new DomainException('No se pudo generar la foto de perfil.');
        } finally { imagedestroy($out); }
    } finally { imagedestroy($image); }
}
function save_profile_photo(array $u): void {
    $op=field('photo_action',20);
    if ($op==='remove') {
        $path=profile_path($u);
        if ($path && (is_link($path) || (is_file($path) && !@unlink($path)))) throw new DomainException('No se pudo eliminar la foto.');
        return;
    }
    if ($op!=='save') throw new DomainException('Acción inválida.');
    $upload=$_FILES['photo']??null;
    if (!is_array($upload) || ($upload['error']??null)!==UPLOAD_ERR_OK || !is_string($upload['tmp_name']??null) || !is_uploaded_file($upload['tmp_name'])) throw new DomainException('Selecciona una imagen válida de hasta 5 MB.');
    $source=$upload['tmp_name']; $size=filesize($source);
    if (!$size || $size>5*1024*1024) throw new DomainException('La imagen debe pesar máximo 5 MB.');
    $path=profile_path($u,true);
    if (!$path || is_link($path) || !is_writable(dirname($path))) throw new DomainException('No se puede escribir en la carpeta privada fuera de la raíz web. Revisa los permisos del hosting.');
    $tmp=tempnam(dirname($path),'.foto-');
    if (!$tmp) throw new DomainException('No se pudo preparar la foto.');
    try {
        if (dirname($tmp)!==dirname($path) || !chmod($tmp,0600)) throw new DomainException('No se pudo asegurar la carpeta privada.');
        profile_convert($source,$tmp);
        if (!@rename($tmp,$path)) throw new DomainException('No se pudo guardar la foto.');
    } finally { if (is_file($tmp)) @unlink($tmp); }
}
