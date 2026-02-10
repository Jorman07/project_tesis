let alertaSeleccionada = null;
let accionActual = null;

document.addEventListener("DOMContentLoaded", () => {
  const btnReload = document.getElementById("btnReload");
  if (btnReload) btnReload.addEventListener("click", cargarAlertas);

  const fEntidad = document.getElementById("fEntidad");
  if (fEntidad) fEntidad.addEventListener("change", cargarAlertas);

  const btnClose = document.getElementById("btnCloseModal");
  const btnCancel = document.getElementById("btnCancelModal");
  const btnConfirm = document.getElementById("btnConfirmModal");

  if (btnClose) btnClose.addEventListener("click", cerrarModal);
  if (btnCancel) btnCancel.addEventListener("click", cerrarModal);
  if (btnConfirm) btnConfirm.addEventListener("click", confirmarAccion);

  const overlay = document.getElementById("modalAccion");
  if (overlay) {
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) cerrarModal();
    });
  }

  cargarAlertas();
});

function canShowActionColumn() {
  return (window.USER_ROLE || "").toUpperCase() !== "ASISTENTE";
}

function canCorregir() {
  const role = (window.USER_ROLE || "").toUpperCase();
  return role === "ADMINISTRADOR" || role === "COORDINADOR";
}

function canGestionarInventario() {
  const role = (window.USER_ROLE || "").toUpperCase();
  return role === "ADMINISTRADOR";
}

function cargarAlertas() {
  const role = (window.USER_ROLE || "").toUpperCase();
  const refresh = (role === "ADMINISTRADOR" || role === "COORDINADOR") ? "&refresh=1" : "";

  const fEntidad = document.getElementById("fEntidad");
  const entidad = fEntidad ? (fEntidad.value || "").trim().toUpperCase() : "";

  const entidadQS = entidad ? `&tipo_entidad=${encodeURIComponent(entidad)}` : "";

  fetch(`/api/alertas?estado=PENDIENTE${entidadQS}${refresh}`, { cache: "no-store" })
    .then(r => r.json())
    .then(data => renderAlertas(Array.isArray(data) ? data : []))
    .catch(() => renderAlertas([]));
}

function renderAlertas(alertas) {
  const body = document.getElementById("alertasBody");
  body.innerHTML = "";

  const showAction = canShowActionColumn();
  const cols = showAction ? 6 : 5;

  if (!alertas.length) {
    body.innerHTML = `
      <tr>
        <td colspan="${cols}" style="text-align:center; padding:14px; color:#9ca3af;">
          Sin alertas pendientes
        </td>
      </tr>
    `;
    return;
  }

  alertas.forEach(a => {
    const tipoEntidad = (a.tipo_entidad || "").toUpperCase();
    const isRegistro = tipoEntidad === "REGISTRO";
    const isInventario = (tipoEntidad === "BIOLOGICO" || tipoEntidad === "INSUMO");

    // Fecha bonita
    const fechaPretty = formatDateTime(a.fecha_creacion);

    // Detalle enriquecido (inventario)
    const detailHtml = buildDetailHtml(a);

    let actionCell = "";
    if (showAction) {
      if (isRegistro && canCorregir()) {
        actionCell = `
          <td class="right">
            <button class="btn-action btn-corregir" type="button"
              onclick="abrirModal(${a.id_alerta}, 'CORREGIR')">
              Corregir
            </button>
          </td>
        `;
      } else if (isInventario && canGestionarInventario()) {
        actionCell = `
          <td class="right">
            <button class="btn-action btn-gestionar" type="button"
              onclick="abrirModal(${a.id_alerta}, 'RESOLVER')">
              Gestionar
            </button>
          </td>
        `;
      } else {
        actionCell = `<td class="right" style="color:#9ca3af;">—</td>`;
      }
    }

    body.innerHTML += `
      <tr>
        <td>${escapeHtml(a.tipo_alerta || "")}</td>
        <td title="${escapeHtml(a.detalle || "")}">${detailHtml}</td>
        <td>${escapeHtml(a.tipo_entidad || "")}</td>
        <td>${escapeHtml(fechaPretty)}</td>
        <td><span class="badge badge-pendiente">${escapeHtml(a.estado || "")}</span></td>
        ${actionCell}
      </tr>
    `;
  });
}

