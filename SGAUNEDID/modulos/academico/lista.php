<?php
require_once __DIR__.'/../../lib/lista_estudiantes.php';
$oid=(int)($_GET['oferta_id']??0);
$datos=listaEstudiantesCargar($oid);
$o=$datos['oferta'];
$rows=$datos['estudiantes'];
$tituloPagina='Lista · '.$o['asignatura'];
$subtituloPagina=$o['nivel'].' · '.$o['aula'].' '.$o['paralelo'].' · '.$o['periodo'];
require __DIR__.'/../../partials/header.php';
?>
<div class="toolbar" style="margin-bottom:14px">
  <div class="actions">
    <a class="btn btn-success" href="<?=e(url('modulos/academico/lista_excel.php?oferta_id='.$oid))?>">Descargar Excel</a>
    <a class="btn btn-primary" href="<?=e(url('modulos/academico/lista_pdf.php?oferta_id='.$oid))?>">Descargar PDF</a>
  </div>
  <span class="badge"><?=count($rows)?> estudiantes matriculados</span>
</div>
<div class="actions" style="margin-bottom:14px">
  <a class="btn btn-secondary" href="<?=e(url('modulos/calificaciones/index.php?oferta_id='.$oid))?>">Abrir calificaciones</a>
  <a class="btn btn-secondary" href="<?=e(url('modulos/calificaciones/finales.php?oferta_id='.$oid))?>">Ver finales</a>
  <a class="btn btn-secondary" href="<?=e(url('modulos/asistencia/registro.php?oferta_id='.$oid))?>">Registrar asistencia</a>
</div>
<div class="table-wrap">
<table class="table table-responsive-cards"><thead><tr><th>No.</th><th>Cédula</th><th>Estudiante</th><th>Correo</th></tr></thead><tbody>
<?php if(!$rows):?><tr><td colspan="4" class="empty">No hay estudiantes matriculados.</td></tr><?php endif;?>
<?php foreach($rows as $r):?>
<tr><td><?=($r['numero_lista']===null?'—':(int)$r['numero_lista'])?></td><td><?=e($r['cedula'])?></td><td><strong><?=e($r['apellidos'].' '.$r['nombres'])?></strong></td><td><?=e($r['correo']??'')?></td></tr>
<?php endforeach;?>
</tbody></table>
</div>
<?php require __DIR__.'/../../partials/footer.php';?>
