<?php
declare(strict_types=1);
if (PHP_SAPI !== 'cli') { http_response_code(404); exit; }
require __DIR__.'/app.php';
date_default_timezone_set('America/Guayaquil');
if ($argc !== 2) { fwrite(STDERR,"Uso: php migrate_json.php /ruta/storage/data.json\n"); exit(1); }
$copied=[];
try {
    $source=realpath($argv[1]);
    if ($source===false || !is_file($source)) throw new RuntimeException('No se encontro el JSON de origen.');
    $old=json_decode((string)file_get_contents($source),true,512,JSON_THROW_ON_ERROR);
    if (!is_array($old) || !is_array($old['raffles']??null) || !is_array($old['participants']??null)) throw new RuntimeException('Formato JSON invalido.');
    $validId=static fn($id)=>is_string($id) && preg_match('/^[a-f0-9]{24}$/D',$id);
    $numbers=[]; $photos=[];
    foreach ($old['raffles'] as $id=>$r) {
        if (!$validId($id) || $r['id']!==$id || !is_int($r['total']) || $r['total']<1 || $r['total']>1000000 || !is_int($r['price_cents']) || $r['price_cents']<0 || $r['price_cents']>99999999 || !isset(STATES[$r['status']],TYPES[$r['type']]) || !is_array($r['photos']) || array_keys($r['photos'])!==[0,1,2]) throw new RuntimeException('Sorteo invalido: '.$id);
        foreach ($r['photos'] as $name) {
            if ($name===null) continue;
            if (!is_string($name) || !preg_match('/^[a-f0-9]{24}\.(jpg|png|webp)$/D',$name,$m) || isset($photos[$name])) throw new RuntimeException('Nombre de foto invalido o repetido.');
            $path=dirname($source).'/uploads/'.$name;
            $mime=['jpg'=>'image/jpeg','png'=>'image/png','webp'=>'image/webp'][$m[1]];
            if (!is_file($path) || is_link($path) || filesize($path)>5*1024*1024 || (new finfo(FILEINFO_MIME_TYPE))->file($path)!==$mime || (@getimagesize($path)['mime']??null)!==$mime) throw new RuntimeException('Foto ausente o invalida: '.$name);
            $photos[$name]=$path;
        }
    }
    foreach ($old['participants'] as $id=>$p) {
        if (!$validId($id) || $p['id']!==$id || !isset($old['raffles'][$p['raffle_id']],PAYMENTS[$p['payment']]) || !is_int($p['number']) || $p['number']<1 || $p['number']>$old['raffles'][$p['raffle_id']]['total']) throw new RuntimeException('Participacion invalida: '.$id);
        $key=$p['raffle_id'].':'.$p['number'];
        if (isset($numbers[$key])) throw new RuntimeException('Numero repetido: '.$key);
        $numbers[$key]=true;
    }
    db(function(array &$d) use ($old,$photos,&$copied) {
        if ($d['raffles'] || $d['participants']) throw new RuntimeException('La base de destino debe estar vacia. No se sobrescriben datos.');
        foreach ($photos as $name=>$path) {
            $dest=STORE.'/uploads/'.$name;
            if (is_file($dest) && hash_file('sha256',$dest)===hash_file('sha256',$path)) continue;
            if (file_exists($dest) || !copy($path,$dest)) throw new RuntimeException('No se pudo copiar sin sobrescribir: '.$name);
            $copied[]=$dest;
        }
        $d=['raffles'=>$old['raffles'],'participants'=>$old['participants']];
    },true);
    echo 'Migracion completada: '.count($old['raffles']).' sorteos, '.count($old['participants'])." participaciones.\n";
} catch (Throwable $e) {
    foreach ($copied as $path) @unlink($path);
    fwrite(STDERR,$e->getMessage()."\n"); exit(1);
}
