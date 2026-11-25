<?php
declare(strict_types=1);
if (!defined('VE_VERSION')) { http_response_code(404); exit; }
if (!course_can_edit($u,$c)) return;
?>
<dialog class="ve-dialog ve-course-enroll" id="course-enroll-dialog" aria-labelledby="course-enroll-title" data-ve-course-id="<?=h($c['id'])?>" data-ve-limit="<?=COURSE_ENROLL_LIMIT?>">
  <div class="ve-dialog-head"><h2 id="course-enroll-title">Crear matrícula</h2><button type="button" class="ve-quiet" data-ve-close aria-label="Cerrar">×</button></div>
  <p class="muted">Selecciona estudiantes para <?=h($c['title'])?>. Los que ya están matriculados no aparecen entre los disponibles.</p>
  <form method="post">
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
  <noscript><p>Activa JavaScript para seleccionar estudiantes.</p></noscript>
</dialog>
