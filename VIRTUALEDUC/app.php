<?php
declare(strict_types=1);

if (realpath($_SERVER['SCRIPT_FILENAME'] ?? '') === __FILE__) {
    http_response_code(404);
    exit;
}

const VE_VERSION = '0.1.38';
date_default_timezone_set('America/Guayaquil');

ini_set('session.use_strict_mode', '1');
ini_set('session.use_only_cookies', '1');
session_name('virtualeduc_session');
session_set_cookie_params([
    'lifetime' => 0,
    'path' => rtrim(dirname($_SERVER['SCRIPT_NAME'] ?? '/'), '/') . '/',
    'secure' => !empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off',
    'httponly' => true,
    'samesite' => 'Lax',
]);
session_start();

header('X-Content-Type-Options: nosniff');
header('X-Frame-Options: DENY');
header('Referrer-Policy: same-origin');
header("Content-Security-Policy: default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; base-uri 'none'; form-action 'self'; frame-ancestors 'none'");
header('Cache-Control: no-store');

// Versioned image URLs: private resources are isolated by login session.
function image_cache_version(?string $path,string $kind,?array $stat=null,bool $private=true): string {
    if ($path===null) return '';
    if ($stat===null) { clearstatcache(true,$path); $stat=@stat($path)?:null; }
    if ($stat===null) return '';
    $revision=implode('|',[$kind,$path,$stat['dev'],$stat['ino'],$stat['size'],$stat['mtime'],$stat['ctime']]);
    if (!$private) return hash('sha256',$revision);
    $key=$_SESSION['image_cache_key']??=bin2hex(random_bytes(32));
    return hash_hmac('sha256',session_id().'|'.$revision,$key);
}
function image_cache_url(string $url,string $version): string {
    return $version===''?$url:$url.'&v='.$version;
}
function image_cache_request_version(string $version): ?string {
    $requested=$_GET['v']??null;
    return $version!=='' && is_string($requested) && hash_equals($version,$requested)?$version:null;
}
function image_cache_headers(?string $version,int $seconds): void {
    if ($version===null) return; // Older links keep the default no-store policy.
    header_remove('Pragma');
    header_remove('Expires');
    header('Cache-Control: private, max-age='.$seconds.', must-revalidate');
    header('Vary: Cookie',false);
    header('ETag: "'.$version.'"');
}
function image_cache_not_modified(?string $version,int $seconds): bool {
    if ($version===null) return false;
    $etag='"'.$version.'"';
    foreach (explode(',',$_SERVER['HTTP_IF_NONE_MATCH']??'') as $candidate) {
        $candidate=trim($candidate);
        if ($candidate==='*' || $candidate===$etag || $candidate==='W/'.$etag) {
            image_cache_headers($version,$seconds);
            http_response_code(304);
            return true;
        }
    }
    return false;
}

