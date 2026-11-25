<?php
/** SGA UNEDID | Historial de notificaciones + composicion en ventana flotante. */
require_once __DIR__.'/../../lib/sga_notificaciones_jornadas.php';
exigirLogin();
$periodoId=(int)(periodoActivo()['id']??0);
if(!$periodoId){http_response_code(409);exit('Se necesita un periodo academico activo.');}
$actor=(int)($_SESSION['usuario_id']??0);
$modo=esAdminAcademico()?'administracion':(esDocenteOperativo($periodoId)?'docente':(esRepresentanteOperativo()?'representante':''));
if($modo===''){http_response_code(403);exit('No tienes acceso al modulo de notificaciones.');}
$ctx=sgaNotiContextoActor($periodoId,$actor,$modo);
if(!$ctx){http_response_code(403);exit('No tienes jornadas o asignaturas autorizadas para enviar notificaciones.');}
$instalado=sgaNotiTablasInstaladas();
$base='modulos/notificaciones/index.php';
if(empty($_SESSION['csrf_notificaciones_grupos']))$_SESSION['csrf_notificaciones_grupos']=bin2hex(random_bytes(24));
if(empty($_SESSION['nonce_notificaciones_grupos']))$_SESSION['nonce_notificaciones_grupos']=bin2hex(random_bytes(24));
$csrf=(string)$_SESSION['csrf_notificaciones_grupos'];
$catalogo=sgaNotiJornadas($periodoId,$ctx);
$ofertas=$modo==='docente'?sgaNotiOfertasDocente($periodoId,$actor,$ctx):[];
$hijos=$modo==='representante'?sgaNotiHijosRepresentante($periodoId,$actor,$ctx):[];
$aulas=$modo==='administracion'?sgaNotiAulas($periodoId,$ctx):[];
$tiposAdmin=[
    'individual'=>'Buscar y seleccionar personas',
    'estudiantes_aula'=>'Estudiantes de un aula',
    'familias_aula'=>'Representantes de los estudiantes de un aula',
    'docentes_aula'=>'Docentes de un aula',
    'docentes_jornada'=>'Docentes de una jornada',
    'subadmins_jornada'=>'Subadministradores de una jornada',
    'todos_estudiantes'=>'Todos los estudiantes de la jornada',
    'todos_docentes'=>'Todos los docentes de la jornada',
    'todos_representantes'=>'Todos los padres y representantes de la jornada',
    'todos_todos'=>'Todos: estudiantes, docentes y representantes de la jornada',
];
$tiposDocente=[
    'estudiantes_asignatura'=>'Estudiantes de mi asignatura',
    'familias_asignatura'=>'Representantes de mis estudiantes (hijos)',
    'docentes_jornada'=>'Otros docentes de mi jornada',
    'subadmins_jornada'=>'Subadministradores de mi jornada',
    'individual'=>'Buscar docente, estudiante, representante o subadministrador',
];
$tiposRepresentante=[
    'individual'=>'Buscar un docente o subadministrador',
    'docentes_hijo'=>'Todos los docentes del aula de mi hijo/a',
    'subadmins_hijo'=>'Subadministradores de la jornada de mi hijo/a',
];
$tipos=$modo==='docente'?$tiposDocente:($modo==='representante'?$tiposRepresentante:$tiposAdmin);
$tipo=(string)($_SERVER['REQUEST_METHOD']==='GET'?($_GET['tipo_destino']??array_key_first($tipos)) : ($_POST['tipo_destino']??array_key_first($tipos)));
if(!isset($tipos[$tipo]))$tipo=array_key_first($tipos);
$ofertaId=(int)($_SERVER['REQUEST_METHOD']==='GET'?($_GET['oferta_id']??0):($_POST['oferta_id']??0));
$ofertaElegida=null;
if($modo==='docente'){
    foreach($ofertas as $oferta){if((int)$oferta['id']===$ofertaId){$ofertaElegida=$oferta;break;}}
    if(!$ofertaElegida && $ofertas){$ofertaElegida=$ofertas[0];$ofertaId=(int)$ofertaElegida['id'];}
}
$hijoId=(int)($_SERVER['REQUEST_METHOD']==='GET'?($_GET['hijo_id']??0):($_POST['hijo_id']??0));
$hijoElegido=null;
if($modo==='representante'){
    foreach($hijos as $h){if((int)$h['estudiante_id']===$hijoId){$hijoElegido=$h;break;}}
    if(!$hijoElegido && $hijos && $_SERVER['REQUEST_METHOD']==='GET'){
        $hijoElegido=$hijos[0];$hijoId=(int)$hijoElegido['estudiante_id'];
    }
}
$jornadaId=(int)($_SERVER['REQUEST_METHOD']==='GET'?($_GET['jornada_id']??0):($_POST['jornada_id']??0));
if($modo==='docente'){
    $jornadaId=(int)($ofertaElegida['jornada_id']??0);
}elseif($modo==='representante'){
    $jornadaId=(int)($hijoElegido['jornada_id']??0);
}else{
    if($jornadaId===0 && !isset($_GET['jornada_id']) && !isset($_POST['jornada_id'])){
        $jidVista=(int)($_SESSION['jornada_vista_periodos'][$periodoId]??0);
        if(in_array($jidVista,$ctx['jornadas'],true))$jornadaId=$jidVista;
    }
    try{sgaNotiComprobarJornada($ctx,$jornadaId);}catch(DomainException $e){$jornadaId=0;}
}
$aulaId=(int)($_SERVER['REQUEST_METHOD']==='GET'?($_GET['aula_periodo_id']??0):($_POST['aula_periodo_id']??0));
$busqueda=trim((string)($_GET['q']??''));$busqueda=substr($busqueda,0,80);
$tipoUsuario=(string)($_GET['tipo_usuario']??'');
if(!in_array($tipoUsuario,['','docente','estudiante','representante'],true))$tipoUsuario='';
$pagina=max(1,min(10000,(int)($_GET['pagina']??1)));
$histPagina=max(1,min(10000,(int)($_GET['hist_pagina']??1)));
$abrirNuevo=isset($_GET['nuevo']) && $_GET['nuevo']==='1';

