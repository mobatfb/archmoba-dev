<?php
/** Registro por ejes y ambitos de aprendizaje, con valoracion por trimestre. */
require_once __DIR__.'/../../lib/funciones.php';
exigirLogin();
header('Cache-Control: private, no-store, max-age=0');
$oid=(int)($_GET['oferta_id']??0);
$trimestre=(int)($_GET['trimestre']??1);
$vista=(string)($_GET['vista']??'');
if($oid<1 || !puedeGestionarOferta($oid)){http_response_code(403);exit('No tienes permiso para calificar esta asignatura.');}
$o=ofertaDetalle($oid);
if(!$o || empty($o['evaluacion_cualitativa_parametros']) || !empty($o['solo_visor_comportamiento']) || (!(int)$o['activo'] && !esAdminAcademico())){
    http_response_code(404);exit('Esta asignatura no tiene activada la evaluación cualitativa por parámetros.');
}
if(!in_array($trimestre,[1,2,3],true))$trimestre=1;
$soloLectura=sgaParametrosSoloVista($o);
$puedeConfigurar=sgaParametrosPuedeConfigurar($o);
if(empty($_SESSION['csrf_parametros_cualitativos']))$_SESSION['csrf_parametros_cualitativos']=bin2hex(random_bytes(32));
$csrf=$_SESSION['csrf_parametros_cualitativos'];

