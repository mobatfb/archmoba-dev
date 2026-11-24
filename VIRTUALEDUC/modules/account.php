<?php
declare(strict_types=1);
if (!defined('VE_VERSION')) { http_response_code(404); exit; }
?>
<section class="ve-form"><h1>Mi cuenta</h1><?php require __DIR__.'/profile_photo.php'; ?><hr><h2 id="ve-password">Cambiar mi contraseña</h2><?php $passwordInDialog=false; require __DIR__.'/password_form.php'; ?></section>
