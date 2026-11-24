<?php
declare(strict_types=1);
if (!defined('VE_VERSION')) { http_response_code(404); exit; }

function institution_settings(): array {
    $default=['institution_name'=>'VIRTUALEDUC','institution_subtitle'=>'Plataforma académica institucional','institutional_phone'=>'','institutional_email'=>'','active_period'=>'','logo_path'=>null,'configured'=>false];
    try {
        $row=one('SELECT * FROM ve_institution_settings WHERE id=1');
        if ($row) return array_merge($default,$row,['configured'=>true]);
    } catch (PDOException $e) {
        // The rest of the site remains available until the migration is imported.
        if (($e->errorInfo[1]??null)!==1146) throw $e;
    }
    return $default;
}

function institution_logo_file(?string $path): ?string {
    if (!$path || !preg_match('~\Auploads/institution/logo-[a-f0-9]{32}\.(png|jpg|webp)\z~D',$path)) return null;
    $file=dirname(__DIR__).'/'.$path;
    return is_file($file) && !is_link($file) ? $file : null;
}

function serve_institution_logo(): never {
    $settings=institution_settings();
    $file=institution_logo_file($settings['logo_path']);
    if (!$file) { http_response_code(404); exit; }
    $types=['png'=>'image/png','jpg'=>'image/jpeg','webp'=>'image/webp'];
    header('Content-Type: '.$types[pathinfo($file,PATHINFO_EXTENSION)]);
    header('Content-Length: '.filesize($file));
    header('Content-Disposition: inline');
    readfile($file); exit;
}

function render_institution_brand(array $settings): void { ?>
    <a class="ve-brand" href="index.php">
      <?php if (institution_logo_file($settings['logo_path'])): ?><img class="ve-brand-logo" src="?institution_logo=1" alt="Logo institucional"><?php else: ?><span class="ve-brand-logo ve-brand-mark" aria-hidden="true">VE</span><?php endif; ?>
      <span class="ve-brand-copy"><strong><?=h($settings['institution_name'])?></strong><?php if($settings['institution_subtitle']!==''):?><small><?=h($settings['institution_subtitle'])?></small><?php endif;?></span>
    </a>
<?php }

function save_institution(): void {
    $name=field('institution_name',180);
    $subtitle=field('institution_subtitle',180,false);
    $phone=field('institutional_phone',50,false);
    $email=field('institutional_email',190,false);
    $period=field('active_period',50,false);
    if ($email!==''&&!filter_var($email,FILTER_VALIDATE_EMAIL)) throw new DomainException('Correo institucional inválido.');
    $current=institution_settings();
    if (!$current['configured']) throw new DomainException('Importa migrations/0.1.10.sql en phpMyAdmin antes de guardar.');
    $upload=$_FILES['logo']??null;
    $new=null;
    if ($upload!==null && ($upload['error']??UPLOAD_ERR_NO_FILE)!==UPLOAD_ERR_NO_FILE) {
        if (($upload['error']??null)!==UPLOAD_ERR_OK || !is_string($upload['tmp_name']??null) || !is_uploaded_file($upload['tmp_name'])) throw new DomainException('No se pudo recibir la imagen. Verifica el tamaño permitido por PHP.');
        $tmp=$upload['tmp_name'];
        $size=filesize($tmp);
        if ($size===false||$size<1||$size>2*1024*1024) throw new DomainException('El logo debe pesar máximo 2 MB.');
        $info=@getimagesize($tmp);
        $exts=[IMAGETYPE_PNG=>'png',IMAGETYPE_JPEG=>'jpg',IMAGETYPE_WEBP=>'webp'];
        if (!$info||!isset($exts[$info[2]])||$info[0]<1||$info[1]<1||$info[0]>4096||$info[1]>4096) throw new DomainException('Usa una imagen PNG, JPG o WebP válida, de hasta 4096 × 4096 píxeles.');
        $mime=(new finfo(FILEINFO_MIME_TYPE))->file($tmp);
        if ($mime!==$info['mime']) throw new DomainException('Tipo de imagen inválido.');
        $dir=dirname(__DIR__).'/uploads/institution';
        if (!is_dir($dir) && !@mkdir($dir,0755,true) && !is_dir($dir)) throw new DomainException('No se pudo crear la carpeta de logos.');
        if (is_link($dir)||!is_writable($dir)) throw new DomainException('La carpeta uploads/institution necesita permisos de escritura.');
        $new='uploads/institution/logo-'.bin2hex(random_bytes(16)).'.'.$exts[$info[2]];
        if (!move_uploaded_file($tmp,dirname(__DIR__).'/'.$new)) throw new DomainException('No se pudo guardar el logo en el hosting.');
    }
    $pdo=db(); $old=null; $path=null;
    try {
        $pdo->beginTransaction();
        $row=one('SELECT logo_path FROM ve_institution_settings WHERE id=1 FOR UPDATE');
        if (!$row) throw new DomainException('Importa la migración institucional.');
        $old=$row['logo_path'];
        $path=$new??(isset($_POST['remove_logo'])?null:$old);
        query('UPDATE ve_institution_settings SET institution_name=?,institution_subtitle=?,institutional_phone=?,institutional_email=?,active_period=?,logo_path=? WHERE id=1',[$name,$subtitle,$phone,$email,$period,$path]);
        $pdo->commit();
    } catch (Throwable $e) {
        if ($pdo->inTransaction()) $pdo->rollBack();
        if ($new && ($f=institution_logo_file($new))) @unlink($f);
        if ($e instanceof DomainException) throw $e;
        error_log($e->getMessage()); throw new DomainException('No se pudo guardar la configuración.');
    }
    if ($old!==$path && ($f=institution_logo_file($old))) @unlink($f);
}