// Carga inicial por oferta: nueve ámbitos tomados del documento Word proporcionado.
$existe=$conexion->prepare('SELECT COUNT(*) n FROM sga_parametros_cualitativos WHERE oferta_id=?');
$existe->bind_param('i',$oid);sgaEjecutar($existe,'comprobar el modelo');
$hayModelo=(int)$existe->get_result()->fetch_assoc()['n']>0;$existe->close();
if(!$hayModelo && ($puedeConfigurar || !$soloLectura)){
    try{sgaParametrosInicializar($conexion,$oid,(int)$o['periodo_id']);}
    catch(Throwable $e){flash('error','No fue posible inicializar los ámbitos: '.$e->getMessage());}
}
if($_SERVER['REQUEST_METHOD']==='POST'){
    try{
        if(!$puedeConfigurar)throw new DomainException('Solo el personal administrativo autorizado puede configurar ámbitos durante el período abierto.');
        if(!hash_equals($csrf,(string)($_POST['csrf']??'')))throw new DomainException('Formulario caducado. Recarga la página.');
        if(!$conexion->begin_transaction())throw new RuntimeException('No se pudo iniciar la configuración.');
        sgaParametrosBloquearAula($conexion,(int)$o['aula_periodo_id']);
        $o=ofertaDetalle($oid);
        if(!$o || !sgaParametrosPuedeConfigurar($o))throw new DomainException('La evaluación ya no admite cambios.');
        sgaAsegurarPeriodoEditable((int)$o['periodo_id']);
        $accion=(string)($_POST['accion']??'');
        $id=(int)($_POST['parametro_id']??0);
        if($accion==='agregar'){
            $eje=trim((string)($_POST['eje']??''));$ambito=trim((string)($_POST['ambito']??''));
            if($eje===''||$ambito===''||(preg_match_all('/./us',$eje)?:0)>180||(preg_match_all('/./us',$ambito)?:0)>220)throw new DomainException('Escribe un eje (máximo 180 caracteres) y un ámbito (máximo 220 caracteres).');
            $s=$conexion->prepare('SELECT COALESCE(MAX(orden),0)+1 orden FROM sga_parametros_cualitativos WHERE oferta_id=?');
            $s->bind_param('i',$oid);sgaEjecutar($s,'calcular orden');$orden=(int)$s->get_result()->fetch_assoc()['orden'];$s->close();
            $s=$conexion->prepare('INSERT INTO sga_parametros_cualitativos(oferta_id,eje,ambito,orden) VALUES(?,?,?,?)');
            $s->bind_param('issi',$oid,$eje,$ambito,$orden);sgaEjecutar($s,'agregar ámbito');$id=(int)$conexion->insert_id;$s->close();
            sgaAuditoriaObligatoria('CREATE','Calificaciones','parametro_cualitativo',$id,'Ámbito añadido a la evaluación del aula.',null,null,['oferta_id'=>$oid,'eje'=>$eje,'ambito'=>$ambito],'exito');
            flash('success','Ámbito agregado correctamente.');
        } elseif($accion==='renombrar'){
            $eje=trim((string)($_POST['eje']??''));$ambito=trim((string)($_POST['ambito']??''));
            if($id<1||$eje===''||$ambito===''||(preg_match_all('/./us',$eje)?:0)>180||(preg_match_all('/./us',$ambito)?:0)>220)throw new DomainException('Datos incompletos del ámbito.');
            $s=$conexion->prepare('SELECT eje,ambito FROM sga_parametros_cualitativos WHERE id=? AND oferta_id=? LIMIT 1');
            $s->bind_param('ii',$id,$oid);sgaEjecutar($s,'consultar ámbito');$antes=$s->get_result()->fetch_assoc();$s->close();
            if(!$antes)throw new DomainException('Ámbito no encontrado.');
            $s=$conexion->prepare('SELECT 1 FROM sga_calificaciones_parametros WHERE parametro_id=? LIMIT 1');
            $s->bind_param('i',$id);sgaEjecutar($s,'validar historial');$evaluado=(bool)$s->get_result()->fetch_row();$s->close();
            if($evaluado && ($antes['eje']!==$eje || $antes['ambito']!==$ambito)) throw new DomainException('Este ámbito ya tiene valoraciones y no puede cambiar de nombre. Crea otro ámbito para no alterar el historial.');
            $s=$conexion->prepare('UPDATE sga_parametros_cualitativos SET eje=?,ambito=? WHERE id=? AND oferta_id=?');
            $s->bind_param('ssii',$eje,$ambito,$id,$oid);sgaEjecutar($s,'actualizar ámbito');$s->close();
            sgaAuditoriaObligatoria('UPDATE','Calificaciones','parametro_cualitativo',$id,'Descripción del ámbito actualizada.',null,$antes,['eje'=>$eje,'ambito'=>$ambito],'exito',null,null,'advertencia');
            flash('success','Nombre del ámbito actualizado.');
        } elseif($accion==='desactivar' || $accion==='activar'){
            if($id<1)throw new DomainException('Ámbito no válido.');
            $s=$conexion->prepare('SELECT id,activo FROM sga_parametros_cualitativos WHERE id=? AND oferta_id=? LIMIT 1');
            $s->bind_param('ii',$id,$oid);sgaEjecutar($s,'consultar ámbito');$antes=$s->get_result()->fetch_assoc();$s->close();
            if(!$antes)throw new DomainException('Ámbito inexistente en esta evaluación.');
            if($accion==='desactivar'){
                $s=$conexion->prepare('SELECT 1 FROM sga_calificaciones_parametros WHERE parametro_id=? LIMIT 1');
                $s->bind_param('i',$id);sgaEjecutar($s,'verificar calificaciones');$hayNotas=(bool)$s->get_result()->fetch_row();$s->close();
                if($hayNotas)throw new DomainException('Este ámbito ya tiene valoraciones. No puede ocultarse para preservar el historial.');
            }
            $activo=$accion==='activar'?1:0;
            $s=$conexion->prepare('UPDATE sga_parametros_cualitativos SET activo=? WHERE id=? AND oferta_id=?');
            $s->bind_param('iii',$activo,$id,$oid);sgaEjecutar($s,'modificar estado');$s->close();
            sgaAuditoriaObligatoria('UPDATE','Calificaciones','parametro_cualitativo',$id,'Disponibilidad de ámbito actualizada.',null,$antes,['activo'=>$activo],'exito');
            flash('success',$activo?'Ámbito habilitado.':'Ámbito desactivado.');
        } else throw new DomainException('Acción no reconocida.');
        if(!$conexion->commit())throw new RuntimeException('No se pudo confirmar la configuración.');
    }catch(Throwable $e){try{$conexion->rollback();}catch(Throwable $ignored){}flash('error',$e->getMessage());}
    redir('modulos/calificaciones/parametros.php?oferta_id='.$oid.'&trimestre='.$trimestre);
}
$parametros=sgaParametrosDeOferta($conexion,$oid);
// Agrupar solo la presentacion de la tabla: mismo eje, una sola cabecera.
// Mantener los IDs de cada ambito y su orden relativo dentro de cada eje.
$gruposEjes=[];
foreach($parametros as $pa){
    $eje=trim((string)$pa['eje']);
    if(!isset($gruposEjes[$eje]))$gruposEjes[$eje]=['eje'=>$eje,'parametros'=>[]];
    $gruposEjes[$eje]['parametros'][]=$pa;
}
$parametrosTabla=[];
foreach($gruposEjes as $grupo)foreach($grupo['parametros'] as $pa)$parametrosTabla[]=$pa;
$cabeceraAgrupada=$vista!=='resumen' && !empty($parametrosTabla);
$todos=$puedeConfigurar?sgaParametrosDeOferta($conexion,$oid,false):[];
$alumnos=sgaParametrosAlumnosDeOferta($conexion,(int)$o['aula_periodo_id']);
$notas=sgaParametrosNotasDeOferta($conexion,$oid);
$tituloPagina='Evaluación por parámetros · '.$o['aula'].' '.$o['paralelo'];
$subtituloPagina=$o['nivel'].' · '.$o['aula'].' '.$o['paralelo'].' · '.$o['periodo'];
require __DIR__.'/../../partials/header.php';
?>
<link rel="stylesheet" href="<?=e(url('assets/css/sga_parametros_cualitativos.css'))?>?v=5">
<div class="toolbar grade-toolbar sga-p-toolbar">
 <div class="actions">
 <?php for($t=1;$t<=3;$t++): ?>
  <a class="btn <?=$vista===''&&$t===$trimestre?'btn-primary':'btn-secondary'?>" href="<?=e(url('modulos/calificaciones/parametros.php?oferta_id='.$oid.'&trimestre='.$t))?>" <?=$vista===''&&$t===$trimestre?'aria-current="page"':''?>>Trimestre <?=$t?></a>
 <?php endfor; ?>
  <a class="btn <?=$vista==='resumen'?'btn-primary':'btn-secondary'?>" href="<?=e(url('modulos/calificaciones/parametros.php?oferta_id='.$oid.'&vista=resumen'))?>">Resumen T1–T3</a>
 </div>
 <div class="actions"><a class="btn btn-success" href="<?=e(url('modulos/calificaciones/reporte_excel.php?oferta_id='.$oid))?>">Exportar parámetros Excel</a><a class="btn btn-secondary" href="<?=e(url('modulos/calificaciones/cursos.php'))?>">Volver a calificaciones</a></div>
