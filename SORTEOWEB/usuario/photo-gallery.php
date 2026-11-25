<?php
declare(strict_types=1);
if(!defined('SW_APP')||!SW_PUBLIC){http_response_code(404);exit;}

// Fetch only the metadata required by the shared, versioned photo URLs.
function user_raffle_photo_record(string $id): ?array {
    if(!valid_id($id))return null;
    $r=one("SELECT id,title,type,draw_version FROM raffles WHERE id=? AND status='activo'",[$id]);
    if(!$r)return null;
    $r['photo_tokens']=[];
    $slots=[];
    if($r['type']==='dinero'&&(int)$r['draw_version']===1){$slots=[1];}
    else foreach(all('SELECT slot,filename FROM raffle_photos WHERE raffle_id=? AND slot BETWEEN 1 AND 3 ORDER BY slot',[$id]) as $p){$slot=(int)$p['slot'];$slots[]=$slot;$r['photo_tokens'][$slot]=photo_version($p['filename']);}
    $r['photo_slots']=implode(',',$slots);$r['photo_slot']=$slots[0]??null;
    return $r;
}
function user_gallery_slots(array $r): array {
    return array_values(array_filter(explode(',',(string)($r['photo_slots']??'')),fn($n)=>in_array($n,['1','2','3'],true)));
}
// One identical carousel and photo URL across active-raffle and ticket pages.
function user_raffle_media(array $r,array $slots): void { ?>
<div class="user-raffle-media">
    <?php if($slots):?>
    <section class="user-mini-carousel" aria-label="Galería de <?=h($r['title'])?>" data-carousel data-gallery data-gallery-title="<?=h($r['title'])?>">
        <?php foreach($slots as $i=>$slot):?><figure class="user-mini-slide" data-slide <?=$i===0?'':'hidden'?>>
            <button type="button" class="user-mini-photo" data-gallery-photo data-full-src="<?=h(pub_photo_url($r,(int)$slot,'original'))?>" aria-label="Ampliar imagen <?=$i+1?> de <?=count($slots)?>">
                <img <?=$i===0?'src':'data-src'?>="<?=h(pub_photo_url($r,(int)$slot,'thumb'))?>" alt="<?=h($r['title'])?> · imagen <?=$i+1?>" decoding="async" <?=$i===0?'loading="lazy"':''?>>
            </button>
        </figure><?php endforeach;?>
        <?php if(count($slots)>1):?><button type="button" class="carousel-arrow prev user-mini-prev" data-prev aria-label="Imagen anterior">‹</button><button type="button" class="carousel-arrow next user-mini-next" data-next aria-label="Imagen siguiente">›</button><div class="user-mini-dots"><?php foreach($slots as $i=>$slot):?><button type="button" data-dot="<?=$i?>" aria-label="Mostrar imagen <?=$i+1?>" aria-pressed="<?=$i===0?'true':'false'?>"></button><?php endforeach;?><button type="button" class="carousel-pause" data-pause aria-label="Pausar carrusel">Ⅱ</button></div><?php endif;?>
    </section>
    <?php else:?><div class="user-raffle-placeholder" aria-hidden="true">★</div><?php endif;?>
</div>
<?php }
// Reuse the original viewer dialog on both pages (one instance per document).
function user_photo_viewer(): void { ?>
<dialog id="user-photo-viewer" class="user-photo-viewer" aria-labelledby="user-photo-viewer-title">
    <header class="photo-viewer-head"><h2 id="user-photo-viewer-title">Fotografías del premio</h2><button type="button" class="photo-viewer-close" data-viewer-close aria-label="Cerrar imagen" autofocus>×</button></header>
    <div class="photo-viewer-stage"><img class="photo-viewer-image" alt=""><button type="button" class="photo-viewer-arrow photo-viewer-prev" data-viewer-prev aria-label="Imagen anterior">‹</button><button type="button" class="photo-viewer-arrow photo-viewer-next" data-viewer-next aria-label="Siguiente imagen">›</button></div>
    <footer class="photo-viewer-foot"><span data-viewer-count aria-live="polite" aria-atomic="true"></span></footer>
</dialog>
<script defer src="usuario/gallery.js?v=<?=h(SW_VERSION)?>"></script>
<?php }
