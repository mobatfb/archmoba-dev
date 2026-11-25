<?php
if (!defined('VE_VERSION')) { http_response_code(404); exit; }
?>
<div class="ve-course-fields">
  <label>Modalidad<select name="modalidad" required><?php foreach(course_modalities() as $key=>$label):?><option value="<?=h($key)?>"><?=h($label)?></option><?php endforeach;?></select></label>
  <label>Duración (horas)<input type="number" name="duracion" min="0.01" max="10000" step="0.01" required placeholder="Ej. 20"></label>
  <label>Nivel<select name="nivel" required><?php foreach(course_levels() as $key=>$label):?><option value="<?=h($key)?>"><?=h($label)?></option><?php endforeach;?></select></label>
  <label>Período<input name="periodo" required maxlength="50" value="<?=h(institution_settings()['active_period'])?>" placeholder="Ej. <?=h(date('Y'))?>"></label>
</div>
<label>Miniatura (opcional)<input type="file" name="miniatura" accept="image/jpeg,image/png,image/webp"></label>
<p class="muted">JPG, PNG o WebP de hasta 5 MB. Si no seleccionas una imagen, se asignará una de tres portadas automáticamente.</p>
