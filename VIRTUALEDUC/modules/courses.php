<?php
declare(strict_types=1);
if (!defined('VE_VERSION')) { http_response_code(404); exit; }
?>
<div class="ve-section-head"><h1><?=$u['role']==='student'?'Mis cursos':'Cursos disponibles'?></h1><?php if($u['role']!=='student') creation_dialog($u,'course'); ?></div>
<div class="grid ve-course-grid">
<?php foreach($courses as $x): $url='?course='.(string)$x['id']; ?>
  <article class="ve-course-card">
    <a class="ve-course-card-link" href="<?=h($url)?>" aria-label="Abrir curso: <?=h($x['title'])?>">
      <img class="ve-course-card-cover" src="<?=h(course_cover_url($x))?>" loading="lazy" decoding="async" width="720" height="405" alt="">
      <span class="ve-course-card-status"><?=$x['published']?'Publicado':'Borrador'?></span><div class="ve-course-card-body"><h3 class="ve-card-title" title="<?=h($x['title'])?>"><?=h($x['title'])?></h3><p class="ve-course-text" title="<?=h($x['description'])?>"><?=h($x['description'])?></p><dl class="ve-course-card-meta"><?php foreach(course_metadata_labels($x) as $label=>$value):?><div><dt><?=h($label)?></dt><dd title="<?=h($value)?>"><?=h($value)?></dd></div><?php endforeach;?></dl></div>
    </a>
    <?php if(course_can_edit($u,$x)):?>
      <a class="ve-course-pencil" href="<?=h($url.'&edit=1')?>" aria-label="Editar curso: <?=h($x['title'])?>" title="Editar curso"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="m16 3 5 5-13 13H3v-5L16 3Zm-3 3 5 5"/></svg></a>
    <?php endif;?>
  </article>
<?php endforeach;?>
</div>
<?php if(!$courses):?><p class="muted">Todavía no hay cursos disponibles.</p><?php endif;?>
