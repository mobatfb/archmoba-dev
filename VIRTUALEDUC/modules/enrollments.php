<?php
declare(strict_types=1);
if (!defined('VE_VERSION')) { http_response_code(404); exit; }
?>
<section><div class="ve-section-head"><h1>Matrículas</h1><?php creation_dialog($u,'enroll'); ?></div><p>Selecciona un curso para matricular estudiantes.</p><div class="ve-table"><table><thead><tr><th>ID</th><th>Curso</th><th>Estudiantes matriculados</th><th>Acción</th></tr></thead><tbody><?php foreach($courses as $x):?><tr><td><?=h($x['id'])?></td><td><?=h($x['title'])?></td><td><?=count_rows('SELECT COUNT(*) FROM ve_enrollments WHERE course_id=?',[$x['id']])?></td><td><a class="btn" href="?course=<?=h($x['id'])?>">Gestionar</a></td></tr><?php endforeach;?></tbody></table></div><?php if(!$courses):?><p class="muted">Crea un curso para comenzar.</p><?php endif;?></section>
