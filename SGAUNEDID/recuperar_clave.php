<?php
require_once __DIR__.'/lib/funciones.php';
require_once __DIR__.'/lib/sga_recuperacion.php';
sgaResetHeaderSeguro();
if (empty($_SESSION['sga_csrf_recuperar'])) $_SESSION['sga_csrf_recuperar'] = bin2hex(random_bytes(32));
$error = '';
$completado = false;
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $csrf = sgaResetTexto($_POST['csrf'] ?? '');
    $esperado = (string)($_SESSION['sga_csrf_recuperar'] ?? '');
    if ($csrf === '' || $esperado === '' || !hash_equals($esperado, $csrf)) {
        $error = 'El formulario venció. Actualiza la página e inténtalo nuevamente.';
    } else {
        // Mantener la cédula como texto: los ceros a la izquierda son significativos.
        $cedula = trim(sgaResetTexto($_POST['cedula'] ?? ''));
        if (!preg_match('/\A[0-9]{10}\z/D', $cedula)) {
            $error = 'Ingresa tu número de cédula de 10 dígitos.';
        } else {
            $completado = true;
            // La respuesta pública es idéntica para cuentas registradas y desconocidas.
            try {
                $config = sgaResetConfiguracion();
                // Se aplica el límite ANTES de consultar la cuenta; no se guarda la cédula en claro.
                // La tabla existente utiliza el nombre histórico correo_hash para este identificador.
                if (sgaResetPermitirSolicitud($conexion, $config, 'cedula:'.$cedula)) {
                    $usuario = sgaResetBuscarUsuarioPorCedula($conexion, $cedula);
                    if ($usuario !== null) {
                        $token = sgaResetCrearToken($conexion, $usuario['id']);
                        sgaResetEnviarCorreo($config, $usuario['correo'], $token);
                    }
                }
            } catch (Throwable $e) {
                // No exponer datos de cuentas, tokens, cédulas ni credenciales SMTP.
                error_log('[SGA UNEDID] Recuperación por cédula: solicitud no completada; revisar el servidor.');
            }
            $_SESSION['sga_csrf_recuperar'] = bin2hex(random_bytes(32));
        }
    }
} elseif ($_SERVER['REQUEST_METHOD'] !== 'GET') {
    header('Allow: GET, POST');http_response_code(405);exit('Método no permitido.');
}
?><!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Recuperar contraseña · SGA UNEDID</title>
<link rel="icon" type="image/jpeg" href="<?=e(url('assets/img/logo.jpeg'))?>"><style>
*{box-sizing:border-box}body{margin:0;min-height:100vh;display:grid;place-items:center;background:linear-gradient(135deg,#071d3b,#0d4f9d);font-family:Arial,Helvetica,sans-serif;color:#152b4c;padding:20px}.login{width:min(430px,100%);background:#fff;border-radius:18px;padding:30px;box-shadow:0 16px 44px #020e234d}.marca{display:flex;gap:12px;align-items:center}.marca img{width:55px;height:55px;object-fit:cover;border-radius:12px}.marca strong{font-size:16px}.intro{color:#586b82;line-height:1.55;margin:19px 0}h1{font-size:23px;margin:20px 0 8px}label{font-weight:700;font-size:14px}input{width:100%;margin-top:8px;padding:12px;font-size:16px;border:1px solid #b9c6d6;border-radius:9px}input:focus{outline:2px solid #2563a8;outline-offset:1px}.btn{margin-top:18px;border:0;background:#0d4f9d;color:#fff;font-weight:700;font-size:15px;width:100%;border-radius:10px;padding:13px;cursor:pointer}.btn:hover{background:#083b78}.enlace{display:block;text-align:center;margin-top:20px;text-decoration:none;font-weight:700;color:#0d4f9d}.enlace:hover{text-decoration:underline}.mensaje{margin-top:18px;padding:15px;border-radius:10px;background:#e8f5ef;border:1px solid #aed5c1;color:#15563f;line-height:1.5}.error{background:#fff0ee;border-color:#e6b0ab;color:#84251d}small{color:#66758a}
</style></head><body><main class="login">
<div class="marca"><img src="<?=e(url('assets/img/logo.jpeg'))?>" alt="Emblema UNEDID"><strong>Sistema de Gestión<br>Académica UNEDID</strong></div>
<h1>Recuperar contraseña</h1>
<?php if($completado): ?>
  <div class="mensaje" role="status">Si la cédula corresponde a una cuenta activa con correo registrado, recibirás un enlace para recuperar tu contraseña. Revisa también la carpeta de correo no deseado.</div>
<?php else: ?>
  <p class="intro">Ingresa tu número de cédula. Enviaremos automáticamente un enlace al correo electrónico registrado en tu cuenta.</p>
  <?php if($error): ?><div class="mensaje error" role="alert"><?=e($error)?></div><?php endif; ?>
  <form method="post" action="<?=e(url('recuperar_clave.php'))?>" autocomplete="on">
    <input type="hidden" name="csrf" value="<?=e($_SESSION['sga_csrf_recuperar'])?>">
    <label for="cedula">Número de cédula</label><input id="cedula" name="cedula" type="text" inputmode="numeric" pattern="[0-9]{10}" autocomplete="username" required minlength="10" maxlength="10" autofocus placeholder="Ej.: 0101234567" aria-describedby="ayudaCedula">
    <p id="ayudaCedula" class="intro" style="margin:8px 0 0"><small>Escribe los 10 dígitos sin espacios ni guiones. No necesitas ingresar tu correo.</small></p>
    <button type="submit" class="btn">Enviar enlace de recuperación</button>
  </form>
  <p class="intro"><small>Por seguridad, no indicaremos si existe una cuenta ni mostraremos su correo.</small></p>
<?php endif; ?>
<a class="enlace" href="<?=e(url('index.php'))?>">Volver al inicio de sesión</a>
</main></body></html>
