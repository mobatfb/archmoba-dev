<?php
declare(strict_types=1);
if (!defined('VE_VERSION')) { http_response_code(404); exit; }

// Shared creation rules for individual forms, CSV templates and imports.
function creation_spec(?array $u, string $kind, string $role = '', int $course = 0): array {
    if (!$u) throw new DomainException('Inicia sesión.');
    if (($kind!=='user' && $role!=='') || (in_array($kind,['user','course'],true) && $course!==0)) throw new DomainException('Contexto inválido.');
    if ($kind === 'user' && is_manager($u) && $role==='') {
        return ['title'=>'Crear usuario','headers'=>['usuario','nombres','apellidos','correo','contrasena','rol'],'return'=>'page=users','limit'=>100];
    }
    if ($kind === 'course' && in_array($u['role'],['admin','subadmin','teacher'],true)) {
        return ['title'=>'Crear curso','headers'=>['titulo','descripcion','usuario_responsable'],'return'=>'page=courses','limit'=>500];
    }
    if ($kind === 'lesson' && $course>0 && $u['role']!=='student' && course_for($course,$u)) {
        return ['title'=>'Crear lección','headers'=>['titulo','contenido'],'return'=>'course='.$course,'limit'=>500];
    }
    if ($kind === 'enroll' && is_manager($u) && ($course===0 || course_for($course,$u))) {
        return ['title'=>'Crear matrícula','headers'=>$course?['usuario_estudiante']:['id_curso','usuario_estudiante'],'return'=>$course?'course='.$course:'page=enrollments','limit'=>500];
    }
    throw new DomainException('No tienes permiso para crear estos registros.');
}
function creation_context(array $data): array {
    $kind=$data['kind']??''; $role=$data['target_role']??'';
    $course=filter_var($data['course_id']??0,FILTER_VALIDATE_INT,['options'=>['min_range'=>0]]);
    if (!is_string($kind)||!is_string($role)||$course===false) throw new DomainException('Contexto inválido.');
    return [$kind,$role,$course];
}
function creation_example(string $kind, array $headers): array {
    $values = [
        'usuario'=>'estudiante.ejemplo',
        'nombres'=>'Ana María',
        'apellidos'=>'Pérez López',
        'correo'=>'estudiante@ejemplo.invalid',
        'contrasena'=>'Reemplazar-123!',
        'rol'=>'estudiante',
        'titulo'=>$kind==='lesson'?'Introducción al tema':'Curso de ejemplo',
        'descripcion'=>'Descripción del curso',
        'usuario_responsable'=>'docente.ejemplo',
        'contenido'=>'Contenido de la lección de ejemplo',
        'id_curso'=>'1',
        'usuario_estudiante'=>'estudiante.ejemplo',
    ];
    return array_map(static fn(string $key): string => $values[$key], $headers);
}
function creation_template(?array $u): never {
    [$kind,$role,$course]=creation_context($_GET);
    $spec=creation_spec($u,$kind,$role,$course);
    header('Content-Type: text/csv; charset=UTF-8');
    header('Content-Disposition: attachment; filename="plantilla_'.$kind.($role?'_'.$role:'').'.csv"');
    echo "\xEF\xBB\xBF";
    $out=fopen('php://output','wb');
    fputcsv($out,$spec['headers'],';','"','');
    $example=creation_example($kind,$spec['headers']);
    if($kind==='course' && $u['role']==='teacher') $example[array_search('usuario_responsable',$spec['headers'],true)]=$u['username'];
    fputcsv($out,$example,';','"','');
    fclose($out); exit;
}
function csv_rows(array $headers,int $limit): array {
    $file=$_FILES['csv']??null;
    if (!is_array($file)||($file['error']??null)!==UPLOAD_ERR_OK||!is_uploaded_file($file['tmp_name']??'')||($file['size']??0)>2097152) throw new DomainException('Selecciona un CSV válido de máximo 2 MB.');
    $f=fopen($file['tmp_name'],'rb'); if (!$f) throw new DomainException('No se pudo leer el archivo.');
    try {
        $head=fgetcsv($f,0,';','"','');
        if (!$head) throw new DomainException('El CSV está vacío.');
        $head[0]=preg_replace('/^\xEF\xBB\xBF/','',(string)$head[0]);
        if (array_map('trim',$head)!==$headers) throw new DomainException('Encabezado incorrecto. Descarga la plantilla de este módulo.');
        $rows=[]; $line=1;
        while (($values=fgetcsv($f,0,';','"',''))!==false) {
            $line++;
            if ($values===[null] || !array_filter($values,fn($v)=>trim((string)$v)!=='')) continue;
            if (count($values)!==count($headers)) throw new DomainException('Registro '.$line.': número de columnas incorrecto. Usa punto y coma.');
            foreach($values as $v) if (!preg_match('//u',(string)$v)) throw new DomainException('Registro '.$line.': guarda el CSV en UTF-8.');
            $rows[$line]=array_combine($headers,$values);
            if(count($rows)>$limit) throw new DomainException('El máximo es '.$limit.' registros por archivo.');
        }
        if (!$rows) throw new DomainException('El CSV no contiene registros.');
        return $rows;
    } finally { fclose($f); }
}
function creation_value(array $r,string $key,int $max,bool $password=false): string {
    $v=$r[$key]??'';
    if (!is_string($v)||!preg_match('//u',$v)) throw new DomainException('Campo inválido: '.$key.'.');
    if(!$password) $v=trim($v);
    if($v===''||strlen($v)>$max) throw new DomainException('Campo obligatorio o demasiado largo: '.$key.'.');
    return $v;
}
function creation_email(array $r,string $key): string {
    $email=strtolower(creation_value($r,$key,190));
    if(!filter_var($email,FILTER_VALIDATE_EMAIL)) throw new DomainException('Correo inválido: '.$key.'.');
    return $email;
}
function identity_fields(array $r, ?array $existing=null): array {
    $username=creation_value($r,'usuario',190);
    if (!valid_username($username) && (!$existing || $username!==$existing['username'])) throw new DomainException('Usuario inválido. Usa hasta 80 caracteres: letras, números, puntos, guiones o guion bajo.');
    $first=creation_value($r,'nombres',150); $last=creation_value($r,'apellidos',150);
    $name=$first.' '.$last;
    if(strlen($name)>150) throw new DomainException('Nombres y apellidos superan la longitud máxima combinada.');
    $email=creation_email($r,'correo');
    $other=find_by_username($username);
    if($other && (!$existing || (int)$other['id']!==(int)$existing['id'])) throw new DomainException('El usuario ya está registrado.');
    $other=one('SELECT id FROM users WHERE email=?',[$email]);
    if($other && (!$existing || (int)$other['id']!==(int)$existing['id'])) throw new DomainException('El correo ya está registrado.');
    return [$username,$first,$last,$name,$email];
}

