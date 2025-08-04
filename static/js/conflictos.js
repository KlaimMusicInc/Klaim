/* eslint-disable no-alert */

/* ======================================================================
   Conflictos – Lógica JS
   ====================================================================== */

/*  Utilidad para obtener el CSRF token */
function getCSRFToken () {
  const inputToken = document.querySelector('[name=csrfmiddlewaretoken]');
  if (inputToken) return inputToken.value;

  const cookie = document.cookie
    .split('; ')
    .find(row => row.startsWith('csrftoken='));
  return cookie ? decodeURIComponent(cookie.split('=')[1]) : '';
}

let obraIdForUpdate   = null;
let plataformaForUpdate = null;

/* ======================================================================
   1 · Crear / Actualizar conflicto
   ====================================================================== */
window.actualizarConflicto = function () {
  const obrasMLC   = document.querySelectorAll('#conflictos-mlc-form   input[type="checkbox"]:checked');
  const obrasADREV = document.querySelectorAll('#conflictos-adrev-form input[type="checkbox"]:checked');

  const obrasSeleccionadas = [];
  let   plataforma         = null;

  if (obrasMLC.length) {
    plataforma = 'MLC';
    obrasMLC.forEach(cb => obrasSeleccionadas.push(cb.value));
  }
  if (obrasADREV.length) {
    plataforma = 'ADREV';
    obrasADREV.forEach(cb => obrasSeleccionadas.push(cb.value));
  }

  if (!obrasSeleccionadas.length) {
    alert('Seleccione al menos una obra en conflicto.');
    return;
  }

  const nombre       = document.getElementById('nombre-contraparte').value;
  const porcentaje   = document.getElementById('porcentaje-contraparte').value;
  const infoAdicional= document.getElementById('informacion-adicional').value;
  const enviarCorreo = confirm('¿Desea enviar un correo notificando el conflicto?');

  fetch('/actualizar-conflicto/', {
    method : 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken' : getCSRFToken()
    },
    body: JSON.stringify({
      obras                : obrasSeleccionadas,
      nombre_contraparte   : nombre,
      porcentaje_contraparte: porcentaje,
      informacion_adicional: infoAdicional,
      plataforma,
      enviar_correo        : enviarCorreo
    })
  })
  .then(r => r.json())
  .then(data => {
    if (data.success) {
      alert('Conflicto creado correctamente.');
      location.reload();
    } else {
      alert(data.error || 'Error inesperado.');
    }
  })
  .catch(err => {
    console.error(err);
    alert('Error al crear el conflicto.');
  });
};

/* ======================================================================
   2 · Eliminar conflicto y pedir nuevo estado
   ====================================================================== */
window.eliminarConflicto = function () {
  const obrasMLC   = document.querySelectorAll('#conflictos-mlc-form   input[type="checkbox"]:checked');
  const obrasADREV = document.querySelectorAll('#conflictos-adrev-form input[type="checkbox"]:checked');

  const obrasSeleccionadas = [];

  if (obrasMLC.length) {
    plataformaForUpdate = 'MLC';
    obrasMLC.forEach(cb => obrasSeleccionadas.push(cb.value));
  }
  if (obrasADREV.length) {
    plataformaForUpdate = 'ADREV';
    obrasADREV.forEach(cb => obrasSeleccionadas.push(cb.value));
  }

  if (!obrasSeleccionadas.length) {
    alert('Seleccione al menos una obra en conflicto para eliminar.');
    return;
  }

  if (!confirm('¿Está seguro de que desea eliminar los conflictos seleccionados?')) return;

  fetch(URL_ELIMINAR_CONFLICTO, {
    method : 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken' : getCSRFToken()
    },
    body: JSON.stringify({ obras: obrasSeleccionadas })
  })
  .then(r => r.json())
  .then(data => {
    if (data.success) {
      obraIdForUpdate = obrasSeleccionadas[0]; // primera obra para el nuevo estado
      openModalEstado();
    } else {
      alert(data.error || 'Error al eliminar los conflictos.');
    }
  })
  .catch(err => {
    console.error(err);
    alert('Error al eliminar los conflictos.');
  });
};

/* ======================================================================
   3 · Modal Estado plataforma
   ====================================================================== */
function openModalEstado () {
  const modal = document.getElementById('modal-estado');
  if (modal) {
    modal.classList.add('active');
  } else {
    console.warn("No se encontró el modal con id 'modal-estado'");
  }
}

function closeModalEstado () {
  document.getElementById('modal-estado').classList.remove('active');
}
window.closeModalEstado = closeModalEstado;

window.window.submitEstadoConflicto = function () {
  const estado = document.getElementById('estado-select').value;
  if (!estado) {
    alert('Seleccione un estado válido.');
    return;
  }

  const fecha = new Date().toISOString().split('T')[0];
  const mensaje =
    estado === 'LIBERADA' ? `Obra liberada ${fecha}` :
    estado === 'OK'       ? `Conflicto ganado ${fecha}` :
    '';

  fetch(URL_UPDATE_ESTADO_OBRA, {  // 🔧 Corregido aquí
    method : 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken' : getCSRFToken()
    },
    body: JSON.stringify({
      obra_id              : obraIdForUpdate,
      estado,
      plataforma           : plataformaForUpdate,
      informacion_adicional: mensaje
    })
  })
  .then(r => r.json())
  .then(data => {
    if (data.success) {
      closeModalEstado();
      location.reload();
    } else {
      alert(data.error || 'Error al actualizar el estado.');
    }
  })
  .catch(err => {
    console.error(err);
    alert('Error al actualizar el estado.');
  });
};

window.addEventListener('click', e => {
  if (e.target === document.getElementById('modal-estado')) closeModalEstado();
});

/* ======================================================================
   4 · Insertar información adicional a conflictos existentes
   ====================================================================== */
window.insertarInformacionConflicto = function () {
  const obrasMLC   = document.querySelectorAll('#conflictos-mlc-form   input[type="checkbox"]:checked');
  const obrasADREV = document.querySelectorAll('#conflictos-adrev-form input[type="checkbox"]:checked');

  const obrasSeleccionadas = [];
  obrasMLC.forEach(cb   => obrasSeleccionadas.push(cb.value));
  obrasADREV.forEach(cb => obrasSeleccionadas.push(cb.value));

  if (!obrasSeleccionadas.length) {
    alert('Seleccione al menos una obra en conflicto.');
    return;
  }

  const info = document.getElementById('informacion-adicional').value.trim();
  if (!info) {
    alert('El campo "Información Adicional" no puede estar vacío.');
    return;
  }

  fetch('/insertar-informacion-conflicto/', {
    method : 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken' : getCSRFToken()
    },
    body: JSON.stringify({
      obras               : obrasSeleccionadas,
      informacion_adicional: info
    })
  })
  .then(r => r.json())
  .then(data => {
    if (data.success) {
      alert('Información agregada correctamente.');
      location.reload();
    } else {
      alert(data.error || 'Error al agregar información.');
    }
  })
  .catch(err => {
    console.error(err);
    alert('Error al agregar información.');
  });
};