if(($_SERVER['REQUEST_METHOD']??'')==='POST'){
    try{
        if(!hash_equals($csrf,(string)($_POST['csrf']??'')))throw new DomainException('El formulario caduco. Actualiza la pagina.');
        if(!$instalado)throw new DomainException('Primero ejecuta el SQL del nuevo parche.');
        $accion=(string)($_POST['accion']??'');
        if($accion==='enviar'){
            $nonce=(string)($_POST['nonce']??'');
            if(!$nonce||!hash_equals((string)($_SESSION['nonce_notificaciones_grupos']??''),$nonce))
                throw new DomainException('El envio ya se proceso o la pagina caduco.');
            $tipoPost=(string)($_POST['tipo_destino']??'');
            if(!isset($tipos[$tipoPost]))throw new DomainException('Grupo no permitido.');
            $idsPost=$_POST['destinatarios']??[];
            if(!is_array($idsPost)||count($idsPost)>10)throw new DomainException('Para envio individual selecciona hasta 10 personas.');
            $ids=[];
            foreach($idsPost as $v){
                if(!is_scalar($v)||!ctype_digit((string)$v))throw new DomainException('La lista contiene destinatarios invalidos.');
                $ids[]=(int)$v;
            }
            $jidPost=(int)($_POST['jornada_id']??0);
            $ofPost=(int)($_POST['oferta_id']??0);
            $hijoPost=0;
            if($modo==='representante'){
                $hijoPost=(int)($_POST['hijo_id']??0);
                $hijoValidado=sgaNotiHijoValido($periodoId,$actor,$ctx,$hijoPost);
                $jidPost=(int)$hijoValidado['jornada_id'];
            }
            if($modo==='docente'){
                // El servidor comprueba que la asignatura esta asignada al remitente.
                $ofertaPost=sgaNotiOfertaValida($periodoId,$actor,$ctx,$ofPost);
                $jidPost=(int)$ofertaPost['jornada_id'];
            }
            $resultado=sgaNotiCrear($periodoId,$actor,$ctx,$jidPost,$ids,
                (string)($_POST['asunto']??''),(string)($_POST['mensaje']??''),
                $tipoPost,(int)($_POST['aula_periodo_id']??0),$ofPost,$hijoPost);
            $_SESSION['nonce_notificaciones_grupos']=bin2hex(random_bytes(24));
            $texto='Notificacion registrada para '.(int)$resultado['total'].' destinatario(s), sin correos duplicados.';
            // Un lote SMTP corto sale ahora; el resto permanece pendiente para el cron.
            try{
                $lote=sgaNotiEnviarPendientes(10,(int)$resultado['id'],$actor);
                $texto.=' Enviados: '.(int)$lote['enviados'].'.';
                if((int)$resultado['total']>(int)$lote['enviados'])$texto.=' Revisa los pendientes en el historial.';
                flash(($lote['errores']||$lote['omitidos'])?'error':'success',$texto);
            }catch(Throwable $mailError){
                error_log('[SGA] Envio SMTP diferido: '.get_class($mailError));
                flash('error',$texto.' El servicio de correo no completo el primer lote. Revisa pendientes.');
            }
        }elseif($accion==='reintentar'){
            $lote=sgaNotiEnviarPendientes(30,null,$actor);
            flash('success','Cola revisada. Enviados: '.$lote['enviados'].', fallidos: '.$lote['errores'].', omitidos: '.$lote['omitidos'].'.');
        }else throw new DomainException('Accion no reconocida.');
    }catch(Throwable $e){
        error_log('[SGA] Notificaciones: '.get_class($e));
        flash('error',$e instanceof DomainException?$e->getMessage():'No se pudo enviar. Verifica la configuracion o contacta a soporte.');
    }
    redir($base);
}

