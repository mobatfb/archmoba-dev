<?php
/**
 * Pantalla de una sola vez para actualizar registros borrados anteriormente.
 * EXIGE sesion de Administrador principal + CSRF en POST.
 * El usuario debe borrar este archivo despues de completar la migracion.
 */
require_once __DIR__.'/lib/funciones.php';
require_once __DIR__.'/lib/sga_eliminacion_catalogos.php';
exigirSuperadmin();
if (empty($_SESSION['csrf_normalizar_delete'])) {
    $_SESSION['csrf_normalizar_delete'] = bin2hex(random_bytes(24));
}
$mensaje = '';
$error = '';
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    try {
        if (!hash_equals((string)$_SESSION['csrf_normalizar_delete'], (string)($_POST['csrf'] ?? ''))) {
            throw new RuntimeException('Formulario caducado. Actualiza esta pagina.');
        }
        if (($_POST['confirmacion'] ?? '') !== 'NORMALIZAR') {
            throw new RuntimeException('Escribe NORMALIZAR para continuar.');
        }
        $cantidad = sgaCatalogoActualizarArchivadosPrevios($conexion);
        $mensaje = 'Migracion completada. Areas corregidas: '.$cantidad['areas']
            .'. Asignaturas corregidas: '.$cantidad['asignaturas'].'.';
    } catch (Throwable $e) { $error = $e->getMessage(); }
}
$pendientes = ['areas'=>null, 'asignaturas'=>null];
try {
    foreach (['areas','asignaturas'] as $tipo) {
        $result = $conexion->query('SELECT COUNT(*) n FROM `'.$tipo.'` '
            .'WHERE archivado_en IS NOT NULL AND nombre_original_borrado IS NULL');
        if (!$result) throw new RuntimeException('Primero ejecuta SQL_SGA_SUFFIX_DELETE.sql desde phpMyAdmin.');
        $pendientes[$tipo] = (int)($result->fetch_assoc()['n'] ?? 0);
    }
} catch (Throwable $e) { $error = $e->getMessage(); }
?><!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Normalizar archivados [DELETE] - SGA</title>
<style>body{background:#f1f4f8;color:#1a2d46;font:16px system-ui,sans-serif;margin:0;padding:30px}main{margin:auto;max-width:700px;background:white;border:1px solid #d0d8e3;border-radius:12px;padding:30px}button{cursor:pointer;background:#163b70;color:white;border:0;border-radius:7px;padding:11px 19px;font-size:16px}input{padding:10px;border:1px solid #9ab;border-radius:6px}p{line-height:1.55}.ok{color:#17623c}.err{color:#a22323}</style></head><body><main>
<h1>Normalizar registros borrados anteriormente</h1>
<p>Esta herramienta actualiza el código y el nombre de las áreas y asignaturas ocultas con el parche anterior. Conserva todos los IDs, vínculos académicos y fechas de archivado. Nunca elimina filas.</p>
<?php if ($mensaje): ?><p class="ok"><strong><?=e($mensaje)?></strong></p><?php endif; ?>
<?php if ($error): ?><p class="err"><strong><?=e($error)?></strong></p><?php endif; ?>
<p>Áreas por actualizar: <strong><?=e($pendientes['areas'] ?? '—')?></strong><br>
Asignaturas por actualizar: <strong><?=e($pendientes['asignaturas'] ?? '—')?></strong></p>
<?php if (!$error && (($pendientes['areas']??0)+($pendientes['asignaturas']??0)>0)): ?>
<form method="post"><input type="hidden" name="csrf" value="<?=e($_SESSION['csrf_normalizar_delete'])?>">
<label>Escribe <strong>NORMALIZAR</strong>: <input name="confirmacion" required pattern="NORMALIZAR" autocomplete="off"></label>
<p><button type="submit">Corregir áreas y asignaturas borradas</button></p></form>
<?php else: ?><p>Sin elementos pendientes. No es necesario repetir la operación.</p><?php endif; ?>
<p><a href="<?=e(url('modulos/areas/index.php'))?>">Volver a Áreas académicas</a></p>
<p><small>Después de terminar, elimina del servidor el archivo <code>migrar_archivados_delete.php</code>.</small></p>
</main></body></html>
