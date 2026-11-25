<?php
require_once __DIR__.'/../../lib/funciones.php';
require_once __DIR__.'/../../lib/roles_usuarios.php';
require_once __DIR__.'/../../lib/usuarios_jornadas.php';
exigirAdminAcademico();
if (empty($_SESSION['csrf_roles'])) $_SESSION['csrf_roles']=bin2hex(random_bytes(24));
$csrf=$_SESSION['csrf_roles'];
$activo=periodoActivo();
$periodoId=(int)($_REQUEST['periodo_id']??($activo['id']??0));
$periodos=$conexion->query('SELECT id,nombre,estado FROM periodos_academicos ORDER BY anio_inicio DESC,id DESC')->fetch_all(MYSQLI_ASSOC);
if(esSubadmin()){
    $periodos=array_values(array_filter($periodos,static fn($p)=>puedeAccederPeriodo((int)$p['id'])));
    if(!isset($_REQUEST['periodo_id']) && !puedeAccederPeriodo($periodoId) && $periodos)
        $periodoId=(int)$periodos[0]['id'];
    if(!puedeAccederPeriodo($periodoId)){http_response_code(403);die('No tienes jornadas asignadas en el período solicitado.');}
}
if ($periodoId<=0 && $periodos) $periodoId=(int)$periodos[0]['id'];
// Nunca aceptar un periodo arbitrario en el POST: verificar contra el catalogo.
$periodoNombre='Sin periodo';$periodoValido=$periodoId===0 && !$periodos;
foreach($periodos as $p){
    if((int)$p['id']===$periodoId){$periodoNombre=(string)$p['nombre'];$periodoValido=true;break;}
}
$jornadas=$conexion->query('SELECT id,codigo,nombre FROM jornadas WHERE activo=1 ORDER BY orden,nombre')->fetch_all(MYSQLI_ASSOC);
// Jornadas académicas que puede asignar el actor al rol Docente.
$jornadasDocente=sgaUJCatalogo($periodoId);
$porDefecto=[];
foreach($jornadas as $j)if(in_array($j['codigo'],['MAT','VES'],true))$porDefecto[]=(int)$j['id'];
$asignadas=[];
if($periodoId>0){
    $s=$conexion->prepare('SELECT usuario_id,jornada_id FROM subadministrador_jornadas WHERE periodo_id=?');
    $s->bind_param('i',$periodoId);$s->execute();
    foreach($s->get_result()->fetch_all(MYSQLI_ASSOC) as $f)$asignadas[(int)$f['usuario_id']][]=(int)$f['jornada_id'];
    $s->close();
}

