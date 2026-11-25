<?php
declare(strict_types=1);
if (!defined('VE_VERSION')) { http_response_code(404); exit; }
if (!course_can_edit($u,$c)) return;
$templateUrl='?'.http_build_query(['template'=>1,'kind'=>'course_enroll','course_id'=>(int)$c['id']]);
?>
<dialog class="ve-dialog ve-course-enroll" id="course-enroll-dialog" aria-labelledby="course-enroll-title" data-ve-course-id="<?=h($c['id'])?>" data-ve-limit="<?=COURSE_ENROLL_LIMIT?>">
  <div class="ve-dialog-head"><h2 id="course-enroll-title">Crear matrícula</h2><button type="button" class="ve-quiet" data-ve-close aria-label="Cerrar">×</button></div>
  <div class="ve-tabs" role="tablist" aria-label="Tipo de matrícula"><button type="button" role="tab" id="course-enroll-individual-tab" aria-controls="course-enroll-individual" aria-selected="true" data-ve-tab="individual">Selección manual</button><button type="button" role="tab" id="course-enroll-bulk-tab" aria-controls="course-enroll-bulk" aria-selected="false" data-ve-tab="bulk">Masivo (CSV)</button></div>
  <div role="tabpanel" id="course-enroll-individual" aria-labelledby="course-enroll-individual-tab" data-ve-panel="individual">
  <p class="muted">Selecciona estudiantes para <?=h($c['title'])?>. Los que ya están matriculados no aparecen entre los disponibles.</p>
  <form method="post" data-ve-enroll-manual>
    <?php action('course_enroll_many',(int)$c['id']); ?>
    <div class="ve-enroll-columns">
      <div class="ve-enroll-pane">
        <h3>Estudiantes disponibles</h3>
        <label>Buscar por usuario o nombre<input type="search" data-ve-enroll-search maxlength="75" autocomplete="off" placeholder="Buscar estudiante..."></label>
        <p class="muted ve-enroll-status" data-ve-enroll-status role="status" aria-live="polite">Cargando estudiantes...</p>
        <div class="ve-enroll-list" data-ve-enroll-available aria-label="Estudiantes disponibles"></div>
        <div class="ve-enroll-pages"><button type="button" class="ve-quiet" data-ve-enroll-prev disabled>Anterior</button><span data-ve-enroll-page>Página 1</span><button type="button" class="ve-quiet" data-ve-enroll-next disabled>Siguiente</button></div>
      </div>
      <div class="ve-enroll-pane">
        <h3>Seleccionados (<span data-ve-enroll-count>0</span>)</h3>
        <p class="muted">Hasta <?=COURSE_ENROLL_LIMIT?> estudiantes por operación.</p>
        <div class="ve-enroll-list" data-ve-enroll-selected aria-label="Estudiantes seleccionados"><p class="muted">No has seleccionado estudiantes.</p></div>
        <div data-ve-enroll-inputs hidden></div>
      </div>
    </div>
    <div class="ve-dialog-actions"><button type="button" class="ve-quiet" data-ve-close>Cancelar</button><button type="submit" data-ve-enroll-submit disabled>Matricular (0)</button></div>
  </form>
  </div>
  <div role="tabpanel" id="course-enroll-bulk" aria-labelledby="course-enroll-bulk-tab" data-ve-panel="bulk" hidden>
    <p>Descarga la plantilla CSV, reemplaza o elimina la fila de ejemplo e introduce un usuario por fila. Guarda el archivo en formato CSV UTF-8.</p>
    <p class="muted">Curso: <strong><?=h($c['title'])?></strong>. No necesitas indicar el ID del curso.</p>
    <a class="btn" href="<?=h($templateUrl)?>">↓ Descargar plantilla CSV</a>
    <p class="ve-columns"><code>usuario</code></p>
    <p class="muted">Máximo <?=COURSE_ENROLL_LIMIT?> registros y 2 MB. Conserva los ceros iniciales de los usuarios. Los ya matriculados y las filas repetidas se omitirán. Si algún usuario no existe o no es estudiante, no se guardará ninguna matrícula.</p>
    <form method="post" enctype="multipart/form-data" data-ve-enroll-csv>
      <?php creation_hidden('course_enroll','',(int)$c['id'],'bulk'); ?>
      <label>Archivo CSV<input name="csv" type="file" accept=".csv,text/csv" required></label>
      <div class="ve-dialog-actions"><button type="button" class="ve-quiet" data-ve-close>Cancelar</button><button type="submit">Validar y matricular</button></div>
    </form>
  </div>
  <noscript><p>Activa JavaScript para seleccionar estudiantes.</p></noscript>
</dialog>
