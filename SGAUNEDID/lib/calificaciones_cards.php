<?php
/** Tarjeta de una asignatura con botones de trabajo en columna izquierda. */
function tarjetaAsignaturaCalificaciones(array $o, bool $soloCalificar = false, bool $menuDocente = false): void {
    $oid=(int)$o['id'];
    $apid=(int)($o['aula_periodo_id']??0);
    $esParametros=!empty($o['evaluacion_cualitativa_parametros']);
    $rutaPrincipal = $esParametros ? 'modulos/calificaciones/parametros.php?oferta_id=' : (!empty($o['solo_visor_comportamiento'])
        ? 'modulos/calificaciones/comportamiento.php?oferta_id='
        : 'modulos/calificaciones/index.php?oferta_id=');
    $idPrincipal = $oid;
    $datos=trim((string)$o['nivel'].' · '.(string)$o['aula'].' '.(string)$o['paralelo']);
    // Vista exclusiva del docente: una tarjeta compacta con acceso directo al registro de notas.
    // El administrador y subadministrador conservan su tarjeta completa de acciones.
    if ($soloCalificar) {
        ?>
        <article class="card course-card teacher-grade-card" aria-labelledby="curso-calificar-<?=$oid?>">
          <div class="teacher-grade-card-info">
            <h2 class="title" id="curso-calificar-<?=$oid?>"><?=e($o['asignatura'])?></h2>
            <div class="meta"><?=e($datos)?></div>
            <div class="stat-row"><span class="tag"><?=(int)$o['estudiantes']?> estudiantes</span><span class="tag"><?=e($o['periodo']??'')?></span></div>
          </div>
          <a class="btn btn-primary teacher-grade-card-button" href="<?=e(url($rutaPrincipal.$idPrincipal))?>" aria-label="<?=e('Calificar · '.$o['asignatura'].', '.$datos)?>"><?=$esParametros?'Calificar parámetros':(!empty($o['solo_visor_comportamiento'])?'Evaluar comportamiento':'Calificar')?></a>
        </article>
        <?php
        return;
    }
    ?>
    <article class="card course-card course-card-actions-left" aria-labelledby="curso-asignatura-<?=$oid?>">
      <nav class="course-card-buttons" aria-label="Acciones para <?=e($o['asignatura'])?>">
        <a class="btn btn-primary" href="<?=e(url($rutaPrincipal.$idPrincipal))?>"><?=$esParametros?'Calificar parámetros':(!empty($o['solo_visor_comportamiento'])?'Comportamiento':'Calificaciones')?></a>
        <?php if ($menuDocente): ?>
          <a class="btn btn-success" href="<?=e(url('modulos/asistencia/registro.php?oferta_id='.$oid))?>">Asistencia</a>
        <?php else: ?>
          <a class="btn btn-success" href="<?=e(url('modulos/asistencia/registro.php?oferta_id='.$oid))?>">Asistencia</a>
        <?php endif; ?>
        <a class="btn btn-secondary" href="<?=e(url('modulos/academico/lista.php?oferta_id='.$oid))?>">Lista</a>
        <a class="btn btn-secondary" href="<?=e(url('modulos/calificaciones/finales.php?oferta_id='.$oid))?>"><?=$esParametros?'Resumen T1–T3':'Finales'?></a>
      </nav>
      <div class="course-card-info">
        <h2 class="title" id="curso-asignatura-<?=$oid?>"><?=e($o['asignatura'])?></h2>
        <div class="meta"><?=e($datos)?></div>
        <div class="stat-row"><span class="tag"><?= (int)$o['estudiantes'] ?> estudiantes</span><span class="tag"><?=e($o['periodo']??'')?></span></div>
      </div>
    </article>
    <?php
}

/** Tarjeta compacta con una sola acción para elegir asignatura en los módulos docentes. */
function tarjetaSeleccionModuloDocente(array $o, string $modulo): void {
    $config=[
        'calificaciones'=>['Calificar','btn-primary','modulos/calificaciones/index.php?oferta_id='],
        'asistencia'=>['Registrar asistencia','btn-success','modulos/asistencia/registro.php?oferta_id='],
        'lista'=>['Ver lista','btn-secondary','modulos/academico/lista.php?oferta_id='],
        'finales'=>['Ver finales','btn-primary','modulos/calificaciones/finales.php?oferta_id='],
    ];
    if(!isset($config[$modulo])) return;
    [$texto,$estilo,$destino]=$config[$modulo];
    if(!empty($o['evaluacion_cualitativa_parametros'])){
        if($modulo==='calificaciones'){ $texto='Calificar parámetros';$destino='modulos/calificaciones/parametros.php?oferta_id='; }
        if($modulo==='finales'){ $texto='Resumen T1–T3';$destino='modulos/calificaciones/parametros.php?vista=resumen&oferta_id='; }
    }
    $oid=(int)$o['id'];
    $apid=(int)($o['aula_periodo_id']??0);
    $datos=trim((string)$o['nivel'].' · '.(string)$o['aula'].' '.(string)$o['paralelo']);
    ?>
    <article class="card course-card teacher-grade-card" aria-labelledby="curso-<?=e($modulo)?>-<?=$oid?>">
      <div class="teacher-grade-card-info">
        <h2 class="title" id="curso-<?=e($modulo)?>-<?=$oid?>"><?=e($o['asignatura'])?></h2>
        <div class="meta"><?=e($datos)?></div>
        <div class="stat-row"><span class="tag"><?=(int)$o['estudiantes']?> estudiantes</span><span class="tag"><?=e($o['periodo']??'')?></span></div>
      </div>
      <?php if($modulo==='asistencia'): ?>
        <div style="display:flex; flex-direction:column; align-items:stretch; gap:8px; margin-top:auto;">
          <a class="btn btn-success" href="<?=e(url($destino.$oid))?>" aria-label="<?=e($texto.' · '.$o['asignatura'].', '.$datos)?>"><?=e($texto)?></a>
          <a class="btn btn-primary" href="<?=e(url('modulos/asistencia/descargar_por_fechas.php?oferta_id='.$oid))?>">Descargar asistencia por fechas</a>
        </div>
      <?php else: ?>
        <a class="btn <?=e($estilo)?> teacher-grade-card-button" href="<?=e(url($destino.$oid))?>" aria-label="<?=e($texto.' · '.$o['asignatura'].', '.$datos)?>"><?=e($texto)?></a>
      <?php endif; ?>
    </article>
    <?php
}

