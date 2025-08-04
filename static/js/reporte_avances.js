/* === Gráficas === */
(() => {
  if (!rows.length) return;
  const METRICAS = [
    {key:'obras',         label:'Obras',        color:'#3a86ff'},
    {key:'isrc',          label:'ISRC',         color:'#ff006e'},
    {key:'conflictos',    label:'Conflictos',   color:'#dc3545'},
    {key:'matching_isrc', label:'Matching-ISRC',color:'#28a745'},
    {key:'matching_ta',   label:'Matching T/A', color:'#ffc107'},
    {key:'audio_links',   label:'Audios',       color:'#4913df'},
  ];
  const labels = rows.map(r => r.cliente);
  const wrapper = document.getElementById('charts');

  METRICAS.forEach(m => {
    const box = document.createElement('div');
    box.className = 'chart-container';
    box.innerHTML = `<h3>${m.label}</h3><canvas id="c_${m.key}" height="160"></canvas>`;
    wrapper.appendChild(box);

    new Chart(document.getElementById(`c_${m.key}`), {
      type: 'bar',
      data: {
        labels,
        datasets: [{ label: m.label, data: rows.map(r => r[m.key]), backgroundColor: m.color }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: true, precision: 0 } }
      }
    });
  });
})();

/* === PDF captura de pantalla === */
document.getElementById('btnDownloadScreen')
  .addEventListener('click', () => {
    html2pdf().set({
      margin: 0,
      filename: 'Reporte_Klaim_{{ hoy|date:"Ymd_His" }}.pdf',
      image: { type: 'jpeg', quality: 0.98 },
      html2canvas: { scale: 2 },
      jsPDF: { unit: 'in', format: 'letter', orientation: 'portrait' }
    }).from(document.querySelector('.main-container')).save();
  });
