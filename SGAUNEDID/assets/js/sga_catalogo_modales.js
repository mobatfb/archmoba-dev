/* SGA UNEDID v1.6.25 - ventanas flotantes accesibles, sin crecer el contenedor */
(() => {
  'use strict';
  let triggerActual = null;
  const mostrar = (d, trigger) => {
    if (!d) return;
    triggerActual = trigger || document.activeElement;
    if (typeof d.showModal === 'function') {
      if (!d.open) d.showModal();
    } else d.setAttribute('open', '');
    const first = d.querySelector('input:not([type="hidden"]):not([disabled]), select:not([disabled]), [data-sga-cat-tab]');
    if (first) first.focus({ preventScroll: true });
  };
  const cerrar = d => {
    if (!d) return;
    if (typeof d.close === 'function' && d.open) d.close();
    else d.removeAttribute('open');
  };
  document.querySelectorAll('.sga-cat-dialog').forEach(d => {
    d.querySelectorAll('[data-sga-cat-close]').forEach(btn => btn.addEventListener('click', () => cerrar(d)));
    d.addEventListener('click', e => {
      if (e.target !== d) return;
      const r = d.getBoundingClientRect();
      if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) cerrar(d);
    });
    d.addEventListener('close', () => { if (triggerActual && triggerActual.isConnected) triggerActual.focus({ preventScroll:true }); });
    const tabs = Array.from(d.querySelectorAll('[data-sga-cat-tab]'));
    if (tabs.length) {
      const elegir = name => {
        tabs.forEach(t => { const chosen = t.dataset.sgaCatTab === name; t.setAttribute('aria-selected', chosen ? 'true' : 'false'); t.setAttribute('tabindex', chosen ? '0' : '-1'); });
        d.querySelectorAll('[data-sga-cat-panel]').forEach(p => { p.hidden = p.dataset.sgaCatPanel !== name; });
      };
      tabs.forEach((t, i) => {
        t.addEventListener('click', () => elegir(t.dataset.sgaCatTab));
        t.addEventListener('keydown', e => {
          if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(e.key)) return;
          e.preventDefault();
          const next = e.key === 'Home' ? 0 : e.key === 'End' ? tabs.length - 1
            : (i + (e.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
          elegir(tabs[next].dataset.sgaCatTab);
          tabs[next].focus();
        });
      });
      elegir(tabs.find(t => t.getAttribute('aria-selected') === 'true')?.dataset.sgaCatTab || tabs[0].dataset.sgaCatTab);
      d.sgaCatElegirTab = elegir;
    }
  });
  document.querySelectorAll('[data-sga-cat-open]').forEach(b => b.addEventListener('click', () => {
    const d = document.getElementById(b.dataset.sgaCatOpen);
    if (d?.sgaCatElegirTab) d.sgaCatElegirTab('crear');
    mostrar(d, b);
  }));
  const editD = document.getElementById('sga-cat-edit');
  function setFormData(form, datos) {
    if (!form || !datos) return;
    form.reset();
    Object.entries(datos).forEach(([name, value]) => {
      const input = Array.from(form.elements).find(el => el.name === name);
      if (!input) return;
      if (input.type === 'checkbox') input.checked = (String(value) === '1' || value === true);
      else if (input.type !== 'file') input.value = value == null ? '' : String(value);
    });
    const readonly = datos.estado === 'cerrado';
    editD?.querySelectorAll('input,select,textarea').forEach(el => {
      if (el.type === 'hidden') return;
      el.disabled = readonly;
    });
    form.querySelectorAll('input[type="checkbox"]').forEach(el => el.dispatchEvent(new Event('change', { bubbles: true })));
    const save = editD?.querySelector('button[type="submit"]');
    if (save) { save.disabled = readonly; save.hidden = readonly; }
    const title = document.getElementById('sga-cat-edit-title');
    if (title && editD) title.textContent = (readonly ? 'Consultar ' : 'Editar ') + (editD.dataset.sgaCatSingular || 'registro');
  }
  document.querySelectorAll('[data-sga-cat-edit]').forEach(b => b.addEventListener('click', e => {
    if (!editD) return;
    e.preventDefault();
    try {
      const datos = JSON.parse(b.dataset.sgaCatEdit);
      setFormData(editD.querySelector('form'), datos);
      mostrar(editD, b);
    } catch (err) { console.error('No se pudo abrir la edición', err); }
  }));
  if (editD && window.location.search.includes('editar=')) {
    const id = new URLSearchParams(window.location.search).get('editar');
    const b = Array.from(document.querySelectorAll('[data-sga-cat-edit]')).find(x => {try{return String(JSON.parse(x.dataset.sgaCatEdit).id) === String(id)}catch(e){return false}});
    if (b) b.click();
  }
  // Escala especial incompatible con el visor exclusivo de comportamiento.
  document.querySelectorAll('.sga-cat-dialog').forEach(d => {
    const visor = d.querySelector('[name="solo_visor_comportamiento"]');
    const especial = d.querySelector('[name="especial"]');
    if (!visor || !especial) return;
    const sync = () => { if (visor.checked) especial.checked = false; especial.disabled = visor.checked; especial.closest('label').style.opacity = visor.checked ? '0.55' : '1'; };
    visor.addEventListener('change', sync); sync();
  });
})();