function repair_user_role(?array $u): void {
    require_role($u,'admin');
    $id=id_field('user_id');
    $role=field('repair_role',30);
    if (!valid_user_role($role)) throw new DomainException('Selecciona un rol válido.');
    $pdo=db(); $pdo->beginTransaction();
    try {
        $row=one('SELECT role FROM users WHERE id=? FOR UPDATE',[$id]);
        if (!$row || valid_user_role((string)$row['role'])) throw new DomainException('La cuenta ya tiene un rol válido o no existe.');
        query('UPDATE users SET role=? WHERE id=?',[$role,$id]);
        $saved=one('SELECT role FROM users WHERE id=?',[$id]);
        if (!$saved || $saved['role']!==$role) throw new DomainException('No se pudo guardar el rol. Ejecuta migrations/0.1.16.sql.');
        $pdo->commit();
    } catch (Throwable $e) {
        if ($pdo->inTransaction()) $pdo->rollBack();
        if ($e instanceof PDOException) { error_log('VIRTUALEDUC role repair failed: '.get_class($e)); throw new DomainException('No se pudo guardar el rol. Revisa la migración 0.1.16.'); }
        throw $e;
    }
}

function update_user_identity(?array $u): void {
    require_role($u,'admin','subadmin');
    $id=id_field('user_id');
    $role=field('rol',30);
    $pdo=db(); $pdo->beginTransaction();
    try {
        // Recheck both accounts under locks to prevent concurrent privilege changes.
        $locked=array_column(all('SELECT '.user_identity_columns().' FROM users WHERE id IN (?,?) ORDER BY id FOR UPDATE',[$u['id'],$id]),null,'id');
        $actor=$locked[$u['id']]??null; $existing=$locked[$id]??null;
        if (!$actor || !$existing || !is_manager($actor) || !in_array($existing['role'],creatable_roles($actor),true)) throw new DomainException('Usuario no autorizado o inexistente.');
        if (!in_array($role,creatable_roles($actor),true)) throw new DomainException('Rol inválido o no autorizado.');
        if ((int)$actor['id']===$id && $role!==$actor['role']) throw new DomainException('No puedes cambiar tu propio rol.');
        [$username,$first,$last,$name,$email]=identity_fields($_POST,$existing);
        query('UPDATE users SET username=?,first_names=?,last_names=?,name=?,email=?,role=? WHERE id=?',[$username,$first,$last,$name,$email,$role,$id]);
        $saved=one('SELECT role FROM users WHERE id=?',[$id]);
        if (!$saved || $saved['role']!==$role) throw new DomainException('No se pudo guardar el rol. Revisa la migración 0.1.16.');
        $pdo->commit();
    } catch(Throwable $e) {
        if ($pdo->inTransaction()) $pdo->rollBack();
        if ($e instanceof PDOException) {
            if ($e->getCode()==='23000') throw new DomainException('El usuario o correo ya está registrado.');
            error_log('VIRTUALEDUC user edit failed: '.get_class($e));
            throw new DomainException('No se pudieron guardar los cambios. Revisa los datos e inténtalo nuevamente.');
        }
        throw $e;
    }
}

