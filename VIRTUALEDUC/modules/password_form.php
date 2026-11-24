<?php
declare(strict_types=1);
if (!defined('VE_VERSION')) { http_response_code(404); exit; }
require_role($u,'admin','subadmin','teacher','student');
?>
<form method="post" data-ve-password-form>
  <?php action('password'); ?>
  <label>Contraseña actual<input type="password" name="old_password" required autocomplete="current-password"></label>
  <label>Nueva contraseña<input type="password" name="new_password" required minlength="8" maxlength="72" autocomplete="new-password"></label>
  <label>Confirmar contraseña<input type="password" name="confirm_password" required minlength="8" maxlength="72" autocomplete="new-password"></label>
  <p class="muted">Mínimo 8 caracteres, una mayúscula, una minúscula, un número y un signo especial. Máximo 72 bytes.</p>
  <div class="ve-dialog-actions">
    <?php if(!empty($passwordInDialog)): ?><button type="button" class="ve-quiet" data-ve-profile-back>Volver al perfil</button><?php endif; ?>
    <button type="submit">Actualizar contraseña</button>
  </div>
</form>
