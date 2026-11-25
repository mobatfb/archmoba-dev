<?php
/** Lógica de recuperación del SGA. No mostrar correos, contraseñas ni tokens en errores o auditoría. */

function sgaResetConfiguracion(): array {
    $ruta = __DIR__ . '/../config/recuperacion.php';
    $datos = require $ruta;
    if (!is_array($datos)) throw new RuntimeException('Configuración de recuperación no disponible.');
    return $datos;
}

function sgaResetUrlBase(array $config): string {
    $url = trim((string)($config['app_url'] ?? ''));
    $partes = parse_url($url);
    if (!is_array($partes) || ($partes['scheme'] ?? '') !== 'https'
        || empty($partes['host']) || isset($partes['user']) || isset($partes['pass'])
        || isset($partes['query']) || isset($partes['fragment'])
        || !filter_var($url, FILTER_VALIDATE_URL)) {
        throw new RuntimeException('URL HTTPS del sistema no configurada.');
    }
    return rtrim($url, '/');
}

function sgaResetHeaderSeguro(): void {
    header('Cache-Control: no-store, no-cache, must-revalidate, private');
    header('Pragma: no-cache');
    header('Referrer-Policy: no-referrer');
    header('X-Content-Type-Options: nosniff');
    header('X-Frame-Options: DENY');
    header('X-Robots-Tag: noindex, nofollow');
    header("Content-Security-Policy: default-src 'none'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; form-action 'self'; base-uri 'none'; frame-ancestors 'none'");
}

function sgaResetTexto($dato): string {
    return is_string($dato) ? $dato : '';
}

function sgaResetPreparar(mysqli $conexion, string $sql): mysqli_stmt {
    $consulta = $conexion->prepare($sql);
    if (!$consulta) throw new RuntimeException('Consulta de recuperación no disponible.');
    return $consulta;
}

/** Los dos límites se verifican por servidor. No divulgar longitudes técnicas en el formulario. */
function sgaResetValidarContrasena(string $clave): ?string {
    $caracteres = preg_match_all('/./us', $clave);
    if ($caracteres === false || $caracteres < 8) {
        return 'La nueva contraseña debe tener al menos 8 caracteres.';
    }
    if (strlen($clave) > 72) {
        return 'La contraseña es demasiado larga. Prueba una más corta.';
    }
    return null;
}

function sgaResetTokenHash(string $token): ?string {
    if (!preg_match('/\A[0-9a-f]{64}\z/D', $token)) return null;
    return hash('sha256', hex2bin($token));
}

/** Evita identificar cuentas mediante la respuesta pública. Direcciones duplicadas no reciben enlaces. */
function sgaResetBuscarUsuario(mysqli $conexion, string $correo): ?int {
    $s = sgaResetPreparar($conexion,
        'SELECT id FROM usuarios WHERE LOWER(TRIM(correo))=? AND activo=1 LIMIT 2');
    $s->bind_param('s', $correo);
    if (!$s->execute()) { $s->close(); throw new RuntimeException('Error consultando el correo.'); }
    $encontrados = $s->get_result()->fetch_all(MYSQLI_ASSOC);
    $s->close();
    return count($encontrados) === 1 ? (int)$encontrados[0]['id'] : null;
}

/**
 * Busca el destinatario por la cédula exacta y no por el correo introducido.
 * Solo admite una cuenta activa y un correo que sea utilizable.
 * En ningún caso revela al visitante el correo o la existencia de la cuenta.
 */
function sgaResetBuscarUsuarioPorCedula(mysqli $conexion, string $cedula): ?array {
    if (!preg_match('/\A[0-9]{10}\z/D', $cedula)) return null;
    $s = sgaResetPreparar($conexion,
        'SELECT id,correo FROM usuarios WHERE cedula=? AND activo=1 LIMIT 2');
    $s->bind_param('s', $cedula);
    if (!$s->execute()) { $s->close(); throw new RuntimeException('Consulta de recuperación no disponible.'); }
    $encontrados = $s->get_result()->fetch_all(MYSQLI_ASSOC);
    $s->close();
    if (count($encontrados) !== 1) return null;
    $correo = trim((string)($encontrados[0]['correo'] ?? ''));
    if (strlen($correo) > 254 || !filter_var($correo, FILTER_VALIDATE_EMAIL)) return null;
    $id = (int)$encontrados[0]['id'];
    if ($id <= 0) return null;
    return ['id' => $id, 'correo' => $correo];
}

