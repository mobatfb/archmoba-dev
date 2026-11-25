/* SGA UNEDID v1.6.26: abrir, editar y cerrar flotante de supletorios. */
(() => {
  'use strict';
  const d = document.getElementById('sga-sup-modal');
  const form = document.getElementById('sga-sup-modal-form');
  if (!d || !form) return;
  const titular = document.getElementById('sga-sup-modal-titulo');
  const nombre = document.getElementById('sga-sup-modal-estudiante');
  const nota = document.getElementById('sga-sup-nota');
  const prom = document.getElementById('sga-sup-modal-anual');
  const feedback = document.getElementById('sga-sup-feedback');
  let previous = null;
  let promedio = 0, aprobacion = 7;
  const escala = JSON.parse(d.dataset.escalaCualitativa || '[]');
  const mostrar = (n) => {
    if (d.dataset.resultadosCualitativos !== '1') return n.toFixed(2);
    const centavos = Math.round((Math.max(0, Math.min(10, n)) + Number.EPSILON) * 100);
    const letra = escala.find(nivel => centavos >= nivel.min)?.letra ?? 'E-';
    return n.toFixed(2) + ' (' + letra + ')';
  };
  function cerrar() { if (typeof d.close === 'function' && d.open) d.close(); }
  function recalcular() {
    const n = Number(nota.value);
    if (!nota.value || !Number.isFinite(n) || n <= 0 || n > 10) {
      feedback.textContent = 'Ingresa una nota válida entre 0.01 y 10.00. Los tres trimestres se conservarán.';
      return;
    }
    if (n >= aprobacion) {
      feedback.textContent = 'Resultado previsto: Aprobado. La nota final será ' + mostrar(aprobacion) + ' (máximo registrable por supletorio).';
    } else {
      feedback.textContent = 'Resultado previsto: No aprobado. La nota final conservará el promedio anual ' + mostrar(promedio) + '.';
    }
  }
  document.querySelectorAll('[data-sga-sup-editar]').forEach(b => b.addEventListener('click', () => {
    previous = b;
    const data = b.dataset;
    form.reset();
    document.getElementById('sga-sup-matricula').value = data.matricula || '';
    nombre.textContent = data.estudiante || '';
    ['t1','t2','t3'].forEach(key => {
      document.getElementById('sga-sup-modal-' + key).textContent = data[key] === '' || data[key] == null ? '—' : mostrar(Number(data[key]));
    });
    prom.textContent = data.promedio ? mostrar(Number(data.promedio)) : '—';
    promedio = Number(data.promedio) || 0;
    aprobacion = Number(data.aprobado) || 7;
    nota.value = data.anterior || '';
    titular.textContent = data.anterior ? 'Editar nota de supletorio' : 'Registrar supletorio';
    recalcular();
    if (typeof d.showModal === 'function') { if (!d.open) d.showModal(); }
    else d.setAttribute('open', '');
    nota.focus({preventScroll: true});
  }));
  d.querySelectorAll('[data-sga-sup-cerrar]').forEach(b => b.addEventListener('click', cerrar));
  d.addEventListener('click', ev => {
    if (ev.target !== d) return;
    const r = d.getBoundingClientRect();
    if (ev.clientX < r.left || ev.clientX > r.right || ev.clientY < r.top || ev.clientY > r.bottom) cerrar();
  });
  d.addEventListener('close', () => { form.reset(); if (previous?.isConnected) previous.focus({preventScroll:true}); });
  nota.addEventListener('input', recalcular);
  // No hay otro cuadro de confirmación: la validación final ocurre en el servidor.
})();
