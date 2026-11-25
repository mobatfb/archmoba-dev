<?php
declare(strict_types=1);
if (!defined('VE_VERSION')) { http_response_code(404); exit; }
$isStudent=$u['role']==='student';
$canManage=course_can_edit($u,$c);
$modules=all('SELECT id,title,position FROM course_modules WHERE course_id=? ORDER BY position,id',[$c['id']]);
$teacher=one('SELECT id,name,first_names,last_names FROM users WHERE id=?',[$c['teacher_id']]);
$total=count($lessons); $completed=$isStudent?count(array_intersect(array_column($lessons,'id'),$done)):0;
$percent=$total?(int)round(100*$completed/$total):0;
$tabs=['content'=>'Contenido','activities'=>'Actividades','assessments'=>'Evaluaciones','grades'=>'Calificaciones','participants'=>'Participantes','certificate'=>'Certificado'];
$tab=is_string($_GET['tab']??null)&&isset($tabs[$_GET['tab']])?$_GET['tab']:'content';
$empty=['activities'=>'Aún no hay actividades disponibles.','assessments'=>'Aún no hay evaluaciones disponibles.','grades'=>'Aún no hay calificaciones disponibles.','certificate'=>'Aún no hay certificados disponibles.'];
$courseUrl='?course='.(string)$c['id'];
?>
<div class="ve-course-breadcrumb"><a class="btn" href="?page=courses">← Cursos</a><button type="button" class="ve-course-drawer-toggle" id="ve-course-drawer-toggle" aria-haspopup="dialog" aria-controls="ve-course-drawer" aria-expanded="false" hidden><svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M15 4v16m-7-8h4m-2-2 2 2-2 2"/></svg><span>Panel del curso</span></button><span>Inicio / Cursos / <?=h($c['title'])?></span></div>
<div class="ve-course-hero<?=$canManage?' ve-course-hero-has-status':''?>">
  <?php if($canManage):?><span class="ve-course-hero-status <?=$c['published']?'ve-status-published':'ve-status-draft'?>"><span aria-hidden="true"></span><?=$c['published']?'Publicado':'Borrador'?></span><?php endif;?>
  <img class="ve-course-cover" src="<?=h(course_cover_url($c))?>" alt="Portada del curso" width="720" height="405">
  <div class="ve-course-hero-copy"><h1><?=h($c['title'])?></h1><p><?=nl2br(h($c['description']))?></p>
  <div class="ve-course-metadata"><?php foreach(course_metadata_labels($c) as $label=>$value):?><div><small><?=h($label)?></small><strong><?=h($value)?></strong></div><?php endforeach;?></div></div>
</div>
<div class="ve-course-tabbar">
  <nav class="ve-course-tabs" aria-label="Secciones del curso"><?php foreach($tabs as $key=>$label):?><a href="<?=h($courseUrl.'&tab='.$key)?>" <?=$tab===$key?'aria-current="page"':''?>><?=h($label)?></a><?php endforeach;?></nav>
  <?php if($canManage):?><details class="ve-course-admin" data-ve-course-admin><summary class="btn"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="m9 3-.6 2.3-2 .9L4 5l-2 3 1.8 1.6v4.8L2 16l2 3 2.4-1.2 2 .9L9 21h6l.6-2.3 2-.9L20 19l2-3-1.8-1.6V9.6L22 8l-2-3-2.4 1.2-2-.9L15 3z"/></svg><span>Administrar</span><span aria-hidden="true">⌄</span></summary>
    <div class="ve-course-admin-menu"><button type="button" data-ve-open="edit-course-dialog" aria-haspopup="dialog">Editar curso</button><button type="button" data-ve-open="course-enroll-dialog" aria-haspopup="dialog">Crear matrícula</button><form method="post" class="ve-course-visibility"><?php action('publish',(int)$c['id']);?><button type="submit"><?=$c['published']?'Ocultar curso':'Publicar curso'?></button></form></div>
  </details><?php endif;?>
