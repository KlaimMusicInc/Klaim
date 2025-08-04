/* pages/obras_liberadas.js
   ----------------------------------------------------------
   Funciones de búsqueda y eliminación para Obras Liberadas.
   Se cargan como módulo global a través de window.
---------------------------------------------------------- */
(function () {
  /* ——— CSRF util ——— */
  function getCookie (name) {
    const value = document.cookie
      .split('; ')
      .find(row => row.startsWith(name + '='));
    return value ? decodeURIComponent(value.split('=')[1]) : '';
  }
  const csrftoken = getCookie('csrftoken');

  /* ——— Buscar ——— */
  function buscar () {
    const params = {
      titulo       : document.getElementById('titulo').value,
      codigo_iswc  : document.getElementById('codigo_iswc').value,
      nombre_autor : document.getElementById('nombre_autor').value,
      id_cliente   : document.getElementById('id_cliente').value
    };
    const qs = new URLSearchParams(params).toString();
    window.location.href = `/liberadas/?${qs}`;
  }

  /* ——— Eliminar seleccionadas ——— */
  function eliminarLiberaciones () {
    const seleccion = Array.from(
      document.querySelectorAll('.select-checkbox:checked')
    ).map(cb => cb.value);

    if (!seleccion.length) {
      alert('Seleccione al menos una obra para eliminar.');
      return;
    }
    if (
      !confirm(
        '¿Está seguro que desea eliminar las obras seleccionadas? ' +
        'Esta acción no se puede deshacer.'
      )
    ) return;

    fetch('/eliminar-liberaciones/', {
      method : 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken' : csrftoken
      },
      body: JSON.stringify({ obras: seleccion })
    })
      .then(r => r.json())
      .then(data => {
        if (data.success) {
          alert('Obras liberadas eliminadas correctamente.');
          location.reload();
        } else {
          alert(data.error);
        }
      })
      .catch(err => {
        console.error(err);
        alert('Error al eliminar las obras liberadas.');
      });
  }

  /* ——— Exponer en global para los botones ——— */
  window.buscar = buscar;
  window.eliminarLiberaciones = eliminarLiberaciones;
})();
