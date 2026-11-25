<?php
if (!defined('VE_VERSION')) { http_response_code(404); exit; }
$editingCourse=$courseEdit??null;
?>
<div class="ve-course-fields">
  <label>Modalidad<select name="modalidad" required><?php if($editingCourse && !isset(course_modalities()[$editingCourse['modality']??''])):?><option value="" selected>Seleccionar</option><?php endif;?><?php foreach(course_modalities() as $key=>$label):?><option value="<?=h($key)?>" <?=($editingCourse['modality']??null)===$key?'selected':''?>><?=h($label)?></option><?php endforeach;?></select></label>
  <label>Duración (horas)<input type="number" name="duracion" min="0.01" max="10000" step="0.01" required placeholder="Ej. 20" value="<?=h($editingCourse['duration_hours']??'')?>"></label>
  <label>Nivel<select name="nivel" required><?php if($editingCourse && !isset(course_levels()[$editingCourse['level']??''])):?><option value="" selected>Seleccionar</option><?php endif;?><?php foreach(course_levels() as $key=>$label):?><option value="<?=h($key)?>" <?=($editingCourse['level']??null)===$key?'selected':''?>><?=h($label)?></option><?php endforeach;?></select></label>
  <label>Período<input name="periodo" required maxlength="50" value="<?=h($editingCourse['period']??institution_settings()['active_period'])?>" placeholder="Ej. <?=h(date('Y'))?>"></label>
</div>
<?php $selectedAccess=course_access_model($editingCourse??[]); ?>
<fieldset class="ve-access-fields" data-ve-course-access>
  <legend>Modelo de acceso y certificación</legend>
  <label>Modelo<select name="modelo_acceso" required data-ve-access-model><?php foreach(course_access_models() as $key=>$label):?><option value="<?=h($key)?>" <?=$selectedAccess===$key?'selected':''?>><?=h($label)?></option><?php endforeach;?></select></label>
  <p class="muted ve-access-description" data-ve-access-description aria-live="polite"><?=h(course_access_summary($editingCourse??[]))?></p>
  <div data-ve-access-price><label><span data-ve-price-label><?=$selectedAccess==='free_paid_certificate'?'Valor del certificado (USD)':'Valor del curso con certificado (USD)'?></span><input type="number" name="valor" min="0" max="99999999.99" step="0.01" inputmode="decimal" placeholder="Ej. 25.00" value="<?=h($selectedAccess==='free'?'':($editingCourse['access_price']??''))?>"></label></div>
  <p class="muted ve-access-note">El cobro y la emisión de certificados se habilitarán en una próxima etapa. Mientras no exista un sistema de pagos, los estudiantes no podrán abrir el contenido de los cursos de pago.</p>
</fieldset>
<label>Miniatura (opcional)<input type="file" name="miniatura" accept="image/jpeg,image/png,image/webp"></label>
<p class="muted">JPG, PNG o WebP de hasta 5 MB. <?=$editingCourse?'Deja el archivo vacío para conservar la portada actual.':'Si no seleccionas una imagen, se asignará una de tres portadas automáticamente.'?></p>
<?php if($editingCourse):?><label class="ve-cover-restore"><input type="checkbox" name="restore_default" value="1"> Usar una portada predeterminada al azar</label><?php endif;?>
