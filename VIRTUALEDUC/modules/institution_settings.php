<?php
declare(strict_types=1);
if (!defined('VE_VERSION')) { http_response_code(404); exit; }
require_role($u,'admin');
$settings=institution_settings();
?>
<section class="ve-institution-form">
  <h1>Configuración institucional</h1>
  <p class="muted">Personaliza la identidad y los datos de contacto de la plataforma.</p>
  <?php if(!$settings['configured']):?><div class="notice error">Importa <code>migrations/0.1.10.sql</code> en phpMyAdmin para habilitar la configuración.</div><?php else: ?>
  <form method="post" enctype="multipart/form-data">
    <?php action('institution_save'); ?>
    <div class="ve-institution-logo-field">
      <?php if(institution_logo_file($settings['logo_path'])):?><img class="ve-logo-preview" src="<?=h(institution_logo_url($settings))?>" alt="Logo actual"><?php else:?><span class="ve-logo-preview ve-brand-mark">VE</span><?php endif;?>
      <div><label>Logo o icono institucional<input type="file" name="logo" accept="image/png,image/jpeg,image/webp"></label><small class="muted">PNG, JPG o WebP · máximo 2 MB · hasta 4096 × 4096 px</small><?php if($settings['logo_path']):?><label class="ve-remove-logo"><input type="checkbox" name="remove_logo" value="1"> Eliminar logo actual (si no seleccionas uno nuevo)</label><?php endif;?></div>
    </div>
    <label>Nombre de la institución<input name="institution_name" required maxlength="180" value="<?=h($settings['institution_name'])?>"></label>
    <label>Subtítulo<input name="institution_subtitle" maxlength="180" value="<?=h($settings['institution_subtitle'])?>" placeholder="Plataforma académica institucional"></label>
    <div class="ve-institution-fields">
      <label>Teléfono<input type="tel" name="institutional_phone" maxlength="50" value="<?=h($settings['institutional_phone'])?>" placeholder="02 000 0000"></label>
      <label>Correo institucional<input type="email" name="institutional_email" maxlength="190" value="<?=h($settings['institutional_email'])?>" placeholder="contacto@institucion.edu.ec"></label>
    </div>
    <label>Periodo activo<input name="active_period" maxlength="50" value="<?=h($settings['active_period'])?>" placeholder="2026-2027"></label>
    <button type="submit">Guardar configuración</button>
  </form><?php endif; ?>
</section>
