<?php
require_once __DIR__.'/lib/funciones.php';
require_once __DIR__.'/lib/sga_recuperacion.php';
sgaResetHeaderSeguro();
// El CSP del recuperador bloqueaba todo JavaScript (default-src 'none').
// Se permite exclusivamente ESTE script, mediante un nonce aleatorio por respuesta.
// No se usa unsafe-inline ni se relajan las demás directivas de seguridad.
$sgaOjoNonce = base64_encode(random_bytes(18));
header("Content-Security-Policy: default-src 'none'; "
    . "script-src 'nonce-{$sgaOjoNonce}'; "
    . "style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
    . "form-action 'self'; base-uri 'none'; frame-ancestors 'none'");
if (empty($_SESSION['sga_csrf_restablecer'])) $_SESSION['sga_csrf_restablecer'] = bin2hex(random_bytes(32));
$token = $_SERVER['REQUEST_METHOD'] === 'POST'
    ? sgaResetTexto($_POST['token'] ?? '')
    : sgaResetTexto($_GET['token'] ?? '');
$error = '';
$exito = false;
$vigente = false;
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    try {
        $csrf = sgaResetTexto($_POST['csrf'] ?? '');
        $esperado = (string)($_SESSION['sga_csrf_restablecer'] ?? '');
        if ($csrf === '' || $esperado === '' || !hash_equals($esperado,$csrf)) {
            throw new RuntimeException('El formulario venció. Vuelve a abrir el enlace de recuperación.');
        }
        $nueva = sgaResetTexto($_POST['clave_nueva'] ?? '');
        $confirma = sgaResetTexto($_POST['clave_confirmacion'] ?? '');
        if ($nueva === '' || $confirma === '') throw new RuntimeException('Completa los dos campos de contraseña.');
        if (!hash_equals($nueva,$confirma)) throw new RuntimeException('Las contraseñas no coinciden.');
        $usuarioId = sgaResetGuardarNuevaContrasena($conexion,$token,$nueva);
        $exito = true;
        unset($_SESSION['sga_csrf_restablecer']);
        // La contraseña nunca se envía por correo ni se registra en la auditoría.
        // La auditoría no debe atribuir la acción a otra cuenta abierta en este navegador.
        if (empty($_SESSION['usuario_id']) || (int)$_SESSION['usuario_id'] === $usuarioId) {
            registrarAuditoria('PASSWORD_RESET', 'Autenticación','usuario',$usuarioId,
                'El usuario restableció su contraseña con un enlace temporal.', $usuarioId,
                null,['modo'=>'correo'], 'exito',null,null,'advertencia');
        }
    } catch (Throwable $e) {
        $mensajes = [
            'El formulario venció. Vuelve a abrir el enlace de recuperación.',
            'Completa los dos campos de contraseña.',
            'Las contraseñas no coinciden.',
            'La nueva contraseña debe tener al menos 8 caracteres.',
            'La contraseña es demasiado larga. Prueba una más corta.',
            'La nueva contraseña debe ser diferente de la anterior.',
            'El enlace no es válido o ya venció.',
        ];
        $error = in_array($e->getMessage(), $mensajes, true)
            ? $e->getMessage()
            : 'No se pudo actualizar la contraseña. Solicita un nuevo enlace si el problema continúa.';
        error_log('[SGA UNEDID] Restablecimiento: intento no completado.');
    }
} elseif ($_SERVER['REQUEST_METHOD'] !== 'GET') {
    header('Allow: GET, POST');http_response_code(405);exit('Método no permitido.');
}
if (!$exito && sgaResetTokenHash($token) !== null) {
    try { $vigente = sgaResetEnlaceVigente($conexion,$token); }
    catch (Throwable $e) { error_log('[SGA UNEDID] Restablecimiento: verificación no disponible.'); }
}
?><!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Nueva contraseña · SGA UNEDID</title>
<link rel="icon" type="image/jpeg" href="<?=e(url('assets/img/logo.jpeg'))?>"><style>
*{box-sizing:border-box}body{margin:0;min-height:100vh;display:grid;place-items:center;background:linear-gradient(135deg,#071d3b,#0d4f9d);font-family:Arial,Helvetica,sans-serif;color:#152b4c;padding:20px}.login{width:min(430px,100%);background:#fff;border-radius:18px;padding:30px;box-shadow:0 16px 44px #020e234d}.marca{display:flex;gap:12px;align-items:center}.marca img{width:55px;height:55px;object-fit:cover;border-radius:12px}.marca strong{font-size:16px}.intro{color:#586b82;line-height:1.55;margin:19px 0}h1{font-size:23px;margin:20px 0 8px}label{display:block;font-weight:700;font-size:14px;margin-top:12px}input{width:100%;margin-top:8px;padding:12px;font-size:16px;border:1px solid #b9c6d6;border-radius:9px}input:focus{outline:2px solid #2563a8;outline-offset:1px}.btn{margin-top:20px;border:0;background:#0d4f9d;color:#fff;font-weight:700;font-size:15px;width:100%;border-radius:10px;padding:13px;cursor:pointer}.btn:hover{background:#083b78}.enlace{display:block;text-align:center;margin-top:20px;text-decoration:none;font-weight:700;color:#0d4f9d}.enlace:hover{text-decoration:underline}.mensaje{margin-top:18px;padding:15px;border-radius:10px;background:#e8f5ef;border:1px solid #aed5c1;color:#15563f;line-height:1.5}.error{background:#fff0ee;border-color:#e6b0ab;color:#84251d}small{color:#66758a}

/* Ojitos integrados en el restablecimiento: no dependen de archivos externos. */
.sga-pass-field{position:relative;width:100%;margin-top:8px}
.sga-pass-field>input{display:block;width:100%;margin-top:0;padding-right:54px}
.sga-password-eye{position:absolute;right:5px;top:50%;transform:translateY(-50%);display:flex;align-items:center;justify-content:center;width:42px;height:40px;border:0;border-radius:8px;background:transparent;color:#526780;cursor:pointer;touch-action:manipulation}
.sga-password-eye:hover{background:#edf3fa;color:#0d4f9d}
.sga-password-eye:focus-visible{outline:2px solid #0d4f9d;outline-offset:1px}
.sga-password-eye svg{width:22px;height:22px;pointer-events:none}
.sga-password-eye svg[hidden]{display:none!important}
</style></head><body><main class="login">
<div class="marca"><img src="<?=e(url('assets/img/logo.jpeg'))?>" alt="Emblema UNEDID"><strong>Sistema de Gestión<br>Académica UNEDID</strong></div>
<h1>Establecer nueva contraseña</h1>
<?php if($exito): ?>
  <div class="mensaje" role="status">¡Tu contraseña se actualizó correctamente! Ya puedes ingresar con la nueva contraseña.</div>
<?php elseif(!$vigente): ?>
  <div class="mensaje error" role="alert">Este enlace ya se utilizó, caducó o no es válido. Solicita uno nuevo para recuperar tu cuenta.</div>
  <a class="enlace" href="<?=e(url('recuperar_clave.php'))?>">Solicitar otro enlace</a>
<?php else: ?>
  <p class="intro">Crea una contraseña nueva para acceder a tu cuenta.</p>
  <?php if($error): ?><div class="mensaje error" role="alert"><?=e($error)?></div><?php endif; ?>
  <form method="post" action="<?=e(url('restablecer_clave.php'))?>">
    <input type="hidden" name="csrf" value="<?=e($_SESSION['sga_csrf_restablecer'])?>">
    <input type="hidden" name="token" value="<?=e($token)?>">
    <label for="clave_nueva">Nueva contraseña</label>
    <div class="sga-pass-field">
      <input type="password" id="clave_nueva" name="clave_nueva" autocomplete="new-password" minlength="8" maxlength="72" required autofocus>
      <button type="button" class="sga-password-eye" data-sga-eye-for="clave_nueva" aria-label="Mostrar contraseña" aria-controls="clave_nueva" aria-pressed="false" title="Mostrar contraseña"><svg class="sga-eye-show" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg><svg class="sga-eye-hide" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" hidden><path d="M3 3 21 21"/><path d="M10.6 5.1A10.7 10.7 0 0 1 12 5c6.4 0 10 7 10 7a16 16 0 0 1-3.1 3.7"/><path d="M6.4 6.4C3.6 8.2 2 12 2 12s3.6 7 10 7a10.6 10.6 0 0 0 4.3-.9"/><path d="M10.6 10.6a2 2 0 0 0 2.8 2.8"/></svg></button>
    </div>
    <label for="clave_confirmacion">Confirmar nueva contraseña</label>
    <div class="sga-pass-field">
      <input type="password" id="clave_confirmacion" name="clave_confirmacion" autocomplete="new-password" minlength="8" maxlength="72" required >
      <button type="button" class="sga-password-eye" data-sga-eye-for="clave_confirmacion" aria-label="Mostrar contraseña" aria-controls="clave_confirmacion" aria-pressed="false" title="Mostrar contraseña"><svg class="sga-eye-show" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg><svg class="sga-eye-hide" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" hidden><path d="M3 3 21 21"/><path d="M10.6 5.1A10.7 10.7 0 0 1 12 5c6.4 0 10 7 10 7a16 16 0 0 1-3.1 3.7"/><path d="M6.4 6.4C3.6 8.2 2 12 2 12s3.6 7 10 7a10.6 10.6 0 0 0 4.3-.9"/><path d="M10.6 10.6a2 2 0 0 0 2.8 2.8"/></svg></button>
    </div>
    <p class="intro"><small>Utiliza al menos 8 caracteres. No compartas tu contraseña.</small></p>
    <button type="submit" class="btn">Guardar nueva contraseña</button>
  </form>
<?php endif; ?>
<a class="enlace" href="<?=e(url('index.php'))?>">Volver al inicio de sesión</a>
</main><script nonce="<?=e($sgaOjoNonce)?>">
/* Ojitos locales: independientes del JavaScript compartido del SGA. */
(() => {
  'use strict';
  document.querySelectorAll('button[data-sga-eye-for]').forEach((button) => {
    const target = document.getElementById(button.getAttribute('data-sga-eye-for'));
    if (!target) return;
    button.addEventListener('click', () => {
      const visible = target.type === 'password';
      target.type = visible ? 'text' : 'password';
      const text = visible ? 'Ocultar contraseña' : 'Mostrar contraseña';
      button.setAttribute('aria-label', text);
      button.setAttribute('title', text);
      button.setAttribute('aria-pressed', visible ? 'true' : 'false');
      button.querySelector('.sga-eye-show').hidden = visible;
      button.querySelector('.sga-eye-hide').hidden = !visible;
      target.focus({ preventScroll: true });
    });
  });
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) return;
    document.querySelectorAll('button[data-sga-eye-for][aria-pressed="true"]').forEach((button) => button.click());
  });
})();
</script></body></html>
