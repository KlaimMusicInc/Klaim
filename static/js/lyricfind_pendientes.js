/* pages/lyricfind_pendientes.js
   ------------------------------------------------------------------
   Drop-zone  ·  Modal  ·  Wave-effect
------------------------------------------------------------------ */
(function () {
  /* ========== Drop-zone ========== */
  const dropZone = document.getElementById('dropZone');

  const highlight   = () => dropZone.classList.add('hover');
  const unHighlight = () => dropZone.classList.remove('hover');

  ['dragenter', 'dragover'].forEach(evt =>
    dropZone.addEventListener(evt, e => { e.preventDefault(); highlight(); })
  );
  ['dragleave', 'drop'].forEach(evt =>
    dropZone.addEventListener(evt, e => { e.preventDefault(); unHighlight(); })
  );

  dropZone.addEventListener('drop', e => {
    const file = e.dataTransfer.files?.[0];
    if (!file) return;

    const baseName = file.name.replace(/\.mp3$/i, '');
    const [idIsrc] = baseName.split(' - ');
    if (!/^\d+$/.test(idIsrc)) {
      alert('El nombre de archivo debe iniciar con el id_isrc numérico.');
      return;
    }

    const url = new URL(window.location.href);
    url.searchParams.set('id_isrc', idIsrc);
    url.searchParams.delete('page');
    window.location.href = url.toString();

    createWaveEffect();
  });

  function createWaveEffect () {
    const wave = document.createElement('div');
    Object.assign(wave.style, {
      position: 'absolute',
      inset: '0',
      borderRadius: '20px',
      background: 'rgba(108,92,231,.3)',
      animation: 'wave 1s forwards',
      pointerEvents: 'none'
    });
    dropZone.appendChild(wave);
    setTimeout(() => wave.remove(), 1000);
  }

  /* ========== Modal helpers ========== */
  const lyricModal = document.getElementById('lyricModal');
  const lyricForm  = document.getElementById('lyricForm');
  const actionTpl  = lyricForm.getAttribute('data-action-template'); // ej. /lyricfind/guardar/0/

  function openLyricModal (linkId) {
    /* Sustituimos SOLO el 0 final (antes del / opcional) por el id real */
    lyricForm.action = actionTpl.replace(/0\/?$/, linkId + '/');
    lyricModal.classList.add('active');
  }

  function closeLyricModal () {
    lyricModal.classList.remove('active');
  }

  /* Cerrar haciendo click fuera del contenido */
  window.addEventListener('click', e => {
    if (e.target === lyricModal) closeLyricModal();
  });

  /* Exponer en global para uso desde el template */
  window.openLyricModal  = openLyricModal;
  window.closeLyricModal = closeLyricModal;
})();
