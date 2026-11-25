<?php
/**
 * Fotos de perfil SGA UNEDID, guardadas FUERA del DOCUMENT_ROOT.
 * No utilizar rutas publicas ni almacenar fotos o sus rutas en la base de datos.
 */

function sgaPerfilCedulaValida(string $cedula): bool {
    return (bool)preg_match('/\A[0-9]{10,13}\z/D', trim($cedula));
}

/** Primer apellido + primer nombre; funciona tambien sin mbstring. */
function sgaPerfilIniciales(array $usuario): string {
    $primera = static function (string $valor): string {
        $valor = trim($valor);
        if ($valor === '') return '';
        $palabras = preg_split('/\s+/u', $valor) ?: [];
        $palabra = (string)($palabras[0] ?? '');
        if (preg_match('/\p{L}/u', $palabra, $m)) return $m[0];
        return '';
    };
    $inicial = $primera((string)($usuario['apellidos'] ?? ''))
        . $primera((string)($usuario['nombres'] ?? ''));
    if ($inicial === '') return 'U';
    if (function_exists('mb_strtoupper')) return mb_strtoupper($inicial, 'UTF-8');
    return strtoupper($inicial);
}

/**
 * Localiza la raiz PRIVADA del hosting, nunca la raiz de la aplicacion.
 * Para dominios dentro de /public_html/subdominio se sube fuera de public_html.
 * En hostings que impidan salir del DOCUMENT_ROOT se falla sin exponer archivos.
 */
function sgaPerfilRaizPrivada(bool $crear = false): ?string {
    $doc = $_SERVER['DOCUMENT_ROOT'] ?? '';
    $doc = is_string($doc) && $doc !== '' ? realpath($doc) : false;
    if (!$doc || !is_dir($doc) || $doc === DIRECTORY_SEPARATOR) return null;
    $doc = rtrim($doc, DIRECTORY_SEPARATOR);
    $base = dirname($doc);
    // Proteccion adicional en cPanel / Plesk cuando el subdominio vive
    // dentro del document root de otro dominio de la misma cuenta.
    $actual = $doc;
    while ($actual !== dirname($actual)) {
        if (in_array(strtolower(basename($actual)),
                ['public_html', 'httpdocs', 'htdocs', 'www', 'wwwroot'], true)) {
            $base = dirname($actual);
            break;
        }
        $actual = dirname($actual);
    }
    if ($base === DIRECTORY_SEPARATOR) return null;
    $raiz = $base . DIRECTORY_SEPARATOR . '.sga_unedid_privado';
    $fotos = $raiz . DIRECTORY_SEPARATOR . 'fotos_perfil';
    if (is_link($raiz) || is_link($fotos)) return null;

    if ($crear) {
        if (!is_dir($raiz) && !@mkdir($raiz, 0700)) return null;
        if (!is_dir($fotos) && !@mkdir($fotos, 0700)) return null;
        @chmod($raiz, 0700);
        @chmod($fotos, 0700);
        // Segunda barrera para servidores Apache si se reconfigura un vhost.
        $bloqueo = "Options -Indexes\n<IfModule mod_authz_core.c>\nRequire all denied\n</IfModule>\n<IfModule !mod_authz_core.c>\nDeny from all\n</IfModule>\n";
        foreach ([$raiz, $fotos] as $dir) {
            $htaccess = $dir . DIRECTORY_SEPARATOR . '.htaccess';
            if (!is_file($htaccess)) @file_put_contents($htaccess, $bloqueo, LOCK_EX);
            if (is_file($htaccess)) @chmod($htaccess, 0600);
        }
    }
    if (!is_dir($fotos) || is_link($fotos)) return null;
    $real = realpath($fotos);
    if ($real === false) return null;
    $real = rtrim($real, DIRECTORY_SEPARATOR);
    // Nunca permitir almacenamiento dentro de la carpeta web del sitio.
    if ($real === $doc || str_starts_with($real . DIRECTORY_SEPARATOR, $doc . DIRECTORY_SEPARATOR)) return null;
    return $real;
}

