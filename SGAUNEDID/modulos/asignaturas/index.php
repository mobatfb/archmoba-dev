<?php
/** Catálogo de asignaturas vinculado obligatoriamente a las áreas académicas. */
require_once __DIR__ . '/../../lib/funciones.php';
exigirAdminAcademico();
require_once __DIR__ . '/../../lib/sga_catalogos_csv.php';
require_once __DIR__ . '/../../lib/sga_eliminacion_catalogos.php';
require_once __DIR__ . '/../../lib/sga_asignaturas_jornadas.php';
$areasJornadasInstaladas = sgaAreasJornadasInstaladas($conexion);
$asignaturasJornadasInstaladas = sgaAsignaturasJornadasInstaladas($conexion);
$jornadasOpciones = $areasJornadasInstaladas ? sgaAreasJornadasOpciones($conexion) : [];
$jornadasTodos=$conexion->query('SELECT id,nombre FROM jornadas ORDER BY orden,nombre')->fetch_all(MYSQLI_ASSOC);
$jornadasEnVistaAsignaturas = esSuperadmin()
    ? array_map('intval',array_column($jornadasOpciones,'id'))
    : jornadasEnVista((int)(periodoActivo()['id']??0));
if (isset($_GET['descargar_plantilla']) && $_GET['descargar_plantilla'] === 'csv') sgaCatalogoCsvDescargarPlantilla('asignaturas');


