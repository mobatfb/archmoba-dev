<?php
declare(strict_types=1);
if (!defined('VE_VERSION')) { http_response_code(404); exit; }
?>
<h1>Mi progreso académico</h1><div class="grid"><?php foreach($courses as $x):$total=count_rows('SELECT COUNT(*) FROM ve_lessons WHERE course_id=?',[$x['id']]);$completed=count_rows('SELECT COUNT(*) FROM ve_progress p JOIN ve_lessons l ON l.id=p.lesson_id WHERE l.course_id=? AND p.student_id=?',[$x['id'],$u['id']]);?><article><h2 class="ve-card-title"><?=h($x['title'])?></h2><p><?=$completed?> de <?=$total?> lecciones completadas</p><progress value="<?=$completed?>" max="<?=max(1,$total)?>"></progress><p><a class="btn" href="?course=<?=h($x['id'])?>">Continuar curso</a></p></article><?php endforeach;?></div><?php if(!$courses):?><p class="muted">Aún no tienes cursos publicados y matriculados.</p><?php endif;?>
