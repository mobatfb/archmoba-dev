<?php
declare(strict_types=1);
if (!defined('VE_VERSION')) { http_response_code(404); exit; }
?>
<?php require_role($u,'admin','subadmin');
$labels=['admin'=>'Administradores','subadmin'=>'Subadministradores','teacher'=>'Docentes','student'=>'Estudiantes'];
$counts=array_count_values(array_column($users,'role')); ?>
<section class="ve-users">
  <div class="ve-section-head ve-users-head"><h1>Usuarios</h1><?php creation_dialog($u,'user'); ?></div>
  <div class="ve-user-summary" tabindex="0" aria-label="Resumen de usuarios visibles">
    <span>Total: <strong><?=count($users)?></strong></span>
    <?php foreach(creatable_roles($u) as $r):?><span><?=h($labels[$r])?>: <strong><?=$counts[$r]??0?></strong></span><?php endforeach;?>
  </div>
  <div class="ve-table" tabindex="0" aria-label="Tabla de usuarios"><table><thead><tr><th>Nombre</th><th>Correo</th><th>Rol</th></tr></thead><tbody><?php foreach($users as $x):?><tr><td><?=h($x['name'])?></td><td><?=h($x['email'])?></td><td><span class="tag"><?=h(role_label($x['role']))?></span></td></tr><?php endforeach;?></tbody></table></div>
  <?php if(!$users):?><p class="muted">No hay usuarios registrados.</p><?php endif;?>
</section>
