<?php
declare(strict_types=1);
// FUTUREO STUDIO v0.1.18 - validated, non-destructive per-track effect settings.
if (!defined('FUTUREO_RECORDINGS')) { http_response_code(404); exit; }
function fxDefaults(): array {
    return ['enabled'=>true,'tune'=>false,'tuneAmount'=>70,'key'=>0,'scale'=>'chromatic',
        'gate'=>false,'threshold'=>-45,'deess'=>false,'deessAmount'=>45,
        'eq'=>false,'low'=>0,'mid'=>0,'high'=>0,'comp'=>false,'compAmount'=>45,
        'leveler'=>false,'levelTarget'=>-18,'levelStrength'=>85,'levelBoost'=>12,
        'reverb'=>false,'reverbMix'=>20,'delay'=>false,'delayMix'=>15,'delayTime'=>280];
}
function normalizeFx($raw): array {
    $out=fxDefaults(); if(!is_array($raw)) return $out;
    $bounds=['tuneAmount'=>[0,100],'key'=>[0,11],'threshold'=>[-70,-25],'deessAmount'=>[0,100],
        'low'=>[-12,12],'mid'=>[-12,12],'high'=>[-12,12],'compAmount'=>[0,100],
        'levelTarget'=>[-30,-9],'levelStrength'=>[0,100],'levelBoost'=>[0,18],
        'reverbMix'=>[0,60],'delayMix'=>[0,50],'delayTime'=>[80,800]];
    foreach($out as $key=>$value){
        if(!array_key_exists($key,$raw))continue;
        $v=$raw[$key];
        if(is_bool($value)){if(is_bool($v))$out[$key]=$v;}
        elseif($key==='scale'){if(in_array($v,['chromatic','major','minor'],true))$out[$key]=$v;}
        elseif(is_int($v)||is_float($v)){if(is_finite((float)$v))$out[$key]=(int)round(max($bounds[$key][0],min($bounds[$key][1],$v)));}
    }
    return $out;
}
function savedFx(array $project): array {
    $raw=$project['content']['track_fx']??[]; $out=[];
    for($t=1;$t<=4;$t++)$out[$t]=normalizeFx(is_array($raw)?($raw[$t]??[]):[]);
    return $out;
}
function saveTrackFx(string $path,string $folder,string $dir): void {
    $track=filter_var($_POST['track']??null,FILTER_VALIDATE_INT);
    $raw=$_POST['settings']??null;
    if($track===false||$track<1||$track>4||!is_string($raw)||strlen($raw)>4096)fail('Configuración FX inválida.');
    $settings=json_decode($raw,true);
    if(!is_array($settings)||json_last_error()!==JSON_ERROR_NONE)fail('Configuración FX inválida.');
    if(!ensureDir($folder)||!ensureDir($dir)||is_link($dir.'/.lock'))fail('No se puede escribir en el proyecto.',500);
    $lock=@fopen($dir.'/.lock','c+b');
    if(!$lock||!flock($lock,LOCK_EX))fail('No se pudo bloquear el proyecto.',500);
    $data=readProject($path); if(!isset($data['content'])||!is_array($data['content']))$data['content']=[];
    $all=savedFx($data); $all[$track]=normalizeFx($settings);
    $data['content']['track_fx']=$all;
    storeProject($path,$data);
    flock($lock,LOCK_UN);fclose($lock);
    reply(['ok'=>true,'track'=>$track,'settings'=>$all[$track]]);
}
// Shared preset library, not part of the public project listing.
function presetLibrary(string $root): array {
    $file=$root.'/.fx-presets.json';
    if(is_link($file))fail('Biblioteca de presets no válida.',500);
    if(!is_file($file))return [];
    $data=json_decode((string)@file_get_contents($file),true);
    if(!is_array($data))fail('No se pudo leer la biblioteca de presets.',500);
    return array_values($data);
}
function saveFxPreset(string $root): void {
    $name=$_POST['name']??null; $raw=$_POST['settings']??null;
    if(!is_string($name)||!is_string($raw)||strlen($raw)>4096)fail('Preset inválido.');
    $name=trim($name);
    if($name===''||strlen($name)>120||!preg_match('/\A[^\x00-\x1f\x7f]+\z/u',$name))fail('Escribe un nombre válido (máximo 120 bytes).');
    $settings=json_decode($raw,true);
    if(!is_array($settings)||json_last_error()!==JSON_ERROR_NONE)fail('Configuración FX inválida.');
    $lp=$root.'/.fx-presets.lock';
    if(!ensureDir($root)||is_link($lp))fail('No se puede escribir la biblioteca.',500);
    $lock=@fopen($lp,'c+b');
    if(!$lock||!flock($lock,LOCK_EX))fail('No se pudo bloquear la biblioteca.',500);
    $items=presetLibrary($root); $found=false;
    foreach($items as &$item){if(($item['name']??null)===$name){$item['settings']=normalizeFx($settings);$item['updated_at']=date(DATE_ATOM);$found=true;break;}}unset($item);
    if(!$found){if(count($items)>=200)fail('La biblioteca alcanzó 200 presets.',409);$items[]=['name'=>$name,'settings'=>normalizeFx($settings),'updated_at'=>date(DATE_ATOM)];}
    $json=json_encode($items,JSON_PRETTY_PRINT|JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);
    $tmp=@tempnam($root,'.fx-');
    if($tmp===false||$json===false||@file_put_contents($tmp,$json."\n")!==strlen($json)+1||!@chmod($tmp,0640)||!@rename($tmp,$root.'/.fx-presets.json')){if($tmp!==false)@unlink($tmp);fail('No se pudo guardar el preset.',500);}
    flock($lock,LOCK_UN);fclose($lock);reply(['ok'=>true,'presets'=>$items]);
}
