<?php
require_once __DIR__.'/../../lib/funciones.php';
require_once __DIR__.'/../../lib/reporte_asistencia_consolidado.php';
exigirLogin();

$activo=periodoActivo();
$pid=(int)($_GET['periodo_id']??($activo['id']??0));
$pid=periodoInicialSubadmin($pid,isset($_GET['periodo_id'])?1:0);
if($pid>0) raExigirPeriodo($conexion,$pid);
else {http_response_code(403);die('No tienes períodos con registros de asistencia autorizados.');}
$periodos=raListaPeriodos($conexion);
$periodo=$pid?raPeriodo($conexion,$pid):null;
if($pid && !$periodo){http_response_code(404);die('Período inexistente.');}
$aulas=$pid?raListaAulas($conexion,$pid):[];
$apid=(int)($_GET['aula_periodo_id']??0);
if(!$apid && $aulas)$apid=(int)$aulas[0]['aula_periodo_id'];
if($apid && !in_array($apid,array_map('intval',array_column($aulas,'aula_periodo_id')),true)){
    http_response_code(403);die('El aula no pertenece al período consultado o no se encuentra en el filtro de jornada.');
}
[$desde,$hasta]=$periodo?raRangoPeriodo($periodo,$_GET):['',''];
$datos=null;
if($apid){
    foreach($aulas as $a){
        if((int)$a['aula_periodo_id']===$apid){$datos=raCargarAula($conexion,$a,$desde,$hasta);break;}
    }
}
$params=['periodo_id'=>$pid,'aula_periodo_id'=>$apid,'desde'=>$desde,'hasta'=>$hasta];
$extra=http_build_query($params);
$tituloPagina='Reporte de asistencia';
$subtituloPagina=esAdminAcademico()
    ? 'Consolidado por paralelo y período · registros guardados por asignatura.'
    : 'Consolidado de tus asignaturas y paralelos asignados · solo registros guardados.';
