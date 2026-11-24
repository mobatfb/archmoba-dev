<?php
declare(strict_types=1);
if (!defined('VE_VERSION')) { http_response_code(404); exit; }
?>
<section class="auth"><h1><?=$installed?'Iniciar sesión':'Instalación pendiente'?></h1><p class="muted">Tu espacio de aprendizaje en línea.</p><?php if($installed):?><form method="post"><?php action('login');?><label>Usuario o correo electrónico<input type="text" name="email" required autocomplete="username"></label><label>Contraseña<input type="password" name="password" required autocomplete="current-password"></label><button>Ingresar</button></form><?php else:?><p>Importa el SQL de creación del administrador en phpMyAdmin y vuelve a cargar esta página.</p><?php endif;?></section>
