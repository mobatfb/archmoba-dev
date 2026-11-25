<?php
require_once __DIR__.'/../../lib/funciones.php';
exigirLogin();
$p=periodoActivo();
$pid=(int)($p['id']??0);
if(!$pid || (!esAdminAcademico() && !esDocenteOperativo($pid))){
    http_response_code(403); die('No tienes acceso al módulo de asistencia en el periodo activo.');
}
if(!esAdminAcademico()) {
    redir('modulos/docente/seleccionar.php?modulo=asistencia');
}
$uid=(int)$_SESSION['usuario_id'];
$hoy=date('Y-m-d');
$sql="SELECT o.id,a.nivel,a.nombre aula,a.paralelo,s.nombre asignatura,j.nombre jornada,
             CONCAT(u.apellidos,' ',u.nombres) docente,
             (SELECT COUNT(*) FROM matriculas m WHERE m.aula_periodo_id=ap.id AND m.estado='activo') estudiantes,
             COUNT(asi.id) sesiones, MAX(asi.fecha) ultima_fecha,
             MAX(CASE WHEN asi.fecha=? THEN 1 ELSE 0 END) hoy_registrada
      FROM ofertas_academicas o
      JOIN aulas_periodo ap ON ap.id=o.aula_periodo_id
      JOIN aulas a ON a.id=ap.aula_id
      LEFT JOIN jornadas j ON j.id=a.jornada_id
      JOIN asignaturas s ON s.id=o.asignatura_id
      JOIN areas ar ON ar.id=s.area_id
      JOIN usuarios u ON u.id=o.docente_id
      LEFT JOIN asistencia_sesiones asi ON asi.oferta_id=o.id
      WHERE ap.periodo_id=? AND o.activo=1 AND s.archivado_en IS NULL AND ar.archivado_en IS NULL";
if(!esAdminAcademico()) $sql.=' AND o.docente_id=?';
$sql.=filtroJornadasSQL($pid,'a');
$sql.=' GROUP BY o.id,a.nivel,a.nombre,a.paralelo,s.nombre,u.apellidos,u.nombres,ap.id,j.nombre,j.orden,a.orden,a.id ORDER BY COALESCE(j.orden,32767),a.orden,a.id,s.nombre';
$stmt=$conexion->prepare($sql);
if(esAdminAcademico()) $stmt->bind_param('si',$hoy,$pid); else $stmt->bind_param('sii',$hoy,$pid,$uid);
$stmt->execute(); $rows=$stmt->get_result()->fetch_all(MYSQLI_ASSOC); $stmt->close();
$tituloPagina='Registro de asistencia';
$subtituloPagina=esAdminAcademico()?'Control de asistencia por asignatura y paralelo del periodo activo.':'Registra y consulta la asistencia de tus asignaturas asignadas.';
require __DIR__.'/../../partials/header.php';
?>
<link rel="stylesheet" href="<?=e(url('assets/css/sga_listas_compactas_v1614.css'))?>">

<?php if(esAdminAcademico()):?><div class="toolbar" style="margin-bottom:15px">
  <a class="btn btn-primary" href="<?=e(url('modulos/reportes/asistencia.php'))?>">Ver reporte consolidado (PDF / Excel)</a>
</div><?php endif;?>
<div class="sga-listas-leyenda" aria-label="Estados de asistencia">
  <strong>Estados disponibles:</strong>
  <span class="badge good">Presente</span>
  <span class="badge bad">Ausente</span>
  <span class="badge warn">Atraso</span>
  <span class="badge">Justificado</span>
</div>
<?php if(!$rows):?>
  <div class="card empty">No existen asignaturas disponibles para registrar asistencia.</div>
<?php else:?>
<div class="sga-listas-compactas" role="list" aria-label="Asignaturas para registrar asistencia">
<?php foreach($rows as $o):?>
  <article class="sga-listas-fila sga-listas-fila--asistencia" role="listitem">
    <div class="sga-listas-identidad">
      <strong class="sga-listas-titulo"><?=e($o['asignatura'])?></strong>
      <span class="sga-listas-subtitulo"><?=e($o['nivel'].' · '.$o['aula'].' '.$o['paralelo'].' · '.($o['jornada']??'Sin jornada'))?></span>
      <?php if(esAdminAcademico()):?><span class="sga-listas-subtitulo">Docente: <?=e($o['docente'])?></span><?php endif;?>
    </div>
    <div class="sga-listas-metricas" aria-label="Resumen de asistencia">
      <span class="sga-listas-metrica"><strong><?=(int)$o['estudiantes']?></strong> estudiantes</span>
      <span class="sga-listas-metrica"><strong><?=(int)$o['sesiones']?></strong> registros</span>
      <span class="sga-listas-metrica">Última: <?=e($o['ultima_fecha']?:'Sin registro')?></span>
    </div>
    <div class="sga-listas-estado">
      <?php if((int)$o['hoy_registrada']===1):?>
      <span class="badge good">Hoy: registrada</span>
      <?php else:?>
      <span class="badge warn">Hoy: pendiente</span>
      <?php endif;?>
    </div>
    <div class="sga-listas-acciones">
      <a class="btn btn-primary btn-sm" href="<?=e(url('modulos/asistencia/registro.php?oferta_id='.(int)$o['id']))?>"><?=((int)$o['hoy_registrada']===1?'Editar asistencia de hoy':'Registrar asistencia')?></a>
      <a class="btn btn-secondary btn-sm" href="<?=e(url('modulos/asistencia/historial.php?oferta_id='.(int)$o['id']))?>">Historial</a>
      <?php if((int)$o['hoy_registrada']===1):?><a class="btn btn-success btn-sm" href="<?=e(url('modulos/asistencia/reporte_excel.php?oferta_id='.(int)$o['id'].'&fecha='.$hoy))?>">Excel de hoy</a><?php endif;?>
    </div>
  </article>
<?php endforeach;?>
</div>
<?php endif;?>
<?php require __DIR__.'/../../partials/footer.php';?>
