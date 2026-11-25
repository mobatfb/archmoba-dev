<?php
require_once __DIR__.'/../../lib/funciones.php';
require_once __DIR__.'/../../lib/reportes_calificaciones.php';
require_once __DIR__.'/../../lib/comportamiento_trimestres.php';
exigirAdminAcademico();
// Token de uso exclusivo del formulario de descarga masiva (POST).
if (empty($_SESSION['csrf_certificados_zip'])) {
  $_SESSION['csrf_certificados_zip']=bin2hex(random_bytes(24));
}
$csrfCertificadosZip=(string)$_SESSION['csrf_certificados_zip'];
$p=periodoActivo();$pid=(int)($_GET['periodo_id']??($p['id']??0));$apid=(int)($_GET['aula_periodo_id']??0);
$pid=periodoInicialSubadmin($pid,isset($_GET['periodo_id'])?1:0);
if($pid>0)exigirAccesoPeriodo($pid);elseif(esSubadmin()){http_response_code(403);die('Periodo no autorizado.');}
if($apid>0)exigirAccesoAulaPeriodo($apid);
$periodos=$conexion->query('SELECT * FROM periodos_academicos ORDER BY anio_inicio DESC')->fetch_all(MYSQLI_ASSOC);
$aulas=[];
if($pid){
  $stmt=$conexion->prepare("SELECT ap.id,a.nivel,a.nombre,a.paralelo,a.resultados_cualitativos FROM aulas_periodo ap JOIN aulas a ON a.id=ap.aula_id WHERE ap.periodo_id=? AND ap.activo=1".filtroJornadasSQL($pid,'a')." ORDER BY a.id ASC");
  $stmt->bind_param('i',$pid);$stmt->execute();$aulas=$stmt->get_result()->fetch_all(MYSQLI_ASSOC);$stmt->close();
  if(!$apid&&$aulas)$apid=(int)$aulas[0]['id'];
}
$ofertas=[];$estudiantes=[];$notas=[];$notasComportamiento=[];$aulaActual=null;$configConsolidado=$pid?obtenerConfiguracion($pid):[];
if($apid){
  if(!in_array($apid,array_map('intval',array_column($aulas,'id')),true)){http_response_code(403);die('El aula no pertenece al periodo o jornada autorizados.');}
  foreach($aulas as $a)if((int)$a['id']===$apid)$aulaActual=$a;
  $stmt=$conexion->prepare('SELECT o.id,CASE WHEN o.evaluacion_aula=1 THEN \'Evaluación cualitativa del aula\' ELSE s.nombre END asignatura,s.usa_literal_especial,CASE WHEN o.evaluacion_aula=1 OR o.evaluacion_parametros_historica=1 THEN 0 ELSE s.solo_visor_comportamiento END solo_visor_comportamiento,(o.evaluacion_aula=1 OR o.evaluacion_parametros_historica=1) evaluacion_cualitativa_parametros,CASE WHEN o.evaluacion_aula=1 THEN \'Ejes y ámbitos\' ELSE ar.nombre END area FROM ofertas_academicas o JOIN asignaturas s ON s.id=o.asignatura_id JOIN areas ar ON ar.id=s.area_id WHERE o.aula_periodo_id=? AND o.activo=1 ORDER BY ar.orden,s.nombre');
  $stmt->bind_param('i',$apid);$stmt->execute();$ofertas=$stmt->get_result()->fetch_all(MYSQLI_ASSOC);$stmt->close();
  $stmt=$conexion->prepare("SELECT m.id matricula_id,m.numero_lista,u.cedula,u.apellidos,u.nombres FROM matriculas m JOIN usuarios u ON u.id=m.estudiante_id WHERE m.aula_periodo_id=? AND m.estado='activo' ORDER BY COALESCE(m.numero_lista,9999),u.apellidos,u.nombres");
  $stmt->bind_param('i',$apid);$stmt->execute();$estudiantes=$stmt->get_result()->fetch_all(MYSQLI_ASSOC);$stmt->close();
  // Una sola consulta devuelve todas las materias/estudiantes del aula.
  $notas=sgaFinalesPorAula($apid,$pid);
  // La materia marcada como Comportamiento tiene una letra por trimestre;
  // su Final es el promedio cualitativo de las tres letras, nunca una nota /10.
  $hayComportamiento=(bool)array_filter($ofertas,static fn($of)=>!empty($of['solo_visor_comportamiento']));
  if($hayComportamiento){
    $st=$conexion->prepare('SELECT c.matricula_id,c.oferta_id,c.trimestre,c.literal FROM calificaciones_comportamiento_trimestre c JOIN matriculas m ON m.id=c.matricula_id JOIN ofertas_academicas o ON o.id=c.oferta_id WHERE m.aula_periodo_id=? AND o.aula_periodo_id=? AND o.activo=1 AND c.trimestre BETWEEN 1 AND 3');
    $st->bind_param('ii',$apid,$apid);$st->execute();
    $letras=[];
    foreach($st->get_result()->fetch_all(MYSQLI_ASSOC) as $registro){
      $letras[(int)$registro['matricula_id']][(int)$registro['oferta_id']][(int)$registro['trimestre']]=$registro['literal'];
    }
    $st->close();
    foreach($letras as $mid=>$porOferta)foreach($porOferta as $oid=>$tri){
      $notasComportamiento[$mid][$oid]=sgaComportamientoFinal($tri[1]??null,$tri[2]??null,$tri[3]??null);
    }
  }
}
$aulaResultadosCualitativos=!empty($aulaActual['resultados_cualitativos']);
$tituloPagina='Reportes institucionales';$subtituloPagina='Consolidado de calificaciones y emisión de reportes PDF institucionales.';require __DIR__.'/../../partials/header.php';
?>
<section class="card"><form method="get"><div class="form-grid cols-2"><label>Periodo<select name="periodo_id" onchange="this.form.submit()"><?php foreach($periodos as $x):?><option value="<?=$x['id']?>" <?=$x['id']==$pid?'selected':''?>><?=e($x['nombre'])?></option><?php endforeach;?></select></label><label>Paralelo<select name="aula_periodo_id" onchange="this.form.submit()"><?php foreach($aulas as $a):?><option value="<?=$a['id']?>" <?=$a['id']==$apid?'selected':''?>><?=e($a['nivel'].' · '.$a['nombre'].' '.$a['paralelo'])?></option><?php endforeach;?></select></label></div></form></section>
<section class="card" style="border-left:4px solid #1d547c;margin-bottom:14px">
  <div class="toolbar" style="align-items:center;margin:0;gap:12px">
    <div>
      <strong>Reportes PDF con identidad institucional</strong>
      <p class="muted" style="margin:6px 0 0">Certificados de cada trimestre y calificaciones finales del aula seleccionada.</p>
    </div>
    <?php if($pid>0 && $apid>0 && $estudiantes):?>
      <button class="btn btn-primary" type="button" id="sga-abrir-certificados-zip">Descargar certificados</button>
    <?php endif;?>
  </div>