function h(mixed $v): string {
    return htmlspecialchars((string)$v, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}

function db(): PDO {
    static $pdo;
    if (!$pdo) {
        $c = config();
        $pdo = new PDO($c['dsn'], $c['db_user'], $c['db_password'], [
            PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
            PDO::ATTR_EMULATE_PREPARES => false,
        ]);
    }
    return $pdo;
}

function config(): array {
    static $c;
    if ($c === null) {
        $file = __DIR__ . '/config.local.php';
        if (!is_file($file)) {
            throw new RuntimeException('Configuración pendiente.');
        }
        $c = require $file;
        if (!is_array($c)) {
            throw new RuntimeException('Configuración inválida.');
        }
    }
    return $c;
}

function query(string $sql, array $params = []): PDOStatement {
    $stmt = db()->prepare($sql);
    $stmt->execute($params);
    return $stmt;
}

function all(string $sql, array $params = []): array {
    return query($sql, $params)->fetchAll();
}

function one(string $sql, array $params = []): ?array {
    return query($sql, $params)->fetch() ?: null;
}

function count_rows(string $sql, array $params = []): int {
    return (int)query($sql, $params)->fetchColumn();
}

function token(): string {
    return $_SESSION['csrf'] ??= bin2hex(random_bytes(32));
}

function csrf_field(): void {
    echo '<input type="hidden" name="csrf" value="' . h(token()) . '">';
}

function verify_csrf(): void {
    $value = $_POST['csrf'] ?? null;
    if (!is_string($value) || !hash_equals(token(), $value)) {
        http_response_code(403);
        exit('Solicitud no válida. Recarga la página.');
    }
}

function go(string $page = ''): never {
    header('Location: index.php' . ($page !== '' ? '?' . $page : ''), true, 303);
    exit;
}

function flash(string $message, string $kind = 'success'): void {
    $_SESSION['flash'] = [$message, $kind];
}

function current_user(): ?array {
    $id = (int)($_SESSION['user_id'] ?? 0);
    return $id ? one('SELECT '.user_identity_columns().' FROM users WHERE id=?', [$id]) : null;
}

function require_role(?array $u, string ...$roles): void {
    if (!$u || !in_array($u['role'], $roles, true)) {
        http_response_code(403);
        exit('No tienes permiso para esta operación.');
    }
}

function field(string $key, int $max, bool $required = true): string {
    $value = $_POST[$key] ?? '';
    if (!is_string($value)) {
        throw new DomainException('Campo inválido.');
    }
    $value = trim($value);
    if (($required && $value === '') || strlen($value) > $max) {
        throw new DomainException('Completa los campos respetando su longitud máxima.');
    }
    return $value;
}

function id_field(string $key): int {
    $id = filter_var($_POST[$key] ?? '', FILTER_VALIDATE_INT, ['options' => ['min_range' => 1]]);
    if (!$id) throw new DomainException('Selecciona un registro válido.');
    return $id;
}

// The fallback also supports the original private admin SQL on a fresh installation.
function username_sql(): string {
    return "COALESCE(username,CASE WHEN email='admin@virtualeduc.local' AND role='admin' THEN 'admin' ELSE email END)";
}

function user_identity_columns(): string {
    return "id,name,email,role,".username_sql()." AS username,COALESCE(NULLIF(first_names,''),name) AS first_names,last_names";
}

function find_by_username(string $username): ?array {
    return one('SELECT '.user_identity_columns().' FROM users WHERE '.username_sql().'=?', [$username]);
}

function valid_username(string $username): bool {
    return preg_match('/^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$/D',$username)===1;
}

function course_for(int $id, array $u): ?array {
    if (is_manager($u)) {
        return one('SELECT * FROM courses WHERE id=?', [$id]);
    }
    if ($u['role'] === 'teacher') {
        return one('SELECT * FROM courses WHERE id=? AND teacher_id=?', [$id,$u['id']]);
    }
    return one('SELECT c.* FROM courses c JOIN enrollments e ON e.course_id=c.id WHERE c.id=? AND e.student_id=? AND c.published=1', [$id,$u['id']]);
}

function valid_user_role(string $role): bool {
    return in_array($role, ['admin','subadmin','teacher','student'], true);
}

function role_label(string $role): string {
    return ['admin'=>'Administrador','subadmin'=>'Subadministrador','teacher'=>'Docente','student'=>'Estudiante'][$role] ?? 'Sin rol asignado';
}

function is_manager(?array $u): bool {
    return $u !== null && in_array($u['role'], ['admin','subadmin'], true);
}

function creatable_roles(array $u): array {
    return $u['role'] === 'admin' ? ['admin','subadmin','teacher','student'] : ($u['role'] === 'subadmin' ? ['teacher','student'] : []);
}

function available_teachers(array $u): array {
    if ($u['role'] === 'admin') return all("SELECT ".user_identity_columns()." FROM users WHERE role IN ('admin','subadmin','teacher') ORDER BY name");
    if ($u['role'] === 'subadmin') return all("SELECT ".user_identity_columns()." FROM users WHERE role='teacher' OR id=? ORDER BY name", [$u['id']]);
    return [];
}

// Passwords chosen by the account owner must meet the complexity policy.
function valid_personal_password(string $password): bool {
    return strlen($password)<=72 && !str_contains($password,"\0")
        && preg_match_all('/./us',$password)>=8
        && preg_match('/\p{Lu}/u',$password)===1
        && preg_match('/\p{Ll}/u',$password)===1
        && preg_match('/[0-9]/',$password)===1
        && preg_match('/[\p{P}\p{S}]/u',$password)===1;
}
