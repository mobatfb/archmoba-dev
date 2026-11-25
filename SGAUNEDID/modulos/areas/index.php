<?php
/** Catalogo de areas. Borrar = ocultar sin perder el historial academico. */
require_once __DIR__ . '/../../lib/funciones.php';
exigirAdminAcademico();
require_once __DIR__ . '/../../lib/sga_catalogos_csv.php';
require_once __DIR__ . '/../../lib/sga_eliminacion_catalogos.php';
require_once __DIR__ . '/../../lib/areas_jornadas.php';
$areasJornadasInstaladas = sgaAreasJornadasInstaladas($conexion);
$jornadasOpciones = sgaAreasJornadasOpciones($conexion);
$jornadasPermitidasIds = array_map('intval', array_column($jornadasOpciones, 'id'));
if (isset($_GET['descargar_plantilla']) && $_GET['descargar_plantilla'] === 'csv') sgaCatalogoCsvDescargarPlantilla('areas');


if (empty($_SESSION['csrf_catalogo_areas'])) {
    $_SESSION['csrf_catalogo_areas'] = bin2hex(random_bytes(24));
}
$csrf = $_SESSION['csrf_catalogo_areas'];
$editarId = max(0, (int)($_GET['editar'] ?? 0));

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    try {
        if (!hash_equals($csrf, (string)($_POST['csrf'] ?? ''))) {
            throw new RuntimeException('La sesión del formulario caducó. Actualiza la página e inténtalo de nuevo.');
        }
        if (!$areasJornadasInstaladas) {
            throw new RuntimeException('Ejecuta SQL_SGA_AREAS_JORNADAS.sql antes de usar este modulo.');
        }
        $accion = (string)($_POST['accion'] ?? '');
        $id = (int)($_POST['id'] ?? 0);
        if($id>0) sgaParametrosProtegerCatalogo($conexion,'areas',$id,$accion);
        $enTransaccionArea = false;
        if ($accion === 'habilitar_jornada') {
            $jid=(int)($_POST['jornada_id']??0);
            if (!$conexion->begin_transaction()) throw new RuntimeException('No fue posible iniciar la operacion.');
            $enTransaccionArea=true;
            $cambio=sgaAreasJornadasHabilitarPropia($conexion,$id,$jid);
            registrarAuditoria('UPDATE','Áreas','area',$id,'Área habilitada para la jornada propia del Subadministrador.',null,
                ['jornadas'=>$cambio['antes']],['jornadas'=>$cambio['despues']],'exito',null,null,'advertencia');
            if (!$conexion->commit()) throw new RuntimeException('No se pudo confirmar la habilitacion.');
            $enTransaccionArea=false;
            flash('success','Área habilitada para tu jornada. Ahora puedes habilitar sus asignaturas.');
        } elseif ($accion === 'importar_csv') {
            $nuevos = sgaCatalogoCsvImportar($conexion, 'areas');
            flash('success', 'Se importaron '.$nuevos.' áreas correctamente.');
        } elseif ($accion === 'crear' || $accion === 'editar') {
            $jornadasElegidas = sgaAreasJornadasValidarSeleccion($_POST['jornadas'] ?? [], $jornadasOpciones);
            $codigo = strtoupper(trim((string)($_POST['codigo'] ?? '')));
            if($codigo==='SGA_PARAM_AULA_INTERNO')throw new RuntimeException('Código reservado del sistema.');
            $nombre = trim((string)($_POST['nombre'] ?? ''));
            $nombre = preg_replace('/\s+/u', ' ', $nombre) ?: $nombre;
            $orden = filter_var($_POST['orden'] ?? '1', FILTER_VALIDATE_INT);
            if ($codigo === '' || !preg_match('/^[A-Z0-9_-]{2,30}$/D', $codigo)) {
                throw new RuntimeException('El código debe tener entre 2 y 30 caracteres (letras, números, guion o guion bajo).');
            }
            if ($nombre === '' || (preg_match_all('/./us', $nombre) ?: 0) > 150) {
                throw new RuntimeException('El nombre del área es obligatorio (máximo 150 caracteres).');
            }
            if ($orden === false || $orden < 1 || $orden > 9999) {
                throw new RuntimeException('El orden debe ser un número del 1 al 9999.');
            }
            if ($accion === 'editar') {
                if ($id <= 0) throw new RuntimeException('Area invalida.');
                sgaAreasJornadasExigirEdicion($conexion, $id);
            }
            if (!$conexion->begin_transaction()) throw new RuntimeException('No se pudo iniciar la actualizacion.');
            $enTransaccionArea = true;
            if ($accion === 'crear') {
                $stmt = $conexion->prepare('INSERT INTO areas (codigo,nombre,orden,activo) VALUES (?,?,?,1)');
                if (!$stmt) throw new RuntimeException('No se pudo preparar la creación del área.');
                $stmt->bind_param('ssi', $codigo, $nombre, $orden);
                if (!$stmt->execute()) throw new RuntimeException($stmt->errno === 1062 ? 'Ya existe un área con ese código o nombre.' : 'No se pudo crear el área.');
                $id = (int)$conexion->insert_id;
                $stmt->close();
                sgaAreasJornadasGuardar($conexion, $id, $jornadasElegidas);
                registrarAuditoria('CREATE','Áreas','area',$id,'Área académica creada.',null,null,
                    ['codigo'=>$codigo,'nombre'=>$nombre,'orden'=>$orden,'activo'=>1,'jornadas'=>$jornadasElegidas]);
                flash('success','Área académica creada correctamente.');
            } else {
                if ($id <= 0) throw new RuntimeException('Área inválida.');
                $stmt = $conexion->prepare('SELECT id,codigo,nombre,orden,activo FROM areas WHERE id=? AND archivado_en IS NULL LIMIT 1');
                $stmt->bind_param('i',$id); $stmt->execute(); $antes = $stmt->get_result()->fetch_assoc(); $stmt->close();
                if (!$antes) throw new RuntimeException('El área no existe.');
                $consultar=$conexion->prepare('SELECT jornadas_ids FROM areas WHERE id=? LIMIT 1');
                $consultar->bind_param('i',$id);$consultar->execute();$originales=sgaAreasJornadasDecodificar($consultar->get_result()->fetch_assoc()['jornadas_ids']??'');$consultar->close();
                sgaAreasJornadasValidarRetirada($conexion,$id,$originales,$jornadasElegidas);
                $stmt = $conexion->prepare('UPDATE areas SET codigo=?,nombre=?,orden=? WHERE id=?');
                $stmt->bind_param('ssii',$codigo,$nombre,$orden,$id);
                if (!$stmt->execute()) throw new RuntimeException($stmt->errno === 1062 ? 'Ya existe otra área con ese código o nombre.' : 'No se pudo modificar el área.');
                $stmt->close();
                sgaAreasJornadasGuardar($conexion, $id, $jornadasElegidas);
                $despues = $antes;
                $despues['codigo'] = $codigo; $despues['nombre'] = $nombre; $despues['orden'] = $orden; $despues['jornadas'] = $jornadasElegidas;
                registrarAuditoria('UPDATE','Áreas','area',$id,'Área académica actualizada.',null,$antes,$despues,'exito',null,null,'advertencia');
                flash('success','Área académica actualizada. Los certificados utilizarán su nuevo nombre.');
            }
            if (!$conexion->commit()) throw new RuntimeException('No se pudo confirmar el cambio de jornadas.');
            $enTransaccionArea = false;
        } elseif ($accion === 'toggle' || $accion === 'eliminar') {
            if ($id <= 0) throw new RuntimeException('Área inválida.');
            sgaAreasJornadasExigirEdicion($conexion, $id);
            $stmt = $conexion->prepare('SELECT id,codigo,nombre,orden,activo FROM areas WHERE id=? AND archivado_en IS NULL LIMIT 1');
            $stmt->bind_param('i',$id); $stmt->execute(); $antes = $stmt->get_result()->fetch_assoc(); $stmt->close();
            if (!$antes) throw new RuntimeException('El área no existe.');
            $stmt = $conexion->prepare('SELECT COUNT(*) total, COALESCE(SUM(activo=1),0) activas FROM asignaturas WHERE area_id=? AND archivado_en IS NULL');
            $stmt->bind_param('i',$id); $stmt->execute(); $dep = $stmt->get_result()->fetch_assoc(); $stmt->close();
            if ($accion === 'toggle') {
                $nuevo = (int)$antes['activo'] === 1 ? 0 : 1;
                if ($nuevo === 0 && (int)$dep['activas'] > 0) {
                    throw new RuntimeException('Esta área tiene asignaturas activas. Desactívalas o asígnalas a otra área antes de desactivar el área.');
                }
                $stmt = $conexion->prepare('UPDATE areas SET activo=? WHERE id=?');
                $stmt->bind_param('ii',$nuevo,$id);
                if (!$stmt->execute()) throw new RuntimeException('No se pudo cambiar el estado del área.');
                $stmt->close();
                $despues = $antes; $despues['activo'] = $nuevo;
                registrarAuditoria('UPDATE','Áreas','area',$id,$nuevo ? 'Área activada.' : 'Área desactivada.',null,$antes,$despues,'exito',null,null,'advertencia');
                flash('success',$nuevo ? 'Área activada.' : 'Área desactivada.');
            } else {
                $ocultados = sgaCatalogoArchivar(
                    $conexion, 'areas', $id, (string)($_POST['confirmacion'] ?? '')
                );
                flash('success','Área borrada del catálogo: su código y nombre ahora contienen [DELETE]. Se ocultaron '.
                    (int)($ocultados['asignaturas'] ?? 0).' asignaturas vinculadas. '.
                    'Sus registros, notas, asistencias y '.(int)($ocultados['ofertas_conservadas'] ?? 0).' asignaciones académicas se conservaron en la base de datos.');
            }
        } else {
            throw new RuntimeException('Acción no reconocida.');
        }
    } catch (Throwable $e) {
        if (!empty($enTransaccionArea)) $conexion->rollback();
        flash('error',$e->getMessage());
    }
    redir('modulos/areas/index.php');
}

