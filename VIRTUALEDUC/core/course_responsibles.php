<?php
declare(strict_types=1);
if (!defined('VE_VERSION')) { http_response_code(404); exit; }
const COURSE_RESPONSIBLE_LIMIT=50;

// The first responsible remains in courses.teacher_id for backwards compatibility.
function course_responsibles(array $c): array {
    return all('SELECT '.user_identity_columns().' FROM users WHERE id=? OR EXISTS (SELECT 1 FROM course_responsibles cr WHERE cr.course_id=? AND cr.user_id=users.id) ORDER BY (id=?) DESC,name,id',[$c['teacher_id'],$c['id'],$c['teacher_id']]);
}
function course_has_responsible(array $c,mixed $id): bool {
    return (string)$c['teacher_id']===(string)$id || (bool)one('SELECT user_id FROM course_responsibles WHERE course_id=? AND user_id=?',[$c['id'],$id]);
}
// Resolve and validate exact usernames, including the previous single-column CSV format.
// Call inside the transaction. Managers can retain existing assignments they could not newly assign.
function course_responsible_ids(array $actor,array $r,array $existing=[]): array {
    $raw=$r['usuarios_responsables']??null;
    if($raw===null) {
        $value=creation_value($r,'usuario_responsable',10000);
        $raw=explode(',',$value);
    }
    if(!is_array($raw)||!$raw||count($raw)>COURSE_RESPONSIBLE_LIMIT) throw new DomainException('Selecciona entre 1 y '.COURSE_RESPONSIBLE_LIMIT.' responsables.');
    $ids=[];
    foreach($raw as $value) {
        $username=creation_value(['usuario'=>$value],'usuario',190);
        $person=one('SELECT id,role FROM users WHERE '.username_sql().'=? FOR UPDATE',[$username]);
        if(!$person) throw new DomainException('Usuario responsable inexistente.');
        $id=(string)$person['id'];
        $allowed=($actor['role']==='admin' && in_array($person['role'],['admin','subadmin','teacher'],true))
            || ($actor['role']==='subadmin' && ($person['role']==='teacher' || ($id===(string)$actor['id'] && $person['role']==='subadmin')))
            || ($actor['role']==='teacher' && $person['role']==='teacher' && $id===(string)$actor['id'])
            || (is_manager($actor) && in_array($id,$existing,true));
        if(!$allowed) throw new DomainException('Usuario responsable no autorizado.');
        $ids[$id]=$id;
    }
    return array_values($ids);
}
function course_save_extra_responsibles(int|string $courseId,array $ids): void {
    query('DELETE FROM course_responsibles WHERE course_id=?',[$courseId]);
    foreach(array_slice($ids,1) as $id) query('INSERT INTO course_responsibles(course_id,user_id) VALUES(?,?)',[$courseId,$id]);
}
function course_check_title(string $title,array $ids,int $except=0): void {
    $slots=implode(',',array_fill(0,count($ids),'?'));
    if(one('SELECT id FROM courses WHERE title=? AND id<>? AND (teacher_id IN ('.$slots.') OR EXISTS (SELECT 1 FROM course_responsibles cr WHERE cr.course_id=courses.id AND cr.user_id IN ('.$slots.')))',array_merge([$title,$except],$ids,$ids))) throw new DomainException('Ya existe otro curso con este título y uno de los responsables.');
}
