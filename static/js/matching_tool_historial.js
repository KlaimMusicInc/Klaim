/* pages/matching_tool_historial.js
   ------------------------------------------------------------
   Lógica de la vista “Matching Tool · Historial”
------------------------------------------------------------ */

/* ---------- utilidades ---------- */
function getCookie (name) {
  const value = document.cookie
    .split('; ')
    .find(row => row.startsWith(name + '='));
  return value ? decodeURIComponent(value.split('=')[1]) : '';
}
const csrftoken = window.CSRF_TOKEN || getCookie('csrftoken');

/* ---------- partículas de fondo ---------- */
function createParticles () {
  const cnt    = document.getElementById('particles');
  if (!cnt) return;
  const n      = window.innerWidth < 768 ? 20 : 50;
  for (let i = 0; i < n; i++) {
    const p   = document.createElement('div');
    const sz  = Math.random() * 10 + 5;
    p.className = 'particle';
    p.style.cssText = `
      width:${sz}px;height:${sz}px;
      left:${Math.random()*100}%;
      top:${Math.random()*100}%;
      animation-duration:${Math.random()*20+10}s;
      animation-delay:${Math.random()*5}s;`;
    cnt.appendChild(p);
  }
}
document.addEventListener('DOMContentLoaded', createParticles);

/* ---------- helpers de búsqueda / paginación ---------- */
function buildQuery (page = null) {
  const qs = new URLSearchParams({
    work_title    : document.getElementById('work-title').value || '',
    mlc_code      : document.getElementById('mlc-code').value  || '',
    creation_date : document.getElementById('creation-date').value || '',
    status        : document.getElementById('status').value || ''
  });
  if (page !== null) qs.set('page', page);
  return qs.toString();
}

function loadTable (url, target, page = null) {
  fetch(`${url}?${buildQuery(page)}`)
    .then(r => r.text())
    .then(html => { document.getElementById(target).innerHTML = html; });
}

/* ---------- interfaz pública ---------- */
window.search = () => {
  loadTable(window.MATCH_URL_TA , 'table-titulo-autor-container');
  loadTable(window.MATCH_URL_ISRC, 'table-isrc-container');
};

/* paginación delegada (clases ya inyectadas por los partials) */
document.addEventListener('click', e => {
  if (e.target.matches('.page-link-titulo-autor')) {
    e.preventDefault();
    const page = e.target.dataset.page;
    loadTable(window.MATCH_URL_TA, 'table-titulo-autor-container', page);
  }
  if (e.target.matches('.page-link-isrc')) {
    e.preventDefault();
    const page = e.target.dataset.page;
    loadTable(window.MATCH_URL_ISRC, 'table-isrc-container', page);
  }
});

/* ---------- modal de estado ---------- */
let RECORD_ID = null, TABLE_NAME = null;

window.openModal = (id, table) => {
  RECORD_ID  = id;
  TABLE_NAME = table;
  document.getElementById('modal').classList.add('active');
};
window.closeModal = () =>
  document.getElementById('modal').classList.remove('active');

window.submitEstado = () => {
  const estado = document.getElementById('estado-select').value;
  fetch('/update-estado-isrc/', {
    method : 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken' : csrftoken
    },
    body   : JSON.stringify({ id: RECORD_ID, table: TABLE_NAME, estado })
  })
  .then(r => r.json())
  .then(data => {
    if (data.success) { closeModal(); window.location.reload(); }
    else              { alert(data.error || 'Error'); }
  })
  .catch(err => console.error(err));
};

/* cerrar modal al hacer clic fuera */
window.addEventListener('click', e => {
  const m = document.getElementById('modal');
  if (e.target === m) closeModal();
});
