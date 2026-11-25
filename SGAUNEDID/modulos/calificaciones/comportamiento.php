<?php
require_once __DIR__.'/../../lib/funciones.php';
require_once __DIR__.'/../../lib/comportamiento_trimestres.php';
exigirLogin();
header('Cache-Control: private, no-store, max-age=0');
$oid=(int)($_GET['oferta_id']??0);
$trimestre=(int)($_GET['trimestre']??1);
if (!$oid || !puedeGestionarOferta($oid)) { http_response_code(403); die('No tienes acceso a esta asignatura.'); }
$o=ofertaDetalle($oid);
if (!$o || empty($o['solo_visor_comportamiento']) || !(int)$o['activo']) {
    http_response_code(404); die('Esta asignatura no está marcada como asignatura de comportamiento.');
}
if (!in_array($trimestre,[0,1,2,3],true)) { http_response_code(400); die('Trimestre inválido.'); }
$soloLectura=($o['periodo_estado']??'')==='cerrado';
if (empty($_SESSION['csrf_comportamiento_trimestre'])) {
    $_SESSION['csrf_comportamiento_trimestre']=bin2hex(random_bytes(32));
}
$csrf=$_SESSION['csrf_comportamiento_trimestre'];
$apid=(int)$o['aula_periodo_id'];
$stmt=$conexion->prepare("SELECT m.id AS matricula_id,m.numero_lista,u.cedula,u.apellidos,u.nombres,
    c1.literal AS t1,c2.literal AS t2,c3.literal AS t3
    FROM matriculas m JOIN usuarios u ON u.id=m.estudiante_id
    LEFT JOIN calificaciones_comportamiento_trimestre c1
        ON c1.matricula_id=m.id AND c1.oferta_id=? AND c1.trimestre=1
    LEFT JOIN calificaciones_comportamiento_trimestre c2
        ON c2.matricula_id=m.id AND c2.oferta_id=? AND c2.trimestre=2
    LEFT JOIN calificaciones_comportamiento_trimestre c3
        ON c3.matricula_id=m.id AND c3.oferta_id=? AND c3.trimestre=3
    WHERE m.aula_periodo_id=? AND m.estado='activo'
    ORDER BY COALESCE(m.numero_lista,999999),u.apellidos,u.nombres");
$stmt->bind_param('iiii',$oid,$oid,$oid,$apid);
$stmt->execute();$rows=$stmt->get_result()->fetch_all(MYSQLI_ASSOC);$stmt->close();
foreach($rows as &$fila) {
    $fila['final']=sgaComportamientoFinal($fila['t1'],$fila['t2'],$fila['t3']);
}
unset($fila);
$opciones=sgaComportamientoOpciones();
$tituloPagina='Comportamiento · '.$o['asignatura'];
$subtituloPagina=$o['nivel'].' · '.$o['aula'].' '.$o['paralelo'].' · '.$o['periodo'];
require __DIR__.'/../../partials/header.php';
?>
<link rel="stylesheet" href="<?=e(url('assets/css/sga_comportamiento_trimestres.css'))?>?v=5">
<div class="toolbar grade-toolbar comport-toolbar">
  <div class="actions">
    <?php for($s=1;$s<=3;$s++):?>
      <a class="btn <?=$s===$trimestre?'btn-primary':'btn-secondary'?>" href="<?=e(url('modulos/calificaciones/comportamiento.php?oferta_id='.$oid.'&trimestre='.$s))?>" <?=$s===$trimestre?'aria-current="page"':''?>>Trimestre <?=$s?></a>
    <?php endfor;?>
    <a class="btn <?=$trimestre===0?'btn-primary':'btn-secondary'?>" href="<?=e(url('modulos/calificaciones/comportamiento.php?oferta_id='.$oid.'&trimestre=0'))?>" <?=$trimestre===0?'aria-current="page"':''?>>Finales</a>
  </div>
  <div class="actions"><a class="btn btn-success" href="<?=e(url('modulos/calificaciones/comportamiento_excel.php?oferta_id='.$oid))?>">Descargar Excel</a>
    <a class="btn btn-secondary" href="<?=e(url('modulos/calificaciones/cursos.php'))?>">Volver a asignaturas</a></div>
</div>
<section class="card comport-card">
  <div class="comport-intro">
    <div><h2>Evaluación de comportamiento · <?=$trimestre===0?'Finales':'Trimestre '.$trimestre?></h2>
      <p><?=$trimestre===0
          ? 'Promedio cualitativo de los tres trimestres. Solo aparece una letra final cuando las tres valoraciones están completas.'
          : 'Selecciona una valoración por estudiante o pulsa «Sin nota» para retirarla. Cada cambio se guarda automáticamente.'?></p></div>
    <div class="comport-cuenta"><strong><?=count($rows)?></strong><span>estudiantes</span></div>
  </div>
  <?php if($soloLectura && $trimestre!==0):?><div class="notice" role="status">Período cerrado: las valoraciones están en modo de consulta.</div><?php endif;?>
  <?php if(!$rows):?><div class="empty">No hay estudiantes activos en el aula.</div>
  <?php else:?>
  <?php if($trimestre===0):?>
  <div class="comport-scroll" role="region" aria-label="Promedios finales de comportamiento" tabindex="0">
    <table class="comport-tabla comport-tabla-final">
      <thead><tr><th class="comport-num">No.</th><th class="comport-nombre">Estudiante</th>
        <th>Trimestre 1</th><th>Trimestre 2</th><th>Trimestre 3</th><th>Final</th></tr></thead>
      <tbody>
      <?php foreach($rows as $i=>$r): $final=$r['final']; ?>
        <tr>
          <td class="comport-num"><?=e($r['numero_lista']?:($i+1))?></td>
          <th scope="row" class="comport-nombre"><strong><?=e($r['apellidos'].' '.$r['nombres'])?></strong><small><?=e($r['cedula'])?></small></th>
          <?php for($t=1;$t<=3;$t++): $literal=$r['t'.$t]??null; ?>
            <td class="comport-celda-final">
              <?php if($literal!==null && sgaComportamientoValorValido((string)$literal)):?>
                <span class="comport-final-valor comport-grado-<?=e(sgaComportamientoTono((string)$literal))?>"><?=e($literal)?></span>
              <?php else:?>—<?php endif;?>
            </td>
          <?php endfor;?>
          <td class="comport-celda-final">
            <?php if($final!==null):?>
              <strong class="comport-final-valor comport-grado-<?=e(sgaComportamientoTono($final))?>"><?=e($final)?></strong>
            <?php else:?>
              <span class="comport-final-pendiente">Pendiente</span>
            <?php endif;?>
          </td>
        </tr>
      <?php endforeach;?>
      </tbody>
    </table>
  </div>
  <p class="comport-ayuda">La nota final se calcula promediando las posiciones de A+ a F- y redondeando a la letra más cercana. No interviene en el promedio académico general.</p>
  <?php else:?>
  <div class="comport-scroll" role="region" aria-label="Tabla de calificación cualitativa" tabindex="0">
    <table class="comport-tabla" id="comport-tabla"
      data-guardar-url="<?=e(url('modulos/calificaciones/guardar_comportamiento.php'))?>"
      data-oferta-id="<?=$oid?>" data-trimestre="<?=$trimestre?>" data-csrf="<?=e($csrf)?>">
      <thead><tr><th class="comport-num">No.</th><th class="comport-nombre">Estudiante</th>
        <?php foreach($opciones as $literal):?><th scope="col"><?=e($literal)?></th><?php endforeach;?>
        <th scope="col" class="comport-sin-nota-cabecera">Sin nota</th>
        <th class="comport-estado-head">Estado</th></tr></thead>
      <tbody>
      <?php foreach($rows as $i=>$r):
        $mid=(int)$r['matricula_id'];$actual=(string)($r['t'.$trimestre]??'');
      ?>
        <tr data-matricula-id="<?=$mid?>" data-actual="<?=e($actual)?>">
          <td class="comport-num"><?=e($r['numero_lista']?:($i+1))?></td>
          <th scope="row" class="comport-nombre"><strong><?=e($r['apellidos'].' '.$r['nombres'])?></strong><small><?=e($r['cedula'])?></small></th>
          <?php foreach($opciones as $literal): $sel=($actual===$literal);?>
            <td class="comport-celda"><button type="button" class="comport-opcion comport-grado-<?=e(sgaComportamientoTono($literal))?> <?=$sel?'seleccionado':''?>"
              data-literal="<?=e($literal)?>" aria-pressed="<?=$sel?'true':'false'?>"
              aria-label="<?=e($r['apellidos'].' '.$r['nombres'].': '.$literal)?>"
              <?=$soloLectura?'disabled':''?>><?=e($literal)?></button></td>
          <?php endforeach;?>
          <td class="comport-celda comport-celda-sin-nota"><button type="button" class="comport-opcion comport-sin-nota"
            data-literal="" aria-label="Dejar sin nota a <?=e($r['apellidos'].' '.$r['nombres'])?>"
            title="Eliminar valoración del trimestre para este estudiante"
            <?=$soloLectura?'disabled':''?>>Sin nota</button></td>
          <td class="comport-estado"><span class="comport-estado-texto" role="status" aria-live="polite"><?= $actual!==''?'Guardado':'Sin nota' ?></span></td>
        </tr>
      <?php endforeach;?>
      </tbody>
    </table>
  </div>
  <p class="comport-ayuda">A y B: verde; C: amarillo; D, E y F: rojo. «Sin nota» elimina la valoración de este trimestre, sin afectar los demás. Todo se guarda automáticamente.</p>
  <?php endif;?>
  <?php endif;?>
</section>
<script src="<?=e(url('assets/js/sga_comportamiento_trimestres.js'))?>?v=4" defer></script>
<?php require __DIR__.'/../../partials/footer.php';?>
