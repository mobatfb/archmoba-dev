<?php
declare(strict_types=1);
if (!defined('SW_APP') || !SW_PUBLIC) { http_response_code(404); exit; }
function pub_footer(): void { ?><footer class="public-footer"><div><strong>SORTEOWEB</strong><span> · Sorteos en línea</span></div><div><a href="index.php?admin=1">Administración</a> <span>·</span> <small>v<?=h(SW_VERSION)?></small></div></footer></body></html><?php }