if (empty($_SESSION['csrf_catalogo_asignaturas'])) {
    $_SESSION['csrf_catalogo_asignaturas'] = bin2hex(random_bytes(24));
}
$csrf = $_SESSION['csrf_catalogo_asignaturas'];

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    try {
        if (!hash_equals($csrf,(string)($_POST['csrf'] ?? ''))) {
            throw new RuntimeException('La sesión del formulario caducó. Actualiza la página.');
        }
        if (!$areasJornadasInstaladas || !$asignaturasJornadasInstaladas) throw new RuntimeException('Instala las migraciones de jornadas en Areas y Asignaturas antes de gestionar asignaturas.');
        $accion = (string)($_POST['accion'] ?? '');
        $id = (int)($_POST['id'] ?? 0);
        if($id>0) sgaParametrosProtegerCatalogo($conexion,'asignaturas',$id,$accion);
        if ($accion === 'habilitar_jornada') {
            $jornadaId=(int)($_POST['jornada_id']??0);
            if (!$conexion->begin_transaction()) throw new RuntimeException('No se pudo iniciar la habilitacion.');
            try {
                $cambio=sgaAsignaturasHabilitarPropia($conexion,$id,$jornadaId);
                registrarAuditoria('UPDATE','Asignaturas','asignatura',$id,'Asignatura habilitada para jornada autorizada del Subadministrador.',null,
                  ['jornadas'=>$cambio['antes']],['jornadas'=>$cambio['despues']],'exito',null,null,'advertencia');
                if (!$conexion->commit()) throw new RuntimeException('No se pudo confirmar la habilitacion.');
            } catch(Throwable $e) { $conexion->rollback(); throw $e; }
            flash('success','Asignatura habilitada para tu jornada sin afectar las otras.');
        } elseif ($accion === 'importar_csv') {
            $nuevos = sgaCatalogoCsvImportar($conexion, 'asignaturas');
            flash('success', 'Se importaron '.$nuevos.' asignaturas correctamente.');
        } elseif ($accion === 'crear' || $accion === 'editar') {
            $codigo = trim((string)($_POST['codigo'] ?? ''));
            if(strtoupper($codigo)==='SGA_PARAM_AULA_INTERNO')throw new RuntimeException('Código reservado del sistema.');
            $nombre = trim((string)($_POST['nombre'] ?? ''));
            $nombre = preg_replace('/\s+/u',' ',$nombre) ?: $nombre;
            $areaId = (int)($_POST['area_id'] ?? 0);
            $visorComportamiento = isset($_POST['solo_visor_comportamiento']) ? 1 : 0;

            // Esta marca afecta solo la presentacion en reportes, no el registro de notas.
            $especial = isset($_POST['especial']) ? 1 : 0;

            if ($nombre === '' || (preg_match_all('/./us', $nombre) ?: 0) > 150) {
                throw new RuntimeException('El nombre de la asignatura es obligatorio (máximo 150 caracteres).');
            }
            if (strlen($codigo) > 30) throw new RuntimeException('El código no puede superar los 30 caracteres.');
            if ($areaId <= 0) throw new RuntimeException('Selecciona un área académica antes de guardar la asignatura.');
            $area = sgaAsignaturasExigirArea($conexion, $areaId);
            $jornadasElegidas=sgaAsignaturasValidarJornadas($_POST['jornadas']??[],$area,$jornadasOpciones);
            if ($accion === 'editar') {
                sgaAsignaturasExigirRegistro($conexion,$id);
                $q=$conexion->prepare('SELECT jornadas_ids FROM asignaturas WHERE id=? AND archivado_en IS NULL LIMIT 1');
                $q->bind_param('i',$id);$q->execute();$r=$q->get_result()->fetch_assoc();$q->close();
                if (!$r) throw new RuntimeException('Asignatura no encontrada.');
                sgaAsignaturasExigirSinUsoJornadasRetiradas($conexion,$id,sgaAreasJornadasDecodificar($r['jornadas_ids']),$jornadasElegidas);
            }
            $codigoDb = $codigo === '' ? null : $codigo;
            if (!$conexion->begin_transaction()) throw new RuntimeException('No se pudo iniciar la operacion.');
            try {
            if ($accion === 'crear') {
                $stmt = $conexion->prepare('INSERT INTO asignaturas (codigo,nombre,area_id,usa_literal_especial,solo_visor_comportamiento) VALUES (?,?,?,?,?)');
                $stmt->bind_param('ssiii',$codigoDb,$nombre,$areaId,$especial,$visorComportamiento);
                if (!$stmt->execute()) throw new RuntimeException($stmt->errno === 1062 ? 'Ya existe una asignatura con ese nombre o código.' : 'No fue posible crear la asignatura.');
                $id = (int)$conexion->insert_id;
                $stmt->close();
                sgaAsignaturasJornadasGuardar($conexion,$id,$jornadasElegidas);
                registrarAuditoria('CREATE','Asignaturas','asignatura',$id,'Asignatura creada y vinculada a un área.',null,null,
                    ['codigo'=>$codigoDb,'nombre'=>$nombre,'area_id'=>$areaId,'area'=>$area['nombre'],'usa_literal_especial'=>$especial,'solo_visor_comportamiento'=>$visorComportamiento,'jornadas'=>$jornadasElegidas,'activo'=>1]);
                flash('success','Asignatura creada en el área '. $area['nombre'] .'.');
            } else {
                if ($id <= 0) throw new RuntimeException('Asignatura inválida.');
                $stmt = $conexion->prepare('SELECT id,codigo,nombre,area_id,usa_literal_especial,solo_visor_comportamiento,activo FROM asignaturas WHERE id=? AND archivado_en IS NULL LIMIT 1');
                $stmt->bind_param('i',$id); $stmt->execute(); $antes = $stmt->get_result()->fetch_assoc(); $stmt->close();
                if (!$antes) throw new RuntimeException('Asignatura no encontrada.');
                $stmt = $conexion->prepare('UPDATE asignaturas SET codigo=?,nombre=?,area_id=?,usa_literal_especial=?,solo_visor_comportamiento=? WHERE id=?');
                $stmt->bind_param('ssiiii',$codigoDb,$nombre,$areaId,$especial,$visorComportamiento,$id);
                if (!$stmt->execute()) throw new RuntimeException($stmt->errno === 1062 ? 'Ya existe una asignatura con ese nombre o código.' : 'No fue posible actualizar la asignatura.');
                $stmt->close();
                sgaAsignaturasJornadasGuardar($conexion,$id,$jornadasElegidas);
                $despues = $antes; $despues['jornadas_ids']=implode(',',$jornadasElegidas); $despues['codigo'] = $codigoDb; $despues['nombre'] = $nombre;
                $despues['area_id'] = $areaId; $despues['usa_literal_especial'] = $especial; $despues['solo_visor_comportamiento'] = $visorComportamiento;
                registrarAuditoria('UPDATE','Asignaturas','asignatura',$id,'Asignatura y área actualizadas.',null,$antes,$despues,'exito',null,null,'advertencia');
                flash('success','Asignatura actualizada. Su área también se reflejará en los reportes.');
            }
            if (!$conexion->commit()) throw new RuntimeException('No se pudo guardar la seleccion de jornadas.');
            } catch(Throwable $e) { $conexion->rollback(); throw $e; }
        } elseif ($accion === 'toggle' || $accion === 'eliminar') {
            if ($id <= 0) throw new RuntimeException('Asignatura inválida.');
            sgaAsignaturasExigirRegistro($conexion, $id);
            $stmt = $conexion->prepare('SELECT id,codigo,nombre,area_id,usa_literal_especial,solo_visor_comportamiento,activo FROM asignaturas WHERE id=? AND archivado_en IS NULL LIMIT 1');
            $stmt->bind_param('i',$id); $stmt->execute(); $antes = $stmt->get_result()->fetch_assoc(); $stmt->close();
            if (!$antes) throw new RuntimeException('La asignatura no existe.');
            if ($accion === 'toggle') {
                $nuevo = (int)$antes['activo'] ? 0 : 1;
                if ($nuevo === 1) {
                    $stmt = $conexion->prepare('SELECT activo FROM areas WHERE id=? AND archivado_en IS NULL LIMIT 1');
                    $stmt->bind_param('i',$antes['area_id']); $stmt->execute(); $a = $stmt->get_result()->fetch_assoc(); $stmt->close();
                    if (!$a || (int)$a['activo'] !== 1) throw new RuntimeException('Activa primero el área académica de esta asignatura.');
                }
                $stmt = $conexion->prepare('UPDATE asignaturas SET activo=? WHERE id=?');
                $stmt->bind_param('ii',$nuevo,$id);
                if (!$stmt->execute()) throw new RuntimeException('No fue posible cambiar el estado.');
                $stmt->close();
                $despues = $antes; $despues['activo'] = $nuevo;
                registrarAuditoria('UPDATE','Asignaturas','asignatura',$id,$nuevo ? 'Asignatura activada.' : 'Asignatura desactivada.',null,$antes,$despues,'exito',null,null,'advertencia');
                flash('success',$nuevo ? 'Asignatura activada.' : 'Asignatura desactivada.');
            } else {
                $ocultados = sgaCatalogoArchivar(
                    $conexion, 'asignaturas', $id, (string)($_POST['confirmacion'] ?? '')
                );
                flash('success','Asignatura borrada del catálogo: su código y nombre ahora contienen [DELETE]. Se conservaron '.
                    (int)($ocultados['ofertas_conservadas'] ?? 0).' asignaciones y todos sus registros académicos, notas y asistencias.');
            }
        } else {
            throw new RuntimeException('Acción no reconocida.');
        }
    } catch (Throwable $e) {
        flash('error',$e->getMessage());
    }
    redir('modulos/asignaturas/index.php');
}

