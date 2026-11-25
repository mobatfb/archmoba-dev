<?php
/** Cambio individual de contraseña. Compatible con cualquier rol autorizado. */
require_once __DIR__ . '/../../lib/funciones.php';
exigirLogin();

if (empty($_SESSION['csrf_cambiar_clave'])) {
    $_SESSION['csrf_cambiar_clave'] = bin2hex(random_bytes(32));
}

/** Acepta exclusivamente rutas internas; evita redirecciones externas. */
function retornoCambioClave(string $ruta): string {
    $seguro = url('dashboard.php');
    if ($ruta === '' || strlen($ruta) > 1200 || $ruta[0] !== '/' || str_starts_with($ruta, '//')) return $seguro;
    if (preg_match('/[\x00-\x1F\x7F\\]/', $ruta)) return $seguro;
    $datos = parse_url($ruta);
    if ($datos === false || isset($datos['host']) || isset($datos['scheme'])) return $seguro;
    $path = $datos['path'] ?? '';
    $base = rtrim(APP_URL, '/') . '/';
    if (!str_starts_with($path, $base) || str_contains($path, '..')) return $seguro;
    if (preg_match('/%(?:0[0-9a-f]|1[0-9a-f]|2[ef]|5c|7f)/i', $ruta)) return $seguro;
    return $ruta;
}

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $destino = retornoCambioClave((string)($_POST['retorno'] ?? ''));
    try {
        $csrf = (string)($_POST['csrf'] ?? '');
        $esperado = (string)($_SESSION['csrf_cambiar_clave'] ?? '');
        if ($esperado === '' || $csrf === '' || !hash_equals($esperado, $csrf)) {
            throw new RuntimeException('La sesión del formulario expiró. Vuelve a abrir Cambiar contraseña.');
        }

        $actual = (string)($_POST['clave_actual'] ?? '');
        $nueva = (string)($_POST['clave_nueva'] ?? '');
        $confirmacion = (string)($_POST['clave_confirmacion'] ?? '');
        if ($actual === '' || $nueva === '' || $confirmacion === '') {
            throw new RuntimeException('Completa los tres campos de contraseña.');
        }
        $caracteres = preg_match_all('/./us', $nueva);
        if ($caracteres === false || $caracteres < 8) {
            throw new RuntimeException('La nueva contraseña debe tener al menos 8 caracteres.');
        }
        if (strlen($nueva) > 72) {
            throw new RuntimeException('La contraseña es demasiado larga. Prueba una más corta.');
        }
        if (!hash_equals($nueva, $confirmacion)) {
            throw new RuntimeException('La nueva contraseña y su confirmación no coinciden.');
        }
        if (hash_equals($actual, $nueva)) {
            throw new RuntimeException('La nueva contraseña debe ser diferente de la actual.');
        }

        // Limite básico de intentos fallidos de la contraseña actual por sesión.
        $intentos = array_values(array_filter((array)($_SESSION['sga_clave_fallos'] ?? []),
            static fn($t) => is_int($t) && $t > time() - 900));
        $_SESSION['sga_clave_fallos'] = $intentos;
        if (count($intentos) >= 5) {
            throw new RuntimeException('Demasiados intentos. Inténtalo nuevamente en unos minutos.');
        }

        $uid = (int)$_SESSION['usuario_id'];
        $s = $conexion->prepare('SELECT clave, activo FROM usuarios WHERE id=? LIMIT 1');
        if (!$s) throw new RuntimeException('No fue posible verificar la cuenta.');
        $s->bind_param('i', $uid);
        $ok = $s->execute();
        $datos = $ok ? $s->get_result()->fetch_assoc() : null;
        $s->close();
        if (!$datos || (int)$datos['activo'] !== 1) {
            throw new RuntimeException('La cuenta no está disponible.');
        }
        if (!password_verify($actual, (string)$datos['clave'])) {
            $_SESSION['sga_clave_fallos'][] = time();
            registrarAuditoria('CHANGE_PASSWORD_FAIL', 'Autenticación', 'usuario', $uid,
                'Se rechazó cambio de contraseña: contraseña actual incorrecta.', $uid,
                null, null, 'fallo', $uid, null, 'advertencia');
            throw new RuntimeException('La contraseña actual no es correcta.');
        }

        $hash = password_hash($nueva, PASSWORD_DEFAULT);
        if (!$hash) throw new RuntimeException('No se pudo proteger la nueva contraseña.');
        // Garantiza que no se sobrescriba otra modificación hecha concurrentemente.
        $s = $conexion->prepare('UPDATE usuarios SET clave=? WHERE id=? AND clave=? AND activo=1');
        if (!$s) throw new RuntimeException('No fue posible guardar la contraseña.');
        $claveAnteriorHash = (string)$datos['clave'];
        $s->bind_param('sis', $hash, $uid, $claveAnteriorHash);
        $ok = $s->execute();
        $filas = $ok ? $s->affected_rows : 0;
        $s->close();
        if ($filas !== 1) throw new RuntimeException('No se pudo guardar el cambio. Vuelve a intentarlo.');

        // Una modificación personal invalida enlaces de recuperación pendientes.
        $s = $conexion->prepare('UPDATE sga_recuperacion_claves SET usado_en=NOW() WHERE usuario_id=? AND usado_en IS NULL');
        if ($s) {
            $s->bind_param('i', $uid);
            $s->execute();
            $s->close();
        }

        unset($_SESSION['sga_clave_fallos'], $_SESSION['csrf_cambiar_clave'], $_SESSION['sga_reabrir_cambio_clave']);
        session_regenerate_id(true);
        registrarAuditoria('CHANGE_PASSWORD', 'Autenticación', 'usuario', $uid,
            'El usuario actualizó su contraseña personal.', $uid,
            null, ['accion'=>'cambio_clave_personal'], 'exito', $uid, null, 'advertencia');
        flash('success', 'Tu contraseña se actualizó correctamente.');
    } catch (Throwable $error) {
        error_log('[SGA UNEDID] Cambio de contraseña no completado para usuario '.(int)($_SESSION['usuario_id']??0));
        // Mensajes de negocio controlados; los errores internos no se exponen.
        $mensajes = [
            'La sesión del formulario expiró. Vuelve a abrir Cambiar contraseña.',
            'Completa los tres campos de contraseña.',
            'La nueva contraseña debe tener al menos 8 caracteres.',
            'La contraseña es demasiado larga. Prueba una más corta.',
            'La nueva contraseña y su confirmación no coinciden.',
            'La nueva contraseña debe ser diferente de la actual.',
            'Demasiados intentos. Inténtalo nuevamente en unos minutos.',
            'La cuenta no está disponible.',
            'La contraseña actual no es correcta.',
            'No se pudo guardar el cambio. Vuelve a intentarlo.',
        ];
        $texto = in_array($error->getMessage(), $mensajes, true)
            ? $error->getMessage() : 'No se pudo actualizar tu contraseña. Inténtalo nuevamente.';
        flash('error', $texto);
        if (!str_ends_with((string)(parse_url($destino, PHP_URL_PATH) ?: ''), '/modulos/perfil/cambiar_clave.php')) {
            $_SESSION['sga_reabrir_cambio_clave'] = true;
        }
    }
    header('Location: '.$destino, true, 303);
    exit;
}

