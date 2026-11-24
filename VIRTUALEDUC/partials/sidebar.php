<?php
declare(strict_types=1);
if (!defined('VE_VERSION')) { http_response_code(404); exit; }
$settings=institution_settings();
?>
<aside class="ve-sidebar ve-institution-sidebar">
  <?php render_institution_brand($settings); ?>
  <details class="ve-menu" open>
    <summary class="ve-menu-title">Menú de navegación</summary>
    <div class="ve-menu-content">
      <div class="ve-period"><span>PERIODO ACTIVO</span><strong><?=h($settings['active_period']?:'Sin definir')?></strong></div>
      <nav aria-label="Navegación principal" class="ve-scroll-nav">
        <?php foreach(navigation_sections($u) as $section=>$items): ?>
          <details class="ve-group" open>
            <summary><?=h($section)?></summary>
            <?php foreach($items as $key=>$label): ?>
              <a href="?page=<?=h($key)?>" <?=$page===$key?'class="ve-active" aria-current="page"':''?>><?=h($label)?></a>
            <?php endforeach; ?>
          </details>
        <?php endforeach; ?>
      </nav>
      <div class="ve-sidebar-user">
        <a href="?page=account" class="ve-profile-link" data-ve-profile-open aria-label="Abrir mi perfil" aria-haspopup="dialog" aria-controls="ve-profile-dialog">
          <?php profile_avatar($u,'ve-user-avatar'); ?>
          <div class="ve-user-ident"><strong title="<?=h($u['name'])?>"><?=h($u['name'])?></strong><small><?=h(role_label($u['role']))?></small></div>
        </a>
        <form method="post"><?php action('logout');?><button type="submit" class="ve-exit">Salir</button></form>
      </div>
    </div>
  </details>
</aside>