$editarId = (int)($_GET['editar'] ?? 0);
$editar = null;
if ($editarId > 0) {
    $stmt = $conexion->prepare('SELECT * FROM asignaturas WHERE id=? AND archivado_en IS NULL LIMIT 1');
    $stmt->bind_param('i',$editarId); $stmt->execute(); $editar = $stmt->get_result()->fetch_assoc() ?: null; $stmt->close();
}
// Solo se muestran areas de la jornada visible en el menu del Subadministrador.
// Si la migracion no existe, la vista no falla: se deshabilita la gestion.
$columnaJornadasArea = $areasJornadasInstaladas ? 'jornadas_ids' : 'NULL AS jornadas_ids';
$areas = $conexion->query('SELECT id,codigo,nombre,orden,activo,'.$columnaJornadasArea.' FROM areas WHERE archivado_en IS NULL AND codigo<>\'SGA_PARAM_AULA_INTERNO\' ORDER BY orden,nombre')->fetch_all(MYSQLI_ASSOC);
$areas = array_values(array_filter($areas, static function($a) use ($areasJornadasInstaladas) {
    return $areasJornadasInstaladas && sgaAsignaturasAreaVisible($a);
}));
$idsAreasVisibles = array_fill_keys(array_map('intval', array_column($areas, 'id')), true);
$areasActivas = array_filter($areas, static function($a) {return (int)$a['activo'] === 1;});
$areasPorId=[];foreach($areas as $ar) $areasPorId[(int)$ar['id']]=$ar;

