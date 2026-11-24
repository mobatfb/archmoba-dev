<?php
declare(strict_types=1);
if (!defined('VE_VERSION')) { http_response_code(404); exit; }
?>
<section class="hero"><h1>Hola, <?=h($u['name'])?></h1><p>Bienvenido a tu campus virtual. Selecciona una sección del menú para comenzar.</p><span><?=h(role_label($u['role']))?></span></section>
      <div class="ve-stats"><div class="ve-stat">Cursos<strong><?=count($courses)?></strong></div>
      <div class="ve-stat">Cursos publicados<strong><?=count(array_filter($courses,fn($c)=>(int)$c['published']===1))?></strong></div>
      <?php if(is_manager($u)):?><div class="ve-stat">Usuarios visibles<strong><?=count($users)?></strong></div><?php endif;?></div>
      <section><h2>Accesos rápidos</h2><div class="grid"><?php foreach(navigation_sections($u) as $items):foreach($items as $key=>$label):if($key!=='home'):?><a class="btn" href="?page=<?=h($key)?>"><?=h($label)?></a><?php endif;endforeach;endforeach;?></div></section>
