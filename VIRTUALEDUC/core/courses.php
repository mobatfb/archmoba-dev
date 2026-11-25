<?php
declare(strict_types=1);
if (!defined('VE_VERSION')) { http_response_code(404); exit; }

function course_modalities(): array { return ['online'=>'En línea','presential'=>'Presencial','hybrid'=>'Híbrida']; }
function course_levels(): array { return ['basic'=>'Básico','intermediate'=>'Intermedio','advanced'=>'Avanzado']; }
function course_metadata(array $r): array {
    $modality=creation_value($r,'modalidad',30);
    $level=creation_value($r,'nivel',30);
    foreach(course_modalities() as $key=>$label) if($modality===$label) $modality=$key;
    foreach(course_levels() as $key=>$label) if($level===$label) $level=$key;
    if(!isset(course_modalities()[$modality])) throw new DomainException('Selecciona una modalidad válida.');
    if(!isset(course_levels()[$level])) throw new DomainException('Selecciona un nivel válido.');
    $hours=str_replace(',','.',creation_value($r,'duracion',8));
    if(!preg_match('/\A[0-9]{1,5}(?:\.[0-9]{1,2})?\z/D',$hours) || (float)$hours<=0 || (float)$hours>10000) throw new DomainException('La duración debe ser mayor a 0 y hasta 10000 horas, con máximo dos decimales.');
    return [$modality,$hours,$level,creation_value($r,'periodo',50)];
}
function course_metadata_labels(array $c): array {
    $hours=$c['duration_hours']??null;
    return [
        'Modalidad'=>course_modalities()[$c['modality']??'']??'Sin definir',
        'Duración'=>$hours!==null?rtrim(rtrim(number_format((float)$hours,2,',',''),'0'),',').' h':'Sin definir',
        'Nivel'=>course_levels()[$c['level']??'']??'Sin definir',
        'Período'=>($c['period']??'')!==''?$c['period']:'Sin definir'
    ];
}
// Keep user-uploaded covers outside the web root, using the existing private storage.
function course_cover_directory(bool $create=false): ?string {
    $root=profile_directory($create);
    if(!$root) return null;
    $dir=$root.'/course-covers';
    if(is_link($dir)) return null;
    if($create && !is_dir($dir) && !@mkdir($dir,0700) && !is_dir($dir)) return null;
    if(!is_dir($dir) || realpath($dir)!==$dir) return null;
    $mode=fileperms($dir);
    return $mode!==false && ($mode & 0077)===0?$dir:null;
}
function course_cover_file(?string $name): ?string {
    if(!$name || !preg_match('/\A[a-f0-9]{32}\.jpg\z/D',$name)) return null;
    $dir=course_cover_directory();
    if(!$dir) return null;
    $path=$dir.'/'.$name;
    return !is_link($path) && is_file($path) && is_readable($path)?$path:null;
}
function course_cover_url(array $c): string {
    if($file=course_cover_file($c['thumbnail_path']??null)) return image_cache_url('?course_cover='.(string)$c['id'],image_cache_version($file,'course-cover-jpeg'));
    $variant=(int)($c['thumbnail_variant']??1);
    return 'assets/courses/cover-'.(in_array($variant,[1,2,3],true)?$variant:1).'.svg';
}
function course_cover_remove(?string $name): void {
    $path=course_cover_file($name); if($path) @unlink($path);
}
function course_cover_upload(): ?string {
    $f=$_FILES['miniatura']??null;
    if($f===null || (is_array($f)&&($f['error']??null)===UPLOAD_ERR_NO_FILE)) return null;
    if(!is_array($f)||($f['error']??null)!==UPLOAD_ERR_OK||!is_string($f['tmp_name']??null)||!is_uploaded_file($f['tmp_name'])) throw new DomainException('No se pudo recibir la miniatura.');
    $source=$f['tmp_name']; $size=filesize($source);
    if(!$size||$size>5*1024*1024) throw new DomainException('La miniatura debe pesar máximo 5 MB.');
    $info=@getimagesize($source);
    if(!$info||!in_array($info[2],[IMAGETYPE_JPEG,IMAGETYPE_PNG,IMAGETYPE_WEBP],true)||$info[0]<1||$info[1]<1||$info[0]>6000||$info[1]>6000||$info[0]*$info[1]>12000000) throw new DomainException('Usa JPG, PNG o WebP de hasta 12 megapíxeles.');
    if(!function_exists('imagejpeg')||!function_exists('imagecreatefromstring')) throw new DomainException('El hosting necesita GD para subir miniaturas. Puedes crear el curso sin imagen.');
    $dir=course_cover_directory(true);
    if(!$dir||!is_writable($dir)) throw new DomainException('No se puede escribir en la carpeta privada de miniaturas.');
    $raw=file_get_contents($source); $image=$raw===false?false:@imagecreatefromstring($raw); unset($raw);
    if(!$image) throw new DomainException('No se pudo procesar la miniatura.');
    $tmp=null; $out=null;
    try {
        $out=imagecreatetruecolor(720,405);
        if(!$out) throw new DomainException('No se pudo preparar la miniatura.');
        imagefill($out,0,0,imagecolorallocate($out,255,255,255));
        $w=imagesx($image); $h=imagesy($image); $cw=min($w,max(1,(int)round($h*16/9))); $ch=min($h,max(1,(int)round($w*9/16)));
        if(!imagecopyresampled($out,$image,0,0,(int)(($w-$cw)/2),(int)(($h-$ch)/2),720,405,$cw,$ch)) throw new DomainException('No se pudo preparar la miniatura.');
        $tmp=tempnam($dir,'.cover-');
        if(!$tmp||dirname($tmp)!==$dir||!chmod($tmp,0600)||!imagejpeg($out,$tmp,78)||!filesize($tmp)) throw new DomainException('No se pudo guardar la miniatura.');
        $name=bin2hex(random_bytes(16)).'.jpg';
        if(!@rename($tmp,$dir.'/'.$name)) throw new DomainException('No se pudo guardar la miniatura.');
        return $name;
    } finally { if($tmp&&is_file($tmp)) @unlink($tmp); if($out) imagedestroy($out); imagedestroy($image); }
}
function serve_course_cover(?array $u): never {
    require_role($u,'admin','subadmin','teacher','student');
    if(($_SERVER['REQUEST_METHOD']??'GET')!=='GET') { header('Allow: GET'); http_response_code(405); exit; }
    $id=filter_var($_GET['course_cover']??null,FILTER_VALIDATE_INT,['options'=>['min_range'=>1]]);
    $c=$id?course_for($id,$u):null;
    $file=$c?course_cover_file($c['thumbnail_path']??null):null;
    if(!$file||!($fp=@fopen($file,'rb'))) { http_response_code(404); exit; }
    $stat=fstat($fp);
    if(!$stat||$stat['size']<1||$stat['size']>1000000) { fclose($fp); http_response_code(404); exit; }
    $version=image_cache_request_version(image_cache_version($file,'course-cover-jpeg',$stat));
    session_write_close();
    header('Cross-Origin-Resource-Policy: same-origin');
    if(image_cache_not_modified($version,300)) { fclose($fp); exit; }
    image_cache_headers($version,300);
    header('Content-Type: image/jpeg'); header('Content-Disposition: inline');
    header('Content-Length: '.$stat['size']);
    fpassthru($fp); fclose($fp); exit;
}

