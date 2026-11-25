<?php
declare(strict_types=1);
if (!defined('VE_VERSION')) { http_response_code(404); exit; }
?>
<div class="ve-section-head"><h1><?=$u['role']==='student'?'Mis cursos':'Cursos disponibles'?></h1><?php if($u['role']!=='student') creation_dialog($u,'course'); ?></div>
<div class="grid ve-course-grid"><?php foreach($courses as $x):?><article class="ve-course-card"><a href="?course=<?=h($x['id'])?>"><img src="<?=h(course_cover_url($x))?>" loading="lazy" decoding="async" width="720" height="405" alt="Portada del curso"></a><div class="ve-course-card-body"><span class="tag"><?=$x['published']?'Publicado':'Borrador'?></span><h3 class="ve-card-title"><?=h($x['title'])?></h3><p class="ve-course-text"><?=h($x['description'])?></p><dl class="ve-course-card-meta"><?php foreach(course_metadata_labels($x) as $label=>$value):?><div><dt><?=h($label)?></dt><dd><?=h($value)?></dd></div><?php endforeach;?></dl><div class="ve-course-card-actions"><a class="btn" href="?course=<?=h($x['id'])?>">Abrir curso</a><?php if(course_can_edit($u,$x)):?><a class="btn ve-quiet" href="?course=<?=h($x['id'])?>&amp;edit=1">Editar</a><?php endif;?></div></div></article><?php endforeach;?></div>
<?php if(!$courses):?><p class="muted">Todavía no hay cursos disponibles.</p><?php endif;?>
