<?php
declare(strict_types=1);
if (!defined('VE_VERSION')) { http_response_code(404); exit; }
try {
    $installed = count_rows('SELECT COUNT(*) FROM users WHERE role=?',['admin']) > 0;
    $u = current_user();
    if (isset($_GET['institution_logo'])) { serve_institution_logo(); }
    if ($u && !valid_user_role((string)$u['role'])) {
        unset($_SESSION['user_id']);
        session_regenerate_id(true);
        flash('Tu cuenta no tiene un rol válido. Solicita al administrador que lo asigne.','error');
        go();
    }
    if (isset($_GET['profile_photo'])) { serve_profile_photo($u); }
    if (isset($_GET['course_cover'])) { serve_course_cover($u); }
    if (isset($_GET['course_candidates'])) { serve_course_candidates($u); }
    if (isset($_GET['user_picker'])) { serve_user_picker($u); }
    if (isset($_GET['template'])) {
        try { creation_template($u); } catch (DomainException $e) { http_response_code(403); exit(h($e->getMessage())); }
    }
    if ($_SERVER['REQUEST_METHOD']==='POST') {
        verify_csrf();
        $action = field('action',40);
        try {
            if ($action==='profile_photo') {
                require_role($u,'admin','subadmin','teacher','student');
                try { save_profile_photo($u); flash(($_POST['photo_action']??'')==='remove'?'Foto eliminada.':'Foto de perfil actualizada.'); }
                catch (DomainException $e) { flash($e->getMessage(),'error'); }
                go('page=account');
            } elseif ($action==='institution_save') {
                require_role($u,'admin');
                try { save_institution(); flash('Configuración institucional actualizada.'); }
                catch (DomainException $e) { flash($e->getMessage(),'error'); }
                go('page=institution');
            } elseif ($action==='repair_user_role') {
                require_role($u,'admin');
                try { repair_user_role($u); flash('Rol asignado correctamente.'); }
                catch (DomainException $e) { flash($e->getMessage(),'error'); }
                go('page=users');
            } elseif ($action==='user_identity') {
                try { update_user_identity($u); flash('Datos del usuario actualizados.'); }
                catch (DomainException $e) { flash($e->getMessage(),'error'); }
                go('page=users');
            } elseif ($action==='course_enroll_many') {
                require_role($u,'admin','subadmin','teacher');
                $id=id_field('course_id');
                try {
                    $result=course_enroll_many($u,$id,$_POST['student_ids']??null);
                    flash($result['added'].' estudiante(s) matriculado(s).'.($result['existing']?' '.$result['existing'].' ya estaba(n) matriculado(s).':''));
                } catch(DomainException $e) { flash($e->getMessage(),'error'); }
                catch(Throwable $e) { error_log('VIRTUALEDUC enrollment failed: '.get_class($e)); flash('No se guardaron matrículas. Inténtalo nuevamente.','error'); }
                go('course='.$id.'&tab=participants');
            } elseif ($action==='course_edit') {
                require_role($u,'admin','subadmin','teacher');
                $id=id_field('course_id');
                $target=course_for($id,$u);
                if(!$target || !course_can_edit($u,$target)) { http_response_code(403); exit('Acceso denegado'); }
                try { course_edit_update($u,$id,$_POST); flash('Curso actualizado correctamente.'); }
                catch(DomainException $e) { flash($e->getMessage(),'error'); }
                catch(Throwable $e) { error_log('VIRTUALEDUC course edit failed: '.get_class($e)); flash('No se pudieron guardar los cambios del curso.','error'); }
                go('course='.$id);
            } elseif ($action==='create') { handle_creation($u); }
            elseif ($action==='login') {
                if (!$installed) throw new DomainException('Primero importa el archivo SQL del administrador en phpMyAdmin.');
                $identifier=field('email',190);
                $p=$_POST['password'] ?? '';
                $row=one('SELECT id,password_hash,role FROM users WHERE '.username_sql().'=?',[$identifier]);
                if(!$row && str_contains($identifier,'@')) $row=one('SELECT id,password_hash FROM users WHERE email=?',[$identifier]);
                if (!$row || !is_string($p) || !password_verify($p,$row['password_hash'])) { usleep(500000); throw new DomainException('Credenciales incorrectas.'); }
                if (!valid_user_role((string)$row['role'])) {
                    unset($_SESSION['user_id']);
                    session_regenerate_id(true);
                    throw new DomainException('Tu cuenta no tiene un rol válido. Solicita al administrador que lo asigne.');
                }
                session_regenerate_id(true);
                $_SESSION['user_id']=$row['id']; unset($_SESSION['csrf']);
            } elseif ($action==='password') {
                require_role($u,'admin','subadmin','teacher','student');
                $old=$_POST['old_password'] ?? ''; $new=$_POST['new_password'] ?? ''; $confirm=$_POST['confirm_password'] ?? '';
                $row=one('SELECT password_hash FROM users WHERE id=?',[$u['id']]);
                if (!is_string($old) || !$row || !password_verify($old,$row['password_hash'])) throw new DomainException('La contraseña actual no es correcta.');
                if (!is_string($new) || !valid_personal_password($new)) throw new DomainException('La nueva contraseña debe tener al menos 8 caracteres, una mayúscula, una minúscula, un número y un signo; máximo 72 bytes.');
                if ($new!==$confirm) throw new DomainException('Las contraseñas no coinciden.');
                if ($new===$old) throw new DomainException('La nueva contraseña debe ser diferente de la actual.');
                query('UPDATE users SET password_hash=? WHERE id=?',[password_hash($new,PASSWORD_DEFAULT),$u['id']]);
                session_regenerate_id(true); flash('Contraseña actualizada.'); go('page=account');
            } elseif ($action==='logout') {
                $_SESSION=[]; session_destroy(); go();
            } elseif (in_array($action,['publish','complete'],true)) {
                $id=id_field('course_id');
                if (!$u || !($c=course_for($id,$u))) { http_response_code(403); exit('Acceso denegado'); }
                if ($action==='complete') {
                    require_role($u,'student'); $lesson=id_field('lesson_id');
                    if (!one('SELECT id FROM lessons WHERE id=? AND course_id=?',[$lesson,$id])) throw new DomainException('Lección inválida.');
                    query('INSERT INTO progress(lesson_id,student_id) VALUES(?,?) ON DUPLICATE KEY UPDATE completed_at=completed_at',[$lesson,$u['id']]);
                } elseif ($action==='publish') {
                    require_role($u,'admin','subadmin','teacher');
                    query('UPDATE courses SET published=1-published WHERE id=?',[$id]);
                }
                flash('Cambios guardados.'); go('course='.$id);
            } else throw new DomainException('Acción inválida.');
        } catch (DomainException $e) { flash($e->getMessage(),'error'); if ($action==='password') go('page=account'); }
        go();
    }
    $courses=[]; $users=[]; $c=null; $lessons=[]; $done=[]; $page='home';
    if ($u) {
        if (is_manager($u)) { $courses=all('SELECT * FROM courses ORDER BY id DESC'); $users=$u['role']==='admin'?all('SELECT '.user_identity_columns().' FROM users ORDER BY name'):all("SELECT ".user_identity_columns()." FROM users WHERE role IN ('teacher','student') ORDER BY name"); }
        elseif ($u['role']==='teacher') $courses=all('SELECT * FROM courses WHERE teacher_id=? ORDER BY id DESC',[$u['id']]);
        else $courses=all('SELECT c.* FROM courses c JOIN enrollments e ON e.course_id=c.id WHERE e.student_id=? AND c.published=1 ORDER BY c.id DESC',[$u['id']]);
        require_role($u,'admin','subadmin','teacher','student');
        $page=is_string($_GET['page'] ?? null)?$_GET['page']:'home';
        if ($page==='create_user'||in_array($page,['users_admin','users_subadmin','users_teacher','users_student'],true)) $page='users';
        if ($page==='create_course') $page='courses';
        if (isset($_GET['course'])) $page='courses';
        if (!in_array($page,allowed_pages($u),true)) { http_response_code(403); exit('Sección no autorizada.'); }
        if (isset($_GET['course'])) {
            $c=course_for((int)$_GET['course'],$u);
            if (!$c) {http_response_code(404); exit('Curso no disponible.');}
            $lessons=all('SELECT * FROM lessons WHERE course_id=? ORDER BY sort_order,id',[$c['id']]);
            if ($u['role']==='student') $done=array_column(all('SELECT lesson_id FROM progress WHERE student_id=?',[$u['id']]),'lesson_id');
        }
    }
} catch (Throwable $e) { error_log($e->getMessage()); http_response_code(503); exit('VIRTUALEDUC: verifica config.local.php y la instalación de schema.sql.'); }
function action(string $a, ?int $id=null): void { csrf_field(); echo '<input type="hidden" name="action" value="'.h($a).'">'; if($id!==null) echo '<input type="hidden" name="course_id" value="'.$id.'">'; }
