<?php
declare(strict_types=1);
if (!defined('VE_VERSION')) { http_response_code(404); exit; }
require_role($u,'admin','subadmin');
?>
<dialog class="ve-dialog ve-user-edit" id="edit-user-dialog" data-ve-actor-id="<?=h($u['id'])?>" aria-labelledby="edit-user-title">
  <div class="ve-dialog-head"><h2 id="edit-user-title">Editar usuario</h2><button type="button" class="ve-quiet" data-ve-close aria-label="Cerrar">×</button></div>
  <p class="muted">Actualiza la identificación y el rol del usuario seleccionado.</p>
  <form method="post">
    <?php action('user_identity'); ?>
    <input type="hidden" name="user_id" value="">
    <label>Usuario<input name="usuario" required maxlength="190" autocomplete="off"></label>
    <label>Nombres<input name="nombres" required maxlength="150"></label>
    <label>Apellidos<input name="apellidos" required maxlength="150"></label>
    <label>Correo electrónico<input type="email" name="correo" required maxlength="190"></label>
    <label>Rol<select name="rol" required><?php foreach(creatable_roles($u) as $r):?><option value="<?=h($r)?>"><?=h(role_label($r))?></option><?php endforeach;?></select></label>
    <p class="muted" data-ve-own-role hidden>No puedes cambiar tu propio rol.</p>
    <div class="ve-dialog-actions"><button type="button" class="ve-quiet" data-ve-close>Cancelar</button><button type="submit">Guardar cambios</button></div>
  </form>
</dialog>
