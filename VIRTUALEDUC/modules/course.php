<?php
declare(strict_types=1);
if (!defined('VE_VERSION')) { http_response_code(404); exit; }
$isStudent=$u['role']==='student';
$modules=all('SELECT id,title,position FROM course_modules WHERE course_id=? ORDER BY position,id',[$c['id']]);
$teacher=one('SELECT name FROM users WHERE id=?',[$c['teacher_id']]);
$total=count($lessons); $completed=$isStudent?count(array_intersect(array_column($lessons,'id'),$done)):0;
$percent=$total?(int)round(100*$completed/$total):0;
$tabs=['content'=>'Contenido','activities'=>'Actividades','assessments'=>'Evaluaciones','grades'=>'Calificaciones','certificate'=>'Certificado'];
$tab=is_string($_GET['tab']??null)&&isset($tabs[$_GET['tab']])?$_GET['tab']:'content';
$empty=['activities'=>'Aún no hay actividades disponibles.','assessments'=>'Aún no hay evaluaciones disponibles.','grades'=>'Aún no hay calificaciones disponibles.','certificate'=>'Aún no hay certificados disponibles.'];
$courseUrl='?course='.(string)$c['id'];
?>
<div class="ve-course-breadcrumb"><a class="btn" href="?page=courses">← Cursos</a><span>Inicio / Cursos / <?=h($c['title'])?></span></div>
<div class="ve-course-hero">
  <img class="ve-course-cover" src="<?=h(course_cover_url($c))?>" alt="Portada del curso" width="720" height="405">
  <div class="ve-course-hero-copy"><h1><?=h($c['title'])?></h1><p><?=nl2br(h($c['description']))?></p>
  <div class="ve-course-metadata"><?php foreach(course_metadata_labels($c) as $label=>$value):?><div><small><?=h($label)?></small><strong><?=h($value)?></strong></div><?php endforeach;?></div></div>
</div>
<nav class="ve-course-tabs" aria-label="Secciones del curso"><?php foreach($tabs as $key=>$label):?><a href="<?=h($courseUrl.'&tab='.$key)?>" <?=$tab===$key?'aria-current="page"':''?>><?=h($label)?></a><?php endforeach;?></nav>
<?php if(!$isStudent):?><div class="ve-course-tools"><button type="button" data-ve-open="edit-course-dialog" aria-haspopup="dialog">Editar curso</button><span class="tag"><?=$c['published']?'Publicado':'Borrador'?></span><form method="post"><?php action('publish',(int)$c['id']);?><button class="ve-quiet"><?=$c['published']?'Ocultar curso':'Publicar curso'?></button></form><?php creation_dialog($u,'lesson','',(int)$c['id']); if(is_manager($u)) creation_dialog($u,'enroll','',(int)$c['id']); ?></div><?php endif;?>
<?php if(!$isStudent) require __DIR__.'/course_edit.php'; ?>
<div class="ve-course-layout">
  <section class="ve-course-panel">
  <?php if($tab==='content'):?><h2>Temario del curso</h2>
    <?php foreach($modules as $m): $items=array_values(array_filter($lessons,fn($l)=>(string)$l['module_id']===(string)$m['id'])); $doneCount=$isStudent?count(array_intersect(array_column($items,'id'),$done)):0; ?>
      <details class="ve-course-module" open><summary><span><?=h($m['title'])?></span><small><?=$isStudent?$doneCount.' / '.count($items):count($items).' lecciones'?></small></summary>
        <?php if(!$items):?><div class="ve-course-empty"><span class="ve-empty-icon" aria-hidden="true">+</span><strong>Este módulo está vacío</strong><p class="muted">Aún no se han añadido contenidos.</p></div><?php endif;?>
        <?php foreach($items as $l):?><details class="ve-course-lesson"><summary><span class="ve-lesson-symbol" aria-hidden="true">▤</span><span><?=h($l['title'])?></span><?php if($isStudent):?><small class="<?=in_array($l['id'],$done)?'ve-done':''?>"><?=in_array($l['id'],$done)?'✓ Completada':'Pendiente'?></small><?php endif;?></summary><div class="ve-lesson-body"><p class="lesson"><?=h($l['content'])?></p><?php if($isStudent&&!in_array($l['id'],$done)):?><form method="post"><?php action('complete',(int)$c['id']);?><input type="hidden" name="lesson_id" value="<?=h($l['id'])?>"><button>Marcar como completada</button></form><?php endif;?></div></details><?php endforeach;?>
      </details>
    <?php endforeach;?>
  <?php else:?><h2><?=h($tabs[$tab])?></h2><div class="ve-course-empty"><strong><?=h($empty[$tab])?></strong><p class="muted">Este apartado queda preparado para una próxima fase.</p></div><?php endif;?>
  </section>
  <aside class="ve-course-aside">
    <section class="ve-course-panel"><h2><?=$isStudent?'Mi progreso del curso':'Contenido del curso'?><?php if($isStudent):?><strong><?=$percent?> %</strong><?php endif;?></h2><?php if($isStudent):?><progress value="<?=$completed?>" max="<?=max(1,$total)?>" aria-label="Progreso del curso"></progress><p class="muted"><?=$completed?> de <?=$total?> lecciones completadas</p><?php else:?><p class="muted"><?=count($modules)?> módulo(s) · <?=$total?> lección(es)</p><?php endif;?></section>
    <section class="ve-course-panel"><h2>Responsable</h2><div class="ve-course-teacher"><span aria-hidden="true">♙</span><strong><?=h($teacher['name']??'Sin definir')?></strong></div></section>
    <section class="ve-course-panel"><h2>Recursos del curso</h2><p class="muted">Aún no hay recursos disponibles.</p></section>
  </aside>
</div>
