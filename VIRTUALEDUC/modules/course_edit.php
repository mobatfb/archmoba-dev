<?php
declare(strict_types=1);
if (!defined('VE_VERSION')) { http_response_code(404); exit; }
if(!course_can_edit($u,$c)) return;
$owner=one('SELECT '.user_identity_columns().' FROM users WHERE id=?',[$c['teacher_id']]);
?>
<dialog class="ve-dialog" id="edit-course-dialog" aria-labelledby="edit-course-title" <?=($_GET['edit']??null)==='1'?'data-ve-edit-auto':''?>>
  <div class="ve-dialog-head"><h2 id="edit-course-title">Editar curso</h2><button type="button" class="ve-quiet" data-ve-close aria-label="Cerrar">×</button></div>
  <form method="post" enctype="multipart/form-data">
    <?php action('course_edit',(int)$c['id']); ?>
    <img class="ve-edit-cover" src="<?=h(course_cover_url($c))?>" width="160" height="90" alt="Portada actual">
    <label>Título<input name="titulo" required maxlength="180" value="<?=h($c['title'])?>"></label>
    <label>Descripción<textarea name="descripcion" required maxlength="20000"><?=h($c['description'])?></textarea></label>
    <label>Usuario responsable<input name="usuario_responsable" required maxlength="190" autocomplete="off" value="<?=h($owner['username']??'')?>" <?=is_manager($u)?'list="edit-course-responsibles"':'readonly'?>></label>
    <?php if(is_manager($u)):?><datalist id="edit-course-responsibles"><?php foreach(available_teachers($u) as $x):?><option value="<?=h($x['username'])?>" label="<?=h($x['name'])?>"></option><?php endforeach;?></datalist><?php endif;?>
    <?php $courseEdit=$c; require __DIR__.'/course_fields.php'; unset($courseEdit); ?>
    <div class="ve-dialog-actions"><button type="button" class="ve-quiet" data-ve-close>Cancelar</button><button type="submit">Guardar cambios</button></div>
  </form>
</dialog>
<script src="modules/course_edit.js?v=<?=h(VE_VERSION)?>" defer></script>
