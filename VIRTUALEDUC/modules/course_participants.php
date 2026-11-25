<?php
declare(strict_types=1);
if (!defined('VE_VERSION')) { http_response_code(404); exit; }
$canManage=course_can_edit($u,$c);
$participantTotal=count_rows('SELECT COUNT(*) FROM enrollments WHERE course_id=?',[$c['id']]);
$pages=max(1,(int)ceil($participantTotal/COURSE_STUDENT_PAGE));
$participantPage=min($pages,filter_var($_GET['participant_page']??'1',FILTER_VALIDATE_INT,['options'=>['min_range'=>1]])?:1);
$columns=$canManage?'u.name,COALESCE(u.username,u.email) AS username,e.enrolled_at':'u.name';
$participants=all('SELECT '.$columns.' FROM enrollments e JOIN users u ON u.id=e.student_id WHERE e.course_id=? ORDER BY u.name,u.id LIMIT '.COURSE_STUDENT_PAGE.' OFFSET '.(($participantPage-1)*COURSE_STUDENT_PAGE),[$c['id']]);
?>
<h2>Participantes <span class="tag"><?=h($participantTotal)?> matriculados</span></h2>
<p class="muted">Responsable: <?=h($teacher['name']??'Sin definir')?></p>
<?php if (!$participants): ?><div class="ve-course-empty"><strong>Aún no hay estudiantes matriculados.</strong></div>
<?php else: ?><div class="ve-table ve-participants-table" tabindex="0" aria-label="Participantes matriculados"><table><thead><tr><th>Nombre</th><?php if ($canManage):?><th>Usuario</th><th>Fecha de matrícula</th><?php endif;?></tr></thead><tbody>
<?php foreach ($participants as $participant):?><tr><td><?=h($participant['name'])?></td><?php if ($canManage):?><td><?=h($participant['username'])?></td><td><?=h($participant['enrolled_at'])?></td><?php endif;?></tr><?php endforeach;?>
</tbody></table></div>
<?php if ($pages>1):?><nav class="ve-participant-pages" aria-label="Páginas de participantes"><?php if ($participantPage>1):?><a class="btn" href="<?=h($courseUrl.'&tab=participants&participant_page='.($participantPage-1))?>">Anterior</a><?php endif;?><span>Página <?=$participantPage?> de <?=$pages?></span><?php if ($participantPage<$pages):?><a class="btn" href="<?=h($courseUrl.'&tab=participants&participant_page='.($participantPage+1))?>">Siguiente</a><?php endif;?></nav><?php endif;?>
<?php endif;?>
