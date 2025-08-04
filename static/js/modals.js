// static/js/modals.js

document.addEventListener("DOMContentLoaded", function () {
  // Modal lógica
  window.openModal = function (obraId, campoEstado) {
    window._obraId = obraId;
    window._campoEstado = campoEstado;
    document.getElementById("modal").classList.add("active");
  };

  window.closeModal = function () {
    document.getElementById("modal").classList.remove("active");
  };

  window.submitEstado = function () {
    const estado = document.getElementById("estado-select").value;
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;

    if (!estado) {
      alert("El estado no puede estar vacío.");
      return;
    }

    fetch("/update-estado/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken
      },
      body: JSON.stringify({
        obra_id: window._obraId,
        campo: window._campoEstado,
        estado: estado
      })
    })
      .then((res) => res.json())
      .then((data) => {
        if (data.success) {
          window.closeModal();
          window.location.reload();
        } else {
          alert(data.error);
        }
      })
      .catch((err) => {
        console.error("Error al actualizar estado:", err);
      });
  };

  // Cierre de modal al hacer clic afuera
  window.onclick = function (e) {
    const modal = document.getElementById("modal");
    if (e.target === modal) {
      window.closeModal();
    }
  };
});
