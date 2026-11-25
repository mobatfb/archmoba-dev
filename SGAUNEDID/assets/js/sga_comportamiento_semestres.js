(function () {
  'use strict';
  const tabla = document.getElementById('comport-tabla');
  if (!tabla) return;
  const url = tabla.dataset.guardarUrl;
  const oid = tabla.dataset.ofertaId;
  const semestre = tabla.dataset.semestre;
  const csrf = tabla.dataset.csrf;

  tabla.addEventListener('click', async function (event) {
    const boton = event.target.closest('button.comport-opcion');
    if (!boton || boton.disabled) return;
    const fila = boton.closest('tr[data-matricula-id]');
    if (!fila || fila.dataset.guardando === '1') return;
    const anterior = fila.dataset.actual || '';
    const literal = boton.dataset.literal;
    if (literal === anterior) return;
    const estado = fila.querySelector('.comport-estado-texto');
    const opciones = Array.from(fila.querySelectorAll('button.comport-opcion'));
    fila.dataset.guardando = '1';
    fila.classList.add('comport-guardando');
    estado.textContent = 'Guardando…';
    estado.classList.remove('comport-error');
    opciones.forEach(function (b) { b.disabled = true; });
    try {
      const datos = new FormData();
      datos.append('csrf', csrf);
      datos.append('oferta_id', oid);
      datos.append('matricula_id', fila.dataset.matriculaId);
      datos.append('semestre', semestre);
      datos.append('literal', literal);
      const respuesta = await fetch(url, {
        method: 'POST', body: datos, credentials: 'same-origin',
        headers: { 'Accept': 'application/json' }
      });
      const resultado = await respuesta.json();
      if (!respuesta.ok || !resultado.ok || resultado.literal !== literal) {
        throw new Error(resultado.mensaje || 'No se pudo guardar.');
      }
      fila.dataset.actual = literal;
      opciones.forEach(function (b) {
        const marcado = b.dataset.literal === literal;
        b.classList.toggle('seleccionado', marcado);
        b.setAttribute('aria-pressed', marcado ? 'true' : 'false');
      });
      estado.textContent = '✓ Guardado';
    } catch (error) {
      estado.textContent = error instanceof Error ? error.message : 'Error al guardar';
      estado.classList.add('comport-error');
    } finally {
      fila.dataset.guardando = '0';
      fila.classList.remove('comport-guardando');
      opciones.forEach(function (b) { b.disabled = false; });
    }
  });
})();