$personas=[];$haySiguiente=false;
if($abrirNuevo && $tipo==='individual'){
    try{
        if($modo==='docente'){
            if($ofertaElegida)$personas=sgaNotiBuscarDocente($periodoId,$actor,$ctx,$ofertaId,$busqueda,[],$pagina,25);
        }elseif($modo==='representante'){
            if($hijoElegido)$personas=sgaNotiBuscarRepresentante($periodoId,$actor,$ctx,$hijoId,$busqueda,[],$pagina,25);
        }else $personas=sgaNotiBuscar($periodoId,$ctx,$jornadaId,$busqueda,$tipoUsuario,[],$pagina,25);
        $haySiguiente=count($personas)>25;
        if($haySiguiente)$personas=array_slice($personas,0,25);
    }catch(Throwable $e){error_log('[SGA] Busqueda notificaciones: '.get_class($e));$personas=[];}
}
$historial=[];$tieneMasHist=false;
if($instalado){
    $histSql="SELECT n.id,n.asunto,n.grupo_etiqueta,n.tipo_destino,n.creado_en,
        COUNT(e.id) total,COALESCE(SUM(e.estado='enviado'),0) enviados,
        COALESCE(SUM(e.estado='pendiente' OR e.estado='enviando'),0) pendientes,
        COALESCE(SUM(e.estado='error'),0) errores,
        COALESCE(SUM(e.estado='omitido'),0) omitidos
        FROM sga_notificaciones_jornadas n
        LEFT JOIN sga_notificaciones_jornadas_envios e ON e.notificacion_id=n.id
        WHERE n.periodo_id=? AND n.remitente_id=?
        GROUP BY n.id,n.asunto,n.grupo_etiqueta,n.tipo_destino,n.creado_en
        ORDER BY n.id DESC LIMIT 21 OFFSET ".(($histPagina-1)*20);
    $stmt=$conexion->prepare($histSql);
    if($stmt){$stmt->bind_param('ii',$periodoId,$actor);
        if($stmt->execute())$historial=$stmt->get_result()->fetch_all(MYSQLI_ASSOC);
        $stmt->close();}
    $tieneMasHist=count($historial)>20;
    if($tieneMasHist)$historial=array_slice($historial,0,20);
}
$tituloPagina='Notificaciones';
$subtituloPagina='Historial de notificaciones por correo institucional.';
require __DIR__.'/../../partials/header.php';
?>
<style>
.sga-n-bar{display:flex;justify-content:space-between;align-items:center;gap:14px;flex-wrap:wrap;margin-bottom:15px}
.sga-n-bar h2{margin:0 0 4px;font-size:20px}.sga-n-muted{font-size:13px;color:#60728b;margin:0}
.sga-n-actions{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.sga-n-table td,.sga-n-table th{padding:12px 13px}.sga-n-table{min-width:660px}
.sga-n-status{font-size:12px;color:#526984;white-space:nowrap}.sga-n-empty{padding:38px 12px;text-align:center;color:#61738d}
.sga-n-dialog{position:fixed;inset:0;margin:auto;padding:0;width:min(850px,calc(100vw - 20px));max-width:calc(100vw - 20px);max-height:calc(100dvh - 20px);border:1px solid #d4dfec;border-radius:15px;background:#fff;color:#1c3351;box-shadow:0 22px 80px rgba(4,19,41,.35);overflow-y:auto;overscroll-behavior:contain}
.sga-n-dialog:not([open]){display:none}.sga-n-dialog::backdrop{background:rgba(3,18,38,.66);backdrop-filter:blur(2px)}
.sga-n-head{display:flex;align-items:flex-start;justify-content:space-between;padding:18px 20px 15px;border-bottom:1px solid #e1e8f1;gap:12px}
.sga-n-head h2{margin:0;color:#153f6c;font-size:20px}.sga-n-head p{color:#60728b;font-size:12px;margin:5px 0 0}
.sga-n-close{border:0;background:#eef3f9;color:#183c63;font-size:24px;line-height:1;border-radius:9px;padding:7px 12px;cursor:pointer}
.sga-n-content{padding:17px 20px 20px}.sga-n-filter{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:0 0 16px}
.sga-n-filter label,.sga-n-compose label{display:block;font-size:13px;font-weight:700;color:#264769}
.sga-n-filter select,.sga-n-filter input,.sga-n-compose input,.sga-n-compose textarea{display:block;width:100%;margin-top:5px;box-sizing:border-box}
.sga-n-full{grid-column:1/-1}.sga-n-filter-row{display:flex;gap:8px;align-items:end}
.sga-n-box{background:#f5f8fc;border:1px solid #dce7f4;border-radius:10px;padding:12px 14px;margin:12px 0;font-size:13px;color:#365775}
.sga-n-choice{border:1px solid #dde7f1;border-radius:10px;overflow:hidden;margin:10px 0}
.sga-n-choice .table-wrap{max-height:230px;overflow-y:auto}.sga-n-choice table{width:100%;border-collapse:collapse;min-width:570px}
.sga-n-choice th,.sga-n-choice td{padding:9px 12px;border-bottom:1px solid #ecf0f6;text-align:left;font-size:13px}
.sga-n-compose{display:grid;gap:11px;margin:13px 0}.sga-n-compose textarea{min-height:125px;resize:vertical}
.sga-n-buttons{display:flex;justify-content:flex-end;gap:10px;flex-wrap:wrap;margin-top:18px}
.sga-n-pager{display:flex;justify-content:space-between;align-items:center;gap:8px;margin:12px 0 0;flex-wrap:wrap}
.sga-n-pager a{font-size:13px}.sga-n-tick{width:18px;height:18px;accent-color:#002f6c}
.sga-n-count{font-size:12px;color:#5f7590}.sga-n-dialog:focus-visible,.sga-n-dialog button:focus-visible{outline:3px solid #5e9de7;outline-offset:2px}
@media(max-width:620px){.sga-n-filter{grid-template-columns:1fr}.sga-n-content{padding:15px 13px}.sga-n-head{padding:15px 13px}.sga-n-filter-row{flex-wrap:wrap}}
</style>
<?php if(!$instalado): ?>
<div class="alert error"><strong>Instalacion pendiente:</strong> ejecuta el SQL <code>sql/SQL_SGA_NOTIFICACIONES_COMUNIDAD_Y_REPRESENTANTES.sql</code> para habilitar el envio por grupos e historial.</div>
<?php endif; ?>
<section class="card">
  <div class="sga-n-bar">
    <div><h2>Notificaciones enviadas</h2><p class="sga-n-muted">Correos registrados por tu usuario en este periodo academico.</p></div>
    <div class="sga-n-actions">
      <button type="button" class="btn btn-primary" id="sga-n-nuevo" <?=$instalado?'':'disabled'?>>+ Enviar notificaci&oacute;n</button>
    </div>
  </div>
  <div class="table-wrap"><table class="table sga-n-table">
    <thead><tr><th>Fecha</th><th>Asunto</th><th>Grupo destinatario</th><th>Entrega</th></tr></thead>
    <tbody>
    <?php foreach($historial as $h): ?>
      <tr>
        <td style="white-space:nowrap"><?=e($h['creado_en'])?></td>
        <td><strong><?=e($h['asunto'])?></strong><div class="muted" style="font-size:11px">#<?=(int)$h['id']?></div></td>
        <td><?=e($h['grupo_etiqueta']?:'Destinatarios individuales')?></td>
        <td class="sga-n-status">
          <strong><?=(int)$h['enviados']?> / <?=(int)$h['total']?> enviados</strong>
          <?php if((int)$h['pendientes']>0):?><div>Pendientes: <?=(int)$h['pendientes']?></div><?php endif;?>
          <?php if((int)$h['errores']>0):?><div style="color:#a93a3a">Fallidos: <?=(int)$h['errores']?></div><?php endif;?>
          <?php if((int)$h['omitidos']>0):?><div>Omitidos: <?=(int)$h['omitidos']?></div><?php endif;?>
        </td>
      </tr>
    <?php endforeach; ?>
    <?php if(!$historial):?><tr><td colspan="4"><div class="sga-n-empty">A&uacute;n no tienes notificaciones enviadas en este per&iacute;odo.</div></td></tr><?php endif;?>
    </tbody></table></div>
  <div class="sga-n-pager">
    <div class="sga-n-actions">
      <?php if($histPagina>1):?><a class="btn btn-secondary" href="<?=e(url($base.'?hist_pagina='.($histPagina-1)))?>">&larr; Anterior</a><?php endif;?>
      <?php if($tieneMasHist):?><a class="btn btn-secondary" href="<?=e(url($base.'?hist_pagina='.($histPagina+1)))?>">Siguiente &rarr;</a><?php endif;?>
    </div>
    <?php if($instalado):?><form method="post" action="<?=e(url($base))?>">
      <input type="hidden" name="csrf" value="<?=e($csrf)?>"><input type="hidden" name="accion" value="reintentar">
      <button type="submit" class="btn btn-secondary">Procesar correos pendientes</button>
    </form><?php endif;?>
  </div>
</section>

<dialog class="sga-n-dialog" id="sga-n-dialog" aria-labelledby="sga-n-dialog-title">
 <div class="sga-n-head">
  <div><h2 id="sga-n-dialog-title">Enviar notificaci&oacute;n</h2><p>Selecciona un grupo o busca personas y redacta el mensaje.</p></div>
  <button type="button" id="sga-n-cerrar" class="sga-n-close" aria-label="Cerrar">&times;</button>
 </div>
 <div class="sga-n-content">
  <?php if($modo==='docente'&&!$ofertas):?><div class="alert error">No tienes asignaturas activas asignadas en este per&iacute;odo.</div><?php endif;?>
  <?php if($modo==='representante'&&!$hijos):?><div class="alert error">No tienes hijos matriculados con vinculaci&oacute;n activa en este per&iacute;odo.</div><?php endif;?>
  <form method="get" action="<?=e(url($base))?>" class="sga-n-filter" id="sga-n-filtros">
    <input type="hidden" name="nuevo" value="1"><input type="hidden" name="pagina" value="1">
    <?php if($modo==='docente'): ?>
      <label class="sga-n-full">Asignatura que identifica al docente remitente
        <select name="oferta_id" id="sga-n-oferta" required onchange="this.form.submit()">
        <?php foreach($ofertas as $o):?><option value="<?=(int)$o['id']?>" <?=(int)$o['id']===$ofertaId?'selected':''?>><?=e($o['etiqueta'])?></option><?php endforeach; ?>
        </select>
      </label>
    <?php elseif($modo==='representante'): ?>
      <label class="sga-n-full">Hijo/a, aula y jornada de la notificaci&oacute;n
        <select name="hijo_id" required onchange="this.form.submit()">
          <?php foreach($hijos as $h):?><option value="<?=(int)$h['estudiante_id']?>" <?=(int)$h['estudiante_id']===$hijoId?'selected':''?>><?=e($h['etiqueta'])?></option><?php endforeach;?>
        </select>
      </label>
    <?php else: ?>
      <label>Jornada
        <select name="jornada_id" id="sga-n-jornada" onchange="this.form.submit()">
          <option value="0" <?=$jornadaId===0?'selected':''?>><?=$ctx['super']?'Todas las jornadas':'Todas mis jornadas'?></option>
          <?php foreach($catalogo as $j):?><option value="<?=(int)$j['id']?>" <?=$jornadaId===(int)$j['id']?'selected':''?>><?=e($j['nombre'])?></option><?php endforeach;?>
        </select>
      </label>
    <?php endif;?>
    <label class="<?=$modo==='docente'||$modo==='representante'?'sga-n-full':''?>">Destinatarios
      <select name="tipo_destino" id="sga-n-tipo" onchange="this.form.submit()">
        <?php foreach($tipos as $valor=>$etiqueta):?><option value="<?=e($valor)?>" <?=$tipo===$valor?'selected':''?>><?=e($etiqueta)?></option><?php endforeach;?>
      </select>
    </label>
    <?php if($tipo==='individual'): ?>
      <label class="sga-n-full">Buscar destinatario (opcional)
        <div class="sga-n-filter-row">
          <input name="q" type="search" maxlength="80" value="<?=e($busqueda)?>" placeholder="Nombres, apellidos, c&eacute;dula o correo" autocomplete="off">
          <?php if($modo==='administracion'): ?>
            <select name="tipo_usuario" style="max-width:170px">
              <option value="">Todos</option>
              <?php foreach(['docente'=>'Docentes','estudiante'=>'Estudiantes','representante'=>'Representantes'] as $v=>$txt):?>
                <option value="<?=$v?>" <?=$tipoUsuario===$v?'selected':''?>><?=$txt?></option>
              <?php endforeach;?>
            </select>
          <?php endif; ?>
          <button class="btn btn-secondary" type="submit">Buscar</button>
        </div>
      </label>
    <?php elseif($modo==='administracion' && in_array($tipo,['estudiantes_aula','familias_aula','docentes_aula'],true)): ?>
      <label class="sga-n-full">Aula del per&iacute;odo
        <select name="aula_periodo_id" id="sga-n-aula" onchange="this.form.submit()" required>
          <option value="0">Selecciona un aula</option>
          <?php foreach($aulas as $a):if($jornadaId>0 && (int)$a['jornada_id']!==$jornadaId)continue;?>
            <option value="<?=(int)$a['id']?>" <?=$aulaId===(int)$a['id']?'selected':''?>><?=e($a['etiqueta'])?></option>
          <?php endforeach; ?>
        </select>
      </label>
    <?php elseif(in_array($tipo,['docentes_jornada','subadmins_jornada'],true) && $modo==='administracion' && $jornadaId===0): ?>
      <p class="sga-n-box sga-n-full">Para este grupo selecciona una jornada espec&iacute;fica.</p>
    <?php endif;?>
  </form>
  <form method="post" action="<?=e(url($base))?>" id="sga-n-enviar">
    <input type="hidden" name="accion" value="enviar">
    <input type="hidden" name="csrf" value="<?=e($csrf)?>">
    <input type="hidden" name="nonce" value="<?=e($_SESSION['nonce_notificaciones_grupos'])?>">
    <input type="hidden" name="tipo_destino" value="<?=e($tipo)?>">
    <input type="hidden" name="jornada_id" value="<?=$jornadaId?>">
    <input type="hidden" name="oferta_id" value="<?=$ofertaId?>">
    <input type="hidden" name="hijo_id" value="<?=$hijoId?>">
    <input type="hidden" name="aula_periodo_id" value="<?=$aulaId?>">
    <?php if($tipo==='individual'): ?>
      <div class="sga-n-choice"><div class="table-wrap"><table>
        <thead><tr><th style="width:38px"><input id="sga-n-marcar-todos" type="checkbox" aria-label="Seleccionar todos"></th><th>Nombre</th><th>Perfil</th><th>Correo</th></tr></thead>
        <tbody>
        <?php foreach($personas as $p):$valido=(bool)filter_var((string)$p['correo'],FILTER_VALIDATE_EMAIL);?>
          <tr><td><input class="sga-n-tick" type="checkbox" name="destinatarios[]" value="<?=(int)$p['id']?>" <?=$valido?'':'disabled'?>></td>
            <td><strong><?=e(trim($p['apellidos'].' '.$p['nombres']))?></strong><div class="muted" style="font-size:11px"><?=e($p['cedula'])?></div></td>
            <td><?=e($p['tipo'])?></td><td><?=e($p['correo']?:'Sin correo')?></td></tr>
        <?php endforeach;?>
        <?php if(!$personas):?><tr><td colspan="4" style="text-align:center">No se encontraron personas en el grupo autorizado.</td></tr><?php endif;?>
        </tbody></table></div></div>
      <div class="sga-n-pager">
        <small class="sga-n-count" id="sga-n-contador">Selecciona de 1 a 10 personas.</small>
        <div class="sga-n-actions">
        <?php
        $params=['nuevo'=>1,'tipo_destino'=>$tipo,'oferta_id'=>$ofertaId,'hijo_id'=>$hijoId,'jornada_id'=>$jornadaId,'aula_periodo_id'=>$aulaId,'q'=>$busqueda,'tipo_usuario'=>$tipoUsuario];
        if($pagina>1){$params['pagina']=$pagina-1;}
        ?>
        <?php if($pagina>1):?><a href="<?=e(url($base.'?'.http_build_query($params,'','&',PHP_QUERY_RFC3986)))?>">&larr; Anterior</a><?php endif;?>
        <?php if($haySiguiente):$params['pagina']=$pagina+1;?><a href="<?=e(url($base.'?'.http_build_query($params,'','&',PHP_QUERY_RFC3986)))?>">Siguiente &rarr;</a><?php endif;?>
        </div>
      </div>
    <?php else: ?>
      <div class="sga-n-box">
        <strong>Env&iacute;o por grupo:</strong> los integrantes se calculan al enviar, seg&uacute;n el per&iacute;odo, jornada, aula y asignatura autorizados. Cada correo se env&iacute;a una sola vez, incluso si el usuario tiene varias materias.
      </div>
    <?php endif;?>
    <div class="sga-n-compose">
      <label>Asunto<input type="text" name="asunto" required minlength="4" maxlength="150" placeholder="Ejemplo: Convocatoria a reuni&oacute;n acad&eacute;mica"></label>
      <label>Mensaje<textarea name="mensaje" required minlength="5" maxlength="4000" placeholder="Escribe la notificaci&oacute;n institucional..."></textarea></label>
    </div>
    <?php if($modo==='docente' && $ofertaElegida): ?>
      <div class="sga-n-box"><strong>Firma autom&aacute;tica del correo:</strong><div><?=e(trim((string)(usuarioActual()['apellidos']??'').' '.(string)(usuarioActual()['nombres']??'')))?></div><div>Docente de la asignatura: <?=e($ofertaElegida['asignatura'])?></div><div>Jornada: <?=e($ofertaElegida['jornada'])?></div></div>
    <?php elseif($modo==='representante' && $hijoElegido): ?>
      <div class="sga-n-box"><strong>Firma autom&aacute;tica:</strong><div><?=e(trim((string)(usuarioActual()['apellidos']??'').' '.(string)(usuarioActual()['nombres']??'')))?></div><div>Representante de: <?=e($hijoElegido['hijo_nombre'])?></div><div>Aula: <?=e($hijoElegido['aula_nombre'])?> · Jornada: <?=e($hijoElegido['jornada'])?></div></div>
    <?php else: ?><div class="sga-n-box">Al final del correo se incluir&aacute;n el nombre del remitente y el grupo destinatario.</div><?php endif;?>
    <div class="sga-n-buttons">
      <button type="button" class="btn btn-secondary" id="sga-n-cancelar">Cancelar</button>
      <button type="submit" class="btn btn-primary" <?=$instalado && ($modo==='administracion'||($modo==='docente'&&$ofertaElegida)||($modo==='representante'&&$hijoElegido))?'':'disabled'?>>Enviar correos</button>
    </div>
  </form>
 </div>
</dialog>
<script>
(function(){
 const dialog=document.getElementById('sga-n-dialog');
 const open=document.getElementById('sga-n-nuevo');
 function show(){if(!dialog)return; if(typeof dialog.showModal==='function'){if(!dialog.open)dialog.showModal();}else{dialog.setAttribute('open','');}}
 function close(){if(!dialog)return;if(typeof dialog.close==='function')dialog.close();else dialog.removeAttribute('open');}
 if(open)open.addEventListener('click',show);
 for(const id of ['sga-n-cerrar','sga-n-cancelar']){const b=document.getElementById(id);if(b)b.addEventListener('click',close);}
 if(dialog)dialog.addEventListener('click',function(e){if(e.target===dialog)close();});
 const all=document.getElementById('sga-n-marcar-todos');
 const checks=[...document.querySelectorAll('input.sga-n-tick:not(:disabled)')];
 const counter=document.getElementById('sga-n-contador');
 function count(){const n=checks.filter(c=>c.checked).length;if(counter)counter.textContent=n+' destinatario(s) seleccionado(s), maximo 10.';if(all)all.checked=checks.length>0&&n===checks.length;}
 if(all)all.addEventListener('change',function(){checks.forEach((c,i)=>{c.checked=this.checked&&i<10;});count();});
 checks.forEach(c=>c.addEventListener('change',function(){if(checks.filter(c=>c.checked).length>10){this.checked=false;alert('Maximo 10 destinatarios individuales.');}count();}));
 count();
 const send=document.getElementById('sga-n-enviar');
 if(send)send.addEventListener('submit',function(event){
   if(checks.length && !checks.some(c=>c.checked)){event.preventDefault();alert('Selecciona al menos una persona.');return;}
   if(!confirm('¿Deseas registrar y enviar esta notificacion a los destinatarios seleccionados?'))event.preventDefault();
 });
 <?php if($abrirNuevo):?>show();<?php endif;?>
})();
</script>
<?php require __DIR__.'/../../partials/footer.php'; ?>