/** Limita peticiones por IP y por correo a través de la BD (también entre navegadores). */
function sgaResetPermitirSolicitud(mysqli $conexion, array $config, string $correo): bool {
    $secreto = (string)($config['rate_secret'] ?? '');
    if (strlen($secreto) < 32) throw new RuntimeException('Límite de solicitudes sin configurar.');
    // REMOTE_ADDR procede de la conexión, no de encabezados X-Forwarded-For del usuario.
    $ip = (string)($_SERVER['REMOTE_ADDR'] ?? 'desconocida');
    $ipHash = hash_hmac('sha256', $ip, $secreto);
    $correoHash = hash_hmac('sha256', $correo, $secreto);
    $s = sgaResetPreparar($conexion,
        'SELECT COUNT(*) n FROM sga_recuperacion_solicitudes WHERE ip_hash=? AND creado_en>DATE_SUB(NOW(),INTERVAL 1 HOUR)');
    $s->bind_param('s', $ipHash);
    if (!$s->execute()) { $s->close(); throw new RuntimeException('Control de solicitudes no disponible.'); }
    $porIp = (int)($s->get_result()->fetch_assoc()['n'] ?? 0);
    $s->close();
    if ($porIp >= 30) return false;
    $s = sgaResetPreparar($conexion,
        'SELECT COUNT(*) n FROM sga_recuperacion_solicitudes WHERE correo_hash=? AND creado_en>DATE_SUB(NOW(),INTERVAL 1 HOUR)');
    $s->bind_param('s', $correoHash);
    if (!$s->execute()) { $s->close(); throw new RuntimeException('Control de solicitudes no disponible.'); }
    $porCorreo = (int)($s->get_result()->fetch_assoc()['n'] ?? 0);
    $s->close();
    if ($porCorreo >= 3) return false;
    $s = sgaResetPreparar($conexion,
        'INSERT INTO sga_recuperacion_solicitudes (ip_hash,correo_hash) VALUES (?,?)');
    $s->bind_param('ss', $ipHash, $correoHash);
    $ok = $s->execute(); $s->close();
    if (!$ok) throw new RuntimeException('No fue posible registrar la solicitud.');
    // Mantenimiento liviano ocasional (cada ~100 solicitudes aceptadas).
    if (random_int(1,100) === 1) {
        $conexion->query('DELETE FROM sga_recuperacion_solicitudes WHERE creado_en<DATE_SUB(NOW(),INTERVAL 3 DAY)');
        $conexion->query('DELETE FROM sga_recuperacion_claves WHERE vence_en<DATE_SUB(NOW(),INTERVAL 3 DAY)');
    }
    return true;
}

/** Genera token de 256 bits. En SQL se guarda SOLO su huella criptográfica. */
function sgaResetCrearToken(mysqli $conexion, int $usuarioId): string {
    $token = bin2hex(random_bytes(32));
    $hash = hash('sha256', hex2bin($token));
    if (!$conexion->begin_transaction()) throw new RuntimeException('Error iniciando la solicitud.');
    try {
        $s = sgaResetPreparar($conexion,
            'UPDATE sga_recuperacion_claves SET usado_en=NOW() WHERE usuario_id=? AND usado_en IS NULL');
        $s->bind_param('i', $usuarioId);
        $ok = $s->execute(); $s->close();
        if (!$ok) throw new RuntimeException('No fue posible cerrar enlaces anteriores.');
        $s = sgaResetPreparar($conexion,
            'INSERT INTO sga_recuperacion_claves (usuario_id,token_hash,vence_en) VALUES (?,?,DATE_ADD(NOW(), INTERVAL 30 MINUTE))');
        $s->bind_param('is', $usuarioId, $hash);
        $ok = $s->execute(); $s->close();
        if (!$ok) throw new RuntimeException('No fue posible crear el enlace.');
        if (!$conexion->commit()) throw new RuntimeException('No fue posible confirmar el enlace.');
    } catch (Throwable $error) {
        $conexion->rollback();
        throw $error;
    }
    return $token;
}

