<?php
/** Crea, reemplaza o elimina exclusivamente la foto del usuario logueado. */
require_once __DIR__ . '/../../lib/funciones.php';
require_once __DIR__ . '/../../lib/foto_perfil_privada.php';
exigirLogin();

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    header('Allow: POST');
    http_response_code(405);
    exit('Metodo no permitido.');
}

/** Volver solo a paginas internas del SGA (nunca a URLs externas). */
function sgaPerfilRetornoSeguro(string $pedido): string {
    $defecto = url('dashboard.php');
    if (strlen($pedido) > 1200 || $pedido === '' || $pedido[0] !== '/' || str_starts_with($pedido, '//')) return $defecto;
    if (preg_match('/[\x00-\x1F\x7F\\]/', $pedido)) return $defecto;
    $partes = parse_url($pedido);
    if (!is_array($partes) || isset($partes['host']) || isset($partes['scheme'])) return $defecto;
    $path = (string)($partes['path'] ?? '');
    if (!str_starts_with($path, rtrim(APP_URL, '/') . '/') || str_contains($path, '..')) return $defecto;
    if (preg_match('/%(?:0[0-9a-f]|1[0-9a-f]|2[ef]|5c|7f)/i', $pedido)) return $defecto;
    return $pedido;
}

$destino = sgaPerfilRetornoSeguro((string)($_POST['retorno'] ?? ''));
try {
    $actual = (string)($_SESSION['csrf_perfil_foto'] ?? '');
    $token = (string)($_POST['csrf'] ?? '');
    if ($actual === '' || $token === '' || !hash_equals($actual, $token)) {
        throw new RuntimeException('La sesion del formulario expiro. Abre nuevamente tu perfil.');
    }
    $usuario = usuarioActual();
    if (!$usuario || !sgaPerfilCedulaValida((string)$usuario['cedula'])) {
        throw new RuntimeException('La cedula de tu cuenta no permite guardar fotos.');
    }
    $accion = (string)($_POST['accion'] ?? '');
    if ($accion === 'eliminar') {
        $ruta = sgaPerfilRutaFoto($usuario);
        if ($ruta && is_file($ruta)) {
            if (is_link($ruta) || !@unlink($ruta)) {
                throw new RuntimeException('No se pudo eliminar la foto actual.');
            }
        }
        registrarAuditoria('REMOVE_PROFILE_PHOTO', 'Perfil', 'usuario', (int)$usuario['id'],
            'El usuario elimino su foto privada de perfil.', (int)$usuario['id']);
        flash('success', 'Foto eliminada. Tu avatar vuelve a mostrar las iniciales.');
        $_SESSION['sga_perfil_feedback']=['tipo'=>'success','mensaje'=>'Foto eliminada. Tu avatar vuelve a mostrar las iniciales.'];
    } elseif ($accion === 'guardar') {
        $foto = $_FILES['foto'] ?? null;
        if (!is_array($foto) || is_array($foto['tmp_name'] ?? null)) {
            throw new RuntimeException('Selecciona primero una foto.');
        }
        $error = (int)($foto['error'] ?? UPLOAD_ERR_NO_FILE);
        if ($error !== UPLOAD_ERR_OK) {
            throw new RuntimeException('No se pudo recibir la imagen. Comprueba que pese menos de 5 MB.');
        }
        $peso = (int)($foto['size'] ?? 0);
        if ($peso <= 0 || $peso > 5 * 1024 * 1024) {
            throw new RuntimeException('La imagen debe pesar entre 1 byte y 5 MB.');
        }
        $tmp = (string)($foto['tmp_name'] ?? '');
        if ($tmp === '' || !is_uploaded_file($tmp)) {
            throw new RuntimeException('El archivo no corresponde a una subida valida.');
        }
        $ruta = sgaPerfilRutaFoto($usuario, true);
        if (!$ruta) {
            throw new RuntimeException('No se puede crear la carpeta privada fuera del sitio web. Pide al administrador revisar los permisos del hosting.');
        }
        if (is_link($ruta)) throw new RuntimeException('No se pudo reemplazar la foto de forma segura.');
        $temporal = tempnam(dirname($ruta), '.foto-perfil-');
        if ($temporal === false) {
            throw new RuntimeException('No se pudo preparar la imagen privada.');
        }
        try {
            @chmod($temporal, 0600);
            sgaPerfilConvertirPNG($tmp, $temporal);
            if (!@rename($temporal, $ruta)) {
                throw new RuntimeException('No se pudo reemplazar la foto de perfil.');
            }
            @chmod($ruta, 0600);
        } finally {
            if (is_file($temporal)) @unlink($temporal);
        }
        registrarAuditoria('UPDATE_PROFILE_PHOTO', 'Perfil', 'usuario', (int)$usuario['id'],
            'El usuario guardo su foto de perfil PNG privada, 120x120.', (int)$usuario['id']);
        flash('success', 'La foto de perfil se actualizo correctamente.');
        $_SESSION['sga_perfil_feedback']=['tipo'=>'success','mensaje'=>'La foto de perfil se actualizo correctamente.'];
    } else {
        throw new RuntimeException('Accion no reconocida.');
    }
    $_SESSION['csrf_perfil_foto'] = bin2hex(random_bytes(32));
    $_SESSION['sga_reabrir_perfil'] = true;
} catch (Throwable $ex) {
    error_log('[SGA UNEDID] Foto de perfil: no se pudo completar la operacion para usuario '.(int)($_SESSION['usuario_id'] ?? 0));
    $mensajes = [
        'La sesion del formulario expiro. Abre nuevamente tu perfil.',
        'La cedula de tu cuenta no permite guardar fotos.',
        'No se pudo eliminar la foto actual.',
        'Selecciona primero una foto.',
        'No se pudo recibir la imagen. Comprueba que pese menos de 5 MB.',
        'La imagen debe pesar entre 1 byte y 5 MB.',
        'El archivo no corresponde a una subida valida.',
        'No se puede crear la carpeta privada fuera del sitio web. Pide al administrador revisar los permisos del hosting.',
        'No se pudo reemplazar la foto de forma segura.',
        'No se pudo preparar la imagen privada.',
        'No se pudo reemplazar la foto de perfil.',
        'Accion no reconocida.',
        'El servidor necesita la extension GD de PHP para procesar fotos.',
        'Selecciona una imagen valida (JPG, PNG, GIF o WebP).',
        'La imagen es demasiado grande. Usa una foto de hasta 12 megapixeles.',
        'Formato no admitido en este servidor. Usa JPG, PNG o WebP.',
        'No se pudo procesar la foto.',
        'No se pudo redimensionar la foto.',
        'No se pudo guardar la imagen PNG.',
    ];
    $msg = in_array($ex->getMessage(), $mensajes, true)
        ? $ex->getMessage() : 'No se pudo actualizar tu foto. Intentalo nuevamente.';
    flash('error', $msg);
    $_SESSION['sga_perfil_feedback']=['tipo'=>'error','mensaje'=>$msg];
    $_SESSION['sga_reabrir_perfil'] = true;
}
header('Location: ' . $destino, true, 303);
exit;