require __DIR__.'/../../partials/header.php';
?>
<style>
.ra-actions{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.ra-table-wrap{overflow-x:auto;max-width:100%;-webkit-overflow-scrolling:touch}
.ra-table{table-layout:fixed;min-width:var(--ra-min-width);width:100%}
.ra-table thead th{padding:9px 6px;white-space:normal;overflow-wrap:break-word;word-break:normal;hyphens:auto;text-align:center;vertical-align:middle;font-size:10.5px;line-height:1.25}
.ra-table thead th.ra-student{text-align:left}
.ra-table .ra-area{display:block;font-size:9px;line-height:1.2;color:#426282;margin-bottom:3px}
.ra-table .ra-matter{display:block;overflow-wrap:break-word;line-height:1.3}
.ra-table tbody td{font-size:12px;padding:8px 6px;text-align:center;vertical-align:middle}
.ra-table tbody td.ra-student{text-align:left;white-space:normal;overflow-wrap:normal;word-break:normal;line-height:1.3}
.ra-table tbody td.ra-student strong{font-size:11.5px;display:block;line-height:1.35}
.ra-table .ra-breakdown{font-size:10px;color:#5b6e83;white-space:nowrap;display:block;margin-top:4px}
.ra-table .ra-missing{font-size:10px;color:#8d6b3b;display:block;margin-top:2px}
.ra-table td.ra-bad{color:#ac2c36;font-weight:700}
.ra-table td.ra-good{color:#147a4d;font-weight:700}
.ra-table .ra-detail{display:block;font-size:9.5px;color:#607187;font-weight:400;margin-top:4px}
@media(max-width:760px){.ra-table thead th{font-size:10px}.ra-table tbody td{padding:7px 5px}}
</style>
<section class="card" style="margin-bottom:16px">
  <form method="get" id="ra-filter">
    <div class="form-grid">
      <label>Período académico
        <select name="periodo_id" onchange="this.form.aula_periodo_id.value='0';this.form.desde.value='';this.form.hasta.value='';this.form.submit()">
          <?php foreach($periodos as $p):?><option value="<?=(int)$p['id']?>" <?=(int)$p['id']===$pid?'selected':''?>><?=e($p['nombre'])?></option><?php endforeach;?>
        </select>
      </label>
      <label>Paralelo
        <select name="aula_periodo_id">
          <?php foreach($aulas as $a):?><option value="<?=(int)$a['aula_periodo_id']?>" <?=(int)$a['aula_periodo_id']===$apid?'selected':''?>><?=e($a['nivel'].' · '.$a['nombre'].' '.$a['paralelo'])?></option><?php endforeach;?>
        </select>
      </label>
      <label>Desde<input type="date" name="desde" value="<?=e($desde)?>"></label>
      <label>Hasta<input type="date" name="hasta" value="<?=e($hasta)?>"></label>
    </div>
    <div class="ra-actions" style="margin-top:14px">
      <button class="btn btn-primary" type="submit">Consultar asistencia</button>
      <a class="btn btn-secondary" href="<?=e(url(esAdminAcademico()?'modulos/asistencia/index.php':'modulos/docente/seleccionar.php?modulo=asistencia'))?>">Volver a asistencia</a>
    </div>
  </form>
</section>
<?php if($datos):?>
<div class="toolbar" style="gap:9px;align-items:center;flex-wrap:wrap">
  <div><strong><?=e($datos['aula']['nivel'].' · '.$datos['aula']['nombre'].' '.$datos['aula']['paralelo'])?></strong>
    <span class="mini-note"> · <?=count($datos['estudiantes'])?> estudiantes · <?=e($desde)?> a <?=e($hasta)?></span></div>
  <div class="ra-actions">
    <a class="btn btn-primary" href="<?=e(url('modulos/reportes/asistencia_pdf.php?'.$extra))?>">Descargar PDF del paralelo</a>
    <a class="btn btn-success" href="<?=e(url('modulos/reportes/asistencia_excel.php?'.$extra))?>">Excel del paralelo</a>
    <a class="btn btn-secondary" href="<?=e(url('modulos/reportes/asistencia_excel.php?'.http_build_query(['periodo_id'=>$pid,'todos'=>1,'desde'=>$desde,'hasta'=>$hasta])))?>">Excel del período · <?=esAdminAcademico()?'aulas autorizadas':'mis cursos'?></a>
  </div>
</div>
<?php endif;?>
<h2 class="section-title">Consolidado de asistencia del paralelo</h2>
<?php if(!$datos || !$datos['estudiantes']):?>
  <div class="card empty">No existen estudiantes matriculados para el paralelo seleccionado.</div>
<?php else:?>
  <div class="table-wrap ra-table-wrap">
    <table class="table ra-table" style="--ra-min-width:<?=44+206+count($datos['ofertas'])*180+164+146?>px">
      <colgroup><col style="width:44px"><col style="width:206px">
        <?php foreach($datos['ofertas'] as $o):?><col style="width:180px"><?php endforeach;?>
        <col style="width:164px"><col style="width:146px">
      </colgroup>
      <thead><tr><th>No.</th><th class="ra-student">Estudiante</th>
      <?php foreach($datos['ofertas'] as $o):?>
        <th><span class="ra-area"><?=e($o['area'])?></span><span class="ra-matter"><?=e($o['asignatura'])?></span>
          <span class="ra-detail"><?=($datos['sesiones'][(int)$o['id']]??0)?> sesiones guardadas</span></th>
      <?php endforeach;?>
      <th>Asistencia total</th><th>Reporte</th></tr></thead>
      <tbody>
      <?php foreach($datos['estudiantes'] as $idx=>$est):?>
      <tr>
        <td><?=e($est['numero_lista']?:($idx+1))?></td>
        <td class="ra-student"><strong><?=e($est['apellidos'].' '.$est['nombres'])?></strong><span class="muted"><?=e($est['cedula'])?></span></td>
        <?php foreach($datos['ofertas'] as $o):$r=$est['por_oferta'][(int)$o['id']];?>
          <td >
            <?php if($r['porcentaje']===null):?><span class="muted">—</span><span class="ra-missing">Sin registro</span>
            <?php else:?><?=number_format($r['porcentaje'],2,'.','')?>%
              <span class="ra-breakdown">P:<?=$r['presente']?> · A:<?=$r['ausente']?> · T:<?=$r['atraso']?> · J:<?=$r['justificado']?></span>
              <?php if($r['sesiones']>$r['registros']):?><span class="ra-missing"><?=($r['sesiones']-$r['registros'])?> sin dato</span><?php endif;?>
            <?php endif;?>
          </td>
        <?php endforeach;?>
        <?php $rt=$est['total'];?><td>
          <?php if($rt['porcentaje']===null):?><span class="muted">—</span>
          <?php else:?><strong><?=number_format($rt['porcentaje'],2,'.','')?>%</strong>
            <span class="ra-breakdown">P:<?=$rt['presente']?> · A:<?=$rt['ausente']?> · T:<?=$rt['atraso']?> · J:<?=$rt['justificado']?></span><?php endif;?>
        </td>
        <td><div class="actions" style="justify-content:center;gap:4px;flex-wrap:nowrap">
          <a class="btn btn-sm btn-primary" href="<?=e(url('modulos/reportes/asistencia_pdf.php?'.$extra.'&matricula_id='.(int)$est['matricula_id']))?>">PDF</a>
          <a class="btn btn-sm btn-secondary" target="_blank" rel="noopener noreferrer"
            href="<?=e(url('modulos/reportes/asistencia_pdf.php?'.$extra.'&matricula_id='.(int)$est['matricula_id'].'&vista=1'))?>">Ver</a>
        </div></td>
      </tr>
      <?php endforeach;?>
      </tbody>
    </table>
  </div>
<?php endif;?>
<p class="mini-note" style="margin-top:12px">P = Presente · A = Ausente · T = Atraso · J = Justificado. Porcentaje = (Presentes + Atrasos) / registros de asistencia guardados × 100. Los estados justificados se informan por separado; los registros faltantes no se cuentan como ausencias.</p>
<?php require __DIR__.'/../../partials/footer.php';?>