/** La ruta se deriva SOLO de la cedula leida del usuario autenticado. */
function sgaPerfilRutaFoto(array $usuario, bool $crear = false): ?string {
    $cedula = trim((string)($usuario['cedula'] ?? ''));
    if (!sgaPerfilCedulaValida($cedula)) return null;
    $dir = sgaPerfilRaizPrivada($crear);
    return $dir === null ? null : $dir . DIRECTORY_SEPARATOR . $cedula . '.png';
}

function sgaPerfilFotoExiste(array $usuario): bool {
    $ruta = sgaPerfilRutaFoto($usuario);
    return $ruta !== null && is_file($ruta) && !is_link($ruta);
}

/**
 * Decodifica exclusivamente imagenes reales y genera PNG 120x120.
 * Recorte centrado: preserva proporciones y evita estiramiento.
 */
function sgaPerfilConvertirPNG(string $origen, string $destino): void {
    if (!extension_loaded('gd')) {
        throw new RuntimeException('El servidor necesita la extension GD de PHP para procesar fotos.');
    }
    $info = @getimagesize($origen);
    if (!$info || !isset($info[0], $info[1], $info[2])) {
        throw new RuntimeException('Selecciona una imagen valida (JPG, PNG, GIF o WebP).');
    }
    [$ancho, $alto] = [(int)$info[0], (int)$info[1]];
    if ($ancho < 1 || $alto < 1 || $ancho > 5000 || $alto > 5000 || $ancho * $alto > 12000000) {
        throw new RuntimeException('La imagen es demasiado grande. Usa una foto de hasta 12 megapixeles.');
    }
    switch ((int)$info[2]) {
        case IMAGETYPE_JPEG: $origenImagen = @imagecreatefromjpeg($origen); break;
        case IMAGETYPE_PNG: $origenImagen = @imagecreatefrompng($origen); break;
        case IMAGETYPE_GIF: $origenImagen = @imagecreatefromgif($origen); break;
        case IMAGETYPE_WEBP:
            $origenImagen = function_exists('imagecreatefromwebp') ? @imagecreatefromwebp($origen) : false;
            break;
        default: $origenImagen = false;
    }
    if ($origenImagen === false) {
        throw new RuntimeException('Formato no admitido en este servidor. Usa JPG, PNG o WebP.');
    }
    try {
        // Ajuste de orientacion en fotos JPG de camaras moviles.
        if ((int)$info[2] === IMAGETYPE_JPEG && function_exists('exif_read_data')) {
            $exif = @exif_read_data($origen);
            $orientacion = (int)($exif['Orientation'] ?? 1);
            if (in_array($orientacion, [3, 6, 8], true)) {
                $grados = [3 => 180, 6 => 270, 8 => 90][$orientacion];
                $rotada = imagerotate($origenImagen, $grados, 0);
                if ($rotada !== false) {
                    imagedestroy($origenImagen);
                    $origenImagen = $rotada;
                }
            }
            if (in_array($orientacion, [2, 4, 5, 7], true) && function_exists('imageflip')) {
                imageflip($origenImagen, IMG_FLIP_HORIZONTAL);
            }
        }
        $w = imagesx($origenImagen);
        $h = imagesy($origenImagen);
        $lado = min($w, $h);
        $x = (int)floor(($w - $lado) / 2);
        $y = (int)floor(($h - $lado) / 2);
        $salida = imagecreatetruecolor(120, 120);
        if ($salida === false) throw new RuntimeException('No se pudo procesar la foto.');
        try {
            imagealphablending($salida, false);
            imagesavealpha($salida, true);
            $transparente = imagecolorallocatealpha($salida, 0, 0, 0, 127);
            imagefilledrectangle($salida, 0, 0, 119, 119, $transparente);
            if (!imagecopyresampled($salida, $origenImagen, 0, 0, $x, $y,
                    120, 120, $lado, $lado)) {
                throw new RuntimeException('No se pudo redimensionar la foto.');
            }
            if (!imagepng($salida, $destino, 7)) {
                throw new RuntimeException('No se pudo guardar la imagen PNG.');
            }
        } finally {
            imagedestroy($salida);
        }
    } finally {
        imagedestroy($origenImagen);
    }
}
