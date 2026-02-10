(() => {
  const rTipo = document.getElementById('rTipo');
  const rFechaAnual = document.getElementById('rFechaAnual');
  const rFechaMensual = document.getElementById('rFechaMensual');
  const rFechaDiario = document.getElementById('rFechaDiario');

  const btnRun = document.getElementById('btnRun');
  const btnClear = document.getElementById('btnClear');
  const btnPdf = document.getElementById('btnPdf');

  const msgRep = document.getElementById('msgRep');
  const repOut = document.getElementById('repOut');

  const repMeta = document.getElementById('repMeta');
  const repResumen = document.getElementById('repResumen');

  const tSerie = document.getElementById('tSerie');
  const serieHead = document.getElementById('serieHead');
  const serieBody = document.getElementById('serieBody');

  const captHead = document.getElementById('captHead');
  const captBody = document.getElementById('captBody');

  const dosisBody = document.getElementById('dosisBody');
  const persBody = document.getElementById('persBody');
  const alertBody = document.getElementById('alertBody');

  let lastQuery = null;

  function show(el){ el.classList.remove('hidden'); }
  function hide(el){ el.classList.add('hidden'); }

  function resetInputs(){
    rFechaAnual.value = '';
    rFechaMensual.value = '';
    rFechaDiario.value = '';
  }

  function switchTipo(){
    const t = rTipo.value;
    hide(rFechaAnual); hide(rFechaMensual); hide(rFechaDiario);
    if (t === 'ANUAL') show(rFechaAnual);
    if (t === 'MENSUAL') show(rFechaMensual);
    if (t === 'DIARIO') show(rFechaDiario);
  }
  rTipo.addEventListener('change', switchTipo);
  switchTipo();

  function safe(v, d='—'){ return (v===null||v===undefined||v==='') ? d : v; }

  function renderKPIs(items){
    repResumen.innerHTML = '';
    items.forEach(it => {
      const div = document.createElement('div');
      div.className = 'kpi-box';
      div.innerHTML = `
        <div class="kpi-label">${it.label}</div>
        <div class="kpi-value">${safe(it.value, 0)}</div>
      `;
      repResumen.appendChild(div);
    });
  }

  function renderSerie(tipo, rep){
    serieHead.innerHTML = '';
    serieBody.innerHTML = '';

    if (tipo === 'ANUAL'){
      tSerie.textContent = 'Total por mes (dosis)';
      serieHead.innerHTML = `<th>Mes</th><th class="rep-right">Total</th>`;
      (rep.total_por_mes || []).forEach(x => {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td title="${x.mes}">${x.mes}</td><td class="rep-right">${x.total}</td>`;
        serieBody.appendChild(tr);
      });

    } else if (tipo === 'MENSUAL'){
      tSerie.textContent = 'Total por día (dosis)';
      serieHead.innerHTML = `<th>Fecha</th><th class="rep-right">Total</th>`;
      (rep.total_por_dia || []).forEach(x => {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td title="${x.fecha}">${x.fecha}</td><td class="rep-right">${x.total}</td>`;
        serieBody.appendChild(tr);
      });

    } else {
      tSerie.textContent = 'Resumen diario';
      serieHead.innerHTML = `<th>Campo</th><th class="rep-right">Valor</th>`;
      const rows = [
        ['Total dosis', rep.total_diario],
        ['Personas únicas', rep.personas_total],
        ['Captación temprana', rep.captacion_temprana],
        ['Captación tardía', rep.captacion_tardia],
      ];
      rows.forEach(([k,v]) => {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td title="${k}">${k}</td><td class="rep-right">${safe(v,0)}</td>`;
        serieBody.appendChild(tr);
      });
    }
  }

  function renderList2(body, arr, keyText, keyNum){
    body.innerHTML = '';
    if (!arr || !arr.length){
      body.innerHTML = `<tr><td colspan="2" class="empty-row">Sin datos</td></tr>`;
      return;
    }
    arr.forEach(x => {
      const txt = x[keyText];
      const num = x[keyNum];
      const tr = document.createElement('tr');
      tr.innerHTML = `<td title="${txt}">${txt}</td><td class="rep-right">${safe(num,0)}</td>`;
      body.appendChild(tr);
    });
  }

  function renderCaptacion(tipo, rep){
    captHead.innerHTML = '';
    captBody.innerHTML = '';

    if (tipo === 'ANUAL'){
      captHead.innerHTML = `<th>Mes</th><th class="rep-right">Temprana</th><th class="rep-right">Tardía</th>`;
      const arr = rep.captacion_por_mes || [];
      if (!arr.length){
        captBody.innerHTML = `<tr><td colspan="3" class="empty-row">Sin datos</td></tr>`;
        return;
      }
      arr.forEach(x => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td title="${x.mes}">${x.mes}</td>
          <td class="rep-right">${safe(x.temprana,0)}</td>
          <td class="rep-right">${safe(x.tardia,0)}</td>
        `;
        captBody.appendChild(tr);
      });

    } else if (tipo === 'MENSUAL'){
      captHead.innerHTML = `<th>Fecha</th><th class="rep-right">Temprana</th><th class="rep-right">Tardía</th>`;
      const arr = rep.captacion_por_dia || [];
      if (!arr.length){
        captBody.innerHTML = `<tr><td colspan="3" class="empty-row">Sin datos</td></tr>`;
        return;
      }
      arr.forEach(x => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td title="${x.fecha}">${x.fecha}</td>
          <td class="rep-right">${safe(x.temprana,0)}</td>
          <td class="rep-right">${safe(x.tardia,0)}</td>
        `;
        captBody.appendChild(tr);
      });

    } else {
      // DIARIO: ya lo ves en KPIs/serie; mostramos una fila simple también
      captHead.innerHTML = `<th>Tipo</th><th class="rep-right">Valor</th>`;
      const rows = [
        ['Captación temprana', rep.captacion_temprana],
        ['Captación tardía', rep.captacion_tardia],
      ];
      rows.forEach(([k,v]) => {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td title="${k}">${k}</td><td class="rep-right">${safe(v,0)}</td>`;
        captBody.appendChild(tr);
      });
    }
  }

  btnRun.addEventListener('click', async () => {
    msgRep.textContent = '';
    hide(repOut);
    hide(btnPdf);
    lastQuery = null;

    const tipo = rTipo.value;
    let fecha = '';

    if (tipo === 'ANUAL'){
      fecha = (rFechaAnual.value || '').trim();
      if (!/^\d{4}$/.test(fecha)){
        msgRep.textContent = 'Para ANUAL ingresa YYYY (ej: 2025).';
        return;
      }
    } else if (tipo === 'MENSUAL'){
      fecha = (rFechaMensual.value || '').trim();
      if (!fecha){
        msgRep.textContent = 'Selecciona un mes.';
        return;
      }
    } else {
      fecha = (rFechaDiario.value || '').trim();
      if (!fecha){
        msgRep.textContent = 'Selecciona una fecha.';
        return;
      }
    }

    msgRep.textContent = 'Generando reporte...';

    const res = await fetch(`/api/reportes?tipo=${encodeURIComponent(tipo)}&fecha=${encodeURIComponent(fecha)}`, { cache:'no-store' });
    const data = await res.json().catch(() => ({}));
    if (!res.ok){
      msgRep.textContent = data.message || 'No se pudo generar el reporte.';
      return;
    }

    const rep = data.reporte || {};
    const als = data.alertas || [];

    repMeta.textContent = `Tipo: ${tipo} • Periodo: ${fecha}`;

    if (tipo === 'ANUAL'){
      renderKPIs([
        { label: 'Año', value: fecha },
        { label: 'Total dosis', value: safe(rep.total_anual, 0) },
        { label: 'Capt. temprana', value: safe(rep.captacion_temprana, 0) },
        { label: 'Capt. tardía', value: safe(rep.captacion_tardia, 0) },
      ]);
    } else if (tipo === 'MENSUAL'){
      renderKPIs([
        { label: 'Mes', value: fecha },
        { label: 'Total dosis', value: safe(rep.total_mensual, 0) },
        { label: 'Personas únicas', value: safe(rep.personas_total, 0) },
        { label: 'Capt. temprana', value: safe(rep.captacion_temprana, 0) },
        { label: 'Capt. tardía', value: safe(rep.captacion_tardia, 0) },
      ]);
    } else {
      renderKPIs([
        { label: 'Día', value: fecha },
        { label: 'Total dosis', value: safe(rep.total_diario, 0) },
        { label: 'Personas únicas', value: safe(rep.personas_total, 0) },
        { label: 'Capt. temprana', value: safe(rep.captacion_temprana, 0) },
        { label: 'Capt. tardía', value: safe(rep.captacion_tardia, 0) },
      ]);
    }

    renderSerie(tipo, rep);
    renderCaptacion(tipo, rep);

    renderList2(dosisBody, rep.dosis_por_vacuna || [], 'vacuna', 'dosis_total');
    renderList2(persBody, rep.personas_por_vacuna || [], 'vacuna', 'personas_total');

    alertBody.innerHTML = '';
    if (!als.length){
      alertBody.innerHTML = `<tr><td colspan="3" class="empty-row">Sin alertas</td></tr>`;
    } else {
      als.forEach(a => {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td title="${a.tipo_alerta}">${a.tipo_alerta}</td><td title="${a.estado}">${a.estado}</td><td class="rep-right">${a.total}</td>`;
        alertBody.appendChild(tr);
      });
    }

    lastQuery = { tipo, fecha };
    show(btnPdf);

    show(repOut);
    msgRep.textContent = '';
  });

  btnPdf.addEventListener('click', () => {
    if (!lastQuery) return;
    const { tipo, fecha } = lastQuery;
    const url = `/api/reportes/pdf?tipo=${encodeURIComponent(tipo)}&fecha=${encodeURIComponent(fecha)}`;
    window.open(url, '_blank'); // o window.location.href = url;
    });


  btnClear.addEventListener('click', () => {
    resetInputs();
    msgRep.textContent = '';
    hide(repOut);
    hide(btnPdf);
    lastQuery = null;
  });
})();
