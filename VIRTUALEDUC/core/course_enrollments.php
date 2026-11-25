<?php
declare(strict_types=1);
if (!defined('VE_VERSION')) { http_response_code(404); exit; }

const COURSE_ENROLL_LIMIT = 500;
const COURSE_STUDENT_PAGE = 50;

function course_enrollment_ids(mixed $raw): array {
    if (!is_array($raw) || !$raw || count($raw)>COURSE_ENROLL_LIMIT) throw new DomainException('Selecciona entre 1 y 500 estudiantes.');
    $ids=[];
    foreach ($raw as $id) {
        if (!is_string($id) || !preg_match('/\A[1-9][0-9]{0,19}\z/D',$id) || (strlen($id)===20 && strcmp($id,'18446744073709551615')>0)) throw new DomainException('Estudiante inválido.');
        $ids[$id]=$id;
    }
    return array_values($ids);
}
function course_enroll_many(array $actor,int $courseId,mixed $raw): array {
    require_role($actor,'admin','subadmin','teacher');
    $ids=course_enrollment_ids($raw);
    $pdo=db(); $pdo->beginTransaction();
    try {
        $fresh=one('SELECT id,role FROM users WHERE id=? FOR UPDATE',[$actor['id']]);
        $course=one('SELECT id,teacher_id FROM courses WHERE id=? FOR UPDATE',[$courseId]);
        if (!$fresh || !$course || !course_can_edit($fresh,$course)) throw new DomainException('Curso inexistente o no autorizado.');
        $slots=implode(',',array_fill(0,count($ids),'?'));
        $students=all("SELECT id FROM users WHERE role='student' AND id IN ($slots) ORDER BY id FOR UPDATE",$ids);
        if (count($students)!==count($ids) || array_diff($ids,array_map('strval',array_column($students,'id')))) throw new DomainException('Algún usuario seleccionado ya no es estudiante. No se guardó ninguna matrícula.');
        $added=0;
        foreach ($students as $student) {
            $added+=query('INSERT INTO enrollments(course_id,student_id) VALUES(?,?) ON DUPLICATE KEY UPDATE enrolled_at=enrolled_at',[$courseId,$student['id']])->rowCount();
        }
        $pdo->commit();
        return ['added'=>$added,'existing'=>count($ids)-$added];
    } catch (Throwable $e) {
        if ($pdo->inTransaction()) $pdo->rollBack();
        throw $e;
    }
}
function course_candidate_page(int $courseId,string $search,int $page): array {
    $page=max(1,min(1000000,$page));
    $params=[$courseId];
    $sql="SELECT id,name,".username_sql()." AS username FROM users WHERE role='student' AND NOT EXISTS (SELECT 1 FROM enrollments e WHERE e.course_id=? AND e.student_id=users.id)";
    if ($search!=='') {
        $term='%'.strtr($search,['!'=>'!!','%'=>'!%','_'=>'!_']).'%';
        $sql.=" AND (name LIKE ? ESCAPE '!' OR ".username_sql()." LIKE ? ESCAPE '!')";
        $params[]=$term; $params[]=$term;
    }
    $rows=all($sql.' ORDER BY name,id LIMIT '.(COURSE_STUDENT_PAGE+1).' OFFSET '.(($page-1)*COURSE_STUDENT_PAGE),$params);
    $more=count($rows)>COURSE_STUDENT_PAGE;
    return ['students'=>array_map(static fn(array $x):array=>['id'=>(string)$x['id'],'name'=>$x['name'],'username'=>$x['username']],array_slice($rows,0,COURSE_STUDENT_PAGE)),'page'=>$page,'more'=>$more];
}
function serve_course_candidates(?array $u): never {
    header('Content-Type: application/json; charset=utf-8');
    header('Cache-Control: private, no-store');
    header('Cross-Origin-Resource-Policy: same-origin');
    header('X-Content-Type-Options: nosniff');
    if (($_SERVER['REQUEST_METHOD']??'')!=='GET') { header('Allow: GET'); http_response_code(405); echo '{}'; exit; }
    if (!$u || !in_array($u['role'],['admin','subadmin','teacher'],true) || in_array($_SERVER['HTTP_SEC_FETCH_SITE']??'',['cross-site','same-site'],true)) { http_response_code(403); echo '{}'; exit; }
    $id=filter_var($_GET['course_candidates']??'',FILTER_VALIDATE_INT,['options'=>['min_range'=>1]]);
    $c=$id?course_for($id,$u):null;
    if (!$c || !course_can_edit($u,$c)) { http_response_code(403); echo '{}'; exit; }
    $q=$_GET['q']??'';
    if (!is_string($q) || strlen($q)>300 || !preg_match('//u',$q)) { http_response_code(400); echo '{}'; exit; }
    $page=filter_var($_GET['candidate_page']??'1',FILTER_VALIDATE_INT,['options'=>['min_range'=>1,'max_range'=>1000000]])?:1;
    session_write_close();
    echo json_encode(course_candidate_page($id,trim($q),$page),JSON_UNESCAPED_UNICODE|JSON_INVALID_UTF8_SUBSTITUTE|JSON_THROW_ON_ERROR);
    exit;
}
