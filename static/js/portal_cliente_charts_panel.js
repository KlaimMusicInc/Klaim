// static/js/portal_cliente_charts_panel.js
(() => {
  'use strict';

  // =========================
  // Utilidades y estado
  // =========================
  const fmt = new Intl.NumberFormat('es-CO', {
    style: 'currency', currency: 'USD', maximumFractionDigits: 2,
  });

  // Mapa de instancias Chart vivas por id de canvas
  const CHARTS = Object.create(null);

  // Registro seguro del plugin DataLabels (si está disponible)
  document.addEventListener('DOMContentLoaded', () => {
    if (window.Chart && window.ChartDataLabels) {
      try { Chart.register(window.ChartDataLabels); } catch (_) {}
    }
  });

  const raf = () => new Promise(r => requestAnimationFrame(r));
  const raf2 = async () => { await raf(); await raf(); };

  // Paleta basada en variables CSS con fallback robusto
  function palette() {
    const cs = getComputedStyle(document.documentElement);
    const val = k => (cs.getPropertyValue(k) || '').trim();
    return [
      val('--primary')        || '#112F6D',
      val('--primary-light')  || '#1A4A9E',
      val('--accent')         || '#4FC3F7',
      val('--success')        || '#058B2D',
      val('--danger')         || '#7E0404',
      '#9CA3AF', '#8B5CF6', '#EC4899', '#06B6D4', '#F59E0B',
    ];
  }
  const colors = n => {
    const base = palette();
    return Array.from({ length: n }, (_, i) => base[i % base.length]);
  };

  // Limpia todas las instancias vivas (antes de reemplazar el panel)
  function destroyAllCharts() {
    for (const id in CHARTS) {
      try { CHARTS[id]?.destroy(); } catch (_) {}
      delete CHARTS[id];
    }
  }

  // Obtiene los ids de todos los canvas de charts dentro del panel
  function getCanvasIds() {
    return Array.from(document.querySelectorAll('#charts-panel .chart-box canvas[id]'))
      .map(el => el.id);
  }

  // Espera fuentes + layout + tamaño real de los canvas
  async function waitForPanelReady() {
    // 1) Fuentes web listas (si el navegador expone document.fonts)
    try { if (document.fonts && document.fonts.ready) await document.fonts.ready; } catch (_) {}
    // 2) Dos RAF para dejar que el grid/estilos se asienten
    await raf2();

    // 3) Verificar que los canvas tengan tamaño real
    const ids = getCanvasIds();
    if (!ids.length) return true;

    for (let i = 0; i < 20; i++) { // ~320ms máx
      const ok = ids.every(id => {
        const el = document.getElementById(id);
        if (!el) return false;
        const { width, height } = el.getBoundingClientRect();
        return width > 10 && height > 10;
      });
      if (ok) return true;
      await new Promise(r => setTimeout(r, 16));
    }
    // Si no logramos tamaño > 0, forzamos un tamaño mínimo para evitar 0×0
    ids.forEach(id => {
      const el = document.getElementById(id);
      if (!el) return;
      const b = el.getBoundingClientRect();
      if (b.width < 10 || b.height < 10) {
        el.setAttribute('width', String(640));
        el.setAttribute('height', String(360));
        el.style.width = '100%';
        el.style.height = '100%';
      }
    });
    return true;
  }

  // =========================
  // Normalización de payload
  // =========================
  const toSeries = (src) => {
    if (!src) return [];
    if (Array.isArray(src)) return src.map(s => ({ label: s.label, value: Number(s.value) || 0 }));
    return Object.entries(src).map(([label, value]) => ({ label, value: Number(value) || 0 }));
  };

  function normalizePayload(raw) {
    // Soporta dos formas:
    //  A) Plana (mecánico legacy): { total_distributed_amount, by_dsp, by_processing_type }
    //  B) Estructurada: { derecho: 'Mecanico'|'MicroSync', mecanico: {...}, microsync: {...} }
    const derecho = (raw && (raw.derecho || raw.mode)) || 'Mecanico';

    if (derecho === 'MicroSync') {
      const m = raw.microsync || raw;
      return {
        mode: 'MicroSync',
        totals: {
          amountPayable: Number(m.total_amount_payable || 0),
          marketShare: Number(m.total_market_share || 0),
        },
        series: {
          byCountry: toSeries(m.by_country),
          byAssetTitle: toSeries(m.by_asset_title),
        }
      };
    } else {
      const m = raw.mecanico || raw;
      return {
        mode: 'Mecanico',
        totals: {
          distributed: Number(m.total_distributed_amount || 0),
        },
        series: {
          byDSP: toSeries(m.by_dsp),
          byProcessing: toSeries(m.by_processing_type || m.by_processing),
        }
      };
    }
  }

  // =========================
  // Render principal de charts
  // =========================
  function renderChartsFromEmbeddedJSON() {
    if (!window.Chart) return;

    const tag = document.getElementById('charts-data');
    if (!tag) return;

    // 1) Lee JSON embebido de forma segura
    let raw = {};
    try { raw = JSON.parse(tag.textContent || '{}'); }
    catch (e) { console.error('JSON charts-data inválido:', e); return; }

    const data = normalizePayload(raw);

    // 2) Estado vacío
    const emptyBox = document.getElementById('charts-empty');
    const isEmptyMec = data.mode === 'Mecanico'
      && !data.totals.distributed
      && !data.series.byDSP.length
      && !data.series.byProcessing.length;
    const isEmptyMs  = data.mode === 'MicroSync'
      && !data.totals.amountPayable
      && !data.totals.marketShare
      && !data.series.byCountry.length
      && !data.series.byAssetTitle.length;
    if (emptyBox) emptyBox.style.display = (isEmptyMec || isEmptyMs) ? 'block' : 'none';

    // 3) Escribe métricas
    // Mecánico
    const metricMec = document.getElementById('metric-total');
    if (metricMec) metricMec.textContent = fmt.format(Number(data.totals.distributed || 0));
    // MicroSync
    const metricMsTotal = document.getElementById('metric-ms-total');
    const metricMsShare = document.getElementById('metric-ms-marketshare');
    if (metricMsTotal) metricMsTotal.textContent = fmt.format(Number(data.totals.amountPayable || 0));
    if (metricMsShare) metricMsShare.textContent = fmt.format(Number(data.totals.marketShare || 0));

    // 4) Creador de donut idempotente
    function donut(id, series) {
      const el = document.getElementById(id);
      if (!el || !series?.length) {
        // Si no existe el canvas o la serie está vacía, destruye cualquier instancia previa
        try { CHARTS[id]?.destroy(); } catch (_) {}
        delete CHARTS[id];
        return;
      }

      const labels = series.map(s => s.label);
      const values = series.map(s => Number(s.value) || 0);
      const bg = colors(labels.length);
      const datalabelColor =
        (getComputedStyle(document.documentElement).getPropertyValue('--dark').trim()) || '#0A1A3A';

      // Destruir instancia previa si existiera
      try { CHARTS[id]?.destroy(); } catch (_) {}
      CHARTS[id] = null;

      const ctx = el.getContext('2d');
      const instance = new Chart(ctx, {
        type: 'doughnut',
        data: { labels, datasets: [{ data: values, backgroundColor: bg, borderWidth: 0 }] },
        options: {
          responsive: true,
          maintainAspectRatio: false,        // el contenedor fija la altura
          animation: { duration: 0 },        // evita parpadeos y carreras
          resizeDelay: 50,                   // debounce interno de Chart.js
          devicePixelRatio: window.devicePixelRatio || 1,
          cutout: '58%',
          layout: { padding: 8 },
          plugins: {
            legend: { position: 'bottom' },
            tooltip: {
              callbacks: {
                label: (ctx) => {
                  const v = +ctx.raw || 0;
                  const tot = (ctx.dataset.data || []).reduce((a, b) => a + (+b || 0), 0);
                  const pct = tot ? (v * 100 / tot) : 0;
                  return ` ${ctx.label}: ${fmt.format(v)} (${pct.toFixed(1)}%)`;
                }
              }
            },
            datalabels: {
              display: (ctx) => {
                const v = ctx.dataset.data[ctx.dataIndex] || 0;
                const tot = (ctx.dataset.data || []).reduce((a, b) => a + (+b || 0), 0);
                return tot ? (v / tot) >= 0.05 : false; // evita ruido en porciones pequeñas
              },
              anchor: 'center',
              align: 'center',
              backgroundColor: 'rgba(255,255,255,.85)',
              borderRadius: 6,
              padding: { top: 3, bottom: 3, left: 6, right: 6 },
              color: datalabelColor,
              font: { weight: '700', size: 11, lineHeight: 1.1 },
              formatter: (value, ctx) => {
                const tot = (ctx.dataset.data || []).reduce((a, b) => a + (+b || 0), 0);
                const pct = tot ? (value * 100 / tot) : 0;
                return `${fmt.format(+value || 0)}\n${pct.toFixed(1)}%`;
              }
            }
          }
        }
      });

      CHARTS[id] = instance;

      // Reacciona a cambios de tamaño del contenedor del canvas
      try {
        const box = el.parentElement || el;
        new ResizeObserver(() => CHARTS[id]?.resize()).observe(box);
      } catch (_) {}
    }

    // 5) Render según modo
    if (data.mode === 'Mecanico') {
      donut('chartByDSP',        data.series.byDSP);
      donut('chartByProcessing', data.series.byProcessing);
      // Limpia gráficos de microsync si existían
      donut('chartMsByCountry',     []);
      donut('chartMsByAssetTitle',  []);
    } else {
      donut('chartMsByCountry',     data.series.byCountry);
      donut('chartMsByAssetTitle',  data.series.byAssetTitle);
      // Limpia gráficos de mecánico si existían
      donut('chartByDSP',        []);
      donut('chartByProcessing', []);
    }
  }

  // =========================
  // Carga del panel (HTMX)
  // =========================
  function loadChartsPanel() {
    const form  = document.getElementById('statements-filters');
    const panel = document.getElementById('charts-panel');
    if (!form || !panel || !window.htmx) return;

    const baseUrl = panel.dataset.chartsPanelUrl;
    if (!baseUrl) return;

    const params = new URLSearchParams(new FormData(form)).toString();
    // Evita caches agresivos
    window.htmx.ajax('GET', `${baseUrl}?${params}`, {
      target: '#charts-panel',
      swap: 'innerHTML',
      headers: { 'Cache-Control': 'no-cache' },
    });
  }

  // =========================
  // Orquestación
  // =========================
  document.addEventListener('DOMContentLoaded', async () => {
    // Modo ADMIN: el parcial ya viene en el HTML
    if (document.getElementById('charts-data')) {
      await waitForPanelReady();
      renderChartsFromEmbeddedJSON();
      return;
    }
    // Modo PORTAL (cliente): pedimos el parcial por HTMX
    loadChartsPanel();
  });

  // Hooks HTMX (si está presente)
  if (window.htmx) {
    // Antes de reemplazar el panel, destruye instancias para no acumular
    document.body.addEventListener('htmx:beforeSwap', (e) => {
      if (e.detail?.target?.id === 'charts-panel') destroyAllCharts();
    });

    // Cuando cambia la tabla, recarga el panel de gráficas
    document.body.addEventListener('htmx:afterSettle', (e) => {
      if (e.detail?.target?.id === 'statements-panel') loadChartsPanel();
    });

    // Cuando el panel quedó asentado en el DOM, espera layout real y renderiza
    document.body.addEventListener('htmx:afterSettle', async (e) => {
      if (e.detail?.target?.id === 'charts-panel') {
        await waitForPanelReady();
        renderChartsFromEmbeddedJSON();
      }
    });
  }

  // Fallback extra: si todo cargó pero no hay charts, reintenta 1 vez tras window.load
  window.addEventListener('load', async () => {
    const hasCharts = Object.keys(CHARTS).length > 0;
    if (!hasCharts && document.getElementById('charts-data')) {
      await waitForPanelReady();
      renderChartsFromEmbeddedJSON();
    }
  });
})();