function buildDetailHtml(a) {
  const raw = String(a.detalle || "");
  const tipoEntidad = (a.tipo_entidad || "").toUpperCase();

  // REGISTRO: se muestra igual
  if (tipoEntidad === "REGISTRO") {
    return escapeHtml(raw);
  }

  // INVENTARIO: formatear bonito
  // Esperado: "CATEGORIA / Nombre tipo lote XXX caduca YYYY-MM-DD (unidades: 500)"
  // o: "BCG lote XXX caduca YYYY-MM-DD (frascos: 60)"
  const parsed = parseInventarioDetalle(raw);

  // Si no pude parsear, muestro el texto limpio sin paréntesis
  if (!parsed) return escapeHtml(stripParenStock(raw));

  const { entidad, categoria, nombreTipo, lote, caduca, qtyType, qtyValue } = parsed;

  // Convertir cantidad a presentación humana
  const pres = formatStockPresentation({
    categoria,
    nombreTipo,
    qtyType,
    qtyValue
  });

  // Construir texto bonito
  // Ejemplos:
  // "JERINGAS / 26G x 3/8 1ml TB • Lote: IL-4478 • Caduca: 2027-01-31 • Stock: 5 cajas"
  // "BCG • Lote: 0344X002A • Caduca: 2026-08-31 • Stock: 60 frascos"
  const left = categoria ? `${categoria} / ${nombreTipo}` : entidad;
  const parts = [
    left,
    lote ? `Lote: ${lote}` : null,
    caduca ? `Caduca: ${caduca}` : null,
    pres ? `Stock: ${pres}` : null
  ].filter(Boolean);

  return escapeHtml(parts.join(" • "));
}

function stripParenStock(s) {
  // quita "(unidades: ...)" o "(frascos: ...)"
  return String(s || "").replace(/\s*\((unidades|frascos)\s*:\s*[^)]+\)\s*/ig, "").trim();
}

function parseInventarioDetalle(raw) {
  const s = String(raw || "").trim();
  if (!s) return null;

  // Captura cantidad en paréntesis
  const mUn = s.match(/\(unidades:\s*([0-9]+(?:\.[0-9]+)?)\)/i);
  const mFr = s.match(/\(frascos:\s*([0-9]+(?:\.[0-9]+)?)\)/i);

  let qtyType = null;
  let qtyValue = null;
  if (mFr) { qtyType = "FRASCOS"; qtyValue = Number(mFr[1]); }
  else if (mUn) { qtyType = "UNIDADES"; qtyValue = Number(mUn[1]); }

  // Limpiar texto sin paréntesis
  const clean = stripParenStock(s);

  // Caso BIOLÓGICO típico:
  // "BCG lote 0344X... caduca 2026-08-31"
  const bio = clean.match(/^([A-Z0-9_]+)\s+lote\s+(.+?)\s+caduca\s+(\d{4}-\d{2}-\d{2})/i);
  if (bio) {
    return {
      entidad: bio[1].toUpperCase(),
      categoria: "",
      nombreTipo: "",
      lote: bio[2].trim(),
      caduca: bio[3],
      qtyType,
      qtyValue
    };
  }

  // Caso INSUMO típico:
  // "JERINGAS / 26G... lote IL-4478 caduca 2027-01-31"
  const ins = clean.match(/^(.+?)\s*\/\s*(.+?)\s+lote\s+(.+?)\s+caduca\s+(\d{4}-\d{2}-\d{2})/i);
  if (ins) {
    return {
      entidad: "",
      categoria: ins[1].trim().toUpperCase(),
      nombreTipo: ins[2].trim(),
      lote: ins[3].trim(),
      caduca: ins[4],
      qtyType,
      qtyValue
    };
  }

  // Caso STOCK BAJO (probable):
  // "JERINGAS / 26G... stock bajo: 1200 unidades (umbral 1500)"
  // Aquí no hay lote, pero sí unidades.
  const low = clean.match(/^(.+?)\s*\/\s*(.+?)\s+stock\s+bajo:\s*([0-9]+(?:\.[0-9]+)?)\s*(dosis|unidades)\s*\(umbral\s*([0-9.]+)\)/i);
  if (low) {
    const cat = low[1].trim().toUpperCase();
    const nt = low[2].trim();
    const val = Number(low[3]);
    const kind = low[4].toUpperCase() === "DOSIS" ? "DOSIS" : "UNIDADES";

    return {
      entidad: "",
      categoria: cat,
      nombreTipo: nt,
      lote: "",
      caduca: "",
      qtyType: kind,
      qtyValue: val
    };
  }

  return null;
}

