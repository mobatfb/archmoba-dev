<?php
declare(strict_types=1);
if (!defined('VE_VERSION')) { http_response_code(404); exit; }
require_role($u,'admin','subadmin','teacher','student');
?>
<div class="ve-profile-identity">
  <?php profile_avatar($u,'ve-profile-large'); ?>
  <div><strong><?=h($u['name'])?></strong><small>Usuario: <?=h($u['username'])?></small><small>Correo: <?=h($u['email'])?></small><small>Rol: <?=h(role_label($u['role']))?></small></div>
</div>
<h3>Foto de perfil</h3>
<p class="muted">Imagen privada, PNG de 120 × 120 píxeles. La imagen completa es privada. Los gestores autorizados pueden ver tu miniatura en los listados y buscadores; los miembros de un curso también pueden verla en el listado de participantes y en el responsable.</p>
<form method="post" enctype="multipart/form-data" class="ve-profile-upload">
  <?php action('profile_photo'); ?><input type="hidden" name="photo_action" value="save">
  <label>Seleccionar imagen (JPG, PNG, GIF o WebP, hasta 5 MB)<input type="file" name="photo" accept="image/jpeg,image/png,image/gif,image/webp" required></label>
  <button type="submit">Guardar foto</button>
</form>
<?php if(profile_has_photo($u)): ?>
<form method="post" class="ve-profile-remove"><?php action('profile_photo'); ?><input type="hidden" name="photo_action" value="remove"><button type="submit" class="ve-quiet">Eliminar foto y mostrar iniciales</button></form>
<?php else: ?><p class="muted">Sin foto de perfil; se muestran tus iniciales.</p><?php endif; ?>
