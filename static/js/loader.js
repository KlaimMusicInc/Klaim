// static/js/loader.js

document.addEventListener('DOMContentLoaded', () => {
  const loader = document.getElementById('loader');
  if (!loader) return;

  // Mostrar loader al inicio y ocultarlo cuando la página haya cargado completamente
  loader.classList.add('active');
  window.addEventListener('load', () => {
    loader.classList.remove('active');
  });

  // Mostrar loader en navegación de enlaces internos
  document.querySelectorAll('a[href]').forEach(anchor => {
    const href = anchor.getAttribute('href');
    if (href.startsWith('/') || href.startsWith(window.location.origin)) {
      anchor.addEventListener('click', () => {
        loader.classList.add('active');
      });
    }
  });
});
