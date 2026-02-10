(() => {
  // =========================
  // Permisos
  // =========================
  const permsTag = document.getElementById('biologicos-perms');
  let CAN_MANAGE = false;
  try {
    const perms = permsTag ? JSON.parse(permsTag.textContent) : {};
    CAN_MANAGE = !!perms.can_manage;
  } catch { CAN_MANAGE = false; }

  // =========================
  // Focus (desde alertas)
  // =========================
  function getFocusParams(){
    const sp = new URLSearchParams(window.location.search);
    return {
      focusId: (sp.get('focus_id') || '').trim(),
      focusLote: (sp.get('lote') || '').trim(),
    };
  }
  const FOCUS = getFocusParams();
  let pendingFocusLote = FOCUS.focusLote || null;

  function clearFocusParamsFromUrl(){
    try {
      const url = new URL(window.location.href);
      url.searchParams.delete('focus_id');
      url.searchParams.delete('lote');
      window.history.replaceState({}, document.title, url.pathname + url.search);
    } catch {}
  }

  function applyFocusToLoteRow(lote){
    if (!lote) return false;
    const rows = Array.from(document.querySelectorAll('#lotBody tr'));
    const tr = rows.find(r => (r.dataset?.lote || '').trim() === lote);
    if (!tr) return false;

    tr.scrollIntoView({ behavior: 'smooth', block: 'center' });

    const prevOutline = tr.style.outline;
    const prevBg = tr.style.background;
    tr.style.outline = '2px solid #f59e0b';
    tr.style.background = '#fff7ed';

    setTimeout(() => {
      tr.style.outline = prevOutline;
      tr.style.background = prevBg;
    }, 2500);

    return true;
  }

  // =========================
  // Helpers UI / Fetch
  // =========================
  const show = (el) => el && el.classList.remove('hidden');
  const hide = (el) => el && el.classList.add('hidden');

  async function fetchJSON(url){
    const res = await fetch(url, { cache: 'no-store' });
    const data = await res.json().catch(() => null);
    if (!res.ok){
      console.error("API ERROR:", url, data);
      return null;
    }
    return data;
  }

  async function postJSON(url, payload){
    const res = await fetch(url, {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify(payload)
    });
    const data = await res.json().catch(() => ({}));
    return { res, data };
  }

  // =========================
  // DOM
  // =========================
  const pageTitle = document.getElementById('pageTitle');
  const pageSub = document.getElementById('pageSub');
  const btnBack = document.getElementById('btnBack');
  const btnRegistrar = document.getElementById('btnRegistrar');

  const listView = document.getElementById('listView');
  const bioContainer = document.getElementById('bioContainer');
  const qBio = document.getElementById('qBio');

  const detailSection = document.getElementById('detailSection');
  const detailTitle = document.getElementById('detailTitle');
  const detailSummary = document.getElementById('detailSummary');
  const lotBody = document.getElementById('lotBody');

  const insumosBlock = document.getElementById('insumosBlock');
  const insumoList = document.getElementById('insumoList');
  const thActions = document.getElementById('thActions');

  // ===== Modal =====
  const modalBio = document.getElementById('modalBiologico');
  const modalBioBackdrop = document.getElementById('modalBiologicoBackdrop');
  const modalBioClose = document.getElementById('modalBiologicoClose');

  const formBio = document.getElementById('formBiologico');
  const formMsg = document.getElementById('formMsg');

  const fNombre = document.getElementById('fNombreBiologico');
  const fLote = document.getElementById('fLote');
  const fCadDate = document.getElementById('fCadDate');

  const fVia = document.getElementById('fVia');
  const fDosisPorFrasco = document.getElementById('fDosisPorFrasco');
  const fDosisAdministrada = document.getElementById('fDosisAdministrada');

  const fAngulo = document.getElementById('fAngulo');
  const fDesc = document.getElementById('fDesc');

  const fCajas = document.getElementById('fCajas');
  const fFrascosPorCaja = document.getElementById('fFrascosPorCaja');
  const fFrascosTotales = document.getElementById('fFrascosTotales');

  const btnCalcFrascos = document.getElementById('btnCalcFrascos');
  const btnGuardarBio = document.getElementById('btnGuardarBio') || null;

  const fJeringaTipo = document.getElementById('fJeringaTipo');
  const btnAddJeringa = document.getElementById('btnAddJeringa');
  const selectedJeringasWrap = document.getElementById('selectedJeringasWrap');
  const selectedJeringasList = document.getElementById('selectedJeringasList');

  // =========================
  // Estado
  // =========================
  let currentNombre = null;
  let currentLotes = [];
  let selectedJeringas = [];

  let modalMode = 'create'; // 'create' | 'edit'
  let editingLote = null;

  // =========================
  // Ángulo por vía
  // =========================
  const VIA_ANGULO_DEFAULT = { IM:"90°", ID:"15°", SC:"45°", VO:"BOCA" };

  function applyDefaultAngulo(force=false){
    const via = (fVia?.value || "").trim().toUpperCase();
    const def = VIA_ANGULO_DEFAULT[via] || "";
    if (!def || !fAngulo) return;

    const cur = (fAngulo.value || "").trim();
    const isDef = ["90°","15°","45°","BOCA"].includes(cur.toUpperCase());
    if (force || !cur || isDef) fAngulo.value = def;
  }

  // =========================
  // Limpieza / Header
  // =========================
  function clearDetailUI(){
    detailTitle.textContent = "Detalle";
    detailSummary.innerHTML = "";
    lotBody.innerHTML = "";
    insumoList.innerHTML = "";
    hide(insumosBlock);
  }

  function setHeaderList(){
    pageTitle.textContent = 'Biológicos';
    pageSub.textContent = 'Seleccione un biológico para ver los detalles de la vacuna.';
    hide(btnBack);
    show(listView);
    hide(detailSection);
    clearDetailUI();
    if (CAN_MANAGE) show(btnRegistrar); else hide(btnRegistrar);
  }

  function setHeaderDetail(nombre){
    pageTitle.textContent = `Biológicos – ${nombre}`;
    pageSub.textContent = 'Detalle de vacunas y lotes registrados.';
    show(btnBack);
    hide(listView);
    show(detailSection);
    if (CAN_MANAGE) show(btnRegistrar); else hide(btnRegistrar);
  }

  // =========================
  // Lista
  // =========================
  async function loadBiologicos(){
    const q = encodeURIComponent((qBio?.value || "").trim());
    const ts = Date.now();
    const data = await fetchJSON(`/api/biologicos/nombres?q=${q}&_ts=${ts}`);
    renderBiologicos(Array.isArray(data) ? data : []);
  }

  function renderBiologicos(items){
    bioContainer.innerHTML = '';
    if (!items.length){
      bioContainer.innerHTML = `<div class="empty">No hay biológicos registrados.</div>`;
      return;
    }

    items.forEach(b => {
      const nombre = b.nombre_biologico || '';
      const cajas = b.total_cajas ?? 0;
      const frascos = b.total_frascos ?? 0;

      const card = document.createElement('div');
      card.className = 'bio-card';
      card.innerHTML = `
        <h4 class="bio-name">${nombre}</h4>
        <div class="bio-kpis">
          <span class="kpi">Cajas: <b>${cajas}</b></span>
          <span class="kpi">Frascos: <b>${frascos}</b></span>
        </div>
      `;
      card.addEventListener('click', () => {
        currentNombre = nombre;
        loadDetail(nombre);
      });
      bioContainer.appendChild(card);
    });
  }

  // =========================
  // Detalle
  // =========================
  async function loadDetail(nombre){
    setHeaderDetail(nombre);
    detailTitle.textContent = `Detalle – ${nombre}`;

    const ts = Date.now();

    currentLotes = await fetchJSON(`/api/biologicos/lotes?nombre=${encodeURIComponent(nombre)}&_ts=${ts}`);
    currentLotes = Array.isArray(currentLotes) ? currentLotes : [];
    renderLotes(currentLotes);

    const ins = await fetchJSON(`/api/biologicos/insumos?nombre=${encodeURIComponent(nombre)}&_ts=${ts}`);
    renderInsumos(Array.isArray(ins) ? ins : []);

    // aplicar focus
    if (pendingFocusLote) {
      const ok = applyFocusToLoteRow(pendingFocusLote);
      if (ok) {
        pendingFocusLote = null;
        clearFocusParamsFromUrl();
      }
    }
  }

  function renderLotes(lotes){
    // Totales SOLO activos (como quedó pepa)
    const activos = lotes.filter(x => !!x.estado);
    const totalCajasAct = activos.reduce((a,x) => a + Number(x.cajas || 0), 0);
    const totalFrascosAct = activos.reduce((a,x) => a + Number(x.frascos || 0), 0);
    const inactivosCount = lotes.length - activos.length;

    detailSummary.innerHTML = `
      <span>Cajas (activos): <b>${totalCajasAct}</b></span>
      <span>Frascos (activos): <b>${totalFrascosAct}</b></span>
      ${inactivosCount > 0 ? `<span class="muted">Inactivos: <b>${inactivosCount}</b></span>` : ''}
    `;

    if (thActions){
      if (CAN_MANAGE) thActions.classList.remove('hidden');
      else thActions.classList.add('hidden');
    }

    lotBody.innerHTML = '';
    if (!lotes.length){
      lotBody.innerHTML = `<tr><td colspan="${CAN_MANAGE ? 9 : 8}" class="empty-row">No hay lotes para este biológico.</td></tr>`;
      return;
    }

    lotes.forEach(l => {
      const estado = !!l.estado;
      const tr = document.createElement('tr');

      const actions = CAN_MANAGE ? `
        <div class="actions">
          <button class="btn-mini" type="button" data-action="edit-lote">Editar</button>
          <button class="btn-mini ${estado ? 'danger' : ''}" type="button" data-action="toggle-lote">
            ${estado ? 'Desactivar' : 'Activar'}
          </button>
        </div>
      ` : '';

      tr.innerHTML = `
        <td>${l.lote || '—'}</td>
        <td>${l.fecha_caducidad || '—'}</td>
        <td>${(l.via || '').toUpperCase() || '—'}</td>
        <td class="right">${l.cajas ?? 0}</td>
        <td class="right">${l.frascos_por_caja ?? 0}</td>
        <td class="right">${l.frascos ?? 0}</td>
        <td>${l.angulo || '—'}</td>
        <td>${estado ? '<span class="pill pill-ok">ACTIVO</span>' : '<span class="pill pill-bad">INACTIVO</span>'}</td>
        ${CAN_MANAGE ? `<td>${actions}</td>` : ``}
      `;

      tr.dataset.lote = l.lote || '';
      tr.dataset.estado = estado ? 'true' : 'false';
      tr.dataset.cad = l.fecha_caducidad || '';
      tr.dataset.via = (l.via || '').toUpperCase();
      tr.dataset.cajas = String(l.cajas ?? 0);
      tr.dataset.fxc = String(l.frascos_por_caja ?? 1);
      tr.dataset.angulo = l.angulo || '';
      tr.dataset.desc = l.descripcion || '';
      tr.dataset.dpf = String(l.dosis_por_frasco ?? 1);
      tr.dataset.dadm = String(l.dosis_administrada ?? 0.5);

      lotBody.appendChild(tr);
    });
  }

  function renderInsumos(insumos){
    if (!insumos.length){
      hide(insumosBlock);
      insumoList.innerHTML = '';
      return;
    }
    show(insumosBlock);
    insumoList.innerHTML = '';
    insumos.forEach(x => {
      const li = document.createElement('li');
      li.innerHTML = `<b>${x.categoria_insumo}</b> – ${x.nombre_tipo_insumo}`;
      insumoList.appendChild(li);
    });
  }

  // =========================
  // Modal helpers
  // =========================
  function renderSelectedJeringas(){
    if (!selectedJeringas.length){
      hide(selectedJeringasWrap);
      selectedJeringasList.innerHTML = '';
      return;
    }
    show(selectedJeringasWrap);
    selectedJeringasList.innerHTML = '';
    selectedJeringas.forEach(name => {
      const chip = document.createElement('div');
      chip.className = 'chip';
      chip.innerHTML = `<span>${name}</span><button type="button" class="chip-x" data-name="${name}">×</button>`;
      selectedJeringasList.appendChild(chip);
    });
  }

  async function loadJeringasTipos(){
    fJeringaTipo.innerHTML = `<option value="">Cargando...</option>`;
    const tipos = await fetchJSON(`/api/insumos/tipos?categoria=JERINGAS&estado=true&_ts=${Date.now()}`);
    fJeringaTipo.innerHTML = `<option value="">Seleccione...</option>`;
    (Array.isArray(tipos) ? tipos : []).forEach(t => {
      if (!t.nombre_tipo) return;
      const opt = document.createElement('option');
      opt.value = t.nombre_tipo;
      opt.textContent = t.nombre_tipo;
      fJeringaTipo.appendChild(opt);
    });
  }

  async function prefillFromExisting(nombreUpper){
    const ins = await fetchJSON(`/api/biologicos/insumos?nombre=${encodeURIComponent(nombreUpper)}&_ts=${Date.now()}`);
    const jers = Array.isArray(ins) ? ins.map(x => x.nombre_tipo_insumo).filter(Boolean) : [];
    selectedJeringas = [...new Set(jers)];
    renderSelectedJeringas();

    const lotes = await fetchJSON(`/api/biologicos/lotes?nombre=${encodeURIComponent(nombreUpper)}&_ts=${Date.now()}`);
    if (Array.isArray(lotes) && lotes.length){
      const l0 = lotes[0];
      fVia.value = (l0.via || 'IM').toUpperCase();
      fDosisPorFrasco.value = l0.dosis_por_frasco ?? '1';
      fDosisAdministrada.value = l0.dosis_administrada ?? '0.5';
      fAngulo.value = l0.angulo || '';
      fDesc.value = l0.descripcion || '';
      fFrascosPorCaja.value = l0.frascos_por_caja ?? '1';
      applyDefaultAngulo(true);
      return true;
    }
    return false;
  }

  function resetModal(){
    formMsg.textContent = '';
    modalMode = 'create';
    editingLote = null;

    fNombre.value = currentNombre || '';
    fLote.value = '';
    fCadDate.value = '';

    fVia.value = 'IM';
    fDosisPorFrasco.value = '1';
    fDosisAdministrada.value = '0.5';
    fAngulo.value = '';
    fDesc.value = '';

    fCajas.value = '0';
    fFrascosPorCaja.value = '1';
    fFrascosTotales.value = '0';

    selectedJeringas = [];
    renderSelectedJeringas();
    applyDefaultAngulo(true);

    // habilitar en registrar
    fNombre.readOnly = false;
    fLote.readOnly = false;
    fVia.disabled = false;
    fAngulo.readOnly = false;

    btnAddJeringa.disabled = false;
    fJeringaTipo.disabled = false;
    show(selectedJeringasWrap);

    if (btnGuardarBio) btnGuardarBio.textContent = 'Guardar';
  }

  async function openModalCreate(){
    if (!CAN_MANAGE) return;
    resetModal();
    show(modalBio);
    await loadJeringasTipos();

    const nombreUpper = (fNombre.value || '').trim().toUpperCase();
    if (nombreUpper) {
      await prefillFromExisting(nombreUpper);
    }
  }

  function openModalEditFromRow(tr){
    if (!CAN_MANAGE) return;
    if (!tr) return;

    resetModal();
    show(modalBio);

    modalMode = 'edit';
    editingLote = tr.dataset.lote;

    fNombre.value = (currentNombre || '').toUpperCase();
    fLote.value = tr.dataset.lote || '';
    fCadDate.value = tr.dataset.cad || '';

    fVia.value = (tr.dataset.via || 'IM').toUpperCase();
    fDosisPorFrasco.value = tr.dataset.dpf || '1';
    fDosisAdministrada.value = tr.dataset.dadm || '0.5';
    fAngulo.value = tr.dataset.angulo || '';
    fDesc.value = tr.dataset.desc || '';

    fCajas.value = tr.dataset.cajas || '0';
    fFrascosPorCaja.value = tr.dataset.fxc || '1';
    fFrascosTotales.value = String(Number(fCajas.value || 0) * Number(fFrascosPorCaja.value || 1));

    // En editar: NO permite cambiar nombre/lote/via/angulo
    fNombre.readOnly = true;
    fLote.readOnly = true;
    fVia.disabled = true;
    fAngulo.readOnly = true;

    // En editar: no tocamos jeringas
    selectedJeringas = [];
    renderSelectedJeringas();
    hide(selectedJeringasWrap);
    btnAddJeringa.disabled = true;
    fJeringaTipo.disabled = true;

    if (btnGuardarBio) btnGuardarBio.textContent = 'Guardar cambios';
  }

  function closeModal(){
    hide(modalBio);
  }

  modalBioBackdrop?.addEventListener('click', closeModal);
  modalBioClose?.addEventListener('click', closeModal);

  fVia?.addEventListener('change', () => applyDefaultAngulo(true));

  btnCalcFrascos?.addEventListener('click', () => {
    const cajas = Number(fCajas.value || 0);
    const fxc = Number(fFrascosPorCaja.value || 0);
    const total = Math.max(0, cajas * fxc);
    fFrascosTotales.value = String(total);
    formMsg.textContent = `Autocalculado: ${total} frascos totales.`;
  });

  btnAddJeringa?.addEventListener('click', () => {
    const val = (fJeringaTipo.value || '').trim();
    if (!val) return;
    if (!selectedJeringas.includes(val)){
      selectedJeringas.push(val);
      renderSelectedJeringas();
    }
    fJeringaTipo.value = '';
  });

  // =========================
  // Delegación de clicks (async)
  // =========================
  document.addEventListener('click', async (e) => {
    const btn = e.target;
    if (!(btn instanceof HTMLElement)) return;

    if (btn.classList.contains('chip-x')){
      const name = btn.dataset.name;
      selectedJeringas = selectedJeringas.filter(x => x !== name);
      renderSelectedJeringas();
      return;
    }

    if (btn.dataset.action === 'toggle-lote'){
      if (!CAN_MANAGE) return;
      const tr = btn.closest('tr');
      if (!tr) return;

      const lote = tr.dataset.lote;
      const estadoActual = tr.dataset.estado === 'true';
      const nuevoEstado = !estadoActual;

      btn.disabled = true;

      const { res, data } = await postJSON('/api/biologicos/estado-lote', {
        nombre_biologico: currentNombre,
        lote,
        estado: nuevoEstado
      });

      if (!res.ok){
        btn.disabled = false;
        alert(data.message || 'No se pudo actualizar.');
        return;
      }

      await loadDetail(currentNombre);
      await loadBiologicos();
      btn.disabled = false;
      return;
    }

    if (btn.dataset.action === 'edit-lote'){
      const tr = btn.closest('tr');
      openModalEditFromRow(tr);
      return;
    }
  });

  // =========================
  // Submit (registrar o editar)
  // =========================
  formBio?.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!CAN_MANAGE) return;

    applyDefaultAngulo(true);

    const nombreUpper = (fNombre.value || '').trim().toUpperCase();

    const cajas = Number(fCajas.value || 0);
    const fxc = Number(fFrascosPorCaja.value || 0);
    const frascosTotal = Math.max(0, cajas) * Math.max(1, fxc);
    fFrascosTotales.value = String(frascosTotal);

    if (!nombreUpper || !(fLote.value || '').trim() || !(fCadDate.value || '').trim()){
      formMsg.textContent = 'Completa: biológico, lote y caducidad.';
      return;
    }

    if (modalMode === 'edit'){
      const payload = {
        nombre_biologico: nombreUpper,
        lote: (fLote.value || '').trim(),
        fecha_caducidad: (fCadDate.value || '').trim(),
        via: (fVia.value || '').trim().toUpperCase(),
        dosis_por_frasco: Number(fDosisPorFrasco.value || 0),
        dosis_administrada: Number(fDosisAdministrada.value || 0),
        angulo: (fAngulo.value || '').trim(),
        descripcion: (fDesc.value || '').trim(),
        cajas: cajas,
        frascos_por_caja: fxc,
        frascos: frascosTotal
      };

      const { res, data } = await postJSON('/api/biologicos/editar-lote', payload);
      if (!res.ok){
        formMsg.textContent = data.message || 'Error actualizando lote.';
        return;
      }

      closeModal();
      await loadDetail(currentNombre);
      await loadBiologicos();
      return;
    }

    // registrar
    const payload = {
      nombre_biologico: nombreUpper,
      lote: (fLote.value || '').trim(),
      fecha_caducidad: (fCadDate.value || '').trim(),
      via: (fVia.value || '').trim().toUpperCase(),
      dosis_por_frasco: Number(fDosisPorFrasco.value || 0),
      dosis_administrada: Number(fDosisAdministrada.value || 0),
      angulo: (fAngulo.value || '').trim(),
      descripcion: (fDesc.value || '').trim(),
      cajas: cajas,
      frascos_por_caja: fxc,
      frascos: frascosTotal,
      jeringas_asociadas: selectedJeringas
    };

    const { res, data } = await postJSON('/api/biologicos/registrar', payload);
    if (!res.ok){
      formMsg.textContent = data.message || 'Error registrando biológico.';
      return;
    }

    closeModal();
    await loadBiologicos();
    if (currentNombre) await loadDetail(currentNombre);
  });

  // =========================
  // Eventos
  // =========================
  btnRegistrar?.addEventListener('click', openModalCreate);

  btnBack?.addEventListener('click', () => {
    currentNombre = null;
    currentLotes = [];
    selectedJeringas = [];
    clearDetailUI();
    setHeaderList();
    loadBiologicos();
  });

  qBio?.addEventListener('input', loadBiologicos);

  // =========================
  // Boot
  // =========================
  if (CAN_MANAGE) show(btnRegistrar); else hide(btnRegistrar);
  setHeaderList();
  loadBiologicos();

  //  Auto-abrir desde focus (requiere /api/biologicos/focus)
  (async () => {
    if (!FOCUS.focusId && !FOCUS.focusLote) return;

    const r = await fetchJSON(
      `/api/biologicos/focus?focus_id=${encodeURIComponent(FOCUS.focusId)}&lote=${encodeURIComponent(FOCUS.focusLote)}&_ts=${Date.now()}`
    );

    if (!r || !r.ok || !r.nombre_biologico) return;

    currentNombre = r.nombre_biologico;
    pendingFocusLote = FOCUS.focusLote || r.lote || null;

    await loadDetail(currentNombre);
    await loadBiologicos();
  })();
})();
