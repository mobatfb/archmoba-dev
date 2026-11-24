<?php
declare(strict_types=1);

if (!defined('VE_VERSION')) { http_response_code(404); exit; }

function navigation_sections(array $u): array {
    $sections=['Inicio'=>['home'=>'Panel principal']];
    if ($u['role']==='student') $sections['Aprendizaje']=['courses'=>'Mis capacitaciones','progress'=>'Mi progreso','certificates'=>'Mis certificados'];
    else {
        $sections['Capacitaciones']=['courses'=>$u['role']==='teacher'?'Mis cursos':'Todos los cursos'];
        if ($u['role']==='teacher') $sections['Capacitaciones']['certificates']='Mis certificados';
        if (is_manager($u)) $sections['Capacitaciones']['enrollments']='Matrículas';
    }
    if (is_manager($u)) $sections['Administración']=['users'=>'Usuarios'];
    if ($u['role']==='admin') $sections['Configuración']=['institution'=>'Configuración institucional'];
    $sections['Mi cuenta']=['account'=>'Perfil y contraseña'];
    return $sections;
}

function allowed_pages(array $u): array {
    $pages=[];
    foreach (navigation_sections($u) as $items) $pages=array_merge($pages,array_keys($items));
    return $pages;
}

function render_navigation(array $u,string $page): void {
    require __DIR__.'/partials/sidebar.php';
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
    $modules=['home'=>'home.php','users'=>'users.php','courses'=>'courses.php','enrollments'=>'enrollments.php','progress'=>'progress.php','account'=>'account.php','institution'=>'institution_settings.php','certificates'=>'certificates.php'];
    if (!isset($modules[$page]) || !in_array($page,allowed_pages($u),true)) { http_response_code(403); exit('Sección no autorizada.'); }
    require __DIR__.'/modules/'.$modules[$page];
}
