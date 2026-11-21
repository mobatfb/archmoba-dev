<?php
declare(strict_types=1);
header('Content-Type: text/html; charset=utf-8');
header('X-Content-Type-Options: nosniff');
header('Referrer-Policy: no-referrer');
header('Cache-Control: no-store, private');
header("Content-Security-Policy: default-src 'none'; style-src 'self'; script-src 'self'; connect-src 'self' https: wss:; img-src 'self' data:; font-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'");
?>
<!doctype html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#071322">
<meta name="description" content="Control remoto web de KOFMULTI compatible con P1, P2 y lista de espera.">
<title>KOFMULTI · Multimando Web</title>
<link rel="stylesheet" href="assets/estilo.css?v=1.0.0">
<script src="control.php?v=1.0.0" defer></script>
</head>
<body>
<main class="shell">
<header class="topbar">
  <div class="identity"><span class="mark" aria-hidden="true">K</span><div><strong>KOFMULTI</strong><small>CONTROL WEB · v1.0</small></div></div>
  <span class="status-pill off" id="stateTag"><span class="dot"></span><span id="statusText">Desconectado</span></span>
</header>
<section class="connect-panel" aria-label="Conexión de sala">
  <div class="connect-form">
    <label>Nombre del jugador<input id="playerName" type="text" maxlength="24" autocomplete="nickname" spellcheck="false" placeholder="Tu nombre único"></label>
    <label>Enlace directo <span class="optional">opcional</span><input id="directUrl" type="text" inputmode="url" autocomplete="off" spellcheck="false" placeholder="Vacío = buscar por API"></label>
    <div class="connect-buttons"><button id="connectBtn" class="btn primary" type="button">CONECTAR</button><button id="disconnectBtn" class="btn outline" type="button" disabled>DESCONECTAR</button></div>
  </div>
  <div class="session-strip" aria-live="polite"><div><small>CONTROL</small><strong id="slotLabel">—</strong></div><div><small>TURNO</small><strong id="queueLabel">—</strong></div><div><small>TIEMPO</small><strong id="timerLabel">—</strong></div><div><small>SALA ID</small><strong id="roomId">—</strong></div></div>
</section>
<section class="game-panel" aria-label="Mando">
  <div class="game-head"><div><strong>ARENA KOF 2002</strong><p id="modeLabel">Sin sala activa</p></div><span class="pad-badge" id="padBadge">Sin asignar</span></div>
  <div class="controls-grid">
    <div class="dpad" aria-label="Cruceta direccional">
      <button class="padkey up" data-action="UP" aria-label="Arriba" type="button">▲</button>
      <button class="padkey left" data-action="LEFT" aria-label="Izquierda" type="button">◀</button>
      <span class="padcenter" aria-hidden="true"></span>
      <button class="padkey right" data-action="RIGHT" aria-label="Derecha" type="button">▶</button>
      <button class="padkey down" data-action="DOWN" aria-label="Abajo" type="button">▼</button>
    </div>
    <div class="mid-controls">
      <button class="utility" data-action="COIN" type="button">COIN</button>
      <button class="start" data-action="START" id="startBtn" type="button">CONECTAR</button>
      <small>ENTER = COIN + START</small>
    </div>
    <div class="fight-buttons" aria-label="Golpes y patadas">
      <button class="attack a" data-action="A" type="button">A</button><button class="attack s" data-action="S" type="button">S</button>
      <button class="attack z" data-action="Z" type="button">Z</button><button class="attack x" data-action="X" type="button">X</button>
    </div>
  </div>
  <p class="help-text">Teclado: <strong>↑ ↓ ← →</strong> mover · <strong>A S Z X</strong> combatir · <strong>Enter</strong> iniciar · <strong>5</strong> moneda. También admite controles táctiles y gamepads estándar.</p>
</section>
<section class="activity" aria-label="Actividad y conexión"><div class="activity-heading"><strong>ACTIVIDAD</strong><span id="playersLabel">—</span></div><div id="eventLog" class="log" role="log" aria-live="polite" aria-relevant="additions"></div></section>
<footer>Compatible con KOF_Anfitrion.py · Las teclas solo se detectan con esta pestaña activa.</footer>
</main>
</body>
</html>
