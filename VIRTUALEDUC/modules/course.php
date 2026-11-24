<?php
declare(strict_types=1);
if (!defined('VE_VERSION')) { http_response_code(404); exit; }
?>
<a class="btn" href="?page=courses">← Cursos</a><section style="margin-top:16px"><h1><?=h($c['title'])?></h1><p><?=nl2br(h($c['description']))?></p>
<?php if($u['role']!=='student'):?><form method="post"><?php action('publish',(int)$c['id']);?><button><?=$c['published']?'Ocultar curso':'Publicar curso'?></button></form><div class="ve-section-head" style="margin-top:18px"><?php creation_dialog($u,'lesson','',(int)$c['id']); if(is_manager($u)) creation_dialog($u,'enroll','',(int)$c['id']); ?></div>
<?php else: $total=count($lessons);$completed=count(array_intersect(array_column($lessons,'id'),$done));?><p>Progreso: <?=$completed?> de <?=$total?> lecciones</p><progress value="<?=$completed?>" max="<?=max(1,$total)?>"></progress><?php endif;?></section>
<?php foreach($lessons as $l):?><article><h2><?=h($l['title'])?></h2><p class="lesson"><?=h($l['content'])?></p><?php if($u['role']==='student'):if(in_array($l['id'],$done)):?><span class="tag">Completada</span><?php else:?><form method="post"><?php action('complete',(int)$c['id']);?><input type="hidden" name="lesson_id" value="<?=h($l['id'])?>"><button>Marcar como completada</button></form><?php endif;endif;?></article><?php endforeach;?>
