<?php
require_once __DIR__.'/../../lib/funciones.php';exigirAdminAcademico();
if(empty($_SESSION['csrf_periodos']))$_SESSION['csrf_periodos']=bin2hex(random_bytes(24));
$csrfPeriodo=(string)$_SESSION['csrf_periodos'];
$editarId=(int)($_GET['editar']??0);$editar=null;if($editarId){$stmt=$conexion->prepare('SELECT p.*,c.ponderacion_aportes,c.ponderacion_sumativa,c.nota_aprobacion,c.nota_min_supletorio FROM periodos_academicos p LEFT JOIN configuracion_evaluacion c ON c.periodo_id=p.id WHERE p.id=? LIMIT 1');$stmt->bind_param('i',$editarId);$stmt->execute();$editar=$stmt->get_result()->fetch_assoc()?:null;$stmt->close();}
if($_SERVER['REQUEST_METHOD']==='POST'){
    $accion=(string)($_POST['accion']??'');
    $validas=['crear','editar','activar','desactivar','cerrar','eliminar'];
    try {
        if(!hash_equals($csrfPeriodo,(string)($_POST['csrf_periodos']??'')))throw new DomainException('Formulario de período caducado. Actualiza la página.');
        if(!in_array($accion,$validas,true))throw new DomainException('Operación de período no reconocida.');
        if(!$conexion->begin_transaction())throw new RuntimeException('No se pudo iniciar la operación.');
        if($accion==='crear'||$accion==='editar'){
            $nombre=trim((string)($_POST['nombre']??''));
            $ai=(int)($_POST['anio_inicio']??0);$af=(int)($_POST['anio_fin']??0);
            $fi=trim((string)($_POST['fecha_inicio']??''));$ff=trim((string)($_POST['fecha_fin']??''));
            $fi=$fi===''?null:$fi;$ff=$ff===''?null:$ff;
            $pa=(float)str_replace(',','.',(string)($_POST['ponderacion_aportes']??'0.70'));
            $ps=(float)str_replace(',','.',(string)($_POST['ponderacion_sumativa']??'0.30'));
            $apr=(float)str_replace(',','.',(string)($_POST['nota_aprobacion']??'7'));
            $min=(float)str_replace(',','.',(string)($_POST['nota_min_supletorio']??'4'));
            if($nombre===''||$ai<2000||$af<$ai)throw new DomainException('Datos de período inválidos.');
            if($fi!==null&&$ff!==null&&$ff<$fi)throw new DomainException('La fecha fin no puede ser anterior a la inicial.');
            if(abs(($pa+$ps)-1)>0.0001)throw new DomainException('Las ponderaciones deben sumar 100 %.');
            if($apr<0||$apr>10||$min<0||$min>10)throw new DomainException('Notas de configuración inválidas.');
            if($accion==='crear'){
                $stmt=$conexion->prepare("INSERT INTO periodos_academicos(nombre,anio_inicio,anio_fin,fecha_inicio,fecha_fin,estado) VALUES(?,?,?,?,?,'planificacion')");
                $stmt->bind_param('siiss',$nombre,$ai,$af,$fi,$ff);sgaEjecutar($stmt,'crear período');
                $id=(int)$conexion->insert_id;$stmt->close();
                $stmt=$conexion->prepare('INSERT INTO configuracion_evaluacion(periodo_id,ponderacion_aportes,ponderacion_sumativa,nota_aprobacion,nota_min_supletorio) VALUES(?,?,?,?,?)');
                $stmt->bind_param('idddd',$id,$pa,$ps,$apr,$min);sgaEjecutar($stmt,'guardar evaluación');$stmt->close();
                sgaAuditoriaObligatoria('CREATE','Periodos','periodo_academico',$id,'Período académico creado.',null,null,
                   ['nombre'=>$nombre,'anio_inicio'=>$ai,'anio_fin'=>$af,'fecha_inicio'=>$fi,'fecha_fin'=>$ff,'estado'=>'planificacion','ponderacion_aportes'=>$pa,'ponderacion_sumativa'=>$ps]);
                $mensaje='Período creado en planificación.';
            } else {
                $id=(int)($_POST['id']??0);
                $stmt=$conexion->prepare('SELECT p.*,c.ponderacion_aportes,c.ponderacion_sumativa,c.nota_aprobacion,c.nota_min_supletorio FROM periodos_academicos p LEFT JOIN configuracion_evaluacion c ON c.periodo_id=p.id WHERE p.id=? LIMIT 1 FOR UPDATE');
                $stmt->bind_param('i',$id);sgaEjecutar($stmt,'consultar período');$antes=$stmt->get_result()->fetch_assoc();$stmt->close();
                if(!$antes)throw new DomainException('Período inexistente.');
                if($antes['estado']==='cerrado')throw new DomainException('El período cerrado es de solo lectura.');
                $stmt=$conexion->prepare('UPDATE periodos_academicos SET nombre=?,anio_inicio=?,anio_fin=?,fecha_inicio=?,fecha_fin=? WHERE id=?');
                $stmt->bind_param('siissi',$nombre,$ai,$af,$fi,$ff,$id);sgaEjecutar($stmt,'actualizar período');$stmt->close();
                $stmt=$conexion->prepare('UPDATE configuracion_evaluacion SET ponderacion_aportes=?,ponderacion_sumativa=?,nota_aprobacion=?,nota_min_supletorio=? WHERE periodo_id=?');
                $stmt->bind_param('ddddi',$pa,$ps,$apr,$min,$id);sgaEjecutar($stmt,'actualizar evaluación');$stmt->close();
                $despues=$antes;foreach(['nombre'=>$nombre,'anio_inicio'=>$ai,'anio_fin'=>$af,'fecha_inicio'=>$fi,'fecha_fin'=>$ff,
                  'ponderacion_aportes'=>$pa,'ponderacion_sumativa'=>$ps,'nota_aprobacion'=>$apr,'nota_min_supletorio'=>$min] as $k=>$v)$despues[$k]=$v;
                sgaAuditoriaObligatoria('UPDATE','Periodos','periodo_academico',$id,'Configuración del período actualizada.',null,$antes,$despues,'exito',null,null,'advertencia');
                $mensaje='Período actualizado.';
            }
        } else {
            $id=(int)($_POST['id']??0);
            $stmt=$conexion->prepare('SELECT id,nombre,estado FROM periodos_academicos WHERE id=? LIMIT 1 FOR UPDATE');
            $stmt->bind_param('i',$id);sgaEjecutar($stmt,'consultar el estado del período');$antes=$stmt->get_result()->fetch_assoc();$stmt->close();
            if(!$antes)throw new DomainException('Período no encontrado.');
            if($accion==='activar'){
                if($antes['estado']==='cerrado')throw new DomainException('Un período cerrado no puede reactivarse.');
                if(!$conexion->query("UPDATE periodos_academicos SET estado='planificacion' WHERE estado='activo'"))throw new RuntimeException('No se pudo desactivar el período anterior.');
                $nuevo='activo';$mensaje='Período activo actualizado.';$detalle='Período establecido como activo.';
            }elseif($accion==='desactivar'){
                if($antes['estado']!=='activo')throw new DomainException('Solo el período activo puede desactivarse.');
                $nuevo='planificacion';$mensaje='Período desactivado.';$detalle='Período devuelto a planificación.';
            }elseif($accion==='cerrar'){
                if($antes['estado']==='cerrado')throw new DomainException('El período ya está cerrado.');
                $nuevo='cerrado';$mensaje='Período cerrado.';$detalle='Período académico cerrado.';
            }else{
                if($antes['estado']==='activo')throw new DomainException('Desactiva el período antes de eliminarlo.');
                $stmt=$conexion->prepare('SELECT (SELECT COUNT(*) FROM aulas_periodo WHERE periodo_id=?)+(SELECT COUNT(*) FROM usuario_roles WHERE periodo_id=?)+(SELECT COUNT(*) FROM elecciones WHERE periodo_id=?) c');
                $stmt->bind_param('iii',$id,$id,$id);sgaEjecutar($stmt,'comprobar dependencias');$dependencias=(int)$stmt->get_result()->fetch_assoc()['c'];$stmt->close();
                if($dependencias>0)throw new DomainException('El período tiene historial. Ciérralo en vez de eliminarlo.');
                $stmt=$conexion->prepare('DELETE FROM periodos_academicos WHERE id=?');$stmt->bind_param('i',$id);sgaEjecutar($stmt,'eliminar período');$stmt->close();
                sgaAuditoriaObligatoria('DELETE','Periodos','periodo_academico',$id,'Período sin historial eliminado.',null,$antes,null,'exito',null,null,'critica');
                $mensaje='Período eliminado.';
            }
            if($accion!=='eliminar'){
                $stmt=$conexion->prepare('UPDATE periodos_academicos SET estado=? WHERE id=?');
                $stmt->bind_param('si',$nuevo,$id);sgaEjecutar($stmt,'cambiar estado del período');$stmt->close();
                $despues=$antes;$despues['estado']=$nuevo;
                sgaAuditoriaObligatoria('UPDATE','Periodos','periodo_academico',$id,$detalle,null,$antes,$despues,'exito',null,null,'advertencia');
            }
        }
        if(!$conexion->commit())throw new RuntimeException('No se pudo confirmar la operación académica.');
        flash('success',$mensaje);
    } catch(Throwable $e){
        try{$conexion->rollback();}catch(Throwable $x){}
        flash('error',$e->getMessage());
    }
    redir('modulos/periodos/index.php');
}
$periodos=$conexion->query('SELECT p.*,c.ponderacion_aportes,c.ponderacion_sumativa,c.nota_aprobacion,c.nota_min_supletorio FROM periodos_academicos p LEFT JOIN configuracion_evaluacion c ON c.periodo_id=p.id ORDER BY p.anio_inicio DESC,p.id DESC')->fetch_all(MYSQLI_ASSOC);
$tituloPagina='Periodos académicos';$subtituloPagina='Edita la configuración anual; activa, desactiva, cierra o elimina solo periodos sin historial.';require __DIR__.'/../../partials/header.php';
?>
<link rel="stylesheet" href="<?=e(url('assets/css/sga_catalogo_modales.css'))?>?v=1625">
<script defer src="<?=e(url('assets/js/sga_catalogo_modales.js'))?>?v=1625"></script>
<div class="sga-cat-toolbar"><div><h2 class="sga-cat-toolbar-title">Períodos registrados</h2><small class="sga-cat-toolbar-sub">Configura cada período y administra su estado desde el listado.</small></div>
<div class="actions"><button type="button" class="btn btn-primary" data-sga-cat-open="sga-cat-create">+ Crear período</button></div></div>
<dialog class="sga-cat-dialog" id="sga-cat-create" aria-labelledby="sga-cat-create-title">
<header class="sga-cat-dialog-head"><div><h2 id="sga-cat-create-title">Crear período académico</h2><p>Crea un período en estado de planificación; después podrás activarlo.</p></div>
<button class="sga-cat-dialog-close" type="button" aria-label="Cerrar ventana" data-sga-cat-close>&times;</button></header>
<div class="sga-cat-dialog-inner">
<form method="post"><input type="hidden" name="csrf_periodos" value="<?=e($csrfPeriodo)?>"><input type="hidden" name="accion" value="crear"><div class="form-grid cols-3">
<label>Nombre<input name="nombre" placeholder="2027-2028" required></label>
<label>Año inicio<input type="number" name="anio_inicio" min="2000" max="2100" required></label>
<label>Año fin<input type="number" name="anio_fin" min="2000" max="2101" required></label>
<label>Fecha inicio<input type="date" name="fecha_inicio"></label>
<label>Fecha fin<input type="date" name="fecha_fin"></label>
<label>Ponderación aportes<input type="number" step="0.01" min="0" max="1" name="ponderacion_aportes" value="0.70" required></label>
<label>Ponderación sumativa<input type="number" step="0.01" min="0" max="1" name="ponderacion_sumativa" value="0.30" required></label>
<label>Nota aprobación<input type="number" step="0.01" min="0" max="10" name="nota_aprobacion" value="7.00" required></label>
<label>Nota mín. supletorio<input type="number" step="0.01" min="0" max="10" name="nota_min_supletorio" value="4.00" required></label></div><div class="sga-cat-actions"><button class="btn btn-secondary" type="button" data-sga-cat-close>Cancelar</button><button class="btn btn-primary" type="submit">Crear período</button></div></form></div></dialog>
<dialog class="sga-cat-dialog" id="sga-cat-edit" aria-labelledby="sga-cat-edit-title" data-sga-cat-singular="período académico">
<header class="sga-cat-dialog-head"><div><h2 id="sga-cat-edit-title">Editar período académico</h2><p>Los períodos cerrados solo se pueden consultar.</p></div>
<button class="sga-cat-dialog-close" type="button" aria-label="Cerrar ventana" data-sga-cat-close>&times;</button></header>
<div class="sga-cat-dialog-inner">
<form method="post" data-sga-cat-edit-form><input type="hidden" name="csrf_periodos" value="<?=e($csrfPeriodo)?>"><input type="hidden" name="accion" value="editar"><input type="hidden" name="id" value=""><div class="form-grid cols-3">
<label>Nombre<input name="nombre" placeholder="2027-2028" required></label>
<label>Año inicio<input type="number" name="anio_inicio" min="2000" max="2100" required></label>
<label>Año fin<input type="number" name="anio_fin" min="2000" max="2101" required></label>
<label>Fecha inicio<input type="date" name="fecha_inicio"></label>
<label>Fecha fin<input type="date" name="fecha_fin"></label>
<label>Ponderación aportes<input type="number" step="0.01" min="0" max="1" name="ponderacion_aportes" value="0.70" required></label>
<label>Ponderación sumativa<input type="number" step="0.01" min="0" max="1" name="ponderacion_sumativa" value="0.30" required></label>
<label>Nota aprobación<input type="number" step="0.01" min="0" max="10" name="nota_aprobacion" value="7.00" required></label>
<label>Nota mín. supletorio<input type="number" step="0.01" min="0" max="10" name="nota_min_supletorio" value="4.00" required></label></div><div class="sga-cat-actions"><button class="btn btn-secondary" type="button" data-sga-cat-close>Cancelar</button><button class="btn btn-primary" type="submit">Guardar cambios</button></div></form></div></dialog>
<h2 class="section-title">Historial</h2><div class="table-wrap"><table class="table table-responsive-cards"><thead><tr><th>Periodo</th><th>Fechas</th><th>Evaluación</th><th>Estado</th><th>Acciones</th></tr></thead><tbody><?php foreach($periodos as $p):?><tr><td><strong><?=e($p['nombre'])?></strong></td><td><?=e(($p['fecha_inicio']??'').' — '.($p['fecha_fin']??''))?></td><td><?=round((float)$p['ponderacion_aportes']*100)?>% aportes / <?=round((float)$p['ponderacion_sumativa']*100)?>% sumativa · aprueba <?=fmt($p['nota_aprobacion'])?></td><td><span class="badge <?=$p['estado']==='activo'?'good':($p['estado']==='cerrado'?'bad':'')?>"><?=e(ucfirst($p['estado']))?></span></td><td><div class="actions"><a class="btn btn-sm btn-secondary" href="?editar=<?=(int)$p['id']?>" data-sga-cat-edit='<?=e(json_encode($p,JSON_UNESCAPED_UNICODE|JSON_HEX_TAG|JSON_HEX_AMP|JSON_HEX_APOS|JSON_HEX_QUOT))?>' ><?=$p['estado']==='cerrado'?'Consultar':'Editar'?></a><?php if($p['estado']==='planificacion'):?><form method="post"><input type="hidden" name="csrf_periodos" value="<?=e($csrfPeriodo)?>"><input type="hidden" name="accion" value="activar"><input type="hidden" name="id" value="<?=$p['id']?>"><button class="btn btn-sm btn-success">Activar</button></form><?php elseif($p['estado']==='activo'):?><form method="post"><input type="hidden" name="csrf_periodos" value="<?=e($csrfPeriodo)?>"><input type="hidden" name="accion" value="desactivar"><input type="hidden" name="id" value="<?=$p['id']?>"><button class="btn btn-sm btn-secondary" data-confirm="¿Desactivar el periodo activo y devolverlo a planificación?">Desactivar</button></form><?php endif;?><?php if($p['estado']!=='cerrado'):?><form method="post"><input type="hidden" name="csrf_periodos" value="<?=e($csrfPeriodo)?>"><input type="hidden" name="accion" value="cerrar"><input type="hidden" name="id" value="<?=$p['id']?>"><button class="btn btn-sm btn-secondary" data-confirm="¿Cerrar este periodo académico?">Cerrar</button></form><?php endif;?><form method="post"><input type="hidden" name="csrf_periodos" value="<?=e($csrfPeriodo)?>"><input type="hidden" name="accion" value="eliminar"><input type="hidden" name="id" value="<?=$p['id']?>"><button class="btn btn-sm btn-danger" data-confirm="Solo se eliminará si no tiene aulas, roles ni procesos asociados. ¿Continuar?">Eliminar</button></form></div></td></tr><?php endforeach;?></tbody></table></div>
<?php require __DIR__.'/../../partials/footer.php'; ?>
