<?php
require_once __DIR__.'/lib/funciones.php';
require_once __DIR__.'/lib/calificaciones_cards.php';
exigirLogin();
$tituloPagina='Panel principal';
$subtituloPagina='Acceso a los módulos disponibles según tu rol y asignaciones del periodo.';
$u=usuarioActual();$p=periodoActivo();$pid=$p?(int)$p['id']:0;$super=esSuperadmin();$admin=esAdminAcademico();$doc=$pid?esDocenteOperativo($pid):false;$est=$pid?esEstudianteOperativo($pid):false;$rep=esRepresentanteOperativo();
$metricas=['usuarios'=>0,'aulas'=>0,'ofertas'=>0,'matriculas'=>0];
if($admin && $pid>0){
  $join=' JOIN aulas_periodo ap ON ap.id=m.aula_periodo_id JOIN aulas a ON a.id=ap.aula_id';
  $alcance=filtroJornadasSQL($pid,'a');
  $queries=[
    'usuarios'=>"SELECT COUNT(DISTINCT u.id) c FROM usuarios u WHERE u.activo=1".($super?'':filtroUsuariosJornadasSQL($pid,'u')),
    'aulas'=>"SELECT COUNT(*) c FROM aulas_periodo ap JOIN aulas a ON a.id=ap.aula_id WHERE ap.periodo_id=$pid AND ap.activo=1$alcance",
    'ofertas'=>"SELECT COUNT(*) c FROM ofertas_academicas o JOIN aulas_periodo ap ON ap.id=o.aula_periodo_id JOIN aulas a ON a.id=ap.aula_id WHERE ap.periodo_id=$pid AND o.activo=1$alcance",
    'matriculas'=>"SELECT COUNT(*) c FROM matriculas m $join WHERE ap.periodo_id=$pid AND m.estado='activo'$alcance"
  ];
  foreach($queries as $k=>$sql){$r=$conexion->query($sql);$metricas[$k]=(int)($r?$r->fetch_assoc()['c']:0);}
}

$misOfertas=[];
if($doc){$uid=(int)$u['id'];$stmt=$conexion->prepare("SELECT o.id,ap.id aula_periodo_id,a.nivel,a.nombre aula,a.paralelo,CASE WHEN o.evaluacion_aula=1 THEN 'Evaluación cualitativa del aula' ELSE s.nombre END asignatura,CASE WHEN o.evaluacion_aula=1 OR o.evaluacion_parametros_historica=1 THEN 0 ELSE s.solo_visor_comportamiento END solo_visor_comportamiento,(o.evaluacion_aula=1 OR o.evaluacion_parametros_historica=1) evaluacion_cualitativa_parametros,p.nombre periodo,(SELECT COUNT(*) FROM matriculas m WHERE m.aula_periodo_id=ap.id AND m.estado='activo') estudiantes FROM ofertas_academicas o JOIN aulas_periodo ap ON ap.id=o.aula_periodo_id JOIN aulas a ON a.id=ap.aula_id JOIN asignaturas s ON s.id=o.asignatura_id JOIN areas ar ON ar.id=s.area_id JOIN periodos_academicos p ON p.id=ap.periodo_id WHERE o.docente_id=? AND ap.periodo_id=? AND ap.activo=1 AND o.activo=1 AND (ap.evaluacion_cualitativa_parametros=0 OR o.evaluacion_aula=1) AND s.archivado_en IS NULL AND ar.archivado_en IS NULL".filtroJornadasSQL($pid,'a')." ORDER BY a.id ASC,s.nombre ASC");$stmt->bind_param('ii',$uid,$pid);$stmt->execute();$misOfertas=$stmt->get_result()->fetch_all(MYSQLI_ASSOC);$stmt->close();}
require __DIR__.'/partials/header.php';
?>
<?php if(!$p):?><div class="notice">No existe un periodo académico activo. El superadministrador debe crear o activar uno.</div><?php endif;?>
<?php if($admin):?>
<div class="grid cols-4">
  <div class="card metric"><span>Usuarios activos</span><strong><?=$metricas['usuarios']?></strong></div>
  <div class="card metric"><span>Aulas del periodo</span><strong><?=$metricas['aulas']?></strong></div>
  <div class="card metric"><span>Asignaciones académicas</span><strong><?=$metricas['ofertas']?></strong></div>
  <div class="card metric"><span>Matrículas activas</span><strong><?=$metricas['matriculas']?></strong></div>
