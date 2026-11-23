/* MULTIMANDO v2.2.1: verificador pasivo del modulo de control.
 * No modifica WebSocket, turnos ni botones. Solo explica fallos de arranque.
 * El sistema de imagen se carga independientemente del modulo del mando.
 */
(() => {
  "use strict";
  function display(message) {
    const warn = document.getElementById("controllerDiagnostic");
    if (!warn) return;
    warn.textContent = message;
    warn.hidden = false;
  }
  document.addEventListener("DOMContentLoaded", () => {
    const label = document.getElementById("connectionText");
    const connect = document.getElementById("connectBtn");
    if (!connect || !label) return;

    // control.php agrega el indicador SOLAMENTE cuando el modulo AES-GCM
    // ha sido descifrado y ejecutado. El secreto jamas viaja al navegador.
    if (window.__MULTIMANDO_CONTROL_MODULE_LOADED__ !== true) {
      display("MANDO NO DISPONIBLE: no cargo control.php. En tu hosting, conserva "
        + "private/FRASE_CIFRADO.php y el archivo private/palanca.enc compatible. "
        + "La imagen del juego puede funcionar aunque el mando no se cargue.");
      return;
    }
    connect.addEventListener("click", () => {
      const start = performance.now();
      setTimeout(() => {
        const current = (label.textContent || "").toLowerCase();
        if ((current.includes("sin conexión") || current.includes("sin conexion")
            || current.includes("error") || current.includes("desconect")) &&
            performance.now() - start > 9500) {
          display("El mando no confirmo conexion. Revisa que el anfitrion v2.2.1 "
            + "tenga la sala ABIERTA, el enlace Cloudflare publicado "
            + "y que el navegador use la URL actual (modo AUTO).");
        }
      }, 10500);
    });
  });
})();