$items = $conexion->query('SELECT s.*,a.nombre AS area,a.codigo AS area_codigo,a.activo AS area_activa,a.orden AS area_orden,(SELECT COUNT(*) FROM ofertas_academicas o WHERE o.asignatura_id=s.id) AS ofertas FROM asignaturas s JOIN areas a ON a.id=s.area_id WHERE s.archivado_en IS NULL AND a.archivado_en IS NULL AND COALESCE(s.codigo,\'\')<>\'SGA_PARAM_AULA_INTERNO\' ORDER BY a.orden,a.nombre,s.nombre')->fetch_all(MYSQLI_ASSOC);
$items = array_values(array_filter($items, static function($s) use ($idsAreasVisibles) {
    return isset($idsAreasVisibles[(int)$s['area_id']]);
}));
$otrasAsignaturas=[];
$itemsVisibles=[];
foreach($items as $item) {
    $ids=sgaAreasJornadasDecodificar((string)($item['jornadas_ids']??''));
    $item['ids_jornada']=$ids;
    $item['jornadas_label']=implode(' / ',array_map(static fn($j)=>$j['nombre'],array_values(array_filter($jornadasTodos,static fn($j)=>in_array((int)$j['id'],$ids,true))))) ?: 'Sin jornadas';
    $item['puede_editar']=esSuperadmin() || ($ids && !array_diff($ids,jornadasPermitidasPeriodo((int)(periodoActivo()['id']??0))));
    if (esSuperadmin() || array_intersect($ids,$jornadasEnVistaAsignaturas)) $itemsVisibles[]=$item;
    elseif (esSubadmin() && (int)$item['activo']===1 && (int)$item['area_activa']===1) $otrasAsignaturas[]=$item;
}
$items=$itemsVisibles;
if ($editar && !isset($idsAreasVisibles[(int)$editar['area_id']])) $editar = null;
// Cantidad real de materias seleccionadas en aulas de las jornadas visibles.
$usadas=[];$pid=(int)(periodoActivo()['id']??0);
if($pid>0 && $jornadasEnVistaAsignaturas){
 $q=$conexion->prepare('SELECT DISTINCT x.asignatura_id,au.jornada_id FROM (
 SELECT t.aula_periodo_id,t.asignatura_id FROM aula_asignaturas_seleccionadas t WHERE t.seleccionada=1
 UNION SELECT o.aula_periodo_id,o.asignatura_id FROM ofertas_academicas o WHERE o.activo=1
 ) x JOIN aulas_periodo ap ON ap.id=x.aula_periodo_id AND ap.activo=1 JOIN aulas au ON au.id=ap.aula_id WHERE ap.periodo_id=?');
 $q->bind_param('i',$pid);$q->execute();
 foreach($q->get_result()->fetch_all(MYSQLI_ASSOC) as $r){
    if(in_array((int)$r['jornada_id'],$jornadasEnVistaAsignaturas,true))$usadas[(int)$r['asignatura_id']]=true;
 }$q->close();
}
$filtrarArea = max(0,(int)($_GET['area_id'] ?? 0));
$buscar = trim((string)($_GET['buscar'] ?? ''));
$filtrados = array_values(array_filter($items,static function($s) use($filtrarArea,$buscar) {
    if ($filtrarArea > 0 && (int)$s['area_id'] !== $filtrarArea) return false;
    if ($buscar === '') return true;
    $texto = $s['nombre'].' '.$s['codigo'].' '.$s['area'];
    $acentos = ['á'=>'a','é'=>'e','í'=>'i','ó'=>'o','ú'=>'u','ü'=>'u','ñ'=>'n',
        'Á'=>'A','É'=>'E','Í'=>'I','Ó'=>'O','Ú'=>'U','Ü'=>'U','Ñ'=>'N'];
    return stripos(strtr($texto,$acentos), strtr($buscar,$acentos)) !== false;
}));
$tituloPagina = 'Asignaturas';
$subtituloPagina = 'Cada asignatura debe pertenecer a un área. Las áreas se administran antes de crear materias.';
require __DIR__ . '/../../partials/header.php';
?>
<?php if (!$areasJornadasInstaladas || !$asignaturasJornadasInstaladas): ?>
<div class="alert info">Ejecuta <code>sql/SQL_SGA_ASIGNATURAS_MULTI_JORNADA.sql</code> para activar las jornadas múltiples en las asignaturas; instala primero la migración de Áreas si aún no está aplicada.</div>
<?php elseif (!$areasActivas): ?>
<div class="alert info">No existen áreas activas para la jornada visible. <a href="<?= e(url('modulos/areas/index.php')) ?>">Revisa las jornadas asignadas a las áreas</a>.</div>
<?php endif; ?>
<script type="application/json" id="sga-area-jornadas-json"><?=json_encode(array_combine(array_map('strval',array_keys($areasPorId)),array_map(static fn($a)=>sgaAreasJornadasDecodificar($a['jornadas_ids']),array_values($areasPorId))),JSON_HEX_TAG|JSON_HEX_AMP|JSON_HEX_APOS|JSON_HEX_QUOT)?></script>
<link rel="stylesheet" href="<?=e(url('assets/css/sga_catalogo_modales.css'))?>?v=1625">
<script defer src="<?=e(url('assets/js/sga_catalogo_modales.js'))?>?v=1625"></script>
<div class="sga-cat-toolbar"><div><h2 class="sga-cat-toolbar-title">Asignaturas académicas</h2><small class="sga-cat-toolbar-sub">Cada asignatura pertenece a un área académica activa.</small></div>
<div class="actions"><a class="btn btn-secondary" href="<?=e(url('modulos/areas/index.php'))?>">Administrar áreas</a><button type="button" class="btn btn-primary" data-sga-cat-open="sga-cat-create" <?= !$areasJornadasInstaladas || !$asignaturasJornadasInstaladas || !$areasActivas ? 'disabled title="No existen areas activas autorizadas"' : '' ?>>+ Crear / importar asignaturas</button></div></div>
<dialog class="sga-cat-dialog" id="sga-cat-create" aria-labelledby="sga-cat-create-title">
<header class="sga-cat-dialog-head"><div><h2 id="sga-cat-create-title">Crear o importar asignaturas</h2><p>Selecciona cómo deseas registrar las asignaturas académicas.</p></div>
<button class="sga-cat-dialog-close" type="button" aria-label="Cerrar ventana" data-sga-cat-close>&times;</button></header>
<div class="sga-cat-tabs" role="tablist" aria-label="Método de registro">
<button type="button" class="sga-cat-tab" data-sga-cat-tab="crear" role="tab" id="sga-cat-tab-crear" aria-selected="true" aria-controls="sga-cat-panel-crear">Crear asignatura</button>
<button type="button" class="sga-cat-tab" data-sga-cat-tab="csv" role="tab" id="sga-cat-tab-csv" aria-selected="false" aria-controls="sga-cat-panel-csv" tabindex="-1">Importar CSV</button>
</div>
<div class="sga-cat-dialog-inner">
<section class="sga-cat-panel" data-sga-cat-panel="crear" id="sga-cat-panel-crear" role="tabpanel" aria-labelledby="sga-cat-tab-crear"><form method="post"><input type="hidden" name="csrf" value="<?=e($csrf)?>"><input type="hidden" name="accion" value="crear"><div class="form-grid cols-3"><label>Área académica<select name="area_id" required><option value="">Selecciona un área...</option>
<?php foreach ($areas as $a):?><option value="<?=(int)$a['id']?>" <?=!(int)$a['activo']?'disabled':''?>><?=e($a['nombre'])?><?=!(int)$a['activo']?' (inactiva)':''?></option><?php endforeach;?></select></label>
<label>Código de asignatura<input name="codigo" maxlength="30" placeholder="MAT"></label>
<label>Nombre de asignatura<input name="nombre" maxlength="150" placeholder="Matemática" required></label></div>
<fieldset class="sga-cat-form-fieldset sga-asig-jornadas" data-sga-asig-jornadas><legend>Jornadas de la asignatura (puedes marcar varias)</legend>
<p class="mini-note">Se habilitan solo las jornadas que también correspondan al área seleccionada.</p>
<div class="sga-asig-jornadas-grid">
<?php foreach($jornadasOpciones as $j): ?><label class="sga-asig-jornada-option"><input type="checkbox" name="jornadas[]" value="<?=(int)$j['id']?>"> <?=e($j['nombre'])?></label><?php endforeach; ?>
</div><small class="sga-asig-jornadas-count" aria-live="polite">Selecciona un área para activar las jornadas.</small></fieldset>
<fieldset class="sga-cat-form-fieldset"><legend>Configuración de calificaciones</legend>
<label class="sga-cat-checkbox"><input type="checkbox" name="especial" value="1"> Promedio y nota final en escala cualitativa (A+, A−, B+, B−).</label>
<label class="sga-cat-checkbox"><input type="checkbox" name="solo_visor_comportamiento" value="1"> Asignatura de comportamiento</label>