</div>
<h2 class="section-title">Operación académica</h2>
<div class="grid cols-4">
  <a class="card course-card" href="<?=e(url('modulos/academico/index.php'))?>"><div class="title">Gestión académica</div><div class="meta">Matrículas, paralelos, asignaturas y docentes responsables del periodo.</div></a>
  <a class="card course-card" href="<?=e(url('modulos/asistencia/index.php'))?>"><div class="title">Asistencia</div><div class="meta">Registro y control diario de asistencia por asignatura y paralelo.</div></a>
  <?php if($super):?><a class="card course-card" href="<?=e(url('modulos/votaciones/index.php'))?>"><div class="title">Votaciones</div><div class="meta">Elecciones estudiantiles anuales, jornadas, candidatos y resultados.</div></a><?php endif;?>
  <a class="card course-card" href="<?=e(url('modulos/reportes/index.php'))?>"><div class="title">Reportes académicos</div><div class="meta">Consolidados, certificaciones anuales y reportes trimestrales.</div></a>
  <a class="card course-card" href="<?=e(url('modulos/representantes/index.php'))?>"><div class="title">Representantes</div><div class="meta">Vincular familias y notificar novedades de estudiantes.</div></a>
  <a class="card course-card" href="<?=e(url('modulos/usuarios/index.php'))?>"><div class="title">Usuarios</div><div class="meta">Personas, carga masiva y consulta de roles asignados.</div></a>
</div>
<h2 class="section-title">Configuración y control</h2>
<div class="grid cols-4">
  <?php if($super):?><a class="card course-card" href="<?=e(url('modulos/periodos/index.php'))?>"><div class="title">Periodos académicos</div><div class="meta">Creación, activación y administración de periodos anuales.</div></a><?php endif;?>
  <?php if($super): ?><a class="card course-card" href="<?=e(url('modulos/aulas/index.php'))?>"><div class="title">Aulas y paralelos</div><div class="meta">Catálogo institucional de niveles, cursos y paralelos reutilizables.</div></a>
  <a class="card course-card" href="<?=e(url('modulos/asignaturas/index.php'))?>"><div class="title">Asignaturas</div><div class="meta">Catálogo de materias disponibles para cada periodo académico.</div></a>
  <a class="card course-card" href="<?=e(url('modulos/jornadas/index.php'))?>"><div class="title">Jornadas</div><div class="meta">Catálogo de horarios y jornadas vinculadas a cada aula.</div></a><?php endif;?>
  <?php if($super):?><a class="card course-card" href="<?=e(url('modulos/roles/index.php'))?>"><div class="title">Roles de usuarios</div><div class="meta">Permisos de administrador, subadministrador, docente y estudiante.</div></a>
  <a class="card course-card" href="<?=e(url('modulos/auditoria/index.php'))?>"><div class="title">Auditoría</div><div class="meta">Bitácora de accesos, cambios y operaciones sensibles del sistema.</div></a><?php endif;?>
</div>
<?php endif;?>
<?php if($doc):?>
<h2 class="section-title">Mis asignaturas</h2>
<?php if(!$admin):?><p><a class="btn btn-secondary" href="<?=e(url('modulos/representantes/index.php'))?>">Consultar representantes de mis estudiantes</a></p><?php endif;?>
<p class="muted" style="margin-top:-5px;margin-bottom:15px">Accede desde cada asignatura a Calificaciones, Asistencia, Lista y Finales.</p>
<?php if(!$misOfertas):?><div class="card empty">No tienes asignaturas asignadas en el periodo activo.</div>
<?php else:?><div class="grid cols-2 subject-card-grid">
  <?php foreach($misOfertas as $o) tarjetaAsignaturaCalificaciones($o,false,!$admin); ?>
</div><?php endif;?>
<?php endif;?>
<?php if($est):?>
<h2 class="section-title">Mi gestión académica</h2><div class="grid cols-2"><a class="card course-card" href="<?=e(url('modulos/estudiante/index.php'))?>"><div class="title">Mis calificaciones</div><div class="meta">Consulta las asignaturas y notas finales del periodo activo.</div></a><a class="card course-card" href="<?=e(url('modulos/votaciones/index.php'))?>"><div class="title">Votaciones estudiantiles</div><div class="meta">Participa en el proceso electoral anual cuando tu paralelo esté habilitado.</div></a></div>
<?php endif;?>
<?php if($rep):?><h2 class="section-title">Familia</h2><div class="grid cols-2"><a class="card course-card" href="<?=e(url('modulos/representantes/mis_hijos.php'))?>"><div class="title">Mis hijos</div><div class="meta">Consultar calificaciones, asistencia y novedades de tus estudiantes vinculados.</div></a></div><?php endif;?>
<?php if(!$admin&&!$doc&&!$est&&!$rep):?><div class="card empty"><h3>Usuario sin rol en el periodo activo</h3><p>Tu cuenta existe, pero aún no ha sido matriculada como estudiante ni asignada como docente.</p></div><?php endif;?>
<?php require __DIR__.'/partials/footer.php'; ?>
