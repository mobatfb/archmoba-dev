/* ISTPNCHAT 2.0: JavaScript propio, sin librerias ni conexiones a IA. */
(function () {
  'use strict';
  function start() {
    const root = document.getElementById('istpnchat-root');
    const config = window.ISTPNCHAT_CONFIG || {};
    if (!root || root.dataset.ready === '1') return;
    root.dataset.ready = '1';
    root.style.setProperty('--istpnchat-accent', /^#[0-9a-fA-F]{6}$/.test(config.accent || '') ? config.accent : '#1262ba');
    const launcher = root.querySelector('.istpnchat-launcher');
    const panel = root.querySelector('.istpnchat-panel');
    const closeButton = root.querySelector('.istpnchat-close');
    const form = root.querySelector('.istpnchat-form');
    const input = root.querySelector('#istpnchat-input');
    const submit = root.querySelector('.istpnchat-send');
    const messages = root.querySelector('.istpnchat-messages');
    if (!launcher || !panel || !form || !input || !submit || !messages) return;
    let busy = false;
    let greeted = false;
    // Solo se conserva el ID del ultimo tema durante esta visita. Sin cookies ni historial.
    let lastContext = '';

    function show(isOpen) {
      panel.hidden = !isOpen;
      panel.classList.toggle('istpnchat-open', isOpen);
      launcher.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
      launcher.setAttribute('aria-label', isOpen ? 'Ocultar ISTPNCHAT' : 'Abrir ISTPNCHAT');
      if (isOpen) {
        if (!greeted) {
          addMessage(config.welcome || '¡Hola! Soy ISTPNCHAT. ¿En qué puedo ayudarte?', 'bot', []);
          greeted = true;
        }
        input.focus();
      } else {
        launcher.focus();
      }
    }

    function addMessage(text, sender, sources) {
      const message = document.createElement('div');
      message.className = 'istpnchat-bubble ' + (sender === 'user' ? 'istpnchat-user' : 'istpnchat-bot');
      const body = document.createElement('div');
      body.className = 'istpnchat-body';
      body.textContent = String(text || ''); // Sin innerHTML: protege contra XSS.
      message.appendChild(body);
      if (Array.isArray(sources) && sources.length) {
        const links = document.createElement('div');
        links.className = 'istpnchat-links';
        const names = new Set();
        for (const item of sources.slice(0, 12)) {
          try {
            const url = new URL(item.url);
            const host = url.hostname.toLowerCase();
            if (url.protocol !== 'https:' || (host !== 'isupol.edu.ec' && !host.endsWith('.isupol.edu.ec'))) continue;
            if (names.has(url.href)) continue;
            names.add(url.href);
            const link = document.createElement('a');
            link.href = url.href;
            link.target = '_blank';
            link.rel = 'noopener noreferrer';
            link.textContent = '↗ ' + String(item.titulo || 'Fuente oficial');
            links.appendChild(link);
          } catch (error) { /* La URL inválida se omite. */ }
        }
        if (links.children.length) message.appendChild(links);
      }
      messages.appendChild(message);
      messages.scrollTop = messages.scrollHeight;
      return message;
    }

    async function ask(question) {
      const q = String(question || '').trim();
      if (!q || busy) return;
      busy = true;
      submit.disabled = true;
      input.disabled = true;
      addMessage(q, 'user', []);
      input.value = '';
      const thinking = addMessage('Buscando en la información institucional…', 'bot', []);
      try {
        const headers = {'Content-Type': 'application/json'};
        if (config.nonce) headers['X-WP-Nonce'] = config.nonce;
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 15000);
        let response;
        try {
          response = await fetch(config.endpoint, {
            method: 'POST', headers, credentials: 'same-origin',
            body: JSON.stringify({pregunta: q, contexto: lastContext}), signal: controller.signal
          });
        } finally { clearTimeout(timeout); }
        const data = await response.json();
        thinking.remove();
        if (!response.ok) {
          addMessage(data.message || 'No se pudo completar la consulta.', 'bot', []);
        } else {
          if (typeof data.contexto === 'string' && /^[a-z0-9-]{1,80}$/.test(data.contexto)) {
            lastContext = data.contexto;
          }
          addMessage(data.respuesta || 'Por ahora no tengo una respuesta confirmada para esa pregunta. ¿Puedes hacerla de otra forma?', 'bot', data.fuentes || []);
        }
      } catch (error) {
        thinking.remove();
        addMessage('No pude conectar con WordPress. Revisa tu conexión o intenta más tarde.', 'bot', []);
      } finally {
        busy = false;
        submit.disabled = false;
        input.disabled = false;
        input.focus();
      }
    }

    launcher.addEventListener('click', () => show(panel.hidden));
    closeButton.addEventListener('click', () => show(false));
    form.addEventListener('submit', (event) => {
      event.preventDefault();
      ask(input.value);
    });
    input.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
        event.preventDefault();
        ask(input.value);
      }
    });
    root.querySelectorAll('[data-question]').forEach((button) => {
      button.addEventListener('click', () => {
        show(true);
        ask(button.dataset.question);
      });
    });
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && !panel.hidden) show(false);
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once: true});
  else start();
})();
