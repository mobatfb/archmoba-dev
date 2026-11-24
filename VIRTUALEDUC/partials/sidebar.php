<?php
declare(strict_types=1);
if (!defined('VE_VERSION')) { http_response_code(404); exit; }
$settings=institution_settings();
// Fixed SVG shapes; the icons are decorative and never depend on user input.
$navIcons=[
    'home'=>'<path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1z"/>',
    'learning'=>'<path d="m2 9 10-5 10 5-10 5zM6 11v6c4 3 8 3 12 0v-6M22 9v7"/>',
    'courses'=>'<path d="M12 5c-3-2-6-2-10-1v15c4-1 7-1 10 1 3-2 6-2 10-1V4c-4-1-7-1-10 1v15"/>',
    'progress'=>'<path d="M3 21h18"/><rect x="4" y="12" width="4" height="6" rx="1"/><rect x="10" y="8" width="4" height="10" rx="1"/><rect x="16" y="3" width="4" height="15" rx="1"/>',
    'certificates'=>'<circle cx="12" cy="9" r="6"/><path d="m8 14-2 8 6-3 6 3-2-8M10 9l1.5 1.5L14 8"/>',
    'users'=>'<circle cx="9" cy="7" r="3"/><path d="M3 21v-3a6 6 0 0 1 12 0v3M16 4a3 3 0 0 1 0 6M21 21v-3a5 5 0 0 0-4-5"/>',
    'enrollments'=>'<rect x="5" y="5" width="14" height="16" rx="2"/><rect x="9" y="3" width="6" height="4" rx="1"/><path d="M9 12h6m-6 4h6"/>',
    'institution'=>'<circle cx="12" cy="12" r="3"/><path d="m9 3-.6 2.3-2 .9L4 5l-2 3 1.8 1.6v4.8L2 16l2 3 2.4-1.2 2 .9L9 21h6l.6-2.3 2-.9L20 19l2-3-1.8-1.6V9.6L22 8l-2-3-2.4 1.2-2-.9L15 3z"/>',
    'account'=>'<circle cx="12" cy="7" r="4"/><path d="M4 21v-2a8 8 0 0 1 16 0v2z"/>',
    'logout'=>'<path d="M10 4H4v16h6M9 12h12m-4-4 4 4-4 4"/>'
];
$sectionIcons=['Inicio'=>'home','Aprendizaje'=>'learning','Cursos'=>'courses','Administración'=>'users','Configuración'=>'institution','Mi cuenta'=>'account'];
$navIcon=static function(string $key) use($navIcons): void {
    echo '<svg class="ve-nav-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">'.($navIcons[$key]??$navIcons['home']).'</svg>';
};
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
            <summary><?php $navIcon($sectionIcons[$section]??'home'); ?><span><?=h($section)?></span></summary>
            <?php foreach($items as $key=>$label): ?>
              <a href="?page=<?=h($key)?>" <?=$page===$key?'class="ve-active" aria-current="page"':''?>><?php $navIcon($key); ?><span><?=h($label)?></span></a>
            <?php endforeach; ?>
          </details>
        <?php endforeach; ?>
      </nav>
      <div class="ve-sidebar-user">
        <a href="?page=account" class="ve-profile-link" data-ve-profile-open aria-label="Abrir mi perfil" aria-haspopup="dialog" aria-controls="ve-profile-dialog">
          <?php profile_avatar($u,'ve-user-avatar'); ?>
          <div class="ve-user-ident"><strong title="<?=h($u['name'])?>"><?=h($u['name'])?></strong><small><?=h(role_label($u['role']))?></small></div>
        </a>
        <form method="post"><?php action('logout');?><button type="submit" class="ve-exit"><?php $navIcon('logout'); ?><span>Salir</span></button></form>
      </div>
    </div>
  </details>
</aside>
