<?php
/**
 * SGA UNEDID - diagnóstico del correo saliente (V1.5.3).
 * Solo superadministrador autenticado. No publica claves ni tokens.
 * Eliminar este archivo del servidor despues de resolver la incidencia.
 */
require_once __DIR__ . '/lib/funciones.php';
exigirSuperadmin();
require_once __DIR__ . '/lib/sga_recuperacion.php';
require_once __DIR__ . '/lib/sga_smtp.php';
sgaResetHeaderSeguro();

if (empty($_SESSION['sga_diag_csrf'])) {
    $_SESSION['sga_diag_csrf'] = bin2hex(random_bytes(32));
}

$estado = [];
$config = [];
$alertas = [];
$resultado = '';
$claseResultado = 'notice';

function sgaDiagFila(string $etiqueta, bool $ok, string $detalle): array {
    return ['etiqueta' => $etiqueta, 'ok' => $ok, 'detalle' => $detalle];
}

function sgaDiagErrorVisible(Throwable $error): string {
    $m = $error->getMessage();
    if (str_contains($m, 'Configuracion SMTP incompleta')) {
        return 'La configuracion SMTP no esta completa. Comprueba la contraseña del buzon en config/recuperacion.php.';
    }
    if (preg_match('/operacion: (535|534|530|538)\\b/', $m, $coincide)) {
        return 'El servidor rechazo la autenticacion SMTP (codigo '. $coincide[1].'). Revisa el usuario y la contraseña del correo.';
    }
    if (preg_match('/operacion: (550|551|552|553|554)\\b/', $m, $coincide)) {
        return 'El servidor SMTP rechazo el mensaje o el destinatario (codigo '. $coincide[1].'). Revisa la direccion de prueba y las restricciones del proveedor.';
    }
    if (preg_match('/operacion: ([0-9]{3})\\b/', $m, $coincide)) {
        return 'El servidor SMTP no acepto una operacion (codigo '. $coincide[1].'). Revisa el registro de correo de cPanel.';
    }
    if (str_contains($m, 'No se pudo conectar al servidor SMTP')) {
        return 'No se pudo conectar al servidor SMTP. Revisa que el hosting permita conexiones al puerto 465 y que el certificado SSL del servidor sea valido.';
    }
    if (str_contains($m, 'Tiempo SMTP agotado')) {
        return 'El servidor SMTP no respondio a tiempo. Comprueba la conectividad y los bloqueos de puerto.';
    }
    if (str_contains($m, 'servidor SMTP no admite autenticacion') || str_contains($m, 'no admite autenticacion compatible')) {
        return 'El servidor no anuncia un metodo de autenticacion SMTP compatible.';
    }
    if (str_contains($m, 'TLS SMTP') || str_contains($m, 'STARTTLS')) {
        return 'No pudo completarse la conexion cifrada. Comprueba SSL/TLS y el certificado del servidor SMTP.';
    }
    return 'Error al enviar el mensaje. Revisa el registro de errores de PHP y el seguimiento de entregas de correo en cPanel.';
}

try {
    $config = sgaResetConfiguracion();
    $estado[] = sgaDiagFila('Archivo de configuracion', true, 'Se pudo leer config/recuperacion.php.');
} catch (Throwable $ex) {
    $estado[] = sgaDiagFila('Archivo de configuracion', false, 'No se pudo leer config/recuperacion.php.');
    $alertas[] = 'Revisa que config/recuperacion.php exista en la instalacion del SGA.';
}

$smtp = is_array($config['smtp'] ?? null) ? $config['smtp'] : [];
$host = (string)($smtp['host'] ?? '');
$puerto = (int)($smtp['port'] ?? 0);
$seguridad = (string)($smtp['security'] ?? '');
$usuario = (string)($smtp['username'] ?? '');
$remitente = (string)($smtp['from'] ?? '');
$clave = (string)($smtp['password'] ?? '');
$claveValida = trim($clave) !== '' && !preg_match('/^(CONTRASEÑA|PASSWORD|CAMBIAR|ESCRIBE|TU[_ ]?CLAVE)/iu',trim($clave));
$hostValido = $host === 'mail.aulaprofenathaly.com' && $puerto === 465 && $seguridad === 'ssl';
$usuarioValido = $usuario === 'info@aulaprofenathaly.com' && $remitente === $usuario;
$estado[] = sgaDiagFila('Servidor, puerto y cifrado', $hostValido,
    $hostValido ? 'mail.aulaprofenathaly.com · 465 · SSL/TLS' : 'Revisa host, port y security en config/recuperacion.php.');
$estado[] = sgaDiagFila('Remitente y autenticacion', $usuarioValido,
    $usuarioValido ? 'info@aulaprofenathaly.com' : 'Revisa username y from: deben coincidir con el buzon.');
$estado[] = sgaDiagFila('Contraseña del buzon', $claveValida,
    $claveValida ? 'Hay una contraseña configurada (su valor no se muestra).' : 'La contraseña SMTP esta vacia o es un texto de ejemplo.');
