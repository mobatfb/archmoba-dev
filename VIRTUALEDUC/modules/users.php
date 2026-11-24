<?php
declare(strict_types=1);
if (!defined('VE_VERSION')) { http_response_code(404); exit; }
require_role($u,'admin','subadmin');
$labels=['admin'=>'Administradores','subadmin'=>'Subadministradores','teacher'=>'Docentes','student'=>'Estudiantes'];
$roles=array_values(array_intersect(['student','teacher','subadmin','admin'],creatable_roles($u)));
$counts=array_count_values(array_column($users,'role'));
$search=is_string($_GET['q']??null)?trim($_GET['q']):'';
if (strlen($search)>300 || !preg_match('//u',$search)) $search='';
$selected=is_string($_GET['role']??null)&&in_array($_GET['role'],$roles,true)?$_GET['role']:'';
// Keep the fallback search case- and accent-insensitive for Spanish names.
$fold=static fn(string $s):string=>strtr($s,['á'=>'a','é'=>'e','í'=>'i','ó'=>'o','ú'=>'u','ü'=>'u','ñ'=>'n','Á'=>'A','É'=>'E','Í'=>'I','Ó'=>'O','Ú'=>'U','Ü'=>'U','Ñ'=>'N']);
$matches=static function(array $x) use($search,$selected,$fold):bool {
    return ($selected===''||$x['role']===$selected)&&($search===''||preg_match('/'.preg_quote($fold($search),'/').'/iu',$fold($x['username'].' '.$x['first_names'].' '.$x['last_names'].' '.$x['email']))===1);
};
$visible=count(array_filter($users,$matches));
$editId=filter_var($_GET['edit']??0,FILTER_VALIDATE_INT,['options'=>['min_range'=>1]]);
$editing=null;
if($editId) foreach($users as $x) if((int)$x['id']===$editId && in_array($x['role'],$roles,true)) { $editing=$x; break; }
?>
<style>
.ve-users-filters{display:flex;align-items:end;gap:12px;flex-wrap:wrap;margin-bottom:8px}
.ve-users-filters label{min-width:0;margin:0;font-size:13px;color:#334b64}
.ve-users-search{flex:2 1 240px}.ve-users-role{flex:1 1 180px}
.ve-users-filters input,.ve-users-filters select{margin:5px 0 0;min-height:42px}
.ve-users-clear{display:inline-flex;align-items:center;justify-content:center;min-height:42px;padding:8px 14px;border:1px solid #c5d1df;border-radius:8px;background:#fff;color:#10294d;text-decoration:none;font-weight:600}
.ve-users-clear:hover{background:#eaf0f8;color:#10294d}.ve-users-clear:focus-visible{outline:2px solid #1655a8;outline-offset:2px}
.ve-users .ve-user-summary{gap:0;white-space:nowrap}.ve-users .ve-user-summary>span{flex:none;padding:0 12px;border-right:1px solid #cbd5e1}.ve-users .ve-user-summary>span:first-child{padding-left:0}.ve-users .ve-user-summary>span:last-child{border-right:0;padding-right:0;font-weight:600}
.ve-users-results{font-size:13px;margin:8px 0 12px}.ve-users [hidden]{display:none!important}
@media(max-width:480px){.ve-users-filters{gap:10px}.ve-users-search{flex:1 1 100%}.ve-users-role{flex:1 1 140px}.ve-users-clear{min-height:44px}}
</style>
<section class="ve-users" data-ve-users>
  <div class="ve-section-head ve-users-head"><h1>Usuarios</h1><?php creation_dialog($u,'user'); ?></div>
  <div class="ve-user-summary" tabindex="0" aria-label="Resumen de usuarios visibles">
    <?php foreach($roles as $r):?><span><?=h($labels[$r])?>: <strong><?=$counts[$r]??0?></strong></span><?php endforeach;?>
    <span>Total: <strong><?=count($users)?></strong></span>
  </div>
  <?php if($editing):?>
  <section class="ve-form"><h2>Editar identificación</h2><form method="post"><?php action('user_identity');?><input type="hidden" name="user_id" value="<?=h($editing['id'])?>"><label>Usuario<input name="usuario" required maxlength="190" value="<?=h($editing['username'])?>"></label><label>Nombres<input name="nombres" required maxlength="150" value="<?=h($editing['first_names'])?>"></label><label>Apellidos<input name="apellidos" required maxlength="150" value="<?=h($editing['last_names'])?>"></label><label>Correo<input name="correo" type="email" required maxlength="190" value="<?=h($editing['email'])?>"></label><button>Guardar cambios</button> <a class="ve-users-clear" href="?page=users">Cancelar</a></form></section>
  <?php endif;?>
  <form class="ve-users-filters" method="get" action="index.php" role="search" aria-label="Buscar usuarios">
    <input type="hidden" name="page" value="users">
    <label class="ve-users-search">Buscar usuario<input type="search" name="q" value="<?=h($search)?>" placeholder="Usuario, nombres, apellidos o correo..." maxlength="150" autocomplete="off"></label>
    <label class="ve-users-role">Filtrar por rol<select name="role"><option value="">Todos los roles</option><?php foreach($roles as $r):?><option value="<?=h($r)?>" <?=$selected===$r?'selected':''?>><?=h(role_label($r))?></option><?php endforeach;?></select></label>
    <a class="ve-users-clear" href="?page=users">Limpiar</a>
    <noscript><button type="submit">Buscar</button></noscript>
  </form>
  <p class="muted ve-users-results" role="status" aria-live="polite">Mostrando <strong data-ve-user-count><?=$visible?></strong> de <?=count($users)?> usuarios</p>
  <div class="ve-table" tabindex="0" aria-label="Tabla de usuarios"><table><thead><tr><th>Usuario</th><th>Nombres</th><th>Apellidos</th><th>Correo</th><th>Rol</th><th>Acción</th></tr></thead><tbody><?php foreach($users as $x):?><tr data-ve-user-role="<?=h($x['role'])?>" <?=$matches($x)?'':'hidden'?>><td><?=h($x['username'])?></td><td><?=h($x['first_names'])?></td><td><?=h($x['last_names'])?></td><td><?=h($x['email'])?></td><td><span class="tag"><?=h(role_label($x['role']))?></span></td><td><a href="?page=users&amp;edit=<?=h($x['id'])?>">Editar</a></td></tr><?php endforeach;?></tbody></table></div>
  <p class="muted" data-ve-users-empty <?=$visible?'hidden':''?>><?=$users?'No se encontraron usuarios con los filtros seleccionados.':'No hay usuarios registrados.'?></p>
</section>
<script src="modules/users.js?v=<?=h(VE_VERSION)?>" defer></script>