</fieldset><div class="sga-cat-actions"><button class="btn btn-secondary" type="button" data-sga-cat-close>Cancelar</button><button class="btn btn-primary" type="submit">Crear asignatura</button></div></form></section><section class="sga-cat-panel" data-sga-cat-panel="csv" id="sga-cat-panel-csv" role="tabpanel" aria-labelledby="sga-cat-tab-csv" hidden>
<p class="sga-cat-help">Columnas: codigo;nombre;area_codigo;usa_literal_especial;solo_visor_comportamiento;jornadas. Ejemplo de varias jornadas: MAT|VES.<br><strong>Formato:</strong> UTF-8, columnas separadas por <strong>;</strong>. Usa el código del área y 0 o 1 para las casillas.</p>
<p><a class="btn btn-secondary" href="?descargar_plantilla=csv">Descargar plantilla CSV (;)</a></p>
<p class="sga-cat-template-warning"><strong>Plantilla con ejemplo:</strong> reemplaza o elimina la fila de demostración antes de importar datos reales. El área debe estar activa y pertenecer a la jornada visible.</p>
<form method="post" enctype="multipart/form-data">
<input type="hidden" name="csrf" value="<?=e($csrf)?>"><input type="hidden" name="accion" value="importar_csv">
<label>Seleccionar archivo CSV<input type="file" name="archivo_csv" accept=".csv,text/csv" required></label>
<div class="mini-note">Hasta 1500 registros o 2 MB. Si hay un error, no se importa ninguna fila.</div>
<div class="sga-cat-actions"><button class="btn btn-secondary" type="button" data-sga-cat-close>Cancelar</button><button class="btn btn-primary" type="submit">Importar asignaturas</button></div>
</form></section></div></dialog>
<dialog class="sga-cat-dialog" id="sga-cat-edit" aria-labelledby="sga-cat-edit-title" data-sga-cat-singular="asignatura">
<header class="sga-cat-dialog-head"><div><h2 id="sga-cat-edit-title">Editar asignatura</h2><p>Edita los campos del registro seleccionado.</p></div>
<button class="sga-cat-dialog-close" type="button" aria-label="Cerrar ventana" data-sga-cat-close>&times;</button></header>
<div class="sga-cat-dialog-inner">
<form method="post" data-sga-cat-edit-form><input type="hidden" name="csrf" value="<?=e($csrf)?>"><input type="hidden" name="accion" value="editar"><input type="hidden" name="id" value=""><div class="form-grid cols-3"><label>Área académica<select name="area_id" required><option value="">Selecciona un área...</option>
<?php foreach ($areas as $a):?><option value="<?=(int)$a['id']?>" <?=!(int)$a['activo']?'disabled':''?>><?=e($a['nombre'])?><?=!(int)$a['activo']?' (inactiva)':''?></option><?php endforeach;?></select></label>
<label>Código de asignatura<input name="codigo" maxlength="30" placeholder="MAT"></label>
<label>Nombre de asignatura<input name="nombre" maxlength="150" placeholder="Matemática" required></label></div>
<fieldset class="sga-cat-form-fieldset sga-asig-jornadas" data-sga-asig-jornadas><legend>Jornadas de la asignatura (puedes marcar varias)</legend>
<p class="mini-note">Se habilitan solo las jornadas que también correspondan al área seleccionada.</p>
<div class="sga-asig-jornadas-grid">
<?php foreach($jornadasOpciones as $j): ?><label class="sga-asig-jornada-option"><input type="checkbox" name="jornadas[]" value="<?=(int)$j['id']?>"> <?=e($j['nombre'])?></label><?php endforeach; ?>
</div><small class="sga-asig-jornadas-count" aria-live="polite">Selecciona un área para activar las jornadas.</small></fieldset>
<fieldset class="sga-cat-form-fieldset"><legend>Configuración de calificaciones</legend>
<label class="sga-cat-checkbox"><input type="checkbox" name="especial" value="1"> Promedio y nota final en escala cualitativa (A+, A−, B+, B−).</label>
<label class="sga-cat-checkbox"><input type="checkbox" name="solo_visor_comportamiento" value="1"> Asignatura de comportamiento</label>