</div>
<section class="card sga-p-card">
 <div class="sga-p-head"><div><h2><?=e($vista==='resumen'?'Resumen cualitativo':'Evaluación cualitativa · Trimestre '.$trimestre)?></h2>
 <p>Valora cada ámbito de aprendizaje de manera independiente. Escala A+ a E-. No se calculan promedios numéricos.</p></div>
 <span class="sga-p-count"><?=count($alumnos)?> estudiantes · <?=count($parametros)?> ámbitos</span></div>
 <?php if($soloLectura):?><div class="notice"><?=($o['periodo_estado']??'')==='cerrado'?'Período cerrado: solo consulta.':(sgaParametrosEvaluacionEditable($o)?'No tienes permiso para registrar valoraciones en esta aula.':'Registro histórico o inactivo: solo consulta.')?></div>
 <?php elseif(esAdminAcademico() && $vista!=='resumen'):?><div class="notice">Calificación habilitada para <?=esSuperadmin()?'Administración':'Subadministración de la jornada'?>. Las modificaciones quedan registradas a nombre del usuario que las realiza; el docente responsable no cambia.</div><?php endif;?>
 <?php if(!$parametros):?><div class="alert info">No hay ámbitos configurados para esta evaluación. Un administrador puede crear los parámetros desde «Administrar parámetros».</div><?php endif;?>
 <?php if(!$alumnos):?><div class="empty">No hay estudiantes activos matriculados en esta aula.</div><?php else:?>
 <div class="sga-p-scroll" role="region" aria-label="Tabla de evaluación cualitativa por parámetros" tabindex="0">
 <table class="sga-p-table" id="sga-p-table" data-url="<?=e(url('modulos/calificaciones/guardar_parametro.php'))?>" data-oferta-id="<?=$oid?>" data-trimestre="<?=$trimestre?>" data-csrf="<?=e($csrf)?>">
 <?php if($cabeceraAgrupada): ?>
 <colgroup span="1"></colgroup><colgroup span="1"></colgroup>
 <?php foreach($gruposEjes as $grupo): ?><colgroup span="<?=count($grupo['parametros'])?>"></colgroup><?php endforeach; ?>
 <colgroup span="1"></colgroup>
 <?php endif; ?>
 <thead>
 <?php if($vista==='resumen'): ?>
 <tr><th class="sga-p-sticky-num" scope="col">No.</th><th class="sga-p-sticky-name" scope="col">Estudiante</th><th scope="col">Ámbito evaluado</th><th scope="col">T1</th><th scope="col">T2</th><th scope="col">T3</th><th scope="col">Informe</th></tr>
 <?php else: ?>
 <tr class="sga-p-ejes">
 <th class="sga-p-sticky-num" scope="col" rowspan="<?=$cabeceraAgrupada?2:1?>">No.</th>
 <th class="sga-p-sticky-name" scope="col" rowspan="<?=$cabeceraAgrupada?2:1?>">Estudiante</th>
 <?php foreach($gruposEjes as $grupo): ?>
 <th class="sga-p-eje" scope="colgroup" colspan="<?=count($grupo['parametros'])?>"><?=e($grupo['eje'])?></th>
 <?php endforeach; ?>
 <th class="sga-p-estado" scope="col" rowspan="<?=$cabeceraAgrupada?2:1?>">Estado / Informe</th>
 </tr>
 <?php if($cabeceraAgrupada): ?>
 <tr class="sga-p-ambitos">
 <?php foreach($parametrosTabla as $pa): ?>
 <th scope="col" title="<?=e($pa['eje'].' · '.$pa['ambito'])?>"><span><?=e($pa['ambito'])?></span></th>
 <?php endforeach; ?>
 </tr>
 <?php endif; ?>
 <?php endif; ?>
 </thead>
 <tbody>
 <?php foreach($alumnos as $i=>$al): $mid=(int)$al['matricula_id']; $nombre=$al['apellidos'].' '.$al['nombres']; ?>
 <?php if($vista==='resumen'):?>
 <?php foreach($parametros as $j=>$pa):$pid=(int)$pa['id'];?><tr>
 <?php if($j===0):?><td rowspan="<?=count($parametros)?>" class="sga-p-sticky-num"><?=e($al['numero_lista']?:($i+1))?></td>
 <td rowspan="<?=count($parametros)?>" class="sga-p-sticky-name"><strong><?=e($nombre)?></strong><small><?=e($al['cedula'])?></small></td><?php endif; ?>
 <td><small><?=e($pa['eje'])?></small> <?=e($pa['ambito'])?></td>
 <?php for($t=1;$t<=3;$t++): $v=$notas[$mid][$pid][$t]??'';?><td class="sga-p-lit"><?=e($v?:'—')?></td><?php endfor; ?>
 <?php if($j===0):?><td rowspan="<?=count($parametros)?>"><a class="btn btn-sm btn-secondary" target="_blank" rel="noopener" href="<?=e(url('modulos/calificaciones/informe_aprendizaje.php?oferta_id='.$oid.'&matricula_id='.$mid))?>">Informe</a></td><?php endif; ?>
 </tr><?php endforeach;?>
 <?php else: ?><tr data-matricula="<?=$mid?>">
 <td class="sga-p-sticky-num"><?=e($al['numero_lista']?:($i+1))?></td>
 <th class="sga-p-sticky-name" scope="row"><strong><?=e($nombre)?></strong><small><?=e($al['cedula'])?></small></th>
 <?php foreach($parametrosTabla as $pa): $pid=(int)$pa['id'];$actual=$notas[$mid][$pid][$trimestre]??''; ?>
 <td><select class="sga-p-select" data-parametro="<?=$pid?>" data-valor="<?=e($actual)?>" aria-label="<?=e($nombre.' · '.$pa['ambito'])?>" <?=$soloLectura?'disabled':''?>>
 <option value="" <?=$actual===''?'selected':''?>>—</option>
 <?php foreach(sgaParametrosOpciones() as $lit):?><option value="<?=e($lit)?>" <?=$actual===$lit?'selected':''?>><?=e($lit)?></option><?php endforeach; ?>
 </select></td><?php endforeach; ?>
 <td><span class="sga-p-row-status" aria-live="polite">—</span>
 <a class="sga-p-informe-link" target="_blank" rel="noopener" href="<?=e(url('modulos/calificaciones/informe_aprendizaje.php?oferta_id='.$oid.'&matricula_id='.$mid))?>">Informe</a></td>
 </tr><?php endif;?>
 <?php endforeach; ?>
 </tbody></table></div>
 <?php endif; ?>
 <p class="mini-note"><?=$soloLectura?'Consulta de las valoraciones guardadas.':'Cada selección se guarda automáticamente, sin recargar la página. «—» permite dejar un ámbito sin nota. Los registros de los otros trimestres se conservan.'?></p>