$estado[] = sgaDiagFila('Extension OpenSSL', extension_loaded('openssl') && function_exists('stream_socket_client'),
    extension_loaded('openssl') && function_exists('stream_socket_client') ? 'PHP puede abrir conexiones SMTP cifradas.' : 'Activa OpenSSL y sockets de PHP en el hosting.');
$baseValida = false;
try {
    $baseValida = sgaResetUrlBase($config) === 'https://sgaunedid.aulaprofenathaly.com';
} catch (Throwable $ex) {}
$estado[] = sgaDiagFila('Direccion publica del SGA', $baseValida,
    $baseValida ? 'https://sgaunedid.aulaprofenathaly.com' : 'Corrige app_url en config/recuperacion.php.');

$tablasOk = true;
foreach (['sga_recuperacion_claves', 'sga_recuperacion_solicitudes'] as $tabla) {
    $res = $conexion->query('SELECT 1 FROM '.$tabla.' LIMIT 0');
    if (!$res) $tablasOk = false;
    else $res->free();
}
$estado[] = sgaDiagFila('Tablas para recuperacion', $tablasOk,
    $tablasOk ? 'Las dos tablas estan disponibles.' : 'Falta alguna tabla. Ejecuta el SQL de la version 1.5 en la BD correcta.');

$destinatarioInicial = (string)(usuarioActual()['correo'] ?? '');
$destinatario = $destinatarioInicial;
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $destinatario = trim((string)($_POST['destinatario'] ?? ''));
    $token = (string)($_POST['csrf'] ?? '');
    if (!$token || !hash_equals((string)$_SESSION['sga_diag_csrf'], $token)) {
        $resultado = 'La sesion del formulario ha cambiado. Actualiza la pagina y vuelve a intentarlo.';
        $claseResultado = 'error';
    } elseif (strlen($destinatario) > 254 || !filter_var($destinatario, FILTER_VALIDATE_EMAIL)) {
        $resultado = 'Indica una direccion de correo valida para recibir la prueba.';
        $claseResultado = 'error';
    } else {
        // La comprobacion de cuenta utiliza la misma regla del recuperador.
        try {
            $coincidencias = 0;
            $correoNorm = strtolower($destinatario);
            $stmt = $conexion->prepare('SELECT COUNT(*) n FROM usuarios WHERE LOWER(TRIM(correo))=? AND activo=1');
            if (!$stmt) throw new RuntimeException('Consulta SQL no disponible.');
            $stmt->bind_param('s', $correoNorm);
            if (!$stmt->execute()) { $stmt->close(); throw new RuntimeException('Consulta SQL no disponible.'); }
            $coincidencias = (int)($stmt->get_result()->fetch_assoc()['n'] ?? 0);
            $stmt->close();
            if ($coincidencias === 1) {
                $alertas[] = 'El correo tiene exactamente una cuenta activa. Puede utilizar el recuperador.';
            } elseif ($coincidencias === 0) {
                $alertas[] = 'ATENCION: ese correo no corresponde a ninguna cuenta activa del SGA. No recibira el enlace de recuperacion, aunque SMTP funcione.';
            } else {
                $alertas[] = 'ATENCION: el correo figura en varias cuentas activas. El recuperador no enviara un enlace hasta corregir los duplicados.';
            }
        } catch (Throwable $ex) {
            $alertas[] = 'No se pudo validar si el correo esta registrado en la base de datos.';
        }

        $ahora = time();
        $ultimo = (int)($_SESSION['sga_diag_ultimo_envio'] ?? 0);
        $historial = array_values(array_filter(
            (array)($_SESSION['sga_diag_historial'] ?? []),
            static fn($t): bool => is_int($t) && $t > time() - 3600
        ));
        if ($ultimo && $ahora - $ultimo < 30) {
            $resultado = 'Por seguridad, espera 30 segundos antes de repetir una prueba.';
            $claseResultado = 'error';
        } elseif (count($historial) >= 8) {
            $resultado = 'Se alcanzo el limite de pruebas por hora para esta sesion.';
            $claseResultado = 'error';
        } elseif (!$claveValida || !$hostValido || !$usuarioValido || !extension_loaded('openssl')) {
            $resultado = 'La configuracion SMTP no esta lista. Corrige primero los puntos marcados en rojo.';
            $claseResultado = 'error';
        } else {
            $_SESSION['sga_diag_ultimo_envio'] = $ahora;
            $historial[] = $ahora;
            $_SESSION['sga_diag_historial'] = $historial;
            try {
                $transport = new SgaSmtp( (int)($smtp['timeout'] ?? 10) );
                $mensaje = "Este es un mensaje de prueba del Sistema de Gestion Academica UNEDID.\n\n"
                         . "Se ha podido autenticar el remitente SMTP y el servidor ha aceptado el envio.\n\n"
                         . "Si recibes este correo, la conexion SMTP funciona.\n";
                $transport->send($smtp, $destinatario, 'Prueba de correo - SGA UNEDID', $mensaje);
                $resultado = 'El servidor SMTP acepto el mensaje. Comprueba la bandeja de entrada, Spam y el seguimiento de entregas de cPanel.';
                $claseResultado = 'ok';
                error_log('[SGA UNEDID] Diagnostico SMTP: mensaje aceptado por el servidor.');
            } catch (Throwable $ex) {
                $resultado = sgaDiagErrorVisible($ex);
                $claseResultado = 'error';
                // No registrar correo, contraseña ni enlace de restablecimiento.
                error_log('[SGA UNEDID] Diagnostico SMTP: error durante prueba.');
            }
        }
    }
} elseif ($_SERVER['REQUEST_METHOD'] !== 'GET') {
    header('Allow: GET, POST');
    http_response_code(405);
    exit('Metodo no permitido');
}

