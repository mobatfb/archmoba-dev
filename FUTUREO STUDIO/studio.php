<?php
declare(strict_types=1);
// FUTUREO STUDIO v0.1.26 - PHP 7.4+
date_default_timezone_set('America/Guayaquil');
header('X-Content-Type-Options: nosniff');
header('Referrer-Policy: same-origin');
header('X-Frame-Options: DENY');
header('Cache-Control: no-store');
$adminPage = $adminPage ?? false;
$storage = __DIR__ . '/proyectos';
function e(string $s): string { return htmlspecialchars($s, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8'); }
function redirect(string $url): void { header('Location: ' . $url, true, 303); exit; }
require_once __DIR__ . '/projects.php';
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
    if (is_string($name) && projectName($name) && projectPath($storage, $name) !== null) $project = $name;
    else { http_response_code(404); $error = 'Proyecto no encontrado.'; }
}
$list = (!$adminPage || $logged) && $project === null ? projects($storage) : [];
?><!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>FUTUREO STUDIO<?= $adminPage ? ' | Administración' : '' ?></title><link rel="icon" type="image/png" href="assets/icono.png"><link rel="stylesheet" href="assets/studio.css?v=0.1.12"><?php if ($adminPage && $logged && $project !== null): ?><link rel="stylesheet" href="assets/recorder.css?v=0.1.26"><link rel="stylesheet" href="assets/fx.css?v=0.1.19"><?php endif; ?></head>
<body<?= $adminPage && $logged ? ' class="admin-orientation' . ($project !== null ? ' workspace-open' : '') . '" data-orientation="horizontal"' : '' ?>>
<?php if (!($adminPage && $logged && $project !== null)): ?>
<header class="top"><a class="brand" href="<?= e($page) ?>"><img src="assets/logotipo.png" alt="FUTUREO" onerror="this.hidden=true;this.nextElementSibling.hidden=false"><b hidden>FUTUREO</b><span>STUDIO</span></a><nav><?php if ($adminPage && $logged): ?><a href="index.php">Vista pública</a><button type="button" class="subtle orientation-control" id="orientation-toggle" aria-label="Cambiar a vertical" aria-pressed="false" title="Cambiar a vertical"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><rect x="3" y="6" width="18" height="12" rx="2"/></svg><span id="orientation-label">Horizontal</span></button><form method="post" action="admin.php"><input type="hidden" name="csrf" value="<?= e($csrf) ?>"><button class="subtle" name="action" value="logout">Salir</button></form><?php elseif (!$adminPage): ?><a href="admin.php">Administración</a><?php else: ?><a href="index.php">Inicio</a><?php endif; ?></nav></header>
<?php endif; ?>
<?php if ($adminPage && !$logged): ?>
<main class="login-wrap"><section class="login"><img class="mark" src="assets/icono.png" alt="FUTUREO"><p class="eyebrow">FUTUREO STUDIO</p><h1>Iniciar sesión</h1><p class="muted">Acceso al panel de proyectos.</p><?php if ($error): ?><p class="error" role="alert"><?= e($error) ?></p><?php endif; ?><form method="post" action="admin.php"><input type="hidden" name="csrf" value="<?= e($csrf) ?>"><label for="user">Usuario</label><input id="user" name="user" autocomplete="username" required><label for="password">Contraseña</label><input id="password" name="password" type="password" autocomplete="current-password" required><button class="primary" name="action" value="login">Ingresar</button></form></section></main>
<?php elseif ($project !== null): ?>
<?php if ($adminPage && $logged): ?>
<details class="workspace-controls"><summary title="Controles del proyecto" aria-label="Controles del proyecto"><svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h16"/></svg></summary><div class="workspace-menu"><div class="brand workspace-brand"><img src="assets/logotipo.png" alt="FUTUREO" onerror="this.hidden=true;this.nextElementSibling.hidden=false"><b hidden>FUTUREO</b><span>STUDIO</span></div><span class="workspace-name"><?= e($project) ?></span><a class="subtle" href="admin.php">← Proyectos</a><button type="button" class="subtle orientation-control" id="orientation-toggle" aria-label="Cambiar a vertical" aria-pressed="false" title="Cambiar a vertical"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><rect x="3" y="6" width="18" height="12" rx="2"/></svg><span id="orientation-label">Horizontal</span></button><a class="subtle" href="index.php">Vista pública</a><form method="post" action="admin.php"><input type="hidden" name="csrf" value="<?= e($csrf) ?>"><button class="subtle" name="action" value="logout">Salir</button></form></div></details>
<div class="workspace-stage"><main class="workspace" aria-label="Grabadora multipista"><section class="voice-recorder" data-project="<?= e($project) ?>" data-csrf="<?= e($csrf) ?>" aria-label="Grabadora multipista de voz">
<div class="daw-heading"><span class="daw-track-label"><i></i> FUTUREO STUDIO · 4 PISTAS</span><span id="voice-saved">Sin grabaciones</span></div>
<div class="daw-timeline"><div class="track-list" id="voice-tracks" aria-label="Controles de las cuatro pistas">
<div class="track-row is-armed" data-track-row="1"><span class="track-chip">Pista 1</span><div class="track-actions"><button type="button" class="track-action rec is-armed" data-track="1" data-action="rec" aria-label="Armar pista 1" title="Seleccionar pista para grabar" aria-pressed="true">REC</button><button type="button" class="track-action mute" data-track="1" data-action="mute" aria-label="Silenciar pista 1" title="Silenciar / activar sonido" aria-pressed="false">MUTE</button><button type="button" class="track-action fx" data-track="1" data-action="fx" aria-label="FX de pista 1" title="Abrir efectos de la pista" aria-pressed="false">FX</button></div></div>
<div class="track-row" data-track-row="2"><span class="track-chip">Pista 2</span><div class="track-actions"><button type="button" class="track-action rec" data-track="2" data-action="rec" aria-label="Armar pista 2" title="Seleccionar pista para grabar" aria-pressed="false">REC</button><button type="button" class="track-action mute" data-track="2" data-action="mute" aria-label="Silenciar pista 2" title="Silenciar / activar sonido" aria-pressed="false">MUTE</button><button type="button" class="track-action fx" data-track="2" data-action="fx" aria-label="FX de pista 2" title="Abrir efectos de la pista" aria-pressed="false">FX</button></div></div>
<div class="track-row" data-track-row="3"><span class="track-chip">Pista 3</span><div class="track-actions"><button type="button" class="track-action rec" data-track="3" data-action="rec" aria-label="Armar pista 3" title="Seleccionar pista para grabar" aria-pressed="false">REC</button><button type="button" class="track-action mute" data-track="3" data-action="mute" aria-label="Silenciar pista 3" title="Silenciar / activar sonido" aria-pressed="false">MUTE</button><button type="button" class="track-action fx" data-track="3" data-action="fx" aria-label="FX de pista 3" title="Abrir efectos de la pista" aria-pressed="false">FX</button></div></div>
<div class="track-row" data-track-row="4"><span class="track-chip">Pista 4</span><div class="track-actions"><button type="button" class="track-action rec" data-track="4" data-action="rec" aria-label="Armar pista 4" title="Seleccionar pista para grabar" aria-pressed="false">REC</button><button type="button" class="track-action mute" data-track="4" data-action="mute" aria-label="Silenciar pista 4" title="Silenciar / activar sonido" aria-pressed="false">MUTE</button><button type="button" class="track-action fx" data-track="4" data-action="fx" aria-label="FX de pista 4" title="Abrir efectos de la pista" aria-pressed="false">FX</button></div></div>
</div>
<canvas id="voice-canvas" data-tool="pointer" role="slider" tabindex="0" aria-label="Línea de tiempo: arrastra archivos MP3 o selecciona una herramienta de edición" aria-valuemin="0" aria-valuenow="0" aria-valuemax="30"></canvas></div>
<div class="daw-transport"><div class="daw-buttons"><button type="button" class="daw-button" id="voice-home" aria-label="Ir al inicio" title="Inicio">|◀</button><button type="button" class="daw-button" id="voice-play" disabled aria-label="Reproducir" title="Reproducir">▶</button><button type="button" class="daw-button" id="voice-stop" disabled aria-label="Detener" title="Detener">■</button><button type="button" class="record-button" id="voice-record" disabled aria-label="Grabar voz" title="Grabar voz"><span></span></button></div><div class="daw-tools" role="group" aria-label="Herramientas de edición"><button type="button" class="daw-tool" data-tool="pointer" aria-label="Puntero (V)" title="Puntero (V)" aria-pressed="true"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 3l15 10-7 1.4-3 6.6z"/></svg></button><button type="button" class="daw-tool" data-tool="hand" aria-label="Mano: mover clips (H)" title="Mano: mover clips (H)" aria-pressed="false"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M8 13V5a2 2 0 014 0v7-9a2 2 0 014 0v9-6a2 2 0 014 0v10a6 6 0 01-6 6h-2a6 6 0 01-5-3l-4-6a2 2 0 013-2z"/></svg></button><button type="button" class="daw-tool" data-tool="cut" aria-label="Cúter: dividir (C)" title="Cúter: dividir (C)" aria-pressed="false"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 17L17 3l4 4-14 14H3zM14 6l4 4M4 16l4 4M10 12l2 2"/></svg></button><button type="button" class="daw-tool" data-tool="erase" aria-label="Borrar clip (E)" title="Borrar clip (E)" aria-pressed="false"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7M14 10v7"/></svg></button></div><div class="daw-history" role="group" aria-label="Historial de edición"><button type="button" class="daw-tool" id="voice-undo" aria-label="Deshacer (Ctrl+Z)" title="Deshacer (Ctrl+Z)" disabled><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 14 4 9l5-5M4 9h10a6 6 0 0 1 0 12h-3"/></svg></button><button type="button" class="daw-tool" id="voice-redo" aria-label="Rehacer (Ctrl+Y)" title="Rehacer (Ctrl+Y)" disabled><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m15 14 5-5-5-5m5 5H10a6 6 0 0 0 0 12h3"/></svg></button></div><button type="button" class="daw-tool daw-import" id="voice-import" title="Importar MP3 a la pista armada" aria-label="Importar archivos MP3" disabled><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/></svg><span>MP3</span></button><input type="file" id="voice-files" accept=".mp3,audio/mpeg" multiple hidden><div class="record-meta"><details class="sync-control" id="voice-sync" data-measured="false"><summary title="Alineación automática después de grabar">SYNC AUTO</summary><div class="sync-panel"><strong>SYNC por referencia</strong><small>Graba directamente. El sistema conserva la voz completa y analiza el acompañamiento al detener. No necesitas realizar una prueba de pulsos.</small><small>Con auriculares aislados puede no existir retorno audible en el micrófono. En ese caso se aplica una estimación y se indica el método utilizado.</small><label style="display:flex;align-items:center;gap:7px;font-size:12px"><input type="checkbox" id="voice-sync-dry"> Escucha directa sin FX (prueba)</label><small>La prueba directa desactiva temporalmente el procesamiento de las pistas, sin cambiar tus presets.</small><small id="voice-sync-info" role="status" aria-live="polite">La próxima toma se alineará automáticamente.</small></div></details><div class="record-arm">Armada: <strong id="voice-track-name">Pista 1</strong></div><div class="record-clock" id="voice-clock">00:00.0</div></div></div>
<p class="record-status" id="voice-status" role="status" aria-live="polite">Cargando pistas...</p>
<div class="record-recovery" id="voice-recovery" hidden><button type="button" class="subtle" id="voice-retry">Reintentar guardado</button><a class="subtle" id="voice-download" download>Descargar WAV</a><button type="button" class="subtle" id="voice-discard">Cerrar toma</button></div>
<audio id="voice-audio" preload="metadata" hidden></audio>
</section></main></div>
<?php else: ?><div class="workspace-bar"><a href="<?= e($page) ?>">← Proyectos</a><span><?= e($project) ?></span></div><main class="workspace" aria-label="Espacio de trabajo vacío"></main><?php endif; ?>
<?php else: ?>
<main class="dashboard"><?php if ($adminPage): ?><div class="intro"><div><p class="eyebrow">ADMINISTRACIÓN</p><h1>Proyectos</h1><p class="muted">Crea y abre tus proyectos locales.</p></div><span class="count"><?= count($list) ?> proyectos</span></div><?php endif; ?>
<?php if ($error): ?><p class="error" role="alert"><?= e($error) ?></p><?php endif; ?>
<?php if (!$list && $adminPage): ?><section class="empty"><div class="empty-icon">▱</div><h2>Sin proyectos todavía</h2><p>Pulsa Nuevo para comenzar.</p></section><?php elseif ($list): ?><section class="grid" aria-label="Proyectos"><?php foreach ($list as $item): ?><a class="project" href="<?= e($page . '?project=' . rawurlencode($item['name'])) ?>"><span class="file-icon">F</span><div class="project-info"><strong><?= e($item['name']) ?></strong><small><?= e(date('d/m/Y H:i', $item['mtime'])) ?> · FPRJ</small></div><span class="arrow">↗</span></a><?php endforeach; ?></section><?php endif; ?>
</main>
<?php if ($adminPage): ?><form class="new-form" method="post" action="admin.php"><input type="hidden" name="csrf" value="<?= e($csrf) ?>"><button class="fab" name="action" value="new"><span>＋</span> Nuevo</button></form><?php endif; ?>
<?php endif; ?>
<?php if ($adminPage && $logged): ?>
<script>
(() => {
    const button = document.getElementById('orientation-toggle');
    const label = document.getElementById('orientation-label');
    const controls = document.querySelector('.workspace-controls');
    if (controls) {
        document.addEventListener('click', (event) => {
            if (controls.open && !controls.contains(event.target)) controls.open = false;
        });
        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape' && controls.open) {
                controls.open = false;
                controls.querySelector('summary').focus();
            }
        });
    }
    const key = 'futureo.studio.orientation';
    let orientation = 'horizontal';
    try { if (localStorage.getItem(key) === 'vertical') orientation = 'vertical'; } catch (_) {}
    function render() {
        const vertical = orientation === 'vertical';
        document.body.dataset.orientation = orientation;
        label.textContent = vertical ? 'Vertical' : 'Horizontal';
        button.setAttribute('aria-pressed', String(vertical));
        const hint = vertical ? 'Cambiar a horizontal' : 'Cambiar a vertical';
        button.title = hint;
        button.setAttribute('aria-label', hint);
    }
    button.addEventListener('click', () => {
        orientation = orientation === 'vertical' ? 'horizontal' : 'vertical';
        try { localStorage.setItem(key, orientation); } catch (_) {}
        render();
    });
    render();
})();
</script>
<?php endif; ?>
<?php if ($adminPage && $logged && $project !== null): ?><script src="assets/fx.js?v=0.1.24"></script><script src="assets/adaptive-sync.js?v=0.1.26"></script><script src="assets/recorder.js?v=0.1.26"></script><?php endif; ?>
</body></html>
