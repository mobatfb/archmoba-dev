<?php
/**
 * Texto de usuarios: conservar caracteres de la fuente y detener entradas dañadas.
 * No transliterar Ñ ni tildes: forman parte del nombre registrado.
 */
function sgaUsuariosCsvUtf8(string $datos): string
{
    if (substr($datos, 0, 3) === "\xEF\xBB\xBF") {
        $datos = substr($datos, 3); // UTF-8 con BOM (Excel)
    } elseif (substr($datos, 0, 2) === "\xFF\xFE" || substr($datos, 0, 2) === "\xFE\xFF") {
        if (!function_exists('iconv')) {
            throw new RuntimeException('El CSV es UTF-16 y la extensión iconv no está disponible. Expórtalo como CSV UTF-8.');
        }
        $convertido = @iconv('UTF-16', 'UTF-8', $datos);
        if ($convertido === false) {
            throw new RuntimeException('No se pudo leer el archivo Unicode UTF-16. Vuelve a exportarlo como CSV UTF-8.');
        }
        $datos = $convertido;
    } elseif (preg_match('//u', $datos) !== 1) {
        // Excel en Windows también puede generar CSV Windows-1252.
        if (!function_exists('iconv')) {
            throw new RuntimeException('El CSV no está en UTF-8. Expórtalo como CSV UTF-8 desde Excel.');
        }
        $convertido = @iconv('Windows-1252', 'UTF-8', $datos);
        if ($convertido === false) {
            $convertido = @iconv('ISO-8859-1', 'UTF-8', $datos);
        }
        if ($convertido === false) {
            throw new RuntimeException('No se reconoce la codificación del CSV. Guarda una copia como CSV UTF-8.');
        }
        $datos = $convertido;
    }

    if (preg_match('//u', $datos) !== 1 || strpos($datos, "\xEF\xBF\xBD") !== false || strpos($datos, "\0") !== false) {
        throw new RuntimeException('El CSV contiene caracteres ilegibles o sustituidos. Corrige el archivo original y guárdalo como CSV UTF-8.');
    }
    return $datos;
}

function sgaValidarNombreUtf8(string $valor, string $campo, int $fila = 0): void
{
    $referencia = $fila > 0 ? 'Fila '.$fila.': ' : '';
    if (preg_match('//u', $valor) !== 1) {
        throw new RuntimeException($referencia.$campo.' contiene texto que no está en UTF-8. Revisa la codificación del archivo.');
    }
    // Un signo ? literal ya ha sustituido la letra original: no es recuperable
    // por cambiar el charset. Rechazamos antes de escribir en MySQL.
    if (strpos($valor, '?') !== false || strpos($valor, "\xEF\xBF\xBD") !== false) {
        throw new RuntimeException($referencia.$campo.' contiene ? o un carácter de sustitución. Debes escribir la Ñ o tilde original antes de guardar.');
    }
    // Texto clásico mal decodificado: PEÃ‘A, PEÃ±A, etc. No lo guardar.
    if (preg_match('/(?:Ã[^\s]|Â[^\s])/u', $valor) === 1) {
        throw new RuntimeException($referencia.$campo.' parece tener caracteres mal decodificados. Revisa el CSV y guarda como UTF-8.');
    }
    if (preg_match('/[\x{0000}-\x{001F}\x{007F}-\x{009F}]/u', $valor) === 1) {
        throw new RuntimeException($referencia.$campo.' tiene caracteres de control no válidos.');
    }
}
