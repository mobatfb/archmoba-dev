<?php if(!defined('SW_APP')||!SW_PUBLIC){http_response_code(404);exit;} $enabled=wallet_payments_enabled();$cfg=wallet_config();$min=max(100,(int)($cfg['min_cents']??100));$max=min(100000,(int)($cfg['max_cents']??5000));?>
<p class="user-sub">Añade saldo a tu cuenta de SORTEOWEB utilizando PayPhone.</p>
<div class="wallet-panel">
    <div class="wallet-provider"><span class="wallet-provider-icon" aria-hidden="true">P</span><div><h2>PayPhone</h2><p class="user-sub">Servicio de pago · USD</p></div><span class="wallet-tag"><?=$enabled?'Disponible':'En preparación'?></span></div>
    <?php if(!$walletAvailable):?><?php pub_message('El saldo de tu cuenta aún no está disponible. Inténtalo más tarde.','warning');?><?php elseif(!$enabled):?><?php pub_message('Las recargas aún no están disponibles. No se realizarán cobros.','info');?><?php endif;?>
    <form method="post" action="<?=h(pub_url('account',['tab'=>'recargar']))?>" class="wallet-form">
        <?=csrf()?><input type="hidden" name="action" value="wallet_recharge">
        <label for="wallet-amount">Monto a recargar (USD)</label><input type="number" id="wallet-amount" name="amount" min="<?=h(number_format($min/100,2,'.',''))?>" max="<?=h(number_format($max/100,2,'.',''))?>" step="0.01" value="5.00" required <?=$enabled?'':'disabled'?>>
        <p class="user-sub">El saldo se acreditará únicamente tras verificar un pago aprobado por PayPhone. No ingreses datos de tarjeta en SORTEOWEB.</p>
        <button class="pub-btn cta" type="submit" <?=$enabled?'':'disabled'?>><?=$enabled?'Continuar a PayPhone':'Recargas próximamente'?></button>
    </form>
    <a class="wallet-link" href="<?=h(pub_url('account',['tab'=>'transacciones']))?>">Ver mis transacciones →</a>
</div>