</div>
<?php if($canManage):?><div class="ve-course-tools"><?php creation_dialog($u,'lesson','',(int)$c['id']); ?></div><?php endif;?>
<?php if($canManage): require __DIR__.'/course_edit.php'; require __DIR__.'/course_enroll.php'; ?><script src="modules/course_admin.js?v=<?=h(VE_VERSION)?>" defer></script><?php endif;?>
<div class="ve-course-layout">
  <section class="ve-course-panel">
  <?php if($tab==='content'):?><h2>Temario del curso</h2>
    <?php foreach($modules as $m): $items=array_values(array_filter($lessons,fn($l)=>(string)$l['module_id']===(string)$m['id'])); $doneCount=$isStudent?count(array_intersect(array_column($items,'id'),$done)):0; ?>
      <details class="ve-course-module" open><summary><span><?=h($m['title'])?></span><small><?=$isStudent?$doneCount.' / '.count($items):count($items).' lecciones'?></small></summary>
        <?php if(!$items):?><div class="ve-course-empty"><span class="ve-empty-icon" aria-hidden="true">+</span><strong>Este módulo está vacío</strong><p class="muted">Aún no se han añadido contenidos.</p></div><?php endif;?>
        <?php foreach($items as $l):?><details class="ve-course-lesson"><summary><span class="ve-lesson-symbol" aria-hidden="true">▤</span><span><?=h($l['title'])?></span><?php if($isStudent):?><small class="<?=in_array($l['id'],$done)?'ve-done':''?>"><?=in_array($l['id'],$done)?'✓ Completada':'Pendiente'?></small><?php endif;?></summary><div class="ve-lesson-body"><p class="lesson"><?=h($l['content'])?></p><?php if($isStudent&&!in_array($l['id'],$done)):?><form method="post"><?php action('complete',(int)$c['id']);?><input type="hidden" name="lesson_id" value="<?=h($l['id'])?>"><button>Marcar como completada</button></form><?php endif;?></div></details><?php endforeach;?>
      </details>
    <?php endforeach;?>
  <?php elseif($tab==='participants'): require __DIR__.'/course_participants.php'; ?>
  <?php else:?><h2><?=h($tabs[$tab])?></h2><div class="ve-course-empty"><strong><?=h($empty[$tab])?></strong><p class="muted">Este apartado queda preparado para una próxima fase.</p></div><?php endif;?>
  </section>
  <aside class="ve-course-aside" id="ve-course-aside">
    <section class="ve-course-panel"><h2><?=$isStudent?'Mi progreso del curso':'Contenido del curso'?><?php if($isStudent):?><strong><?=$percent?> %</strong><?php endif;?></h2><?php if($isStudent):?><progress value="<?=$completed?>" max="<?=max(1,$total)?>" aria-label="Progreso del curso"></progress><p class="muted"><?=$completed?> de <?=$total?> lecciones completadas</p><?php else:?><p class="muted"><?=count($modules)?> módulo(s) · <?=$total?> lección(es)</p><?php endif;?></section>
    <section class="ve-course-panel"><h2>Responsable</h2><div class="ve-course-teacher"><?php if($teacher) profile_preview_avatar($teacher,'ve-course-teacher-avatar',(int)$c['id']); else { ?><span class="ve-course-teacher-avatar" aria-hidden="true">?</span><?php } ?><strong><?=h($teacher['name']??'Sin definir')?></strong></div></section>
    <section class="ve-course-panel"><h2>Recursos del curso</h2><p class="muted">Aún no hay recursos disponibles.</p></section>
  </aside>
</div>
<dialog id="ve-course-drawer" class="ve-course-drawer" aria-labelledby="ve-course-drawer-title">
  <div class="ve-course-drawer-head"><h2 id="ve-course-drawer-title">Panel del curso</h2><button type="button" id="ve-course-drawer-close" aria-label="Cerrar panel" autofocus><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18"/></svg></button></div>
  <div id="ve-course-drawer-body" class="ve-course-drawer-body"></div>
</dialog>