function creation_insert(array $u,string $kind,string $role,int $course,array $r): void {
    if($kind==='user') {
        $requested=strtolower(creation_value($r,'rol',30));
        $role=['administrador'=>'admin','subadministrador'=>'subadmin','docente'=>'teacher','estudiante'=>'student'][$requested]??$requested;
        if(!in_array($role,creatable_roles($u),true)) throw new DomainException('Rol inválido o no autorizado.');
        [$username,$first,$last,$name,$email]=identity_fields($r); $p=creation_value($r,'contrasena',72,true);
        if(preg_match_all('/./us',$p)<8||str_contains($p,"\0")) throw new DomainException('La contraseña debe tener al menos 8 caracteres y un máximo de 72 bytes.');
        query('INSERT INTO users(username,first_names,last_names,name,email,password_hash,role) VALUES(?,?,?,?,?,?,?)',[$username,$first,$last,$name,$email,password_hash($p,PASSWORD_DEFAULT),$role]);
        $saved=one('SELECT role FROM users WHERE id=?',[(int)db()->lastInsertId()]);
        if (!$saved || $saved['role']!==$role) throw new DomainException('No se pudo guardar el rol. Ejecuta migrations/0.1.16.sql.');
    } elseif($kind==='course') {
        $title=creation_value($r,'titulo',180); $description=creation_value($r,'descripcion',20000); $teacher=(int)$u['id'];
        $t=find_by_username(creation_value($r,'usuario_responsable',190));
        $allowed=is_manager($u)?array_map('intval',array_column(available_teachers($u),'id')):[(int)$u['id']];
        if(!$t||!in_array((int)$t['id'],$allowed,true)) throw new DomainException('Usuario responsable no autorizado o inexistente.');
        $teacher=(int)$t['id'];
        if(one('SELECT id FROM courses WHERE title=? AND teacher_id=?',[$title,$teacher])) throw new DomainException('Ya existe un curso con este título y responsable.');
        query('INSERT INTO courses(title,description,teacher_id) VALUES(?,?,?)',[$title,$description,$teacher]);
    } elseif($kind==='lesson') {
        $title=creation_value($r,'titulo',180); $content=creation_value($r,'contenido',60000);
        if(one('SELECT id FROM lessons WHERE course_id=? AND title=?',[$course,$title])) throw new DomainException('Ya existe una lección con este título.');
        $order=count_rows('SELECT COALESCE(MAX(sort_order),0) FROM lessons WHERE course_id=?',[$course])+1;
        query('INSERT INTO lessons(course_id,title,content,sort_order) VALUES(?,?,?,?)',[$course,$title,$content,$order]);
    } elseif($kind==='enroll') {
        if(!$course) $course=(int)filter_var($r['id_curso']??'',FILTER_VALIDATE_INT,['options'=>['min_range'=>1]]);
        if(!$course||!course_for($course,$u)) throw new DomainException('Curso inexistente o no autorizado.');
        $student=find_by_username(creation_value($r,'usuario_estudiante',190));
        if(!$student||$student['role']!=='student') throw new DomainException('Estudiante inexistente.');
        if(one('SELECT student_id FROM enrollments WHERE course_id=? AND student_id=?',[$course,$student['id']])) throw new DomainException('El estudiante ya está matriculado.');
        query('INSERT INTO enrollments(course_id,student_id) VALUES(?,?)',[$course,$student['id']]);
    }
}
function handle_creation(?array $u): never {
    $back='';
    try {
        [$kind,$role,$course]=creation_context($_POST);
        $spec=creation_spec($u,$kind,$role,$course); $back=$spec['return'];
        $mode=$_POST['mode']??'';
        if(!in_array($mode,['individual','bulk'],true)) throw new DomainException('Modo inválido.');
        $rows=$mode==='bulk'?csv_rows($spec['headers'],$spec['limit']):[1=>$_POST];
        $pdo=db(); $pdo->beginTransaction(); $errors=[];
        try {
            foreach($rows as $line=>$r) {
                try { creation_insert($u,$kind,$role,$course,$r); }
                catch(DomainException $e) { $errors[]='Registro '.$line.': '.$e->getMessage(); }
                if(count($errors)>=10) break;
            }
            if($errors) throw new DomainException('No se guardó ningún registro. '.implode(' | ',$errors));
            $pdo->commit(); flash(count($rows).' registro(s) creado(s) correctamente.');
        } catch(Throwable $e) { if($pdo->inTransaction()) $pdo->rollBack(); throw $e; }
    } catch(DomainException $e) { flash($e->getMessage(),'error'); }
    catch(Throwable $e) { error_log('VIRTUALEDUC creation failed: '.get_class($e)); flash('No se guardaron registros. Revisa los datos y vuelve a intentar.','error'); }
    go($back);
}
function creation_hidden(string $kind,string $role,int $course,string $mode): void {
    action('create',$course?:null);
    foreach(['kind'=>$kind,'target_role'=>$role,'mode'=>$mode] as $k=>$v) echo '<input type="hidden" name="'.h($k).'" value="'.h($v).'">';
}
function creation_dialog(array $u,string $kind,string $role='',int $course=0): void {
    $s=creation_spec($u,$kind,$role,$course); $id='create-'.$kind.($role?'-'.$role:'').($course?'-'.$course:'');
    $url='?'.http_build_query(['template'=>1,'kind'=>$kind,'target_role'=>$role,'course_id'=>$course]);
    ?>
    <button type="button" data-ve-open="<?=h($id)?>">+ Crear<?=$kind==='lesson'?' lección':($kind==='enroll'?' matrícula':'')?></button>
    <dialog class="ve-dialog" id="<?=h($id)?>" aria-labelledby="<?=h($id)?>-title">
      <div class="ve-dialog-head"><h2 id="<?=h($id)?>-title"><?=h($s['title'])?></h2><button type="button" class="ve-quiet" data-ve-close aria-label="Cerrar">×</button></div>
      <div class="ve-tabs" role="tablist"><button type="button" role="tab" id="<?=h($id)?>-individual-tab" aria-controls="<?=h($id)?>-individual" aria-selected="true" data-ve-tab="individual">Individual</button><button type="button" role="tab" id="<?=h($id)?>-bulk-tab" aria-controls="<?=h($id)?>-bulk" aria-selected="false" data-ve-tab="bulk">Masivo (CSV)</button></div>
      <div role="tabpanel" id="<?=h($id)?>-individual" aria-labelledby="<?=h($id)?>-individual-tab" data-ve-panel="individual"><form method="post"><?php creation_hidden($kind,$role,$course,'individual');?>
      <?php if($kind==='user'):?><label>Usuario<input name="usuario" required maxlength="80" pattern="[A-Za-z0-9][A-Za-z0-9._\-]{0,79}" autocomplete="off"></label><label>Nombres<input name="nombres" required maxlength="150"></label><label>Apellidos<input name="apellidos" required maxlength="150"></label><label>Correo electrónico<input type="email" name="correo" required maxlength="190"></label><label>Contraseña (mínimo 8 caracteres)<input type="password" name="contrasena" required minlength="8" maxlength="72" autocomplete="new-password"></label><label>Rol<select name="rol" required><option value="">Seleccionar rol</option><?php foreach(creatable_roles($u) as $r):?><option value="<?=h($r)?>"><?=h(role_label($r))?></option><?php endforeach;?></select></label>
      <?php elseif($kind==='course'||$kind==='lesson'):?><label>Título<input name="titulo" required maxlength="180"></label><label><?=$kind==='course'?'Descripción':'Contenido'?><textarea name="<?=$kind==='course'?'descripcion':'contenido'?>" required></textarea></label><?php if($kind==='course'):?><label>Usuario responsable<input name="usuario_responsable" required maxlength="190" autocomplete="off" <?php if(is_manager($u)):?>list="<?=h($id)?>-responsables"<?php else:?>value="<?=h($u['username'])?>" readonly<?php endif;?>></label><?php if(is_manager($u)):?><datalist id="<?=h($id)?>-responsables"><?php foreach(available_teachers($u) as $x):?><option value="<?=h($x['username'])?>" label="<?=h($x['name'])?>"></option><?php endforeach;?></datalist><?php endif;?><?php endif;?>
      <?php elseif($kind==='enroll'): if(!$course):?><label>Curso<select name="id_curso" required><option value="">Seleccionar</option><?php foreach(all('SELECT id,title FROM courses ORDER BY title') as $x):?><option value="<?=h($x['id'])?>">#<?=h($x['id'])?> · <?=h($x['title'])?></option><?php endforeach;?></select></label><?php endif;?><label>Usuario del estudiante<input name="usuario_estudiante" required maxlength="190" autocomplete="off" list="<?=h($id)?>-estudiantes"></label><datalist id="<?=h($id)?>-estudiantes"><?php foreach(all("SELECT ".user_identity_columns()." FROM users WHERE role='student' ORDER BY name") as $x):?><option value="<?=h($x['username'])?>" label="<?=h($x['name'])?>"></option><?php endforeach;?></datalist><?php endif;?>
      <div class="ve-dialog-actions"><button type="button" class="ve-quiet" data-ve-close>Cancelar</button><button>Crear registro</button></div></form></div>
      <div role="tabpanel" id="<?=h($id)?>-bulk" aria-labelledby="<?=h($id)?>-bulk-tab" data-ve-panel="bulk" hidden><p>Descarga la plantilla con una fila de ejemplo. Reemplaza o elimina esa fila, completa tus registros y guarda el archivo como CSV UTF-8 separado por punto y coma (;).</p><a class="btn" href="<?=h($url)?>">↓ Descargar plantilla CSV</a><p class="ve-columns"><code><?=h(implode(';',$s['headers']))?></code></p><p class="muted">Máximo <?=h($s['limit'])?> registros y 2 MB. Si hay errores, no se guardará ningún registro.<?=$kind==='user'?' Usa contraseñas individuales de al menos 8 caracteres y protege el archivo.':''?></p><?php if($kind==='user'):?><p class="muted">Valores permitidos en rol: <?=h(implode(', ',creatable_roles($u)))?> (también se aceptan los nombres de los roles en español).</p><?php endif;?><?php if($kind==='course'):?><p class="muted">Usa el usuario exacto del responsable. Los docentes solo pueden asignarse a sí mismos.</p><?php endif;?><?php if($kind==='enroll'):?><p class="muted">Usa el usuario exacto del estudiante registrado.</p><?php endif;?><?php if($kind==='enroll'&&!$course):?><p class="muted">Usa los ID de curso que aparecen en la tabla de matrículas.</p><?php endif;?><form method="post" enctype="multipart/form-data"><?php creation_hidden($kind,$role,$course,'bulk');?><label>Archivo CSV<input name="csv" type="file" accept=".csv,text/csv" required></label><div class="ve-dialog-actions"><button type="button" class="ve-quiet" data-ve-close>Cancelar</button><button>Validar e importar</button></div></form></div>
    </dialog>
    <?php
}
function creation_styles(): void { ?>
<style>
.ve-dialog{width:min(600px,calc(100% - 28px));max-height:90vh;overflow:auto;border:1px solid #cfdae8;border-radius:16px;padding:24px;color:#17253b;box-shadow:0 24px 90px #10294d50}.ve-dialog::backdrop{background:#091b38a0}.ve-dialog-head,.ve-dialog-actions,.ve-section-head{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}.ve-dialog-head h2,.ve-section-head h1{margin:0}.ve-tabs{display:flex;gap:8px;border-bottom:1px solid #dce5ef;margin:18px 0}.ve-tabs button{background:transparent;color:#526982;border-radius:8px 8px 0 0;border-bottom:3px solid transparent;flex:1}.ve-tabs button[aria-selected=true]{color:#1655a8;border-color:#1655a8;background:#edf4fe;font-weight:700}.ve-quiet{background:#eaf0f8;color:#10294d}.ve-quiet:hover{background:#d6e3f3}.ve-dialog-actions{justify-content:flex-end;margin-top:12px}.ve-columns{overflow-wrap:anywhere;background:#eef4fb;padding:12px;border-radius:8px}.ve-section-head{margin-bottom:18px}.ve-role-card{display:flex;align-items:center;justify-content:space-between;gap:10px}.ve-role-card a{font-weight:700;text-decoration:none;color:#1655a8}.ve-dialog [hidden]{display:none!important}

/* Shared action contrast: explicit foreground, including all interaction states. */
body button,body a.btn,body .btn{background:#1655a8;color:#fff!important;-webkit-text-fill-color:#fff!important;opacity:1;font-size:15px;font-weight:600;line-height:1.4;text-shadow:none;white-space:normal;border:1px solid transparent;min-height:40px}
body button:hover,body button:active,body a.btn:hover,body a.btn:active,body .btn:hover{background:#103d7d;color:#fff!important;-webkit-text-fill-color:#fff!important}
body button:focus-visible,body a.btn:focus-visible{outline:3px solid #e3a329;outline-offset:2px}
body button.ve-quiet,body .ve-tabs button{background:#eaf0f8;color:#10294d!important;-webkit-text-fill-color:#10294d!important;border-color:#d1deee}
body button.ve-quiet:hover,body .ve-tabs button:hover{background:#d6e3f3;color:#10294d!important;-webkit-text-fill-color:#10294d!important}
body .ve-tabs button[aria-selected=true]{background:#1655a8;color:#fff!important;-webkit-text-fill-color:#fff!important;border-color:#1655a8}
body button:disabled,body button[aria-disabled=true]{background:#e2e8f0;color:#475569!important;-webkit-text-fill-color:#475569!important;cursor:not-allowed}
body input[type=file]::file-selector-button{background:#1655a8;color:#fff;-webkit-text-fill-color:#fff;font:inherit;font-weight:600;border:0;border-radius:6px;padding:8px 10px;margin-right:10px;cursor:pointer}
.ve-role-card{flex-wrap:wrap}.ve-role-card button[data-ve-open]{flex:none}.ve-section-head button[data-ve-open]{flex-shrink:0}
</style><?php }