</section>
<?php if($puedeConfigurar): ?>
<details class="card sga-p-config"><summary><strong>Administrar parámetros del aula</strong> · Editar ejes y ámbitos</summary>
<p class="mini-note">El modelo inicial reproduce nueve ámbitos del documento de Inicial y Preparatoria. Puedes añadir o renombrar parámetros para adaptar este aula. Los cambios de esta evaluación no afectan las otras aulas ni los períodos anteriores.</p>
<div class="sga-p-config-grid">
<?php foreach($todos as $pa): ?>
<form method="post" class="sga-p-param-card">
<input type="hidden" name="csrf" value="<?=e($csrf)?>"><input type="hidden" name="parametro_id" value="<?=(int)$pa['id']?>">
<label>Eje<input name="eje" maxlength="180" value="<?=e($pa['eje'])?>" required></label>
<label>Ámbito o indicador<input name="ambito" maxlength="220" value="<?=e($pa['ambito'])?>" required></label>
<div class="actions"><button class="btn btn-sm btn-secondary" name="accion" value="renombrar">Actualizar</button>
<button class="btn btn-sm btn-secondary" name="accion" value="<?=$pa['activo']?'desactivar':'activar'?>" <?=$pa['activo'] && (int)$pa['registros']>0?'disabled title="Tiene evaluaciones guardadas"':''?>><?=$pa['activo']?'Desactivar':'Activar'?></button></div>
</form><?php endforeach; ?>
</div>
<form method="post" class="sga-p-new"><input type="hidden" name="csrf" value="<?=e($csrf)?>"><input type="hidden" name="accion" value="agregar">
<h3>Añadir un ámbito o indicador</h3><label>Eje<input name="eje" maxlength="180" required placeholder="Eje de desarrollo y aprendizaje"></label>
<label>Ámbito o indicador<input name="ambito" maxlength="220" required placeholder="Nombre del ámbito o indicador"></label>
<button class="btn btn-primary" type="submit">Añadir parámetro</button></form>
</details>
<?php endif; ?>
<script src="<?=e(url('assets/js/sga_parametros_cualitativos.js'))?>?v=1" defer></script>
<?php require __DIR__.'/../../partials/footer.php'; ?>
