<?php if(!defined('SW_APP')||!SW_PUBLIC||!$u||!profile_complete($u)){http_response_code(403);exit;}
require_once dirname(__DIR__).'/tickets.php';
try{$s=ticket_snapshot($_GET['id']??null,$_GET['p']??1,$_GET['numero']??null);}catch(DomainException $e){$s=null;}
?>
<a class="ticket-back" href="<?=h(pub_url('account',['tab'=>'sorteos']))?>">← Volver a sorteos</a>
<?php if(!$s||!$s['active']):?><div class="user-empty">Este sorteo no está disponible.</div><?php else:
    $params=['tab'=>'numeros','id'=>$s['id']];$blocked=(array)$s['blocked'];
    $jump=$_GET['numero']??'';$highlight=is_string($jump)&&preg_match('/^[0-9]{1,7}$/D',$jump)?(int)$jump:0;
?>
<section class="ticket-board" data-ticket-board data-url="<?=h(pub_url('ticket_status',['id'=>$s['id'],'p'=>$s['page']]))?>" data-start="<?=$s['start']?>" data-end="<?=$s['end']?>">
    <div class="ticket-board-head"><div><h2><?=h($s['title'])?></h2><p>Selecciona un número disponible · <strong data-ticket-price><?=h($s['price_label'])?></strong> por boleto</p></div><span class="ticket-live" data-ticket-live role="status">Actualización cada 5 s</span></div>
    <div class="ticket-summary"><span><strong data-ticket-paid><?=number_format($s['paid'])?></strong> vendidos</span><span><strong data-ticket-pending><?=number_format($s['pending'])?></strong> pendientes</span><span><strong data-ticket-available><?=number_format($s['available'])?></strong> disponibles</span><span><strong data-ticket-total><?=number_format($s['total'])?></strong> total</span></div>
    <div class="ticket-toolbar"><div class="ticket-legend"><span><i class="ticket-swatch free"></i> Disponible</span><span><i class="ticket-swatch sold"></i> Vendido</span><span><i class="ticket-swatch pending"></i> Pendiente</span></div><form class="ticket-find" method="get" action="index.php"><input type="hidden" name="view" value="account"><input type="hidden" name="tab" value="numeros"><input type="hidden" name="id" value="<?=h($s['id'])?>"><input name="numero" aria-label="Buscar número de boleto" inputmode="numeric" pattern="[0-9]{1,7}" maxlength="7" placeholder="Ej. 0001" required><button class="pub-btn secondary" type="submit">Ir al número</button></form></div>
    <div class="ticket-grid" aria-label="Números de boletos">
    <?php for($n=$s['start'];$n<=$s['end'];$n++):$state=$blocked[$n]??'free';$label=ticket_number_label($n);?>
        <button type="button" class="ticket-number<?=$highlight===$n?' ticket-highlight':''?>" data-number="<?=$n?>" data-state="<?=$state?>" aria-label="<?=$label?>: <?=$state==='sold'?'vendido':($state==='pending'?'pendiente de pago':'disponible')?>" <?=$state==='free'?'':'disabled'?>><?=$label?></button>
    <?php endfor;?>
    </div>
    <?php if($s['pages']>1):?><nav class="ticket-pages" aria-label="Páginas de números"><?php if($s['page']>1):?><a class="pub-btn secondary" href="<?=h(pub_url('account',$params+['p'=>$s['page']-1]))?>">← Anterior</a><?php endif;?><span>Página <?=$s['page']?> de <?=$s['pages']?> · <?=$s['start']?>–<?=$s['end']?></span><?php if($s['page']<$s['pages']):?><a class="pub-btn secondary" href="<?=h(pub_url('account',$params+['p'=>$s['page']+1]))?>">Siguiente →</a><?php endif;?></nav><?php endif;?>
    <noscript><p class="user-sub">Activa JavaScript para seleccionar números y actualizar la disponibilidad automáticamente.</p></noscript>
</section>
<dialog class="user-raffle-dialog ticket-buy-dialog" id="ticket-buy" aria-labelledby="ticket-buy-title">
    <div class="user-dialog-head"><h2 id="ticket-buy-title">¿Comprar este número?</h2><form method="dialog"><button class="user-dialog-close" aria-label="Cerrar" autofocus>×</button></form></div>
    <div class="user-dialog-body"><p><?=h($s['title'])?></p><strong class="ticket-selected" data-ticket-selected>0001</strong><dl class="user-raffle-facts"><div><dt>Valor del boleto</dt><dd data-ticket-price><?=h($s['price_label'])?></dd></div><div><dt>Saldo disponible</dt><dd><?=$walletTotals!==null?money($walletTotals['balance']):'No disponible'?></dd></div></dl><p class="ticket-buy-note" data-ticket-buy-note role="status">La compra todavía no está habilitada. No se reservará el número ni se descontará saldo.</p></div>
    <div class="user-dialog-foot"><form method="dialog"><button class="pub-btn secondary">Cancelar</button></form><button class="pub-btn primary" type="button" disabled>Comprar</button></div>
</dialog>
<script defer src="usuario/tickets.js?v=<?=h(SW_VERSION)?>"></script>
<?php endif;?>
