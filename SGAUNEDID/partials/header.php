<?php
require_once __DIR__ . '/../lib/funciones.php';
require_once __DIR__ . '/../lib/foto_perfil_privada.php';
exigirLogin();
$u=usuarioActual();$p=periodoActivo();$flash=tomarFlash();
$esSuper=esSuperadmin();$esAdmin=esAdminAcademico();$esDoc=$p?esDocenteOperativo((int)$p['id']):false;$esEst=$p?esEstudianteOperativo((int)$p['id']):false;$esRep=esRepresentanteOperativo();
$tituloPagina=$tituloPagina??APP_NAME;
$sgaFotoActual=sgaPerfilFotoExiste($u);
$sgaFotoIniciales=sgaPerfilIniciales($u);
$sgaFotoNombre=trim((string)($u['apellidos']??'').' '.(string)($u['nombres']??''));
$sgaFotoVersion=0;
if ($sgaFotoActual) {
    $sgaRutaFotoActual=sgaPerfilRutaFoto($u);
    $sgaFotoVersion=$sgaRutaFotoActual ? (int)@filemtime($sgaRutaFotoActual) : 0;
}
$sgaFotoImagenUrl=url('modulos/perfil/foto.php').'?v='.$sgaFotoVersion;
?>
<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title><?=e($tituloPagina)?> · <?=e(APP_NAME)?></title><link rel="icon" type="image/jpeg" href="<?=e(url('assets/img/logo.jpeg'))?>?v=20261111"><link rel="stylesheet" href="<?=e(url('assets/css/app.css'))?>?v=<?=(int)filemtime(__DIR__.'/../assets/css/app.css')?>"><?php if (!empty($sgaEstilosSupletorios)): ?><link rel="stylesheet" href="<?=e(url('assets/css/sga_supletorios.css'))?>?v=20261118-1"><?php endif; ?><script>document.documentElement.classList.add("sga-js");</script><link rel="stylesheet" href="<?=e(url('assets/css/sga_perfil.css'))?>?v=1633"></head>
<body>
<div class="app-shell">
<header class="mobile-topbar" aria-label="Barra de navegación móvil">
  <button type="button" class="mobile-menu-button" id="sga-menu-open" aria-label="Abrir menú principal" aria-controls="sga-sidebar" aria-expanded="false"><span aria-hidden="true" class="menu-bars"><span></span><span></span><span></span></span><span>Menú</span></button>
  <a class="mobile-brand" href="<?=e(url('dashboard.php'))?>"><img src="<?=e(url('assets/img/logo.jpeg'))?>" alt=""><span>SGA UNEDID</span></a>
  <span class="mobile-period" title="<?=e($p['nombre']??'Sin periodo activo')?>"><?=e($p['nombre']??'Sin periodo')?></span>
