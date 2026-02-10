(() => {
  const qrFile = document.getElementById("qrFile");
  const qrProcesar = document.getElementById("qrProcesar");
  const qrLimpiar = document.getElementById("qrLimpiar");
  const qrMonthSelect = document.getElementById("qrMonthSelect");
  const qrMsg = document.getElementById("qrMsg");

  const qrOut = document.getElementById("qrOut");
  const qrRegsSection = document.getElementById("qrRegsSection");

  const qrKpis = document.getElementById("qrKpis");

  const qrSerieBody = document.getElementById("qrSerieBody");
  const qrCapBody = document.getElementById("qrCapBody");
  const qrDosisBody = document.getElementById("qrDosisBody");
  const qrPersBody = document.getElementById("qrPersBody");
  const qrAlertBody = document.getElementById("qrAlertBody");

  const fMonth = document.getElementById("fMonth");
  const fCedula = document.getElementById("fCedula");
  const fNombre = document.getElementById("fNombre");
  const fFecha = document.getElementById("fFecha");
  const fEstado = document.getElementById("fEstado");
  const fVacuna = document.getElementById("fVacuna");
  const fCap = document.getElementById("fCap");
  const btnBuscarRegs = document.getElementById("btnBuscarRegs");
  const btnResetRegs = document.getElementById("btnResetRegs");

  const qrRegsBody = document.getElementById("qrRegsBody");
  const btnPrev = document.getElementById("btnPrev");
  const btnNext = document.getElementById("btnNext");
  const qrPageInfo = document.getElementById("qrPageInfo");

  let sessionKey = null;
  let months = [];
  let reportesPorMes = {};
  let currentMonth = "";

  let currentPage = 1;
  const pageSize = 25;

  function show(el){ el.classList.remove("hidden"); }
  function hide(el){ el.classList.add("hidden"); }
  function safe(v,d="—"){ return (v===null||v===undefined||v==="") ? d : v; }

  // Escape básico para pintar texto seguro en HTML
  function esc(s){
    return String(s ?? "").replace(/[&<>"']/g, (m) => ({
      "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"
    }[m]));
  }

  function buildPaciente(r){
    const parts = [
      (r.primer_nombre || "").trim(),
      (r.segundo_nombre || "").trim(),
      (r.apellido_paterno || "").trim(),
      (r.apellido_materno || "").trim(),
    ].filter(Boolean);

    return parts.length ? parts.join(" ") : "";
  }

  qrProcesar.addEventListener("click", async () => {
    qrMsg.textContent = "";
    hide(qrOut);
    hide(qrRegsSection);

    sessionKey = null;
    months = [];
    reportesPorMes = {};
    currentMonth = "";
    currentPage = 1;

    const file = qrFile.files && qrFile.files[0];
    if (!file) { qrMsg.textContent = "Selecciona un archivo."; return; }

    const fd = new FormData();
    fd.append("file", file);

    qrMsg.textContent = "Procesando…";
    const res = await fetch("/api/consulta-rapida/procesar", { method:"POST", body: fd });
    const data = await res.json().catch(()=>({}));

    if (!res.ok || !data || !data.ok) {
      qrMsg.textContent = data.message || "No se pudo procesar.";
      return;
    }

    sessionKey = data.session_key;
    months = data.months || [];
    reportesPorMes = data.reportes_por_mes || {};
    currentMonth = data.selected_month || (months[0] || "");

    fillMonths(months);
    show(qrMonthSelect);

    renderMonth(currentMonth, data.alertas || []);
    show(qrOut);

    fillRegMonthFilter(months);
    show(qrRegsSection);

    qrMsg.textContent = "";
    await loadRegistros();
  });

  qrLimpiar.addEventListener("click", () => {
    qrMsg.textContent = "";
    hide(qrOut);
    hide(qrRegsSection);
    sessionKey = null;
    months = [];
    reportesPorMes = {};
    currentMonth = "";
    currentPage = 1;
    qrFile.value = "";
    hide(qrMonthSelect);
    resetFilters();
  });

  qrMonthSelect.addEventListener("change", async () => {
    const m = (qrMonthSelect.value || "").trim();
    if (!m) return;
    currentMonth = m;
    currentPage = 1;
    renderMonth(currentMonth, null);
    fMonth.value = currentMonth;
    await loadRegistros();
  });

  function fillMonths(ms){
    qrMonthSelect.innerHTML = "";
    ms.forEach(m=>{
      const opt = document.createElement("option");
      opt.value = m;
      opt.textContent = m;
      if (m === currentMonth) opt.selected = true;
      qrMonthSelect.appendChild(opt);
    });
  }

  function fillRegMonthFilter(ms){
    fMonth.innerHTML = `<option value="">MES (TODOS)</option>`;
    ms.forEach(m=>{
      const opt = document.createElement("option");
      opt.value = m;
      opt.textContent = m;
      fMonth.appendChild(opt);
    });
    fMonth.value = currentMonth || "";
  }

  function renderMonth(month, alertas) {
    const rep = reportesPorMes[month] || {};
    renderKpis(rep);
    renderTotalPorDia(rep);
    renderCaptacionPorDia(rep);
    renderList(qrDosisBody, rep.dosis_por_vacuna || [], "vacuna", "dosis_total");
    renderList(qrPersBody, rep.personas_por_vacuna || [], "vacuna", "personas_total");
    if (alertas) renderAlertas(alertas);
  }

  function renderKpis(rep){
    qrKpis.innerHTML = "";
    const items = [
      {label:"Mes", value: rep.month},
      {label:"Total dosis", value: safe(rep.total_mensual,0)},
      {label:"Personas únicas", value: safe(rep.personas_total,0)},
      {label:"Capt. temprana", value: safe(rep.captacion_temprana,0)},
      {label:"Capt. tardía", value: safe(rep.captacion_tardia,0)},
    ];
    items.forEach(it=>{
      const div = document.createElement("div");
      div.className = "kpi-box";
      div.innerHTML = `<div class="kpi-label">${esc(it.label)}</div><div class="kpi-value">${esc(it.value)}</div>`;
      qrKpis.appendChild(div);
    });
  }

  function renderTotalPorDia(rep){
    qrSerieBody.innerHTML = "";
    const rows = rep.total_por_dia || [];
    if (!rows.length){
      qrSerieBody.innerHTML = `<tr><td colspan="2" style="text-align:center;color:#9ca3af;">Sin datos</td></tr>`;
      return;
    }
    rows.forEach(x=>{
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${esc(safe(x.fecha,""))}</td><td class="right">${esc(safe(x.total,0))}</td>`;
      qrSerieBody.appendChild(tr);
    });
  }

  function renderCaptacionPorDia(rep){
    qrCapBody.innerHTML = "";
    const rows = rep.captacion_por_dia || [];
    if (!rows.length){
      qrCapBody.innerHTML = `<tr><td colspan="3" style="text-align:center;color:#9ca3af;">Sin datos</td></tr>`;
      return;
    }
    rows.forEach(x=>{
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${esc(safe(x.fecha,""))}</td><td class="right">${esc(safe(x.temprana,0))}</td><td class="right">${esc(safe(x.tardia,0))}</td>`;
      qrCapBody.appendChild(tr);
    });
  }

  function renderList(tbody, arr, k1, k2){
    tbody.innerHTML = "";
    if (!arr.length){
      tbody.innerHTML = `<tr><td colspan="2" style="text-align:center;color:#9ca3af;">Sin datos</td></tr>`;
      return;
    }
    arr.forEach(x=>{
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${esc(safe(x[k1],""))}</td><td class="right">${esc(safe(x[k2],0))}</td>`;
      tbody.appendChild(tr);
    });
  }

  function renderAlertas(arr){
    qrAlertBody.innerHTML = "";
    if (!arr.length){
      qrAlertBody.innerHTML = `<tr><td colspan="3" style="text-align:center;color:#9ca3af;">Sin alertas</td></tr>`;
      return;
    }
    arr.forEach(a=>{
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${esc(safe(a.tipo_alerta,""))}</td><td>${esc(safe(a.estado,""))}</td><td class="right">${esc(safe(a.total,0))}</td>`;
      qrAlertBody.appendChild(tr);
    });
  }

  btnBuscarRegs.addEventListener("click", () => { currentPage = 1; loadRegistros(); });
  btnResetRegs.addEventListener("click", () => { resetFilters(); currentPage = 1; loadRegistros(); });

  btnPrev.addEventListener("click", () => { if (currentPage > 1) { currentPage--; loadRegistros(); } });
  btnNext.addEventListener("click", () => { currentPage++; loadRegistros(); });

  function resetFilters(){
    fMonth.value = "";
    fCedula.value = "";
    fNombre.value = "";
    fFecha.value = "";
    fEstado.value = "";
    fVacuna.value = "";
    fCap.value = "";
  }

  async function loadRegistros() {
    if (!sessionKey) return;

    const qs = new URLSearchParams();
    qs.set("session_key", sessionKey);
    qs.set("page", String(currentPage));
    qs.set("page_size", String(pageSize));

    // 👇 IMPORTANTE: tu backend espera month, pero tu endpoint debe pasarlo.
    if (fMonth.value.trim()) qs.set("month", fMonth.value.trim());
    if (fCedula.value.trim()) qs.set("cedula", fCedula.value.trim());
    if (fNombre.value.trim()) qs.set("nombre", fNombre.value.trim());
    if (fFecha.value.trim()) qs.set("fecha", fFecha.value.trim());
    if (fEstado.value.trim()) qs.set("estado", fEstado.value.trim());
    if (fVacuna.value.trim()) qs.set("vacuna", fVacuna.value.trim().toUpperCase());
    if (fCap.value.trim()) qs.set("captacion", fCap.value.trim());

    const res = await fetch("/api/consulta-rapida/registros?" + qs.toString(), { cache:"no-store" });
    const data = await res.json().catch(()=>({}));

    if (!res.ok || !data.ok){
      qrRegsBody.innerHTML = `<tr><td colspan="5" style="text-align:center;color:#9ca3af;">Sin sesión o error</td></tr>`;
      qrPageInfo.textContent = "—";
      return;
    }

    const total = data.total || 0;
    const totalPages = Math.max(1, data.total_pages || Math.ceil(total / pageSize));
    if (currentPage > totalPages) currentPage = totalPages;

    qrPageInfo.textContent = `Página ${currentPage} / ${totalPages} • ${total} registros`;

    qrRegsBody.innerHTML = "";
    const items = data.items || [];
    if (!items.length){
      qrRegsBody.innerHTML = `<tr><td colspan="5" style="text-align:center;color:#9ca3af;">Sin resultados</td></tr>`;
      btnPrev.disabled = currentPage <= 1;
      btnNext.disabled = currentPage >= totalPages;
      return;
    }

    items.forEach(r=>{
      const paciente = buildPaciente(r); // <- viene del backend (en memoria)

      // SIN CAMBIAR TU TABLA: muestro el nombre debajo de la cédula
      const cedulaCell = paciente
        ? `${esc(safe(r.numero_identificacion,""))}<div style="color:#9ca3af;font-size:12px;margin-top:2px;white-space:normal;">${esc(paciente)}</div>`
        : esc(safe(r.numero_identificacion,""));

      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${esc(safe(r.fecha_vacunacion,""))}</td>
        <td>${cedulaCell}</td>
        <td>${esc(safe(r.vacuna,""))}</td>
        <td class="right">${esc(safe(r.dosis,""))}</td>
        <td>${esc(safe(r.estado_registro,""))}</td>
      `;
      qrRegsBody.appendChild(tr);
    });

    btnPrev.disabled = currentPage <= 1;
    btnNext.disabled = currentPage >= totalPages;
  }
})();
