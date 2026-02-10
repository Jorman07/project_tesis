(() => {
  const msg = document.getElementById('msg');

  // carga principal
  const fileInput = document.getElementById('fileInput');
  const btnPreview = document.getElementById('btnPreview');
  const btnGuardar = document.getElementById('btnGuardar');

  const previewCard = document.getElementById('previewCard');
  const meta = document.getElementById('meta');
  const prevHead = document.getElementById('prevHead');
  const prevBody = document.getElementById('prevBody');

  const fileName = document.getElementById('fileName');

  fileInput.addEventListener('change', () => {
    if (fileInput.files && fileInput.files.length > 0) {
      if (fileName) fileName.textContent = fileInput.files[0].name;
    } else {
      if (fileName) fileName.textContent = 'Ningún archivo seleccionado';
    }
  });

  // filtros
  const fNombreArchivo = document.getElementById('fNombreArchivo');
  const fUsuario = document.getElementById('fUsuario');
  const fMes = document.getElementById('fMes');
  const fEstado = document.getElementById('fEstado');
  const btnClear = document.getElementById('btnClear');

  // tabla
  const archBody = document.getElementById('archBody');

  // modal update
  const modalUpdate = document.getElementById('modalUpdate');
  const modalUpdateBackdrop = document.getElementById('modalUpdateBackdrop');
  const modalUpdateClose = document.getElementById('modalUpdateClose');
  const updMeta = document.getElementById('updMeta');
  const updMsg = document.getElementById('updMsg');

  const fileUpdate = document.getElementById('fileUpdate');
  const btnPreviewUpdate = document.getElementById('btnPreviewUpdate');
  const btnApplyUpdate = document.getElementById('btnApplyUpdate');

  const updSummary = document.getElementById('updSummary');
  const updStats = document.getElementById('updStats');
  const updRows = document.getElementById('updRows');
  const fileUpdateName = document.getElementById('fileUpdateName');

  fileUpdate?.addEventListener('change', () => {
    if (fileUpdate.files && fileUpdate.files.length > 0) {
      if (fileUpdateName) fileUpdateName.textContent = fileUpdate.files[0].name;
    } else {
      if (fileUpdateName) fileUpdateName.textContent = 'Ningún archivo seleccionado';
    }
  });

  let lastPreview = null;
  let allRows = [];
  let monthsSet = new Set();

  // estado modal update
  let updateTarget = null;
  let updatePreview = null;

  function safe(v, d='—'){ return (v === null || v === undefined || v === '') ? d : v; }
  function toMonthsText(ms){
    if (!ms) return '—';
    if (Array.isArray(ms)) return ms.join(', ') || '—';
    try { return JSON.stringify(ms); } catch { return String(ms); }
  }

  function setMainLoading(on, text='Cargando...'){
    if (on){
      msg.textContent = text;
      btnPreview.disabled = true;
      btnGuardar.disabled = true;
      fileInput.disabled = true;
    } else {
      btnPreview.disabled = false;
      btnGuardar.disabled = false;
      fileInput.disabled = false;
    }
  }

  function clearPreviewUI(){
    lastPreview = null;
    btnGuardar.classList.add('hidden');
    previewCard.classList.add('hidden');
    meta.innerHTML = '';
    prevHead.innerHTML = '';
    prevBody.innerHTML = '';
  }

  async function loadList(){
    msg.textContent = 'Cargando archivos...';
    const res = await fetch('/api/archivos/list');
    const data = await res.json().catch(() => []);
    allRows = Array.isArray(data) ? data : [];

    monthsSet = new Set();
    allRows.forEach(r => {
      const ms = Array.isArray(r.meses_detectados) ? r.meses_detectados : [];
      ms.forEach(m => monthsSet.add(m));
    });

    fillMesFilter();
    renderTable();
    msg.textContent = '';
  }

  function fillMesFilter(){
    const current = fMes.value;
    fMes.innerHTML = `<option value="">Mes: Todos</option>`;
    Array.from(monthsSet).sort().forEach(m => {
      const opt = document.createElement('option');
      opt.value = m;
      opt.textContent = m;
      fMes.appendChild(opt);
    });
    fMes.value = current;
  }

  function matchesFilters(row){
    const qA = (fNombreArchivo.value || '').toLowerCase().trim();
    const qU = (fUsuario.value || '').toLowerCase().trim();
    const mes = (fMes.value || '').trim();
    const est = (fEstado.value || '').trim().toUpperCase();

    const name = (row.nombre_archivo || '').toLowerCase();
    const user = (row.usuario_nombre || '').toLowerCase();
    const estado = (row.estado_proceso || '').toUpperCase();
    const meses = Array.isArray(row.meses_detectados) ? row.meses_detectados : [];

    if (qA && !name.includes(qA)) return false;
    if (qU && !user.includes(qU)) return false;
    if (est && estado !== est) return false;
    if (mes && !meses.includes(mes)) return false;

    return true;
  }

  function renderTable(){
    archBody.innerHTML = '';
    const rows = allRows.filter(matchesFilters);

    if (!rows.length){
      const tr = document.createElement('tr');
      tr.innerHTML = `<td colspan="9" class="empty-row">No hay archivos para mostrar.</td>`;
      archBody.appendChild(tr);
      return;
    }

    rows.forEach(r => {
      const meses = Array.isArray(r.meses_detectados) ? r.meses_detectados : [];
      const estado = (r.estado_proceso || 'PENDIENTE').toUpperCase();

      const canProcesar = (estado === 'PENDIENTE');
      const canUpdate = true;

      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td title="${safe(r.nombre_archivo,'')}">${safe(r.nombre_archivo,'')}</td>
        <td>${safe(r.usuario_nombre,'—')}</td>
        <td>${safe(r.fecha_carga,'')}</td>
        <td class="right">${safe(r.total_filas_leidas,0)}</td>
        <td>${safe(r.min_fecha_vacunacion)}</td>
        <td>${safe(r.max_fecha_vacunacion)}</td>
        <td>${toMonthsText(meses)}</td>
        <td>${estado}</td>
        <td>
          <div class="actions">
            <button class="btn-mini" ${canProcesar ? '' : 'disabled'} data-action="procesar">Procesar</button>
            <button class="btn-mini" ${canUpdate ? '' : 'disabled'} data-action="update">Actualizar documento</button>
          </div>
        </td>
      `;

      tr.querySelector('[data-action="procesar"]').addEventListener('click', () => onProcesar(r));
      tr.querySelector('[data-action="update"]').addEventListener('click', () => openUpdateModal(r));

      archBody.appendChild(tr);
    });
  }

  // ========= CARGA PRINCIPAL =========
  btnPreview.addEventListener('click', async () => {
    clearPreviewUI();

    const f = fileInput.files?.[0];
    if (!f){
      msg.textContent = 'Selecciona un archivo (.html/.htm/.xls/.xlsx).';
      return;
    }

    const fd = new FormData();
    fd.append('file', f);

    setMainLoading(true, 'Cargando... Esto puede tardar unos minutos.');

    try{
      const res = await fetch('/api/archivos/preview', { method:'POST', body: fd });
      const data = await res.json().catch(() => ({}));

      if (!res.ok){
        msg.textContent = data.message || 'No se pudo previsualizar.';
        return;
      }

      lastPreview = data;
      previewCard.classList.remove('hidden');
      btnGuardar.classList.remove('hidden');

      meta.innerHTML = `
        <span>Archivo: <b>${safe(data.nombre_archivo)}</b></span>
        <span>Tipo: <b>${safe(data.tipo_detectado)}</b></span>
        <span>Filas: <b>${safe(data.total_filas,0)}</b></span>
        <span>Min vac: <b>${safe(data.min_fecha_vacunacion)}</b></span>
        <span>Max vac: <b>${safe(data.max_fecha_vacunacion)}</b></span>
        <span>Meses: <b>${(data.meses_detectados || []).join(', ') || '—'}</b></span>
      `;

      prevHead.innerHTML = '';
      prevBody.innerHTML = '';

      (data.headers || []).forEach(h => {
        const th = document.createElement('th');
        th.textContent = h;
        prevHead.appendChild(th);
      });

      (data.preview || []).forEach(r => {
        const tr = document.createElement('tr');
        (r || []).forEach(val => {
          const td = document.createElement('td');
          td.textContent = val;
          tr.appendChild(td);
        });
        prevBody.appendChild(tr);
      });

      msg.textContent = '';
    } finally {
      setMainLoading(false);
    }
  });

  btnGuardar.addEventListener('click', async () => {
    const f = fileInput.files?.[0];
    if (!f) return;

    setMainLoading(true, 'Guardando carga (PENDIENTE)...');

    try{
      const fd = new FormData();
      fd.append('file', f);

      const res = await fetch('/api/archivos/guardar', { method:'POST', body: fd });
      const data = await res.json().catch(() => ({}));

      if (!res.ok){
        msg.textContent = data.message || 'No se pudo guardar.';
        return;
      }

      msg.textContent = `Carga guardada como PENDIENTE.`;
      clearPreviewUI();
      fileInput.value = '';
      if (fileName) fileName.textContent = 'Ningún archivo seleccionado';
      await loadList();
    } finally {
      setMainLoading(false);
    }
  });

  // ========= PROCESAR =========
  async function onProcesar(row){
    msg.textContent = 'Procesando...';
    const res = await fetch('/api/archivos/procesar', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ id_archivo: row.id_archivo })
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok){
      msg.textContent = data.message || 'No se pudo procesar.';
      return;
    }
    msg.textContent = `Procesado. Val: ${data.metrics?.validas ?? 0} | Inv: ${data.metrics?.invalidas ?? 0} | Conf: ${data.metrics?.conflictos ?? 0}`;
    await loadList();
  }

  // ========= MODAL UPDATE =========
  function openUpdateModal(row){
    updateTarget = row;
    updatePreview = null;

    updMeta.textContent = `Archivo actual: ${row.nombre_archivo} • Estado: ${row.estado_proceso}`;
    updMsg.textContent = '';
    updSummary.classList.add('hidden');
    updRows.innerHTML = '';
    updStats.innerHTML = '';
    fileUpdate.value = '';
    if (fileUpdateName) fileUpdateName.textContent = 'Ningún archivo seleccionado';

    modalUpdate.classList.remove('hidden');
  }

  function closeUpdateModal(){
    modalUpdate.classList.add('hidden');
    updateTarget = null;
    updatePreview = null;
    updMsg.textContent = '';
  }

  modalUpdateBackdrop.addEventListener('click', closeUpdateModal);
  modalUpdateClose.addEventListener('click', closeUpdateModal);

  btnPreviewUpdate.addEventListener('click', async () => {
    updMsg.textContent = '';
    updSummary.classList.add('hidden');
    updRows.innerHTML = '';
    updStats.innerHTML = '';

    const f = fileUpdate.files?.[0];
    if (!f){
      updMsg.textContent = 'Selecciona un archivo para actualizar.';
      return;
    }

    updMsg.textContent = 'Cargando... procesando nuevo archivo.';
    const fd = new FormData();
    fd.append('file', f);

    const res = await fetch('/api/archivos/preview', { method:'POST', body: fd });
    const data = await res.json().catch(() => ({}));
    if (!res.ok){
      updMsg.textContent = data.message || 'No se pudo previsualizar.';
      return;
    }

    updatePreview = data;
    updSummary.classList.remove('hidden');

    updStats.innerHTML = `
      <span>Filas: <b>${safe(data.total_filas,0)}</b></span>
      <span>Min vac: <b>${safe(data.min_fecha_vacunacion)}</b></span>
      <span>Max vac: <b>${safe(data.max_fecha_vacunacion)}</b></span>
      <span>Meses: <b>${(data.meses_detectados || []).join(', ') || '—'}</b></span>
    `;

    updRows.innerHTML = `
      <tr>
        <td>${safe(data.nombre_archivo)}</td>
        <td class="right">${safe(data.total_filas,0)}</td>
        <td>${safe(data.min_fecha_vacunacion)}</td>
        <td>${safe(data.max_fecha_vacunacion)}</td>
        <td>${(data.meses_detectados || []).join(', ') || '—'}</td>
      </tr>
    `;

    updMsg.textContent = '';
  });

  // ✅ CAMBIO IMPORTANTE: ApplyUpdate envía archivo real por FormData
  btnApplyUpdate.addEventListener('click', async () => {
    if (!updateTarget){
      updMsg.textContent = 'No hay archivo seleccionado.';
      return;
    }
    const f = fileUpdate.files?.[0];
    if (!f){
      updMsg.textContent = 'Selecciona el archivo nuevo antes de aplicar.';
      return;
    }

    updMsg.textContent = 'Aplicando actualización...';

    const fd = new FormData();
    fd.append('id_archivo', updateTarget.id_archivo);
    fd.append('file', f);

    const res = await fetch('/api/archivos/update', {
      method:'POST',
      body: fd
    });

    const data = await res.json().catch(() => ({}));
    if (!res.ok){
      updMsg.textContent = data.message || 'No se pudo actualizar.';
      return;
    }

    updMsg.textContent = 'Actualizado. Estado PENDIENTE.';
    closeUpdateModal();
    await loadList();
  });

  // filtros
  [fNombreArchivo, fUsuario, fMes, fEstado].forEach(el => {
    el.addEventListener('input', renderTable);
    el.addEventListener('change', renderTable);
  });

  btnClear.addEventListener('click', () => {
    fNombreArchivo.value = '';
    fUsuario.value = '';
    fMes.value = '';
    fEstado.value = '';
    renderTable();
  });

  loadList();
})();
