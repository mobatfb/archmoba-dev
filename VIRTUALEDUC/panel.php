<?php
declare(strict_types=1);

if (!defined('VE_VERSION')) { http_response_code(404); exit; }

function navigation_sections(array $u): array {
    $sections=['Inicio'=>['home'=>'Panel principal']];
    if (is_manager($u)) {
        $sections['Administración']=['users'=>'Todos los usuarios'];
        foreach(creatable_roles($u) as $role) $sections['Administración']['users_'.$role]=['admin'=>'Administradores','subadmin'=>'Subadministradores','teacher'=>'Docentes','student'=>'Estudiantes'][$role];
    }
    if ($u['role']==='student') $sections['Aprendizaje']=['courses'=>'Mis capacitaciones','progress'=>'Mi progreso'];
    else {
        $sections['Capacitaciones']=['courses'=>$u['role']==='teacher'?'Mis cursos':'Todos los cursos'];
        if (is_manager($u)) $sections['Capacitaciones']['enrollments']='Matrículas';
    }
    $sections['Mi cuenta']=['account'=>'Perfil y contraseña'];
    return $sections;
}

function allowed_pages(array $u): array {
    $pages=[];
    foreach (navigation_sections($u) as $items) $pages=array_merge($pages,array_keys($items));
    return $pages;
}

function render_navigation(array $u,string $page): void {
    $icons=['Inicio'=>'⌂','Administración'=>'♙','Capacitaciones'=>'▤','Aprendizaje'=>'▤','Mi cuenta'=>'⚙'];
    ?>
    <aside class="ve-sidebar">
      <details class="ve-menu" open>
        <summary class="ve-menu-title">Menú de navegación</summary>
        <div class="ve-person"><strong><?=h($u['name'])?></strong><small><?=h(role_label($u['role']))?></small></div>
        <nav aria-label="Navegación principal">
        <?php foreach(navigation_sections($u) as $section=>$items): ?>
          <details class="ve-group" <?=array_key_exists($page,$items)?'open':''?>>
            <summary><span aria-hidden="true"><?=h($icons[$section] ?? '•')?></span><?=h($section)?></summary>
            <?php foreach($items as $key=>$label): ?>
              <a href="?page=<?=h($key)?>" <?=$page===$key?'class="ve-active" aria-current="page"':''?>><?=h($label)?></a>
            <?php endforeach;?>
          </details>
        <?php endforeach;?>
        </nav>
        <form class="ve-signout" method="post"><?php action('logout');?><button>Salir de la cuenta</button></form>
      </details>
    </aside>
    <?php
}

