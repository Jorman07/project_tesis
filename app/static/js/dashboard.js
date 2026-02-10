(() => {
  const API = {
    init: '/api/dashboard/init',
    data: '/api/dashboard/data',
    predict: '/api/dashboard/predict'
  };



  // =========================
  // THEME / COLORES
  // =========================
  const COLORWAY = [
    '#3b82f6', '#22c55e', '#f59e0b', '#a855f7', '#ef4444',
    '#06b6d4', '#eab308', '#f97316', '#14b8a6', '#60a5fa'
  ];

  const pickColors = (n) => Array.from({ length: n }, (_, i) => COLORWAY[i % COLORWAY.length]);

  // DOM
  const selPeriodo = document.getElementById('selPeriodo');
  const selVacuna = document.getElementById('selVacuna');
  const selEsquema = document.getElementById('selEsquema');
  const btnReset = document.getElementById('btnReset');
  const msgDash = document.getElementById('msgDash');
  const kpiCapLabel = document.querySelector('.dash-kpis .kpi-card:nth-child(2) .kpi-label');
  const kpiCapSub = document.querySelector('.dash-kpis .kpi-card:nth-child(2) .kpi-sub');


  // KPIs superiores
  const kpiDosisMes = document.getElementById('kpiDosisMes');
  const kpiDosisMesSub = document.getElementById('kpiDosisMesSub');
  const kpiTemprana = document.getElementById('kpiTemprana');
  const kpiAlertas = document.getElementById('kpiAlertas');
  const kpiValidos = document.getElementById('kpiValidos');
  const kpiValidosSub = document.getElementById('kpiValidosSub');
  const kpiBioVence = document.getElementById('kpiBioVence');
  const kpiPred = document.getElementById('kpiPred');
  const kpiPredSub = document.getElementById('kpiPredSub');

  // KPIs internos insumos
  const kpiAlcoholMlIn = document.getElementById('kpiAlcoholMlIn');
  const kpiAlcoholSubIn = document.getElementById('kpiAlcoholSubIn');
  const kpiAlgodonRollosIn = document.getElementById('kpiAlgodonRollosIn');
  const kpiAlgodonSubIn = document.getElementById('kpiAlgodonSubIn');

  // KPIs recomendaciones
  const kpiBioRiesgoAlto = document.getElementById('kpiBioRiesgoAlto');
  const kpiBioRiesgoAltoSub = document.getElementById('kpiBioRiesgoAltoSub');
  const kpiInsRiesgoAlto = document.getElementById('kpiInsRiesgoAlto');
  const kpiInsRiesgoAltoSub = document.getElementById('kpiInsRiesgoAltoSub');
  const tblRecomendaciones = document.getElementById('tblRecomendaciones');

  // Panel derecho detalle
  const lotDetail = document.getElementById('lotDetail');

  const PLOTS = {
    mensual: 'pltMensual',
    vacunas: 'pltVacunas',
    diario: 'pltDiario',
    parroquia: 'pltParroquia',
    cad: 'pltCaducidad',
    calidad: 'pltCalidad',

    predPeople: 'pltPredPeople',
    predBioTop: 'pltPredBioTop',

    insumosEst: 'pltInsumosEstimados',
    insFcJer: 'pltInsumosFcJeringas',
    insFcGua: 'pltInsumosFcGuantes',

    jeringasPie: 'pltJeringasPie',

    riskRadar: 'pltRiskRadar'
  };

  const state = {
    periodo: '',
    vacuna: '',
    esquema: '',
    fecha_desde: null,
    fecha_hasta: null,
    parroquia: ''
  };

  const setMsg = (t = '', kind = '') => {
    if (!msgDash) return;
    msgDash.textContent = t;
    msgDash.style.opacity = t ? '0.95' : '0';
    msgDash.style.color = (kind === 'err') ? '#ffb4b4' : '';
  };

  const safeText = (v, fallback = '—') =>
    (v === null || v === undefined || v === '') ? fallback : String(v);

  const clean = (v) => {
    if (v === null || v === undefined) return null;
    if (typeof v === 'string') {
      const s = v.trim();
      return s === '' ? null : s;
    }
    return v;
  };

  const fetchJSON = async (url, options = {}) => {
    const res = await fetch(url, {
      headers: { 'Accept': 'application/json', 'Content-Type': 'application/json' },
      ...options
    });

    const ct = (res.headers.get('content-type') || '').toLowerCase();
    const raw = await res.text();

    let data = null;
    if (ct.includes('application/json') || (raw && raw.trim().startsWith('{'))) {
      try { data = JSON.parse(raw); } catch (_) { data = null; }
    }

    if (!res.ok) {
      const serverMsg =
        (data && (data.message || data.error || data.detail)) ?
          (data.message || data.error || data.detail) :
          (raw ? raw.slice(0, 300) : '');
      throw new Error(`HTTP ${res.status} ${res.statusText}${serverMsg ? ` | ${serverMsg}` : ''}`);
    }

    if (data === null) throw new Error('Respuesta OK pero no es JSON');
    return data;
  };

  const plotConfig = {
    responsive: true,
    displaylogo: false,
    modeBarButtonsToRemove: ['lasso2d', 'select2d']
  };

  // =========================
  // LAYOUTS BASE (con colorway)
  // =========================
  const baseLayout = () => ({
    margin: { t: 10, r: 10, b: 60, l: 55 },
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    font: { color: '#e6eefc', size: 12 },
    colorway: COLORWAY,
    xaxis: {
      gridcolor: 'rgba(255,255,255,0.08)',
      zerolinecolor: 'rgba(255,255,255,0.10)',
      tickfont: { color: '#e6eefc' }
    },
    yaxis: {
      gridcolor: 'rgba(255,255,255,0.08)',
      zerolinecolor: 'rgba(255,255,255,0.10)',
      tickfont: { color: '#e6eefc' }
    },
    legend: { orientation: 'h', y: -0.25 }
  });

  const pieLayoutBase = () => ({
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    font: { color: '#e6eefc', size: 12 },
    colorway: COLORWAY
  });

  const resizeAll = () => {
    Object.values(PLOTS).forEach(id => {
      const el = document.getElementById(id);
      if (!el) return;
      try { Plotly.Plots.resize(el); } catch (_) { }
    });
  };

  const observePlots = () => {
    if (!('ResizeObserver' in window)) return;
    const ro = new ResizeObserver(() => resizeAll());
    Object.values(PLOTS).forEach(id => {
      const el = document.getElementById(id);
      if (el) ro.observe(el);
    });
  };

  const normalizePeriodoYM = (p) => {
    const s = (p ?? '').toString().trim();
    if (!s) return '';
    if (/^\d{4}-\d{2}-\d{2}/.test(s)) return s.slice(0, 7);
    if (/^\d{4}-\d{2}$/.test(s)) return s;
    return s.length >= 7 ? s.slice(0, 7) : s;
  };

  const normalizeDateYMD = (x) => {
    if (!x) return null;
    const s = String(x);
    const m = s.match(/^(\d{4}-\d{2}-\d{2})/);
    return m ? m[1] : null;
  };

  // KPIs superiores
  const renderKPIs = (payload) => {
    const k = payload?.kpis || {};
    const cal = payload?.calidad || {};

    if (kpiDosisMes) kpiDosisMes.textContent = safeText(k.dosis_mes ?? k.total_registros);

    const parts = [];
    if (state.periodo) parts.push(`Periodo ${normalizePeriodoYM(state.periodo)}`);
    if (state.fecha_desde && state.fecha_hasta && state.fecha_desde === state.fecha_hasta) parts.push(`Día ${state.fecha_desde}`);
    if (state.parroquia) parts.push(`Parroquia ${state.parroquia}`);
    if (kpiDosisMesSub) kpiDosisMesSub.textContent = parts.length ? parts.join(' • ') : '—';


    const esquema = (state.esquema || '').trim();
    const isTemprana = /TEMPRANA/i.test(esquema);
    const isTardia = /TARD/i.test(esquema);
    const isCampania = /CAMPA/i.test(esquema);

    // ratio 0..1 -> porcentaje 0..100 (number seguro)
    const pctNum = (ratio01) => {
      const n = Number(ratio01);
      if (!Number.isFinite(n)) return 0;
      return n * 100;
    };

    // formateo seguro "12.3%"
    const fmtPct = (num, digits = 1) => {
      const n = Number(num);
      if (!Number.isFinite(n)) return '—';
      return `${n.toFixed(digits)}%`;
    };

    // % esquema sobre TOTAL (numbers seguros)
    const tmpTotal = pctNum(k.pct_temprana_total);
    const tarTotal = pctNum(k.pct_tardia_total);
    const campTotal = pctNum(k.pct_campania_total);
    const otrosTotal = pctNum(k.pct_otros_total);
    const sinTotal = pctNum(k.pct_sin_esquema_total);
    const restoTotal = otrosTotal + sinTotal;

    let ratio = null;   // 0..1
    let labelTxt = '';
    let subTxt = '';

    if (!esquema) {
      // Default: porcentajes SOBRE EL TOTAL
      ratio01 = k.pct_temprana_total; // 0..1
      // y el KPI title sigue siendo "Captación temprana" si quieres mantenerlo así
      labelTxt = '% Captación Total';
      const hasCamp = Number.isFinite(campTotal) && campTotal > 0.0001;

      subTxt =
        `Tardía ${fmtPct(tarTotal)}` +
        (hasCamp ? ` • Campaña ${fmtPct(campTotal)}` : '') +
        (restoTotal > 0 ? ` • Otros/Sin ${fmtPct(restoTotal)}` : '');

    }
    else if (isTemprana) {
      ratio = k.pct_temprana_total;
      labelTxt = '% Temprana';
      subTxt = `Tardía ${fmtPct(tarTotal)} • Campaña ${fmtPct(campTotal)}` +
        (restoTotal > 0 ? ` • Otros/Sin ${fmtPct(restoTotal)}` : '');

    } else if (isTardia) {
      ratio = k.pct_tardia_total;
      labelTxt = '% Tardía';
      subTxt = `Temprana ${fmtPct(tmpTotal)} • Campaña ${fmtPct(campTotal)}` +
        (restoTotal > 0 ? ` • Otros/Sin ${fmtPct(restoTotal)}` : '');

    } else if (isCampania) {
      ratio = k.pct_campania_total;
      labelTxt = '% Campaña';
      subTxt = `Temprana ${fmtPct(tmpTotal)} • Tardía ${fmtPct(tarTotal)}` +
        (restoTotal > 0 ? ` • Otros/Sin ${fmtPct(restoTotal)}` : '');

    } else {
      ratio = null;
      labelTxt = '% Esquema';
      subTxt = `Temprana ${fmtPct(tmpTotal)} • Tardía ${fmtPct(tarTotal)} • Campaña ${fmtPct(campTotal)}` +
        (restoTotal > 0 ? ` • Otros/Sin ${fmtPct(restoTotal)}` : '');
    }

    const pctVal = (ratio === null || ratio === undefined) ? null : pctNum(ratio);
    if (kpiTemprana) kpiTemprana.textContent = (pctVal === null) ? '100%' : fmtPct(pctVal);

    // actualizar label/sub del mismo kpi-card (sin tocar IDs/clases)
    const kpiCard = kpiTemprana?.closest('.kpi-card');
    if (kpiCard) {
      const lbl = kpiCard.querySelector('.kpi-label');
      const sub = kpiCard.querySelector('.kpi-sub');
      if (lbl) lbl.textContent = labelTxt;
      if (sub) sub.textContent = subTxt;
    }

    if (kpiAlertas) kpiAlertas.textContent = safeText(k.alertas_pendientes);

    if (kpiValidos) kpiValidos.textContent = safeText(k.reg_validos ?? cal.validos);
    if (kpiValidosSub) kpiValidosSub.textContent = safeText(k.reg_invalidos_conflictos ?? cal.invalidos_conflictos, '—');

    if (kpiBioVence) kpiBioVence.textContent = safeText(k.bio_vence_60);
  };

  // =========================
  // HELPERS DE TRAZAS (colores)
  // =========================
  const barTraceMulticolor = ({ x, y, hovertemplate, orientation = 'v' }) => ({
    type: 'bar',
    orientation,
    x,
    y,
    marker: { color: pickColors((orientation === 'h' ? y.length : x.length)) },
    hovertemplate
  });

  const renderCharts = async (payload) => {
    const mensual = Array.isArray(payload?.mensual) ? payload.mensual : [];
    const mensualAsc = [...mensual].reverse();
    await Plotly.newPlot(PLOTS.mensual, [
      barTraceMulticolor({
        x: mensualAsc.map(r => r.periodo),
        y: mensualAsc.map(r => Number(r.total || 0)),
        hovertemplate: '%{x}<br>%{y}<extra></extra>'
      })
    ], { ...baseLayout(), margin: { t: 10, r: 10, b: 70, l: 55 } }, plotConfig);

    const vacTop = Array.isArray(payload?.vacunas_top) ? payload.vacunas_top : [];
    await Plotly.newPlot(PLOTS.vacunas, [
      barTraceMulticolor({
        x: vacTop.map(r => r.vacuna),
        y: vacTop.map(r => Number(r.total || 0)),
        hovertemplate: '%{x}<br>%{y}<extra></extra>'
      })
    ], {
      ...baseLayout(),
      margin: { t: 10, r: 10, b: 90, l: 55 },
      xaxis: { ...(baseLayout().xaxis || {}), tickangle: -25 }
    }, plotConfig);

    const diario = Array.isArray(payload?.diario) ? payload.diario : [];
    await Plotly.newPlot(PLOTS.diario, [
      barTraceMulticolor({
        x: diario.map(r => r.fecha),
        y: diario.map(r => Number(r.total || 0)),
        hovertemplate: '%{x}<br>%{y}<extra></extra>'
      })
    ], {
      ...baseLayout(),
      margin: { t: 10, r: 10, b: 90, l: 55 },
      xaxis: { ...(baseLayout().xaxis || {}), type: 'category', nticks: 10, tickangle: -35 }
    }, plotConfig);

    const parr = Array.isArray(payload?.parroquia_top) ? payload.parroquia_top : [];
    await Plotly.newPlot(PLOTS.parroquia, [
      barTraceMulticolor({
        orientation: 'h',
        x: parr.map(r => Number(r.total || 0)),
        y: parr.map(r => r.parroquia),
        hovertemplate: '%{y}<br>%{x}<extra></extra>'
      })
    ], { ...baseLayout(), margin: { t: 10, r: 10, b: 40, l: 160 } }, plotConfig);

    const cad = Array.isArray(payload?.bio_cad) ? payload.bio_cad : [];
    await Plotly.newPlot(PLOTS.cad, [
      barTraceMulticolor({
        x: cad.map(r => r.bucket),
        y: cad.map(r => Number(r.total_frascos || 0)),
        hovertemplate: '%{x}<br>%{y}<extra></extra>'
      })
    ], { ...baseLayout(), margin: { t: 10, r: 10, b: 70, l: 55 } }, plotConfig);

    const cal = payload?.calidad || {};
    const v1 = Number(cal.validos || 0);
    const v2 = Number(cal.invalidos_conflictos || 0);

    await Plotly.newPlot(PLOTS.calidad, [{
      type: 'pie',
      labels: ['Válidos', 'Inválidos/Conflictos'],
      values: [v1, v2],
      hole: 0.52,
      sort: false,
      marker: { colors: ['#22c55e', '#f59e0b'] },
      textinfo: 'percent',
      textposition: 'outside',
      automargin: true,
      hovertemplate: '%{label}<br>%{value}<extra></extra>'
    }], {
      ...pieLayoutBase(),
      margin: { t: 40, r: 140, b: 20, l: 20 },
      legend: { x: 1.02, y: 1, xanchor: 'left', yanchor: 'top' },
      title: { text: 'Calidad de datos', x: 0, xanchor: 'left', font: { size: 14 } }
    }, { ...plotConfig, displayModeBar: false });

    // clicks
    const elMensual = document.getElementById(PLOTS.mensual);
    elMensual?.removeAllListeners?.('plotly_click');
    elMensual?.on?.('plotly_click', (ev) => {
      const periodoClicked = ev?.points?.[0]?.x;
      if (!periodoClicked) return;
      state.periodo = String(periodoClicked);
      state.fecha_desde = null;
      state.fecha_hasta = null;
      const ym = normalizePeriodoYM(state.periodo);
      if (selPeriodo && [...selPeriodo.options].some(o => o.value === ym)) selPeriodo.value = ym;
      refreshAll();
    });

    const elVac = document.getElementById(PLOTS.vacunas);
    elVac?.removeAllListeners?.('plotly_click');
    elVac?.on?.('plotly_click', (ev) => {
      const vacunaClicked = ev?.points?.[0]?.x;
      if (!vacunaClicked) return;
      state.vacuna = String(vacunaClicked);
      if (selVacuna) selVacuna.value = state.vacuna;
      refreshAll();
    });

    const elDia = document.getElementById(PLOTS.diario);
    elDia?.removeAllListeners?.('plotly_click');
    elDia?.on?.('plotly_click', (ev) => {
      const ymd = normalizeDateYMD(ev?.points?.[0]?.x);
      if (!ymd) return;
      state.fecha_desde = ymd;
      state.fecha_hasta = ymd;
      refreshAll();
    });

    const elParr = document.getElementById(PLOTS.parroquia);
    elParr?.removeAllListeners?.('plotly_click');
    elParr?.on?.('plotly_click', (ev) => {
      const p = ev?.points?.[0]?.y;
      if (!p) return;
      state.parroquia = String(p);
      refreshAll();
    });

    resizeAll();
  };

  // Pred: plotForecast
  const plotForecast = async (plotId, block, titleText = '') => {
    const el = document.getElementById(plotId);
    if (!el) return;

    const s = block?.series || {};
    const xh = s.x_hist || [];
    const yh = s.y_hist || [];
    const xf = s.x_fc || [];
    const yf = s.y_fc || [];
    if (!(xh.length || xf.length)) { try { Plotly.purge(el); } catch (_) { } return; }

    await Plotly.newPlot(plotId, [
      {
        type: 'scatter', mode: 'lines', name: 'Histórico',
        x: xh, y: yh,
        line: { width: 2, color: '#60a5fa' },
        hovertemplate: '%{x}<br>%{y}<extra></extra>'
      },
      {
        type: 'scatter', mode: 'lines', name: 'Forecast',
        x: xf, y: yf,
        line: { width: 2, color: '#f59e0b', dash: 'dot' },
        hovertemplate: '%{x}<br>%{y}<extra></extra>'
      }
    ], {
      ...baseLayout(),
      title: titleText ? { text: titleText } : undefined,
      margin: { t: titleText ? 35 : 10, r: 10, b: 55, l: 55 },
      xaxis: { ...(baseLayout().xaxis || {}), type: 'category', nticks: 8, tickangle: -45 }
    }, plotConfig);
  };

  // Estimado (1 gráfico)
  const renderInsumosEstimados = async (out) => {
    const block = out?.insumos_estimados;
    const daily = Array.isArray(block?.daily) ? block.daily : [];
    const k = block?.kpis || {};

    if (kpiAlcoholMlIn) kpiAlcoholMlIn.textContent = safeText(k.alcohol_ml_total);
    if (kpiAlgodonRollosIn) kpiAlgodonRollosIn.textContent = safeText(k.algodon_rollos);

    const ym = normalizePeriodoYM(state.periodo);
    const subTxt = ym ? `Periodo ${ym}` : 'Periodo';
    if (kpiAlcoholSubIn) kpiAlcoholSubIn.textContent = subTxt;
    if (kpiAlgodonSubIn) kpiAlgodonSubIn.textContent = subTxt;

    const el = document.getElementById(PLOTS.insumosEst);
    if (!el) return;

    if (!daily.length) {
      try { Plotly.purge(el); } catch (_) { }
      return;
    }

    const daily2 = ym ? daily.filter(r => String(r.fecha).startsWith(ym)) : daily;

    const x = daily2.map(r => r.fecha);
    const yJ = daily2.map(r => Number(r.jeringas || 0));
    const yG = daily2.map(r => Number(r.guantes || 0));

    await Plotly.newPlot(PLOTS.insumosEst, [
      { type: 'scatter', mode: 'lines', name: 'Jeringas', x, y: yJ, line: { color: '#06b6d4', width: 2 }, hovertemplate: '%{x}<br>Jeringas: %{y}<extra></extra>' },
      { type: 'scatter', mode: 'lines', name: 'Guantes (pares)', x, y: yG, line: { color: '#a855f7', width: 2, dash: 'dot' }, hovertemplate: '%{x}<br>Guantes: %{y}<extra></extra>' }
    ], {
      ...baseLayout(),
      margin: { t: 10, r: 10, b: 60, l: 55 },
      xaxis: { ...(baseLayout().xaxis || {}), type: 'category', nticks: 10, tickangle: -45 }
    }, plotConfig);

    resizeAll();
  };

  // Proyección (2 gráficos)
  const renderInsumosForecastSplit = async (out) => {
    const elJer = document.getElementById(PLOTS.insFcJer);
    if (elJer) {
      const s = out?.doses?.series || {};
      const x = s.x_fc || [];
      const y = (s.y_fc || []).map(v => Number(v || 0));
      if (x.length) {
        await Plotly.newPlot(PLOTS.insFcJer, [{
          type: 'scatter', mode: 'lines', name: 'Jeringas (proyección)', x, y,
          line: { color: '#06b6d4', width: 2 },
          hovertemplate: '%{x}<br>Jeringas: %{y}<extra></extra>'
        }], {
          ...baseLayout(),
          title: { text: 'Proyección Jeringas (próx mes)' },
          margin: { t: 35, r: 10, b: 60, l: 55 },
          xaxis: { ...(baseLayout().xaxis || {}), type: 'category', nticks: 10, tickangle: -45 }
        }, plotConfig);
      } else {
        try { Plotly.purge(elJer); } catch (_) { }
      }
    }

    const elGua = document.getElementById(PLOTS.insFcGua);
    if (elGua) {
      const s = out?.people?.series || {};
      const x = s.x_fc || [];
      const y = (s.y_fc || []).map(v => Number(v || 0));
      if (x.length) {
        await Plotly.newPlot(PLOTS.insFcGua, [{
          type: 'scatter', mode: 'lines', name: 'Guantes (proyección)', x, y,
          line: { color: '#a855f7', width: 2, dash: 'dot' },
          hovertemplate: '%{x}<br>Guantes: %{y}<extra></extra>'
        }], {
          ...baseLayout(),
          title: { text: 'Proyección Guantes (próx mes)' },
          margin: { t: 35, r: 10, b: 60, l: 55 },
          xaxis: { ...(baseLayout().xaxis || {}), type: 'category', nticks: 10, tickangle: -45 }
        }, plotConfig);
      } else {
        try { Plotly.purge(elGua); } catch (_) { }
      }
    }

    resizeAll();
  };

  // Pie jeringas
  const renderJeringasPie = async (out) => {
    const el = document.getElementById(PLOTS.jeringasPie);
    if (!el) return;

    const map = out?.insumos_estimados?.jeringas_por_tipo_total || {};
    const entries = Object.entries(map)
      .filter(([k, v]) => k && Number(v) > 0)
      .map(([k, v]) => [k, Number(v)])
      .sort((a, b) => b[1] - a[1]);

    if (!entries.length) {
      try { Plotly.purge(el); } catch (_) { }
      return;
    }

    const topN = 6;
    const top = entries.slice(0, topN);
    const rest = entries.slice(topN);
    const otrosSum = rest.reduce((acc, x) => acc + x[1], 0);

    const labels = top.map(x => x[0]);
    const values = top.map(x => x[1]);
    if (otrosSum > 0) { labels.push('OTROS'); values.push(otrosSum); }

    await Plotly.newPlot(PLOTS.jeringasPie, [{
      type: 'pie',
      labels,
      values,
      hole: 0.55,
      sort: false,
      marker: { colors: pickColors(labels.length) },
      textinfo: 'percent',
      textposition: 'inside',
      insidetextorientation: 'radial',
      automargin: true,
      hovertemplate: '%{label}<br>%{value}<extra></extra>'
    }], {
      ...pieLayoutBase(),
      title: { text: out?.jeringas_pie_title || 'Jeringas por tipo (total)', x: 0.5, xanchor: 'center' },
      margin: { t: 50, r: 170, b: 20, l: 20 },
      legend: { x: 1.02, y: 1, xanchor: 'left', yanchor: 'top' },
      uniformtext: { mode: 'hide', minsize: 10 }
    }, plotConfig);

    resizeAll();
  };

  // =========================
  // RECOMENDACIONES: radar NO-barra
  // =========================
  const renderRiskRadar = async (rec) => {
    const elId = PLOTS.riskRadar;
    const el = document.getElementById(elId);
    if (!el) return;

    const bio = Array.isArray(rec?.biologicos_riesgo) ? rec.biologicos_riesgo : [];
    const ins = Array.isArray(rec?.insumos_riesgo) ? rec.insumos_riesgo : [];

    const bioItems = bio.map(r => {
      const q = Number(r.p_quiebre_30d || 0);
      const v = Number(r.p_vencimiento || 0);
      return {
        name: `BIO:${String(r.vacuna || '').toUpperCase()}`,
        q, v,
        score: Math.max(q, v)
      };
    });

    const insItems = ins.map(r => {
      const q = Number(r.p_quiebre_nm || 0);
      const v = Number(r.p_vencimiento || 0);
      return {
        name: `INS:${String(r.categoria || '').toUpperCase()}`,
        q, v,
        score: Math.max(q, v)
      };
    });

    if (!bioItems.length && !insItems.length) {
      try { Plotly.purge(el); } catch (_) { }
      return;
    }

    bioItems.sort((a, b) => b.score - a.score);
    insItems.sort((a, b) => b.score - a.score);

    const topBio = bioItems.slice(0, 6);
    const topIns = insItems.slice(0, 6);

    const combined = [...topBio, ...topIns];

    const rest = [...bioItems.slice(6), ...insItems.slice(6)]
      .sort((a, b) => b.score - a.score);

    while (combined.length < 12 && rest.length) combined.push(rest.shift());

    const topN = combined.length ? combined.slice(0, 12) : [...bioItems, ...insItems].slice(0, 12);

    const theta = topN.map(x => x.name);
    const close = (arr) => arr.length ? [...arr, arr[0]] : arr;

    const thetaClosed = close(theta);
    const rQuiebre = close(topN.map(x => x.q));
    const rVenc = close(topN.map(x => x.v));

    try {
      await Plotly.newPlot(elId, [
        {
          type: "scatterpolar",
          r: rQuiebre,
          theta: thetaClosed,
          fill: "toself",
          name: "Riesgo quiebre",
          hovertemplate: "%{theta}<br>Quiebre: %{r:.2f}<extra></extra>"
        },
        {
          type: "scatterpolar",
          r: rVenc,
          theta: thetaClosed,
          fill: "toself",
          name: "Riesgo vencimiento",
          hovertemplate: "%{theta}<br>Venc.: %{r:.2f}<extra></extra>"
        }
      ], {
        paper_bgcolor: "rgba(0,0,0,0)",
        plot_bgcolor: "rgba(0,0,0,0)",
        font: { color: "#e6eefc", size: 12 },
        margin: { t: 40, r: 20, b: 20, l: 20 },
        title: { text: "Mapa de riesgos (Top ítems)", x: 0, xanchor: "left", font: { size: 13 } },
        legend: { orientation: "h", y: -0.15 },
        polar: {
          bgcolor: "rgba(0,0,0,0)",
          radialaxis: {
            range: [0, 1],
            showticklabels: true,
            tickfont: { size: 10 },
            gridcolor: "rgba(255,255,255,0.10)"
          },
          angularaxis: {
            gridcolor: "rgba(255,255,255,0.08)",
            tickfont: { size: 10 }
          }
        }
      }, plotConfig);

      resizeAll();
    } catch (e) {
      console.warn("renderRiskRadar error:", e);
    }
  };

  // =========================
  // RECOMENDACIONES: tabla + detalle
  // =========================
  let _lastRec = null;

  const badge = (lvl) => {
    const v = String(lvl || '').toUpperCase();
    const cls = v === 'ALTO' ? 'risk risk-high' : v === 'MEDIO' ? 'risk risk-med' : 'risk risk-low';
    return `<span class="${cls}">${v || '—'}</span>`;
  };

  const setLotEmpty = (msg = 'Haz clic en un ítem de la tabla para ver lotes y riesgos FEFO.') => {
    if (!lotDetail) return;
    lotDetail.classList.add('is-empty');
    lotDetail.innerHTML = `
      <div class="lot-empty">
        <div class="lot-empty-title">Sin selección</div>
        <div class="lot-empty-sub">${msg}</div>
      </div>
    `;
  };

  const renderRecomendaciones = (rec) => {
    _lastRec = rec;

    if (!rec) {
      setLotEmpty('Sin datos de recomendaciones.');
      return;
    }

    if (lotDetail && lotDetail.classList.contains('is-empty')) {
      setLotEmpty();
    }

    const k = rec.kpis || {};

    if (kpiBioRiesgoAlto) kpiBioRiesgoAlto.textContent =
      `${k.bio_riesgo_quiebre_alto ?? 0} / ${k.bio_riesgo_venc_alto ?? 0}`;
    if (kpiBioRiesgoAltoSub) kpiBioRiesgoAltoSub.textContent = 'quiebre / vencimiento';

    if (kpiInsRiesgoAlto) kpiInsRiesgoAlto.textContent =
      `${k.ins_riesgo_quiebre_alto ?? 0} / ${k.ins_riesgo_venc_alto ?? 0}`;
    if (kpiInsRiesgoAltoSub) kpiInsRiesgoAltoSub.textContent = 'quiebre / vencimiento';

    renderRiskRadar(rec);

    if (!tblRecomendaciones) return;

    const bio = Array.isArray(rec.biologicos_riesgo) ? rec.biologicos_riesgo.slice(0, 6) : [];
    const ins = Array.isArray(rec.insumos_riesgo) ? rec.insumos_riesgo.slice(0, 6) : [];

    const bioPed = {};
    (rec.biologicos_pedido || []).forEach(x => { bioPed[(x.vacuna || '').toUpperCase()] = x; });

    const insPed = {};
    (rec.insumos_pedido || []).forEach(x => { insPed[(x.categoria || '').toUpperCase()] = x; });

    const rows = [];

    bio.forEach(r => {
      const v = (r.vacuna || '').toUpperCase();
      const p = bioPed[v];
      rows.push({
        tipo: 'BIO',
        item: v,
        quiebre: r.nivel_quiebre || '—',
        venc: r.nivel_vencimiento || '—',
        pedido: p ? `${p.pedido_frascos} frascos` : '—'
      });
    });

    ins.forEach(r => {
      const c = (r.categoria || '').toUpperCase();
      const p = insPed[c];
      rows.push({
        tipo: 'INS',
        item: c,
        quiebre: r.nivel_quiebre || '—',
        venc: r.nivel_vencimiento || '—',
        pedido: p ? `${p.pedido_unidades} u` : '—'
      });
    });

    if (!rows.length) {
      tblRecomendaciones.innerHTML = `<tr><td colspan="5" class="rec-muted">Sin recomendaciones</td></tr>`;
      setLotEmpty('Sin ítems en recomendaciones.');
      return;
    }

    tblRecomendaciones.innerHTML = rows.map(r => `
      <tr class="rec-row" data-tipo="${r.tipo}" data-item="${r.item}">
        <td>${r.tipo}</td>
        <td>${r.item}</td>
        <td>${badge(r.quiebre)}</td>
        <td>${badge(r.venc)}</td>
        <td>${r.pedido}</td>
      </tr>
    `).join('');

    tblRecomendaciones.querySelectorAll('.rec-row').forEach(tr => {
      tr.addEventListener('click', () => {
        const tipo = tr.dataset.tipo;
        const item = tr.dataset.item;

        if (!lotDetail || !_lastRec) return;

        if (tipo === 'BIO') {
          const bioSel = (_lastRec.biologicos_riesgo || []).find(x =>
            String(x.vacuna).toUpperCase() === String(item).toUpperCase()
          );
          const lotes = bioSel?.lotes || [];
          if (!lotes.length) {
            setLotEmpty(`Sin lotes para ${item}.`);
            return;
          }

          lotDetail.classList.remove('is-empty');
          lotDetail.innerHTML = `
            <div class="lot-title">BIO: ${item}</div>
            <table class="lot-table">
              <thead>
                <tr>
                  <th>Lote</th>
                  <th>Caduca</th>
                  <th>Días</th>
                  <th>Frascos</th>
                  <th>Riesgo venc.</th>
                </tr>
              </thead>
              <tbody>
                ${lotes.map(l => `
                  <tr>
                    <td>${l.lote || '—'}</td>
                    <td>${l.fecha_caducidad || '—'}</td>
                    <td>${(l.dias_a_caducar ?? '—')}</td>
                    <td>${(l.stock_frascos ?? '—')}</td>
                    <td>${badge(l.nivel_vencimiento)}</td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          `;
        } else {
          const insSel = (_lastRec.insumos_riesgo || []).find(x =>
            String(x.categoria).toUpperCase() === String(item).toUpperCase()
          );
          const lotes = insSel?.lotes || [];
          if (!lotes.length) {
            setLotEmpty(`Sin lotes para ${item}.`);
            return;
          }

          lotDetail.classList.remove('is-empty');
          lotDetail.innerHTML = `
            <div class="lot-title">INS: ${item}</div>
            <table class="lot-table">
              <thead>
                <tr>
                  <th>Lote</th>
                  <th>Caduca</th>
                  <th>Días</th>
                  <th>Unidades</th>
                  <th>Riesgo venc.</th>
                </tr>
              </thead>
              <tbody>
                ${lotes.map(l => `
                  <tr>
                    <td>${l.lote || '—'}</td>
                    <td>${l.fecha_caducidad || '—'}</td>
                    <td>${(l.dias_a_caducar ?? '—')}</td>
                    <td>${(l.stock_unidades ?? '—')}</td>
                    <td>${badge(l.nivel_vencimiento)}</td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          `;
        }
      });
    });
  };

  // Predict
  const loadPredict = async () => {
    try {
      if (state.fecha_desde && state.fecha_hasta && state.fecha_desde === state.fecha_hasta) return;

      const body = {
        periodo: normalizePeriodoYM(state.periodo),
        vacuna: state.vacuna || null,
        parroquia: state.parroquia || null,
        fecha_desde: state.fecha_desde || null,
        fecha_hasta: state.fecha_hasta || null,
        window_days: 180
      };

      const out = await fetchJSON(API.predict, { method: 'POST', body: JSON.stringify(body) });
      if (!out || out.ok !== true) return;

      renderRecomendaciones(out.recomendaciones);

      // KPI predicción debe ser PERSONAS, no DOSIS
      const pPeople = out.people;
      if (pPeople?.next !== undefined) kpiPred.textContent = safeText(pPeople.next);
      if (pPeople?.label !== undefined) kpiPredSub.textContent = safeText(pPeople.label);

      await plotForecast(PLOTS.predPeople, out.people);
      await renderInsumosEstimados(out);
      await renderInsumosForecastSplit(out);

      const topEl = document.getElementById(PLOTS.predBioTop);
      if (topEl) {
        const top = Array.isArray(out?.pred_bio_top) ? out.pred_bio_top : [];
        const x = top.map(r => r.vacuna);
        const y = top.map(r => Number(r.pred_dosis || 0));
        const next = out?.next_label || 'Próximo mes';

        if (x.length) {
          await Plotly.newPlot(PLOTS.predBioTop, [
            barTraceMulticolor({
              x, y,
              hovertemplate: '%{x}<br>Pred (dosis): %{y}<extra></extra>'
            })
          ], {
            ...baseLayout(),
            margin: { t: 35, r: 10, b: 90, l: 55 },
            title: { text: `Top vacunas (dosis) ${next}` },
            xaxis: { ...(baseLayout().xaxis || {}), tickangle: -25 }
          }, plotConfig);
        } else {
          try { Plotly.purge(topEl); } catch (_) { }
        }
      }

      await renderJeringasPie(out);
      resizeAll();
    } catch (err) {
      console.warn('predict error', err);
    }
  };

  // Init
  const loadInit = async () => {
    setMsg('Cargando dashboard...');
    const init = await fetchJSON(API.init, { method: 'GET' });

    if (selPeriodo) {
      selPeriodo.innerHTML = '';
      (init?.periodos || []).forEach(p => {
        const opt = document.createElement('option');
        opt.value = p;
        opt.textContent = p;
        selPeriodo.appendChild(opt);
      });

      const def = init?.periodo_default ? String(init.periodo_default) : '';
      if (def && [...selPeriodo.options].some(o => o.value === def)) {
        selPeriodo.value = def;
        state.periodo = def;
      } else {
        state.periodo = selPeriodo.value || '';
      }
    }

    if (selVacuna) {
      const optAll = document.createElement('option');
      optAll.value = '';
      optAll.textContent = 'Todas';

      selVacuna.innerHTML = '';
      selVacuna.appendChild(optAll);

      (init?.vacunas || []).forEach(v => {
        const opt = document.createElement('option');
        opt.value = v;
        opt.textContent = v;
        selVacuna.appendChild(opt);
      });
    }

    state.vacuna = '';
    state.esquema = selEsquema ? (selEsquema.value || '') : '';
    state.fecha_desde = null;
    state.fecha_hasta = null;
    state.parroquia = '';
    setMsg('');

    if (lotDetail) {
      setLotEmpty();
    }
  };

  // Data
  const loadData = async () => {
    const body = {
      periodo: clean(normalizePeriodoYM(state.periodo)),
      vacuna: clean(state.vacuna),
      esquema: clean(state.esquema),
      fecha_desde: clean(state.fecha_desde),
      fecha_hasta: clean(state.fecha_hasta),
      parroquia: clean(state.parroquia)
    };

    const payload = await fetchJSON(API.data, { method: 'POST', body: JSON.stringify(body) });
    if (!payload || payload.ok !== true) throw new Error('dashboard_data ok=false');

    renderKPIs(payload);
    await renderCharts(payload);
  };

  const refreshAll = async () => {
    try {
      setMsg('Actualizando...');
      await loadData();
      await loadPredict();
      setMsg('');
      setTimeout(resizeAll, 120);
    } catch (err) {
      console.error(err);
      setMsg(`Sin datos al filtrar. ${err?.message || ''}`.trim(), 'err');
    }
  };

  const bindUI = () => {
    selPeriodo?.addEventListener('change', () => {
      state.periodo = selPeriodo.value || '';
      state.fecha_desde = null;
      state.fecha_hasta = null;
      refreshAll();
    });

    selVacuna?.addEventListener('change', () => {
      state.vacuna = selVacuna.value || '';
      refreshAll();
    });

    selEsquema?.addEventListener('change', () => {
      state.esquema = selEsquema.value || '';
      refreshAll();
    });

    btnReset?.addEventListener('click', () => {
      state.vacuna = '';
      state.esquema = '';
      state.fecha_desde = null;
      state.fecha_hasta = null;
      state.parroquia = '';

      if (selVacuna) selVacuna.value = '';
      if (selEsquema) selEsquema.value = '';

      setMsg('Filtros reseteados');
      setTimeout(() => setMsg(''), 1000);

      if (lotDetail) setLotEmpty();

      refreshAll();
    });

    window.addEventListener('resize', resizeAll);
  };

  (async () => {
    bindUI();
    observePlots();
    await loadInit();
    await refreshAll();
  })();
})();
