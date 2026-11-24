<?php
declare(strict_types=1);
require __DIR__.'/app.php';
require __DIR__.'/panel.php';
require __DIR__.'/create.php';
try {
    $installed = count_rows('SELECT COUNT(*) FROM ve_users WHERE role=?',['admin']) > 0;
    $u = current_user();
    if (isset($_GET['template'])) {
        try { creation_template($u); } catch (DomainException $e) { http_response_code(403); exit(h($e->getMessage())); }
    }
    if ($_SERVER['REQUEST_METHOD']==='POST') {
        verify_csrf();
        $action = field('action',40);
        try {
            if ($action==='create') { handle_creation($u); }
            elseif ($action==='login') {
                if (!$installed) throw new DomainException('Primero importa el archivo SQL del administrador en phpMyAdmin.');
                $email=strtolower(field('email',190));
                if ($email==='admin') $email='admin@virtualeduc.local';
                $p=$_POST['password'] ?? '';
                $row=one('SELECT * FROM ve_users WHERE email=?',[$email]);
                if (!$row || !is_string($p) || !password_verify($p,$row['password_hash'])) { usleep(500000); throw new DomainException('Credenciales incorrectas.'); }
                session_regenerate_id(true);
                $_SESSION['user_id']=$row['id']; unset($_SESSION['csrf']);
            } elseif ($action==='password') {
                require_role($u,'admin','subadmin','teacher','student');
                $old=$_POST['old_password'] ?? ''; $new=$_POST['new_password'] ?? ''; $confirm=$_POST['confirm_password'] ?? '';
                $row=one('SELECT password_hash FROM ve_users WHERE id=?',[$u['id']]);
                if (!is_string($old) || !$row || !password_verify($old,$row['password_hash'])) throw new DomainException('La contraseña actual no es correcta.');
                if (!is_string($new) || strlen($new)<12 || strlen($new)>72 || $new!==$confirm || $new===$old) throw new DomainException('Usa una contraseña nueva de 12 a 72 bytes y confirma que coincida.');
                query('UPDATE ve_users SET password_hash=? WHERE id=?',[password_hash($new,PASSWORD_DEFAULT),$u['id']]);
                session_regenerate_id(true); flash('Contraseña actualizada.'); go('page=account');
            } elseif ($action==='logout') {
                $_SESSION=[]; session_destroy(); go();
            } elseif (in_array($action,['publish','complete'],true)) {
                $id=id_field('course_id');
                if (!$u || !($c=course_for($id,$u))) { http_response_code(403); exit('Acceso denegado'); }
                if ($action==='complete') {
                    require_role($u,'student'); $lesson=id_field('lesson_id');
                    if (!one('SELECT id FROM ve_lessons WHERE id=? AND course_id=?',[$lesson,$id])) throw new DomainException('Lección inválida.');
                    query('INSERT INTO ve_progress(lesson_id,student_id) VALUES(?,?) ON DUPLICATE KEY UPDATE completed_at=completed_at',[$lesson,$u['id']]);
                } elseif ($action==='publish') {
                    require_role($u,'admin','subadmin','teacher');
                    query('UPDATE ve_courses SET published=1-published WHERE id=?',[$id]);
                }
                flash('Cambios guardados.'); go('course='.$id);
            } else throw new DomainException('Acción inválida.');
        } catch (DomainException $e) { flash($e->getMessage(),'error'); }
        go();
    }
    $courses=[]; $users=[]; $c=null; $lessons=[]; $done=[]; $page='home';
    if ($u) {
        if (is_manager($u)) { $courses=all('SELECT * FROM ve_courses ORDER BY id DESC'); $users=$u['role']==='admin'?all('SELECT id,name,email,role FROM ve_users ORDER BY name'):all("SELECT id,name,email,role FROM ve_users WHERE role IN ('teacher','student') ORDER BY name"); }
        elseif ($u['role']==='teacher') $courses=all('SELECT * FROM ve_courses WHERE teacher_id=? ORDER BY id DESC',[$u['id']]);
        else $courses=all('SELECT c.* FROM ve_courses c JOIN ve_enrollments e ON e.course_id=c.id WHERE e.student_id=? AND c.published=1 ORDER BY c.id DESC',[$u['id']]);
        require_role($u,'admin','subadmin','teacher','student');
        $page=is_string($_GET['page'] ?? null)?$_GET['page']:'home';
        if ($page==='create_user') $page='users';
        if ($page==='create_course') $page='courses';
        if (isset($_GET['course'])) $page='courses';
        if (!in_array($page,allowed_pages($u),true)) { http_response_code(403); exit('Sección no autorizada.'); }
        if (isset($_GET['course'])) {
            $c=course_for((int)$_GET['course'],$u);
            if (!$c) {http_response_code(404); exit('Curso no disponible.');}
            $lessons=all('SELECT * FROM ve_lessons WHERE course_id=? ORDER BY sort_order,id',[$c['id']]);
            if ($u['role']==='student') $done=array_column(all('SELECT lesson_id FROM ve_progress WHERE student_id=?',[$u['id']]),'lesson_id');
        }
    }
} catch (Throwable $e) { error_log($e->getMessage()); http_response_code(503); exit('VIRTUALEDUC: verifica config.local.php y la instalación de schema.sql.'); }
function action(string $a, ?int $id=null): void { csrf_field(); echo '<input type="hidden" name="action" value="'.h($a).'">'; if($id!==null) echo '<input type="hidden" name="course_id" value="'.$id.'">'; }
?>
<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>VIRTUALEDUC</title><style>
*{box-sizing:border-box}body{margin:0;background:#f1f5f9;color:#17253b;font:15px system-ui,sans-serif}header{background:#10294d;color:white;padding:20px 6%;display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}header a{color:white;text-decoration:none;font-size:23px;font-weight:800;letter-spacing:2px}main{max-width:1160px;margin:auto;padding:26px 18px}section,article{background:white;border:1px solid #dce5ef;border-radius:14px;padding:22px;margin-bottom:18px}h1,h2,h3{margin-top:0}p{line-height:1.65}input,textarea,select{width:100%;padding:11px;border:1px solid #c5d1df;border-radius:8px;margin:5px 0 12px;font:inherit}textarea{min-height:90px}button,.btn{display:inline-block;background:#1655a8;color:white;border:0;padding:10px 15px;border-radius:8px;cursor:pointer;text-decoration:none;font:inherit}button:hover,.btn:hover{background:#103d7d}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,260px),1fr));gap:16px}.hero{background:linear-gradient(125deg,#10294d,#1655a8);color:white;padding:32px}.muted{color:#607187}.notice{padding:14px;background:#e0f2e9;border-radius:8px;margin-bottom:18px}.error{background:#fee2e2}.auth{max-width:480px;margin:40px auto}.tag{font-size:12px;background:#e5edf7;padding:5px 10px;border-radius:30px}progress{width:100%;height:18px}footer{text-align:center;color:#607187;padding:22px}label{display:block;font-weight:600}details{margin:12px 0}summary{cursor:pointer;font-weight:600}.lesson{white-space:pre-wrap;overflow-wrap:anywhere}header form{margin:0}
</style><?php panel_styles(); creation_styles(); ?><script src="create.js" defer></script></head><body><header><a href="index.php">VIRTUALEDUC</a><?php if($u): ?><span><?=h($u['name'])?> · <?=h(role_label($u['role']))?></span><form method="post"><?php action('logout');?><button>Salir</button></form><?php endif;?></header><?php if($u): ?><div class="ve-shell"><?php render_navigation($u,$page); ?><?php endif; ?><main>
<?php if(isset($_SESSION['flash'])): $f=$_SESSION['flash'];unset($_SESSION['flash']);?><div class="notice <?=h($f[1])?>"><?=h($f[0])?></div><?php endif;?>
<?php if(!$u): ?><section class="auth"><h1><?=$installed?'Iniciar sesión':'Instalación pendiente'?></h1><p class="muted">Tu espacio de aprendizaje en línea.</p><?php if($installed):?><form method="post"><?php action('login');?><label>Usuario o correo electrónico<input type="text" name="email" required autocomplete="username"></label><label>Contraseña<input type="password" name="password" required autocomplete="current-password"></label><button>Ingresar</button></form><?php else:?><p>Importa el SQL de creación del administrador en phpMyAdmin y vuelve a cargar esta página.</p><?php endif;?></section>
<?php elseif($c): ?><a class="btn" href="?page=courses">← Capacitaciones</a><section style="margin-top:16px"><h1><?=h($c['title'])?></h1><p><?=nl2br(h($c['description']))?></p>
<?php if($u['role']!=='student'):?><form method="post"><?php action('publish',(int)$c['id']);?><button><?=$c['published']?'Ocultar curso':'Publicar curso'?></button></form><div class="ve-section-head" style="margin-top:18px"><?php creation_dialog($u,'lesson','',(int)$c['id']); if(is_manager($u)) creation_dialog($u,'enroll','',(int)$c['id']); ?></div>
<?php else: $total=count($lessons);$completed=count(array_intersect(array_column($lessons,'id'),$done));?><p>Progreso: <?=$completed?> de <?=$total?> lecciones</p><progress value="<?=$completed?>" max="<?=max(1,$total)?>"></progress><?php endif;?></section>
<?php foreach($lessons as $l):?><article><h2><?=h($l['title'])?></h2><p class="lesson"><?=h($l['content'])?></p><?php if($u['role']==='student'):if(in_array($l['id'],$done)):?><span class="tag">Completada</span><?php else:?><form method="post"><?php action('complete',(int)$c['id']);?><input type="hidden" name="lesson_id" value="<?=h($l['id'])?>"><button>Marcar como completada</button></form><?php endif;endif;?></article><?php endforeach;?>
<?php else: render_panel($u,$page,$courses,$users); endif; ?>
</main><?php if($u): ?></div><?php endif; ?><footer>VIRTUALEDUC · v<?=h(VE_VERSION)?></footer></body></html>
