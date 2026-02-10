(() => {
  // =========================
  // DOM filtros
  // =========================
  const fYear = document.getElementById('fYear');
  const fMonth = document.getElementById('fMonth');
  const fDay = document.getElementById('fDay');
  const fSexo = document.getElementById('fSexo');

  const fEdadMin = document.getElementById('fEdadMin');
  const fEdadMax = document.getElementById('fEdadMax');

  const fEsquema = document.getElementById('fEsquema');
  const fGrupo = document.getElementById('fGrupo');

  const fCedula = document.getElementById('fCedula');
  const fNombre = document.getElementById('fNombre');
  const fVacuna = document.getElementById('fVacuna');
  const fEstado = document.getElementById('fEstado');

  const btnClear = document.getElementById('btnClear');

  // =========================
  // Tabla / pager
  // =========================
  const msgReg = document.getElementById('msgReg');
  const regBody = document.getElementById('regBody');
  const pager = document.getElementById('pager');

  const state = {
    page: 1,
    pageSize: 50,
    total: 0,
    totalPages: 1,
    loading: false,
    // evita que debounce "pise" una navegación
    navLockUntil: 0,
  };

  // =========================
  // Helpers
  // =========================
  function fillDays(){
    const current = fDay.value;
    fDay.innerHTML = `<option value="">Día: Todos</option>`;
    for (let i=1;i<=31;i++){
      const v = String(i).padStart(2,'0');
      const opt = document.createElement('option');
      opt.value = v;
      opt.textContent = v;
      fDay.appendChild(opt);
    }
    fDay.value = current;
  }
  fillDays();

  function clearTable(text){
    regBody.innerHTML = `<tr><td colspan="12" class="empty-row">${text}</td></tr>`;
  }

  function nombreCompleto(r){
    return `${r.primer_nombre || ''} ${r.segundo_nombre || ''} ${r.apellido_paterno || ''} ${r.apellido_materno || ''}`
      .replace(/\s+/g,' ').trim() || '—';
  }

  function edadText(r){
    const a = (r.edad_ano ?? '').toString().trim();
    const m = (r.edad_mes ?? '').toString().trim();
    const d = (r.edad_dia ?? '').toString().trim();
    if (!a && !m && !d) return '—';
    return `${a || '0'}a ${m || '0'}m ${d || '0'}d`;
  }

  function debounce(fn, wait=350){
    let t=null;
    return (...args) => {
      clearTimeout(t);
      t=setTimeout(() => fn(...args), wait);
    };
  }

  function getFilters(){
    return {
      year: (fYear.value || '').trim(),
      month: (fMonth.value || '').trim(),
      day: (fDay.value || '').trim(),
      sexo: (fSexo.value || '').trim(),
      esquema: (fEsquema.value || '').trim(),
      grupo: (fGrupo.value || '').trim(),
      cedula: (fCedula.value || '').trim(),
      nombre: (fNombre.value || '').trim(),
      vacuna: (fVacuna.value || '').trim(),
      estado: (fEstado.value || '').trim(),
      edad_min: (fEdadMin.value || '').trim(),
      edad_max: (fEdadMax.value || '').trim(),
    };
  }

  function qsFromFilters(filters){
    const qs = new URLSearchParams();
    Object.entries(filters).forEach(([k,v]) => { if (v) qs.set(k, v); });
    return qs.toString();
  }

  // =========================
  // Fetch server
  // =========================
  async function fetchCount(filters){
    const qs = qsFromFilters(filters);
    const res = await fetch(`/api/registros/count?${qs}`);
    const data = await res.json().catch(() => ({total:0}));
    return data.total || 0;
  }

  async function fetchPage(filters){
    const qs = new URLSearchParams(qsFromFilters(filters));
    qs.set('page', String(state.page));
    qs.set('page_size', String(state.pageSize));
    const res = await fetch(`/api/registros/page?${qs.toString()}`);
    const data = await res.json().catch(() => []);
    return Array.isArray(data) ? data : [];
  }

  // =========================
  // Render
  // =========================
  function renderPager(){
    pager.innerHTML = '';

    const info = document.createElement('span');
    info.textContent = `Página ${state.page} / ${state.totalPages} • Total: ${state.total}`;
    info.style.color = 'var(--muted)';
    info.style.fontSize = '13px';

    const btnPrev = document.createElement('button');
    btnPrev.className = 'btn-mini';
    btnPrev.textContent = '← Anterior';
    btnPrev.disabled = state.loading || state.page <= 1;
    btnPrev.addEventListener('click', () => {
      if (state.loading) return;             //  evita doble click mientras carga
      if (state.page <= 1) return;
      state.page -= 1;

      // bloquea debounce por un instante
      state.navLockUntil = Date.now() + 700;
      fetchAndRender(false);
    });

    const btnNext = document.createElement('button');
    btnNext.className = 'btn-mini';
    btnNext.textContent = 'Siguiente →';
    btnNext.disabled = state.loading || state.page >= state.totalPages;
    btnNext.addEventListener('click', () => {
      if (state.loading) return;             //  evita doble click mientras carga
      if (state.page >= state.totalPages) return;
      state.page += 1;

      state.navLockUntil = Date.now() + 700;
      fetchAndRender(false);
    });

    const sel = document.createElement('select');
    sel.className = 'uf-input';
    sel.style.minWidth = '120px';
    [50, 100, 200].forEach(n => {
      const opt = document.createElement('option');
      opt.value = String(n);
      opt.textContent = `${n} / pág`;
      if (n === state.pageSize) opt.selected = true;
      sel.appendChild(opt);
    });
    sel.addEventListener('change', () => {
      state.pageSize = parseInt(sel.value, 10) || 50;
      applyFilters(); // recalcula count y vuelve a page 1
    });

    pager.append(btnPrev, btnNext, sel, info);
  }

  function renderTable(rows){
    regBody.innerHTML = '';
    if (!rows.length){
      clearTable('No hay registros para esos filtros.');
      return;
    }

    rows.forEach(r => {
      const est = (r.estado_registro || '').toUpperCase();
      const pillClass = est === 'CONFLICTO' ? 'pill-bad' : 'pill-ok';

      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${r.fecha_vacunacion || '—'}</td>
        <td>${r.numero_identificacion || '—'}</td>
        <td>${nombreCompleto(r)}</td>
        <td>${r.sexo || '—'}</td>
        <td>${edadText(r)}</td>
        <td>${r.vacuna_raw || '—'}</td>
        <td>${r.vacuna_canon || '—'}</td>
        <td>${r.dosis || '—'}</td>
        <td>${r.esquema || '—'}</td>
        <td>${r.grupo_riesgo || '—'}</td>
        <td><span class="pill ${pillClass}">${est || '—'}</span></td>
        <td>${r.periodo || '—'}</td>
      `;
      regBody.appendChild(tr);
    });
  }

  // =========================
  // Core: fetch+render
  // =========================
  async function fetchAndRender(withCount){
    if (state.loading) return;

    state.loading = true;

    //  CLAVE: renderizar pager apenas empieza (queda bloqueado)
    renderPager();

    msgReg.textContent = 'Cargando...';
    clearTable('Cargando...');

    const filters = getFilters();

    try{
      if (withCount){
        state.total = await fetchCount(filters);
        state.totalPages = Math.max(1, Math.ceil(state.total / state.pageSize));
        if (state.page > state.totalPages) state.page = state.totalPages;
      }

      const rows = await fetchPage(filters);
      renderTable(rows);

      msgReg.textContent = `Mostrando ${rows.length} registros en página ${state.page}.`;
    } catch (e){
      console.error(e);
      msgReg.textContent = 'Error cargando registros.';
      clearTable('Error cargando registros.');
    } finally {
      state.loading = false;

      // CLAVE: volver a renderizar pager al final (ya habilitado)
      renderPager();
    }
  }

  // =========================
  // Aplicar filtros (resetea a página 1)
  // =========================
  function applyFilters(){
    state.page = 1;
    fetchAndRender(true);
  }

  // =========================
  // Años dinámicos
  // =========================
  async function loadYears(){
    const res = await fetch('/api/registros/years');
    const data = await res.json().catch(() => []);
    fYear.innerHTML = `<option value="">Año: Todos</option>`;
    (data || []).forEach(x => {
      const y = x.year;
      if (!y) return;
      const opt = document.createElement('option');
      opt.value = y;
      opt.textContent = y;
      fYear.appendChild(opt);
    });
  }

  // =========================
  // Events: selects immediate, inputs debounced
  // =========================
  function onSelectChange(){
    // si el usuario acaba de navegar de página, no resetees por eventos raros
    if (Date.now() < state.navLockUntil) return;
    applyFilters();
  }

  const onTextChange = debounce(() => {
    if (Date.now() < state.navLockUntil) return;
    applyFilters();
  }, 350);

  [fYear, fMonth, fDay, fSexo, fEstado].forEach(el => el?.addEventListener('change', onSelectChange));

  [fEsquema, fGrupo, fCedula, fNombre, fVacuna, fEdadMin, fEdadMax]
    .forEach(el => el?.addEventListener('input', onTextChange));

  btnClear.addEventListener('click', () => {
    fYear.value = '';
    fMonth.value = '';
    fDay.value = '';
    fSexo.value = '';
    fEdadMin.value = '';
    fEdadMax.value = '';
    fEsquema.value = '';
    fGrupo.value = '';
    fCedula.value = '';
    fNombre.value = '';
    fVacuna.value = '';
    fEstado.value = '';
    applyFilters();
  });

  // =========================
  // Buscar paciente (tarjetas)
  // =========================
  const pCedula = document.getElementById('pCedula');
  const btnBuscarPaciente = document.getElementById('btnBuscarPaciente');
  const btnLimpiarPaciente = document.getElementById('btnLimpiarPaciente');
  const msgPaciente = document.getElementById('msgPaciente');

  const patientSummary = document.getElementById('patientSummary');
  const patientMeta = document.getElementById('patientMeta');
  const patientFields = document.getElementById('patientFields');
  const patientVaccines = document.getElementById('patientVaccines');

  function hidePacienteUI(){
    msgPaciente.textContent = '';
    patientSummary.classList.add('hidden');
    patientVaccines.classList.add('hidden');
    patientFields.innerHTML = '';
    patientMeta.innerHTML = '';
    patientVaccines.innerHTML = '';
  }

  function getJson(obj, key, fallback=''){
    const d = obj?.datos_archivo || {};
    const v = d[key];
    return (v === null || v === undefined) ? fallback : String(v).trim();
  }

  function pickFirst(obj, keys){
    for (const k of keys){
      const v = getJson(obj, k, '');
      if (v) return v;
    }
    return '';
  }

  function normalizeSexoTxt(s){
    const x = (s || '').toUpperCase();
    if (['M','MASCULINO','HOMBRE'].includes(x)) return 'MASCULINO';
    if (['F','FEMENINO','MUJER'].includes(x)) return 'FEMENINO';
    return x || '—';
  }

  function edadPaciente(obj){
    const a = pickFirst(obj, ['edad_ano','edad_ano_nombre','edad_ano_nombre_2']);
    const m = pickFirst(obj, ['edad_mes','edad_mes_nombre','edad_mes_nombre_2']);
    const d = pickFirst(obj, ['edad_dia','edad_dia_nombre','edad_dia_nombre_2']);
    if (!a && !m && !d) return '—';
    return `${a || '0'}a ${m || '0'}m ${d || '0'}d`;
  }

  function nombrePaciente(obj){
    const pn = (obj.primer_nombre || '').trim() || getJson(obj, 'primer_nombre', '');
    const sn = (obj.segundo_nombre || '').trim() || getJson(obj, 'segundo_nombre', '');
    const ap = (obj.apellido_paterno || '').trim() || getJson(obj, 'apellido_paterno', '');
    const am = (obj.apellido_materno || '').trim() || getJson(obj, 'apellido_materno', '');
    return `${pn} ${sn} ${ap} ${am}`.replace(/\s+/g,' ').trim() || '—';
  }

  function renderPacienteSummary(cedula, items){
    const last = items[items.length - 1];

    const sexo = normalizeSexoTxt(last.sexo || getJson(last,'sexo','') || getJson(last,'sexo_nombre',''));
    const edad = edadPaciente(last);

    const provincia = pickFirst(last, ['residencia_provincia','residencia_provincia_2']);
    const canton = pickFirst(last, ['residencia_canton','residencia_canton_2']);
    const parroquia = pickFirst(last, ['residencia_parroquia','residencia_parroquia_2']);

    const grupo = (last.grupo_riesgo || getJson(last,'grupo_de_riesgo','')).trim();

    patientSummary.classList.remove('hidden');

    patientMeta.innerHTML = `
      <span>Cédula: <b>${cedula}</b></span>
      <span>Total eventos: <b>${items.length}</b></span>
    `;

    patientFields.innerHTML = `
      <div class="pf"><span class="k">Nombre:</span>${nombrePaciente(last)}</div>
      <div class="pf"><span class="k">Sexo:</span>${sexo}</div>
      <div class="pf"><span class="k">Edad:</span>${edad}</div>
      <div class="pf"><span class="k">Provincia:</span>${provincia || '—'}</div>
      <div class="pf"><span class="k">Cantón:</span>${canton || '—'}</div>
      <div class="pf"><span class="k">Parroquia:</span>${parroquia || '—'}</div>
      <div class="pf"><span class="k">Grupo riesgo:</span>${grupo || '—'}</div>
    `;
  }

  function renderVacunaCards(items){
    const groups = new Map();
    items.forEach(it => {
      const canon = (it.vacuna_canon || '').trim() || 'SIN_VACUNA';
      if (!groups.has(canon)) groups.set(canon, []);
      groups.get(canon).push(it);
    });

    patientVaccines.innerHTML = '';
    patientVaccines.classList.remove('hidden');

    const keys = Array.from(groups.keys()).sort();
    keys.forEach(canon => {
      const evs = groups.get(canon).slice().sort((a,b) => (a.fecha_vacunacion||'').localeCompare(b.fecha_vacunacion||''));

      const rawSet = new Set(evs.map(x => (x.vacuna_raw || '').trim()).filter(Boolean));
      const rawLabel = rawSet.size ? Array.from(rawSet).slice(0,3).join(' / ') : canon;

      const firstDate = evs[0]?.fecha_vacunacion || '—';
      const lastDate = evs[evs.length-1]?.fecha_vacunacion || '—';

      const card = document.createElement('div');
      card.className = 'vcard';
      card.innerHTML = `
        <div class="vtitle">${canon}</div>
        <div class="vmeta">RAW: ${rawLabel} • Eventos: ${evs.length} • ${firstDate} → ${lastDate}</div>
        <ul class="vlist">
          ${evs.map(x => `
            <li>
              <b>${x.fecha_vacunacion || '—'}</b> · ${x.vacuna_raw || canon}
              ${x.dosis ? `· Dosis: ${x.dosis}` : ''}
              ${x.esquema ? `· Esquema: ${x.esquema}` : ''}
              ${x.estado_registro && x.estado_registro !== 'VALIDO' ? `· <span style="color:#ef4444">${x.estado_registro}</span>` : ''}
            </li>
          `).join('')}
        </ul>
      `;
      patientVaccines.appendChild(card);
    });
  }

  btnLimpiarPaciente?.addEventListener('click', () => {
    pCedula.value = '';
    hidePacienteUI();
  });

  btnBuscarPaciente?.addEventListener('click', async () => {
    const ced = (pCedula.value || '').trim();
    hidePacienteUI();

    if (!ced){
      msgPaciente.textContent = 'Ingresa una cédula.';
      return;
    }

    msgPaciente.textContent = 'Buscando paciente...';

    const res = await fetch(`/api/paciente/historial?cedula=${encodeURIComponent(ced)}`);
    const data = await res.json().catch(() => []);

    if (!Array.isArray(data) || data.length === 0){
      msgPaciente.textContent = 'No se encontraron registros para esa cédula.';
      return;
    }

    msgPaciente.textContent = `Historial cargado: ${data.length} eventos.`;
    renderPacienteSummary(ced, data);
    renderVacunaCards(data);
  });

  // init
  loadYears().then(() => fetchAndRender(true));
})();
