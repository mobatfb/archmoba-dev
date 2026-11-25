<?php
declare(strict_types=1);
// FUTUREO STUDIO v0.1.0 - PHP 7.4+
date_default_timezone_set('America/Guayaquil');
header('X-Content-Type-Options: nosniff');
header('Referrer-Policy: same-origin');
header('X-Frame-Options: DENY');
header('Cache-Control: no-store');
$adminPage = $adminPage ?? false;
$storage = __DIR__ . '/proyectos';
function e(string $s): string { return htmlspecialchars($s, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8'); }
function redirect(string $url): void { header('Location: ' . $url, true, 303); exit; }
function projectName(string $s): bool { return strlen($s) <= 160 && preg_match('/\A[A-Za-z0-9_-]+\.fprj\z/i', $s) === 1; }
function projects(string $dir): array {
    $out = [];
    foreach (glob($dir . '/*', GLOB_NOSORT) ?: [] as $path) {
        $name = basename($path);
        if (!projectName($name) || !is_file($path) || is_link($path)) continue;
        $out[] = ['name' => $name, 'mtime' => (int) filemtime($path)];
    }
    usort($out, static function ($a, $b) { return ($b['mtime'] <=> $a['mtime']) ?: strcmp($b['name'], $a['name']); });
    return $out;
}
function createProject(string $dir): string {
    if (!is_dir($dir) && !@mkdir($dir, 0755, true) && !is_dir($dir)) throw new RuntimeException('No se pudo crear la carpeta proyectos.');
    if (!is_writable($dir) || is_link($dir)) throw new RuntimeException('La carpeta proyectos no permite escritura.');
    $base = 'sin_nombre_' . date('Ymd');
    for ($i = 1; $i <= 9999; $i++) {
        $name = $base . ($i === 1 ? '' : '_' . sprintf('%02d', $i)) . '.fprj';
        $path = $dir . '/' . $name;
        $fp = @fopen($path, 'xb');
        if ($fp === false) {
            if (file_exists($path) || is_link($path)) continue;
            throw new RuntimeException('No se pudo escribir el proyecto. Revisa los permisos del hosting.');
        }
        $data = json_encode(['format'=>'FPRJ','version'=>1,'name'=>substr($name,0,-5),'status'=>'temporal','created_at'=>date(DATE_ATOM),'module'=>null,'content'=>new stdClass()], JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE) . "\n";
        $n = fwrite($fp, $data);
        fclose($fp);
        if ($n !== strlen($data)) { @unlink($path); throw new RuntimeException('No se pudo guardar el proyecto completo.'); }
        return $name;
    }
    throw new RuntimeException('Se alcanzó el límite de nombres para hoy.');
}
$error = '';
$logged = false;
$csrf = '';
if ($adminPage) {
    ini_set('session.use_strict_mode', '1');
    session_name('FUTUREOSTUDIO');
    session_set_cookie_params(['lifetime'=>0,'path'=>str_replace('\\','/',dirname($_SERVER['SCRIPT_NAME'] ?? '/admin.php')) === '/' ? '/' : rtrim(str_replace('\\','/',dirname($_SERVER['SCRIPT_NAME'] ?? '/admin.php')), '/') . '/','secure'=>!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off','httponly'=>true,'samesite'=>'Lax']);
    session_start();
    if (empty($_SESSION['csrf'])) $_SESSION['csrf'] = bin2hex(random_bytes(32));
    $csrf = $_SESSION['csrf'];
    $logged = !empty($_SESSION['admin']);
    if ($_SERVER['REQUEST_METHOD'] === 'POST') {
        $action = $_POST['action'] ?? '';
        $token = $_POST['csrf'] ?? '';
        if (!is_string($token) || !hash_equals($csrf, $token)) { http_response_code(403); $error = 'Solicitud no válida. Recarga la página.'; }
        elseif ($action === 'login' && !$logged) {
            $password = getenv('FUTUREO_ADMIN_PASSWORD');
            if ($password === false || $password === '') $password = '12345678';
            $user = $_POST['user'] ?? '';
            $pass = $_POST['password'] ?? '';
            if (is_string($user) && is_string($pass) && hash_equals('admin', $user) && hash_equals($password, $pass)) {
                session_regenerate_id(true); $_SESSION['admin'] = true; $_SESSION['csrf'] = bin2hex(random_bytes(32)); redirect('admin.php');
            }
            $error = 'Usuario o contraseña incorrectos.';
        } elseif ($action === 'logout' && $logged) {
            $_SESSION = []; session_destroy(); redirect('admin.php');
        } elseif ($action === 'new' && $logged) {
            try { redirect('admin.php?project=' . rawurlencode(createProject($storage))); }
            catch (RuntimeException $ex) { $error = $ex->getMessage(); }
        } else { http_response_code(403); $error = 'Acción no autorizada.'; }
    }
}
$page = $adminPage ? 'admin.php' : 'index.php';
$project = null;
if ((!$adminPage || $logged) && isset($_GET['project'])) {
    $name = $_GET['project'];
    if (is_string($name) && projectName($name) && is_file($storage . '/' . $name) && !is_link($storage . '/' . $name)) $project = $name;
    else { http_response_code(404); $error = 'Proyecto no encontrado.'; }
}
$list = (!$adminPage || $logged) && $project === null ? projects($storage) : [];
?><!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>FUTUREO STUDIO<?= $adminPage ? ' | Administración' : '' ?></title><link rel="icon" type="image/png" href="assets/icono.png"><link rel="stylesheet" href="assets/studio.css"></head>
<body>
<header class="top"><a class="brand" href="<?= e($page) ?>"><img src="assets/logotipo.png" alt="FUTUREO" onerror="this.hidden=true;this.nextElementSibling.hidden=false"><b hidden>FUTUREO</b><span>STUDIO</span></a><nav><?php if ($adminPage && $logged): ?><a href="index.php">Vista pública</a><form method="post" action="admin.php"><input type="hidden" name="csrf" value="<?= e($csrf) ?>"><button class="subtle" name="action" value="logout">Salir</button></form><?php elseif (!$adminPage): ?><a href="admin.php">Administración</a><?php else: ?><a href="index.php">Inicio</a><?php endif; ?></nav></header>
<?php if ($adminPage && !$logged): ?>
<main class="login-wrap"><section class="login"><img class="mark" src="assets/icono.png" alt="FUTUREO"><p class="eyebrow">FUTUREO STUDIO</p><h1>Iniciar sesión</h1><p class="muted">Acceso al panel de proyectos.</p><?php if ($error): ?><p class="error" role="alert"><?= e($error) ?></p><?php endif; ?><form method="post" action="admin.php"><input type="hidden" name="csrf" value="<?= e($csrf) ?>"><label for="user">Usuario</label><input id="user" name="user" autocomplete="username" required><label for="password">Contraseña</label><input id="password" name="password" type="password" autocomplete="current-password" required><button class="primary" name="action" value="login">Ingresar</button></form></section></main>
<?php elseif ($project !== null): ?>
<div class="workspace-bar"><a href="<?= e($page) ?>">← Proyectos</a><span><?= e($project) ?></span></div><main class="workspace" aria-label="Espacio de trabajo vacío"></main>
<?php else: ?>
<main class="dashboard"><div class="intro"><div><p class="eyebrow"><?= $adminPage ? 'ADMINISTRACIÓN' : 'ESPACIO PÚBLICO' ?></p><h1>Proyectos</h1><p class="muted"><?= $adminPage ? 'Crea y abre tus proyectos locales.' : 'Explora los proyectos de FUTUREO STUDIO.' ?></p></div><span class="count"><?= count($list) ?> proyectos</span></div>
<?php if ($error): ?><p class="error" role="alert"><?= e($error) ?></p><?php endif; ?>
<?php if (!$list): ?><section class="empty"><div class="empty-icon">▱</div><h2>Sin proyectos todavía</h2><p><?= $adminPage ? 'Pulsa Nuevo para comenzar.' : 'Aquí aparecerán los proyectos disponibles.' ?></p></section><?php else: ?><section class="grid" aria-label="Proyectos"><?php foreach ($list as $item): ?><a class="project" href="<?= e($page . '?project=' . rawurlencode($item['name'])) ?>"><span class="file-icon">F</span><div class="project-info"><strong><?= e($item['name']) ?></strong><small><?= e(date('d/m/Y H:i', $item['mtime'])) ?> · FPRJ</small></div><span class="arrow">↗</span></a><?php endforeach; ?></section><?php endif; ?>
</main>
<?php if ($adminPage): ?><form class="new-form" method="post" action="admin.php"><input type="hidden" name="csrf" value="<?= e($csrf) ?>"><button class="fab" name="action" value="new"><span>＋</span> Nuevo</button></form><?php endif; ?>
<?php endif; ?>
</body></html>
