<?php
declare(strict_types=1);
// FUTUREO STUDIO v0.1.22: persistent, non-destructive timeline history.
if (!defined('FUTUREO_RECORDINGS')) { http_response_code(404); exit; }
const FUTUREO_HISTORY_LIMIT = 40;
const FUTUREO_HISTORY_BYTES = 4194304;
function clipHistory(array $data): array {
    $h=$data['content']['clip_history']??[];
    return ['undo'=>is_array($h['undo']??null)?array_values($h['undo']):[],
            'redo'=>is_array($h['redo']??null)?array_values($h['redo']):[]];
}
function historyInfo(array $data): array {
    $h=clipHistory($data);$u=end($h['undo']);$r=end($h['redo']);
    return ['undo_count'=>count($h['undo']),'redo_count'=>count($h['redo']),
        'undo_id'=>$u['id']??null,'redo_id'=>$r['id']??null,
        'undo_label'=>$u['label']??'','redo_label'=>$r['label']??''];
}
function historyRows(array $items): array {
    $map=[];
    foreach(array_values($items) as $i=>$item){
        if(is_array($item)&&is_string($item['id']??null)&&preg_match('/\A[a-f0-9]{24}\z/',$item['id']))$map[$item['id']]=['index'=>$i,'item'=>$item];
    }
    return $map;
}
function historyPush(array &$data,array $before,string $label): void {
    $a=historyRows($before);$b=historyRows($data['content']['recordings']??[]);
    $old=[];$new=[];
    foreach(array_unique(array_merge(array_keys($a),array_keys($b))) as $id){
        if(isset($a[$id],$b[$id])&&$a[$id]['item']===$b[$id]['item'])continue;
        if(isset($a[$id]))$old[]=$a[$id];
        if(isset($b[$id]))$new[]=$b[$id];
    }
    if(!$old&&!$new)return;
    $h=clipHistory($data);$h['redo']=[];
    $h['undo'][]=['id'=>bin2hex(random_bytes(12)),'label'=>$label,'before'=>$old,'after'=>$new];
    while(count($h['undo'])>FUTUREO_HISTORY_LIMIT || (count($h['undo'])>1&&strlen((string)json_encode($h))>FUTUREO_HISTORY_BYTES))array_shift($h['undo']);
    $data['content']['clip_history']=$h;
}
function handleClipHistory(string $action,string $path,string $folder,string $dir): void {
    if(!ensureDir($folder)||!ensureDir($dir)||is_link($dir.'/.lock'))fail('No se puede escribir en el proyecto.',500);
    $lock=@fopen($dir.'/.lock','c+b');if(!$lock||!flock($lock,LOCK_EX))fail('No se pudo bloquear el proyecto.',500);
    $data=readProject($path);$h=clipHistory($data);$from=$action==='undo_clip'?'undo':'redo';$to=$from==='undo'?'redo':'undo';
    $entry=end($h[$from]);$token=$_POST['history_id']??'';
    if(!$entry)fail($from==='undo'?'No hay cambios para deshacer.':'No hay cambios para rehacer.',409);
    if(!is_string($token)||!is_string($entry['id']??null)||!hash_equals($entry['id'],$token))fail('El historial cambió. Se actualizará la línea de tiempo.',409);
    $expected=$entry[$from==='undo'?'after':'before']??null;
    $restore=$entry[$from==='undo'?'before':'after']??null;
    if(!is_array($expected)||!is_array($restore))fail('Historial inválido.',409);
    $items=$data['content']['recordings']??[];
    if(!is_array($items))fail('Proyecto inválido.',422);
    $current=historyRows($items);$affected=[];$expectedIds=[];
    foreach($expected as $row){
        $item=$row['item']??null;$id=$item['id']??null;
        if(!is_string($id)||!isset($current[$id])||$current[$id]['item']!=$item)fail('Un clip cambió desde la última edición. No se aplicó el historial.',409);
        $affected[$id]=true;$expectedIds[$id]=true;
    }
    foreach($restore as $row){
        $item=$row['item']??null;$id=$item['id']??null;
        if(!is_string($id)||!is_int($row['index']??null)||$row['index']<0||count(savedRecordings(['content'=>['recordings'=>[$item]]]))!==1)fail('Clip del historial inválido.',409);
        if(isset($current[$id])&&!isset($expectedIds[$id]))fail('El identificador del clip ya está en uso.',409);
        $media=$dir.'/'.$item['file'];if(!is_file($media)||is_link($media))fail('No se encuentra el audio original. No se aplicó el historial.',404);
        $affected[$id]=true;
    }
    // Preserve all unrelated clips and project fields, including FX and tempo.
    $out=array_values(array_filter($items,static function($item)use($affected){return !is_array($item)||!is_string($item['id']??null)||!isset($affected[$item['id']]);}));
    usort($restore,static function($a,$b){return $a['index']<=>$b['index'];});
    foreach($restore as $row)array_splice($out,min($row['index'],count($out)),0,[$row['item']]);
    if(count(savedRecordings(['content'=>['recordings'=>$out]]))>500)fail('El proyecto alcanzó el límite de 500 clips.',409);
    array_pop($h[$from]);$h[$to][]=$entry;
    $data['content']['recordings']=$out;$data['content']['clip_history']=$h;
    storeProject($path,$data);
    $visible=array_values(array_filter(savedRecordings($data),static function($r)use($dir){return is_file($dir.'/'.$r['file'])&&!is_link($dir.'/'.$r['file']);}));
    flock($lock,LOCK_UN);fclose($lock);
    reply(['ok'=>true,'recordings'=>array_map(static function($r)use($dir){return waveInfo($r,$dir);},$visible),'history'=>historyInfo($data),'label'=>$entry['label']??'Edición']);
}
