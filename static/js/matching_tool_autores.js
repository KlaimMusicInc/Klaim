/* pages/matching_tool.js
   ----------------------------------------------------------
   Lógica de Matching-Tool (particles + guardar/insertar registros)
   Todas las funciones se cuelgan de window.* para que los
   onclick del template sigan funcionando.
---------------------------------------------------------- */
(function () {
  /* ╭─ Util ───────────────────────────────────────────────╮ */
  function getCookie (name) {
    const match = document.cookie
      .split('; ')
      .find(row => row.startsWith(name + '='));
    return match ? decodeURIComponent(match.split('=')[1]) : '';
  }
  const csrftoken = getCookie('csrftoken');

  /* ╭─ Partículas flotantes ───────────────────────────────╮ */
  function createParticles () {
    const container = document.getElementById('particles');
    if (!container) return;               // por si el div no existe
    const count = window.innerWidth < 768 ? 20 : 50;

    for (let i = 0; i < count; i++) {
      const p = document.createElement('div');
      p.classList.add('particle');

      const size = Math.random() * 10 + 5;
      p.style.width  = `${size}px`;
      p.style.height = `${size}px`;

      p.style.left = `${Math.random() * 100}%`;
      p.style.top  = `${Math.random() * 100}%`;

      p.style.animationDuration = `${Math.random() * 20 + 10}s`;
      p.style.animationDelay    = `${Math.random() * 5}s`;

      container.appendChild(p);
    }
  }
  document.addEventListener('DOMContentLoaded', createParticles);

  /* ╭─ Guardar Match ──────────────────────────────────────╮ */
  function guardarMatch (btn) {
    const row          = btn.closest('tr');
    const obra_id      = row.querySelector('.obra')?.dataset.id;
    const codigo_mlc_id= +row.querySelector('.codigo-mlc')?.dataset.id;
    const autor_id     = row.querySelector('.autor')?.dataset.id;
    const artistas_raw = row.querySelector('.artistas')?.dataset.ids || '';
    const artista_ids  = artistas_raw ? artistas_raw.split(',') : [];
    const usos         = row.querySelector('.usos-input')?.value.trim();

    if (!obra_id || !codigo_mlc_id || !autor_id || !usos) {
      alert('Todos los campos deben estar completos.');
      return;
    }

    fetch('/guardar-match/', {
      method : 'POST',
      headers: { 'Content-Type':'application/json', 'X-CSRFToken': csrftoken },
      body   : JSON.stringify({ obra_id, codigo_mlc_id, autor_id, artista_ids, usos })
    })
      .then(r => r.ok ? r : r.json().then(d => Promise.reject(d.error)))
      .then(() => { alert('Registro guardado.'); location.reload(); })
      .catch(err => alert(`Error al guardar: ${err || 'desconocido'}`));
  }

  /* ╭─ Insertar ISRC ──────────────────────────────────────╮ */
  function insertarISRC (btn) {
    const row        = btn.closest('tr');
    const isrc       = row.querySelector('.isrc-input')?.value.trim();
    const artista    = row.querySelector('.artist-input')?.value.trim();
    const cod_klaim  = row.querySelector('.obra')?.dataset.id;

    if (!isrc || !artista) {
      alert('Complete ISRC e intérprete.');
      return;
    }
    if (!/^[a-zA-Z0-9]+$/.test(isrc)) {
      alert('ISRC debe ser alfanumérico.');
      return;
    }

    fetch('/insertar-isrc/', {
      method : 'POST',
      headers: { 'Content-Type':'application/json', 'X-CSRFToken': csrftoken },
      body   : JSON.stringify({ isrc, artista, cod_klaim })
    })
      .then(r => r.ok ? r : r.json().then(d => Promise.reject(d.error)))
      .then(() => { alert('ISRC registrado.'); location.reload(); })
      .catch(err => alert(`Error al registrar ISRC: ${err || 'desconocido'}`));
  }

  /* ╭─ Exponer funciones globalmente ──────────────────────╮ */
  window.guardarMatch = guardarMatch;
  window.insertarISRC = insertarISRC;
})();