$editar = null;
if ($editarId > 0) {
    $stmt = $conexion->prepare('SELECT * FROM areas WHERE id=? AND archivado_en IS NULL LIMIT 1');
    $stmt->bind_param('i',$editarId); $stmt->execute(); $editar = $stmt->get_result()->fetch_assoc() ?: null; $stmt->close();
}
$areas = $conexion->query('SELECT a.*,COUNT(s.id) total_catalogo,COALESCE(SUM(s.activo=1),0) asignaturas_activas,
 (SELECT COUNT(*) FROM ofertas_academicas o JOIN asignaturas ss ON ss.id=o.asignatura_id WHERE ss.area_id=a.id) AS ofertas
 FROM areas a LEFT JOIN asignaturas s ON s.area_id=a.id AND s.archivado_en IS NULL WHERE a.archivado_en IS NULL AND a.codigo<>\'SGA_PARAM_AULA_INTERNO\' GROUP BY a.id ORDER BY a.orden,a.nombre')->fetch_all(MYSQLI_ASSOC);
$areaVinculos = sgaAreasJornadasTodas($conexion);
// Contar materias distintas realmente seleccionadas en aulas del periodo y de la jornada visible.
$periodoContador=(int)(periodoActivo()['id']??0);
$jornadasContador=esSuperadmin()?array_map('intval',array_column(sgaAreasJornadasOpciones($conexion),'id')):jornadasEnVista($periodoContador);
$usoArea=[];
if ($periodoContador>0 && $jornadasContador) {
    $u=$conexion->prepare('SELECT DISTINCT s.id asignatura_id,s.area_id,au.jornada_id FROM (
      SELECT t.aula_periodo_id,t.asignatura_id FROM aula_asignaturas_seleccionadas t WHERE t.seleccionada=1
      UNION
      SELECT o.aula_periodo_id,o.asignatura_id FROM ofertas_academicas o WHERE o.activo=1
    ) x JOIN aulas_periodo ap ON ap.id=x.aula_periodo_id AND ap.activo=1
      JOIN aulas au ON au.id=ap.aula_id JOIN asignaturas s ON s.id=x.asignatura_id
      WHERE ap.periodo_id=? AND s.archivado_en IS NULL');
    $u->bind_param('i',$periodoContador);$u->execute();
    foreach($u->get_result()->fetch_all(MYSQLI_ASSOC) as $fila) {
        if (!in_array((int)$fila['jornada_id'],$jornadasContador,true)) continue;
        $usoArea[(int)$fila['area_id']][(int)$fila['asignatura_id']]=true;
    }
    $u->close();
}
foreach ($areas as &$a) {
    $link = $areaVinculos[(int)$a['id']] ?? ['ids'=>[], 'nombres'=>[]];
    $a['total_asignaturas'] = count($usoArea[(int)$a['id']]??[]);
    $a['jornadas_ids'] = $link['ids'];
    $a['jornadas_label'] = $link['nombres'] ? implode(' / ', $link['nombres']) : 'Sin jornada asignada';
    $a['puede_editar'] = $areasJornadasInstaladas && sgaAreasJornadasPuedeEditar($link['ids']);
}
unset($a);
if (esSubadmin() && !esSuperadmin()) {
    $areasHabilitables=[];
    $periodoGestion = (int)(periodoActivo()['id'] ?? 0);
    $jornadasEnPantalla = jornadasEnVista($periodoGestion);
    $areasHabilitables=array_values(array_filter($areas,static fn($a)=> (int)$a['activo']===1 && !array_intersect($a['jornadas_ids'],$jornadasEnPantalla)));
    $areas = array_values(array_filter($areas, static function($a) use($jornadasEnPantalla) {
        return (bool)array_intersect($a['jornadas_ids'], $jornadasEnPantalla);
    }));
}

