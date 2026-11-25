(() => {
  'use strict';
  const wrapper = document.getElementById('grade-matrix-wrap');
  const matrix = document.getElementById('grade-matrix');
  const workspace = document.getElementById('grade-workspace');
  const savebar = document.getElementById('grade-savebar');
  const form = document.getElementById('form-calificaciones');
  if (!wrapper || !matrix || !form) return;

  const round2 = n => Math.round((n + Number.EPSILON) * 100) / 100;
  const trunc2 = n => Math.floor((n + 1e-9) * 100) / 100;
  const field = (row, name) => row.querySelector(`input[data-field="${name}"]`);
  const parse = input => {
    if (!input) return null;
    const raw = input.value.trim();
    if (raw === '') return null;
    const n = Number(raw.replace(',', '.'));
    const valid = Number.isFinite(n) && n >= 0 && n <= 10;
    input.classList.toggle('grade-invalid', !valid);
    return valid ? round2(n) : null;
  };
  const update = (row, key, number, rating = false) => {
    const target = row.querySelector(`[data-grade="${key}"]`);
    if (!target) return;
    target.textContent = Number.isFinite(number) ? number.toFixed(2) : '0.00';
    if (rating) {
      target.classList.toggle('grade-low', number < 7);
      target.classList.toggle('grade-good', number >= 7);
    }
  };
  const aporteRefuerzo = (prom, ref) => {
    if (prom >= 7 || ref === null || ref <= prom) return prom;
    return round2(Math.max(prom, Math.min(7, (prom + ref) / 2)));
  };
  const disciplinar = (nota, ref) => {
    const base = nota ?? 0;
    if (base <= 0) return 0;
    if (ref === null || ref <= 0) return round2(base);
    const cap = base >= 7 && base < 9 ? 9 : 7;
    return round2(Math.max(base, Math.min(cap, round2((base + ref) / 2))));
  };
  const escalaCualitativa = JSON.parse(wrapper.dataset.escalaCualitativa || "[]");
  const etiqueta = (valor, especial, resultadosCualitativos) => {
    if (resultadosCualitativos) {
      if (!Number.isFinite(valor)) return '';
      const centavos = Math.round((Math.max(0, Math.min(10, valor)) + Number.EPSILON) * 100);
      return escalaCualitativa.find(nivel => centavos >= nivel.min)?.letra ?? 'E-';
    }
    if (especial) {
      const nota = Math.min(10, Math.max(0, round2(valor)));
      if (nota >= 9) return 'A+';
      if (nota >= 8) return 'A-';
      if (nota >= 7) return 'B+';
      return 'B-';
    }
    if (valor <= 0) return '';
    return valor >= 9 ? 'D.A.R.' : valor >= 7 ? 'A.A.R.' : valor >= 4 ? 'P.A.A.R.' : 'N.A.R.';
  };

  const recalcular = row => {
    const valorNaturaleza = prefijo => {
      const notas = [1, 2, 3].map(n => field(row, `${prefijo}_ap${n}`)).filter(Boolean);
      if (!notas.length) {
        update(row, `${prefijo}_promedio`, 0, true);
        update(row, `${prefijo}_promedio_aporte`, 0, true);
        return null;
      }
      const valores = notas.map(input => parse(input) ?? 0);
      const promedio = round2(valores.reduce((sum, v) => sum + v, 0) / valores.length);
      const reforzado = aporteRefuerzo(promedio, parse(field(row, `${prefijo}_refuerzo`)));
      update(row, `${prefijo}_promedio`, promedio, true);
      update(row, `${prefijo}_promedio_aporte`, reforzado, true);
      return reforzado;
    };
    const aportes = ['deber', 'tarea', 'leccion', 'grupo'].map(valorNaturaleza).filter(v => v !== null);
    const prom = aportes.length ? aportes.reduce((sum, v) => sum + v, 0) / aportes.length : 0;
    const pondA = prom > 0 ? trunc2(prom * Number(wrapper.dataset.pondAp || '0.7')) : 0;
    update(row, 'promedio_aportes', round2(prom));
    update(row, 'ponderado_aportes', pondA);

    const nota = parse(field(row, 'nota_disciplinar'));
    const refD = parse(field(row, 'trabajo_refuerzo_disciplinar'));
    const producto = parse(field(row, 'nota_producto_final'));
    const disc = disciplinar(nota, refD);
    update(row, 'promedio_disciplinar', disc);
    const historico = row.dataset.historico === '1' && nota === null && refD === null && producto === null;
    let promedioS = 0;
    let pondS = 0;
    if (historico) {
      promedioS = Number(row.dataset.promHistorico || '0');
      pondS = Number(row.dataset.pondHistorico || '0');
    } else {
      const productoN = producto ?? 0;
      promedioS = disc > 0 || productoN > 0 ? round2((disc + productoN) / 2) : 0;
      pondS = promedioS > 0 ? round2(promedioS * Number(wrapper.dataset.pondSum || '0.3')) : 0;
    }
    update(row, 'promedio_proyecto', promedioS);
    update(row, 'ponderado_sumativa', pondS);
    const final = round2(pondA + pondS);
    update(row, 'nota_final', final, true);
    const qual = row.querySelector('[data-grade="cualitativo"]');
    if (qual) qual.textContent = etiqueta(final, row.dataset.especial === '1', row.dataset.resultadosCualitativos === '1');
    const history = row.querySelector('.grade-history');
    if (history) history.hidden = !historico;
  };

  matrix.querySelectorAll('tbody tr[data-matricula-id]').forEach(row => {
    row.querySelectorAll('input[data-field]').forEach(input => {
      input.addEventListener('input', () => {
        recalcular(row);
        const pending = row.querySelector('.grade-pending');
        if (pending) pending.hidden = false;
      });
      input.addEventListener('change', () => recalcular(row));
    });
  });

  // Guardar una sola fila sin enviar todas las demás notas al servidor.
  form.addEventListener('submit', event => {
    const submitter = event.submitter;
    if (!submitter || submitter.name !== 'guardar_matricula_id') return;
    const target = Number(submitter.value);
    const row = Array.from(matrix.querySelectorAll('tbody tr[data-matricula-id]'))
      .find(r => Number(r.dataset.matriculaId) === target);
    if (!row) { event.preventDefault(); return; }
    matrix.querySelectorAll('tbody tr[data-matricula-id]').forEach(r => {
      if (r === row) return;
      r.querySelectorAll('input[form="form-calificaciones"]').forEach(input => input.disabled = true);
    });
  });

  // La matriz usa una sola barra horizontal nativa.
  // Se ajusta su altura a la ventana para conservar la barra accesible,
  // y se miden los encabezados fijos sin ninguna sincronización de scroll.
  if (workspace) {
    let layoutFrame = 0;
    const ajustarCabeceras = () => {
      if (!matrix.tHead || matrix.tHead.rows.length < 3) return;
      const h1 = Math.ceil(matrix.tHead.rows[0].getBoundingClientRect().height);
      const h2 = Math.ceil(matrix.tHead.rows[1].getBoundingClientRect().height);
      wrapper.style.setProperty('--grade-h1', `${h1}px`);
      wrapper.style.setProperty('--grade-h2', `${h2}px`);
    };
    const ajustarPantalla = () => {
      layoutFrame = 0;
      const viewport = window.visualViewport?.height || window.innerHeight;
      const top = workspace.getBoundingClientRect().top;
      const actions = savebar?.getBoundingClientRect().height || 65;
      const espacio = Math.floor(viewport - top - actions - 24);
      workspace.style.height = `${Math.max(180, espacio)}px`;
      ajustarCabeceras();
    };
    const programarAjuste = () => {
      if (layoutFrame) cancelAnimationFrame(layoutFrame);
      layoutFrame = requestAnimationFrame(ajustarPantalla);
    };
    window.addEventListener('resize', programarAjuste);
    if (window.visualViewport) window.visualViewport.addEventListener('resize', programarAjuste);
    if ('ResizeObserver' in window) {
      const resize = new ResizeObserver(ajustarCabeceras);
      resize.observe(matrix);
    }
    if (document.fonts?.ready) document.fonts.ready.then(programarAjuste);
    programarAjuste();
  }

  // Eliminar de manera explícita y confirmada todos los registros de esta oferta/trimestre.
  const limpiar = document.getElementById('form-limpiar-todo');
  if (limpiar) {
    limpiar.addEventListener('submit', event => {
      const confirmacion = window.prompt('Esta acción eliminará TODAS las notas guardadas de esta asignatura en el trimestre seleccionado. Para continuar escribe ELIMINAR:');
      if (confirmacion !== 'ELIMINAR') { event.preventDefault(); return; }
      document.getElementById('confirmacion-limpiar-todo').value = 'ELIMINAR';
    });
  }
})();
