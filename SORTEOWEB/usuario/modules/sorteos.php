<?php if(!defined('SW_APP')||!SW_PUBLIC){http_response_code(404);exit;} $rows=active_raffles(); ?>
<p class="user-sub">Hola, <?=h($u['first_names'])?>. Descubre los sorteos disponibles.</p>
<?php if(!$rows):?>
<div class="user-empty">No hay sorteos activos por el momento.</div>
<?php else:?>
<div class="user-raffle-list">
<?php foreach($rows as $r):
    $slots=array_values(array_filter(explode(',',(string)($r['photo_slots']??'')),fn($n)=>in_array($n,['1','2','3'],true)));
    $id='raffle-'.h($r['id']);
    $total=max(0,(int)$r['total']);
    $registered=max(0,(int)$r['registered_count']);
    $paid=min($registered,max(0,(int)$r['paid_count']));
    $pending=$registered-$paid;
    $available=max(0,$total-$registered);
?>
<article class="user-raffle-card">
    <div class="user-raffle-media">
        <?php if($slots):?>
        <section class="user-mini-carousel" aria-label="Galería de <?=h($r['title'])?>" data-carousel>
            <?php foreach($slots as $i=>$slot):?><figure class="user-mini-slide" data-slide <?=$i===0?'':'hidden'?>><img src="<?=h(pub_url('photo',['id'=>$r['id'],'slot'=>(int)$slot]))?>" alt="<?=h($r['title'])?> · imagen <?=$i+1?>" loading="lazy"></figure><?php endforeach;?>
            <?php if(count($slots)>1):?><button type="button" class="carousel-arrow prev user-mini-prev" data-prev aria-label="Imagen anterior">‹</button><button type="button" class="carousel-arrow next user-mini-next" data-next aria-label="Imagen siguiente">›</button><div class="user-mini-dots"><?php foreach($slots as $i=>$slot):?><button type="button" data-dot="<?=$i?>" aria-label="Mostrar imagen <?=$i+1?>" aria-pressed="<?=$i===0?'true':'false'?>"></button><?php endforeach;?><button type="button" class="carousel-pause" data-pause aria-label="Pausar carrusel">Ⅱ</button></div><?php endif;?>
        </section>
        <?php else:?><div class="user-raffle-placeholder" aria-hidden="true">★</div><?php endif;?>
    </div>
    <div class="user-raffle-copy">
        <h2><?=h($r['title'])?></h2>
        <div class="user-ticket-capacity">
            <div class="user-ticket-labels"><span><strong><?=number_format($paid)?></strong> comprados</span><span><strong><?=number_format($available)?></strong> disponibles</span></div>
            <div class="user-ticket-bar" role="img" aria-label="<?=h($paid.' comprados, '.$pending.' pendientes de pago y '.$available.' disponibles, de '.$total.' boletos')?>">
                <?php if($paid>0):?><span class="ticket-paid" style="flex-grow:<?=$paid?>" aria-hidden="true"></span><?php endif;?>
                <?php if($pending>0):?><span class="ticket-pending" style="flex-grow:<?=$pending?>" aria-hidden="true"></span><?php endif;?>
                <?php if($available>0):?><span class="ticket-free" style="flex-grow:<?=$available?>" aria-hidden="true"></span><?php endif;?>
            </div>
            <div class="user-ticket-caption"><span>Total: <?=number_format($total)?> boletos</span><?php if($pending>0):?><span class="ticket-pending-label"><strong><?=number_format($pending)?></strong> pendientes de pago</span><?php endif;?></div>
        </div>
        <div class="user-raffle-actions"><button type="button" class="pub-btn cta" data-user-dialog="<?=$id?>-details">Ver detalles y participar · <?=money($r['price_cents'])?></button></div>
    </div>
</article>
<dialog class="user-raffle-dialog user-details-dialog" id="<?=$id?>-details" aria-labelledby="<?=$id?>-title">
    <div class="user-dialog-head"><h2 id="<?=$id?>-title" tabindex="-1"><?=h($r['title'])?></h2><form method="dialog"><button class="user-dialog-close" aria-label="Cerrar detalles" autofocus>×</button></form></div>
    <?php if($slots):?><div class="user-details-gallery" aria-label="Fotografías del premio"><?php foreach($slots as $i=>$slot):$photoUrl=h(pub_url('photo',['id'=>$r['id'],'slot'=>(int)$slot]));?><button type="button" class="user-details-photo" data-gallery-photo aria-label="Ampliar imagen <?=$i+1?> de <?=count($slots)?>"><img class="user-details-photo-bg" src="<?=$photoUrl?>" alt="" aria-hidden="true" loading="lazy"><img class="user-details-photo-main" src="<?=$photoUrl?>" alt="<?=h($r['title'])?> · imagen <?=$i+1?>" loading="lazy"></button><?php endforeach;?></div><?php endif;?>
    <div class="user-details-scroll" tabindex="0" aria-label="Descripción del sorteo"><p class="raffle-desc"><?=h($r['description']!==''?$r['description']:'Consulta las condiciones del sorteo antes de participar.')?></p></div>
    <dl class="user-raffle-facts user-details-facts"><div><dt>Tipo de premio</dt><dd><?=$r['type']==='producto'?'Producto':'Dinero'?></dd></div><div><dt>Total de boletos</dt><dd><?=number_format((int)$r['total'])?></dd></div><div><dt>Valor por boleto</dt><dd><?=money($r['price_cents'])?></dd></div></dl>
    <div class="user-dialog-foot"><form method="dialog"><button class="pub-btn secondary">Cerrar</button></form><a class="pub-btn primary" href="<?=h(pub_url('account',['tab'=>'numeros','id'=>$r['id']]))?>">Participar por <?=money($r['price_cents'])?></a></div>
</dialog>
<?php endforeach;?>
</div>
<dialog id="user-photo-viewer" class="user-photo-viewer" aria-labelledby="user-photo-viewer-title">
    <header class="photo-viewer-head"><h2 id="user-photo-viewer-title">Fotografías del premio</h2><button type="button" class="photo-viewer-close" data-viewer-close aria-label="Cerrar imagen" autofocus>×</button></header>
    <div class="photo-viewer-stage"><img class="photo-viewer-image" alt=""><button type="button" class="photo-viewer-arrow photo-viewer-prev" data-viewer-prev aria-label="Imagen anterior">‹</button><button type="button" class="photo-viewer-arrow photo-viewer-next" data-viewer-next aria-label="Siguiente imagen">›</button></div>
    <footer class="photo-viewer-foot"><span data-viewer-count aria-live="polite" aria-atomic="true"></span></footer>
</dialog>
<script defer src="usuario/app.js?v=<?=h(SW_VERSION)?>"></script>
<script defer src="usuario/gallery.js?v=<?=h(SW_VERSION)?>"></script>
<?php endif;?>
