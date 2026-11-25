<?php
require_once __DIR__.'/../../lib/funciones.php';
require_once __DIR__.'/../../lib/calificaciones_cards.php';
exigirLogin();
$modulo=(string)($_GET['modulo']??'');
$modulos=[
    'calificaciones'=>['titulo'=>'Calificaciones','descripcion'=>'Selecciona la asignatura que deseas calificar.'],
    'asistencia'=>['titulo'=>'Asistencia','descripcion'=>'Selecciona la asignatura en la que registrarás asistencia.'],
    'lista'=>['titulo'=>'Lista','descripcion'=>'Selecciona la asignatura para consultar la lista de estudiantes.'],
    'finales'=>['titulo'=>'Finales','descripcion'=>'Selecciona la asignatura para consultar sus notas finales.'],
];
if(!isset($modulos[$modulo])) { http_response_code(404); die('Módulo no disponible.'); }
$p=periodoActivo();
$pid=(int)($p['id']??0);
if(!$pid || !esDocenteOperativo($pid)) {
    http_response_code(403); die('No tienes asignaturas docentes autorizadas en el período activo.');
}
$uid=(int)$_SESSION['usuario_id'];
    $sql="SELECT o.id,ap.id aula_periodo_id,a.nivel,a.nombre aula,a.paralelo,CASE WHEN o.evaluacion_aula=1 THEN 'Evaluación cualitativa del aula' ELSE s.nombre END asignatura,CASE WHEN o.evaluacion_aula=1 OR o.evaluacion_parametros_historica=1 THEN 0 ELSE s.solo_visor_comportamiento END solo_visor_comportamiento,(o.evaluacion_aula=1 OR o.evaluacion_parametros_historica=1) evaluacion_cualitativa_parametros,p.nombre periodo,
      (SELECT COUNT(*) FROM matriculas m WHERE m.aula_periodo_id=ap.id AND m.estado='activo') estudiantes
      FROM ofertas_academicas o
      JOIN aulas_periodo ap ON ap.id=o.aula_periodo_id
      JOIN aulas a ON a.id=ap.aula_id
      JOIN asignaturas s ON s.id=o.asignatura_id
      JOIN areas ar ON ar.id=s.area_id
      JOIN periodos_academicos p ON p.id=ap.periodo_id
      WHERE ap.periodo_id=? AND ap.activo=1 AND o.activo=1 AND (ap.evaluacion_cualitativa_parametros=0 OR o.evaluacion_aula=1) AND o.docente_id=? AND s.archivado_en IS NULL AND ar.archivado_en IS NULL";
$sql.=filtroJornadasSQL($pid,'a');
$sql.=' ORDER BY a.id ASC,s.nombre ASC';
$stmt=$conexion->prepare($sql);
$stmt->bind_param('ii',$pid,$uid);
$stmt->execute();
$rows=$stmt->get_result()->fetch_all(MYSQLI_ASSOC);
$stmt->close();
$tituloPagina='Módulo de '.$modulos[$modulo]['titulo'];
$subtituloPagina=$modulos[$modulo]['descripcion'];
require __DIR__.'/../../partials/header.php';
?>
<?php if(!$rows):?>
  <div class="card empty">No tienes cursos asignados en el período académico activo.</div>
<?php else:?>
  <div class="grid cols-2 subject-card-grid teacher-grade-grid">
    <?php foreach($rows as $o) tarjetaSeleccionModuloDocente($o,$modulo); ?>
  </div>
<?php endif;?>
<?php require __DIR__.'/../../partials/footer.php'; ?>