</fieldset><div class="sga-cat-actions"><button class="btn btn-secondary" type="button" data-sga-cat-close>Cancelar</button><button class="btn btn-primary" type="submit">Guardar cambios</button></div></form></div></dialog>
<h2 class="section-title">Asignaturas disponibles (<?= count($filtrados) ?>)</h2>
<p class="mini-note"><?=count($usadas)?> asignaturas utilizadas en aulas del período y jornadas visibles. Una materia usada en varias aulas cuenta una sola vez.</p>
<section class="card" style="margin-bottom:12px"><form method="get" class="form-grid cols-3">
  <label>Buscar asignatura<input name="buscar" value="<?= e($buscar) ?>" placeholder="Nombre o código"></label>
  <label>Filtrar por área<select name="area_id"><option value="0">Todas las áreas</option><?php foreach ($areas as $a): ?><option value="<?= (int)$a['id'] ?>" <?= $filtrarArea === (int)$a['id'] ? 'selected' : '' ?>><?= e($a['nombre']) ?></option><?php endforeach; ?></select></label>
  <div class="form-actions"><button class="btn btn-primary">Filtrar</button><a class="btn btn-secondary" href="<?= e(url('modulos/asignaturas/index.php')) ?>">Limpiar</a></div>
</form></section>
<div class="table-wrap"><table class="table table-responsive-cards"><thead><tr><th>Código</th><th>Asignatura</th><th>Área académica</th><th>Jornadas</th><th>Calificación</th><th>Estado</th><th>Acciones</th></tr></thead><tbody>
<?php if (!$filtrados): ?><tr><td colspan="7" class="empty">No existen asignaturas para los filtros seleccionados.</td></tr><?php endif; ?>
<?php foreach ($filtrados as $s): ?>
<tr>
  <td><?= e($s['codigo'] ?? '') ?></td><td><strong><?= e($s['nombre']) ?></strong></td>
  <td><?= e($s['area']) ?></td><td><?=e($s['jornadas_label'])?></td><td><?= !empty($s['solo_visor_comportamiento']) ? 'Asignatura de comportamiento' : ($s['usa_literal_especial'] ? 'Cualitativa desde nota numérica' : 'Numérica 0–10') ?></td>
  <td><span class="badge <?= $s['activo'] ? 'good' : 'bad' ?>"><?= $s['activo'] ? 'Activa' : 'Inactiva' ?></span></td>
  <td><div class="actions">
    <?php if($s['puede_editar']): ?><a class="btn btn-sm btn-secondary" href="?editar=<?= (int)$s['id'] ?>" data-sga-cat-edit='<?=e(json_encode(array_merge($s,['especial'=>$s['usa_literal_especial']]),JSON_UNESCAPED_UNICODE|JSON_HEX_TAG|JSON_HEX_AMP|JSON_HEX_APOS|JSON_HEX_QUOT))?>' >Editar</a>
    <form method="post"><input type="hidden" name="csrf" value="<?= e($csrf) ?>"><input type="hidden" name="accion" value="toggle"><input type="hidden" name="id" value="<?= (int)$s['id'] ?>"><button class="btn btn-sm <?= $s['activo'] ? 'btn-secondary' : 'btn-success' ?>" data-confirm="¿Cambiar el estado de esta asignatura?" <?= !$s['activo'] && !(int)$s['area_activa'] ? 'disabled title="Activa primero el área"' : '' ?>><?= $s['activo'] ? 'Desactivar' : 'Activar' ?></button></form>
    <button type="button" class="btn btn-sm btn-danger" data-sga-cat-open="sga-cat-delete" data-sga-cat-delete-id="<?= (int)$s['id'] ?>" data-sga-cat-delete-name="<?= e($s['nombre']) ?>" data-sga-cat-delete-ofertas="<?= (int)$s['ofertas'] ?>">Borrar</button><?php else: ?><span class="mini-note">Solo consulta; asignatura compartida</span><?php endif; ?>
  </div></td>