</header>
<button type="button" class="sidebar-scrim" id="sga-menu-scrim" aria-label="Cerrar menú" tabindex="-1"></button>
<aside class="sidebar" id="sga-sidebar" aria-label="Menú principal" tabindex="-1">
  <div class="sidebar-mobile-head"><strong>Navegación</strong><button type="button" class="sidebar-close-button" id="sga-menu-close" aria-label="Cerrar menú principal">Cerrar <span aria-hidden="true">×</span></button></div>
  <a class="brand" href="<?=e(url('dashboard.php'))?>"><img src="<?=e(url('assets/img/logo.jpeg'))?>" alt="Logo"><span><strong>Sistema de Gestión Académica UNEDID</strong><small>Plataforma académica institucional</small></span></a>
  <div class="period-chip"><span>Periodo activo</span><strong><?=e($p['nombre']??'Sin periodo activo')?></strong></div>
  <?php
    $rolesV=rolesOperativosDisponibles();
    $rolV=rolOperativoActual();
    $puedeCambiarV=count($rolesV)>1;
    $puedeJornadaV=$rolV==='subadmin' && !$esSuper && $p;
    if ($puedeJornadaV) {
      $pidV=(int)$p['id'];
      $jornadasIdsV=jornadasPermitidasPeriodo($pidV);
      $jornadasV=$jornadasIdsV
        ? $conexion->query('SELECT id,nombre FROM jornadas WHERE activo=1 AND id IN ('.implode(',',$jornadasIdsV).') ORDER BY orden,id')->fetch_all(MYSQLI_ASSOC)
        : [];
      if(empty($_SESSION['csrf_jornada_vista']))$_SESSION['csrf_jornada_vista']=bin2hex(random_bytes(24));
      $elegidaV=(int)($_SESSION['jornada_vista_periodos'][$pidV]??0);
      if(!in_array($elegidaV,$jornadasIdsV,true))$elegidaV=0;
      if(count($jornadasIdsV)===1)$elegidaV=(int)$jornadasIdsV[0];
    }
    if($puedeCambiarV && empty($_SESSION['csrf_cambio_rol']))$_SESSION['csrf_cambio_rol']=bin2hex(random_bytes(24));
    $nombresRolesV=['subadmin'=>'Subadmin','docente'=>'Docente','representante'=>'Representante',
       'estudiante'=>'Estudiante','superadmin'=>'Admin'];
  ?>
  <?php if($puedeCambiarV || $puedeJornadaV):?>
  <!-- Selector compacto. Jornada visible exclusivamente en perfil Subadministrador. -->
  <div class="sidebar-role-controls sidebar-role-controls--compact <?=$puedeCambiarV && $puedeJornadaV?'sidebar-role-controls--dual':''?>">
    <?php if($puedeCambiarV): ?>
    <form method="post" action="<?=e(url('modulos/roles/cambiar_actual.php'))?>" class="sidebar-role-form">
      <input type="hidden" name="csrf" value="<?=e($_SESSION['csrf_cambio_rol'])?>">
      <label for="sga-rol-operativo">Rol</label>
      <select id="sga-rol-operativo" name="rol" onchange="this.form.submit()" aria-label="Cambiar rol activo" title="<?=e('Perfil activo: '.($nombresRolesV[$rolV]??$rolV))?>">
        <?php foreach($rolesV as $codigo):?><option value="<?=e($codigo)?>" <?=$rolV===$codigo?'selected':''?>><?=e($nombresRolesV[$codigo]??$codigo)?></option><?php endforeach;?>
      </select>
      <noscript><button type="submit">Cambiar rol</button></noscript>
    </form>
    <?php endif; ?>
    <?php if($puedeJornadaV): ?>
      <?php if(count($jornadasV)===1): ?>
      <div class="sidebar-role-form">
        <label for="sga-jornada-vista">Jornada asignada</label>
        <select id="sga-jornada-vista" aria-label="Jornada autorizada" disabled>
          <option selected><?=e($jornadasV[0]['nombre'])?></option>
        </select>
      </div>
      <?php elseif(count($jornadasV)>1): ?>
      <form method="post" action="<?=e(url('modulos/roles/jornada_actual.php'))?>" class="sidebar-role-form">
        <input type="hidden" name="csrf" value="<?=e($_SESSION['csrf_jornada_vista'])?>">
        <label for="sga-jornada-vista">Filtrar mis jornadas</label>
        <select id="sga-jornada-vista" name="jornada_id" onchange="this.form.submit()" aria-label="Seleccionar una jornada autorizada">
          <option value="0">Todas mis jornadas</option>
          <?php foreach($jornadasV as $j):?><option value="<?=(int)$j['id']?>" <?=(int)$j['id']===$elegidaV?'selected':''?>><?=e($j['nombre'])?></option><?php endforeach;?>
        </select>
        <noscript><button type="submit">Aplicar jornada</button></noscript>
      </form>
      <?php else: ?>
      <div class="sidebar-role-form"><small>No tienes jornadas asignadas para este período.</small></div>
      <?php endif; ?>
    <?php endif; ?>
  </div>
  <?php endif; ?>
  <nav aria-label="Secciones de la plataforma">
    <a href="<?=e(url('dashboard.php'))?>">Inicio</a>
    <?php if($esAdmin): ?>
      <div class="nav-label">Operación académica</div>
      <a href="<?=e(url('modulos/academico/index.php'))?>">Gestión académica</a>
      <a href="<?=e(url('modulos/calificaciones/cursos.php'))?>">Calificaciones</a>
      <a href="<?=e(url('modulos/asistencia/index.php'))?>">Asistencia</a>
      <a href="<?=e(url('modulos/supletorios/index.php'))?>">Supletorios</a>
      <?php if($esSuper): ?><a href="<?=e(url('modulos/votaciones/index.php'))?>">Votaciones</a><?php endif; ?>
      <a href="<?=e(url('modulos/reportes/index.php'))?>">Reportes académicos</a>

      <div class="nav-label">Personas</div>
      <a href="<?=e(url('modulos/usuarios/index.php'))?>">Usuarios</a>
      <a href="<?=e(url('modulos/representantes/index.php'))?>">Representantes</a>
      <a href="<?=e(url('modulos/notificaciones/index.php'))?>">Notificaciones</a>
      <a href="<?=e(url('modulos/roles/index.php'))?>">Roles de usuarios</a>

      <div class="nav-label">Configuración académica</div>
      <a href="<?=e(url('modulos/aulas/index.php'))?>">Aulas y paralelos</a>
      <a href="<?=e(url('modulos/jornadas/index.php'))?>">Jornadas</a>
      <a href="<?=e(url('modulos/asignaturas/index.php'))?>">Asignaturas</a>
      <a href="<?=e(url('modulos/periodos/index.php'))?>">Periodos académicos</a>
      <a href="<?=e(url('modulos/areas/index.php'))?>">Áreas académicas</a>

      <?php if($esSuper): ?><div class="nav-label">Control y seguridad</div>
      <a href="<?=e(url('modulos/auditoria/index.php'))?>">Auditoría</a><?php endif; ?>
    <?php endif; ?>
    <?php if($esDoc): ?>
      <div class="nav-label">Docencia</div>
      <a href="<?=e(url('modulos/academico/mis_cursos.php'))?>">Mis cursos y asignaturas</a>
      <?php if(!$esAdmin):?><a href="<?=e(url('modulos/notificaciones/index.php'))?>">Notificaciones</a><?php endif;?>
      <?php if(!$esAdmin):?><a href="<?=e(url('modulos/representantes/index.php'))?>">Representantes</a><?php endif;?>
      <?php if(!$esAdmin): ?>
        <a href="<?=e(url('modulos/calificaciones/cursos.php'))?>">Calificaciones</a>
        <a href="<?=e(url('modulos/docente/seleccionar.php?modulo=asistencia'))?>">Asistencia</a>
        <a href="<?=e(url('modulos/docente/seleccionar.php?modulo=lista'))?>">Lista</a>
        <a href="<?=e(url('modulos/docente/seleccionar.php?modulo=finales'))?>">Finales</a>
        <a href="<?=e(url('modulos/supletorios/index.php'))?>">Supletorios</a>
      <?php endif; ?>
    <?php endif; ?>
    <?php if($esRep): ?><div class="nav-label">Familia</div><a href="<?=e(url('modulos/representantes/mis_hijos.php'))?>">Mis hijos</a><a href="<?=e(url('modulos/notificaciones/index.php'))?>">Notificaciones</a><?php endif; ?>
    <?php if($esEst): ?><div class="nav-label">Estudiante</div><a href="<?=e(url('modulos/estudiante/index.php'))?>">Mis calificaciones</a><a href="<?=e(url('modulos/votaciones/index.php'))?>">Votaciones</a><?php endif; ?>
  </nav>
  <div class="sidebar-bottom sidebar-bottom--perfil">
    <a href="<?=e(url('modulos/perfil/index.php'))?>" id="sga-perfil-open" class="sga-perfil-miniboton"
       title="Ver mi perfil: <?=e($sgaFotoNombre)?>" aria-label="Abrir mi perfil" aria-haspopup="dialog" aria-controls="sga-perfil-dialog">
      <span class="sga-perfil-avatar sga-perfil-avatar--mini" aria-hidden="true">
        <?php if($sgaFotoActual):?><img src="<?=e($sgaFotoImagenUrl)?>" alt="" loading="lazy" draggable="false"><?php else:?><?=e($sgaFotoIniciales)?><?php endif;?>
      </span>
      <span class="sga-perfil-mini-datos">
        <strong class="sga-perfil-mini-nombre"><?=e($sgaFotoNombre)?></strong>
        <small class="sga-perfil-mini-cedula"><?=e($u['cedula']??'')?></small>
      </span>
    </a>
    <a class="logout sga-perfil-logout" href="<?=e(url('logout.php'))?>">Salir</a>
  </div>
</aside>
<main class="content">
<header class="content-top"><div><h1><?=e($tituloPagina)?></h1><?php if(!empty($subtituloPagina)):?><p><?=e($subtituloPagina)?></p><?php endif;?></div></header>
<?php if($flash):?><div class="alert <?=e($flash['tipo'])?>" role="alert"><span><?=e($flash['mensaje'])?></span><button type="button" class="alert-close" aria-label="Cerrar notificación" title="Cerrar notificación">&times;</button></div><?php endif;?>