if ($_SERVER['REQUEST_METHOD'] !== 'GET') {
    header('Allow: GET, POST');
    http_response_code(405);
    exit('Método no permitido.');
}

// Alternativa accesible al modal para navegadores con JavaScript deshabilitado.
$tituloPagina = 'Cambiar contraseña';
$subtituloPagina = 'Actualiza tu clave personal de acceso al sistema.';
require __DIR__ . '/../../partials/header.php';
?>
<section class="card" style="max-width:520px">
  <h2>Seguridad de la cuenta</h2>
  <form method="post" action="<?=e(url('modulos/perfil/cambiar_clave.php'))?>" class="sga-password-form" style="display:grid;gap:14px">
    <input type="hidden" name="csrf" value="<?=e($_SESSION['csrf_cambiar_clave'])?>">
    <input type="hidden" name="retorno" value="<?=e(url('modulos/perfil/cambiar_clave.php'))?>">
    <label>Contraseña actual<input type="password" name="clave_actual" autocomplete="current-password" maxlength="128" required></label>
    <label>Nueva contraseña<input type="password" name="clave_nueva" autocomplete="new-password" minlength="8" maxlength="72" required></label>
    <label>Confirmar nueva contraseña<input type="password" name="clave_confirmacion" autocomplete="new-password" minlength="8" maxlength="72" required></label>
    <p class="mini-note">Utiliza al menos 8 caracteres y una contraseña diferente de la actual.</p>
    <div class="actions"><button type="submit" class="btn btn-primary">Guardar contraseña</button><a href="<?=e(url('dashboard.php'))?>" class="btn btn-secondary">Volver</a></div>
  </form>
</section>
<?php require __DIR__ . '/../../partials/footer.php'; ?>
