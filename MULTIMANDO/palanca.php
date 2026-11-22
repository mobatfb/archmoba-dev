<?php
declare(strict_types=1);
header('Content-Type: text/html; charset=utf-8');
header('Cache-Control: private, no-store');
header('X-Content-Type-Options: nosniff');
header('Referrer-Policy: no-referrer');
header("Content-Security-Policy: default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self' wss:; font-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'");
?>
<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#071222">
<meta name="description" content="MULTIMANDO, control remoto web de una sola pantalla. La administración de jugadores y turnos está exclusivamente en Python.">
<title>MULTIMANDO | Control remoto</title>
<link rel="stylesheet" href="assets/palanca.css?v=2.0.0">
<script src="control.php?v=2.0.0" defer></script>
</head>
<body>
<main class="app-shell">
  <header class="app-header">
    <div class="brand"><div class="brand-mark" aria-hidden="true">M<span class="brand-spark"></span></div>
      <div><strong>MULTIMANDO</strong><small>CONTROL REMOTO WEB</small></div></div>
    <div class="connection-pill" id="connectionPill" role="status"><span class="pulse"></span><span id="connectionText">SIN CONEXIÓN</span></div>
  </header>

  <section class="connect-panel" aria-label="Conectar control remoto">
    <label class="nickname-field"><span>JUGADOR</span><input id="nickname" type="text" maxlength="24" autocomplete="nickname" spellcheck="false" placeholder="Escribe tu nombre" aria-label="Nombre del jugador"></label>
    <div class="connect-tools">
      <details class="manual-connection" id="manualConnection">
        <summary title="Pegar enlace directo de la sala" aria-label="Configurar enlace directo"><span aria-hidden="true">🔗</span><span class="manual-label">URL</span></summary>
        <div class="manual-popover"><label for="directUrl">ENLACE DIRECTO DE LA SALA</label><input id="directUrl" type="url" autocomplete="off" spellcheck="false" placeholder="https://...trycloudflare.com/"><small>Déjalo vacío para buscar la sala automáticamente por API.</small></div>
      </details>
      <button class="connect-btn" type="button" id="connectBtn">CONECTAR</button>
      <button class="disconnect-btn" type="button" id="disconnectBtn" disabled>SALIR</button>
    </div>
    <p class="error-text" id="connectionError" role="alert" hidden></p>
  </section>

  <section class="status-hud" aria-label="Estado de tu control">
    <div class="stat"><span>MI CONTROL</span><strong id="mySlot">—</strong><small id="myStatus">Sin asignar</small></div>
    <div class="stat"><span>TIEMPO RESTANTE</span><strong class="mono" id="timeLeft">--:--</strong><small id="clockStatus">Definido por el anfitrión</small></div>
    <div class="stat"><span>EN ESPERA</span><strong class="mono" id="queueCount">—</strong><small id="myQueuePosition">Sin conexión</small></div>
  </section>

  <section class="control-deck" aria-label="Palanca y botones remotos">
    <div class="deck-header">
      <div class="deck-title"><span class="tiny-led"></span><strong>PALANCA DIGITAL</strong><small id="roomId">SALA —</small></div>
      <div class="deck-badges"><span id="gamepadStatus">TECLADO · TÁCTIL</span><span class="slot-indicator" id="slotIndicator">SIN TURNO</span></div>
    </div>
    <div class="controls" id="controllerArea">
      <div class="joystick-zone">
        <span class="control-label">8 DIRECCIONES</span>
        <div class="joystick-frame" id="joystick" tabindex="0" role="application" aria-label="Palanca direccional táctil, arrastra para mover; usa también las flechas del teclado">
          <span class="joystick-label north">▲</span><span class="joystick-label east">▶</span><span class="joystick-label south">▼</span><span class="joystick-label west">◀</span>
          <div class="joystick-grid" aria-hidden="true"></div>
          <div class="joystick-base" aria-hidden="true"><div class="joystick-thumb" id="joystickThumb"><span class="thumb-light"></span></div></div>
        </div>
        <span class="micro-hint">MUEVE · ARRASTRA · DIAGONALES</span>
      </div>
      <div class="action-zone">
        <span class="control-label">ACCIONES</span>
        <div class="action-buttons">
          <button class="action-btn btn-a" type="button" data-action="A" aria-label="Botón A">A</button>
          <button class="action-btn btn-s" type="button" data-action="C" aria-label="Botón S">S</button>
          <button class="action-btn btn-z" type="button" data-action="B" aria-label="Botón Z">Z</button>
          <button class="action-btn btn-x" type="button" data-action="D" aria-label="Botón X">X</button>
        </div>
        <div class="aux-buttons">
          <button class="aux-btn" type="button" data-action="SELECT">SELECT</button>
          <button class="aux-btn aux-primary" type="button" data-action="START">START</button>
        </div>
        <span class="micro-hint">A · S · Z · X / ENTER · 5</span>
      </div>
    </div>
    <div class="deck-footer"><span class="feedback-indicator" aria-hidden="true"></span><p id="feedback" aria-live="polite">Escribe tu nombre y pulsa CONECTAR.</p><span id="connectionSource">API MULTIMANDO</span></div>
  </section>
  <footer>SOLO CONTROL REMOTO · JUGADORES, COLA Y TURNOS ADMINISTRADOS POR PYTHON</footer>
</main>
</body>
</html>