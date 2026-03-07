(() => {
  const API = {
    init: '/api/dashboard/init',
    data: '/api/dashboard/data',
    insumos_estimados: '/api/dashboard/insumos_estimados',
    predict: '/api/dashboard/predict',
    compare: '/api/dashboard/compare',
    anual: '/api/dashboard/anual'
  };

  const COLORWAY = [
    '#3b82f6', '#22c55e', '#f59e0b', '#a855f7', '#ef4444',
    '#06b6d4', '#eab308', '#f97316', '#14b8a6', '#60a5fa'
  ];
  const pickColors = (n) => Array.from({ length: n }, (_, i) => COLORWAY[i % COLORWAY.length]);

  const nf = new Intl.NumberFormat('es-EC');
  const nFmt = (v, fallback = '—') => {
    const x = Number(v);
    return Number.isFinite(x) ? nf.format(x) : fallback;
  };
  const pctFmt = (v, digits = 1, fallback = '—') => {
    const x = Number(v);
    return Number.isFinite(x) ? `${x.toFixed(digits)}%` : fallback;
  };

  // =========================
  // DOM
  // =========================
  const selPeriodo = document.getElementById('selPeriodo');
  const selVacuna = document.getElementById('selVacuna');
  const selEsquema = document.getElementById('selEsquema');
  const btnReset = document.getElementById('btnReset');
  const msgDash = document.getElementById('msgDash');

  const menuSecciones = document.getElementById('menuSecciones');
  const secPanorama = document.getElementById('secPanorama');
  const secPrediccion = document.getElementById('secPrediccion');
  const secComparativos = document.getElementById('secComparativos');
  const secAnual = document.getElementById('secAnual');
  const dashFilters = document.querySelector('.dash-filters');
  // Predicción
  // Predicción filtros
  const predFilters = document.getElementById('predFilters');
  const selPredPeriodo = document.getElementById('selPredPeriodo');
  const selPredHorizon = document.getElementById('selPredHorizon');
  const btnPredActualizar = document.getElementById('btnPredActualizar');

  // Títulos dinámicos Predicción
  const tPredPersonas = document.getElementById('tPredPersonas');
  const tPredBioTop = document.getElementById('tPredBioTop');
  const tPredInsumos = document.getElementById('tPredInsumos');


  // Compare (SIN dimensión)
  const selPeriodoA = document.getElementById('selPeriodoA');
  const selPeriodoB = document.getElementById('selPeriodoB');
  const btnCompActualizar = document.getElementById('btnCompActualizar');

  const kpiCompDosis = document.getElementById('kpiCompDosis');
  const kpiCompDosisSub = document.getElementById('kpiCompDosisSub');
  const kpiCompPersonas = document.getElementById('kpiCompPersonas');
  const kpiCompPersonasSub = document.getElementById('kpiCompPersonasSub');
  const kpiCompValidos = document.getElementById('kpiCompValidos');
  const kpiCompValidosSub = document.getElementById('kpiCompValidosSub');
  const kpiCompInvalidos = document.getElementById('kpiCompInvalidos');
  const kpiCompInvalidosSub = document.getElementById('kpiCompInvalidosSub');

  // Panorama KPIs
  const kpiDosisMes = document.getElementById('kpiDosisMes');
  const kpiDosisMesSub = document.getElementById('kpiDosisMesSub');
  const kpiTemprana = document.getElementById('kpiTemprana');
  const kpiAlertas = document.getElementById('kpiAlertas');
  const kpiValidos = document.getElementById('kpiValidos');
  const kpiValidosSub = document.getElementById('kpiValidosSub');
  const kpiBioVence = document.getElementById('kpiBioVence');
  const kpiPred = document.getElementById('kpiPred');
  const kpiPredSub = document.getElementById('kpiPredSub');

  const kpiAlcoholMlIn = document.getElementById('kpiAlcoholMlIn');
  const kpiAlcoholSubIn = document.getElementById('kpiAlcoholSubIn');
  const kpiAlgodonRollosIn = document.getElementById('kpiAlgodonRollosIn');
  const kpiAlgodonSubIn = document.getElementById('kpiAlgodonSubIn');

  const kpiBioRiesgoAlto = document.getElementById('kpiBioRiesgoAlto');
  const kpiBioRiesgoAltoSub = document.getElementById('kpiBioRiesgoAltoSub');
  const kpiInsRiesgoAlto = document.getElementById('kpiInsRiesgoAlto');
  const kpiInsRiesgoAltoSub = document.getElementById('kpiInsRiesgoAltoSub');
  const tblRecomendaciones = document.getElementById('tblRecomendaciones');

  // Anual
  const anualFilters = document.getElementById('anualFilters');
  const selAnio = document.getElementById('selAnio');
  const selAnualDimension = document.getElementById('selAnualDimension');
  const btnAnualActualizar = document.getElementById('btnAnualActualizar');

  const lotDetail = document.getElementById('lotDetail');

  // =========================
  // PLOTS
  // =========================
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
    riskRadar: 'pltRiskRadar',

    // Compare (2 principales)
    compDim: 'pltCompDim',
    compDrivers: 'pltCompDrivers',

    // Compare (opcionales fijos, si existen en HTML)
    compEsquemas: 'pltCompEsquemas',
    compRiesgo: 'pltCompRiesgo',
    compSexo: 'pltCompSexo',
    compEdad: 'pltCompEdad',
    compParroquia: 'pltCompParroquia',

    //anualMensual: 'pltAnualMensual',
    //anualTopVac: 'pltAnualTopVac',
    //anualCalidad: 'pltAnualCalidad',

    anualCalidad: 'pltAnualCalidad',
    anualTopVac: 'pltAnualTopVac',
    anualDosisMes: 'pltAnualDosisMes',
    anualPersonasMes: 'pltAnualPersonasMes',
    anualEsquemas: 'pltAnualEsquemas',
    anualTopMes: 'pltAnualTopMes',
    anualInsumosMes: 'pltAnualInsumosMes',
  };

  // =========================
  // STATE
  // =========================
  const state = {
    periodo: '',
    vacuna: '',
    esquema: '',
    fecha_desde: null,
    fecha_hasta: null,
    parroquia: ''
  };

  const stateUI = {
    tab: 'panorama',
    init: null,
    predictCacheKey: null,
    predictCacheOut: null,
    predictWarmScheduled: false
  };

  const predState = {
    periodo_base: '',
    horizon_m: 1
  };


  // =========================
  // Helpers
  // =========================
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

  // Plotly config (estable)
  const plotConfig = {
    responsive: false,
    displaylogo: false,
    displayModeBar: true,
    modeBarButtonsToRemove: ['lasso2d', 'select2d']
  };

  const baseLayout = () => ({
    margin: { t: 70, r: 30, b: 110, l: 85 },
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    font: { color: '#e6eefc', size: 12 },
    colorway: COLORWAY,
    title: {
      x: 0,
      xanchor: 'left',
      y: 0.96
    },
    xaxis: {
      title: { text: '' },
      gridcolor: 'rgba(255,255,255,0.08)',
      zerolinecolor: 'rgba(255,255,255,0.10)',
      tickfont: { color: '#e6eefc' },
      automargin: true
    },
    yaxis: {
      title: { text: '' },
      gridcolor: 'rgba(255,255,255,0.08)',
      zerolinecolor: 'rgba(255,255,255,0.10)',
      tickfont: { color: '#e6eefc' },
      automargin: true
    },
    legend: { orientation: 'h', y: -0.25 }
  });

  const pieLayoutBase = () => ({
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    font: { color: '#e6eefc', size: 12 },
    colorway: COLORWAY
  });

  const isVisible = (el) => {
    if (!el) return false;
    const r = el.getBoundingClientRect();
    return r.width > 10 && r.height > 10;
  };

  const plotHeightFor = (plotId) => {
    const el = document.getElementById(plotId);
    const box = el?.closest('.plot') || el;
    if (!box) return 320;
    const h = Math.round(box.getBoundingClientRect().height);
    return (h && h > 50) ? h : 320;
  };

  let _resizeRaf = 0;
  let _resizing = false;

  const resizeAll = () => {
    if (_resizeRaf) cancelAnimationFrame(_resizeRaf);
    _resizeRaf = requestAnimationFrame(() => {
      _resizeRaf = 0;
      if (_resizing) return;
      _resizing = true;
      try {
        Object.values(PLOTS).forEach(id => {
          const el = document.getElementById(id);
          if (!el || !isVisible(el)) return;
          try { Plotly.Plots.resize(el); } catch (_) { }
        });
      } finally {
        _resizing = false;
      }
    });
  };

  const waitTwoFrames = () =>
    new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));

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

  const barTraceMulticolor = ({ x, y, hovertemplate, orientation = 'v' }) => ({
    type: 'bar',
    orientation,
    x,
    y,
    marker: { color: pickColors((orientation === 'h' ? y.length : x.length)) },
    hovertemplate
  });

  const ensureArray = (x) => Array.isArray(x) ? x : [];

  // =========================
  // TABS (sin display:none)
  // =========================
  const setTab = async (tab) => {
    stateUI.tab = tab;

    if (menuSecciones) {
      menuSecciones.querySelectorAll('.tab-btn').forEach(b => {
        const is = (b.dataset.tab === tab);
        b.classList.toggle('is-active', is);
        b.setAttribute('aria-selected', is ? 'true' : 'false');
      });
    }

    const map = { panorama: secPanorama, prediccion: secPrediccion, comparativos: secComparativos, anual: secAnual };
    Object.entries(map).forEach(([k, el]) => {
      if (!el) return;
      el.classList.toggle('is-hidden', k !== tab);
    });

    if (dashFilters) dashFilters.style.display = (tab === 'comparativos' || tab === 'anual' || tab === 'prediccion') ? 'none' : '';
    if (predFilters) predFilters.style.display = (tab === 'prediccion') ? '' : 'none';
    if (anualFilters) anualFilters.style.display = (tab === 'anual') ? '' : 'none';

    if (tab === 'panorama') {
      setPanoramaTitles(state.periodo);
    }

    if (tab === 'prediccion') {
      setPredTitles(predState.periodo_base, predState.horizon_m);
    }


    await waitTwoFrames();
    await refreshCurrent();
    resizeAll();
  };

  // =========================
  // PANORAMA
  // =========================

  function monthNameFromYYYYMM(yyyymm) {
    if (!yyyymm) return null;

    const [y, m] = String(yyyymm).split('-');
    const meses = [
      'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
      'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
    ];

    const mNum = Number(m);
    if (!Number.isFinite(mNum) || mNum < 1 || mNum > 12) return null;

    return `${meses[mNum - 1]} ${y}`;
  }

  function setPanoramaTitles(periodo) {
    const periodoTxt = monthNameFromYYYYMM(periodo);

    const titles = document.querySelectorAll(
      '#secPanorama .dash-card-title[data-title-base]'
    );

    titles.forEach(el => {
      const base = el.dataset.titleBase || '';
      el.textContent = periodoTxt
        ? `${base} – ${periodoTxt}`
        : base;
    });
  }


  const loadInsumosEstimadosPanorama = async () => {
    // fetch propio (NO depende de "out")
    const body = {
      periodo: clean(normalizePeriodoYM(state.periodo)),
      vacuna: clean(state.vacuna)
    };

    const out = await fetchJSON(API.insumos_estimados, {
      method: 'POST',
      body: JSON.stringify(body)
    });


    if (!out || out.ok !== true) throw new Error('insumos_estimados ok=false');

    // --- KPIs ---
    const daily = ensureArray(out?.daily);
    const k = out?.kpis || {};

    if (kpiAlcoholMlIn) kpiAlcoholMlIn.textContent = safeText(k.alcohol_ml_total);
    if (kpiAlgodonRollosIn) kpiAlgodonRollosIn.textContent = safeText(k.algodon_rollos);

    const ym = normalizePeriodoYM(out?.periodo || state.periodo);
    const subTxt = ym ? `Periodo ${ym}` : 'Periodo';
    if (kpiAlcoholSubIn) kpiAlcoholSubIn.textContent = subTxt;
    if (kpiAlgodonSubIn) kpiAlgodonSubIn.textContent = subTxt;

    // --- Plot insumos estimados ---
    {
      const el = document.getElementById(PLOTS.insumosEst);
      if (el) {
        if (!daily.length) { try { Plotly.purge(el); } catch (_) { } }
        else {
          const x = daily.map(r => r.fecha);
          const yJ = daily.map(r => Number(r.jeringas || 0));
          const yG = daily.map(r => Number(r.guantes || 0));

          await Plotly.newPlot(PLOTS.insumosEst, [
            { type: 'scatter', mode: 'lines', name: 'Jeringas', x, y: yJ, hovertemplate: '%{x}<br>%{y}<extra></extra>' },
            { type: 'scatter', mode: 'lines', name: 'Guantes (pares)', x, y: yG, hovertemplate: '%{x}<br>%{y}<extra></extra>' }
          ], {
            ...baseLayout(),
            height: plotHeightFor(PLOTS.insumosEst),
            margin: { t: 12, r: 12, b: 120, l: 64 },

            legend: {
              orientation: 'h',
              xref: 'paper',
              yref: 'paper',
              x: 0.5,
              y: -0.38,
              xanchor: 'center',
              yanchor: 'top'
            },

            xaxis: {
              ...(baseLayout().xaxis || {}),
              title: { text: 'Fecha diaria' },
              type: 'category',
              nticks: 10,
              tickangle: -45,
              automargin: true
            },
            yaxis: {
              ...(baseLayout().yaxis || {}),
              title: { text: 'Unidades usadas' },
              automargin: true
            }
          }, plotConfig);
        }
      }
    }

    // --- Pie jeringas por tipo ---
    {
      const el = document.getElementById(PLOTS.jeringasPie);
      if (el) {
        const map = out?.jeringas_por_tipo_total || {};
        const entries = Object.entries(map)
          .filter(([k, v]) => k && Number(v) > 0)
          .map(([k, v]) => [k, Number(v)])
          .sort((a, b) => b[1] - a[1]);

        if (!entries.length) { try { Plotly.purge(el); } catch (_) { } }
        else {
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
            hovertemplate: '%{label}<br>%{value}<extra></extra>',
            // Donut grande abajo (reserva franja superior para leyenda)
            domain: { x: [0.06, 0.94], y: [0.00, 0.78] }
          }], {
            ...pieLayoutBase(),
            height: plotHeightFor(PLOTS.jeringasPie),
            margin: { t: 110, r: 20, b: 20, l: 20 },

            legend: {
              orientation: 'h',
              xref: 'paper',
              yref: 'paper',
              x: 0.5,
              y: 1.12,
              xanchor: 'center',
              yanchor: 'top',

              // evita columna: cada item ocupa un ancho fijo y se “reparte”
              entrywidth: 140,
              entrywidthmode: 'pixels',

              // compacto
              itemsizing: 'constant',
              font: { size: 11 }
            }
          }, { ...plotConfig, displayModeBar: false });
        }
      }
    }
  };


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

    const pctNum = (ratio01) => {
      const n = Number(ratio01);
      if (!Number.isFinite(n)) return 0;
      return n * 100;
    };
    const fmtPct = (num, digits = 1) => {
      const n = Number(num);
      if (!Number.isFinite(n)) return '—';
      return `${n.toFixed(digits)}%`;
    };

    const tmpTotal = pctNum(k.pct_temprana_total);
    const tarTotal = pctNum(k.pct_tardia_total);
    const campTotal = pctNum(k.pct_campania_total);
    const otrosTotal = pctNum(k.pct_otros_total);
    const sinTotal = pctNum(k.pct_sin_esquema_total);
    const restoTotal = otrosTotal + sinTotal;

    let ratio = null;
    let labelTxt = '';
    let subTxt = '';

    if (!esquema) {
      ratio = null;
      labelTxt = '% Captación Total';
      const hasCamp = Number.isFinite(campTotal) && campTotal > 0.0001;
      subTxt =
        `Temprana ${fmtPct(tmpTotal)}` +
        ` • Tardía ${fmtPct(tarTotal)}` +
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
  // PANORAMA charts
  // =========================
  const renderCharts = async (payload) => {
    const mensual = ensureArray(payload?.mensual);
    const mensualAsc = [...mensual].reverse();
    await Plotly.newPlot(PLOTS.mensual, [
      barTraceMulticolor({
        x: mensualAsc.map(r => r.periodo),
        y: mensualAsc.map(r => Number(r.total || 0)),
        hovertemplate: '%{x}<br>%{y}<extra></extra>'
      })
    ], {
      ...baseLayout(),
      height: plotHeightFor(PLOTS.mensual),
      xaxis: { ...(baseLayout().xaxis || {}), title: { text: 'Periodo' } },
      yaxis: { ...(baseLayout().yaxis || {}), title: { text: 'Dosis' } },
      margin: { t: 12, r: 12, b: 78, l: 64 }
    }, plotConfig);

    const vacTop = ensureArray(payload?.vacunas_top);
    await Plotly.newPlot(PLOTS.vacunas, [
      barTraceMulticolor({
        x: vacTop.map(r => r.vacuna),
        y: vacTop.map(r => Number(r.total || 0)),
        hovertemplate: '%{x}<br>%{y}<extra></extra>'
      })
    ], {
      ...baseLayout(),
      height: plotHeightFor(PLOTS.vacunas),
      xaxis: { ...(baseLayout().xaxis || {}), title: { text: 'Vacuna' }, tickangle: -25 },
      yaxis: { ...(baseLayout().yaxis || {}), title: { text: 'Dosis Aplicadas' } },
      margin: { t: 12, r: 12, b: 96, l: 64 }
    }, plotConfig);

    const diario = ensureArray(payload?.diario);
    await Plotly.newPlot(PLOTS.diario, [
      barTraceMulticolor({
        x: diario.map(r => r.fecha),
        y: diario.map(r => Number(r.total || 0)),
        hovertemplate: '%{x}<br>%{y}<extra></extra>'
      })
    ], {
      ...baseLayout(),
      height: plotHeightFor(PLOTS.diario),
      xaxis: { ...(baseLayout().xaxis || {}), title: { text: 'Fecha diaria' }, type: 'category', nticks: 10, tickangle: -35 },
      yaxis: { ...(baseLayout().yaxis || {}), title: { text: 'Dosis Aplicadas' } },
      margin: { t: 12, r: 12, b: 100, l: 64 }
    }, plotConfig);

    const parr = ensureArray(payload?.parroquia_top);
    await Plotly.newPlot(PLOTS.parroquia, [
      barTraceMulticolor({
        orientation: 'h',
        x: parr.map(r => Number(r.total || 0)),
        y: parr.map(r => r.parroquia),
        hovertemplate: '%{y}<br>%{x}<extra></extra>'
      })
    ], {
      ...baseLayout(),
      height: plotHeightFor(PLOTS.parroquia),
      xaxis: { ...(baseLayout().xaxis || {}), title: { text: 'Dosis válidas' } },
      yaxis: { ...(baseLayout().yaxis || {}), title: { text: 'Parroquia' } },
      margin: { t: 12, r: 12, b: 50, l: 190 }
    }, plotConfig);

    const cad = ensureArray(payload?.bio_cad);
    await Plotly.newPlot(PLOTS.cad, [
      barTraceMulticolor({
        x: cad.map(r => r.bucket),
        y: cad.map(r => Number(r.total_frascos || 0)),
        hovertemplate: '%{x}<br>%{y}<extra></extra>'
      })
    ], {
      ...baseLayout(),
      height: plotHeightFor(PLOTS.cad),
      xaxis: { ...(baseLayout().xaxis || {}), title: { text: 'Ventana de caducidad' } },
      yaxis: { ...(baseLayout().yaxis || {}), title: { text: 'Frascos' } },
      margin: { t: 12, r: 12, b: 78, l: 64 }
    }, plotConfig);

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
      height: plotHeightFor(PLOTS.calidad),
      margin: { t: 44, r: 160, b: 20, l: 20 },
      legend: { x: 1.02, y: 1, xanchor: 'left', yanchor: 'top' },
      title: { text: 'Calidad de datos', x: 0, xanchor: 'left', font: { size: 14 } }
    }, { ...plotConfig, displayModeBar: false });

    // Clicks (solo fuera de comparativos)
    const shouldBindClicks = (stateUI.tab !== 'comparativos');

    const elMensual = document.getElementById(PLOTS.mensual);
    elMensual?.removeAllListeners?.('plotly_click');
    if (shouldBindClicks) {
      elMensual?.on?.('plotly_click', (ev) => {
        const periodoClicked = ev?.points?.[0]?.x;
        if (!periodoClicked) return;
        state.periodo = String(periodoClicked);
        state.fecha_desde = null;
        state.fecha_hasta = null;
        const ym = normalizePeriodoYM(state.periodo);
        if (selPeriodo && [...selPeriodo.options].some(o => o.value === ym)) selPeriodo.value = ym;
        refreshCurrent();
      });
    }

    const elVac = document.getElementById(PLOTS.vacunas);
    elVac?.removeAllListeners?.('plotly_click');
    if (shouldBindClicks) {
      elVac?.on?.('plotly_click', (ev) => {
        const vacunaClicked = ev?.points?.[0]?.x;
        if (!vacunaClicked) return;
        state.vacuna = String(vacunaClicked);
        if (selVacuna) selVacuna.value = state.vacuna;
        refreshCurrent();
      });
    }

    const elDia = document.getElementById(PLOTS.diario);
    elDia?.removeAllListeners?.('plotly_click');
    if (shouldBindClicks) {
      elDia?.on?.('plotly_click', (ev) => {
        const ymd = normalizeDateYMD(ev?.points?.[0]?.x);
        if (!ymd) return;
        state.fecha_desde = ymd;
        state.fecha_hasta = ymd;
        refreshCurrent();
      });
    }

    const elParr = document.getElementById(PLOTS.parroquia);
    elParr?.removeAllListeners?.('plotly_click');
    if (shouldBindClicks) {
      elParr?.on?.('plotly_click', (ev) => {
        const p = ev?.points?.[0]?.y;
        if (!p) return;
        state.parroquia = String(p);
        refreshCurrent();
      });
    }
  };

  // =========================
  // PREDICT
  // =========================

  function addMonthsYM(ym, k) {
    const s = String(ym || '').trim();
    if (!/^\d{4}-\d{2}$/.test(s)) return null;
    const y = Number(s.slice(0, 4));
    const m = Number(s.slice(5, 7));
    const d = new Date(y, m - 1 + Number(k || 0), 1);
    const yy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    return `${yy}-${mm}`;
  }

  function setPredTitles(periodoBase, horizonM) {
    const base = normalizePeriodoYM(periodoBase) || String(periodoBase || '').slice(0, 7);
    const h = Math.max(1, Number(horizonM || 1));
    const end = addMonthsYM(base, h); // base + h meses (si base=2026-01 y h=3 => end=2026-04)
    const rango = base && end ? `${base} → ${end}` : (base ? `${base}` : '');

    const set = (id, suffix) => {
      const el = document.getElementById(id);
      if (!el) return;
      const baseTxt = el.getAttribute('data-title-base') || el.textContent || '';
      el.textContent = rango ? `${baseTxt} — ${rango}${suffix || ''}` : baseTxt;
    };

    set('tPredPersonas', '');
    set('tPredBioTop', '');
    set('tPredInsumos', '');
  }

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
        type: 'scatter', mode: 'lines', name: 'Histórico', x: xh, y: yh,
        line: { width: 2, color: '#60a5fa' },
        hovertemplate: '%{x}<br>%{y}<extra></extra>'
      },
      {
        type: 'scatter', mode: 'lines', name: 'Proyección', x: xf, y: yf,
        line: { width: 2, color: '#f59e0b', dash: 'dot' },
        hovertemplate: '%{x}<br>%{y}<extra></extra>'
      }
    ], {
      ...baseLayout(),
      height: plotHeightFor(plotId),
      //title: titleText ? { text: titleText } : undefined,
      margin: { t: 12, r: 12, b: 130, l: 64 },

      legend: {
        orientation: 'h',
        xref: 'paper',
        yref: 'paper',
        x: 0.5,
        y: -0.70,
        xanchor: 'center',
        yanchor: 'top'
      },

      xaxis: {
        ...(baseLayout().xaxis || {}),
        title: { text: 'Periodo (mes)' },   // ojo: si es diario, cambia el texto
        type: 'category',
        nticks: 8,
        tickangle: -45,
        automargin: true
      },
      yaxis: {
        ...(baseLayout().yaxis || {}),
        title: { text: 'Personas' },
        automargin: true
      }
    }, plotConfig);
  };



  const renderInsumosForecastSplit = async (out, horizonM = 1) => {
    const h = Math.max(1, Number(horizonM || 1));

    const renderOne = async (plotId, block, opt) => {
      const el = document.getElementById(plotId);
      if (!el) return;

      const s = block?.series || {};
      const xf = s.x_fc || [];
      const yf = (s.y_fc || []).map(v => Number(v || 0));

      // mensual agregado desde backend (metrics.monthly_fc)
      const mfc = ensureArray(block?.metrics?.monthly_fc);
      const xm = mfc.map(r => r.periodo);
      const ym = mfc.map(r => Number(r.total || 0));

      // horizon > 1 => mensual (barras o línea)
      if (h > 1) {
        if (!xm.length) { try { Plotly.purge(el); } catch (_) { } return; }

        await Plotly.newPlot(plotId, [{
          type: opt?.monthlyType || 'bar',     // bar recomendado
          x: xm,
          y: ym,
          name: opt?.name || 'Proyección',
          hovertemplate: '%{x}<br>%{y}<extra></extra>',
          // si quieres multicolor como top vacunas:
          marker: opt?.multicolor ? { color: pickColors(xm.length) } : undefined
        }], {
          ...baseLayout(),
          height: plotHeightFor(plotId),
          title: { text: opt?.titleMonthly || '' },
          margin: { t: 90, r: 12, b: 80, l: 64 },
          xaxis: { ...(baseLayout().xaxis || {}), title: { text: 'Periodo (mes)' }, type: 'category', tickangle: -35 },
          yaxis: { ...(baseLayout().yaxis || {}), title: { text: opt?.yTitle || 'Personas' } }
        }, plotConfig);

        return;
      }

      // horizon == 1 => diario (como antes)
      if (!xf.length) { try { Plotly.purge(el); } catch (_) { } return; }

      await Plotly.newPlot(plotId, [{
        type: 'scatter',
        mode: 'lines',
        name: opt?.name || 'Proyección',
        x: xf,
        y: yf,
        line: opt?.line || { width: 2 },
        hovertemplate: '%{x}<br>%{y}<extra></extra>'
      }], {
        ...baseLayout(),
        height: plotHeightFor(plotId),
        title: { text: opt?.titleDaily || '' },
        margin: { t: 90, r: 12, b: 80, l: 64 },
        xaxis: { ...(baseLayout().xaxis || {}), title: { text: 'Fecha diaria' }, type: 'category', nticks: 10, tickangle: -45 },
        yaxis: { ...(baseLayout().yaxis || {}), title: { text: opt?.yTitle || 'Consumo proyectado' } }
      }, plotConfig);
    };

    await renderOne(PLOTS.insFcJer, out?.doses, {
      name: 'Jeringas (proyección)',
      yTitle: h > 1 ? 'Jeringas (mes)' : 'Jeringas (día)',
      titleDaily: 'Proyección de jeringas',
      titleMonthly: 'Proyección de jeringas (mensual)',
      // multicolor opcional:
      multicolor: true,
      monthlyType: 'bar'
    });

    await renderOne(PLOTS.insFcGua, out?.people, {
      name: 'Guantes (pares, proyección)',
      yTitle: h > 1 ? 'Guantes (mes)' : 'Guantes (día)',
      titleDaily: 'Proyección de guantes',
      titleMonthly: 'Proyección de guantes (mensual)',
      multicolor: true,
      monthlyType: 'bar'
    });
  };





  // =========================
  // Recomendaciones + radar
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

  const renderRiskRadar = async (rec) => {
    const elId = PLOTS.riskRadar;
    const el = document.getElementById(elId);
    if (!el) return;

    const bio = ensureArray(rec?.biologicos_riesgo);
    const ins = ensureArray(rec?.insumos_riesgo);

    const bioItems = bio.map(r => {
      const q = Number(r.p_quiebre_30d || 0);
      const v = Number(r.p_vencimiento || 0);
      return { name: `BIO:${String(r.vacuna || '').toUpperCase()}`, q, v, score: Math.max(q, v) };
    });

    const insItems = ins.map(r => {
      const q = Number(r.p_quiebre_nm || 0);
      const v = Number(r.p_vencimiento || 0);
      return { name: `INS:${String(r.categoria || '').toUpperCase()}`, q, v, score: Math.max(q, v) };
    });

    if (!bioItems.length && !insItems.length) { try { Plotly.purge(el); } catch (_) { } return; }

    bioItems.sort((a, b) => b.score - a.score);
    insItems.sort((a, b) => b.score - a.score);

    const topBio = bioItems.slice(0, 6);
    const topIns = insItems.slice(0, 6);
    const combined = [...topBio, ...topIns];
    const rest = [...bioItems.slice(6), ...insItems.slice(6)].sort((a, b) => b.score - a.score);
    while (combined.length < 12 && rest.length) combined.push(rest.shift());

    const topN = combined.slice(0, 12);
    const theta = topN.map(x => x.name);
    const close = (arr) => arr.length ? [...arr, arr[0]] : arr;

    const thetaClosed = close(theta);
    const rQuiebre = close(topN.map(x => x.q));
    const rVenc = close(topN.map(x => x.v));

    await Plotly.newPlot(elId, [
      {
        type: "scatterpolar", r: rQuiebre, theta: thetaClosed, fill: "toself", name: "Riesgo de quiebre",
        hovertemplate: "%{theta}<br>Quiebre: %{r:.2f}<extra></extra>"
      },
      {
        type: "scatterpolar", r: rVenc, theta: thetaClosed, fill: "toself", name: "Riesgo de vencimiento",
        hovertemplate: "%{theta}<br>Vencimiento: %{r:.2f}<extra></extra>"
      }
    ], {
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      font: { color: "#e6eefc", size: 12 },
      height: plotHeightFor(PLOTS.riskRadar),
      margin: { t: 46, r: 20, b: 24, l: 20 },
      //title: { text: "Mapa de riesgos (ítems con mayor prioridad)", x: 0, xanchor: "left", font: { size: 13 } },
      legend: { orientation: "h", y: -0.15 },
      polar: {
        bgcolor: "rgba(0,0,0,0)",
        radialaxis: { range: [0, 1], showticklabels: true, tickfont: { size: 10 }, gridcolor: "rgba(255,255,255,0.10)" },
        angularaxis: { gridcolor: "rgba(255,255,255,0.08)", tickfont: { size: 10 } }
      }
    }, plotConfig);
  };

  const renderRecomendaciones = (rec) => {
    _lastRec = rec;

    if (!rec) { setLotEmpty('Sin datos de recomendaciones.'); return; }
    if (lotDetail && lotDetail.classList.contains('is-empty')) setLotEmpty();

    const k = rec.kpis || {};
    if (kpiBioRiesgoAlto) kpiBioRiesgoAlto.textContent = `${k.bio_riesgo_quiebre_alto ?? 0} / ${k.bio_riesgo_venc_alto ?? 0}`;
    if (kpiBioRiesgoAltoSub) kpiBioRiesgoAltoSub.textContent = 'quiebre / vencimiento';
    if (kpiInsRiesgoAlto) kpiInsRiesgoAlto.textContent = `${k.ins_riesgo_quiebre_alto ?? 0} / ${k.ins_riesgo_venc_alto ?? 0}`;
    if (kpiInsRiesgoAltoSub) kpiInsRiesgoAltoSub.textContent = 'quiebre / vencimiento';

    renderRiskRadar(rec);

    if (!tblRecomendaciones) return;

    const bio = ensureArray(rec.biologicos_riesgo).slice(0, 6);
    const ins = ensureArray(rec.insumos_riesgo).slice(0, 6);

    const bioPed = {};
    (rec.biologicos_pedido || []).forEach(x => { bioPed[(x.vacuna || '').toUpperCase()] = x; });
    const insPed = {};
    (rec.insumos_pedido || []).forEach(x => { insPed[(x.categoria || '').toUpperCase()] = x; });

    const rows = [];
    bio.forEach(r => {
      const v = (r.vacuna || '').toUpperCase();
      const p = bioPed[v];
      rows.push({ tipo: 'BIO', item: v, quiebre: r.nivel_quiebre || '—', venc: r.nivel_vencimiento || '—', pedido: p ? `${p.pedido_frascos} frascos` : '—' });
    });
    ins.forEach(r => {
      const c = (r.categoria || '').toUpperCase();
      const p = insPed[c];
      rows.push({ tipo: 'INS', item: c, quiebre: r.nivel_quiebre || '—', venc: r.nivel_vencimiento || '—', pedido: p ? `${p.pedido_unidades} u` : '—' });
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

    const renderLotes = (title, lotes, isBio) => {
      if (!lotDetail) return;
      if (!lotes || !lotes.length) { setLotEmpty(`Sin lotes para ${title}.`); return; }

      lotDetail.classList.remove('is-empty');
      lotDetail.innerHTML = `
        <div class="lot-title">${title}</div>
        <table class="lot-table">
          <thead>
            <tr>
              <th>Lote</th>
              <th>Caduca</th>
              <th>Días</th>
              <th>${isBio ? 'Frascos' : 'Unidades'}</th>
              <th>Riesgo venc.</th>
            </tr>
          </thead>
          <tbody>
            ${(lotes || []).map(l => `
              <tr>
                <td>${l.lote || '—'}</td>
                <td>${l.fecha_caducidad || '—'}</td>
                <td>${(l.dias_a_caducar ?? '—')}</td>
                <td>${isBio ? (l.stock_frascos ?? '—') : (l.stock_unidades ?? '—')}</td>
                <td>${badge(l.nivel_vencimiento)}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      `;
    };

    tblRecomendaciones.querySelectorAll('.rec-row').forEach(tr => {
      tr.addEventListener('click', () => {
        const tipo = tr.dataset.tipo;
        const item = tr.dataset.item;
        if (!_lastRec) return;

        if (tipo === 'BIO') {
          const bioSel = (_lastRec.biologicos_riesgo || []).find(x =>
            String(x.vacuna).toUpperCase() === String(item).toUpperCase()
          );
          renderLotes(`BIO: ${item}`, bioSel?.lotes || [], true);
        } else {
          const insSel = (_lastRec.insumos_riesgo || []).find(x =>
            String(x.categoria).toUpperCase() === String(item).toUpperCase()
          );
          renderLotes(`INS: ${item}`, insSel?.lotes || [], false);
        }
      });
    });
  };

  const buildPredictBody = () => ({
    // periodo base del módulo predicción (no el de panorama)
    periodo: normalizePeriodoYM(predState.periodo_base),
    vacuna: state.vacuna || null,
    parroquia: state.parroquia || null,
    fecha_desde: state.fecha_desde || null,
    fecha_hasta: state.fecha_hasta || null,
    // NUEVO: horizonte en meses
    horizon_m: predState.horizon_m,
    window_days: 180
  });

  const loadPredict = async () => {
    if (state.fecha_desde && state.fecha_hasta && state.fecha_desde === state.fecha_hasta) return;

    const body = buildPredictBody();
    const key = JSON.stringify(body);

    let out = null;
    if (stateUI.predictCacheKey === key && stateUI.predictCacheOut) {
      out = stateUI.predictCacheOut;
    } else {
      out = await fetchJSON(API.predict, { method: 'POST', body: JSON.stringify(body) });
      if (out && out.ok === true) {
        stateUI.predictCacheKey = key;
        stateUI.predictCacheOut = out;
      }
    }
    if (!out || out.ok !== true) return;

    renderRecomendaciones(out.recomendaciones);

    const pPeople = out.people;
    if (pPeople?.next !== undefined && kpiPred) kpiPred.textContent = safeText(pPeople.next);
    if (pPeople?.label !== undefined && kpiPredSub) kpiPredSub.textContent = safeText(pPeople.label);

    await plotForecast(PLOTS.predPeople, out.people, 'Proyección de personas vacunadas');
    //await renderInsumosEstimados(out);
    await renderInsumosForecastSplit(out);

    const topEl = document.getElementById(PLOTS.predBioTop);
    if (topEl) {
      const top = ensureArray(out?.pred_bio_top);
      const x = top.map(r => r.vacuna);
      const y = top.map(r => Number(r.pred_dosis || 0));
      const next = out?.next_label || 'Próximo mes';

      if (x.length) {
        await Plotly.newPlot(PLOTS.predBioTop, [
          barTraceMulticolor({ x, y, hovertemplate: '%{x}<br>Dosis (proyección): %{y}<extra></extra>' })
        ], {
          ...baseLayout(),
          height: plotHeightFor(PLOTS.predBioTop),
          margin: { t: 90, r: 12, b: 96, l: 64 },
          title: { text: `Vacunas con mayor demanda para — ${next}` },
          xaxis: { ...(baseLayout().xaxis || {}), title: { text: 'Vacuna' }, tickangle: -25 },
          yaxis: { ...(baseLayout().yaxis || {}), title: { text: 'Cantidad de Dosis' } }
        }, plotConfig);
      } else {
        try { Plotly.purge(topEl); } catch (_) { }
      }
    }

    //await renderJeringasPie(out);
  };

  const warmPredictNonBlocking = () => {
    if (stateUI.predictWarmScheduled) return;
    stateUI.predictWarmScheduled = true;
    setTimeout(() => {
      stateUI.predictWarmScheduled = false;
      loadPredict().catch(() => { });
    }, 0);
  };

  // =========================
  // COMPARE (SIN dimensión)
  // - Mantiene pltCompDim / pltCompDrivers
  // - Render opcional de gráficos fijos si existen sus contenedores
  // =========================


  function fmtPeriod(p) {
    return (p || '').toString().trim(); // ya tienes 'YYYY-MM' normalmente
  }

  function setTitleWithAB(titleElOrId, periodoA, periodoB) {
    const el = (typeof titleElOrId === 'string') ? document.getElementById(titleElOrId) : titleElOrId;
    if (!el) return;

    const base = el.getAttribute('data-title-base') || el.textContent.trim() || '';
    const a = fmtPeriod(periodoA);
    const b = fmtPeriod(periodoB);

    // fallback si falta algo
    const suffix = (a && b) ? ` — ${a} vs ${b}` : (a ? ` — ${a}` : '');

    el.textContent = base + suffix;
  }

  function setCompareTitles(periodoA, periodoB) {
    setTitleWithAB('tCompTopVacunas', periodoA, periodoB);
    setTitleWithAB('tCompDrivers', periodoA, periodoB);
    setTitleWithAB('tCompEsquema', periodoA, periodoB);
    setTitleWithAB('tCompSexo', periodoA, periodoB);
    setTitleWithAB('tCompRiesgo', periodoA, periodoB);
    setTitleWithAB('tCompEdad', periodoA, periodoB);
    setTitleWithAB('tCompParroquia', periodoA, periodoB);
  }

  const fmtDelta = (a, b) => {
    const A = Number(a || 0);
    const B = Number(b || 0);
    const d = A - B;
    const pct = (B === 0) ? null : (d / B) * 100;
    const sign = (d > 0) ? '+' : '';
    const dTxt = `${sign}${nFmt(d)}`;
    const pctTxt = (pct === null || !Number.isFinite(pct)) ? '—' : pctFmt(pct, 1);
    return { A, B, d, dTxt, pctTxt };
  };

  const setKpiLabel = (elVal, title) => {
    const card = elVal?.closest?.('.kpi-card') || elVal?.parentElement;
    const lbl = card?.querySelector?.('.kpi-label');
    if (lbl && title) lbl.textContent = title;
  };

  const renderCompareKPIs = (cmp) => {
    const a = cmp?.a?.kpis || {};
    const b = cmp?.b?.kpis || {};
    const labelA = cmp?.meta?.label_a || 'A';
    const labelB = cmp?.meta?.label_b || 'B';


    const paint = (elVal, elSub, title, A, B) => {
      const d = fmtDelta(A, B);
      setKpiLabel(elVal, title);
      if (elVal) elVal.textContent = `${d.dTxt} (${d.pctTxt})`;
      if (elSub) elSub.textContent = `${labelA}: ${nFmt(d.A)} • ${labelB}: ${nFmt(d.B)}`;
    };

    paint(
      kpiCompDosis, kpiCompDosisSub,
      `Diferencia de dosis válidas (${labelA} vs ${labelB})`,
      a.dosis_validas, b.dosis_validas
    );
    paint(
      kpiCompPersonas, kpiCompPersonasSub,
      `Diferencia de personas únicas (${labelA} vs ${labelB})`,
      a.personas_unicas, b.personas_unicas
    );
    paint(
      kpiCompValidos, kpiCompValidosSub,
      `Diferencia de registros válidos (${labelA} vs ${labelB})`,
      a.reg_validos, b.reg_validos
    );
    paint(
      kpiCompInvalidos, kpiCompInvalidosSub,
      `Diferencia de inválidos/conflictos (${labelA} vs ${labelB})`,
      a.reg_invalidos, b.reg_invalidos
    );
  };

  const renderCompareTopDim = async (cmp) => {
    const el = document.getElementById(PLOTS.compDim);
    if (!el) return;

    const labelA = cmp?.meta?.label_a || 'A';
    const labelB = cmp?.meta?.label_b || 'B';

    const top = ensureArray(cmp?.series?.top_dim);
    const x = top.map(r => r.key);
    const yA = top.map(r => Number(r.total_a || 0));
    const yB = top.map(r => Number(r.total_b || 0));

    await Plotly.newPlot(PLOTS.compDim, [
      { type: 'bar', name: `${labelA}`, x, y: yA, hovertemplate: `%{x}<br>${labelA}: %{y}<extra></extra>` },
      { type: 'bar', name: `${labelB}`, x, y: yB, hovertemplate: `%{x}<br>${labelB}: %{y}<extra></extra>` }
    ], {
      ...baseLayout(),
      height: plotHeightFor(PLOTS.compDim),
      barmode: 'group',
      margin: { t: 18, r: 20, b: 125, l: 70 },          // +b por labels largos
      xaxis: { ...(baseLayout().xaxis || {}), title: { text: 'Vacuna (ítem)' }, tickangle: -35 },
      yaxis: { ...(baseLayout().yaxis || {}), title: { text: 'Dosis válidas' } },
      legend: { orientation: 'h', y: -0.35, x: 0 }      // baja más la leyenda
    }, plotConfig);

  };

  const renderCompareWaterfall = async (cmp) => {
    const el = document.getElementById(PLOTS.compDrivers);
    if (!el) return;

    const labelA = cmp?.meta?.label_a || 'A';
    const labelB = cmp?.meta?.label_b || 'B';

    const wf = ensureArray(cmp?.series?.drivers_waterfall);
    const keys = wf.map(r => r.key);
    const deltas = wf.map(r => Number(r.delta || 0));

    if (!keys.length) { try { Plotly.purge(el); } catch (_) { } return; }

    const total = deltas.reduce((acc, v) => acc + v, 0);
    const x = [...keys, 'TOTAL'];
    const y = [...deltas, total];
    const measures = [...deltas.map(() => 'relative'), 'total'];

    await Plotly.newPlot(PLOTS.compDrivers, [{
      type: 'waterfall',
      x, y,
      measure: measures,
      increasing: { marker: { color: '#22c55e' } },
      decreasing: { marker: { color: '#ef4444' } },
      totals: { marker: { color: '#3b82f6' } },
      connector: { line: { color: 'rgba(255,255,255,0.20)' } },
      hovertemplate: '%{x}<br>Diferencia (A vs B): %{y}<extra></extra>'
    }], {
      ...baseLayout(),
      height: plotHeightFor(PLOTS.compDrivers),
      margin: { t: 18, r: 20, b: 125, l: 80 },
      xaxis: { ...(baseLayout().xaxis || {}), title: { text: 'Vacuna (ítem)' }, tickangle: -35 },
      yaxis: { ...(baseLayout().yaxis || {}), title: { text: `Diferencia (${labelA} - ${labelB})` } },
      showlegend: false
    }, plotConfig);

  };

  const renderCompareDualDonut = async (plotId, title, aLabel, bLabel, rows) => {
    const el = document.getElementById(plotId);
    if (!el) return;

    const data = ensureArray(rows);
    if (!data.length) { try { Plotly.purge(el); } catch (_) { } return; }

    const isRisk = (plotId === PLOTS.compRiesgo);

    // labels (solo riesgo truncado)
    const shortLabel = (s, max = 30) => {
      const t = String(s || '').trim();
      return (t.length <= max) ? t : (t.slice(0, max - 1) + '…');
    };

    const labels = data.map(r => isRisk ? shortLabel(r.key, 30) : r.key);
    const valA = data.map(r => Number(r.total_a || 0));
    const valB = data.map(r => Number(r.total_b || 0));

    // ===== DOMAINS =====
    // Riesgo: horizontal y corrido a la derecha
    // Default: horizontal clásico (dos donuts)
    const domA = isRisk
      ? { x: [0.26, 0.62], y: [0.10, 0.95] }   // <- más a la derecha
      : { x: [0.00, 0.48], y: [0.05, 0.95] };

    const domB = isRisk
      ? { x: [0.64, 0.98], y: [0.10, 0.95] }   // <- más a la derecha
      : { x: [0.52, 1.00], y: [0.05, 0.95] };

    // ===== LEGEND =====
    const legend = isRisk
      ? { orientation: 'v', x: 0.02, y: 0.98, xanchor: 'left', yanchor: 'top', bgcolor: 'rgba(0,0,0,0)', font: { size: 11 } }
      : { orientation: 'h', y: -0.15 };

    // ===== ANNOTATIONS (centros) =====
    const annotations = isRisk
      ? [
        { text: aLabel, x: 0.44, y: 0.52, showarrow: false, font: { size: 12, color: '#e6eefc' } },
        { text: bLabel, x: 0.81, y: 0.52, showarrow: false, font: { size: 12, color: '#e6eefc' } }
      ]
      : [
        { text: aLabel, x: 0.24, y: 0.5, showarrow: false, font: { size: 12, color: '#e6eefc' } },
        { text: bLabel, x: 0.76, y: 0.5, showarrow: false, font: { size: 12, color: '#e6eefc' } }
      ];

    // ===== MARGINS =====
    const margin = isRisk
      ? { t: 56, r: 20, b: 20, l: 10 }   // deja espacio a la leyenda a la izquierda
      : { t: 70, r: 20, b: 20, l: 20 };  // baja un poco donuts en esquema/sexo

    await Plotly.newPlot(plotId, [
      {
        type: 'pie',
        labels,
        values: valA,
        hole: 0.55,
        name: aLabel,
        sort: false,
        textinfo: 'percent',
        textposition: 'inside',
        domain: domA,
        marker: { colors: pickColors(labels.length) },
        hovertemplate: `%{label}<br>${aLabel}: %{value}<extra></extra>`
      },
      {
        type: 'pie',
        labels,
        values: valB,
        hole: 0.55,
        name: bLabel,
        sort: false,
        textinfo: 'percent',
        textposition: 'inside',
        domain: domB,
        marker: { colors: pickColors(labels.length) },
        hovertemplate: `%{label}<br>${bLabel}: %{value}<extra></extra>`
      }
    ], {
      ...pieLayoutBase(),
      height: plotHeightFor(plotId),
      margin,
      annotations,      // aquí van (con :)
      showlegend: true,
      legend
    }, { ...plotConfig, displayModeBar: false });
  };



  const renderCompareEdadLines = async (cmp) => {
    const el = document.getElementById(PLOTS.compEdad);
    if (!el) return;

    const labelA = cmp?.meta?.label_a || 'A';
    const labelB = cmp?.meta?.label_b || 'B';

    const rows = ensureArray(cmp?.series?.edad_bins);
    if (!rows.length) { try { Plotly.purge(el); } catch (_) { } return; }

    const x = rows.map(r => r.key);
    const yA = rows.map(r => Number(r.total_a || 0));
    const yB = rows.map(r => Number(r.total_b || 0));

    await Plotly.newPlot(PLOTS.compEdad, [
      { type: 'scatter', mode: 'lines+markers', name: labelA, x, y: yA, hovertemplate: `%{x}<br>${labelA}: %{y}<extra></extra>` },
      { type: 'scatter', mode: 'lines+markers', name: labelB, x, y: yB, hovertemplate: `%{x}<br>${labelB}: %{y}<extra></extra>` }
    ], {
      ...baseLayout(),
      height: plotHeightFor(PLOTS.compEdad),
      margin: { t: 56, r: 12, b: 80, l: 64 },
      xaxis: { ...(baseLayout().xaxis || {}), title: { text: 'Rango de edad (años)' } },
      yaxis: { ...(baseLayout().yaxis || {}), title: { text: 'Dosis válidas' } },
      legend: { orientation: 'h', y: -0.25 }
    }, plotConfig);
  };

  const renderCompareParroquiaDot = async (cmp) => {
    const el = document.getElementById(PLOTS.compParroquia);
    if (!el) return;

    const labelA = cmp?.meta?.label_a || 'A';
    const labelB = cmp?.meta?.label_b || 'B';

    const rows = ensureArray(cmp?.series?.parroquia_top);
    if (!rows.length) { try { Plotly.purge(el); } catch (_) { } return; }

    const y = rows.map(r => r.key);
    const xA = rows.map(r => Number(r.total_a || 0));
    const xB = rows.map(r => Number(r.total_b || 0));

    await Plotly.newPlot(PLOTS.compParroquia, [
      { type: 'scatter', mode: 'markers', name: labelA, x: xA, y, hovertemplate: `%{y}<br>${labelA}: %{x}<extra></extra>`, marker: { size: 10 } },
      { type: 'scatter', mode: 'markers', name: labelB, x: xB, y, hovertemplate: `%{y}<br>${labelB}: %{x}<extra></extra>`, marker: { size: 10 } }
    ], {
      ...baseLayout(),
      height: plotHeightFor(PLOTS.compParroquia),
      margin: { t: 56, r: 12, b: 60, l: 200 },
      xaxis: { ...(baseLayout().xaxis || {}), title: { text: 'Dosis válidas' } },
      yaxis: { ...(baseLayout().yaxis || {}), title: { text: 'Parroquia' } },
      legend: { orientation: 'h', y: -0.25 }
    }, plotConfig);
  };

  const renderCompareFixedCharts = async (cmp) => {
    const labelA = cmp?.meta?.label_a || 'A';
    const labelB = cmp?.meta?.label_b || 'B';

    await renderCompareDualDonut(
      PLOTS.compEsquemas,
      `Distribución por esquema — ${labelA} vs ${labelB}`,
      labelA, labelB,
      cmp?.series?.esquemas
    );

    await renderCompareDualDonut(
      PLOTS.compRiesgo,
      `Distribución por grupo de riesgo — ${labelA} vs ${labelB}`,
      labelA, labelB,
      cmp?.series?.riesgo,
      { mode: 'risk' } // SOLO aquí
    );


    await renderCompareDualDonut(
      PLOTS.compSexo,
      `Distribución por sexo — ${labelA} vs ${labelB}`,
      labelA, labelB,
      cmp?.series?.sexo
    );

    await renderCompareEdadLines(cmp);
    await renderCompareParroquiaDot(cmp);
  };

  const loadCompare = async () => {
    const pa = selPeriodoA?.value || '';
    const pb = selPeriodoB?.value || '';

    if (!pa || !pb) return;

    // Validación mínima (evita comparar el mismo periodo)
    if (pa === pb) {
      throw new Error('Periodo A y Periodo B no pueden ser iguales');
    }

    // SIN dimensión: solo 2 params
    const body = { periodo_a: pa, periodo_b: pb };

    const out = await fetchJSON(API.compare, {
      method: 'POST',
      body: JSON.stringify(body)
    });

    if (!out || out.ok !== true) throw new Error('compare ok=false');

    renderCompareKPIs(out);
    setCompareTitles(body.periodo_a, body.periodo_b);
    await renderCompareTopDim(out);
    await renderCompareWaterfall(out);
    await renderCompareFixedCharts(out);

    resizeAll();
  };


  // =========================
  // INIT
  // =========================
  const loadInit = async () => {
    setMsg('Cargando dashboard...');
    const init = await fetchJSON(API.init, { method: 'GET' });
    stateUI.init = init;

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

    // ===== Predicción: llenar periodos
    if (selPredPeriodo) {
      selPredPeriodo.innerHTML = '';
      (init?.periodos || []).forEach(p => {
        const opt = document.createElement('option');
        opt.value = p;
        opt.textContent = p;
        selPredPeriodo.appendChild(opt);
      });

      // default: el mismo periodo_default del init, si existe
      const defP = init?.periodo_default ? String(init.periodo_default) : (periodos[0] || '');
      if (defP && [...selPredPeriodo.options].some(o => o.value === defP)) {
        selPredPeriodo.value = defP;
        predState.periodo_base = defP;
      } else {
        predState.periodo_base = selPredPeriodo.value || '';
      }
    }

    // default horizonte
    if (selPredHorizon) {
      const hv = Number(selPredHorizon.value || 1);
      predState.horizon_m = Number.isFinite(hv) ? hv : 1;
    }


    const periodos = Array.isArray(init?.periodos) ? init.periodos : [];
    if (selPeriodoA) {
      selPeriodoA.innerHTML = '';
      periodos.forEach(p => {
        const opt = document.createElement('option');
        opt.value = p;
        opt.textContent = p;
        selPeriodoA.appendChild(opt);
      });
    }
    if (selPeriodoB) {
      selPeriodoB.innerHTML = '';
      periodos.forEach(p => {
        const opt = document.createElement('option');
        opt.value = p;
        opt.textContent = p;
        selPeriodoB.appendChild(opt);
      });
    }

    const defA = init?.periodo_default ? String(init.periodo_default) : (periodos[0] || '');
    if (selPeriodoA && defA && [...selPeriodoA.options].some(o => o.value === defA)) selPeriodoA.value = defA;

    let defB = '';
    if (periodos.length >= 2) {
      const idxA = periodos.findIndex(x => String(x) === String(defA));
      defB = (idxA >= 0 && idxA + 1 < periodos.length) ? periodos[idxA + 1] : periodos[1];
    } else {
      defB = defA;
    }
    if (selPeriodoB && defB && [...selPeriodoB.options].some(o => o.value === defB)) selPeriodoB.value = defB;

    // años para anual
    const years = [...new Set((periodos || [])
      .map(p => String(p || '').slice(0, 4))
      .filter(y => /^\d{4}$/.test(y))
    )].sort((a, b) => Number(b) - Number(a));

    if (selAnio) {
      selAnio.innerHTML = '';
      years.forEach(y => {
        const opt = document.createElement('option');
        opt.value = y;
        opt.textContent = y;
        selAnio.appendChild(opt);
      });

      const defYear = String(init?.periodo_default || '').slice(0, 4);
      if (defYear && years.includes(defYear)) selAnio.value = defYear;
      else if (years[0]) selAnio.value = years[0];
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

    if (lotDetail) setLotEmpty();
  };

  // =========================
  // DATA
  // =========================
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

  const resetFiltrosInteractivos = (mostrarMsg = true) => {
    state.vacuna = '';
    state.esquema = '';
    state.fecha_desde = null;
    state.fecha_hasta = null;
    state.parroquia = '';

    if (selVacuna) selVacuna.value = '';
    if (selEsquema) selEsquema.value = '';

    if (mostrarMsg) {
      setMsg('Filtros reseteados');
      setTimeout(() => setMsg(''), 900);
    }

    if (lotDetail) setLotEmpty();
  };

  // =========================
  // PREDICCION titulos dinámicos
  // =========================

  function setPredTitles(periodoBase, horizonM) {
    const p = String(periodoBase || '').trim();
    const h = Number(horizonM || 1);

    const span = (h === 1) ? 'Proximo mes' : ` Proximos ${h} meses`;
    const suffix = (p ? `— Desde ${p} • Hasta  ${span}` : `— Hasta ${span}`);

    const apply = (el) => {
      if (!el) return;
      const base = el.getAttribute('data-title-base') || el.textContent || '';
      el.textContent = `${base} ${suffix}`.trim();
    };

    apply(tPredPersonas);
    apply(tPredBioTop);
    apply(tPredInsumos);
  }

  // =========================
  // ANUAL titulos dinámicos
  // =========================

  function setAnualTitles(year) {
    const y = String(year || '').trim();
    const set = (id) => {
      const el = document.getElementById(id);
      if (!el) return;
      const base = el.getAttribute('data-title-base') || '';
      el.textContent = y ? `${base} — ${y}` : base;
    };

    [
      'tAnualMain', 'tAnualCalidad', 'tAnualKPIs', 'tAnualTopVac',
      'tAnualDosisMes', 'tAnualPersonasMes', 'tAnualEsquema', 'tAnualTopMes',
      'tAnualInsumosLinea', 'tAnualInsumosKPIs'
    ].forEach(set);
  }


  const renderAnual = async (out) => {
    const year = out?.meta?.year || '';
    const k = out?.kpis || {};
    const cal = out?.calidad || {};

    // ===== KPIs (columna derecha fila 1)
    const dosis = Number(k.dosis_validas || 0);
    const personas = Number(k.personas_unicas || 0);

    const peakMes = String(k.peak_mes || '');
    const peakTotal = Number(k.peak_total_dosis || 0);
    const peakPct = (k.peak_pct_vs_prom_otros === null || k.peak_pct_vs_prom_otros === undefined)
      ? null
      : Number(k.peak_pct_vs_prom_otros);

    // ids (de tu HTML nuevo)
    const kpiAnualDosis = document.getElementById('kpiAnualDosis');
    const kpiAnualDosisSub = document.getElementById('kpiAnualDosisSub');
    const kpiAnualPersonas = document.getElementById('kpiAnualPersonas');
    const kpiAnualPersonasSub = document.getElementById('kpiAnualPersonasSub');
    const kpiAnualPeak = document.getElementById('kpiAnualPeak');
    const kpiAnualPeakSub = document.getElementById('kpiAnualPeakSub');

    if (kpiAnualDosis) kpiAnualDosis.textContent = nFmt(dosis);
    if (kpiAnualDosisSub) kpiAnualDosisSub.textContent = year ? `Año ${year}` : 'Año';

    if (kpiAnualPersonas) kpiAnualPersonas.textContent = nFmt(personas);
    if (kpiAnualPersonasSub) kpiAnualPersonasSub.textContent = year ? `Año ${year}` : 'Año';



    if (kpiAnualPeak) {
      const mensualArr = ensureArray(out?.mensual);
      let picoMes = null;
      let picoVal = -1;
      mensualArr.forEach(r => {
        const val = Number(r.total || 0);
        if (val > picoVal) { picoVal = val; picoMes = String(r.mes || '').padStart(2, '0'); }
      });

      const meses = [
        'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
        'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
      ];

      const peakMesNum = Number(peakMes);
      const picoNombre =
        Number.isFinite(peakMesNum) && peakMesNum >= 1 && peakMesNum <= 12
          ? meses[peakMesNum - 1]
          : '—';

      //if (elPeak) elPeak.textContent = (picoMes ? `${picoNombre} (${fmtInt(picoVal)})` : '—');
      //const pctTxt = (peakPct === null || !Number.isFinite(peakPct)) ? '—' : pctFmt(peakPct, 1);
      kpiAnualPeak.textContent = peakMes ? `${peakMes} (${nFmt(peakTotal)})` : '—';
      if (kpiAnualPeakSub) kpiAnualPeakSub.textContent = year ? `${picoNombre} / Año ${year}` : 'Año';
    }

    // ===== Calidad (columna izquierda fila 1) -> donut % válidos
    {
      const el = document.getElementById(PLOTS.anualCalidad);
      if (el) {
        const pctValid = Number(cal.pct_validos || 0);
        const inv = Number(cal.invalidos_conflictos || 0); // si no hay, queda 0
        const val = Number(cal.validos || 0);

        // Donut: válido vs restante (si no hay invalidos, igual se ve 100/0)
        await Plotly.newPlot(PLOTS.anualCalidad, [{
          type: 'pie',
          labels: ['Válidos', 'Otros'],
          values: [val, inv],
          hole: 0.58,
          sort: false,
          textinfo: 'percent',
          marker: { colors: ['#22c55e', 'rgba(255,255,255,.10)'] },
          hovertemplate: '%{label}<br>%{value}<extra></extra>'
        }], {
          ...pieLayoutBase(),
          height: plotHeightFor(PLOTS.anualCalidad),
          margin: { t: 56, r: 30, b: 20, l: 30 },
          //title: { text: `Calidad de registros válidos — ${year}`, x: 0, xanchor: 'left', font: { size: 13 } },
          annotations: [
            { text: `${pctValid.toFixed(1)}%`, x: 0.5, y: 0.5, showarrow: false, font: { size: 18, color: '#e6eefc' } }
          ],
          showlegend: true,
          legend: { orientation: 'h', y: -0.15 }
        }, { ...plotConfig, displayModeBar: false });
      }
    }

    // ===== Top vacunas anual (ancho completo)
    {
      const top = ensureArray(out?.vacunas_top_anual);
      const x = top.map(r => r.vacuna);
      const y = top.map(r => Number(r.total || 0));

      const el = document.getElementById(PLOTS.anualTopVac);
      if (el) {
        if (!x.length) { try { Plotly.purge(el); } catch (_) { } }
        else {
          await Plotly.newPlot(PLOTS.anualTopVac, [
            barTraceMulticolor({ x, y, hovertemplate: '%{x}<br>%{y}<extra></extra>' })
          ], {
            ...baseLayout(),
            height: plotHeightFor(PLOTS.anualTopVac),
            margin: { t: 56, r: 12, b: 96, l: 64 },
            //title: { text: `Top vacunas anual (dosis) — ${year}`, x: 0, xanchor: 'left', font: { size: 13 } },
            xaxis: { ...(baseLayout().xaxis || {}), title: { text: 'Vacuna' }, tickangle: -25 },
            yaxis: { ...(baseLayout().yaxis || {}), title: { text: 'Dosis' } }
          }, plotConfig);
        }
      }
    }

    // ===== Dosis por mes (línea + área)
    {
      const rows = ensureArray(out?.mensual_dosis);
      const x = rows.map(r => `${year}-${r.mes}`);
      const y = rows.map(r => Number(r.total || 0));

      const el = document.getElementById(PLOTS.anualDosisMes);
      if (el) {
        if (!x.length) { try { Plotly.purge(el); } catch (_) { } }
        else {
          await Plotly.newPlot(PLOTS.anualDosisMes, [{
            type: 'scatter',
            mode: 'lines',
            x, y,
            fill: 'tozeroy',
            hovertemplate: '%{x}<br>%{y}<extra></extra>'
          }], {
            ...baseLayout(),
            height: plotHeightFor(PLOTS.anualDosisMes),
            margin: { t: 56, r: 12, b: 80, l: 64 },
            //title: { text: `Dosis totales por mes — ${year}`, x: 0, xanchor: 'left', font: { size: 13 } },
            xaxis: { ...(baseLayout().xaxis || {}), title: { text: 'Mes' }, type: 'category', tickangle: -35 },
            yaxis: { ...(baseLayout().yaxis || {}), title: { text: 'Dosis' } }
          }, plotConfig);
        }
      }
    }

    // ===== Personas por mes (barras)
    {
      const rows = ensureArray(out?.mensual_personas);
      const x = rows.map(r => `${year}-${r.mes}`);
      const y = rows.map(r => Number(r.total || 0));

      const el = document.getElementById(PLOTS.anualPersonasMes);
      if (el) {
        if (!x.length) { try { Plotly.purge(el); } catch (_) { } }
        else {
          await Plotly.newPlot(PLOTS.anualPersonasMes, [
            barTraceMulticolor({ x, y, hovertemplate: '%{x}<br>%{y}<extra></extra>' })
          ], {
            ...baseLayout(),
            height: plotHeightFor(PLOTS.anualPersonasMes),
            margin: { t: 56, r: 12, b: 80, l: 64 },
            //title: { text: `Personas vacunadas por mes — ${year}`, x: 0, xanchor: 'left', font: { size: 13 } },
            xaxis: { ...(baseLayout().xaxis || {}), title: { text: 'Mes' }, type: 'category', tickangle: -35 },
            yaxis: { ...(baseLayout().yaxis || {}), title: { text: 'Personas' } }
          }, plotConfig);
        }
      }
    }

    // ===== Esquemas (barra horizontal recomendada por nombres largos)
    {
      const rows = ensureArray(out?.esquemas);
      const y = rows.map(r => r.esquema);
      const x = rows.map(r => Number(r.total || 0));

      const el = document.getElementById(PLOTS.anualEsquemas);
      if (el) {
        if (!y.length) { try { Plotly.purge(el); } catch (_) { } }
        else {
          const colors = pickColors(y.length);

          await Plotly.newPlot(PLOTS.anualEsquemas, [{
            type: 'bar',
            orientation: 'h',
            x, y,
            marker: { color: colors },   // <-- clave
            hovertemplate: '%{y}<br>%{x}<extra></extra>'
          }], {
            ...baseLayout(),
            height: plotHeightFor(PLOTS.anualEsquemas),
            margin: { t: 56, r: 12, b: 50, l: 220 },
            //title: { text: `Totales por esquema — ${year}`, x: 0, xanchor: 'left', font: { size: 13 } },
            xaxis: { ...(baseLayout().xaxis || {}), title: { text: 'Dosis' } },
            yaxis: { ...(baseLayout().yaxis || {}), title: { text: 'Esquema' } }
          }, plotConfig);
        }
      }
    }


    // ===== Top vacuna por mes (Top1) barras + etiqueta vacuna en hover
    {
      const rows = ensureArray(out?.top_vacuna_por_mes);
      const x = rows.map(r => `${year}-${r.mes}`);
      const y = rows.map(r => Number(r.total || 0));
      const hover = rows.map(r => `${r.vacuna}`);

      const el = document.getElementById(PLOTS.anualTopMes);
      if (el) {
        if (!x.length) { try { Plotly.purge(el); } catch (_) { } }
        else {
          const colors = pickColors(x.length);

          await Plotly.newPlot(PLOTS.anualTopMes, [{
            type: 'bar',
            x, y,
            marker: { color: colors },   // <-- clave
            customdata: hover,
            hovertemplate: '%{x}<br>%{customdata}<br>%{y}<extra></extra>'
          }], {
            ...baseLayout(),
            height: plotHeightFor(PLOTS.anualTopMes),
            margin: { t: 56, r: 12, b: 80, l: 64 },
            //title: { text: `Vacuna líder por mes (Top 1) — ${year}`, x: 0, xanchor: 'left', font: { size: 13 } },
            xaxis: { ...(baseLayout().xaxis || {}), title: { text: 'Mes' }, type: 'category', tickangle: -35 },
            yaxis: { ...(baseLayout().yaxis || {}), title: { text: 'Dosis (vacuna líder)' } }
          }, plotConfig);
        }
      }
    }


    // ===== Insumos mensual: jeringas y guantes (línea + área)
    {
      const rows = ensureArray(out?.insumos_mensual);
      const x = rows.map(r => `${year}-${r.mes}`);
      const yJ = rows.map(r => Number(r.jeringas || 0));
      const yG = rows.map(r => Number(r.guantes || 0));

      const el = document.getElementById(PLOTS.anualInsumosMes);
      if (el) {
        if (!x.length) { try { Plotly.purge(el); } catch (_) { } }
        else {
          await Plotly.newPlot(PLOTS.anualInsumosMes, [
            {
              type: 'scatter', mode: 'lines', name: 'Jeringas', x, y: yJ, fill: 'tozeroy',
              hovertemplate: '%{x}<br>Jeringas: %{y}<extra></extra>'
            },
            {
              type: 'scatter', mode: 'lines', name: 'Guantes', x, y: yG, fill: 'tozeroy',
              hovertemplate: '%{x}<br>Guantes: %{y}<extra></extra>'
            }
          ], {
            ...baseLayout(),
            height: plotHeightFor(PLOTS.anualInsumosMes),
            margin: { t: 56, r: 12, b: 80, l: 64 },
            //title: { text: `Insumos mensuales estimados — ${year}`, x: 0, xanchor: 'left', font: { size: 13 } },
            xaxis: { ...(baseLayout().xaxis || {}), title: { text: 'Mes' }, type: 'category', tickangle: -35 },
            yaxis: { ...(baseLayout().yaxis || {}), title: { text: 'Unidades' } },
            legend: { orientation: 'h', y: -0.25 }
          }, plotConfig);
        }
      }

      // KPIs algodón + alcohol
      const ik = out?.insumos_kpis || {};
      const rollos = Number(ik.algodon_rollos || 0);
      const litros = Number(ik.alcohol_litros_total || 0);
      const ml = Number(ik.alcohol_ml_total || 0);
      const dpr = Number(ik.dosis_por_rollo || 0);
      const mlpd = Number(ik.ml_alcohol_por_dosis || 0);

      const kpiAlg = document.getElementById('kpiAnualAlgodon');
      const kpiAlgSub = document.getElementById('kpiAnualAlgodonSub');
      const kpiAlcL = document.getElementById('kpiAnualAlcoholL');
      const kpiAlcSub = document.getElementById('kpiAnualAlcoholSub');

      if (kpiAlg) kpiAlg.textContent = nFmt(rollos);
      //if (kpiAlgSub) kpiAlgSub.textContent = dpr ? `Regla: 1 rollo / ${nFmt(dpr)} dosis` : '—';

      if (kpiAlcL) kpiAlcL.textContent = `${litros.toFixed(3)} L`;
      //if (kpiAlcSub) kpiAlcSub.textContent = `${ml.toFixed(2)} ml (Regla: ${mlpd} ml/dosis)`;
    }

    resizeAll();
  };


  const loadAnual = async () => {
    const year = selAnio?.value ? Number(selAnio.value) : null;
    const body = { year };

    const out = await fetchJSON(API.anual, { method: 'POST', body: JSON.stringify(body) });
    if (!out || out.ok !== true) throw new Error('dashboard_anual ok=false');

    setAnualTitles(out?.meta?.year);
    await renderAnual(out);
  };


  // =========================
  // REFRESH
  // =========================
  let _refreshRunning = false;
  let _refreshPending = false;

  const refreshCurrent = async () => {
    if (_refreshRunning) { _refreshPending = true; return; }
    _refreshRunning = true;
    try {
      do {
        _refreshPending = false;
        setMsg('Actualizando...');
        if (stateUI.tab === 'comparativos') await loadCompare();
        else if (stateUI.tab === 'prediccion') { await loadData(); await loadPredict(); }
        else if (stateUI.tab === 'anual') await loadAnual();
        else { await loadData(); await loadInsumosEstimadosPanorama(); }
        setMsg('');
        resizeAll();
      } while (_refreshPending);
    } catch (err) {
      console.error(err);
      setMsg(`Sin datos al filtrar. ${err?.message || ''}`.trim(), 'err');
    } finally {
      _refreshRunning = false;
    }
  };


  // =========================
  // UI
  // =========================
  const bindUI = () => {
    if (menuSecciones) {
      menuSecciones.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
          const t = btn.dataset.tab || 'panorama';
          setTab(t);

        });
      });
    }

    selPeriodo?.addEventListener('change', () => {
      state.periodo = selPeriodo.value || '';
      state.fecha_desde = null;
      state.fecha_hasta = null;
      refreshCurrent();
      warmPredictNonBlocking();
    });

    selVacuna?.addEventListener('change', () => {
      state.vacuna = selVacuna.value || '';
      refreshCurrent();
      warmPredictNonBlocking();
    });

    selEsquema?.addEventListener('change', () => {
      state.esquema = selEsquema.value || '';
      refreshCurrent();
      warmPredictNonBlocking();
    });

    btnReset?.addEventListener('click', () => {
      resetFiltrosInteractivos(true);
      refreshCurrent();
      warmPredictNonBlocking();
    });

    selPredPeriodo?.addEventListener('change', () => {
      predState.periodo_base = selPredPeriodo.value || '';
      setPredTitles(predState.periodo_base, predState.horizon_m);
      if (stateUI.tab === 'prediccion') refreshCurrent();
    });

    selPredHorizon?.addEventListener('change', () => {
      const hv = Number(selPredHorizon.value || 1);
      predState.horizon_m = Number.isFinite(hv) ? hv : 1;
      setPredTitles(predState.periodo_base, predState.horizon_m);
      if (stateUI.tab === 'prediccion') refreshCurrent();
    });

    btnPredActualizar?.addEventListener('click', () => {
      if (stateUI.tab === 'prediccion') {
        setPredTitles(predState.periodo_base, predState.horizon_m);
        refreshCurrent();
      }
    });


    btnCompActualizar?.addEventListener('click', () => refreshCurrent());

    btnAnualActualizar?.addEventListener('click', () => {
      if (stateUI.tab === 'anual') refreshCurrent();
    });

    selAnio?.addEventListener('change', () => {
      if (stateUI.tab === 'anual') refreshCurrent();
    });

    window.addEventListener('resize', resizeAll);
  };

  (async () => {
    bindUI();
    await loadInit();
    await setTab('panorama');
    warmPredictNonBlocking();
  })();
})();
