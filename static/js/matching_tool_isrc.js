/* pages/matching_tool_isrc.js
   ----------------------------------------------------------
   Lógica para la vista “Matching Tool · ISRC”.
   Las funciones se exponen en `window.*` para que los botones
   definidos en la plantilla sigan funcionando.
---------------------------------------------------------- */
(function () {
  /* ───── Util CSRF ───── */
  function getCookie (name) {
    const match = document.cookie
      .split('; ')
      .find(row => row.startsWith(name + '='));
    return match ? decodeURIComponent(match.split('=')[1]) : '';
  }
  const csrftoken = getCookie('csrftoken');



  /* ───── Guardar match ───── */
  function guardarMatchIsrc (idIsrc) {
    const usosInput = document.getElementById(`usos_${idIsrc}`);
    const usos      = usosInput?.value.trim();
    const idSubida  = usosInput?.dataset.idSubida;

    if (!usos || usos < 0 || !idSubida) {
      alert('Por favor, complete todos los campos correctamente.');
      return;
    }

    fetch('/guardar-match-isrc/', {
      method : 'POST',
      headers: { 'Content-Type':'application/json', 'X-CSRFToken': csrftoken },
      body   : JSON.stringify({ id_isrc: idIsrc, usos, id_subida: idSubida })
    })
      .then(r => r.json().then(data => ({ ok: r.ok, data })))
      .then(({ ok, data }) => {
        if (ok) {
          alert('Match guardado correctamente.');
          location.reload();
        } else {
          throw new Error(data.message || 'Error desconocido.');
        }
      })
      .catch(err => alert(`Error al guardar el match: ${err.message}`));
  }

  /* ───── Confirmar / eliminar ISRC ───── */
  function confirmarEliminarIsrc (idIsrc) {
    fetch(`/obtener-info-isrc/${idIsrc}/`)
      .then(r => r.json())
      .then(info => {
        if (!info || !info.codigo_isrc) {
          throw new Error('No se pudo obtener la información del ISRC.');
        }
        const msg =
          `¿Estás seguro de eliminar este ISRC?\n\n` +
          `ISRC: ${info.codigo_isrc}\n` +
          `Obra: ${info.titulo}\n` +
          `Autores: ${info.autores}\n` +
          `Artistas: ${info.artistas}`;
        if (!confirm(msg)) return;

        return fetch(`/eliminar-isrc/${idIsrc}/`, {
          method : 'DELETE',
          headers: { 'X-CSRFToken': csrftoken }
        })
          .then(r => r.json())
          .then(res => {
            if (res.success) {
              alert(res.message);
              location.reload();
            } else {
              throw new Error(res.message || 'Error desconocido.');
            }
          });
      })
      .catch(err => alert(err.message));
  }

  /* ───── Exponer al global ───── */
  window.guardarMatchIsrc      = guardarMatchIsrc;
  window.confirmarEliminarIsrc = confirmarEliminarIsrc;
})();
