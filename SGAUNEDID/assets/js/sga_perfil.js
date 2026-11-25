// SGA UNEDID - perfil en ventana flotante y apertura del modal de contrasena.
(() => {
  const dialog = document.getElementById('sga-perfil-dialog');
  const trigger = document.getElementById('sga-perfil-open');
  if (!dialog || !trigger || typeof dialog.showModal !== 'function') return;

  // El menu lateral solo debe estar inerte cuando esta oculto en movil.
  // En escritorio siempre debe poder recibir clics tras cerrar el perfil.
  function sincronizarMenu() {
    const movil = window.matchMedia('(max-width: 760px)').matches;
    document.documentElement.classList.remove('sga-menu-open');
    const btnMenu = document.getElementById('sga-menu-open');
    if (btnMenu) btnMenu.setAttribute('aria-expanded', 'false');
    const menu = document.getElementById('sga-sidebar');
    if (menu) {
      menu.inert = movil;
      menu.setAttribute('aria-hidden', movil ? 'true' : 'false');
    }
    document.getElementById('sga-menu-scrim')?.setAttribute('aria-hidden', 'true');
  }
  function abrir() {
    // Cierra el menu movil, pero no bloquea el sidebar de escritorio.
    sincronizarMenu();
    if (!dialog.open) dialog.showModal();
  }
  trigger.addEventListener('click', (e) => {e.preventDefault(); abrir();});
  for (const id of ['sga-perfil-cerrar','sga-perfil-listo']) {
    document.getElementById(id)?.addEventListener('click', () => dialog.close());
  }
  dialog.addEventListener('click', (event) => {
    if (event.target !== dialog) return;
    const box = dialog.getBoundingClientRect();
    if (event.clientX < box.left || event.clientX > box.right ||
        event.clientY < box.top || event.clientY > box.bottom) dialog.close();
  });
  // Cambiar contrasena abre el modal existente; no se crean dos formularios.
  document.getElementById('sga-password-open')?.addEventListener('click', () => {
    if (dialog.open) dialog.close();
  }, {capture: true});
  dialog.addEventListener('close', () => {
    document.getElementById('sga-perfil-subir-form')?.reset();
    sincronizarMenu();
  });
  const formEliminar = document.getElementById('sga-perfil-borrar-form');
  formEliminar?.querySelector('button[type=submit]')?.addEventListener('click', (e) => {
    if (!window.confirm('Eliminar tu foto y usar las iniciales del apellido y nombre?')) e.preventDefault();
  });
  if (dialog.dataset.reopen === '1') {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', abrir, {once:true});
    else abrir();
  }
})();
