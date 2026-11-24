<?php
declare(strict_types=1);
if (!defined('VE_VERSION')) { http_response_code(404); exit; }
require_role($u,'admin');
?>
<dialog class="ve-dialog" id="repair-user-role-dialog" aria-labelledby="repair-user-role-title">
  <div class="ve-dialog-head"><h2 id="repair-user-role-title">Asignar rol</h2><button type="button" class="ve-quiet" data-ve-close aria-label="Cerrar">×</button></div>
  <p>Usuario: <strong data-ve-repair-name></strong></p>
  <p class="muted">Esta cuenta no tiene un rol válido. Selecciona el rol que le corresponde.</p>
  <form method="post">
    <?php action('repair_user_role'); ?>
    <input type="hidden" name="user_id" value="">
    <label>Rol<select name="repair_role" required><option value="">Seleccionar rol</option><?php foreach(creatable_roles($u) as $r):?><option value="<?=h($r)?>"><?=h(role_label($r))?></option><?php endforeach;?></select></label>
    <div class="ve-dialog-actions"><button type="button" class="ve-quiet" data-ve-close>Cancelar</button><button type="submit">Guardar rol</button></div>
  </form>
</dialog>
