<?php
declare(strict_types=1);
if (!defined('VE_VERSION')) { http_response_code(404); exit; }
$canManage=course_can_edit($u,$c);
$participantTotal=count_rows('SELECT COUNT(*) FROM enrollments WHERE course_id=?',[$c['id']]);
$participantSearch=is_string($_GET['participant_q']??null)?trim($_GET['participant_q']):'';
if(strlen($participantSearch)>300 || !preg_match('//u',$participantSearch)) $participantSearch='';
$participantParams=[$c['id']];
$participantWhere=' FROM enrollments e JOIN users u ON u.id=e.student_id WHERE e.course_id=?';
if ($participantSearch!=='') {
    $term='%'.strtr($participantSearch,['!'=>'!!','%'=>'!%','_'=>'!_']).'%';
    $participantWhere.=" AND (u.name LIKE ? ESCAPE '!'"; $participantParams[]=$term;
    if($canManage) { $participantWhere.=" OR COALESCE(u.username,u.email) LIKE ? ESCAPE '!'"; $participantParams[]=$term; }
    $participantWhere.=')';
}
$filteredTotal=$participantSearch===''?$participantTotal:count_rows('SELECT COUNT(*)'.$participantWhere,$participantParams);
$pages=max(1,(int)ceil($filteredTotal/COURSE_STUDENT_PAGE));
$participantPage=min($pages,filter_var($_GET['participant_page']??'1',FILTER_VALIDATE_INT,['options'=>['min_range'=>1]])?:1);
$columns='u.id,u.name,u.first_names,u.last_names'.($canManage?',COALESCE(u.username,u.email) AS username,e.enrolled_at':'');
$participants=all('SELECT '.$columns.$participantWhere.' ORDER BY u.name,u.id LIMIT '.COURSE_STUDENT_PAGE.' OFFSET '.(($participantPage-1)*COURSE_STUDENT_PAGE),$participantParams);
$participantUrl=$courseUrl.'&tab=participants&participant_q='.rawurlencode($participantSearch);
?>
<h2>Participantes <span class="tag"><?=h($participantTotal)?> matriculados</span></h2>
<div class="ve-participant-person ve-participant-owner"><?php if($teacher) profile_preview_avatar($teacher,'ve-person-avatar',(int)$c['id']); ?><span>Responsable: <?=h($teacher['name']??'Sin definir')?></span></div>
<form method="get" class="ve-participant-search" role="search" aria-label="Buscar participantes">
  <input type="hidden" name="course" value="<?=h($c['id'])?>"><input type="hidden" name="tab" value="participants">
  <label>Buscar participante<input type="search" name="participant_q" value="<?=h($participantSearch)?>" maxlength="150" placeholder="<?=$canManage?'Nombre o usuario':'Nombre'?>"></label><button type="submit">Buscar</button><?php if($participantSearch!==''):?><a class="btn ve-quiet" href="<?=h($courseUrl.'&tab=participants')?>">Limpiar</a><?php endif;?>
</form>
<?php if($participantSearch!==''):?><p class="muted"><?=h($filteredTotal)?> coincidencia(s).</p><?php endif;?>
<?php if (!$participants): ?><div class="ve-course-empty"><strong><?=$participantSearch!==''?'No se encontraron participantes.':'Aún no hay estudiantes matriculados.'?></strong></div>
<?php else: ?><div class="ve-table ve-participants-table" tabindex="0" aria-label="Participantes matriculados"><table><thead><tr><th>Nombre</th><?php if ($canManage):?><th>Usuario</th><th>Fecha de matrícula</th><?php endif;?></tr></thead><tbody>
<?php foreach ($participants as $participant):?><tr><td><div class="ve-participant-person"><?php profile_preview_avatar($participant,'ve-person-avatar',(int)$c['id'],'member'); ?><span><?=h($participant['name'])?></span></div></td><?php if ($canManage):?><td><?=h($participant['username'])?></td><td><?=h($participant['enrolled_at'])?></td><?php endif;?></tr><?php endforeach;?>
</tbody></table></div>
<?php if ($pages>1):?><nav class="ve-participant-pages" aria-label="Páginas de participantes"><?php if ($participantPage>1):?><a class="btn" href="<?=h($participantUrl.'&participant_page='.($participantPage-1))?>">Anterior</a><?php endif;?><span>Página <?=$participantPage?> de <?=$pages?></span><?php if ($participantPage<$pages):?><a class="btn" href="<?=h($participantUrl.'&participant_page='.($participantPage+1))?>">Siguiente</a><?php endif;?></nav><?php endif;?>
<?php endif;?>
