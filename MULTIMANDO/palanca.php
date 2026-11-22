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
<link rel="stylesheet" href="assets/palanca.css?v=5.0.0">
<script src="control.php?v=5.2.0" defer></script>
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
      <div class="deck-badges"><button type="button" class="keys-config-btn" id="openKeys" title="Personalizar teclas del mando">TECLAS</button><span id="gamepadStatus">TECLADO · TÁCTIL</span><span class="slot-indicator" id="slotIndicator">SIN TURNO</span></div>
    </div>
    <div class="controls" id="controllerArea">
      <div class="joystick-zone">
        <span class="control-label">8 DIRECCIONES</span>
        <div class="joystick-frame" id="joystick" tabindex="0" role="application" aria-label="Palanca direccional; usa WASD, cruceta física o arrastra con el dedo o ratón">
          <span class="joystick-label north">▲</span><span class="joystick-label east">▶</span><span class="joystick-label south">▼</span><span class="joystick-label west">◀</span>
          <div class="joystick-grid" aria-hidden="true"></div>
          <div class="joystick-base" aria-hidden="true"><div class="joystick-thumb" id="joystickThumb"><span class="thumb-light"></span></div></div>
        </div>
        <span class="micro-hint">MUEVE · ARRASTRA · DIAGONALES</span>
      </div>
      <div class="action-zone">
        <span class="control-label">ACCIONES</span>
        <div class="action-buttons" aria-label="Seis botones en dos filas: A B C y D E F">
          <button class="action-btn btn-a" type="button" data-action="ba" aria-label="Botón A">A</button>
          <button class="action-btn btn-b" type="button" data-action="bb" aria-label="Botón B">B</button>
          <button class="action-btn btn-c" type="button" data-action="bc" aria-label="Botón C">C</button>
          <button class="action-btn btn-d" type="button" data-action="bd" aria-label="Botón D">D</button>
          <button class="action-btn btn-e" type="button" data-action="be" aria-label="Botón E">E</button>
          <button class="action-btn btn-f" type="button" data-action="bf" aria-label="Botón F">F</button>
        </div>
        <div class="aux-buttons">
          <button class="aux-btn" type="button" data-action="select" title="SELECT: tecla Retroceso (Backspace)">SELECT</button>
          <button class="aux-btn aux-primary" type="button" data-action="start">START</button>
        </div>
        <span class="micro-hint">WASD · U I O / J K L</span>
      </div>
    </div>
    <div class="deck-footer"><span class="feedback-indicator" aria-hidden="true"></span><p id="feedback" aria-live="polite">Escribe tu nombre y pulsa CONECTAR.</p><span id="connectionSource">API MULTIMANDO</span></div>
  </section>
  <dialog id="keyDialog" class="key-dialog" aria-labelledby="keyDialogTitle">
    <div class="key-dialog-head"><div><strong id="keyDialogTitle">CONFIGURAR TECLAS</strong><small>PERFIL: WASD + U I O / J K L · SELECT = RETROCESO. Los comandos enviados no cambian.</small></div><button type="button" id="closeKeys" class="key-dialog-close" aria-label="Cerrar configuración">CERRAR</button></div>
    <p class="key-instructions">Pulsa una opción y luego la tecla que quieras asignarle. Las asignaciones se guardan en este navegador. RESTAURAR TECLAS activa el perfil predeterminado.</p>
    <div id="keyGrid" class="key-grid" aria-label="Asignación de teclas"></div>
    <p id="keyMessage" class="key-message" role="status">Configuración lista.</p>
    <div class="key-dialog-foot"><button id="resetKeys" type="button">RESTAURAR TECLAS</button><button type="button" id="saveKeys">LISTO</button></div>
  </dialog>
  <footer>SOLO CONTROL REMOTO · JUGADORES, COLA Y TURNOS ADMINISTRADOS POR PYTHON</footer>
</main>
</body>
</html>