</section>
<?php if($pid>0 && $apid>0 && $estudiantes):?>
<style>
#sga-dialogo-certificados-zip{width:min(480px,calc(100vw - 24px));max-width:100%;max-height:90dvh;overflow:auto;margin:auto;padding:0;border:1px solid #d5e1ee;border-radius:14px;background:#fff;color:#143456;box-shadow:0 20px 65px rgba(0,24,53,.3)}
#sga-dialogo-certificados-zip::backdrop{background:rgba(6,21,43,.64)}
#sga-dialogo-certificados-zip .sga-zip-contenido{padding:24px}
#sga-dialogo-certificados-zip h2{margin:0 0 10px;font-size:21px;color:#143456}
#sga-dialogo-certificados-zip p{margin:0 0 14px;line-height:1.5}
#sga-dialogo-certificados-zip label{display:block;margin-bottom:8px;font-weight:650}
#sga-dialogo-certificados-zip select{width:100%;margin-bottom:18px}
#sga-dialogo-certificados-zip .sga-zip-acciones{display:flex;gap:9px;justify-content:flex-end;flex-wrap:wrap}
#sga-dialogo-certificados-zip .sga-zip-estado{margin:12px 0 0;font-size:13px;color:#345678}
#sga-dialogo-certificados-zip .sga-zip-estado:empty{display:none}
#sga-dialogo-certificados-zip .sga-zip-estado.sga-zip-error{color:#a02121;font-weight:600}
@media(max-width:480px){#sga-dialogo-certificados-zip .sga-zip-acciones>*{flex:1}}
</style>
<dialog id="sga-dialogo-certificados-zip" aria-labelledby="sga-zip-titulo">
  <form method="post" action="<?=e(url('modulos/reportes/certificados_zip.php'))?>" class="sga-zip-contenido" id="sga-form-certificados-zip">
    <h2 id="sga-zip-titulo">Descargar certificados</h2>
    <p class="muted">Se generará un ZIP con <strong><?=count($estudiantes)?> certificados PDF</strong> del aula <strong><?=e($aulaActual['nivel'].' '.$aulaActual['nombre'].' '.$aulaActual['paralelo'])?></strong> en el período seleccionado.</p>
    <input type="hidden" name="csrf_certificados_zip" value="<?=e($csrfCertificadosZip)?>">
    <input type="hidden" name="periodo_id" value="<?=(int)$pid?>">
    <input type="hidden" name="aula_periodo_id" value="<?=(int)$apid?>">
    <label for="sga-tipo-certificado">Certificados a descargar</label>
    <select id="sga-tipo-certificado" name="tipo_certificado" required>
      <option value="t1">Trimestre 1</option>
      <option value="t2">Trimestre 2</option>
      <option value="t3">Trimestre 3</option>
      <option value="anual">Anual</option>
    </select>
    <div class="sga-zip-acciones">
      <button type="button" class="btn btn-secondary" id="sga-cerrar-certificados-zip">Cancelar</button>
      <button type="button" class="btn btn-success" id="sga-generar-certificados-zip">Generar ZIP</button>
    </div>
    <p id="sga-zip-estado" class="sga-zip-estado" role="status" aria-live="polite"></p>
  </form>
</dialog>
<script>
(function(){
  'use strict';
  const d=document.getElementById('sga-dialogo-certificados-zip');
  const abrir=document.getElementById('sga-abrir-certificados-zip');
  const cerrar=document.getElementById('sga-cerrar-certificados-zip');
  const formulario=document.getElementById('sga-form-certificados-zip');
  const generar=document.getElementById('sga-generar-certificados-zip');
  const estado=document.getElementById('sga-zip-estado');
  if(!d || !abrir || !cerrar || !formulario || !generar || !estado)return;
  let generando=false;
  let controlador=null;

  function cerrarDialogo(){
    if(typeof d.close==='function')d.close();else d.removeAttribute('open');
  }
  function ponerCarga(activo){
    generar.disabled=activo;
    generar.classList.toggle('is-submitting',activo);
    if(activo)generar.setAttribute('aria-busy','true');
    else generar.removeAttribute('aria-busy');
  }
  function cancelar(){
    if(controlador)controlador.abort();
    cerrarDialogo();
  }
  function nombreDesdeRespuesta(cabecera){
    const encontrado=(cabecera||'').match(/filename\s*=\s*(?:"([^"]+)"|([^;]+))/i);
    let nombre=encontrado?(encontrado[1]||encontrado[2]).trim():'';
    if(!nombre){
      const tipo=formulario.querySelector('[name="tipo_certificado"]');
      nombre='certificados_'+(tipo?tipo.value.toUpperCase():'ANUAL')+'.zip';
    }
    nombre=nombre.replace(/[\\\/:*?"<>|]/g,'_');
    return nombre.toLowerCase().endsWith('.zip')?nombre:nombre+'.zip';
  }
  async function descargar(){
    if(generando)return;
    if(!formulario.reportValidity())return;
    generando=true;
    controlador=new AbortController();
    estado.className='sga-zip-estado';
    estado.textContent='Preparando los certificados PDF y el archivo ZIP...';
    ponerCarga(true);
    try{
      const respuesta=await fetch(formulario.action,{
        method:'POST',
        credentials:'same-origin',
        body:new FormData(formulario),
        signal:controlador.signal
      });
      if(!respuesta.ok){
        const detalle=(await respuesta.text()).replace(/<[^>]*>/g,' ').replace(/\s+/g,' ').trim();
        throw new Error(detalle.slice(0,200)||'El servidor no pudo generar el ZIP.');
      }
      const archivo=await respuesta.blob();
      if(!archivo.size)throw new Error('El servidor devolvió un archivo vacío.');
      // Comprueba que la respuesta es realmente un ZIP y no una página de error.
      const firma=new Uint8Array(await archivo.slice(0,4).arrayBuffer());
      if(firma[0]!==80 || firma[1]!==75 || (firma[2]!==3 && firma[2]!==5 && firma[2]!==7)){
        throw new Error('La respuesta del servidor no contiene un archivo ZIP válido.');
      }
      const nombre=nombreDesdeRespuesta(respuesta.headers.get('Content-Disposition'));
      const enlace=document.createElement('a');
      const urlTemporal=URL.createObjectURL(archivo);
      enlace.href=urlTemporal;
      enlace.download=nombre;
      enlace.style.display='none';
      document.body.appendChild(enlace);
      try{enlace.click();}finally{
        enlace.remove();
        setTimeout(()=>URL.revokeObjectURL(urlTemporal),60000);
      }
      cerrarDialogo();
      estado.textContent='';
    }catch(error){
      if(error.name!=='AbortError'){
        estado.className='sga-zip-estado sga-zip-error';
        estado.textContent=error.message||'No se pudo descargar el ZIP. Inténtalo nuevamente.';
      }
    }finally{
      generando=false;
      controlador=null;
      ponerCarga(false);
    }
  }

  abrir.addEventListener('click',()=>{
    estado.className='sga-zip-estado';estado.textContent='';
    if(typeof d.showModal==='function')d.showModal();else d.setAttribute('open','');
  });
  cerrar.addEventListener('click',cancelar);
  d.addEventListener('cancel',()=>{if(controlador)controlador.abort();});
  d.addEventListener('click',e=>{if(e.target===d)cancelar();});
  // type=button impide el indicador global de formularios POST sin recarga.
  generar.addEventListener('click',descargar);
  formulario.addEventListener('submit',e=>{e.preventDefault();descargar();});
})();
</script>
<?php endif;?>
<section class="card" style="margin-bottom:14px;border-left:4px solid #147a4d">
  <div class="toolbar" style="align-items:center;margin:0">
    <div style="max-width:700px">
      <strong>Cuadros de calificaciones por período · Excel</strong>

      <?php if(esSubadmin()):?><p class="mini-note" style="margin:5px 0 0">El reporte incluye únicamente tus jornadas autorizadas para este período.</p><?php endif;?>
    </div>
    <?php if($pid>0):?>
      <div class="actions" style="align-items:center;gap:8px">
        <a class="btn btn-success" id="sga-descargar-cuadro-anual" href="<?=e(url('modulos/reportes/periodo_excel.php?periodo_id='.$pid.'&incluir_supletorios=1'))?>">Descargar cuadro anual Excel</a>
        <?php for($trimestreExcel=1;$trimestreExcel<=3;$trimestreExcel++):?>
          <a class="btn btn-secondary" href="<?=e(url('modulos/reportes/periodo_excel.php?periodo_id='.$pid.'&trimestre='.$trimestreExcel))?>" aria-label="Descargar cuadro de calificaciones del trimestre <?=$trimestreExcel?> en Excel">Trimestre <?=$trimestreExcel?> · Excel</a>
        <?php endfor;?>
        <a class="btn btn-secondary" href="<?=e(url('modulos/reportes/periodo_excel.php?periodo_id='.$pid.'&supletorio=1'))?>" aria-label="Descargar cuadro de supletorios en Excel">Supletorio · Excel</a>
      </div>
    <?php endif;?>
  </div>
</section>
<?php if($pid>0): ?>
<style>
#sga-dialogo-cuadro-anual { width:min(480px,calc(100vw - 28px)); max-width:100%; max-height:90dvh; overflow:auto; padding:0; margin:auto; border:1px solid #d9e2ed; border-radius:14px; background:#fff; color:#163252; box-shadow:0 20px 60px rgba(8,28,53,.25); }
#sga-dialogo-cuadro-anual::backdrop { background:rgba(6,21,43,.65); }
#sga-dialogo-cuadro-anual .sga-dialogo-contenido { padding:24px; }
#sga-dialogo-cuadro-anual h2 { margin:0 0 10px; font-size:21px; color:#15375d; }
#sga-dialogo-cuadro-anual p { margin:0 0 20px; line-height:1.5; color:#52667d; }
#sga-dialogo-cuadro-anual .sga-opciones { display:flex; flex-wrap:wrap; gap:9px; }
#sga-dialogo-cuadro-anual .sga-opciones .btn { min-height:40px; text-decoration:none; }
@media (max-width:480px) { #sga-dialogo-cuadro-anual .sga-opciones { flex-direction:column; } #sga-dialogo-cuadro-anual .sga-opciones .btn { width:100%; text-align:center; } }
</style>
<dialog id="sga-dialogo-cuadro-anual" aria-labelledby="sga-pregunta-supletorios" aria-describedby="sga-explicacion-supletorios">
  <div class="sga-dialogo-contenido">
    <h2 id="sga-pregunta-supletorios">¿Incluir supletorios?</h2>
    <p id="sga-explicacion-supletorios">Elige cómo descargar el cuadro anual de calificaciones. Si seleccionas <strong>Sí</strong>, se incluirán los exámenes supletorios registrados. Si seleccionas <strong>No</strong>, aparecerán las notas anuales originales, sin la columna de supletorios.</p>
    <div class="sga-opciones">
      <a class="btn btn-success" data-sga-descarga-anual href="<?=e(url('modulos/reportes/periodo_excel.php?periodo_id='.$pid.'&incluir_supletorios=1'))?>">Sí, incluir</a>
      <a class="btn btn-secondary" data-sga-descarga-anual href="<?=e(url('modulos/reportes/periodo_excel.php?periodo_id='.$pid.'&incluir_supletorios=0'))?>">No, sin supletorios</a>
      <button type="button" class="btn" id="sga-cancelar-cuadro-anual">Cancelar</button>
    </div>
  </div>
</dialog>
<script>
(function(){
  'use strict';
  var enlace=document.getElementById('sga-descargar-cuadro-anual');
  var dialogo=document.getElementById('sga-dialogo-cuadro-anual');
  if(!enlace || !dialogo) return;
  enlace.addEventListener('click', function(event){
    event.preventDefault();
    if(typeof dialogo.showModal==='function') dialogo.showModal();
    else {
      var conSupletorios=window.confirm('¿Incluir supletorios?');
      window.location.href=conSupletorios ? enlace.href : dialogo.querySelector('[href*="incluir_supletorios=0"]').href;
    }
  });
  document.getElementById('sga-cancelar-cuadro-anual').addEventListener('click',function(){dialogo.close();});
  dialogo.querySelectorAll('[data-sga-descarga-anual]').forEach(function(opcion){
    opcion.addEventListener('click',function(){ dialogo.close(); });
  });
  dialogo.addEventListener('click',function(event){if(event.target===dialogo)dialogo.close();});
})();
</script>
<?php endif; ?>
<section class="card" style="margin-bottom:14px;border-left:4px solid #1d6792">
  <div class="toolbar" style="align-items:center;margin:0">
    <div><strong>Consolidado de asistencia por paralelo</strong>
      <p class="muted" style="margin:6px 0 0">Consulta presentes, ausentes, atrasos, justificados y porcentajes por asignatura. Descarga PDF o Excel por paralelo, o un Excel del período con una hoja por aula.</p>
    </div>
    <?php if($pid>0):?>
      <a class="btn btn-primary" href="<?=e(url('modulos/reportes/asistencia.php?periodo_id='.$pid.'&aula_periodo_id='.$apid))?>">Ver reporte de asistencia</a>
    <?php endif;?>
  </div>
</section>
<!-- Consolidado con columnas compactas: evita nombres cortados palabra por palabra. -->
<style>
.consolidado-scroll{overflow-x:auto;max-width:100%;-webkit-overflow-scrolling:touch}
.consolidado-tabla{table-layout:fixed;width:100%;min-width:var(--consolidado-min-width)}
.consolidado-tabla thead th{
    padding:9px 7px;
    white-space:normal;
    overflow-wrap:break-word;
    word-break:normal;
    hyphens:auto;
    text-align:center;
    vertical-align:middle;
    font-size:10.5px;
    line-height:1.28;
}
.consolidado-tabla thead th.consolidado-alumno{text-align:left}
.consolidado-tabla thead th.consolidado-asignatura .consolidado-area{
    display:block;
    font-size:9px;
    font-weight:700;
    letter-spacing:.025em;
    color:#426282;
    line-height:1.25;
    margin-bottom:3px;
}
.consolidado-tabla thead th.consolidado-asignatura .consolidado-materia{
    display:block;
    white-space:normal;
    overflow-wrap:break-word;
    word-break:normal;
    font-size:10.5px;
    line-height:1.3;
}
.consolidado-tabla tbody td{padding:8px 7px;vertical-align:middle;font-size:12px}
.consolidado-tabla tbody td.consolidado-alumno{
    text-align:left;
    white-space:normal;
    overflow-wrap:normal;
    word-break:normal;
    line-height:1.35;
}
.consolidado-tabla tbody td.consolidado-alumno strong{
    display:block;
    white-space:normal;
    overflow-wrap:normal;
    word-break:normal;
    font-size:11.5px;
    line-height:1.35;
}
.consolidado-tabla tbody td.consolidado-alumno .muted{
    display:block;
    font-size:11px;
    margin-top:3px;
}
.consolidado-tabla tbody td.consolidado-nota{text-align:center;line-height:1.45}
.consolidado-tabla .actions{gap:4px;justify-content:center}
.consolidado-tabla .actions .btn{padding:6px 8px;font-size:11px}
.consolidado-tabla tbody td.consolidado-certificaciones{text-align:center}
.consolidado-tabla tbody td.consolidado-certificaciones details{text-align:left}
@media(max-width:650px){
    .consolidado-tabla thead th{font-size:10px;padding:8px 5px}
    .consolidado-tabla tbody td{padding:7px 5px}
}
</style>
<h2 class="section-title">Consolidado del paralelo</h2>
<?php if(!$apid||!$estudiantes):?><div class="card empty">No existen estudiantes para el paralelo seleccionado.</div><?php else:?>
<div class="table-wrap consolidado-scroll">
<table class="table consolidado-tabla" style="--consolidado-min-width:<?=46+206+(int)count($ofertas)*182+118+248?>px">
<colgroup>
  <col style="width:46px">
  <col style="width:206px">
  <?php foreach($ofertas as $o):?><col style="width:182px"><?php endforeach;?>
  <col style="width:118px">
  <col style="width:248px">
</colgroup>
<thead><tr><th>No.</th><th class="consolidado-alumno">Estudiante</th>
<?php foreach($ofertas as $o):?>
  <th class="consolidado-asignatura"><span class="consolidado-area"><?=e($o['area'])?></span><span class="consolidado-materia"><?=e($o['asignatura'])?></span></th>
<?php endforeach;?><th>Promedio general</th><th>Certificaciones</th></tr></thead><tbody>
<?php foreach($estudiantes as $e):$vals=[];?><tr><td style="text-align:center"><?=$e['numero_lista']?></td><td class="consolidado-alumno"><strong><?=e($e['apellidos'].' '.$e['nombres'])?></strong><span class="muted"><?=e($e['cedula'])?></span></td>
<?php foreach($ofertas as $o):
    if(!empty($o['evaluacion_cualitativa_parametros'])){
      ?><td class="consolidado-nota"><strong>Por parámetros</strong><br>
      <a class="btn btn-sm btn-secondary" target="_blank" rel="noopener" href="<?=e(url('modulos/calificaciones/informe_aprendizaje.php?oferta_id='.(int)$o['id'].'&matricula_id='.(int)$e['matricula_id']))?>">Ver informe de aprendizaje</a></td><?php
      continue;
    }
    if(!empty($o['solo_visor_comportamiento'])){
      $letra=$notasComportamiento[(int)$e['matricula_id']][(int)$o['id']]??null;
      ?><td class="consolidado-nota" style="font-weight:800"><?=e($letra??'—')?></td><?php
      continue;
    }
    $f=$notas[(int)$e['matricula_id']][(int)$o['id']]??['promedio_final'=>null,'promedio_tres'=>null,'observacion'=>'EN CURSO','trimestres_completos'=>false,'examen_supletorio'=>null];
    $completo=!empty($f['trimestres_completos']);
    $base=(float)$f['promedio_tres'];
    $minSup=(float)($configConsolidado['nota_min_supletorio']??4.0);
    $aprobacion=(float)($configConsolidado['nota_aprobacion']??7.0);
    $requiereSup=$completo && $base >= $minSup && $base < $aprobacion;
    $supRegistrado=$f['examen_supletorio']??null;
    // El estado del supletorio es informativo y se muestra SOLO en el HTML.
    // La nota previa siempre permanece visible incluso si el examen falta.
    $notaPantalla=$aulaResultadosCualitativos?(float)$f['promedio_final']:($requiereSup?$base:(float)$f['promedio_final']);
    // Si aun no rinde, el promedio general utiliza su nota real, nunca un cero ficticio.
    if($completo)$vals[]=$f['observacion']==='SUPLETORIO'?$base:(float)$f['promedio_final'];
?><td class="consolidado-nota <?=$completo?($notaPantalla >= $aprobacion?'grade-good':'grade-low'):''?>">
<?php if($completo):?>
    <?php if($aulaResultadosCualitativos):?>
      <?=e(sgaLetraResultadoCualitativo($notaPantalla))?>
    <?php else:?>
      <?=fmt($notaPantalla)?><?php if(!empty($o['usa_literal_especial'])):?> <span style="white-space:nowrap">(<?=e(literalEspecial($notaPantalla))?>)</span><?php endif;?>
    <?php endif;?>
    <?php if($requiereSup):?>
      <span style="display:inline-block;white-space:nowrap;font-size:11px;font-weight:700;color:#795d12">
        <?php if($aulaResultadosCualitativos):?>
          <?=e($supRegistrado===null?'Supletorio pendiente':'Supletorio: '.sgaLetraResultadoCualitativo((float)$supRegistrado))?>
        <?php else:?>
          (SUP: <?=e($supRegistrado===null?'Falta':fmt($supRegistrado))?>)
        <?php endif;?>
      </span>
    <?php endif;?>
<?php else:?><span class="muted">—</span><?php endif;?>
</td><?php endforeach;?>
<td><strong><?=($vals && count($vals)===count(array_filter($ofertas,static fn($of)=>empty($of['solo_visor_comportamiento']) && empty($of['evaluacion_cualitativa_parametros']))))?($aulaResultadosCualitativos?e(sgaLetraResultadoCualitativo(truncar2(array_sum($vals)/count($vals)))):fmt(array_sum($vals)/count($vals))):'En curso'?></strong></td>
<td class="consolidado-certificaciones"><div class="actions">
<a class="btn btn-sm btn-secondary" href="<?=e(url('modulos/reportes/certificacion.php?matricula_id='.$e['matricula_id'].'&trimestre=1'))?>">T1</a>
<a class="btn btn-sm btn-secondary" href="<?=e(url('modulos/reportes/certificacion.php?matricula_id='.$e['matricula_id'].'&trimestre=2'))?>">T2</a>
<a class="btn btn-sm btn-secondary" href="<?=e(url('modulos/reportes/certificacion.php?matricula_id='.$e['matricula_id'].'&trimestre=3'))?>">T3</a>
<a class="btn btn-sm btn-primary" href="<?=e(url('modulos/reportes/certificacion.php?matricula_id='.$e['matricula_id']))?>">Anual</a>
</div>
<details style="margin-top:7px"><summary style="cursor:pointer;font-size:12px;color:#235a83">Ver PDF antes de descargar</summary><div class="actions" style="margin-top:7px">
<?php for($t=1;$t<=3;$t++):?><a class="btn btn-sm btn-secondary" target="_blank" rel="noopener noreferrer" href="<?=e(url('modulos/reportes/certificacion.php?matricula_id='.$e['matricula_id'].'&trimestre='.$t.'&vista=1'))?>">T<?=$t?></a><?php endfor;?>
<a class="btn btn-sm btn-primary" target="_blank" rel="noopener noreferrer" href="<?=e(url('modulos/reportes/certificacion.php?matricula_id='.$e['matricula_id'].'&vista=1'))?>">Anual</a></div></details></td></tr><?php endforeach;?>
</tbody></table></div><?php endif;?>
<?php require __DIR__.'/../../partials/footer.php';?>