// Sugerir el siguiente numero consecutivo (1, 2, 3...) al crear un area.
$siguienteOrden = 1;
foreach ($areas as $areaCatalogo) {
    $siguienteOrden = max($siguienteOrden, (int)$areaCatalogo['orden'] + 1);
}
$totales = ['areas'=>count($areas),'activas'=>0,'asignaturas'=>0];
foreach ($areas as $a) { $totales['activas'] += (int)$a['activo']; $totales['asignaturas'] += (int)$a['total_asignaturas']; }
$tituloPagina = 'Áreas académicas';
$subtituloPagina = 'Primero crea las áreas; después podrás vincular las asignaturas a cada una.';
require __DIR__ . '/../../partials/header.php';
?>
<link rel="stylesheet" href="<?=e(url('assets/css/sga_catalogo_modales.css'))?>?v=1625">
<script defer src="<?=e(url('assets/js/sga_catalogo_modales.js'))?>?v=1625"></script>
<style>
/* Seleccion multiple visible de jornadas en el catalogo de areas. */
.sga-cat-dialog .sga-area-jornadas-fieldset{background:#f7faff}
.sga-area-jornadas-toolbar{display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;margin-bottom:10px}
.sga-area-jornadas-help{font-size:12px;color:#415c78}
.sga-area-jornadas-toggle{border:1px solid #bcd0e6;border-radius:7px;background:#fff;color:#1b5187;font-size:12px;font-weight:700;padding:7px 11px;cursor:pointer}
.sga-area-jornadas-toggle:hover{background:#eef6ff}
.sga-area-jornadas-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:8px}
.sga-cat-dialog .sga-area-jornadas-grid .sga-area-jornada-option{display:flex;align-items:center;flex-direction:row;gap:10px;min-height:44px;padding:10px 12px;margin:0;border:1px solid #d5dfeb;border-radius:9px;background:#fff;cursor:pointer;font-size:13px;font-weight:700;color:#214566;white-space:normal}
.sga-cat-dialog .sga-area-jornadas-grid .sga-area-jornada-option.is-selected{background:#e9f2ff;border-color:#7da7d5}
.sga-cat-dialog .sga-area-jornadas-grid .sga-area-jornada-option input{flex:0 0 17px;width:17px;height:17px;margin:0;accent-color:#1b5b9f}
.sga-area-jornadas-summary{font-size:12px;font-weight:700;color:#245b89;margin-top:9px}
.sga-area-jornadas-error{font-size:12px;font-weight:700;color:#ad2828;margin-top:5px}
@media(max-width:550px){.sga-area-jornadas-grid{grid-template-columns:1fr}.sga-area-jornadas-toggle{width:100%}}
</style>

<?php if (!$areasJornadasInstaladas): ?>
<div class="alert error" role="alert"><strong>Configuración pendiente:</strong> ejecuta <code>sql/SQL_SGA_AREAS_JORNADAS.sql</code> en phpMyAdmin para activar jornadas en áreas. Mientras tanto el catálogo se muestra en modo consulta.</div>
<?php elseif (!$jornadasOpciones): ?>
<div class="alert info">No existen jornadas activas autorizadas para tu perfil. Solicita al Administrador que las configure.</div>
<?php endif; ?>
<div class="sga-cat-metrics" aria-label="Resumen del catálogo de áreas"><span><strong><?= (int)$totales['areas'] ?></strong> áreas registradas</span><span><strong><?= (int)$totales['activas'] ?></strong> activas</span><span><strong><?= (int)$totales['asignaturas'] ?></strong> asignaturas en uso en esta jornada y período</span></div>
<div class="sga-cat-toolbar"><div><h2 class="sga-cat-toolbar-title">Catálogo de áreas</h2><small class="sga-cat-toolbar-sub">Define el orden en que se agrupan las asignaturas en certificados.</small></div>
<div class="actions"><a class="btn btn-secondary" href="<?=e(url('modulos/asignaturas/index.php'))?>">Ir a Asignaturas</a><button class="btn btn-primary" type="button" data-sga-cat-open="sga-cat-create" <?= !$areasJornadasInstaladas || !$jornadasOpciones ? 'disabled title="Configura primero las jornadas del area"' : '' ?>>+ Crear / importar áreas</button></div></div>
<dialog class="sga-cat-dialog" id="sga-cat-create" aria-labelledby="sga-cat-create-title">
<header class="sga-cat-dialog-head"><div><h2 id="sga-cat-create-title">Crear o importar áreas</h2><p>Selecciona cómo deseas registrar las áreas académicas.</p></div>
<button class="sga-cat-dialog-close" type="button" aria-label="Cerrar ventana" data-sga-cat-close>&times;</button></header>
<div class="sga-cat-tabs" role="tablist" aria-label="Método de registro">
<button type="button" class="sga-cat-tab" data-sga-cat-tab="crear" role="tab" id="sga-cat-tab-crear" aria-selected="true" aria-controls="sga-cat-panel-crear">Crear área</button>
<button type="button" class="sga-cat-tab" data-sga-cat-tab="csv" role="tab" id="sga-cat-tab-csv" aria-selected="false" aria-controls="sga-cat-panel-csv" tabindex="-1">Importar CSV</button>
</div>
<div class="sga-cat-dialog-inner">
<section class="sga-cat-panel" data-sga-cat-panel="crear" id="sga-cat-panel-crear" role="tabpanel" aria-labelledby="sga-cat-tab-crear"><form method="post"><input type="hidden" name="csrf" value="<?=e($csrf)?>"><input type="hidden" name="accion" value="crear"><div class="form-grid cols-3">
<label>Código del área<input name="codigo" maxlength="30" pattern="[A-Za-z0-9_-]{2,30}" placeholder="CCNN" required></label>
<label>Nombre del área<input name="nombre" maxlength="150" placeholder="CIENCIAS NATURALES" required></label>
<label>Orden en certificados<input type="number" name="orden" value="<?= (int)$siguienteOrden ?>" min="1" max="9999" required></label></div>
<fieldset class="sga-cat-form-fieldset sga-area-jornadas-fieldset" data-sga-area-jornadas><legend>Jornadas del área (selección múltiple)</legend>
<div class="sga-area-jornadas-toolbar"><span class="sga-area-jornadas-help">Marca una o varias jornadas para esta área.</span><button type="button" class="sga-area-jornadas-toggle" data-sga-area-jornadas-toggle>Seleccionar todas</button></div>
<div class="sga-area-jornadas-grid">
<?php foreach ($jornadasOpciones as $j): ?><label class="sga-area-jornada-option"><input type="checkbox" name="jornadas[]" value="<?= (int)$j['id'] ?>"><span><?=e($j['nombre'])?></span></label><?php endforeach; ?>
</div><div class="sga-area-jornadas-summary" data-sga-area-jornadas-summary aria-live="polite">0 jornadas seleccionadas</div><div class="sga-area-jornadas-error" data-sga-area-jornadas-error role="alert" hidden>Selecciona al menos una jornada.</div></fieldset>
<div class="sga-cat-actions"><button class="btn btn-secondary" type="button" data-sga-cat-close>Cancelar</button><button class="btn btn-primary" type="submit">Crear área</button></div></form></section><section class="sga-cat-panel" data-sga-cat-panel="csv" id="sga-cat-panel-csv" role="tabpanel" aria-labelledby="sga-cat-tab-csv" hidden>
<p class="sga-cat-help"><strong>Importación multijornada:</strong> columnas <code>codigo;nombre;orden;jornadas</code> (UTF-8, separador <strong>;</strong>). En <code>jornadas</code> escribe <strong>MAT|VES</strong> para ambas, o <strong>MAT</strong>/<strong>VES</strong> para una sola. Se admiten los códigos reales de tus jornadas.</p>
<p><a class="btn btn-secondary" href="?descargar_plantilla=csv">Descargar plantilla CSV (;)</a></p>
<p class="sga-cat-template-warning"><strong>Plantilla con ejemplo:</strong> reemplaza o elimina la fila de demostración antes de importar datos reales.</p>
<form method="post" enctype="multipart/form-data">
<input type="hidden" name="csrf" value="<?=e($csrf)?>"><input type="hidden" name="accion" value="importar_csv">
<label>Seleccionar archivo CSV<input type="file" name="archivo_csv" accept=".csv,text/csv" required></label>
<div class="mini-note">Hasta 1500 registros o 2 MB. Si hay un error, no se importa ninguna fila.</div>
<div class="sga-cat-actions"><button class="btn btn-secondary" type="button" data-sga-cat-close>Cancelar</button><button class="btn btn-primary" type="submit">Importar áreas</button></div>
</form></section></div></dialog>
<dialog class="sga-cat-dialog" id="sga-cat-edit" aria-labelledby="sga-cat-edit-title" data-sga-cat-singular="área académica">
<header class="sga-cat-dialog-head"><div><h2 id="sga-cat-edit-title">Editar área académica</h2><p>Edita el área seleccionada y guarda los cambios.</p></div>
<button class="sga-cat-dialog-close" type="button" aria-label="Cerrar ventana" data-sga-cat-close>&times;</button></header>
<div class="sga-cat-dialog-inner">
<form method="post" data-sga-cat-edit-form><input type="hidden" name="csrf" value="<?=e($csrf)?>"><input type="hidden" name="accion" value="editar"><input type="hidden" name="id" value=""><div class="form-grid cols-3">
<label>Código del área<input name="codigo" maxlength="30" pattern="[A-Za-z0-9_-]{2,30}" placeholder="CCNN" required></label>
<label>Nombre del área<input name="nombre" maxlength="150" placeholder="CIENCIAS NATURALES" required></label>
<label>Orden en certificados<input type="number" name="orden" value="" min="1" max="9999" required></label></div>
<fieldset class="sga-cat-form-fieldset sga-area-jornadas-fieldset" data-sga-area-jornadas><legend>Jornadas del área (selección múltiple)</legend>
<div class="sga-area-jornadas-toolbar"><span class="sga-area-jornadas-help">Las jornadas marcadas son las actualmente asignadas.</span><button type="button" class="sga-area-jornadas-toggle" data-sga-area-jornadas-toggle>Seleccionar todas</button></div>
<div class="sga-area-jornadas-grid">
<?php foreach ($jornadasOpciones as $j): ?><label class="sga-area-jornada-option"><input type="checkbox" name="jornadas[]" value="<?= (int)$j['id'] ?>"><span><?=e($j['nombre'])?></span></label><?php endforeach; ?>
</div><div class="sga-area-jornadas-summary" data-sga-area-jornadas-summary aria-live="polite">0 jornadas seleccionadas</div><div class="sga-area-jornadas-error" data-sga-area-jornadas-error role="alert" hidden>Selecciona al menos una jornada.</div><div class="mini-note">Las asignaturas existentes se conservan. Solo se actualiza su disponibilidad por jornada.</div></fieldset>
<div class="sga-cat-actions"><button class="btn btn-secondary" type="button" data-sga-cat-close>Cancelar</button><button class="btn btn-primary" type="submit">Guardar cambios</button></div></form></div></dialog>

<p class="mini-note">Una misma área puede estar disponible en varias jornadas. La lista indica todas las jornadas asignadas a cada área.</p>
<div class="table-wrap"><table class="table table-responsive-cards"><thead><tr><th>Orden</th><th>Código</th><th>Área</th><th>Jornadas</th><th>Asignaturas</th><th>Estado</th><th>Acciones</th></tr></thead><tbody>
<?php if (!$areas): ?><tr><td colspan="7" class="empty">Todavía no hay áreas. Registra la primera para habilitar el catálogo de asignaturas.</td></tr><?php endif; ?>
<?php foreach ($areas as $a): ?>
<tr>
  <td><?= (int)$a['orden'] ?></td><td><?= e($a['codigo']) ?></td><td><strong><?= e($a['nombre']) ?></strong></td>
  <td><?= e($a['jornadas_label']) ?></td>
  <td><a href="<?= e(url('modulos/asignaturas/index.php?area_id='.(int)$a['id'])) ?>"><?= (int)$a['total_asignaturas'] ?> materia(s) en uso</a></td>
  <td><span class="badge <?= $a['activo'] ? 'good' : 'bad' ?>"><?= $a['activo'] ? 'Activa' : 'Inactiva' ?></span></td>
  <td><div class="actions">
    <?php if ($a['puede_editar']): ?>
    <a class="btn btn-sm btn-secondary" href="?editar=<?= (int)$a['id'] ?>" data-sga-cat-edit='<?=e(json_encode($a,JSON_UNESCAPED_UNICODE|JSON_HEX_TAG|JSON_HEX_AMP|JSON_HEX_APOS|JSON_HEX_QUOT))?>' >Editar</a>
    <form method="post"><input type="hidden" name="csrf" value="<?= e($csrf) ?>"><input type="hidden" name="accion" value="toggle"><input type="hidden" name="id" value="<?= (int)$a['id'] ?>"><button class="btn btn-sm <?= $a['activo'] ? 'btn-secondary' : 'btn-success' ?>" data-confirm="¿Cambiar el estado de esta área?" <?= $a['activo'] && (int)$a['asignaturas_activas'] > 0 ? 'disabled title="Tiene asignaturas activas"' : '' ?>><?= $a['activo'] ? 'Desactivar' : 'Activar' ?></button></form>
    <button type="button" class="btn btn-sm btn-danger" data-sga-cat-open="sga-cat-delete" data-sga-cat-delete-id="<?= (int)$a['id'] ?>" data-sga-cat-delete-name="<?= e($a['nombre']) ?>" data-sga-cat-delete-materias="<?= (int)$a['total_asignaturas'] ?>" data-sga-cat-delete-ofertas="<?= (int)$a['ofertas'] ?>">Borrar</button>
    <?php else: ?><span class="mini-note">Solo lectura</span><?php endif; ?>
  </div></td>
</tr>
<?php endforeach; ?>
</tbody></table></div>
<?php if (!empty($areasHabilitables)): ?>
<section class="card" style="margin-top:16px"><h2 class="section-title">Áreas disponibles para habilitar en tu jornada</h2>
<p class="mini-note">El área se comparte sin duplicarse. Solo añades tu jornada; no modificas las asignaciones de otras jornadas.</p>
<div class="table-wrap"><table class="table"><thead><tr><th>Área</th><th>Jornadas actuales</th><th>Acción</th></tr></thead><tbody>
<?php foreach ($areasHabilitables as $otra): ?><tr><td><?=e($otra['nombre'])?></td><td><?=e($otra['jornadas_label'])?></td><td>
<?php foreach (sgaAreasJornadasOpciones($conexion) as $j): ?>
<form method="post" style="display:inline-block"><input type="hidden" name="csrf" value="<?=e($csrf)?>"><input type="hidden" name="accion" value="habilitar_jornada"><input type="hidden" name="id" value="<?=(int)$otra['id']?>"><input type="hidden" name="jornada_id" value="<?=(int)$j['id']?>"><button type="submit" class="btn btn-sm btn-secondary" data-confirm="¿Habilitar esta área para <?=e($j['nombre'])?>?">Habilitar en <?=e($j['nombre'])?></button></form>
<?php endforeach; ?></td></tr><?php endforeach; ?>
</tbody></table></div></section>
<?php endif; ?>
<dialog class="sga-cat-dialog" id="sga-cat-delete" aria-labelledby="sga-cat-delete-title">
<header class="sga-cat-dialog-head"><div><h2 id="sga-cat-delete-title">Borrar área del catálogo</h2><p>Se ocultará sin borrar sus registros de la base de datos. El código y nombre del área y de sus asignaturas recibirán el sufijo [DELETE].</p></div>
<button class="sga-cat-dialog-close" type="button" aria-label="Cerrar ventana" data-sga-cat-close>&times;</button></header>
<div class="sga-cat-dialog-inner">
<p><strong id="sga-cat-delete-nombre"></strong></p>
<p>El área y todas sus asignaturas dejarán de aparecer en los listados y no estarán disponibles para nuevas asignaciones.</p>
<p id="sga-cat-delete-cantidades" class="mini-note"></p>
<div class="alert info" role="note"><strong>Conservación de datos:</strong> el área, las asignaturas y sus relaciones seguirán almacenadas en la base de datos, junto con todas las calificaciones, notas finales, asistencias y registros históricos. Esta acción solo las oculta del uso académico habitual.</div>
<form method="post" id="sga-cat-delete-form">
<input type="hidden" name="csrf" value="<?=e($csrf)?>">
<input type="hidden" name="accion" value="eliminar">
<input type="hidden" name="id" value="">
<label>Para confirmar, escribe <strong>ELIMINAR</strong>:
<input type="text" name="confirmacion" autocomplete="off" pattern="ELIMINAR" placeholder="ELIMINAR" required></label>
<div class="sga-cat-actions"><button class="btn btn-secondary" type="button" data-sga-cat-close>Cancelar</button><button class="btn btn-danger" type="submit">Borrar del catálogo</button></div>
</form></div></dialog>
<script>
document.addEventListener('DOMContentLoaded', () => {
  // Cada modal tiene su seleccion independiente (crear y editar).
  const gruposJornadas = Array.from(document.querySelectorAll('[data-sga-area-jornadas]'));
  function actualizarGrupo(grupo) {
    const casillas = Array.from(grupo.querySelectorAll('input[name="jornadas[]"]'));
    const total = casillas.filter(c => c.checked).length;
    casillas.forEach(c => c.closest('.sga-area-jornada-option')?.classList.toggle('is-selected', c.checked));
    const resumen = grupo.querySelector('[data-sga-area-jornadas-summary]');
    if (resumen) resumen.textContent = total + (total === 1 ? ' jornada seleccionada' : ' jornadas seleccionadas');
    const boton = grupo.querySelector('[data-sga-area-jornadas-toggle]');
    if (boton) boton.textContent = (total === casillas.length && casillas.length > 0) ? 'Quitar selección' : 'Seleccionar todas';
    const error = grupo.querySelector('[data-sga-area-jornadas-error]');
    if (error) error.hidden = total > 0 || grupo.dataset.sgaAreaTriedSubmit !== '1';
    return total;
  }
  gruposJornadas.forEach(grupo => {
    grupo.querySelectorAll('input[name="jornadas[]"]').forEach(c => c.addEventListener('change', () => actualizarGrupo(grupo)));
    const boton = grupo.querySelector('[data-sga-area-jornadas-toggle]');
    if (boton) boton.addEventListener('click', () => {
      const casillas = Array.from(grupo.querySelectorAll('input[name="jornadas[]"]'));
      const marcar = !casillas.every(c => c.checked);
      casillas.forEach(c => { c.checked = marcar; });
      actualizarGrupo(grupo);
    });
    grupo.closest('form')?.addEventListener('submit', evento => {
      if (actualizarGrupo(grupo) > 0) return;
      evento.preventDefault();
      grupo.dataset.sgaAreaTriedSubmit = '1';
      actualizarGrupo(grupo);
      grupo.querySelector('input[name="jornadas[]"]')?.focus();
    });
    actualizarGrupo(grupo);
  });
  function marcarJornadas(datos) {
    const elegidas = new Set((datos.jornadas_ids || []).map(String));
    document.querySelectorAll('#sga-cat-edit input[name="jornadas[]"]').forEach(c => {
      c.checked = elegidas.has(c.value);
    });
    const grupo = document.querySelector('#sga-cat-edit [data-sga-area-jornadas]');
    if (grupo) actualizarGrupo(grupo);
  }
  document.querySelectorAll('[data-sga-cat-edit]').forEach(b => b.addEventListener('click', () => {
    try { marcarJornadas(JSON.parse(b.dataset.sgaCatEdit)); } catch (err) { console.error('Jornadas de area', err); }
  }));
  // Tambien funciona el enlace directo ?editar=ID si el JS generico lo abrio al cargar.
  const id = new URLSearchParams(window.location.search).get('editar');
  if (id) {
    const b = Array.from(document.querySelectorAll('[data-sga-cat-edit]')).find(x => {
      try { return String(JSON.parse(x.dataset.sgaCatEdit).id) === id; } catch(e) { return false; }
    });
    if (b) marcarJornadas(JSON.parse(b.dataset.sgaCatEdit));
  }
});
(() => {
  const dialog = document.getElementById('sga-cat-delete');
  if (!dialog) return;
  const idInput = dialog.querySelector('input[name="id"]');
  const confirmar = dialog.querySelector('input[name="confirmacion"]');
  const nombre = document.getElementById('sga-cat-delete-nombre');
  const cantidades = document.getElementById('sga-cat-delete-cantidades');
  document.querySelectorAll('[data-sga-cat-delete-id]').forEach(boton => {
    boton.addEventListener('click', () => {
      idInput.value = boton.dataset.sgaCatDeleteId || '';
      nombre.textContent = boton.dataset.sgaCatDeleteName || '';
      cantidades.textContent = 'Asignaturas vinculadas: ' + (boton.dataset.sgaCatDeleteMaterias || '0') + '. Asignaciones en aulas: ' + (boton.dataset.sgaCatDeleteOfertas || '0') + '.';
      confirmar.value = '';
    });
  });
})();
</script>
<?php require __DIR__ . '/../../partials/footer.php'; ?>
