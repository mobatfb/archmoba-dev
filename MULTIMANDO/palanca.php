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
<meta name="theme-color" content="#071326">
<meta name="description" content="MULTIMANDO: palanca de control remoto con turnos y lista de espera.">
<title>MULTIMANDO | Palanca Web</title>
<link rel="stylesheet" href="assets/palanca.css?v=1.0.0">
<script src="control.php?v=1.0.0" defer></script>
</head>
<body>
<main class="app-shell">
  <header class="app-header">
    <div class="brand"><div class="brand-mark" aria-hidden="true">M<span class="brand-spark"></span></div>
      <div><strong>MULTIMANDO</strong><small>CONTROL REMOTO · PALANCA WEB</small></div></div>
    <div class="connection-pill" id="connectionPill"><span class="pulse"></span><span id="connectionText">SIN CONEXIÓN</span></div>
  </header>

  <section class="connect-card" aria-label="Acceso a sala">
    <div class="panel-heading"><span class="eyebrow">01 / ACCESO</span><h1>Conecta tu mando</h1><p>Introduce un nombre único. La sala se obtiene automáticamente de la API de MULTIMANDO.</p></div>
    <div class="login-grid">
      <label class="field">NOMBRE DEL JUGADOR<input id="nickname" type="text" maxlength="24" autocomplete="nickname" placeholder="Tu nombre" spellcheck="false"></label>
      <label class="field">ENLACE DIRECTO <small>(OPCIONAL)</small><input id="directUrl" type="url" autocomplete="off" spellcheck="false" placeholder="Automático desde la API"></label>
      <div class="login-actions"><button class="btn btn-primary" id="connectBtn" type="button">CONECTAR <span aria-hidden="true">↗</span></button><button class="btn btn-ghost" id="disconnectBtn" type="button" disabled>SALIR</button></div>
    </div>
    <p id="connectionError" class="error-text" role="alert" hidden></p>
  </section>

  <section class="dashboard" aria-label="Estado de la sala">
    <div class="stat"><span>MI PUESTO</span><strong id="mySlot">—</strong><small id="myStatus">Sin asignar</small></div>
    <div class="stat"><span>MI TURNO</span><strong class="mono" id="timeLeft">10:00</strong><small id="clockStatus">En espera de conexión</small></div>
    <div class="stat"><span>PERSONAS EN COLA</span><strong class="mono" id="queueCount">0</strong><small id="myQueuePosition">Sin cola</small></div>
    <div class="stat"><span>SALA</span><strong class="mono room-number" id="roomId">—</strong><small id="connectionSource">API MULTIMANDO</small></div>
  </section>

  <section class="controller-card" aria-label="Mando remoto">
    <div class="controller-title"><div><span class="eyebrow">02 / CONTROL</span><h2>Tu palanca digital</h2></div><div class="controller-side"><span class="badge" id="gamepadStatus">TECLADO / TÁCTIL</span><span class="slot-indicator" id="slotIndicator">SIN TURNO</span></div></div>
    <div class="controller-layout" id="controllerArea">
      <div class="joystick-column">
        <div class="input-name">PALANCA · 8 DIRECCIONES</div>
        <div class="joystick-frame" id="joystick" role="application" tabindex="0" aria-label="Palanca direccional. Arrastra para mover, o usa las flechas del teclado.">
          <span class="joystick-label north">▲</span><span class="joystick-label east">▶</span><span class="joystick-label south">▼</span><span class="joystick-label west">◀</span>
          <div class="joystick-grid" aria-hidden="true"><span></span><span></span></div>
          <div class="joystick-base" aria-hidden="true"><div class="joystick-thumb" id="joystickThumb"><div class="thumb-light"></div></div></div>
        </div>
        <div class="joystick-hint">ARRASTRA PARA MOVER · ADMITE DIAGONALES</div>
      </div>
      <div class="button-column">
        <div class="input-name">BOTONES DE ACCIÓN</div>
        <div class="action-buttons" aria-label="Botones A S Z X">
          <button class="action-btn btn-a" type="button" data-action="A" aria-label="Botón A">A<small>TECLA A</small></button>
          <button class="action-btn btn-s" type="button" data-action="C" aria-label="Botón S">S<small>TECLA S</small></button>
          <button class="action-btn btn-z" type="button" data-action="B" aria-label="Botón Z">Z<small>TECLA Z</small></button>
          <button class="action-btn btn-x" type="button" data-action="D" aria-label="Botón X">X<small>TECLA X</small></button>
        </div>
        <div class="aux-buttons"><button class="aux-btn" type="button" data-action="SELECT"><span class="small-bar"></span> SELECT</button><button class="aux-btn aux-primary" type="button" data-action="START"><span class="small-bar"></span> START</button></div>
        <p class="keyboard-hint">TECLADO: <strong>↑ ↓ ← →</strong> · <strong>A S Z X</strong> · <strong>ENTER</strong> / <strong>5</strong></p>
      </div>
    </div>
  </section>

  <section class="queue-grid" aria-label="Jugadores y lista de espera">
    <div class="queue-panel">
      <div class="section-title"><div><span class="eyebrow">03 / EN JUEGO</span><h2>Mandos ocupados</h2></div><button class="text-button" type="button" id="yieldBtn" disabled>CEDER MI TURNO</button></div>
      <div class="player-slot" id="slotOne"><span class="player-id">P1</span><div><strong id="playerOne">LIBRE</strong><small id="p1Timer">Esperando jugador</small></div><span class="slot-dot"></span></div>
      <div class="player-slot" id="slotTwo"><span class="player-id">P2</span><div><strong id="playerTwo">LIBRE</strong><small id="p2Timer">Esperando jugador</small></div><span class="slot-dot"></span></div>
    </div>
    <div class="queue-panel">
      <div class="section-title"><div><span class="eyebrow">04 / SIGUIENTES</span><h2>Lista de espera</h2></div><button class="text-button" type="button" id="requestBtn" disabled>PEDIR TURNO</button></div>
      <ol class="queue-list" id="queueList"><li class="queue-empty">No hay personas esperando</li></ol>
      <p class="queue-note">El reloj de 10 minutos <strong>solo corre si hay alguien en cola</strong>. Si la cola se vacía, se pausa.</p>
    </div>
  </section>

  <section class="events-panel"><div class="events-title"><span class="eyebrow">REGISTRO DE ACTIVIDAD</span><button type="button" class="text-button" id="clearLogBtn">LIMPIAR</button></div><div class="event-list" id="eventLog" aria-live="polite" role="log"><div class="log-item">MULTIMANDO listo. Introduce tu nombre para conectar.</div></div></section>
  <footer>Proyecto independiente MULTIMANDO · Enlace obtenido desde /api/geturlmultimando · Los tiempos y turnos los administra el anfitrión Python.</footer>
</main>
</body>
</html>