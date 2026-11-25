<?php if(!defined('SW_APP')||!SW_PUBLIC){http_response_code(404);exit;} $rows=active_raffles(); ?>
<p class="user-sub">Hola, <?=h($u['first_names'])?>. Descubre los sorteos disponibles.</p>
<?php if(!$rows):?>
<div class="user-empty">No hay sorteos activos por el momento.</div>
<?php else:?>
<div class="user-raffle-list"><?php foreach($rows as $r): $slots=array_values(array_filter(explode(',',(string)($r['photo_slots']??'')),fn($n)=>in_array($n,['1','2','3'],true))); ?>
<article class="user-raffle-card">
    <div class="user-raffle-media">
        <?php if($slots):?>
        <section class="user-mini-carousel" aria-label="Galería de <?=h($r['title'])?>" data-carousel>
            <?php foreach($slots as $i=>$slot):?><figure class="user-mini-slide" data-slide <?=$i===0?'':'hidden'?>><img src="<?=h(pub_url('photo',['id'=>$r['id'],'slot'=>(int)$slot]))?>" alt="<?=h($r['title'])?> · imagen <?=$i+1?>" <?=$i===0?'fetchpriority="high"':'loading="lazy"'?>></figure><?php endforeach;?>
            <?php if(count($slots)>1):?><button type="button" class="carousel-arrow prev user-mini-prev" data-prev aria-label="Imagen anterior">‹</button><button type="button" class="carousel-arrow next user-mini-next" data-next aria-label="Imagen siguiente">›</button><div class="user-mini-dots"><?php foreach($slots as $i=>$slot):?><button type="button" data-dot="<?=$i?>" aria-label="Mostrar imagen <?=$i+1?>" aria-pressed="<?=$i===0?'true':'false'?>"></button><?php endforeach;?><button type="button" class="carousel-pause" data-pause aria-label="Pausar carrusel">Ⅱ</button></div><?php endif;?>
        </section>
        <?php else:?><div class="user-raffle-placeholder" aria-hidden="true">★</div><?php endif;?>
    </div>
    <div class="user-raffle-copy">
        <div class="user-raffle-meta"><span class="badge">Sorteo activo</span><?php if((string)$r['type']==='producto'):?><span class="muted-chip">Premio físico</span><?php else:?><span class="muted-chip">Premio en dinero</span><?php endif;?></div>
        <h2><?=h($r['title'])?></h2>
        <p class="raffle-desc"><?=h($r['description']!==''?$r['description']:'Descubre este premio y participa desde tu cuenta.')?></p>
        <div class="user-raffle-stats"><div><small>Boletos disponibles</small><strong><?=number_format((int)$r['total'])?></strong></div><div><small>Valor por boleto</small><strong><?=money($r['price_cents'])?></strong></div></div>
        <div class="user-raffle-actions"><a class="pub-btn cta" href="<?=h(pub_url('account',['tab'=>'boletos']))?>">Participar por <?=money($r['price_cents'])?></a></div>
    </div>
</article><?php endforeach;?></div>
<?php endif;?>
<p class="user-sub">La selección de boletos y el pago en línea se habilitarán más adelante.</p>
