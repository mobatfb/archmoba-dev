<?php
declare(strict_types=1);
if (!defined('VE_VERSION')) { http_response_code(404); exit; }

function user_picker_results(array $u,string $kind,string $search,?int $courseId): array {
    if (!is_manager($u)) throw new DomainException('Búsqueda no autorizada.');
    $params=[];
    if ($kind==='responsible') {
        $where=$u['role']==='admin'?"role IN ('admin','subadmin','teacher')":"(role='teacher' OR id=?)";
        if ($u['role']==='subadmin') $params[]=$u['id'];
    } elseif ($kind==='student') {
        if (!$courseId || !course_for($courseId,$u)) throw new DomainException('Selecciona un curso autorizado.');
        $where="role='student' AND NOT EXISTS (SELECT 1 FROM enrollments e WHERE e.course_id=? AND e.student_id=users.id)";
        $params[]=$courseId;
    } else throw new DomainException('Búsqueda inválida.');
    if ($search!=='') {
        $term='%'.strtr($search,['!'=>'!!','%'=>'!%','_'=>'!_']).'%';
        $where.=" AND (name LIKE ? ESCAPE '!' OR ".username_sql()." LIKE ? ESCAPE '!')";
        $params[]=$term; $params[]=$term;
    }
    $rows=all('SELECT id,name,first_names,last_names,'.username_sql().' AS username FROM users WHERE '.$where.' ORDER BY name,id LIMIT 31',$params);
    return ['people'=>array_map(static fn(array $x):array=>['name'=>$x['name'],'username'=>$x['username']]+profile_preview_data($x),array_slice($rows,0,30)),'more'=>count($rows)>30];
}
function serve_user_picker(?array $u): never {
    header('Content-Type: application/json; charset=utf-8');
    header('Cache-Control: private, no-store');
    header('Cross-Origin-Resource-Policy: same-origin');
    if (($_SERVER['REQUEST_METHOD']??'')!=='GET') { header('Allow: GET'); http_response_code(405); echo '{}'; exit; }
    if (!is_manager($u) || in_array($_SERVER['HTTP_SEC_FETCH_SITE']??'',['cross-site','same-site'],true)) { http_response_code(403); echo '{}'; exit; }
    $kind=$_GET['user_picker']??null; $q=$_GET['q']??'';
    $courseId=filter_var($_GET['course_id']??'',FILTER_VALIDATE_INT,['options'=>['min_range'=>1]])?:null;
    if (!is_string($kind) || !is_string($q) || strlen($q)>760 || !preg_match('//u',$q)) { http_response_code(400); echo '{}'; exit; }
    session_write_close();
    try { echo json_encode(user_picker_results($u,$kind,trim($q),$courseId),JSON_UNESCAPED_UNICODE|JSON_INVALID_UTF8_SUBSTITUTE|JSON_THROW_ON_ERROR); }
    catch(DomainException $e) { http_response_code(403); echo '{}'; }
    exit;
}
function render_user_picker(string $label,string $field,string $kind,?array $selected=null,bool $readOnly=false,int $courseId=0): void { ?>
<div class="ve-user-picker" data-ve-user-picker="<?=h($kind)?>" data-ve-picker-course="<?=h($courseId)?>">
  <label><?=h($label)?><input name="<?=h($field)?>" required maxlength="190" autocomplete="off" value="<?=h($selected['username']??'')?>" <?=$readOnly?'readonly':'placeholder="Buscar por usuario o nombre"'?>></label>
  <div class="ve-picker-selected" data-ve-picker-selected <?=$selected?'':'hidden'?>><?php if($selected): profile_preview_avatar($selected,'ve-person-avatar',$courseId&&$kind==='responsible'?$courseId:null); ?><strong><?=h($selected['name'])?></strong><?php endif;?></div>
  <?php if(!$readOnly):?><div class="ve-picker-results" data-ve-picker-results hidden role="group" aria-label="Resultados de búsqueda"><p class="muted" data-ve-picker-status role="status"></p><div data-ve-picker-list></div></div><?php endif;?>
</div>
<?php }
