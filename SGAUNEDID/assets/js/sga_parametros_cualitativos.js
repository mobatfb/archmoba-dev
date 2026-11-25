(() => {
  const tabla=document.getElementById('sga-p-table');
  if(!tabla)return;
  const tonos = {'A+':'alto','A-':'alto','B+':'alto','B-':'alto','C+':'medio','C-':'medio','D+':'bajo','D-':'bajo','E+':'bajo','E-':'bajo'};
  const actualizarColor = select => {
    select.classList.remove('sga-p-alto','sga-p-medio','sga-p-bajo');
    if(tonos[select.value])select.classList.add('sga-p-'+tonos[select.value]);
  };
  const pendientes = new WeakMap();
  tabla.querySelectorAll('.sga-p-select').forEach(sel => {
    actualizarColor(sel);
    sel.addEventListener('change', async () => {
      const tr=sel.closest('tr');const indicador=tr?.querySelector('.sga-p-row-status');
      const anterior=sel.dataset.valor || '';
      const nuevo=sel.value;
      if(anterior===nuevo)return;
      const mid=tr?.dataset.matricula;
      if(!mid || pendientes.has(sel))return;
      const params=new URLSearchParams({
        csrf:tabla.dataset.csrf,oferta_id:tabla.dataset.ofertaId,
        matricula_id:mid,parametro_id:sel.dataset.parametro,
        trimestre:tabla.dataset.trimestre,literal:nuevo
      });
      sel.disabled=true; sel.classList.add('sga-p-saving');
      if(indicador){indicador.textContent='Guardando…';indicador.className='sga-p-row-status sga-p-pending';}
      pendientes.set(sel,true);
      try {
        const res=await fetch(tabla.dataset.url,{method:'POST',body:params,credentials:'same-origin',headers:{'Accept':'application/json','X-Requested-With':'XMLHttpRequest'}});
        const data=await res.json();
        if(!res.ok || !data.ok)throw new Error(data.mensaje || 'No se pudo guardar.');
        sel.dataset.valor=nuevo;
        actualizarColor(sel);
        if(indicador){indicador.textContent=nuevo?'Guardado':'Sin nota';indicador.className='sga-p-row-status sga-p-done';}
      } catch(err) {
        sel.value=anterior;
        actualizarColor(sel);
        if(indicador){indicador.textContent='Error al guardar';indicador.className='sga-p-row-status sga-p-error';}
        alert(err?.message || 'No se pudo guardar la valoración.');
      } finally {
        pendientes.delete(sel);sel.disabled=false;sel.classList.remove('sga-p-saving');
      }
    });
  });
})();
