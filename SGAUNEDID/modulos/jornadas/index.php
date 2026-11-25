<?php
/** Catálogo de jornadas. Las aulas existentes quedan sin jornada hasta que se configuren. */
require_once __DIR__ . '/../../lib/funciones.php';
exigirAdminAcademico();
require_once __DIR__ . '/../../lib/sga_catalogos_csv.php';
if (isset($_GET['descargar_plantilla']) && $_GET['descargar_plantilla'] === 'csv') sgaCatalogoCsvDescargarPlantilla('jornadas');

if (empty($_SESSION['csrf_jornadas'])) $_SESSION['csrf_jornadas'] = bin2hex(random_bytes(24));
$csrf = $_SESSION['csrf_jornadas'];
$periodoJornadas=(int)(periodoActivo()['id']??0);
if(esSubadmin()) exigirAccesoPeriodo($periodoJornadas);
$permitidasJornadas=esSubadmin()?jornadasPermitidasPeriodo($periodoJornadas):[];
$editarId = max(0, (int)($_GET['editar'] ?? 0));

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    try {
        if (!hash_equals($csrf, (string)($_POST['csrf'] ?? ''))) throw new RuntimeException('La sesión del formulario caducó.');
        $accion = (string)($_POST['accion'] ?? '');
        $id = (int)($_POST['id'] ?? 0);
        if(esSubadmin()){
            if($accion!=='editar') throw new RuntimeException('La creación y desactivación de jornadas corresponde al Administrador principal.');
            if(!puedeAccederJornada($id,$periodoJornadas)) throw new RuntimeException('Jornada no autorizada.');
        }
        if ($accion === 'importar_csv') {
            $nuevos = sgaCatalogoCsvImportar($conexion, 'jornadas');
            flash('success', 'Se importaron '.$nuevos.' jornadas correctamente.');
        } elseif ($accion === 'crear' || $accion === 'editar') {
            $codigo = strtoupper(trim((string)($_POST['codigo'] ?? '')));
            $nombre = trim((string)($_POST['nombre'] ?? ''));
            $nombre = preg_replace('/\s+/u',' ',$nombre) ?: $nombre;
            $orden = filter_var($_POST['orden'] ?? '', FILTER_VALIDATE_INT);
            if (!preg_match('/^[A-Z0-9_-]{2,30}$/D', $codigo)) throw new RuntimeException('Código inválido: usa de 2 a 30 letras, números o guiones.');
            if ($nombre === '' || strlen($nombre) > 100) throw new RuntimeException('El nombre de la jornada es obligatorio (máximo 100 caracteres).');
            if ($orden === false || $orden < 1 || $orden > 9999) throw new RuntimeException('El orden debe estar entre 1 y 9999.');
            if ($accion === 'crear') {
                $s=$conexion->prepare('INSERT INTO jornadas (codigo,nombre,orden) VALUES (?,?,?)');
                $s->bind_param('ssi',$codigo,$nombre,$orden);
                if (!$s->execute()) throw new RuntimeException($s->errno===1062?'Ya existe esa jornada o código.':'Error al crear la jornada.');
                $id=(int)$conexion->insert_id; $s->close();
                registrarAuditoria('CREATE','Jornadas','jornada',$id,'Jornada creada.',null,null,['codigo'=>$codigo,'nombre'=>$nombre,'orden'=>$orden]);
                flash('success','Jornada creada. Ya puedes asignarla a las aulas.');
            } else {
                $s=$conexion->prepare('SELECT * FROM jornadas WHERE id=?');$s->bind_param('i',$id);$s->execute();$antes=$s->get_result()->fetch_assoc();$s->close();
                if (!$antes) throw new RuntimeException('Jornada inexistente.');
                $s=$conexion->prepare('UPDATE jornadas SET codigo=?,nombre=?,orden=? WHERE id=?');$s->bind_param('ssii',$codigo,$nombre,$orden,$id);
                if (!$s->execute()) throw new RuntimeException($s->errno===1062?'Ya existe esa jornada o código.':'Error al actualizar la jornada.');
                $s->close();$despues=$antes;$despues['codigo']=$codigo;$despues['nombre']=$nombre;$despues['orden']=$orden;
                registrarAuditoria('UPDATE','Jornadas','jornada',$id,'Jornada actualizada.',null,$antes,$despues,'exito',null,null,'advertencia');
                flash('success','Jornada actualizada.');
            }
        } elseif ($accion==='toggle' || $accion==='eliminar') {
            $s=$conexion->prepare('SELECT * FROM jornadas WHERE id=?');$s->bind_param('i',$id);$s->execute();$antes=$s->get_result()->fetch_assoc();$s->close();
            if (!$antes) throw new RuntimeException('Jornada inexistente.');
            $s=$conexion->prepare('SELECT COUNT(*) total,COALESCE(SUM(activo=1),0) activas FROM aulas WHERE jornada_id=?');$s->bind_param('i',$id);$s->execute();$dep=$s->get_result()->fetch_assoc();$s->close();
            if ($accion === 'toggle') {
                $nuevo=(int)$antes['activo']===1?0:1;
                if (!$nuevo && (int)$dep['activas']>0) throw new RuntimeException('Hay aulas activas con esta jornada. Reasígnalas antes de desactivarla.');
                $s=$conexion->prepare('UPDATE jornadas SET activo=? WHERE id=?');$s->bind_param('ii',$nuevo,$id);$s->execute();$s->close();
                registrarAuditoria('UPDATE','Jornadas','jornada',$id,'Estado de jornada actualizado.',null,$antes,['activo'=>$nuevo]);
                flash('success',$nuevo?'Jornada activada.':'Jornada desactivada.');
            } else {
                if ((int)$dep['total']>0) throw new RuntimeException('No puedes eliminar una jornada asignada a un aula.');
                $s=$conexion->prepare('SELECT (SELECT COUNT(*) FROM subadministrador_jornadas WHERE jornada_id=?)+(SELECT COUNT(*) FROM usuarios_jornadas_gestion WHERE jornada_id=?) total');
                $s->bind_param('ii',$id,$id);$s->execute();$usos=(int)$s->get_result()->fetch_assoc()['total'];$s->close();
                if($usos>0)throw new RuntimeException('Esta jornada tiene permisos de subadministradores o usuarios asociados. Reasígnalos antes de eliminarla.');
                $s=$conexion->prepare('DELETE FROM jornadas WHERE id=?');$s->bind_param('i',$id);$s->execute();$s->close();
                registrarAuditoria('DELETE','Jornadas','jornada',$id,'Jornada sin aulas eliminada.',null,$antes,null,'exito',null,null,'critica');
                flash('success','Jornada eliminada.');
            }
        } else throw new RuntimeException('Acción no reconocida.');
    } catch (Throwable $e) { flash('error',$e->getMessage()); }
    redir('modulos/jornadas/index.php');
}

