<?php
declare(strict_types=1);
if(!defined('SW_APP')||!SW_PUBLIC){http_response_code(404);exit;}
function draw_public_record(mixed $id,bool $archive=false): ?array {
    if(!valid_id($id))return null;
    return one("SELECT r.id,r.title,r.status,r.type,r.total,r.price_cents,r.participation_mode,r.prize_cents,r.closes_at,r.close_mode,r.participation_limit,r.draw_outcome,r.finalized_at,e.sha256,e.size_bytes,e.published_at,CASE WHEN r.status='finalizado' THEN e.revealed_number ELSE NULL END AS revealed_number,CASE WHEN r.status='finalizado' THEN e.revealed_password ELSE NULL END AS revealed_password".($archive?',e.archive':'')." FROM raffles r JOIN raffle_evidence e ON e.raffle_id=r.id WHERE r.id=? AND r.draw_version=1 AND r.status IN ('activo','finalizado') AND e.published_at IS NOT NULL",[$id]);
}
function draw_download(): never {
    if(($_SERVER['REQUEST_METHOD']??'')!=='GET'){http_response_code(405);exit;}
    $r=draw_public_record($_GET['id']??null,true);
    if(!$r||!is_string($r['archive'])||!hash_equals($r['sha256'],hash('sha256',$r['archive']))){http_response_code(404);exit;}
    session_write_close();header('Content-Type: application/zip');header('Content-Disposition: attachment; filename="resultado-'.$r['id'].'.zip"');header('X-Content-Type-Options: nosniff');header('Content-Length: '.strlen($r['archive']));header('Cache-Control: no-store');echo $r['archive'];exit;
}
// Only reconstruct known internal routes; never trust a supplied redirect URL.
function draw_back_url(?array $r,string $view): string {
    if($view==='results')return pub_url('home').'#transparencia';
    $from=$_GET['from']??null;
    if($from==='home')return pub_url('home').'#sorteos';
    if($from==='sorteos')return pub_url('account',['tab'=>'sorteos']);
    if($from==='numeros'&&$r){
        $params=['tab'=>'numeros','id'=>$r['id']];
        foreach(['return_page'=>'p','return_number'=>'numero'] as $key=>$name){
            $n=filter_var($_GET[$key]??null,FILTER_VALIDATE_INT,['options'=>['min_range'=>1,'max_range'=>1000000]]);
            if($n!==false)$params[$name]=$n;
        }
        return pub_url('account',$params);
    }
    return pub_url('results');
}
function draw_public_page(?array $u,string $view): void {
    $r=$view==='evidence'?draw_public_record($_GET['id']??null):null;
    if($view==='evidence'&&!$r)http_response_code(404);
    pub_head($view==='results'?'Resultados':'Transparencia del sorteo',$u);
    ?><main class="public-wrap draw-public">
        <a class="pub-btn secondary" data-draw-back href="<?=h(draw_back_url($r,$view))?>">Volver</a>
        <h1><?=$view==='results'?'Sorteos y resultados':h($r['title']??'Información no disponible')?></h1>
        <?php if($view==='results'):
            $rows=all("SELECT r.id,r.title,r.status,r.draw_outcome,e.revealed_number FROM raffles r JOIN raffle_evidence e ON e.raffle_id=r.id WHERE r.draw_version=1 AND r.status IN ('activo','finalizado') AND e.published_at IS NOT NULL ORDER BY r.created_at DESC");
            if(!$rows):?><div class="user-empty">Aún no hay sorteos con resultados protegidos publicados.</div><?php else:foreach($rows as $x):?>
                <article class="draw-result-row"><div><strong><?=h($x['title'])?></strong><p><?=h(state_name($x['status']))?><?=$x['status']==='finalizado'&&$x['revealed_number']!==null?' · Número '.h(str_pad((string)$x['revealed_number'],4,'0',STR_PAD_LEFT)):''?></p></div><a class="pub-btn primary" href="<?=h(pub_url('evidence',['id'=>$x['id'],'from'=>'results']))?>">Ver condiciones y resultado</a></article>
            <?php endforeach;endif;
        elseif($r):?>
            <article class="draw-evidence-card">
                <p>Estado: <strong><?=h(state_name($r['status']))?></strong> · <?=h(draw_close_label($r))?></p>
                <p>Modalidad: <?=h(ucfirst($r['participation_mode']))?> · <?=number_format((int)$r['total'])?> números · <?=money($r['price_cents'])?> por participación</p>
                <?php if($r['prize_cents']!==null):?><p><?=$r['type']==='producto'?'Equivalente económico del producto':'Valor del premio'?>: <strong><?=money($r['prize_cents'])?></strong></p><?php endif;?>
                <?php if($r['status']==='finalizado'&&$r['revealed_password']!==null):?>
                    <h2><?=$r['draw_outcome']==='premiado'?'Número ganador: ':'Número seleccionado: '?><?=h(str_pad((string)$r['revealed_number'],4,'0',STR_PAD_LEFT))?></h2>
                    <p><?=$r['draw_outcome']==='premiado'?'Premio asignado a las participaciones ganadoras pagadas. La entrega requiere gestión posterior.':'No se ha asignado el premio. Las devoluciones de las participaciones pagadas están pendientes de revisión.'?></p>
                    <label>Contraseña del archivo protegido</label><code class="draw-hash"><?=h($r['revealed_password'])?></code>
                <?php else:?><p>El resultado está protegido. La contraseña se publicará al finalizar el sorteo.</p><?php endif;?>
                <h2>Verificación del resultado</h2>
                <p>Archivo publicado: <?=h($r['published_at'])?> (hora del servidor).</p>
                <label>Código de verificación del archivo original</label><code class="draw-hash"><?=h($r['sha256'])?></code>
                <a class="pub-btn primary" href="<?=h(pub_url('evidence_zip',['id'=>$r['id']]))?>">Descargar archivo protegido (ZIP)</a>
                <details class="draw-technical"><summary>Información técnica de verificación</summary><p>El código de verificación es el SHA-256 del ZIP original. Puedes calcular el SHA-256 del archivo descargado y compararlo con el código que conservaste antes de participar. El archivo usa cifrado AES-256.</p></details>
            </article>
            <?php pub_draw_conditions($r,false);
        else:?><div class="user-empty">No hay información de verificación publicada para este sorteo.</div><?php endif;?>
    </main><?php pub_footer();
}
