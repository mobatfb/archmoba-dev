<?php
declare(strict_types=1);
require __DIR__.'/app.php';
try {
    $installed = count_rows('SELECT COUNT(*) FROM ve_users WHERE role=?',['admin']) > 0;
    $u = current_user();
    if ($_SERVER['REQUEST_METHOD']==='POST') {
        verify_csrf();
        $action = field('action',40);
        try {
            if ($action==='login') {
                if (!$installed) throw new DomainException('Primero configura el administrador desde la terminal.');
                $email=strtolower(field('email',190));
                $p=$_POST['password'] ?? '';
                $row=one('SELECT * FROM ve_users WHERE email=?',[$email]);
                if (!$row || !is_string($p) || !password_verify($p,$row['password_hash'])) { usleep(500000); throw new DomainException('Credenciales incorrectas.'); }
                session_regenerate_id(true);
                $_SESSION['user_id']=$row['id']; unset($_SESSION['csrf']);
            } elseif ($action==='logout') {
                $_SESSION=[]; session_destroy(); go();
            } elseif ($action==='user') {
                require_role($u,'admin'); new_user(field('role',10)); flash('Usuario creado.');
            } elseif ($action==='course') {
                require_role($u,'admin','teacher');
                $teacher=$u['role']==='teacher'?(int)$u['id']:id_field('teacher_id');
                if (!one("SELECT id FROM ve_users WHERE id=? AND role IN ('admin','teacher')",[$teacher])) throw new DomainException('Docente inválido.');
                query('INSERT INTO ve_courses(title,description,teacher_id) VALUES(?,?,?)',[field('title',180),field('description',20000),$teacher]);
                flash('Curso creado.');
            } elseif (in_array($action,['lesson','publish','enroll','complete'],true)) {
                $id=id_field('course_id');
                if (!$u || !($c=course_for($id,$u))) { http_response_code(403); exit('Acceso denegado'); }
                if ($action==='complete') {
                    require_role($u,'student'); $lesson=id_field('lesson_id');
                    if (!one('SELECT id FROM ve_lessons WHERE id=? AND course_id=?',[$lesson,$id])) throw new DomainException('Lección inválida.');
                    query('INSERT INTO ve_progress(lesson_id,student_id) VALUES(?,?) ON DUPLICATE KEY UPDATE completed_at=completed_at',[$lesson,$u['id']]);
                } elseif ($action==='lesson') {
                    require_role($u,'admin','teacher');
                    query('INSERT INTO ve_lessons(course_id,title,content,sort_order) VALUES(?,?,?,?)',[$id,field('title',180),field('content',60000),count_rows('SELECT COUNT(*) FROM ve_lessons WHERE course_id=?',[$id])+1]);
                } elseif ($action==='publish') {
                    require_role($u,'admin','teacher');
                    query('UPDATE ve_courses SET published=1-published WHERE id=?',[$id]);
                } else {
                    require_role($u,'admin'); $student=id_field('student_id');
                    if (!one("SELECT id FROM ve_users WHERE id=? AND role='student'",[$student])) throw new DomainException('Estudiante inválido.');
                    query('INSERT INTO ve_enrollments(course_id,student_id) VALUES(?,?) ON DUPLICATE KEY UPDATE enrolled_at=enrolled_at',[$id,$student]);
                }
                flash('Cambios guardados.'); go('course='.$id);
            } else throw new DomainException('Acción inválida.');
        } catch (DomainException $e) { flash($e->getMessage(),'error'); }
        go();
    }
    $courses=[]; $users=[]; $c=null; $lessons=[]; $done=[];
    if ($u) {
        if ($u['role']==='admin') { $courses=all('SELECT * FROM ve_courses ORDER BY id DESC'); $users=all('SELECT id,name,email,role FROM ve_users ORDER BY name'); }
        elseif ($u['role']==='teacher') $courses=all('SELECT * FROM ve_courses WHERE teacher_id=? ORDER BY id DESC',[$u['id']]);
        else $courses=all('SELECT c.* FROM ve_courses c JOIN ve_enrollments e ON e.course_id=c.id WHERE e.student_id=? AND c.published=1 ORDER BY c.id DESC',[$u['id']]);
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
</style></head><body><header><a href="index.php">VIRTUALEDUC</a><?php if($u): ?><span><?=h($u['name'])?> · <?=h(role_label($u['role']))?></span><form method="post"><?php action('logout');?><button>Salir</button></form><?php endif;?></header><main>
<?php if(isset($_SESSION['flash'])): $f=$_SESSION['flash'];unset($_SESSION['flash']);?><div class="notice <?=h($f[1])?>"><?=h($f[0])?></div><?php endif;?>
<?php if(!$u): ?><section class="auth"><h1><?=$installed?'Iniciar sesión':'Instalación pendiente'?></h1><p class="muted">Tu espacio de aprendizaje en línea.</p><?php if($installed):?><form method="post"><?php action('login');?><label>Correo electrónico<input type="email" name="email" required></label><label>Contraseña<input type="password" name="password" required autocomplete="current-password"></label><button>Ingresar</button></form><?php else:?><p>El administrador inicial debe crearse desde la terminal del servidor ejecutando <code>php install.php</code>. Si no tienes terminal, consulta la opción de phpMyAdmin en el README.</p><?php endif;?></section>
<?php elseif($c): ?><a class="btn" href="index.php">← Mis cursos</a><section style="margin-top:16px"><h1><?=h($c['title'])?></h1><p><?=nl2br(h($c['description']))?></p>
<?php if($u['role']!=='student'):?><form method="post"><?php action('publish',(int)$c['id']);?><button><?=$c['published']?'Ocultar curso':'Publicar curso'?></button></form><details><summary>Añadir lección</summary><form method="post"><?php action('lesson',(int)$c['id']);?><label>Título<input name="title" required maxlength="180"></label><label>Contenido de texto<textarea name="content" required></textarea></label><button>Guardar lección</button></form></details>
<?php if($u['role']==='admin'):?><details><summary>Matricular estudiante</summary><form method="post"><?php action('enroll',(int)$c['id']);?><select name="student_id" required><option value="">Seleccionar estudiante</option><?php foreach($users as $x):if($x['role']==='student'):?><option value="<?=h($x['id'])?>"><?=h($x['name'])?></option><?php endif;endforeach;?></select><button>Matricular</button></form></details><?php endif;?>
<?php else: $total=count($lessons);$completed=count(array_intersect(array_column($lessons,'id'),$done));?><p>Progreso: <?=$completed?> de <?=$total?> lecciones</p><progress value="<?=$completed?>" max="<?=max(1,$total)?>"></progress><?php endif;?></section>
<?php foreach($lessons as $l):?><article><h2><?=h($l['title'])?></h2><p class="lesson"><?=h($l['content'])?></p><?php if($u['role']==='student'):if(in_array($l['id'],$done)):?><span class="tag">Completada</span><?php else:?><form method="post"><?php action('complete',(int)$c['id']);?><input type="hidden" name="lesson_id" value="<?=h($l['id'])?>"><button>Marcar como completada</button></form><?php endif;endif;?></article><?php endforeach;?>
<?php else:?><section class="hero"><h1>Hola, <?=h($u['name'])?></h1><p>Bienvenido a tu campus virtual.</p><strong><?=count($courses)?> cursos disponibles en tu panel</strong></section>
<?php if($u['role']==='admin'):?><section><h2>Administración de usuarios</h2><details><summary>Crear usuario</summary><form method="post"><?php action('user');?><label>Nombre<input name="name" required></label><label>Correo<input type="email" name="email" required></label><label>Contraseña (mínimo 12 caracteres)<input type="password" name="password" required minlength="12"></label><label>Rol<select name="role"><option value="student">Estudiante</option><option value="teacher">Docente</option><option value="admin">Administrador</option></select></label><button>Crear usuario</button></form></details><details><summary>Usuarios registrados (<?=count($users)?>)</summary><?php foreach($users as $x):?><p><?=h($x['name'])?> · <?=h($x['email'])?> · <?=h(role_label($x['role']))?></p><?php endforeach;?></details></section><?php endif;?>
<?php if($u['role']!=='student'):?><section><details><summary>Crear capacitación</summary><form method="post"><?php action('course');?><label>Título<input name="title" required maxlength="180"></label><label>Descripción<textarea name="description" required></textarea></label><?php if($u['role']==='admin'):?><label>Responsable<select name="teacher_id"><?php foreach($users as $x):if($x['role']!=='student'):?><option value="<?=h($x['id'])?>"><?=h($x['name'])?></option><?php endif;endforeach;?></select></label><?php endif;?><button>Crear curso</button></form></details></section><?php endif;?>
<h2>Mis capacitaciones</h2><div class="grid"><?php foreach($courses as $x):?><article><span class="tag"><?=$x['published']?'Publicado':'Borrador'?></span><h3 style="margin-top:12px"><?=h($x['title'])?></h3><p><?=h($x['description'])?></p><a class="btn" href="?course=<?=h($x['id'])?>">Abrir curso</a></article><?php endforeach;?></div><?php if(!$courses):?><p class="muted">Todavía no hay cursos disponibles.</p><?php endif;endif;?>
</main><footer>VIRTUALEDUC · v<?=h(VE_VERSION)?></footer></body></html>