$editar=null;
if ($editarId>0 && esSubadmin()) exigirAccesoJornada($editarId,$periodoJornadas);
if ($editarId>0) {$s=$conexion->prepare('SELECT * FROM jornadas WHERE id=?');$s->bind_param('i',$editarId);$s->execute();$editar=$s->get_result()->fetch_assoc()?:null;$s->close();}
$jornadas=$conexion->query('SELECT j.*,COUNT(a.id) total_aulas,COALESCE(SUM(a.activo=1),0) aulas_activas FROM jornadas j LEFT JOIN aulas a ON a.jornada_id=j.id'.(esSubadmin()?' WHERE j.id IN ('.implode(',',$permitidasJornadas?:[0]).')':'').' GROUP BY j.id ORDER BY j.orden,j.nombre')->fetch_all(MYSQLI_ASSOC);
$siguiente=1;foreach ($jornadas as $j) $siguiente=max($siguiente,(int)$j['orden']+1);
$sinJornada=(int)$conexion->query('SELECT COUNT(*) n FROM aulas WHERE jornada_id IS NULL')->fetch_assoc()['n'];
$tituloPagina='Jornadas académicas';$subtituloPagina='Crea las jornadas antes de asignarlas a las aulas y paralelos.';require __DIR__.'/../../partials/header.php';
?>
<link rel="stylesheet" href="<?=e(url('assets/css/sga_catalogo_modales.css'))?>?v=1625">
<script defer src="<?=e(url('assets/js/sga_catalogo_modales.js'))?>?v=1625"></script>
<div class="sga-cat-metrics" aria-label="Resumen de jornadas"><span><strong><?=count($jornadas)?></strong> jornadas registradas</span><?php if(esSuperadmin()):?><span><strong><?=$sinJornada?></strong> aulas por configurar</span><?php endif;?><span><strong><?=count(array_filter($jornadas,static fn($j)=>(int)$j['activo']===1))?></strong> jornadas activas</span></div>
<div class="sga-cat-toolbar"><div><h2 class="sga-cat-toolbar-title">Catálogo de jornadas</h2><small class="sga-cat-toolbar-sub">Jornadas disponibles y cantidad de aulas asociadas.</small></div>
<div class="actions"><a class="btn btn-secondary" href="<?=e(url('modulos/aulas/index.php'))?>">Ir a Aulas</a><?php if(esSuperadmin()):?><button class="btn btn-primary" type="button" data-sga-cat-open="sga-cat-create">+ Crear / importar jornadas</button><?php endif;?></div></div>
<?php if(esSuperadmin()):?>
<dialog class="sga-cat-dialog" id="sga-cat-create" aria-labelledby="sga-cat-create-title">
<header class="sga-cat-dialog-head"><div><h2 id="sga-cat-create-title">Crear o importar jornadas</h2><p>Selecciona cómo deseas registrar las jornadas académicas.</p></div>
<button class="sga-cat-dialog-close" type="button" aria-label="Cerrar ventana" data-sga-cat-close>&times;</button></header>
<div class="sga-cat-tabs" role="tablist" aria-label="Método de registro">
<button type="button" class="sga-cat-tab" data-sga-cat-tab="crear" role="tab" id="sga-cat-tab-crear" aria-selected="true" aria-controls="sga-cat-panel-crear">Crear jornada</button>
<button type="button" class="sga-cat-tab" data-sga-cat-tab="csv" role="tab" id="sga-cat-tab-csv" aria-selected="false" aria-controls="sga-cat-panel-csv" tabindex="-1">Importar CSV</button>
</div>
<div class="sga-cat-dialog-inner">
<section class="sga-cat-panel" data-sga-cat-panel="crear" id="sga-cat-panel-crear" role="tabpanel" aria-labelledby="sga-cat-tab-crear"><form method="post"><input type="hidden" name="csrf" value="<?=e($csrf)?>"><input type="hidden" name="accion" value="crear"><div class="form-grid cols-3"><label>Código<input name="codigo" required maxlength="30" pattern="[A-Za-z0-9_-]{2,30}" placeholder="MAT"></label><label>Nombre<input name="nombre" required maxlength="100" placeholder="MATUTINA"></label><label>Orden<input name="orden" type="number" min="1" max="9999" required value="<?=$siguiente?>"></label></div><div class="sga-cat-actions"><button class="btn btn-secondary" type="button" data-sga-cat-close>Cancelar</button><button class="btn btn-primary" type="submit">Crear jornada</button></div></form></section><section class="sga-cat-panel" data-sga-cat-panel="csv" id="sga-cat-panel-csv" role="tabpanel" aria-labelledby="sga-cat-tab-csv" hidden>
<p class="sga-cat-help">Columnas: codigo;nombre;orden.<br><strong>Formato:</strong> UTF-8, columnas separadas por <strong>;</strong>. Utiliza el código para asociar aulas en futuras importaciones.</p>
<p><a class="btn btn-secondary" href="?descargar_plantilla=csv">Descargar plantilla CSV (;)</a></p>
<p class="sga-cat-template-warning"><strong>Plantilla con ejemplo:</strong> reemplaza o elimina la fila de demostración antes de importar datos reales.</p>
<form method="post" enctype="multipart/form-data">
<input type="hidden" name="csrf" value="<?=e($csrf)?>"><input type="hidden" name="accion" value="importar_csv">
<label>Seleccionar archivo CSV<input type="file" name="archivo_csv" accept=".csv,text/csv" required></label>
<div class="mini-note">Hasta 1500 registros o 2 MB. Si hay un error, no se importa ninguna fila.</div>
<div class="sga-cat-actions"><button class="btn btn-secondary" type="button" data-sga-cat-close>Cancelar</button><button class="btn btn-primary" type="submit">Importar jornadas</button></div>
</form></section></div></dialog>
<?php endif;?>
<dialog class="sga-cat-dialog" id="sga-cat-edit" aria-labelledby="sga-cat-edit-title" data-sga-cat-singular="jornada">
<header class="sga-cat-dialog-head"><div><h2 id="sga-cat-edit-title">Editar jornada</h2><p>Modifica la jornada seleccionada.</p></div>
<button class="sga-cat-dialog-close" type="button" aria-label="Cerrar ventana" data-sga-cat-close>&times;</button></header>
<div class="sga-cat-dialog-inner">
<form method="post" data-sga-cat-edit-form><input type="hidden" name="csrf" value="<?=e($csrf)?>"><input type="hidden" name="accion" value="editar"><input type="hidden" name="id" value=""><div class="form-grid cols-3"><label>Código<input name="codigo" required maxlength="30" pattern="[A-Za-z0-9_-]{2,30}" placeholder="MAT"></label><label>Nombre<input name="nombre" required maxlength="100" placeholder="MATUTINA"></label><label>Orden<input name="orden" type="number" min="1" max="9999" required value=""></label></div><div class="sga-cat-actions"><button class="btn btn-secondary" type="button" data-sga-cat-close>Cancelar</button><button class="btn btn-primary" type="submit">Guardar cambios</button></div></form></div></dialog>
<div class="table-wrap"><table class="table table-responsive-cards"><thead><tr><th>Orden</th><th>Código</th><th>Jornada</th><th>Aulas</th><th>Estado</th><th>Acciones</th></tr></thead><tbody>
<?php foreach ($jornadas as $j):?><tr><td><?=(int)$j['orden']?></td><td><?=e($j['codigo'])?></td><td><strong><?=e($j['nombre'])?></strong></td><td><?=(int)$j['total_aulas']?></td><td><span class="badge <?=$j['activo']?'good':'bad'?>"><?=$j['activo']?'Activa':'Inactiva'?></span></td><td><div class="actions"><a class="btn btn-sm btn-secondary" href="?editar=<?=(int)$j['id']?>" data-sga-cat-edit='<?=e(json_encode($j,JSON_UNESCAPED_UNICODE|JSON_HEX_TAG|JSON_HEX_AMP|JSON_HEX_APOS|JSON_HEX_QUOT))?>' >Editar</a>
<?php if(esSuperadmin()):?>
<form method="post"><input type="hidden" name="csrf" value="<?=e($csrf)?>"><input type="hidden" name="accion" value="toggle"><input type="hidden" name="id" value="<?=(int)$j['id']?>"><button class="btn btn-sm <?=$j['activo']?'btn-secondary':'btn-success'?>" data-confirm="¿Cambiar el estado de la jornada?" <?=$j['activo']&&(int)$j['aulas_activas']>0?'disabled':''?>><?=$j['activo']?'Desactivar':'Activar'?></button></form>
<form method="post"><input type="hidden" name="csrf" value="<?=e($csrf)?>"><input type="hidden" name="accion" value="eliminar"><input type="hidden" name="id" value="<?=(int)$j['id']?>"><button class="btn btn-sm btn-danger" data-confirm="¿Eliminar la jornada?" <?=(int)$j['total_aulas']>0?'disabled':''?>>Eliminar</button></form>
<?php endif;?>
</div></td></tr><?php endforeach; ?></tbody></table></div>
<?php require __DIR__.'/../../partials/footer.php'; ?>
