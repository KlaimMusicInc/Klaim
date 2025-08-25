// static/js/portal_cliente_microsync.js
(() => {
  'use strict';

  // =========================
  // Estado y utilidades
  // =========================
  const fmtUSD = new Intl.NumberFormat('es-CO', {
    style: 'currency', currency: 'USD', maximumFractionDigits: 2,
  });

  // Mantenemos instancias para poder destruirlas al refrescar
  const CHARTS_MS = Object.create(null);

  // Registrar DataLabels si existe
  document.addEventListener('DOMContentLoaded', () => {
    if (window.Chart && window.ChartDataLabels) {
      try { Chart.register(window.ChartDataLabels); } catch (_) {}
    }
  });

  function parseEmbeddedPayload() {
    const tag = document.getElementById('charts-data');
    if (!tag) return null;
    try { return JSON.parse(tag.textContent || '{}'); } catch { return null; }
  }

  function animateMetric(el, toValue, { duration = 700 } = {}) {
    if (!el) return;
    const fromText = (el.textContent || '').replace(/[^\d.-]/g, '');
    const fromValue = Number(fromText) || 0;
    const start = performance.now();
    const ease = t => 1 - Math.pow(1 - t, 3);
    function step(now) {
      const t = Math.min(1, (now - start) / duration);
      const v = fromValue + (toValue - fromValue) * ease(t);
      el.textContent = fmtUSD.format(v);
      if (t < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }

  function truncate(str, max = 40) {
    if (!str) return '';
    if (str.length <= max) return str;
    const cut = str.slice(0, max);
    const space = cut.lastIndexOf(' ');
    return (space > 24 ? cut.slice(0, space) : cut) + '…';
  }

  // Paleta (usa CSS variables cuando existan)
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

  function destroyMicroSyncCharts() {
    for (const id in CHARTS_MS) {
      try { CHARTS_MS[id]?.destroy(); } catch (_) {}
      delete CHARTS_MS[id];
    }
  }

  // Espera a que los canvas tengan tamaño > 0
  async function waitForCanvasReady(ids) {
    const tries = 20;
    for (let i = 0; i < tries; i++) {
      const ok = ids.every(id => {
        const el = document.getElementById(id);
        if (!el) return false;
        const r = el.getBoundingClientRect();
        return r.width > 10 && r.height > 10;
      });
      if (ok) return true;
      await new Promise(r => setTimeout(r, 16));
    }
    // Fuerza tamaño mínimo si no logramos medida
    ids.forEach(id => {
      const el = document.getElementById(id);
      if (!el) return;
      const r = el.getBoundingClientRect();
      if (r.width < 10 || r.height < 10) {
        el.setAttribute('width', '640');
        el.setAttribute('height', '360');
        el.style.width = '100%';
        el.style.height = '100%';
      }
    });
    return true;
  }

  // Crea donut idempotente
  function donut(id, series) {
    const el = document.getElementById(id);
    if (!el || !window.Chart) return;

    const labels = series.map(s => s.label);
    const values = series.map(s => Number(s.value) || 0);
    const bg = colors(labels.length);
    const datalabelColor =
      (getComputedStyle(document.documentElement).getPropertyValue('--dark').trim()) || '#0A1A3A';

    try { CHARTS_MS[id]?.destroy(); } catch (_) {}
    CHARTS_MS[id] = null;

    const ctx = el.getContext('2d');
    CHARTS_MS[id] = new Chart(ctx, {
      type: 'doughnut',
      data: { labels, datasets: [{ data: values, backgroundColor: bg, borderWidth: 0 }] },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 0 },
        resizeDelay: 50,
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
                return ` ${ctx.label}: ${fmtUSD.format(v)} (${pct.toFixed(1)}%)`;
              }
            }
          },
          datalabels: {
            display: (ctx) => {
              const v = ctx.dataset.data[ctx.dataIndex] || 0;
              const tot = (ctx.dataset.data || []).reduce((a, b) => a + (+b || 0), 0);
              return tot ? (v / tot) >= 0.05 : false;
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
              return `${fmtUSD.format(+value || 0)}\n${pct.toFixed(1)}%`;
            }
          }
        }
      }
    });

    // Resize reactivo
    try {
      const box = el.parentElement || el;
      new ResizeObserver(() => CHARTS_MS[id]?.resize()).observe(box);
    } catch (_) {}
  }

  // =========================
  // Render MicroSync
  // =========================
  async function renderMicroSync() {
    const payload = parseEmbeddedPayload();
    if (!payload || (payload.derecho || payload.mode) !== 'MicroSync') return;

    const m = payload.microsync || {};
    const totalPayable = Number(m.total_amount_payable || 0);
    const totalShare   = Number(m.total_market_share || 0);
    const byCountry    = Array.isArray(m.by_country) ? m.by_country : [];
    const byAsset      = Array.isArray(m.by_asset_title) ? m.by_asset_title : [];

    // Tarjetas
    const elPayable = document.getElementById('metric-ms-total');
    const elShare   = document.getElementById('metric-ms-marketshare');
    if (elPayable) animateMetric(elPayable, totalPayable, { duration: 800 });
    if (elShare)   animateMetric(elShare,   totalShare,   { duration: 800 });

    // Accesibilidad/títulos
    const titleCountry = document.getElementById('chart-ms-country-title');
    const titleAsset   = document.getElementById('chart-ms-asset-title');
    if (titleCountry) titleCountry.title = 'Distribución por país según Amount Payable';
    if (titleAsset)   titleAsset.title   = 'Distribución por Asset Title según Amount Payable';
    [document.getElementById('metric-ms-total-title'), document.getElementById('metric-ms-share-title')]
      .filter(Boolean)
      .forEach(n => { n.textContent = truncate(n.textContent, 64); n.setAttribute('title', n.textContent); });

    // Estado vacío
    const isEmpty = !totalPayable && !totalShare && !byCountry.length && !byAsset.length;
    const emptyBox = document.getElementById('charts-empty');
    if (emptyBox) emptyBox.style.display = isEmpty ? 'block' : 'none';

    if (isEmpty) { destroyMicroSyncCharts(); return; }

    // Render donuts
    destroyMicroSyncCharts();
    await waitForCanvasReady(['chartMsByCountry', 'chartMsByAssetTitle']);
    donut('chartMsByCountry',   byCountry);
    donut('chartMsByAssetTitle', byAsset);
  }

  // =========================
  // Orquestación
  // =========================
  document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('charts-data')) {
      renderMicroSync();
    }
  });

  if (window.htmx) {
    // Cuando se reemplaza el panel de charts
    document.body.addEventListener('htmx:beforeSwap', (e) => {
      if (e.detail?.target?.id === 'charts-panel') destroyMicroSyncCharts();
    });
    document.body.addEventListener('htmx:afterSettle', (e) => {
      if (e.detail?.target?.id === 'charts-panel') renderMicroSync();
    });
    // Si cambia la tabla (aplican filtros), recargar charts
    document.body.addEventListener('htmx:afterSettle', (e) => {
      if (e.detail?.target?.id === 'statements-panel') renderMicroSync();
    });
  }

  window.addEventListener('load', () => {
    if (document.getElementById('charts-data')) {
      renderMicroSync();
    }
  });
})();