function panel_styles(): void { ?>
<style>
.ve-shell{display:grid;grid-template-columns:252px minmax(0,1fr);min-height:calc(100vh - 143px)}.ve-shell main{width:100%;max-width:1350px;margin:0 auto;padding:30px 28px;min-width:0}
.ve-sidebar{background:#10294d;color:#d8e5f6;padding:18px 12px}.ve-menu{margin:0;position:sticky;top:18px}.ve-menu-title{font-size:13px;font-weight:700;color:#a9bfd9;padding:12px 10px;letter-spacing:.3px}
.ve-person{padding:14px 12px;margin:6px 0 14px;background:#1a385e;border:1px solid #345173;border-radius:10px;overflow-wrap:anywhere}.ve-person strong,.ve-person small{display:block}.ve-person small{margin-top:5px;color:#bcd3ec}
.ve-group{margin:6px 0;border-bottom:1px solid #294665;padding:0 0 5px}.ve-group summary{list-style:none;display:flex;align-items:center;gap:10px;padding:12px 10px;border-radius:8px;color:#e4edf8;font-size:14px}.ve-group summary::-webkit-details-marker{display:none}.ve-group summary::after{content:"›";margin-left:auto;font-size:20px}.ve-group[open] summary::after{transform:rotate(90deg)}.ve-group summary:hover{background:#254568}
.ve-group a{display:block;color:#bcd3ec;text-decoration:none;padding:10px 12px 10px 36px;border-radius:8px;font-size:14px}.ve-group a:hover,.ve-group a.ve-active{background:#245b9d;color:#fff}.ve-signout{margin:24px 0 0}.ve-signout button{width:100%;background:#1b3c63;border:1px solid #426289}
.ve-stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:14px;margin-bottom:20px}.ve-stat{background:white;border:1px solid #dce5ef;border-radius:12px;padding:18px}.ve-stat strong{display:block;font-size:30px;color:#1655a8;margin-top:8px}.ve-table{overflow-x:auto}.ve-table table{width:100%;border-collapse:collapse}.ve-table th,.ve-table td{padding:12px 10px;text-align:left;border-bottom:1px solid #e2e8f0;overflow-wrap:anywhere}.ve-table th{background:#eff4fa;font-size:13px}.ve-form{max-width:680px}.ve-card-title{overflow-wrap:anywhere}.ve-course-text{overflow-wrap:anywhere}
@media(max-width:760px){.ve-shell{display:block}.ve-sidebar{padding:8px 14px}.ve-menu{position:static}.ve-shell main{padding:18px 14px}.ve-menu-title{padding:10px}.ve-person{margin:0 0 8px}.ve-group{margin:0}.ve-signout{margin:12px 0}.ve-stats{grid-template-columns:repeat(2,minmax(0,1fr))}header{padding:15px 18px}}
</style>
<?php }

function render_panel(array $u,string $page,array $courses,array $users): void {
    if ($page==='home') { ?>
      <section class="hero"><h1>Hola, <?=h($u['name'])?></h1><p>Bienvenido a tu campus virtual. Selecciona una sección del menú para comenzar.</p><span><?=h(role_label($u['role']))?></span></section>
      <div class="ve-stats"><div class="ve-stat">Capacitaciones<strong><?=count($courses)?></strong></div>
      <div class="ve-stat">Cursos publicados<strong><?=count(array_filter($courses,fn($c)=>(int)$c['published']===1))?></strong></div>
      <?php if(is_manager($u)):?><div class="ve-stat">Usuarios visibles<strong><?=count($users)?></strong></div><?php endif;?></div>
      <section><h2>Accesos rápidos</h2><div class="grid"><?php foreach(navigation_sections($u) as $items):foreach($items as $key=>$label):if($key!=='home'):?><a class="btn" href="?page=<?=h($key)?>"><?=h($label)?></a><?php endif;endforeach;endforeach;?></div></section>
    <?php } elseif ($page==='users'||str_starts_with($page,'users_')) { 
      $role=$page==='users'?'':substr($page,6); $visible=$role?array_values(array_filter($users,fn($x)=>$x['role']===$role)):$users; ?>
      <section><div class="ve-section-head"><h1><?=$role?h(['admin'=>'Administradores','subadmin'=>'Subadministradores','teacher'=>'Docentes','student'=>'Estudiantes'][$role]):'Usuarios registrados'?></h1><?php if($role) creation_dialog($u,'user',$role); ?></div>
      <?php if(!$role):?><div class="grid"><?php foreach(creatable_roles($u) as $r):?><article class="ve-role-card"><a href="?page=users_<?=h($r)?>"><?=h(role_label($r))?> · <?=count(array_filter($users,fn($x)=>$x['role']===$r))?></a><?php creation_dialog($u,'user',$r);?></article><?php endforeach;?></div><?php endif;?>
      <p class="muted"><?=count($visible)?> usuarios disponibles.</p><div class="ve-table"><table><thead><tr><th>Nombre</th><th>Correo</th><th>Rol</th></tr></thead><tbody><?php foreach($visible as $x):?><tr><td><?=h($x['name'])?></td><td><?=h($x['email'])?></td><td><span class="tag"><?=h(role_label($x['role']))?></span></td></tr><?php endforeach;?></tbody></table></div><?php if(!$visible):?><p class="muted">No hay usuarios registrados.</p><?php endif;?></section>
    <?php } elseif ($page==='courses') { ?>
      <div class="ve-section-head"><h1><?=$u['role']==='student'?'Mis capacitaciones':'Cursos disponibles'?></h1><?php if($u['role']!=='student') creation_dialog($u,'course'); ?></div>
      <div class="grid"><?php foreach($courses as $x):?><article><span class="tag"><?=$x['published']?'Publicado':'Borrador'?></span><h3 class="ve-card-title" style="margin-top:12px"><?=h($x['title'])?></h3><p class="ve-course-text"><?=h($x['description'])?></p><a class="btn" href="?course=<?=h($x['id'])?>">Abrir curso</a></article><?php endforeach;?></div><?php if(!$courses):?><p class="muted">Todavía no hay cursos disponibles.</p><?php endif;?>
    <?php } elseif ($page==='enrollments') { ?>
      <section><div class="ve-section-head"><h1>Matrículas</h1><?php creation_dialog($u,'enroll'); ?></div><p>Selecciona un curso para matricular estudiantes.</p><div class="ve-table"><table><thead><tr><th>ID</th><th>Curso</th><th>Estudiantes matriculados</th><th>Acción</th></tr></thead><tbody><?php foreach($courses as $x):?><tr><td><?=h($x['id'])?></td><td><?=h($x['title'])?></td><td><?=count_rows('SELECT COUNT(*) FROM ve_enrollments WHERE course_id=?',[$x['id']])?></td><td><a class="btn" href="?course=<?=h($x['id'])?>">Gestionar</a></td></tr><?php endforeach;?></tbody></table></div><?php if(!$courses):?><p class="muted">Crea un curso para comenzar.</p><?php endif;?></section>
    <?php } elseif ($page==='progress') { ?>
      <h1>Mi progreso académico</h1><div class="grid"><?php foreach($courses as $x):$total=count_rows('SELECT COUNT(*) FROM ve_lessons WHERE course_id=?',[$x['id']]);$completed=count_rows('SELECT COUNT(*) FROM ve_progress p JOIN ve_lessons l ON l.id=p.lesson_id WHERE l.course_id=? AND p.student_id=?',[$x['id'],$u['id']]);?><article><h2 class="ve-card-title"><?=h($x['title'])?></h2><p><?=$completed?> de <?=$total?> lecciones completadas</p><progress value="<?=$completed?>" max="<?=max(1,$total)?>"></progress><p><a class="btn" href="?course=<?=h($x['id'])?>">Continuar curso</a></p></article><?php endforeach;?></div><?php if(!$courses):?><p class="muted">Aún no tienes cursos publicados y matriculados.</p><?php endif;?>
    <?php } elseif ($page==='account') { ?>
      <section class="ve-form"><h1>Mi cuenta</h1><p><strong>Nombre:</strong> <?=h($u['name'])?></p><p><strong>Correo:</strong> <?=h($u['email'])?></p><p><strong>Rol:</strong> <?=h(role_label($u['role']))?></p><hr><h2>Cambiar mi contraseña</h2><form method="post"><?php action('password');?><label>Contraseña actual<input type="password" name="old_password" required autocomplete="current-password"></label><label>Nueva contraseña (mínimo 12 caracteres)<input type="password" name="new_password" required minlength="12" autocomplete="new-password"></label><label>Confirmar contraseña<input type="password" name="confirm_password" required minlength="12" autocomplete="new-password"></label><button>Actualizar contraseña</button></form></section>
    <?php }
}