$errores = count(array_filter($estado, static fn($it): bool => !$it['ok']));
?><!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Diagnostico SMTP · SGA UNEDID</title>
<style>
*{box-sizing:border-box}body{margin:0;padding:20px;background:#eef3f9;color:#132b4b;font-family:Arial,sans-serif;line-height:1.45}
main{max-width:770px;margin:20px auto;background:#fff;border-radius:18px;padding:24px 30px;box-shadow:0 10px 28px #0c2e5d17}
h1{font-size:24px;margin:0 0 9px;color:#002f6c}h2{font-size:19px;margin-top:24px}.muted{color:#5f6f84}
.row{display:flex;justify-content:space-between;align-items:flex-start;gap:14px;padding:12px 0;border-bottom:1px solid #e5edf5}.row:last-child{border:0}
.dot{display:inline-block;border-radius:20px;padding:3px 9px;font-size:12px;font-weight:700}.good{background:#ddf6e9;color:#11643c}.bad{background:#ffe7e4;color:#a62c2c}
.name{font-weight:700}.description{font-size:13px;color:#5f6f84;margin-top:4px;max-width:490px}
input{padding:12px;border:1px solid #b8c7d7;border-radius:9px;width:100%;font-size:16px}label{display:block;font-weight:700;margin:9px 0}
button{margin-top:12px;border:0;border-radius:9px;background:#002f6c;color:white;font-weight:700;padding:13px 20px;cursor:pointer}
a{color:#002f6c;font-weight:700}.notice{background:#e9f2fe;border-radius:10px;padding:13px;margin:13px 0}.error{background:#ffeded;border:1px solid #e3b0b0;color:#922527}.ok{background:#e1f5e9;border:1px solid #b3dfc7;color:#145b37}
footer{font-size:13px;color:#57677b;margin-top:22px;border-top:1px solid #e5edf5;padding-top:15px}
@media(max-width:600px){main{padding:18px}.row{flex-direction:column;gap:5px}}
</style></head><body><main>
<h1>Diagnostico del envio de correos</h1>
<p class="muted">Acceso exclusivo del superadministrador. Esta pagina no muestra ni almacena en pantalla la contraseña del correo.</p>
<p><strong>Estado:</strong> <?= $errores === 0 ? 'configuracion basica completa' : $errores.' elemento(s) requieren revision' ?></p>
<section aria-label="Comprobaciones">
<?php foreach($estado as $fila): ?>
<div class="row"><div><div class="name"><?=e($fila['etiqueta'])?></div><div class="description"><?=e($fila['detalle'])?></div></div>
<span class="dot <?=$fila['ok'] ? 'good' : 'bad'?>"><?=$fila['ok'] ? 'Correcto' : 'Revisar'?></span></div>
<?php endforeach; ?>
</section>
<h2>Enviar un correo de prueba</h2>
<p class="muted">Se envia un mensaje de prueba a la direccion indicada. Comprueba tambien si esta registrada en la base del SGA.</p>
<?php if($resultado):?><div class="notice <?=e($claseResultado)?>" role="status"><?=e($resultado)?></div><?php endif;?>
<?php foreach($alertas as $alerta):?><div class="notice" role="status"><?=e($alerta)?></div><?php endforeach;?>
<form method="post" action="<?=e(url('diagnostico_correo.php'))?>">
<input type="hidden" name="csrf" value="<?=e($_SESSION['sga_diag_csrf'])?>">
<label for="destinatario">Correo destinatario de la prueba</label>
<input id="destinatario" type="email" name="destinatario" required maxlength="254" value="<?=e($destinatario)?>" placeholder="correo@ejemplo.com">
<button type="submit">Enviar prueba SMTP</button>
</form>
<footer>El diagnostico no crea enlaces para restablecer contraseñas. La aceptacion SMTP no garantiza entrega en bandeja: revisa cPanel &gt; Seguimiento de entregas. Retira <code>diagnostico_correo.php</code> del servidor una vez resuelto el problema.<p><a href="<?=e(url('dashboard.php'))?>">Volver al SGA</a></p></footer>
</main></body></html>
