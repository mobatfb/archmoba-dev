<?php
declare(strict_types=1);
if (!defined('VE_VERSION')) { http_response_code(404); exit; }
?>
<section class="ve-form"><h1>Mi cuenta</h1><?php require __DIR__.'/profile_photo.php'; ?><hr><h2 id="ve-password">Cambiar mi contraseña</h2><form method="post"><?php action('password');?><label>Contraseña actual<input type="password" name="old_password" required autocomplete="current-password"></label><label>Nueva contraseña (mínimo 8 caracteres)<input type="password" name="new_password" required minlength="8" maxlength="72" autocomplete="new-password"></label><label>Confirmar contraseña<input type="password" name="confirm_password" required minlength="8" maxlength="72" autocomplete="new-password"></label><p class="muted">Usa al menos 8 caracteres, una mayúscula, una minúscula, un número y un signo especial. Máximo 72 bytes.</p><button>Actualizar contraseña</button></form></section>
