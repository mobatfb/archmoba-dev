<?php
declare(strict_types=1);
if (!defined('VE_VERSION')) { http_response_code(404); exit; }
?>
<dialog class="ve-dialog" id="ve-profile-dialog" aria-labelledby="ve-profile-title">
  <div class="ve-dialog-head"><h2 id="ve-profile-title">Mi perfil</h2><button type="button" class="ve-quiet" data-ve-close aria-label="Cerrar">×</button></div>
  <div data-ve-profile-pane="profile">
    <?php require __DIR__.'/profile_photo.php'; ?>
    <div class="ve-dialog-actions"><button type="button" data-ve-profile-password>Cambiar contraseña</button><button type="button" class="ve-quiet" data-ve-close>Cerrar</button></div>
  </div>
  <div data-ve-profile-pane="password" hidden>
    <?php $passwordInDialog=true; require __DIR__.'/password_form.php'; $passwordInDialog=false; ?>
  </div>
</dialog>