function sgaResetEnviarCorreo(array $config, string $correo, string $token): void {
    require_once __DIR__ . '/sga_smtp.php';
    $base = sgaResetUrlBase($config);
    $enlace = $base.'/restablecer_clave.php?token='.rawurlencode($token);
    $mensaje = "Hola:\n\nRecibimos una solicitud para restablecer la contraseña de tu cuenta del Sistema de Gestión Académica UNEDID.\n\n"
        ."Abre este enlace para crear tu nueva contraseña:\n".$enlace."\n\n"
        ."El enlace caduca en 30 minutos y solo puede utilizarse una vez.\n\n"
        ."Si no solicitaste el cambio, ignora este mensaje. Tu contraseña actual seguirá siendo válida.\n\n"
        ."Sistema de Gestión Académica UNEDID\n";
    $mailer = new SgaSmtp((int)($config['smtp']['timeout'] ?? 10));
    $mailer->send((array)($config['smtp'] ?? []), $correo,
        'Recuperación de contraseña - SGA UNEDID', $mensaje);
}

/** Se comprueba únicamente el hash, vigencia, uso y estado del usuario. */
function sgaResetEnlaceVigente(mysqli $conexion, string $token): bool {
    $hash = sgaResetTokenHash($token);
    if ($hash === null) return false;
    $s = sgaResetPreparar($conexion,
        'SELECT 1 FROM sga_recuperacion_claves r JOIN usuarios u ON u.id=r.usuario_id '
        .'WHERE r.token_hash=? AND r.usado_en IS NULL AND r.vence_en>NOW() AND u.activo=1 LIMIT 1');
    $s->bind_param('s',$hash);
    if (!$s->execute()) { $s->close(); throw new RuntimeException('Verificación del enlace no disponible.'); }
    $vigente = (bool)$s->get_result()->fetch_row();
    $s->close();
    return $vigente;
}

/** Cambio atómico; consume el token y revoca otros enlaces del mismo usuario. */
function sgaResetGuardarNuevaContrasena(mysqli $conexion,string $token,string $nueva): int {
    $hashToken = sgaResetTokenHash($token);
    if ($hashToken === null) throw new RuntimeException('El enlace no es válido o ya venció.');
    if (($err = sgaResetValidarContrasena($nueva)) !== null) throw new RuntimeException($err);
    if (!$conexion->begin_transaction()) throw new RuntimeException('No se pudo iniciar la actualización.');
    try {
        $s = sgaResetPreparar($conexion,
            'SELECT r.usuario_id,u.clave FROM sga_recuperacion_claves r '
            .'JOIN usuarios u ON u.id=r.usuario_id '
            .'WHERE r.token_hash=? AND r.usado_en IS NULL AND r.vence_en>NOW() AND u.activo=1 '
            .'LIMIT 1 FOR UPDATE');
        $s->bind_param('s',$hashToken);
        $ok = $s->execute();
        $datos = $ok ? $s->get_result()->fetch_assoc() : null;
        $s->close();
        if (!$datos) throw new RuntimeException('El enlace no es válido o ya venció.');
        $id = (int)$datos['usuario_id'];
        if (password_verify($nueva,(string)$datos['clave'])) {
            throw new RuntimeException('La nueva contraseña debe ser diferente de la anterior.');
        }
        $hashNueva = password_hash($nueva,PASSWORD_DEFAULT);
        if (!$hashNueva) throw new RuntimeException('No fue posible crear una contraseña segura.');
        $s = sgaResetPreparar($conexion,
            'UPDATE usuarios SET clave=?, debe_cambiar_clave=0 WHERE id=? AND activo=1');
        $s->bind_param('si',$hashNueva,$id);
        $ok = $s->execute(); $afectados = $s->affected_rows; $s->close();
        if (!$ok || $afectados !== 1) throw new RuntimeException('No se pudo actualizar la contraseña.');
        $s = sgaResetPreparar($conexion,
            'UPDATE sga_recuperacion_claves SET usado_en=NOW() WHERE usuario_id=? AND usado_en IS NULL');
        $s->bind_param('i',$id);
        $ok = $s->execute(); $s->close();
        if (!$ok) throw new RuntimeException('No fue posible cerrar los enlaces utilizados.');
        if (!$conexion->commit()) throw new RuntimeException('No fue posible confirmar la actualización.');
        return $id;
    } catch (Throwable $error) {
        $conexion->rollback();
        throw $error;
    }
}