function formatStockPresentation({ categoria, nombreTipo, qtyType, qtyValue }) {
  if (qtyValue == null || Number.isNaN(qtyValue)) return "";

  // BIOLOGICOS: frascos (si qtyType FRASCOS)
  if (qtyType === "FRASCOS") {
    return `${Math.round(qtyValue)} frascos`;
  }

  // Si viene como DOSIS (stock bajo biológico por dosis)
  if (qtyType === "DOSIS") {
    return `${Math.round(qtyValue)} dosis`;
  }

  // INSUMOS: unidades o ml
  const cat = (categoria || "").toUpperCase();

  // JERINGAS/GUANTES: cajas = ceil(unidades / 100)
  if (cat.includes("JERING") || cat.includes("GUANT")) {
    const cajas = Math.ceil(qtyValue / 100);
    return `${cajas} cajas (${Math.round(qtyValue)} und)`;
  }

  // ALGODON: paquetes = ceil(unidades / 3) (porque paquete trae 3)
  if (cat.includes("ALGOD")) {
    const paquetes = Math.ceil(qtyValue / 3);
    return `${paquetes} paquetes (${Math.round(qtyValue)} und)`;
  }

  // ALCOHOL: convertir ml -> botellas según capacidad en nombreTipo (ej. "1000ml", "3800ml")
  if (cat.includes("ALCOHOL")) {
    const cap = extractMlCapacity(nombreTipo);
    if (cap && cap > 0) {
      const botellas = Math.ceil(qtyValue / cap);
      return `${botellas} botellas (${Math.round(qtyValue)} ml)`;
    }
    // si no puedo extraer capacidad, muestro ml
    return `${Math.round(qtyValue)} ml`;
  }

  // fallback genérico
  return `${Math.round(qtyValue)} unidades`;
}

function extractMlCapacity(nombreTipo) {
  const s = String(nombreTipo || "");
  const m = s.match(/(\d{2,5})\s*ml/i);
  if (!m) return null;
  const n = Number(m[1]);
  return Number.isFinite(n) ? n : null;
}


function parseCategoria(detalle) {
  // espera: "CATEGORIA / Nombre tipo lote ..."
  const parts = detalle.split("/");
  if (!parts.length) return "";
  return (parts[0] || "").trim().toUpperCase();
}

function mapCategoriaToUnit(cat) {
  // mapeo que pediste:
  // jeringuilla -> cajas, guantes -> cajas, alcohol -> botellas, algodon -> paquetes
  if (cat.includes("JERING")) return "cajas";
  if (cat.includes("GUANT")) return "cajas";
  if (cat.includes("ALCOHOL")) return "botellas";
  if (cat.includes("ALGOD")) return "paquetes";
  return "unidades";
}

function formatDateTime(value) {
  // value puede venir como "2026-01-22 18:56:45.828956+00"
  // o ISO. Intentamos parsear robusto.
  if (!value) return "—";
  const s = String(value).replace(" ", "T"); // para que sea parseable
  const d = new Date(s);
  if (isNaN(d.getTime())) {
    // fallback: solo primera parte YYYY-MM-DD HH:MM
    return String(value).slice(0, 16);
  }
  // formato local corto
  return d.toLocaleString(undefined, {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  });
}

function abrirModal(id_alerta, accion) {
  alertaSeleccionada = id_alerta;
  accionActual = accion;

  const title = document.getElementById("modalTitulo");
  if (title) title.textContent = (accion === "CORREGIR") ? "Corregir alerta" : "Gestionar alerta";

  const ta = document.getElementById("accionDetalle");
  if (ta) ta.value = "";

  const overlay = document.getElementById("modalAccion");
  overlay.classList.remove("hidden");
  overlay.setAttribute("aria-hidden", "false");
}

function cerrarModal() {
  const overlay = document.getElementById("modalAccion");
  overlay.classList.add("hidden");
  overlay.setAttribute("aria-hidden", "true");
}

function confirmarAccion() {
  let detalle = (document.getElementById("accionDetalle").value || "").trim();
  if (!detalle) detalle = "REVISÉ Y CONFIRMÉ QUE NO ES UN PROBLEMA";

  fetch("/api/alertas/accion", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      id_alerta: alertaSeleccionada,
      accion: accionActual,
      accion_detalle: detalle
    })
  })
    .then(r => r.json())
    .then(res => {
      cerrarModal();
      if (res && res.redirect_url) {
        window.location.href = res.redirect_url;
        return;
      }
      cargarAlertas();
    })
    .catch(() => {
      cerrarModal();
      cargarAlertas();
    });
}

function escapeHtml(str) {
  return String(str || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
