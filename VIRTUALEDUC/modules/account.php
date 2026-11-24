<?php
declare(strict_types=1);
if (!defined('VE_VERSION')) { http_response_code(404); exit; }
?>
<section class="ve-form"><h1>Mi cuenta</h1><p><strong>Nombre:</strong> <?=h($u['name'])?></p><p><strong>Correo:</strong> <?=h($u['email'])?></p><p><strong>Rol:</strong> <?=h(role_label($u['role']))?></p><hr><h2>Cambiar mi contraseña</h2><form method="post"><?php action('password');?><label>Contraseña actual<input type="password" name="old_password" required autocomplete="current-password"></label><label>Nueva contraseña (mínimo 12 caracteres)<input type="password" name="new_password" required minlength="12" autocomplete="new-password"></label><label>Confirmar contraseña<input type="password" name="confirm_password" required minlength="12" autocomplete="new-password"></label><button>Actualizar contraseña</button></form></section>
