<?php
declare(strict_types=1);
if(!defined('SW_APP')||!SW_PUBLIC){http_response_code(404);exit;}
// Public explanation only: the recorded rules and evidence remain unchanged.
function pub_draw_conditions(array $r,bool $link=true): void {
    $shared=$r['participation_mode']==='compartido';
    $physical=$r['type']==='producto';
    $date=$r['close_mode']==='fecha';
    ?>
    <section class="draw-transparency" aria-label="Transparencia y condiciones del sorteo">
        <h3>Transparencia y condiciones del sorteo</h3>
        <p>El número se selecciona automáticamente al activar el sorteo, antes de iniciar la venta, mediante un generador aleatorio seguro. El resultado se guarda en un archivo protegido con contraseña, que se publica antes de aceptar participaciones. La contraseña se revela al finalizar.</p>
        <p>Conserva el archivo original y su código de verificación antes de participar. Podrás comprobar que el archivo no ha cambiado. Esta comprobación no certifica de forma independiente cómo se eligió el número ni impide que quien controla el servidor pueda conocerlo anticipadamente.</p>
        <h4>Condiciones de participación y premiación</h4>
        <ul>
            <li><strong>Cierre:</strong> <?=h(draw_close_label($r))?>.</li>
            <?php if($shared):?>
                <li>Varias cuentas pueden adquirir el mismo número. Cada cuenta puede adquirirlo una sola vez y elegir otros números distintos.</li>
                <?php if($physical):?>
                    <li>Si una sola cuenta tiene una participación pagada del número seleccionado, recibe el producto. Si hay varias, se reparten su equivalente de <strong><?=money($r['prize_cents'])?></strong> en partes iguales, con ajuste al centavo.</li>
                <?php else:?>
                    <li>El premio de <strong><?=money($r['prize_cents'])?></strong> se reparte en partes iguales entre las cuentas que tengan una participación pagada del número seleccionado, con ajuste al centavo. Si hay una sola, recibe el importe completo.</li>
                <?php endif;?>
            <?php else:?>
                <li>Cada número puede ser adquirido por una única cuenta. Si se cumplen las condiciones de cierre y premiación, quien tenga el número seleccionado y pagado recibe <?=$physical?'el producto':'el premio completo de '.money($r['prize_cents'])?>.</li>
            <?php endif;?>
            <li>Solo participan en la premiación los boletos pagados. Si nadie ha pagado el número seleccionado, no se elige otro número: se registran las devoluciones de los boletos pagados, pendientes de revisión.</li>
            <?php if(!$shared&&$date):?><li>Si llega la fecha de cierre sin que todos los números estén vendidos y pagados, no se entrega el premio y se registran las devoluciones de los boletos pagados, pendientes de revisión.</li><?php endif;?>
            <li>Las entregas de premios y devoluciones requieren gestión posterior; no se realizan transferencias automáticas.</li>
        </ul>
        <?php if($link):?><a class="draw-verify-link" href="<?=h(pub_url('evidence',['id'=>$r['id']]))?>">Consultar archivo y código de verificación →</a><?php endif;?>
    </section>
    <?php
}
function pub_draw_overview(): void { ?>
<section class="public-wrap" id="transparencia">
    <article class="draw-transparency draw-transparency-home">
        <h2>Transparencia y condiciones del sorteo</h2>
        <p>En los sorteos con evidencia publicada, el número se selecciona automáticamente antes de iniciar la venta. El resultado queda guardado en un archivo protegido que puedes descargar junto con su código de verificación. Al finalizar, se publica la contraseña del archivo.</p>
        <p>El código permite comprobar que el archivo se mantiene sin cambios; no es una certificación independiente de la imparcialidad de la selección ni garantiza que el operador no pueda conocer el resultado de antemano. Consulta las condiciones de participación, cierre, premios y devoluciones de cada sorteo antes de participar.</p>
        <a class="pub-btn secondary" href="<?=h(pub_url('results'))?>">Consultar sorteos y resultados →</a>
    </article>
</section>
<?php }
