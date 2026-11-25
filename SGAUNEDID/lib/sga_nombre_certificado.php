<?php
/**
 * Nombre de certificado identico para descarga individual y ZIP.
 * Formato: ANUAL_APELLIDOS_NOMBRES_CEDULA.pdf o T1/T2/T3_...pdf
 * No modifica el contenido, las calificaciones ni los datos de la matricula.
 */
function sgaNombreArchivoCertificado(array $estudiante, int $trimestre=0): string {
    $prefijos = [0 => 'ANUAL', 1 => 'T1', 2 => 'T2', 3 => 'T3'];
    if (!isset($prefijos[$trimestre])) {
        throw new InvalidArgumentException('Trimestre de certificado no valido.');
    }
    $nombre = trim((string)($estudiante['apellidos'] ?? '') . ' ' . (string)($estudiante['nombres'] ?? ''));
    // Evita tildes y caracteres incompatibles con Windows y los ZIP.
    $equiv = [
        'Á'=>'A','É'=>'E','Í'=>'I','Ó'=>'O','Ú'=>'U','Ü'=>'U','Ñ'=>'N',
        'á'=>'a','é'=>'e','í'=>'i','ó'=>'o','ú'=>'u','ü'=>'u','ñ'=>'n'
    ];
    $nombre = strtr($nombre, $equiv);
    if (function_exists('iconv')) {
        $ascii = @iconv('UTF-8', 'ASCII//TRANSLIT//IGNORE', $nombre);
        if ($ascii !== false) $nombre = $ascii;
    }
    $nombre = trim((string)preg_replace('/[^A-Z0-9]+/', '_', strtoupper($nombre)), '_');
    $nombre = rtrim(substr($nombre, 0, 96), '_');
    if ($nombre === '') $nombre = 'ESTUDIANTE';

    // Mantener la cedula como texto evita perder ceros iniciales.
    $cedula = strtoupper((string)preg_replace('/[^A-Za-z0-9]/', '', (string)($estudiante['cedula'] ?? '')));
    if ($cedula === '') $cedula = 'SIN_CEDULA';

    return $prefijos[$trimestre] . '_' . $nombre . '_' . $cedula . '.pdf';
}
