<?php
declare(strict_types=1);
if (!defined('VE_VERSION')) { http_response_code(404); exit; }
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
        if ($page==='create_user'||in_array($page,['users_admin','users_subadmin','users_teacher','users_student'],true)) $page='users';
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