</tr>
<?php endforeach; ?>
</tbody></table></div>
<?php if($otrasAsignaturas): ?>
<section class="card" style="margin-top:18px"><h2 class="section-title">Asignaturas disponibles para habilitar en tu jornada</h2>
<p class="mini-note">Se comparte la asignatura existente sin duplicar el catálogo ni modificar la configuración de otras jornadas.</p>
<div class="table-wrap"><table class="table"><thead><tr><th>Asignatura</th><th>Área</th><th>Jornadas actuales</th><th>Acción</th></tr></thead><tbody>
<?php foreach($otrasAsignaturas as $otra): ?><tr><td><?=e($otra['nombre'])?></td><td><?=e($otra['area'])?></td><td><?=e($otra['jornadas_label'])?></td><td>
<?php foreach($jornadasOpciones as $j): ?><?php if(in_array((int)$j['id'],$jornadasEnVistaAsignaturas,true) && in_array((int)$j['id'],sgaAreasJornadasDecodificar($areasPorId[(int)$otra['area_id']]['jornadas_ids']??''),true)): ?>
<form method="post" style="display:inline-block"><input type="hidden" name="csrf" value="<?=e($csrf)?>"><input type="hidden" name="accion" value="habilitar_jornada"><input type="hidden" name="id" value="<?=(int)$otra['id']?>"><input type="hidden" name="jornada_id" value="<?=(int)$j['id']?>"><button type="submit" class="btn btn-sm btn-secondary" data-confirm="¿Habilitar asignatura en <?=e($j['nombre'])?>?">Habilitar en <?=e($j['nombre'])?></button></form>
<?php endif; ?><?php endforeach; ?></td></tr><?php endforeach; ?>
</tbody></table></div></section>
<?php endif; ?>
<dialog class="sga-cat-dialog" id="sga-cat-delete" aria-labelledby="sga-cat-delete-title">
<header class="sga-cat-dialog-head"><div><h2 id="sga-cat-delete-title">Borrar asignatura del catálogo</h2><p>Se ocultará sin eliminar el historial almacenado. Su código y nombre pasarán a tener el sufijo [DELETE].</p></div>
<button class="sga-cat-dialog-close" type="button" aria-label="Cerrar ventana" data-sga-cat-close>&times;</button></header>
<div class="sga-cat-dialog-inner">
<p><strong id="sga-cat-delete-nombre"></strong></p>
<p>La asignatura dejará de aparecer en los listados y no estará disponible para nuevas asignaciones a docentes o aulas.</p>
<p id="sga-cat-delete-cantidades" class="mini-note"></p>
<div class="alert info" role="note"><strong>Conservación de datos:</strong> la asignatura, sus asignaciones en aulas, las calificaciones, los supletorios y las asistencias seguirán en la base de datos para fines históricos y de auditoría.</div>
<form method="post" id="sga-cat-delete-form">
<input type="hidden" name="csrf" value="<?=e($csrf)?>">
<input type="hidden" name="accion" value="eliminar">
<input type="hidden" name="id" value="">
<label>Para confirmar, escribe <strong>ELIMINAR</strong>:
<input type="text" name="confirmacion" autocomplete="off" pattern="ELIMINAR" placeholder="ELIMINAR" required></label>
<div class="sga-cat-actions"><button class="btn btn-secondary" type="button" data-sga-cat-close>Cancelar</button><button class="btn btn-danger" type="submit">Borrar del catálogo</button></div>
</form></div></dialog>
<script>
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
      cantidades.textContent = 'Asignaciones en aulas: ' + (boton.dataset.sgaCatDeleteOfertas || '0') + '.';
      confirmar.value = '';
    });
  });
})();
</script>
<style>
.sga-asig-jornadas-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(155px,1fr));gap:7px;margin:8px 0}
.sga-cat-dialog .sga-asig-jornada-option{display:flex;flex-direction:row;align-items:center;gap:9px;background:#f5f9ff;border:1px solid #d4e2f4;border-radius:8px;padding:10px;margin:0;color:#193e65;font-weight:700}
.sga-cat-dialog .sga-asig-jornada-option input{margin:0;width:17px;height:17px;accent-color:#145796}
.sga-cat-dialog .sga-asig-jornada-option:has(input:checked){border-color:#75a3d8;background:#e7f3ff}
.sga-cat-dialog .sga-asig-jornada-option:has(input:disabled){opacity:.46}
.sga-asig-jornadas-count{font-weight:600;color:#375c7e}
</style>
<script>
document.addEventListener('DOMContentLoaded',()=>{
 const areas=JSON.parse(document.getElementById('sga-area-jornadas-json').textContent);
 const sync=form=>{
   if(!form) return;
   const id=form.querySelector('select[name="area_id"]')?.value||'';
   const permitidas=new Set((areas[id]||[]).map(String));
   const checks=Array.from(form.querySelectorAll('input[name="jornadas[]"]'));
   checks.forEach(c=>{
     const enable=permitidas.has(c.value);
     if(!enable)c.checked=false;
     c.disabled=!enable;
   });
   const num=checks.filter(c=>c.checked).length;
   const contador=form.querySelector('.sga-asig-jornadas-count');
   if(contador)contador.textContent=num+' jornada(s) seleccionada(s)';
 };
 document.querySelectorAll('.sga-cat-dialog form:has([data-sga-asig-jornadas])').forEach(form=>{
   form.querySelector('select[name="area_id"]')?.addEventListener('change',()=>sync(form));
   form.querySelectorAll('input[name="jornadas[]"]').forEach(c=>c.addEventListener('change',()=>sync(form)));
   form.addEventListener('submit',ev=>{
      sync(form);
      if(Array.from(form.querySelectorAll('input[name="jornadas[]"]')).some(c=>c.checked&&!c.disabled))return;
      ev.preventDefault();window.alert('Selecciona al menos una jornada de la asignatura.');
   });
   sync(form);
 });
 document.querySelectorAll('[data-sga-cat-edit]').forEach(b=>b.addEventListener('click',()=>{
   const form=document.querySelector('#sga-cat-edit form');
   try{
     const datos=JSON.parse(b.dataset.sgaCatEdit);
     sync(form);
     const valores=new Set((datos.ids_jornada||[]).map(String));
     form.querySelectorAll('input[name="jornadas[]"]').forEach(c=>c.checked=!c.disabled&&valores.has(c.value));
     sync(form);
   }catch(e){console.error('Jornadas de asignatura',e);}
 }));
});
</script>


<?php require __DIR__ . '/../../partials/footer.php'; ?>
