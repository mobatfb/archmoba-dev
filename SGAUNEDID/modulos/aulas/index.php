<?php
require_once __DIR__.'/../../lib/funciones.php';
exigirAdminAcademico();
require_once __DIR__ . '/../../lib/sga_catalogos_csv.php';
if (isset($_GET['descargar_plantilla']) && $_GET['descargar_plantilla'] === 'csv') sgaCatalogoCsvDescargarPlantilla('aulas');

if (empty($_SESSION['csrf_aulas_jornada'])) $_SESSION['csrf_aulas_jornada']=bin2hex(random_bytes(24));
$csrf=$_SESSION['csrf_aulas_jornada'];
$periodoAulas=(int)(periodoActivo()['id']??0);
if(esSubadmin()) exigirAccesoPeriodo($periodoAulas);
$idsAulasPermitidas=esSubadmin()?jornadasPermitidasPeriodo($periodoAulas):[];
// Filtro de visualización: no cambia la jornada asignada a ninguna aula.
// Se valida contra las jornadas reales para evitar valores arbitrarios en la URL.
$jornadasSQL='SELECT id,codigo,nombre,activo FROM jornadas';
if(esSubadmin())$jornadasSQL.=' WHERE id IN ('.implode(',',$idsAulasPermitidas?:[0]).')';
$jornadas=$conexion->query($jornadasSQL.' ORDER BY orden,nombre')->fetch_all(MYSQLI_ASSOC);
$filtroJornada=0;
$parametroJornada=$_GET['jornada']??'';
if (is_string($parametroJornada) && ctype_digit($parametroJornada)) {
    $jornadaSolicitada=(int)$parametroJornada;
    foreach ($jornadas as $jornadaCatalogo) {
        if ((int)$jornadaCatalogo['id']===$jornadaSolicitada) {
            $filtroJornada=$jornadaSolicitada;
            break;
        }
    }
}
$editarId=max(0,(int)($_GET['editar']??0));
$editar=null;
if ($editarId && esSubadmin()) exigirAccesoAula($editarId,$periodoAulas);
if ($editarId){$s=$conexion->prepare('SELECT * FROM aulas WHERE id=? LIMIT 1');$s->bind_param('i',$editarId);$s->execute();$editar=$s->get_result()->fetch_assoc()?:null;$s->close();}
if ($_SERVER['REQUEST_METHOD']==='POST') {
    try {
        if (!hash_equals($csrf,(string)($_POST['csrf']??''))) throw new RuntimeException('La sesión del formulario caducó. Actualiza la página.');
        $accion=(string)($_POST['accion']??'');
        if ($accion==='importar_csv') {
            $nuevos = sgaCatalogoCsvImportar($conexion, 'aulas');
            flash('success', 'Se importaron '.$nuevos.' aulas correctamente.');
        } elseif ($accion==='crear'||$accion==='editar') {
            $codigo=trim((string)($_POST['codigo']??''));$nivel=trim((string)($_POST['nivel']??''));
            $nombre=trim((string)($_POST['nombre']??''));$par=trim((string)($_POST['paralelo']??''));
            $jornadaId=(int)($_POST['jornada_id']??0);
            $orden=filter_var($_POST['orden']??'999',FILTER_VALIDATE_INT);
            $resultadoCualitativoPost=(string)($_POST['resultados_cualitativos']??'0');
            if (!in_array($resultadoCualitativoPost, ['0','1'], true)) {
                throw new RuntimeException('El campo Resultados cualitativos debe ser Sí o No.');
            }
            $resultadosCualitativos=(int)$resultadoCualitativoPost;
            $porParametros=isset($_POST['evaluacion_cualitativa_parametros'])?1:0;
            if($orden===false||$orden<1||$orden>9999) throw new RuntimeException('El orden debe ser un entero del 1 al 9999.');
            if ($nivel===''||$nombre===''||$par==='') throw new RuntimeException('Nivel, curso y paralelo son obligatorios.');
            if (!$jornadaId) throw new RuntimeException('Selecciona una jornada académica para el aula.');
            if(esSubadmin()) exigirAccesoJornada($jornadaId,$periodoAulas);
            $s=$conexion->prepare('SELECT id FROM jornadas WHERE id=? AND activo=1');$s->bind_param('i',$jornadaId);$s->execute();$valida=$s->get_result()->fetch_assoc();$s->close();
            if (!$valida) throw new RuntimeException('La jornada seleccionada no existe o está inactiva.');
            $codigoDb=$codigo!==''?$codigo:null;
            if ($accion==='crear') {
                $s=$conexion->prepare('INSERT INTO aulas (codigo,nivel,nombre,paralelo,jornada_id,orden,resultados_cualitativos,evaluacion_cualitativa_parametros) VALUES (?,?,?,?,?,?,?,?)');
                $s->bind_param('ssssiiii',$codigoDb,$nivel,$nombre,$par,$jornadaId,$orden,$resultadosCualitativos,$porParametros);
                if (!$s->execute()) throw new RuntimeException($s->errno===1062?'Ya existe un aula con ese código o combinación de nivel, curso y paralelo.':'No fue posible crear el aula.');
                $id=(int)$conexion->insert_id;$s->close();
                registrarAuditoria('CREATE','Aulas','aula',$id,'Aula/paralelo creado con jornada.',null,null,['codigo'=>$codigoDb,'nivel'=>$nivel,'nombre'=>$nombre,'paralelo'=>$par,'jornada_id'=>$jornadaId,'orden'=>$orden,'resultados_cualitativos'=>$resultadosCualitativos,'evaluacion_cualitativa_parametros'=>$porParametros,'activo'=>1]);
                flash('success','Aula creada y vinculada a una jornada.');
            } else {
                $id=(int)($_POST['id']??0);$s=$conexion->prepare('SELECT * FROM aulas WHERE id=?');$s->bind_param('i',$id);$s->execute();$antes=$s->get_result()->fetch_assoc();$s->close();
                if (!$antes) throw new RuntimeException('Aula no encontrada.');
                if(esSubadmin()) exigirAccesoAula($id,$periodoAulas);
                if(!$conexion->begin_transaction())throw new RuntimeException('No fue posible iniciar el cambio de modalidad.');
                sgaParametrosActualizarModoAula($conexion,$id,$periodoAulas,$porParametros);
                $s=$conexion->prepare('UPDATE aulas SET codigo=?,nivel=?,nombre=?,paralelo=?,jornada_id=?,orden=?,resultados_cualitativos=?,evaluacion_cualitativa_parametros=? WHERE id=?');
                $s->bind_param('ssssiiiii',$codigoDb,$nivel,$nombre,$par,$jornadaId,$orden,$resultadosCualitativos,$porParametros,$id);
                if (!$s->execute()) throw new RuntimeException($s->errno===1062?'Ya existe un aula con ese código o combinación de nivel, curso y paralelo.':'No fue posible actualizar el aula.');
                $s->close();$despues=$antes;foreach (['codigo'=>$codigoDb,'nivel'=>$nivel,'nombre'=>$nombre,'paralelo'=>$par,'jornada_id'=>$jornadaId,'orden'=>$orden,'resultados_cualitativos'=>$resultadosCualitativos,'evaluacion_cualitativa_parametros'=>$porParametros] as $k=>$v) $despues[$k]=$v;
                registrarAuditoria('UPDATE','Aulas','aula',$id,'Aula y jornada actualizadas.',null,$antes,$despues,'exito',null,null,'advertencia');
                if(!$conexion->commit())throw new RuntimeException('No se pudo confirmar la actualización.');
                flash('success','Aula y jornada actualizadas.');
            }
        } elseif ($accion==='toggle'||$accion==='eliminar') {
            $id=(int)($_POST['id']??0);$s=$conexion->prepare('SELECT * FROM aulas WHERE id=?');$s->bind_param('i',$id);$s->execute();$antes=$s->get_result()->fetch_assoc();$s->close();
            if (!$antes) throw new RuntimeException('Aula no encontrada.');
            if(esSubadmin()) exigirAccesoAula($id,$periodoAulas);
            if ($accion==='toggle') {
                $nuevo=(int)$antes['activo']?0:1;
                $s=$conexion->prepare('UPDATE aulas SET activo=? WHERE id=?');$s->bind_param('ii',$nuevo,$id);$s->execute();$s->close();
                registrarAuditoria('UPDATE','Aulas','aula',$id,'Estado del aula actualizado.',null,$antes,['activo'=>$nuevo]);
                flash('success',$nuevo?'Aula activada.':'Aula desactivada.');
            } else {
                $s=$conexion->prepare('SELECT COUNT(*) c FROM aulas_periodo WHERE aula_id=?');$s->bind_param('i',$id);$s->execute();$dep=(int)$s->get_result()->fetch_assoc()['c'];$s->close();
                if ($dep>0) throw new RuntimeException('Aula con historial académico: desactívala en lugar de eliminarla.');
                $s=$conexion->prepare('DELETE FROM aulas WHERE id=?');$s->bind_param('i',$id);$s->execute();$s->close();
                registrarAuditoria('DELETE','Aulas','aula',$id,'Aula sin historial eliminada.',null,$antes,null,'exito',null,null,'critica');flash('success','Aula eliminada.');
            }
        } else throw new RuntimeException('Acción no reconocida.');
    } catch (Throwable $e) { try{$conexion->rollback();}catch(Throwable $ignored){} flash('error','No se pudo completar la acción: '.$e->getMessage()); }
    // Mantener el filtro de la jornada al volver al catálogo después de guardar.
    redir('modulos/aulas/index.php'.($filtroJornada>0?'?jornada='.$filtroJornada:''));
}
if ($filtroJornada>0) {
    $s=$conexion->prepare('SELECT a.*,j.nombre jornada FROM aulas a LEFT JOIN jornadas j ON j.id=a.jornada_id WHERE a.jornada_id=? ORDER BY COALESCE(j.orden, 32767) ASC, a.orden ASC, a.nivel ASC, a.nombre ASC, a.paralelo ASC, a.id ASC');
    $s->bind_param('i',$filtroJornada);
    $s->execute();
    $aulas=$s->get_result()->fetch_all(MYSQLI_ASSOC);
    $s->close();
} else {
    $filtroCatalogo=esSubadmin()?filtroJornadasSQL($periodoAulas,'a'):'';
    $aulas=$conexion->query('SELECT a.*,j.nombre jornada FROM aulas a LEFT JOIN jornadas j ON j.id=a.jornada_id WHERE 1=1'.$filtroCatalogo.' ORDER BY COALESCE(j.orden, 32767) ASC, a.orden ASC, a.nivel ASC, a.nombre ASC, a.paralelo ASC, a.id ASC')->fetch_all(MYSQLI_ASSOC);
}
$tituloPagina='Aulas y paralelos';$subtituloPagina='Aulas ordenadas por jornada y secuencia académica, desde Inicial hasta Bachillerato.';
require __DIR__.'/../../partials/header.php';
?>
<link rel="stylesheet" href="<?=e(url('assets/css/sga_catalogo_modales.css'))?>?v=1625">
<script defer src="<?=e(url('assets/js/sga_catalogo_modales.js'))?>?v=1625"></script>
<style>
.sga-aula-cualitativos{margin:13px 0 4px;padding:11px 13px;border:1px solid #cadcf0;border-radius:10px;background:#f2f7fd}
.sga-cat-dialog form label.sga-aula-cualitativos-check{display:flex;flex-direction:row;align-items:flex-start;gap:10px;margin:0;font-size:13px;cursor:pointer;color:#193c64}
.sga-aula-cualitativos-check input[type="checkbox"]{width:18px;height:18px;margin:1px 0 0;flex:0 0 18px}
.sga-aula-cualitativos-check span{display:flex;flex-direction:column;gap:3px}
.sga-aula-cualitativos-check small{font-size:11px;line-height:1.45;font-weight:400;color:#526980}
</style>
<div class="sga-cat-toolbar"><div><h2 class="sga-cat-toolbar-title">Catálogo de aulas y paralelos</h2><small class="sga-cat-toolbar-sub">Los registros conservan su jornada y orden académico.</small></div>
<div class="actions"><a class="btn btn-secondary" href="<?=e(url('modulos/jornadas/index.php'))?>">Gestionar jornadas</a><button class="btn btn-primary" type="button" data-sga-cat-open="sga-cat-create">+ Crear / importar aulas</button></div></div>
<dialog class="sga-cat-dialog" id="sga-cat-create" aria-labelledby="sga-cat-create-title">
<header class="sga-cat-dialog-head"><div><h2 id="sga-cat-create-title">Crear o importar aulas</h2><p>Selecciona cómo deseas registrar las aulas y paralelos.</p></div>
<button class="sga-cat-dialog-close" type="button" aria-label="Cerrar ventana" data-sga-cat-close>&times;</button></header>
<div class="sga-cat-tabs" role="tablist" aria-label="Método de registro">
<button type="button" class="sga-cat-tab" data-sga-cat-tab="crear" role="tab" id="sga-cat-tab-crear" aria-selected="true" aria-controls="sga-cat-panel-crear">Crear aula</button>
<button type="button" class="sga-cat-tab" data-sga-cat-tab="csv" role="tab" id="sga-cat-tab-csv" aria-selected="false" aria-controls="sga-cat-panel-csv" tabindex="-1">Importar CSV</button>
</div>
<div class="sga-cat-dialog-inner">
<section class="sga-cat-panel" data-sga-cat-panel="crear" id="sga-cat-panel-crear" role="tabpanel" aria-labelledby="sga-cat-tab-crear"><?php if (!$jornadas):?><p class="alert info">Primero registra una jornada académica.</p><?php endif;?><form method="post"><input type="hidden" name="csrf" value="<?=e($csrf)?>"><input type="hidden" name="accion" value="crear"><div class="form-grid cols-3"><label>Código<input name="codigo" maxlength="30" placeholder="8EGB-A"></label>
<label>Nivel<input name="nivel" maxlength="100" required placeholder="EGB"></label>
<label>Curso<input name="nombre" maxlength="100" required placeholder="OCTAVO"></label>
<label>Paralelo<input name="paralelo" maxlength="20" required placeholder="A"></label>
<label>Jornada<select name="jornada_id" required><option value="">Selecciona una jornada</option>
<?php foreach ($jornadas as $j):?><option value="<?=(int)$j['id']?>" <?=!(int)$j['activo']?'disabled':''?>><?=e($j['nombre'])?></option><?php endforeach;?></select></label>
<label>Orden en la jornada<input type="number" name="orden" min="1" max="9999" value="999" required></label></div>
<div class="sga-aula-cualitativos"><label class="sga-aula-cualitativos-check"><input type="checkbox" name="resultados_cualitativos" value="1"><span><strong>Resultados cualitativos</strong><small>Convierte los resultados numéricos de cada trimestre y del año a la escala A+ (9,50–10,00) hasta E- (1,00–1,49). Se aplica a consultas y reportes sin modificar las notas numéricas.</small></span></label></div><div class="sga-aula-cualitativos"><label class="sga-aula-cualitativos-check"><input type="checkbox" name="evaluacion_cualitativa_parametros" value="1"><span><strong>Evaluación cualitativa por parámetros</strong><small>Evalúa ejes, ámbitos e indicadores con letras A+ a E-, por cada trimestre. El aula tendrá un único docente responsable. Al activar en el período abierto actual se desactivan las ofertas ordinarias, sin borrar sus notas ni asistencias. No cambia períodos cerrados.</small></span></label></div><div class="mini-note">El orden permite ubicar las aulas desde Inicial hasta Bachillerato dentro de cada jornada.</div><div class="sga-cat-actions"><button class="btn btn-secondary" type="button" data-sga-cat-close>Cancelar</button><button class="btn btn-primary" type="submit">Crear aula</button></div></form></section><section class="sga-cat-panel" data-sga-cat-panel="csv" id="sga-cat-panel-csv" role="tabpanel" aria-labelledby="sga-cat-tab-csv" hidden>
<p class="sga-cat-help">Columnas: codigo;nivel;nombre;paralelo;jornada_codigo;orden;resultados_cualitativos;evaluacion_cualitativa_parametros.<br><strong>Formato:</strong> UTF-8, columnas separadas por <strong>;</strong>. La jornada se identifica por su código (ej.: MAT o VES).</p>
<p><a class="btn btn-secondary" href="?descargar_plantilla=csv">Descargar plantilla CSV (;)</a></p>
<p class="sga-cat-template-warning"><strong>Plantilla con ejemplo:</strong> reemplaza o elimina la fila de demostración antes de importar datos reales. El código de jornada debe existir y estar activo. En ambas columnas de evaluación usa <strong>1 = Sí</strong> o <strong>0 = No</strong>.</p>
<form method="post" enctype="multipart/form-data">
<input type="hidden" name="csrf" value="<?=e($csrf)?>"><input type="hidden" name="accion" value="importar_csv">
<label>Seleccionar archivo CSV<input type="file" name="archivo_csv" accept=".csv,text/csv" required></label>
<div class="mini-note">Hasta 1500 registros o 2 MB. Si hay un error, no se importa ninguna fila.</div>
<div class="sga-cat-actions"><button class="btn btn-secondary" type="button" data-sga-cat-close>Cancelar</button><button class="btn btn-primary" type="submit">Importar aulas</button></div>
</form></section></div></dialog>
<dialog class="sga-cat-dialog" id="sga-cat-edit" aria-labelledby="sga-cat-edit-title" data-sga-cat-singular="aula">
<header class="sga-cat-dialog-head"><div><h2 id="sga-cat-edit-title">Editar aula</h2><p>Modifica el curso, la jornada o el orden de esta aula.</p></div>
<button class="sga-cat-dialog-close" type="button" aria-label="Cerrar ventana" data-sga-cat-close>&times;</button></header>
<div class="sga-cat-dialog-inner">
<form method="post" data-sga-cat-edit-form><input type="hidden" name="csrf" value="<?=e($csrf)?>"><input type="hidden" name="accion" value="editar"><input type="hidden" name="id" value=""><div class="form-grid cols-3"><label>Código<input name="codigo" maxlength="30" placeholder="8EGB-A"></label>
<label>Nivel<input name="nivel" maxlength="100" required placeholder="EGB"></label>
<label>Curso<input name="nombre" maxlength="100" required placeholder="OCTAVO"></label>
<label>Paralelo<input name="paralelo" maxlength="20" required placeholder="A"></label>
<label>Jornada<select name="jornada_id" required><option value="">Selecciona una jornada</option>
<?php foreach ($jornadas as $j):?><option value="<?=(int)$j['id']?>" <?=!(int)$j['activo']?'disabled':''?>><?=e($j['nombre'])?></option><?php endforeach;?></select></label>
<label>Orden en la jornada<input type="number" name="orden" min="1" max="9999" value="999" required></label></div>
<div class="sga-aula-cualitativos"><label class="sga-aula-cualitativos-check"><input type="checkbox" name="resultados_cualitativos" value="1"><span><strong>Resultados cualitativos</strong><small>Convierte los resultados numéricos de cada trimestre y del año a la escala A+ (9,50–10,00) hasta E- (1,00–1,49). Se aplica a consultas y reportes sin modificar las notas numéricas.</small></span></label></div><div class="sga-aula-cualitativos"><label class="sga-aula-cualitativos-check"><input type="checkbox" name="evaluacion_cualitativa_parametros" value="1"><span><strong>Evaluación cualitativa por parámetros</strong><small>Evalúa ejes, ámbitos e indicadores con letras A+ a E-, por cada trimestre. El aula tendrá un único docente responsable. Al activar en el período abierto actual se desactivan las ofertas ordinarias, sin borrar sus notas ni asistencias. No cambia períodos cerrados.</small></span></label></div><div class="sga-cat-actions"><button class="btn btn-secondary" type="button" data-sga-cat-close>Cancelar</button><button class="btn btn-primary" type="submit">Guardar cambios</button></div></form></div></dialog>
<div class="toolbar" style="margin-top:26px;align-items:end">
  <div>
    <h2 class="section-title" style="margin:0">Catálogo de aulas</h2>
    <p class="mini-note" style="margin:6px 0 0">Mostrando <?=count($aulas)?> <?=count($aulas)===1?'aula':'aulas'?>.</p>
  </div>
  <form method="get" action="<?=e(url('modulos/aulas/index.php'))?>" class="actions" style="align-items:end;gap:8px">
    <label for="sga-filtrar-aulas-jornada" style="min-width:185px">Filtrar por jornada
      <select id="sga-filtrar-aulas-jornada" name="jornada" aria-label="Filtrar aulas y paralelos por jornada">
        <option value="todas" <?=$filtroJornada===0?'selected':''?>>Todas</option>
        <?php foreach ($jornadas as $j):?>
        <option value="<?=(int)$j['id']?>" <?=$filtroJornada===(int)$j['id']?'selected':''?>><?=e($j['nombre'])?></option>
        <?php endforeach;?>
      </select>
    </label>
    <button type="submit" class="btn btn-primary">Filtrar</button>
  </form>
</div>
<?php if (!$aulas): ?>
<div class="card empty">No hay aulas ni paralelos registrados en esta jornada.</div>
<?php else: ?>
<div class="table-wrap"><table class="table table-responsive-cards"><thead><tr><th>ID</th><th>Código</th><th>Nivel</th><th>Curso</th><th>Paralelo</th><th>Jornada</th><th>Resultados</th><th>Estado</th><th>Acciones</th></tr></thead><tbody>
<?php foreach ($aulas as $a):?><tr><td><?=(int)$a['id']?></td><td><?=e($a['codigo']??'')?></td><td><?=e($a['nivel'])?></td><td><strong><?=e($a['nombre'])?></strong></td><td><?=e($a['paralelo'])?></td><td><?=!empty($a['jornada'])?e($a['jornada']):'<span class="badge warn">Por configurar</span>'?></td><td><span class="badge <?=!empty($a['resultados_cualitativos'])?'good':''?>"><?=!empty($a['evaluacion_cualitativa_parametros'])?'Por parámetros':(!empty($a['resultados_cualitativos'])?'Cualitativos':'Cuantitativos')?></span></td><td><span class="badge <?=$a['activo']?'good':'bad'?>"><?=$a['activo']?'Activo':'Inactivo'?></span></td><td><div class="actions">
<a class="btn btn-sm btn-secondary" href="?editar=<?=(int)$a['id']?><?=$filtroJornada>0?'&amp;jornada='.$filtroJornada:''?>" data-sga-cat-edit='<?=e(json_encode($a,JSON_UNESCAPED_UNICODE|JSON_HEX_TAG|JSON_HEX_AMP|JSON_HEX_APOS|JSON_HEX_QUOT))?>' >Editar</a>
<form method="post"><input type="hidden" name="csrf" value="<?=e($csrf)?>"><input type="hidden" name="accion" value="toggle"><input type="hidden" name="id" value="<?=(int)$a['id']?>"><button class="btn btn-sm <?=$a['activo']?'btn-secondary':'btn-success'?>" data-confirm="¿Cambiar el estado de esta aula?"><?=$a['activo']?'Desactivar':'Activar'?></button></form>
<form method="post"><input type="hidden" name="csrf" value="<?=e($csrf)?>"><input type="hidden" name="accion" value="eliminar"><input type="hidden" name="id" value="<?=(int)$a['id']?>"><button class="btn btn-sm btn-danger" data-confirm="Solo se eliminará si nunca fue utilizada. ¿Continuar?">Eliminar</button></form>
</div></td></tr><?php endforeach;?></tbody></table></div>
<?php endif; ?>
<?php require __DIR__.'/../../partials/footer.php'; ?>