// Edit metadata only: existing modules, lessons, enrollments and progress stay intact.
function course_can_edit(?array $u,array $c): bool {
    return is_manager($u) || ($u!==null && $u['role']==='teacher' && (string)$u['id']===(string)$c['teacher_id']);
}
function course_edit_update(array $u,int $id,array $r): void {
    require_role($u,'admin','subadmin','teacher');
    $title=creation_value($r,'titulo',180);
    $description=creation_value($r,'descripcion',20000);
    [$modality,$hours,$level,$period]=course_metadata($r);
    $username=creation_value($r,'usuario_responsable',190);
    $restore=$r['restore_default']??'';
    if(!in_array($restore,['','1'],true)) throw new DomainException('Opción de miniatura inválida.');
    $pdo=db(); $pdo->beginTransaction();
    $newCover=null; $oldCover=null; $cover=null; $committed=false;
    try {
        $actor=one('SELECT '.user_identity_columns().' FROM users WHERE id=? FOR UPDATE',[$u['id']]);
        $c=one('SELECT * FROM courses WHERE id=? FOR UPDATE',[$id]);
        if(!$actor || !$c || !course_can_edit($actor,$c)) throw new DomainException('Curso inexistente o no autorizado.');
        $responsible=find_by_username($username);
        if(!$responsible) throw new DomainException('Usuario responsable inexistente.');
        $teacher=(int)$responsible['id'];
        $allowed=is_manager($actor)?array_map('intval',array_column(available_teachers($actor),'id')):[(int)$actor['id']];
        // A manager can retain the existing owner even if reassignment to that role is restricted.
        if(!in_array($teacher,$allowed,true) && !(is_manager($actor) && $teacher===(int)$c['teacher_id'])) throw new DomainException('Usuario responsable no autorizado.');
        if(one('SELECT id FROM courses WHERE title=? AND teacher_id=? AND id<>?',[$title,$teacher,$id])) throw new DomainException('Ya existe otro curso con este título y responsable.');
        $oldCover=$c['thumbnail_path']; $cover=$oldCover; $variant=(int)$c['thumbnail_variant'];
        $newCover=course_cover_upload();
        if($newCover!==null && $restore==='1') throw new DomainException('Elige una miniatura nueva o restaura la predeterminada, no ambas opciones.');
        if($newCover!==null) $cover=$newCover;
        elseif($restore==='1') { $cover=null; $variant=random_int(1,3); }
        query('UPDATE courses SET title=?,description=?,teacher_id=?,modality=?,duration_hours=?,level=?,period=?,thumbnail_variant=?,thumbnail_path=? WHERE id=?',[$title,$description,$teacher,$modality,$hours,$level,$period,$variant,$cover,$id]);
        $pdo->commit(); $committed=true;
    } catch(Throwable $e) {
        if($pdo->inTransaction()) $pdo->rollBack();
        throw $e;
    } finally { if(!$committed && $newCover!==null) course_cover_remove($newCover); }
    if($oldCover!==null && $oldCover!==$cover) course_cover_remove($oldCover);
}
