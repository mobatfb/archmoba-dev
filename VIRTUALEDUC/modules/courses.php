<?php
declare(strict_types=1);
if (!defined('VE_VERSION')) { http_response_code(404); exit; }
?>
<div class="ve-section-head"><h1><?=$u['role']==='student'?'Mis capacitaciones':'Cursos disponibles'?></h1><?php if($u['role']!=='student') creation_dialog($u,'course'); ?></div>
      <div class="grid"><?php foreach($courses as $x):?><article><span class="tag"><?=$x['published']?'Publicado':'Borrador'?></span><h3 class="ve-card-title" style="margin-top:12px"><?=h($x['title'])?></h3><p class="ve-course-text"><?=h($x['description'])?></p><a class="btn" href="?course=<?=h($x['id'])?>">Abrir curso</a></article><?php endforeach;?></div><?php if(!$courses):?><p class="muted">Todavía no hay cursos disponibles.</p><?php endif;?>
