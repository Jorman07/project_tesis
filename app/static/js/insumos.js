(() => {
  // =========================
  // Permisos
  // =========================
  const permsTag = document.getElementById('insumos-perms');
  let CAN_MANAGE = false;
  try {
    const perms = permsTag ? JSON.parse(permsTag.textContent) : {};
    CAN_MANAGE = !!perms.can_manage; // solo ADMINISTRADOR
  } catch { CAN_MANAGE = false; }

  // =========================
  // Focus params (desde alertas)
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
  // DOM (vista principal)
  // =========================
  const pageTitle = document.getElementById('pageTitle');
  const pageSub = document.getElementById('pageSub');
  const btnBack = document.getElementById('btnBack');
  const btnRegistrar = document.getElementById('btnRegistrar');

  const categoriesView = document.getElementById('categoriesView');
  const typesView = document.getElementById('typesView');

  const catContainer = document.getElementById('catContainer');
  const typesContainer = document.getElementById('typesContainer');
  const qTipo = document.getElementById('qTipo');

  const detailSection = document.getElementById('detailSection');
  const detailTitle = document.getElementById('detailTitle');
  const detailSummary = document.getElementById('detailSummary');
  const lotBody = document.getElementById('lotBody');

  const vaccinesBlock = document.getElementById('vaccinesBlock');
  const vacList = document.getElementById('vacList');

  // ===== filtros de detalle =====
  const fLote = document.getElementById('fLote');
  const fEstadoLote = document.getElementById('fEstadoLote');
  const fExpLote = document.getElementById('fExpLote');

  const fFabFrom = document.getElementById('fFabFrom');
  const fFabTo = document.getElementById('fFabTo');
  const fFabExact = document.getElementById('fFabExact');

  const fCadFrom = document.getElementById('fCadFrom');
  const fCadTo = document.getElementById('fCadTo');
  const fCadExact = document.getElementById('fCadExact');

  const btnClearDetail = document.getElementById('btnClearDetail');

  // ===== Modal registrar insumo =====
  const modalInsumo = document.getElementById('modalInsumo');
  const modalInsumoBackdrop = document.getElementById('modalInsumoBackdrop');
  const modalInsumoClose = document.getElementById('modalInsumoClose');

  const formInsumo = document.getElementById('formInsumo');
  const formMsg = document.getElementById('formMsg');

  const fCat = document.getElementById('fCat');
  const newCatBlock = document.getElementById('newCatBlock');
  const fNewCat = document.getElementById('fNewCat');

  const fTipo = document.getElementById('fTipo');
  const fLoteReg = document.getElementById('fLoteReg');
  const fPacks = document.getElementById('fPacks');
  const fUnidades = document.getElementById('fUnidades');
  const fFabMonth = document.getElementById('fFabMonth');
  const fCadMonth = document.getElementById('fCadMonth');

  const lblPacks = document.getElementById('lblPacks');
  const hintPacks = document.getElementById('hintPacks');
  const hintTipo = document.getElementById('hintTipo');

  const alcoholCapBlock = document.getElementById('alcoholCapBlock');
  const fAlcoholCap = document.getElementById('fAlcoholCap');

  const btnCalc = document.getElementById('btnCalc');

  // ===== Modal editar lote =====
  const modalEditLote = document.getElementById('modalEditLote');
  const modalEditLoteBackdrop = document.getElementById('modalEditLoteBackdrop');
  const modalEditLoteClose = document.getElementById('modalEditLoteClose');
  const btnEditCancel = document.getElementById('btnEditCancel');

  const formEditLote = document.getElementById('formEditLote');
  const editInfo = document.getElementById('editInfo');
  const editMsg = document.getElementById('editMsg');

  const eLote = document.getElementById('eLote');
  const ePacks = document.getElementById('ePacks');
  const eFabMonth = document.getElementById('eFabMonth');
  const eCadMonth = document.getElementById('eCadMonth');

  // =========================
  // Estado UI
  // =========================
  let currentCategory = null;
  let currentSelectedTipo = null;
  let currentLotes = [];

  // =========================
  // Helpers UI / Fetch
  // =========================
  function show(el){ el && el.classList.remove('hidden'); }
  function hide(el){ el && el.classList.add('hidden'); }

  async function fetchJSON(url){
    const res = await fetch(url, { cache: 'no-store' });
    if (!res.ok) return [];
    return await res.json().catch(() => []);
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

  function setHeaderDefault(){
    pageTitle.textContent = 'Gestión de Insumos';
    pageSub.textContent = 'Seleccione una categoría para ver los tipos disponibles.';
    hide(btnBack);
    hide(typesView);
    hide(detailSection);
    show(categoriesView);
    CAN_MANAGE ? show(btnRegistrar) : hide(btnRegistrar);
  }

  function setHeaderCategory(cat){
    pageTitle.textContent = `Gestión de Insumos – ${cat}`;
    pageSub.textContent = 'Seleccione un tipo para ver detalle por lote y recomendaciones.';
    show(btnBack);
    hide(categoriesView);
    show(typesView);
    CAN_MANAGE ? show(btnRegistrar) : hide(btnRegistrar);
  }

  function syncActionsColumnVisibility(){
    const table = lotBody?.closest('table');
    if (!table) return;

    const ths = table.querySelectorAll('thead th');
    if (ths.length) {
      const lastTh = ths[ths.length - 1];
      if (lastTh) lastTh.style.display = CAN_MANAGE ? '' : 'none';
    }

    table.querySelectorAll('tbody tr').forEach(tr => {
      const cells = tr.children;
      if (!cells || !cells.length) return;
      const lastTd = cells[cells.length - 1];
      if (lastTd) lastTd.style.display = CAN_MANAGE ? '' : 'none';
    });
  }

  // =========================
  // Modal registrar
  // =========================
  function resetModalKeepCatType(){
    if (formMsg) formMsg.textContent = '';
    if (fLoteReg) fLoteReg.value = '';
    if (fPacks) fPacks.value = '0';
    if (fUnidades) fUnidades.value = '0';
    if (fFabMonth) fFabMonth.value = '';
    if (fCadMonth) fCadMonth.value = '';
    if (fAlcoholCap) fAlcoholCap.value = '1000';
  }

  function resetModalFull(){
    if (formMsg) formMsg.textContent = '';
    if (fCat) fCat.value = '';
    if (fTipo) {
      fTipo.value = '';
      fTipo.placeholder = 'Nombre del tipo';
    }
    if (fLoteReg) fLoteReg.value = '';
    if (fPacks) fPacks.value = '0';
    if (fUnidades) fUnidades.value = '0';
    if (fFabMonth) fFabMonth.value = '';
    if (fCadMonth) fCadMonth.value = '';

    if (fAlcoholCap) fAlcoholCap.value = '1000';
    if (alcoholCapBlock) hide(alcoholCapBlock);

    if (newCatBlock) hide(newCatBlock);
    if (fNewCat) fNewCat.value = '';

    if (lblPacks) lblPacks.textContent = 'Packs';
    if (hintPacks) hintPacks.textContent = '';
    if (hintTipo) hintTipo.textContent = '';
  }

  function closeModalInsumo(){
    hide(modalInsumo);
    resetModalKeepCatType();
  }

  function parseAlcoholCapFromTipoName(name){
    if (!name) return null;
    const lower = name.toLowerCase();
    if (lower.includes('galon') || lower.includes('galón')) return 3785;
    const m = lower.match(/(\d{2,4})\s*ml/);
    if (m) return Number(m[1]);
    return null;
  }

  function removeAlcoholCapFromTipoName(name){
    if (!name) return '';
    return name
      .replace(/(\d{2,4})\s*ml/ig, '')
      .replace(/gal[oó]n/ig, '')
      .replace(/\s+/g, ' ')
      .trim();
  }

  function updateModalByCategory(){
    const cat = (fCat.value || '').toUpperCase();

    if (cat === 'OTRO') show(newCatBlock);
    else {
      hide(newCatBlock);
      if (fNewCat) fNewCat.value = '';
    }

    if (fTipo) {
      if (cat === 'JERINGAS') fTipo.placeholder = 'Ej: 26G x 3/8" 1ml TB';
      else if (cat === 'GUANTES') fTipo.placeholder = 'Ej: Guantes Latex MEDIUM';
      else if (cat === 'ALCOHOL') fTipo.placeholder = 'Ej: Alcohol 70%';
      else if (cat === 'ALGODON') fTipo.placeholder = 'Ej: Algodón Hidrófilo Rollo';
      else fTipo.placeholder = 'Nombre del tipo';
    }

    if (hintTipo) {
      if (cat === 'ALCOHOL') hintTipo.textContent = 'Selecciona la capacidad (ml). El sistema guarda el tipo como: "Alcohol 70% 1000ml".';
      else if (cat === 'ALGODON') hintTipo.textContent = 'Nota: 1 paquete = 3 rollos.';
      else hintTipo.textContent = '';
    }

    if (cat === 'JERINGAS' || cat === 'GUANTES') {
      if (lblPacks) lblPacks.textContent = 'Cajas';
      if (hintPacks) hintPacks.textContent = 'Ej: 6 cajas';
      hide(alcoholCapBlock);
    } else if (cat === 'ALCOHOL') {
      if (lblPacks) lblPacks.textContent = 'Botellas';
      if (hintPacks) hintPacks.textContent = 'Ej: 10 botellas';
      show(alcoholCapBlock);
    } else if (cat === 'ALGODON') {
      if (lblPacks) lblPacks.textContent = 'Paquetes';
      if (hintPacks) hintPacks.textContent = '1 paquete = 3 rollos';
      hide(alcoholCapBlock);
    } else {
      if (lblPacks) lblPacks.textContent = 'Packs';
      if (hintPacks) hintPacks.textContent = '';
      hide(alcoholCapBlock);
    }
  }

  function openModalInsumo(){
    show(modalInsumo);
    if (formMsg) formMsg.textContent = '';

    if (currentCategory && fCat) fCat.value = currentCategory;

    const cat = (fCat.value || '').toUpperCase();

    if (cat === 'ALCOHOL') {
      show(alcoholCapBlock);

      if (currentSelectedTipo?.nombre_tipo) {
        const selName = currentSelectedTipo.nombre_tipo;
        const cap = parseAlcoholCapFromTipoName(selName);
        const base = removeAlcoholCapFromTipoName(selName);

        if (fTipo) fTipo.value = base || 'Alcohol 70%';
        if (fAlcoholCap) fAlcoholCap.value = String(cap || 1000);
      } else {
        if (fTipo) fTipo.value = 'Alcohol 70%';
        if (fAlcoholCap) fAlcoholCap.value = '1000';
      }
    } else {
      hide(alcoholCapBlock);
      if (currentSelectedTipo?.nombre_tipo && fTipo) fTipo.value = currentSelectedTipo.nombre_tipo;
    }

    updateModalByCategory();
  }

  // =========================
  // Categorías
  // =========================
  async function loadCategories(){
    const cats = await fetchJSON(`/api/insumos/categorias?_ts=${Date.now()}`);
    renderCategories((cats || []).map(x => x.categoria || x));
  }

  function renderCategories(cats){
    const ICONS = {
      JERINGAS: { icon: '💉', desc: 'Tipos por calibre y tamaño' },
      GUANTES:  { icon: '🧤', desc: 'Cajas y Pares' },
      ALCOHOL:  { icon: '🧴', desc: 'Litros y mililitros' },
      ALGODON:  { icon: '☁️', desc: 'Rollos' },
      OTRO:     { icon: '📦', desc: 'Otros insumos' },
    };

    catContainer.innerHTML = '';
    cats.forEach(c => {
      const meta = ICONS[c] || ICONS.OTRO;
      const card = document.createElement('div');
      card.className = 'cat-card';
      card.innerHTML = `
        <div class="cat-icon">${meta.icon}</div>
        <div class="cat-info">
          <h4>${c}</h4>
          <p>${meta.desc}</p>
        </div>
      `;
      card.addEventListener('click', () => {
        currentCategory = c;
        currentSelectedTipo = null;
        currentLotes = [];
        qTipo.value = '';
        setHeaderCategory(c);
        loadTypes();
      });
      catContainer.appendChild(card);
    });
  }

  // =========================
  // Tipos (cards)
  // =========================
  async function loadTypes(){
    const q = encodeURIComponent((qTipo.value || '').trim());
    const url = `/api/insumos/tipos?categoria=${encodeURIComponent(currentCategory)}&q=${q}&_ts=${Date.now()}`;
    const tipos = await fetchJSON(url);
    renderTypes(Array.isArray(tipos) ? tipos : []);
    return Array.isArray(tipos) ? tipos : [];
  }

  function renderTypes(tipos){
    typesContainer.innerHTML = '';
    if (!tipos.length){
      typesContainer.innerHTML = `<div class="empty">No hay tipos para mostrar.</div>`;
      hide(detailSection);
      return;
    }

    tipos.forEach(t => {
      const card = document.createElement('div');
      card.className = 'type-card';

      const active = currentSelectedTipo && currentSelectedTipo.nombre_tipo === t.nombre_tipo;
      if (active) card.classList.add('active');

      card.innerHTML = `
        <h4 class="type-name">${t.nombre_tipo}</h4>
        <div class="type-kpis">
          <span class="kpi">Packs (activos): <b>${t.total_packs}</b></span>
          <span class="kpi">Unidades (activos): <b>${t.total_unidades}</b></span>
        </div>
      `;

      card.addEventListener('click', async () => {
        currentSelectedTipo = t;
        renderTypes(tipos);
        await loadDetail(t.nombre_tipo);
      });

      typesContainer.appendChild(card);
    });
  }

  // =========================
  // Detalle
  // =========================
  async function loadDetail(nombreTipo){
    show(detailSection);
    detailTitle.textContent = `Detalle – ${nombreTipo}`;

    clearDetailFilters(false);

    const lotesUrl = `/api/insumos/lotes?categoria=${encodeURIComponent(currentCategory)}&nombre_tipo=${encodeURIComponent(nombreTipo)}&_ts=${Date.now()}`;
    currentLotes = await fetchJSON(lotesUrl);
    currentLotes = Array.isArray(currentLotes) ? currentLotes : [];
    renderLotes(currentLotes);

    if (currentCategory === 'JERINGAS'){
      const vacs = await fetchJSON(`/api/insumos/vacunas?nombre_tipo=${encodeURIComponent(nombreTipo)}&_ts=${Date.now()}`);
      renderVacunas(vacs);
    } else {
      hide(vaccinesBlock);
      vacList.innerHTML = '';
    }

    // ✅ aplicar focus al lote si corresponde
    if (pendingFocusLote) {
      const ok = applyFocusToLoteRow(pendingFocusLote);
      if (ok) {
        pendingFocusLote = null;
        clearFocusParamsFromUrl();
      }
    }
  }

  function renderLotes(lotes){
    const activos = lotes.filter(x => !!x.estado);
    const totalPAct = activos.reduce((a, x) => a + Number(x.packs || 0), 0);
    const totalUAct = activos.reduce((a, x) => a + Number(x.unidades || 0), 0);
    const inactivosCount = lotes.length - activos.length;

    detailSummary.innerHTML = `
      <span>Packs (activos): <b>${totalPAct}</b></span>
      <span>Unidades (activos): <b>${totalUAct}</b></span>
      ${inactivosCount > 0 ? `<span class="muted">Inactivos: <b>${inactivosCount}</b></span>` : ''}
    `;

    lotBody.innerHTML = '';
    lotes.forEach(l => {
      const tr = document.createElement('tr');

      const actionsHtml = CAN_MANAGE ? `
        <button class="btn-mini" type="button" data-action="edit-lote">Editar</button>
        <button class="btn-mini ${l.estado ? 'danger' : ''}" type="button" data-action="toggle-lote">
          ${l.estado ? 'Desactivar' : 'Activar'}
        </button>
      ` : '';

      tr.innerHTML = `
        <td>${l.lote}</td>
        <td>${l.fecha_fabricacion || '—'}</td>
        <td>${l.fecha_caducidad}</td>
        <td class="right">${l.packs}</td>
        <td class="right">${l.unidades}</td>
        <td>${l.estado ? '<span class="pill pill-ok">ACTIVO</span>' : '<span class="pill pill-bad">INACTIVO</span>'}</td>
        <td><div class="actions">${actionsHtml}</div></td>
      `;

      tr.dataset.lote = l.lote;
      tr.dataset.packs = String(l.packs);
      tr.dataset.fab = l.fecha_fabricacion || '';
      tr.dataset.cad = l.fecha_caducidad;
      tr.dataset.estado = l.estado ? 'true' : 'false';

      lotBody.appendChild(tr);
    });

    syncActionsColumnVisibility();
  }

  function renderVacunas(vacs){
    if (vacs && vacs.length){
      show(vaccinesBlock);
      vacList.innerHTML = '';
      vacs.forEach(v => {
        const li = document.createElement('li');
        li.innerHTML = `<b>${v.nombre_biologico}</b> – ${v.via} – ${v.dosis_administrada} – ${v.angulo} – ${v.descripcion}`;
        vacList.appendChild(li);
      });
    } else {
      hide(vaccinesBlock);
      vacList.innerHTML = '';
    }
  }

  // =========================
  // Filtros detalle
  // =========================
  function applyDetailFilters(){
    if (!currentLotes.length) return;

    const ql = (fLote.value || '').toLowerCase().trim();
    const estSel = (fEstadoLote.value || '').trim();
    const expSel = (fExpLote.value || '').trim();

    const fabFrom = fFabFrom.value ? new Date(fFabFrom.value) : null;
    const fabTo   = fFabTo.value ? new Date(fFabTo.value) : null;
    const fabExact = fFabExact.value ? new Date(fFabExact.value) : null;

    const cadFrom = fCadFrom.value ? new Date(fCadFrom.value) : null;
    const cadTo   = fCadTo.value ? new Date(fCadTo.value) : null;
    const cadExact = fCadExact.value ? new Date(fCadExact.value) : null;

    const today = new Date();
    const expLimit = expSel ? new Date(today.getTime() + Number(expSel) * 86400000) : null;

    const filtered = currentLotes.filter(l => {
      const loteTxt = (l.lote || '').toLowerCase();
      if (ql && !loteTxt.includes(ql)) return false;

      if (estSel) {
        const est = l.estado ? 'true' : 'false';
        if (est !== estSel) return false;
      }

      const fab = l.fecha_fabricacion ? new Date(l.fecha_fabricacion) : null;
      const cad = l.fecha_caducidad ? new Date(l.fecha_caducidad) : null;

      if (expLimit && cad && cad > expLimit) return false;

      if (fabExact) {
        if (!fab || fab.getTime() !== fabExact.getTime()) return false;
      } else {
        if (fabFrom && (!fab || fab < fabFrom)) return false;
        if (fabTo   && (!fab || fab > fabTo)) return false;
      }

      if (cadExact) {
        if (!cad || cad.getTime() !== cadExact.getTime()) return false;
      } else {
        if (cadFrom && (!cad || cad < cadFrom)) return false;
        if (cadTo   && (!cad || cad > cadTo)) return false;
      }

      return true;
    });

    renderLotes(filtered);
  }

  function clearDetailFilters(reRender = true){
    fLote.value = '';
    fEstadoLote.value = '';
    fExpLote.value = '';

    fFabFrom.value = '';
    fFabTo.value = '';
    fFabExact.value = '';

    fCadFrom.value = '';
    fCadTo.value = '';
    fCadExact.value = '';

    if (reRender) renderLotes(currentLotes);
  }

  btnClearDetail?.addEventListener('click', () => clearDetailFilters(true));

  // =========================
  // Modal editar lote (ADMIN)
  // =========================
  function openEditModalFromRow(tr){
    if (!tr || !CAN_MANAGE) return;

    if (editMsg) editMsg.textContent = '';

    const lote = tr.dataset.lote || '';
    const packs = tr.dataset.packs || '0';
    const fab = tr.dataset.fab || '';
    const cad = tr.dataset.cad || '';

    if (eLote) eLote.value = lote;
    if (ePacks) ePacks.value = packs;

    if (eFabMonth) eFabMonth.value = fab ? fab.slice(0,7) : '';
    if (eCadMonth) eCadMonth.value = cad ? cad.slice(0,7) : '';

    if (editInfo) {
      editInfo.textContent = `Categoría: ${currentCategory} • Tipo: ${currentSelectedTipo?.nombre_tipo || ''}`;
    }

    show(modalEditLote);
  }

  function closeEditModal(){ hide(modalEditLote); }

  modalEditLoteBackdrop?.addEventListener('click', closeEditModal);
  modalEditLoteClose?.addEventListener('click', closeEditModal);
  btnEditCancel?.addEventListener('click', closeEditModal);

  // =========================
  // Delegación (async)
  // =========================
  document.addEventListener('click', async (e) => {
    const btn = e.target;
    if (!(btn instanceof HTMLElement)) return;

    if (btn.dataset.action === 'edit-lote') {
      const tr = btn.closest('tr');
      openEditModalFromRow(tr);
      return;
    }

    if (btn.dataset.action === 'toggle-lote') {
      if (!CAN_MANAGE) return;

      const tr = btn.closest('tr');
      if (!tr) return;

      const lote = tr.dataset.lote;
      const estadoActual = tr.dataset.estado === 'true';
      const nuevoEstado = !estadoActual;

      if (!currentCategory || !currentSelectedTipo?.nombre_tipo) {
        alert('Selecciona un tipo primero.');
        return;
      }

      btn.disabled = true;

      const { res, data } = await postJSON('/api/insumos/estado-lote', {
        categoria: currentCategory,
        nombre_tipo: currentSelectedTipo.nombre_tipo,
        lote: lote,
        estado: nuevoEstado
      });

      if (!res.ok) {
        btn.disabled = false;
        alert(data.message || 'No se pudo actualizar el estado.');
        return;
      }

      await loadDetail(currentSelectedTipo.nombre_tipo);
      await loadTypes();
      btn.disabled = false;
      return;
    }
  });

  // =========================
  // Submit editar lote
  // =========================
  formEditLote?.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!CAN_MANAGE) return;

    if (editMsg) editMsg.textContent = '';

    const payload = {
      categoria: currentCategory,
      nombre_tipo: currentSelectedTipo?.nombre_tipo,
      lote: eLote?.value || '',
      packs: Number(ePacks?.value || 0),
      fab_month: (eFabMonth?.value || '').trim(),
      cad_month: (eCadMonth?.value || '').trim()
    };

    if (!payload.categoria || !payload.nombre_tipo || !payload.lote || !payload.cad_month) {
      if (editMsg) editMsg.textContent = 'Completa packs y caducidad (mes-año).';
      return;
    }

    const { res, data } = await postJSON('/api/insumos/editar-lote', payload);

    if (!res.ok) {
      if (editMsg) editMsg.textContent = data.message || 'Error al actualizar.';
      return;
    }

    closeEditModal();
    await loadDetail(currentSelectedTipo.nombre_tipo);
    await loadTypes();
  });

  // =========================
  // Eventos
  // =========================
  modalInsumoBackdrop?.addEventListener('click', closeModalInsumo);
  modalInsumoClose?.addEventListener('click', closeModalInsumo);

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      if (modalInsumo && !modalInsumo.classList.contains('hidden')) closeModalInsumo();
      if (modalEditLote && !modalEditLote.classList.contains('hidden')) closeEditModal();
    }
  });

  fCat?.addEventListener('change', updateModalByCategory);

  btnBack?.addEventListener('click', () => {
    currentCategory = null;
    currentSelectedTipo = null;
    currentLotes = [];

    typesContainer.innerHTML = '';
    lotBody.innerHTML = '';
    vacList.innerHTML = '';
    detailSummary.innerHTML = '';
    detailTitle.textContent = 'Detalle';

    hide(vaccinesBlock);
    hide(detailSection);
    hide(typesView);
    show(categoriesView);

    qTipo.value = '';
    clearDetailFilters(false);

    resetModalFull();
    hide(modalInsumo);
    closeEditModal();

    setHeaderDefault();
  });

  qTipo?.addEventListener('input', () => loadTypes());

  [fLote, fEstadoLote, fExpLote, fFabFrom, fFabTo, fFabExact, fCadFrom, fCadTo, fCadExact].forEach(el => {
    el?.addEventListener('input', applyDetailFilters);
    el?.addEventListener('change', applyDetailFilters);
  });

  btnRegistrar?.addEventListener('click', openModalInsumo);

  btnCalc?.addEventListener('click', () => {
    const cat = (fCat.value || '').toUpperCase();
    const packs = Number(fPacks.value || 0);
    let u = 0;

    if (cat === 'JERINGAS') u = packs * 100;
    else if (cat === 'GUANTES') u = packs * 100;
    else if (cat === 'ALGODON') u = packs * 3;
    else if (cat === 'ALCOHOL') {
      const cap = Number(fAlcoholCap?.value || 1000);
      u = packs * cap;
    } else u = packs;

    if (formMsg) formMsg.textContent = `Cálculo sugerido: ${u}`;
    if (fUnidades) fUnidades.value = String(u);
  });

  // =========================
  // Submit registrar insumo
  // =========================
  formInsumo?.addEventListener('submit', async (e) => {
    e.preventDefault();

    let categoriaFinal = (fCat.value || '').trim().toUpperCase();

    if (categoriaFinal === 'OTRO') {
      categoriaFinal = (fNewCat?.value || '').trim().toUpperCase();
    }
    if (!categoriaFinal) {
      if (formMsg) formMsg.textContent = 'Escribe el nombre de la nueva categoría.';
      return;
    }

    const payload = {
      categoria: categoriaFinal,
      lote: (fLoteReg.value || '').trim(),
      packs: Number(fPacks.value || 0),
      fab_month: (fFabMonth.value || '').trim(),
      cad_month: (fCadMonth.value || '').trim(),
      nombre_tipo_base: (fTipo.value || '').trim(),
      alcohol_cap_ml: null
    };

    if (!payload.lote || !payload.cad_month || !payload.nombre_tipo_base) {
      if (formMsg) formMsg.textContent = 'Completa: lote, tipo y caducidad.';
      return;
    }

    if (payload.categoria === 'ALCOHOL') {
      payload.alcohol_cap_ml = Number(fAlcoholCap?.value || 0);
      if (!payload.alcohol_cap_ml || payload.alcohol_cap_ml <= 0) {
        if (formMsg) formMsg.textContent = 'Selecciona la capacidad del alcohol (ml).';
        return;
      }
    }

    const { res, data } = await postJSON('/api/insumos/registrar', payload);

    if (!res.ok) {
      if (formMsg) formMsg.textContent = data.message || 'Error registrando insumo';
      return;
    }

    await loadTypes();
    if (currentSelectedTipo?.nombre_tipo) {
      await loadDetail(currentSelectedTipo.nombre_tipo);
    }

    resetModalKeepCatType();
    hide(modalInsumo);
  });

  // =========================
  // Boot
  // =========================
  CAN_MANAGE ? show(btnRegistrar) : hide(btnRegistrar);
  setHeaderDefault();
  loadCategories();

  // ✅ AUTO-ABRIR desde focus (requiere /api/insumos/focus)
  (async () => {
    if (!FOCUS.focusId && !FOCUS.focusLote) return;

    const r = await fetchJSON(
      `/api/insumos/focus?focus_id=${encodeURIComponent(FOCUS.focusId)}&lote=${encodeURIComponent(FOCUS.focusLote)}&_ts=${Date.now()}`
    );

    if (!r || !r.ok || !r.categoria || !r.nombre_tipo) return;

    currentCategory = (r.categoria || '').toUpperCase();
    pendingFocusLote = FOCUS.focusLote || r.lote || null;

    setHeaderCategory(currentCategory);

    // cargar tipos y seleccionar el correcto
    const tipos = await loadTypes();
    currentSelectedTipo = { nombre_tipo: r.nombre_tipo };

    // forzar highlight del card seleccionado re-renderizando
    renderTypes(Array.isArray(tipos) ? tipos : []);

    await loadDetail(r.nombre_tipo);

    // si ya se aplicó el focus, limpiamos params
    // (si no se aplicó, se limpia cuando el lote exista en tabla)
  })();
})();
