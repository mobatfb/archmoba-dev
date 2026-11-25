/* SGA UNEDID - Ojo para campos de contrasena (V1.5.5).
 * No cambia el nombre de los campos, los valores ni las validaciones PHP.
 * Funcionamiento con teclados, pantalla tactil y formularios dinamicos.
 */
(() => {
  'use strict';
  const INPUT_MARK = 'sgaEyeReady';
  const EYE = '<svg xmlns="http://www.w3.org/2000/svg" aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>';
  const EYE_OFF = '<svg xmlns="http://www.w3.org/2000/svg" aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3 21 21"/><path d="M10.6 5.1A10.7 10.7 0 0 1 12 5c6.4 0 10 7 10 7a16 16 0 0 1-3.1 3.7"/><path d="M6.4 6.4C3.6 8.2 2 12 2 12s3.6 7 10 7a10.6 10.6 0 0 0 4.3-.9"/><path d="M10.6 10.6a2 2 0 0 0 2.8 2.8"/></svg>';

  function addStyles() {
    if (document.getElementById('sga-eye-styles')) return;
    const style = document.createElement('style');
    style.id = 'sga-eye-styles';
    style.textContent = `
      .sga-eye-wrap{position:relative;display:block;width:100%;max-width:100%;min-width:0;box-sizing:border-box}
      .sga-eye-wrap>input{box-sizing:border-box;width:100%!important;max-width:100%;padding-right:52px!important;margin:0!important}
      .sga-eye-wrap>.sga-eye-btn{position:absolute;right:5px;top:50%;transform:translateY(-50%);display:grid;place-items:center;width:40px;height:37px;min-width:40px;min-height:37px;padding:6px;border:0;border-radius:8px;background:transparent;color:#526780;cursor:pointer;box-shadow:none;line-height:1;z-index:1;touch-action:manipulation}
      .sga-eye-wrap>.sga-eye-btn svg{display:block;width:21px;height:21px;pointer-events:none}
      .sga-eye-wrap>.sga-eye-btn:hover{background:rgba(13,79,157,.09);color:#0d4f9d}
      .sga-eye-wrap>.sga-eye-btn:focus-visible{outline:2px solid #0d4f9d;outline-offset:1px}
      .sga-eye-wrap>.sga-eye-btn[aria-pressed="true"]{color:#0d4f9d}
      @media(hover:none){.sga-eye-wrap>.sga-eye-btn{width:43px;height:43px;min-width:43px;min-height:43px}}
    `;
    document.head.appendChild(style);
  }

  let idCounter = 0;
  function enhance(input) {
    if (!(input instanceof HTMLInputElement) || input.type !== 'password' || input.dataset[INPUT_MARK] === '1') return;
    if (!input.parentNode) return;
    const focused = document.activeElement === input;
    const computed = window.getComputedStyle(input);
    const wrapper = document.createElement('span');
    wrapper.className = 'sga-eye-wrap';
    // Mantener el espaciado original, incluido el formulario de recuperacion.
    wrapper.style.margin = computed.margin;
    // En campos incluidos dentro de <label>, usar un control con role=button
    // evita anidar dos controles de formulario dentro de la etiqueta.
    const button = document.createElement(input.closest('label') ? 'span' : 'button');
    if (button.tagName === 'BUTTON') button.type = 'button';
    else { button.setAttribute('role', 'button'); button.tabIndex = 0; }
    button.className = 'sga-eye-btn';
    button.setAttribute('aria-pressed', 'false');
    const fieldId = input.id || ('sga-eye-field-' + (++idCounter));
    if (!input.id) input.id = fieldId;
    button.setAttribute('aria-controls', fieldId);

    const update = (shown) => {
      input.type = shown ? 'text' : 'password';
      button.setAttribute('aria-label', shown ? 'Ocultar contrase\u00f1a' : 'Mostrar contrase\u00f1a');
      button.setAttribute('title', shown ? 'Ocultar contrase\u00f1a' : 'Mostrar contrase\u00f1a');
      button.setAttribute('aria-pressed', shown ? 'true' : 'false');
      button.innerHTML = shown ? EYE_OFF : EYE;
    };
    const onToggle = () => update(input.type === 'password');
    button.addEventListener('click', onToggle);
    if (button.tagName !== 'BUTTON') {
      button.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          onToggle();
        }
      });
    }

    input.dataset[INPUT_MARK] = '1';
    input.parentNode.insertBefore(wrapper, input);
    wrapper.append(input, button);
    update(false);
    if (focused) input.focus({preventScroll: true});
  }

  function scan(node) {
    if (node.nodeType !== Node.ELEMENT_NODE && node.nodeType !== Node.DOCUMENT_NODE) return;
    if (node.matches && node.matches('input[type="password"]')) enhance(node);
    if (node.querySelectorAll) node.querySelectorAll('input[type="password"]').forEach(enhance);
  }

  function hideAll(container) {
    if (!container.querySelectorAll) return;
    container.querySelectorAll('input[data-sga-eye-ready="1"]').forEach((input) => {
      if (input.type !== 'text') return;
      const button = input.parentNode && input.parentNode.querySelector('.sga-eye-btn');
      if (!button) return;
      input.type = 'password';
      button.setAttribute('aria-label', 'Mostrar contrase\u00f1a');
      button.setAttribute('title', 'Mostrar contrase\u00f1a');
      button.setAttribute('aria-pressed', 'false');
      button.innerHTML = EYE;
    });
  }

  function boot() {
    addStyles();
    scan(document);
    // Campos cargados mas tarde mediante AJAX o modales.
    const observer = new MutationObserver((records) => {
      for (const record of records) {
        if (record.type === 'attributes') {
          scan(record.target);
        } else {
          for (const node of record.addedNodes) scan(node);
        }
      }
    });
    observer.observe(document.body, {childList: true, subtree: true, attributes: true, attributeFilter: ['type']});
    // Evitar que una ventana reutilizada muestre claves al abrirse otra vez.
    document.addEventListener('reset', (event) => hideAll(event.target), true);
    document.addEventListener('visibilitychange', () => { if (document.hidden) hideAll(document); });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, {once: true});
  else boot();
})();