if($_SERVER['REQUEST_METHOD']==='POST'){
    $enTransaccion=false;
    try{
        if(!hash_equals($csrf,(string)($_POST['csrf']??'')))throw new RuntimeException('La sesión del formulario caducó.');
        if(!$periodoValido)throw new RuntimeException('El periodo seleccionado no existe.');
        $id=(int)($_POST['usuario_id']??0);
        if($id<=0)throw new RuntimeException('Selecciona un usuario válido.');
        if(($_POST['accion']??'')!=='guardar_roles')throw new RuntimeException('Acción no permitida. Actualiza la página antes de guardar.');
        // La consulta del perfil es visible, pero sus roles permanecen intocables.
        if(esSubadmin() && tieneRolGlobalUsuario($id))
            throw new RuntimeException('La cuenta administrativa es de solo consulta; no puedes modificar sus roles.');
        $seleccion=(array)($_POST['roles']??[]);
        $jornadasSolicitadas=(array)($_POST['jornadas']??[]);
        $tendraRolDocente=in_array('docente',$seleccion,true);
        $jornadasDocenteSolicitadas=[];
        if ($tendraRolDocente) {
            if ($periodoId<=0) throw new RuntimeException('Selecciona un período para asignar jornadas al docente.');
            // Valida TODAS las jornadas en servidor, no solo en el formulario.
            $jornadasDocenteSolicitadas=sgaUJValidarIds(
                (array)($_POST['docente_jornadas']??[]),sgaUJCatalogo($periodoId),true
            );
        }
        $antes=rolesVisiblesUsuario($id);
        $jornadasDocenteAntes=$periodoId>0?sgaUJAsignadas($id,$periodoId):[];
        if(!$conexion->begin_transaction())throw new RuntimeException('No se pudo iniciar el guardado.');
        $enTransaccion=true;
        $resultado=sgaGuardarRolesMultiples($id,$periodoId,$seleccion,$jornadasSolicitadas);
        if ($tendraRolDocente) {
            // No permitir eliminar una jornada donde conserva materias asignadas.
            $s=$conexion->prepare('SELECT DISTINCT a.jornada_id FROM ofertas_academicas o JOIN aulas_periodo ap ON ap.id=o.aula_periodo_id AND ap.activo=1 JOIN aulas a ON a.id=ap.aula_id WHERE o.docente_id=? AND ap.periodo_id=? AND o.activo=1');
            if(!$s)throw new RuntimeException('No se pudieron verificar las asignaturas activas del docente.');
            $s->bind_param('ii',$id,$periodoId);
            if(!$s->execute())throw new RuntimeException('No se pudieron validar las jornadas académicas del docente.');
            $conAsignaturas=array_map('intval',array_column($s->get_result()->fetch_all(MYSQLI_ASSOC),'jornada_id'));
            $s->close();
            if(array_diff($conAsignaturas,$jornadasDocenteSolicitadas))
                throw new RuntimeException('El docente tiene asignaturas activas en una jornada que estás retirando. Reasigna primero esas materias.');
            // Guarda varias jornadas para UN usuario y ESTE período; no duplica roles.
            sgaUJGuardar($id,$periodoId,$jornadasDocenteSolicitadas);
        }
        if(!$conexion->commit())throw new RuntimeException('No se pudo confirmar el guardado.');
        $enTransaccion=false;
        registrarAuditoria('ASSIGN_ROLE','Roles','usuario_rol',$id,
            'Actualización de roles seleccionados desde casillas.',$id,$antes,
            ['roles'=>$resultado['roles'],'jornadas_subadministrador'=>$resultado['jornadas'],
             'jornadas_docente_antes'=>$jornadasDocenteAntes,
             'jornadas_docente'=>$tendraRolDocente?$jornadasDocenteSolicitadas:$jornadasDocenteAntes,
             'periodo_id'=>$periodoId],
            'exito',null,null,'advertencia');
        flash('success','Roles guardados correctamente. Las demás asignaciones históricas se conservaron.');
    } catch(Throwable $e){
        if($enTransaccion)$conexion->rollback();
        flash('error','No se pudieron guardar los roles: '.$e->getMessage());
    }
    redir('modulos/roles/index.php?periodo_id='.$periodoId);
}
$q=trim((string)($_GET['q']??''));
$sql='SELECT u.id,u.cedula,u.apellidos,u.nombres,u.activo FROM usuarios u WHERE 1=1';
if(esSubadmin())$sql.=filtroUsuariosJornadasSQL($periodoId,'u');
if($q!=='')$sql.=' AND (u.cedula LIKE ? OR u.apellidos LIKE ? OR u.nombres LIKE ?)';
$sql.=' ORDER BY u.apellidos,u.nombres,u.id LIMIT 500';
$s=$conexion->prepare($sql);
if($q!==''){$like='%'.$q.'%';$s->bind_param('sss',$like,$like,$like);}
$s->execute();$usuarios=$s->get_result()->fetch_all(MYSQLI_ASSOC);$s->close();
$marcados=[];
// Prefija las jornadas ya guardadas y las de materias que el docente imparte.
// Consulta por lote para evitar una consulta por cada fila del directorio.
$docenteJornadasMarcadas=[];
if($usuarios && $periodoId>0){
    $ids=implode(',',array_map('intval',array_column($usuarios,'id')));
    $periodoSeguro=(int)$periodoId;
    $sqlDocenteJornadas="SELECT uj.usuario_id,uj.jornada_id FROM usuarios_jornadas_gestion uj
        WHERE uj.periodo_id=$periodoSeguro AND uj.usuario_id IN ($ids)
        UNION
        SELECT o.docente_id AS usuario_id,a.jornada_id
        FROM ofertas_academicas o JOIN aulas_periodo ap ON ap.id=o.aula_periodo_id AND ap.activo=1
        JOIN aulas a ON a.id=ap.aula_id
        WHERE o.activo=1 AND ap.periodo_id=$periodoSeguro AND o.docente_id IN ($ids)";
    $res=$conexion->query($sqlDocenteJornadas);
    if(!$res)throw new RuntimeException('No se pudieron recuperar las jornadas de docentes.');
    foreach($res->fetch_all(MYSQLI_ASSOC) as $fila)
        $docenteJornadasMarcadas[(int)$fila['usuario_id']][(int)$fila['jornada_id']]=true;
    $res->free();
}
if($usuarios){
    $ids=implode(',',array_map('intval',array_column($usuarios,'id')));
    // El listado se construye con IDs enteros y se filtra por periodo.
    $s=$conexion->prepare("SELECT ur.usuario_id,r.codigo FROM usuario_roles ur JOIN roles r ON r.id=ur.rol_id
        WHERE ur.usuario_id IN ($ids) AND ((ur.periodo_id IS NULL AND r.codigo IN ('superadmin','subadmin','representante'))
        OR (ur.periodo_id=? AND r.codigo IN ('docente','estudiante')))");
    $s->bind_param('i',$periodoId);$s->execute();
    foreach($s->get_result()->fetch_all(MYSQLI_ASSOC) as $fila)$marcados[(int)$fila['usuario_id']][$fila['codigo']]=true;
    $s->close();
}
$filtroConteo=esSubadmin()?filtroUsuariosJornadasSQL($periodoId,'u'):'';
$s=$conexion->prepare("SELECT r.codigo,COUNT(DISTINCT ur.usuario_id) total FROM usuario_roles ur
 JOIN roles r ON r.id=ur.rol_id JOIN usuarios u ON u.id=ur.usuario_id
 WHERE ((r.codigo IN ('superadmin','subadmin','representante') AND ur.periodo_id IS NULL)
 OR (r.codigo IN ('docente','estudiante') AND ur.periodo_id=?))".$filtroConteo." GROUP BY r.id,r.codigo");
$s->bind_param('i',$periodoId);$s->execute();$estadisticas=$s->get_result()->fetch_all(MYSQLI_ASSOC);$s->close();
$totales=['superadmin'=>0,'subadmin'=>0,'docente'=>0,'estudiante'=>0,'representante'=>0];
foreach($estadisticas as $e)$totales[$e['codigo']]=(int)$e['total'];
$nombres=esSuperadmin()
    ? ['superadmin'=>'Administrador','subadmin'=>'Subadministrador','docente'=>'Docente','estudiante'=>'Estudiante','representante'=>'Representante']
    : ['docente'=>'Docente','estudiante'=>'Estudiante','representante'=>'Representante'];
$tituloPagina='Roles de usuarios';
$subtituloPagina=esSuperadmin()?'Gestiona roles globales y académicos.':'Puedes consultar a otros administradores de tu jornada, pero sus roles están protegidos.';
$nombresRolesVisibles=['superadmin'=>'Administrador','subadmin'=>'Subadministrador','docente'=>'Docente','estudiante'=>'Estudiante','representante'=>'Representante'];
require __DIR__.'/../../partials/header.php';
?>
<style>
/* Panel flotante de roles: no modifica la altura de la fila ni es cortado por la tabla desplazable. */
.sga-roles-form{display:grid!important;grid-template-columns:minmax(0,1fr) auto;align-items:start;gap:8px;min-width:0;width:100%;max-width:460px}
.sga-roles-form>.btn{margin:0;min-height:40px;white-space:nowrap}
.sga-roles-picker{position:relative;display:block;min-width:0;width:100%;color:#234363}
.sga-roles-picker>summary{list-style:none;display:flex;align-items:center;justify-content:space-between;gap:10px;min-height:40px;width:100%;border:1px solid #cfd9e5;border-radius:8px;background:#fff;padding:8px 11px;font-size:12px;font-weight:700;cursor:pointer;user-select:none}
.sga-roles-picker>summary::-webkit-details-marker{display:none}
.sga-roles-picker>summary::after{content:'';display:block;width:8px;height:8px;flex:0 0 8px;border-right:2px solid #41617f;border-bottom:2px solid #41617f;transform:rotate(45deg);transition:transform .15s ease}
.sga-roles-picker[open]>summary{border-color:#508bc8;background:#f7fbff}
.sga-roles-picker[open]>summary::after{transform:rotate(225deg)}
.sga-roles-picker>summary:focus-visible{outline:2px solid #1c6ab8;outline-offset:2px}
.sga-roles-picker-summary{display:block;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
/* Position fixed sale del contenedor .table-wrap (que tiene overflow:auto). JS alinea el flotante con summary. */
.sga-roles-picker-panel{position:fixed;top:0;left:0;z-index:100000;box-sizing:border-box;width:min(455px,calc(100vw - 24px));max-height:min(64dvh,455px);overflow-y:auto;overscroll-behavior:contain;padding:12px;border:1px solid #b9cee5;border-radius:11px;background:#fff;box-shadow:0 18px 45px rgba(8,36,72,.24)}
.sga-roles-panel-title{margin:0 0 10px;font-size:12px;font-weight:800;color:#17365f}
.sga-roles-list{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px;width:100%}
.sga-roles-list label{display:flex;flex-direction:row;align-items:center;gap:9px;min-width:0;margin:0;padding:10px 9px;border:1px solid #dae3ed;border-radius:8px;background:#fff;color:#234363;font-size:12px;line-height:1.3;font-weight:700;cursor:pointer;overflow-wrap:normal;word-break:normal}
.sga-roles-list label:hover{border-color:#81addc;background:#f8fbff}
.sga-roles-list label:has(input:checked){border-color:#8cb7e4;background:#ebf4ff}
.sga-jornadas-list[hidden]{display:none!important}
.sga-jornadas-list[data-sga-docente-jornadas]{background:#f0f8ff;border-color:#c8dfef}
.sga-jornadas-list .sga-jornadas-ayuda{font-size:11px;line-height:1.4;color:#506985;margin:5px 0 8px}
.sga-roles-list input,.sga-jornadas-list input{width:16px!important;height:16px!important;margin:0!important;flex:0 0 16px;padding:0;accent-color:#1255a2;cursor:pointer}
.sga-roles-list label:last-child{grid-column:1/-1}
.sga-jornadas-list{margin-top:12px;background:#f4f7fb;border:1px solid #dbe3ed;padding:11px;border-radius:9px}
.sga-jornadas-list label{display:flex;flex-direction:row;align-items:center;gap:9px;margin:9px 0 0;font-size:12px;cursor:pointer}
.sga-roles-current{display:flex;flex-wrap:wrap;gap:5px;max-width:190px}
@media(max-width:620px){.sga-roles-form{max-width:100%;min-width:0}.sga-roles-current{max-width:none}}
@media(max-width:380px){.sga-roles-list{grid-template-columns:1fr}.sga-roles-list label:last-child{grid-column:auto}.sga-roles-form{grid-template-columns:minmax(0,1fr) auto;gap:6px}.sga-roles-form>.btn{padding-left:7px;padding-right:7px}}
</style>
<link rel="stylesheet" href="<?=e(url('assets/css/sga_catalogo_modales.css'))?>?v=1625">
<script defer src="<?=e(url('assets/js/sga_catalogo_modales.js'))?>?v=1625"></script>
<div class="sga-cat-metrics" aria-label="Usuarios por perfil">
<?php $nombresPlural=['superadmin'=>'Administradores','subadmin'=>'Subadministradores','docente'=>'Docentes','estudiante'=>'Estudiantes','representante'=>'Representantes']; foreach($nombres as $codigo=>$titulo):?><span><strong><?=(int)$totales[$codigo]?></strong> <?=e((int)$totales[$codigo]===1?$titulo:$nombresPlural[$codigo])?></span><?php endforeach;?></div>
<div class="sga-cat-rolebar"><div class="sga-cat-rolebar-heading"><strong>Gestión de accesos</strong><small>Selecciona uno o varios roles por usuario y pulsa Guardar roles.</small></div>
<form method="get">
<label>Período<select name="periodo_id"><?php foreach($periodos as $p):?><option value="<?=(int)$p['id']?>" <?=(int)$p['id']===$periodoId?'selected':''?>><?=e($p['nombre'].' · '.$p['estado'])?></option><?php endforeach;?></select></label>
<label>Buscar usuario<input type="search" name="q" value="<?=e($q)?>" placeholder="Cédula, apellidos o nombres"></label>
<button class="btn btn-secondary" type="submit">Buscar</button>
</form></div>
<details class="sga-cat-help-details"><summary>Información sobre roles y restricciones</summary>
<p>Administrador, Subadministrador y Representante son roles permanentes. Docente y Estudiante se asignan para el período seleccionado. <strong>Docente admite varias jornadas en un mismo período</strong> (por ejemplo, Matutina y Vespertina), sin crear otra cuenta ni otro rol. Las jornadas de Docente no conceden permisos de Subadministrador. Administrador y Subadministrador no pueden combinarse; tampoco Estudiante con Docente o roles administrativos. El Subadministrador solo puede asignar jornadas que administra y no puede modificar cuentas administrativas.</p></details>
<h2 class="section-title">Asignación de roles</h2>
<div class="table-wrap"><table class="table table-responsive-cards"><thead><tr><th>Usuario</th><th>Estado</th><th>Roles actuales</th><th><?=esSuperadmin()?'Seleccionar roles y jornadas':'Seleccionar roles académicos'?></th></tr></thead><tbody>
<?php foreach($usuarios as $u):
    $uid=(int)$u['id'];$actuales=$marcados[$uid]??[];
    $esSub=isset($actuales['subadmin']);
    $esCuentaProtegida=isset($actuales['superadmin'])||isset($actuales['subadmin']);
    $soloConsulta=esSubadmin() && $esCuentaProtegida;
    $marcadas=$asignadas[$uid]??$porDefecto;
?>
<tr>
<td><strong><?=e($u['apellidos'].' '.$u['nombres'])?></strong><div class="mini-note"><?=e($u['cedula'])?></div></td>
<td><span class="badge <?=$u['activo']?'good':'bad'?>"><?=$u['activo']?'Activo':'Inactivo'?></span></td>
<td><div class="sga-roles-current"><?php if(!$actuales):?><span class="badge">Sin roles</span><?php else:foreach($nombresRolesVisibles as $codigo=>$titulo):if(isset($actuales[$codigo])):?><span class="badge"><?=e($titulo)?></span><?php endif;endforeach;endif;?></div></td>
<td>
<?php if($soloConsulta):?>
  <span class="badge">Cuenta administrativa · solo consulta</span>
<?php else:?>
<form method="post" class="sga-roles-form" data-sga-roles-form>
<input type="hidden" name="csrf" value="<?=e($csrf)?>">
<input type="hidden" name="accion" value="guardar_roles">
<input type="hidden" name="usuario_id" value="<?=$uid?>">
<input type="hidden" name="periodo_id" value="<?=$periodoId?>">
<?php
    $rolesSeleccionados=[];
    foreach($nombres as $cod=>$nombre)if(isset($actuales[$cod]))$rolesSeleccionados[]=$nombre;
    $resumenRoles=count($rolesSeleccionados)===0?'Seleccionar roles':
       (count($rolesSeleccionados)<=2?implode(' + ',$rolesSeleccionados):count($rolesSeleccionados).' roles seleccionados');
?>
<details class="sga-roles-picker" data-sga-role-picker>
<summary aria-label="Seleccionar roles de <?=e($u['apellidos'].' '.$u['nombres'])?>">
  <span class="sga-roles-picker-summary" data-sga-role-summary><?=e($resumenRoles)?></span>
</summary>
<div class="sga-roles-picker-panel" data-sga-role-panel>
  <p class="sga-roles-panel-title">Seleccionar roles</p>
  <div class="sga-roles-list" role="group" aria-label="Roles de <?=e($u['apellidos'].' '.$u['nombres'])?>">
  <?php foreach($nombres as $codigo=>$titulo):?>
  <label><input type="checkbox" name="roles[]" value="<?=e($codigo)?>" data-sga-rol="<?=e($codigo)?>" <?=isset($actuales[$codigo])?'checked':''?>><?=e($titulo)?></label>
  <?php endforeach;?>
  </div>
  <div class="sga-jornadas-list" data-sga-docente-jornadas <?=isset($actuales['docente'])?'':'hidden'?> aria-label="Jornadas del docente">
    <div class="mini-note"><strong>Jornadas del Docente · <?=e($periodoNombre)?></strong></div>
    <p class="sga-jornadas-ayuda">Marca una o varias jornadas en las que podrá impartir asignaturas. No cambia permisos administrativos.</p>
    <?php foreach($jornadasDocente as $j):?>
    <label><input type="checkbox" name="docente_jornadas[]" value="<?=(int)$j['id']?>" <?=isset($docenteJornadasMarcadas[$uid][(int)$j['id']])?'checked':''?>><?=e($j['nombre'])?></label>
    <?php endforeach;?>
    <?php if(!$jornadasDocente):?><span class="mini-note">No hay jornadas académicas autorizadas para este período.</span><?php endif;?>
  </div>
  <div class="sga-jornadas-list" data-sga-jornadas <?=esSuperadmin() && $esSub?'':'hidden'?> aria-label="Jornadas del Subadministrador">
    <div class="mini-note"><strong>Jornadas del Subadministrador · <?=e($periodoNombre)?></strong></div>
    <p class="sga-jornadas-ayuda">Selecciona las jornadas que podra administrar como Subadministrador. Son independientes de las jornadas del rol Docente.</p>
    <?php foreach($jornadas as $j):?>
    <label><input type="checkbox" name="jornadas[]" value="<?=(int)$j['id']?>" <?=in_array((int)$j['id'],$marcadas,true)?'checked':''?>><?=e($j['nombre'])?></label>
    <?php endforeach;?>
    <?php if(!$jornadas):?><span class="mini-note">Primero crea jornadas activas.</span><?php endif;?>
  </div>
</div>
</details>
<button class="btn btn-sm btn-primary" type="submit" data-confirm="¿Guardar los roles marcados para esta persona?">Guardar roles</button>
</form>
<?php endif;?>
</td></tr>
<?php endforeach;?>
<?php if(!$usuarios):?><tr><td colspan="4" class="empty">No hay usuarios coincidentes.</td></tr><?php endif;?>
</tbody></table></div>
<script>
(function(){
  'use strict';
  var selectores=Array.from(document.querySelectorAll('[data-sga-role-picker]'));
  var abierto=null;
  function cerrar(selector, devolverFoco){
    if(!selector || !selector.open) return;
    selector.open=false;
    if(devolverFoco){var disparador=selector.querySelector('summary');if(disparador)disparador.focus();}
  }
  function posicionar(selector){
    if(!selector || !selector.open) return;
    var summary=selector.querySelector('summary');
    var panel=selector.querySelector('[data-sga-role-panel]');
    if(!summary || !panel) return;
    var r=summary.getBoundingClientRect();
    var w=window.innerWidth, h=window.innerHeight, borde=12, separacion=6;
    if(r.bottom<0 || r.top>h){cerrar(selector,false);return;}
    var ancho=Math.max(180,Math.min(455,w-2*borde));
    var altoDeseado=Math.min(455,panel.scrollHeight+2,h-2*borde);
    var abajo=Math.max(0,h-r.bottom-borde-separacion);
    var arriba=Math.max(0,r.top-borde-separacion);
    var haciaArriba=abajo<Math.min(230,altoDeseado) && arriba>abajo;
    var disponible=haciaArriba?arriba:abajo;
    var altoMax=Math.max(70,Math.min(altoDeseado,disponible));
    panel.style.width=ancho+'px';
    panel.style.maxHeight=altoMax+'px';
    panel.style.left=Math.min(Math.max(r.left,borde),w-ancho-borde)+'px';
    panel.style.top=(haciaArriba?Math.max(borde,r.top-separacion-altoMax):Math.min(h-borde-altoMax,r.bottom+separacion))+'px';
    panel.dataset.sgaAbre=haciaArriba?'arriba':'abajo';
  }
  selectores.forEach(function(selector){
    var form=selector.closest('[data-sga-roles-form]');
    var sub=form.querySelector('[data-sga-rol="subadmin"]');
    var docente=form.querySelector('[data-sga-rol="docente"]');
    var jornadas=form.querySelector('[data-sga-jornadas]');
    var docentesJornadas=form.querySelector('[data-sga-docente-jornadas]');
    var resumen=form.querySelector('[data-sga-role-summary]');
    var casillas=Array.from(form.querySelectorAll('[data-sga-rol]'));
    function actualizar(){
      if(sub&&jornadas)jornadas.hidden=!sub.checked;
      if(docente&&docentesJornadas)docentesJornadas.hidden=!docente.checked;
      var titulos=casillas.filter(function(c){return c.checked;}).map(function(c){return c.closest('label').textContent.trim();});
      if(resumen)resumen.textContent=titulos.length===0?'Seleccionar roles':
         (titulos.length<=2?titulos.join(' + '):titulos.length+' roles seleccionados');
      if(selector.open)posicionar(selector);
    }
    casillas.forEach(function(c){c.addEventListener('change',actualizar);});
    if(jornadas)jornadas.querySelectorAll('input[type="checkbox"]').forEach(function(c){c.addEventListener('change',function(){posicionar(selector);});});
    if(docentesJornadas)docentesJornadas.querySelectorAll('input[type="checkbox"]').forEach(function(c){c.addEventListener('change',function(){posicionar(selector);});});
    form.addEventListener('submit',function(event){
      if(docente && docente.checked && docentesJornadas && !docentesJornadas.querySelector('input[type="checkbox"]:checked')){
        event.preventDefault();
        alert('Selecciona al menos una jornada para el rol Docente.');
        if(!selector.open)selector.open=true;
        posicionar(selector);
        var primera=docentesJornadas.querySelector('input[type="checkbox"]');
        if(primera)primera.focus();
      }
    });
    selector.addEventListener('toggle',function(){
      if(selector.open){
        if(abierto&&abierto!==selector)cerrar(abierto,false);
        abierto=selector;
        posicionar(selector);
      } else if(abierto===selector)abierto=null;
    });
    actualizar();
  });
  // Cierra al pulsar fuera o al abrir otro selector; dentro del panel las casillas permanecen abiertas.
  document.addEventListener('pointerdown',function(ev){
    if(abierto&&abierto.open&&!abierto.contains(ev.target))cerrar(abierto,false);
  });
  document.addEventListener('keydown',function(ev){
    if(ev.key==='Escape'&&abierto&&abierto.open){ev.preventDefault();cerrar(abierto,true);}
  });
  window.addEventListener('resize',function(){posicionar(abierto);},{passive:true});
  // Captura incluso el desplazamiento de la tabla o la pagina principal.
  document.addEventListener('scroll',function(){posicionar(abierto);},true);
})();
</script>
<?php require __DIR__.'/../../partials/footer.php'; ?>
