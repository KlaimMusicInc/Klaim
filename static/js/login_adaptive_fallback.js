/* static/js/login_adaptive_fallback.js
   Fallback adaptativo para el fondo del login:
   - Intenta reproducir video base.
   - Desactiva overlay en condiciones limitadas (móvil/red lenta/ahorro).
   - Si autoplay falla o hay errores/stalls -> cambia a imagen estática ligera.
   - Pausa videos cuando la pestaña no está visible.
*/

(function () {
  'use strict';

  const bg = document.querySelector('.bg-video');
  if (!bg) return;

  const base = document.getElementById('bgVideoBase') || bg.querySelector('.bg-video__base');
  const overlay = document.getElementById('bgVideoOverlay') || bg.querySelector('.bg-video__overlay');
  const posterUrl = bg.getAttribute('data-fallback-image') || '';
  const conn = navigator.connection || navigator.webkitConnection || navigator.mozConnection;

  const state = {
    imageMode: false,
    overlayRemoved: false,
    decided: false,
  };

  /* ===== Helpers de entorno ===== */
  const mm = (q) => (window.matchMedia ? window.matchMedia(q).matches : false);
  const prefersReducedData = () => mm('(prefers-reduced-data: reduce)');
  const prefersReducedMotion = () => mm('(prefers-reduced-motion: reduce)');
  const smallScreen = () => mm('(max-width: 480px)');
  const isMobileUA = () => /Mobi|Android|iPhone|iPad|iPod/i.test(navigator.userAgent);
  const slowNetwork = () => {
    if (!conn) return false;
    const slowTypes = ['slow-2g', '2g', '3g'];
    return conn.saveData === true || slowTypes.includes(conn.effectiveType || '');
  };

  /* ===== Acciones ===== */
  function removeOverlay(reason) {
    if (!overlay || state.overlayRemoved) return;
    try { overlay.pause(); } catch (_) {}
    // Libera fuentes para no seguir descargando
    overlay.removeAttribute('src');
    while (overlay.firstChild) overlay.removeChild(overlay.firstChild);
    overlay.parentNode && overlay.parentNode.removeChild(overlay);
    state.overlayRemoved = true;
    // console.debug('[login] Overlay desactivado:', reason);
  }

  function switchToImageMode(reason) {
    if (state.imageMode) return;
    // Pausa y limpia videos para cortar descargas/cpu
    [base, overlay].forEach((v) => {
      if (!v) return;
      try { v.pause(); } catch (_) {}
      v.removeAttribute('src');
      while (v.firstChild) v.removeChild(v.firstChild);
    });

    if (posterUrl) {
      bg.style.backgroundImage = `url('${posterUrl}')`;
    }
    bg.classList.add('bg-video--image');
    state.imageMode = true;
    // console.debug('[login] Fallback a imagen:', reason);
  }

  function maybeDisableBlurIfUnsupported() {
    const supports = (prop) => (CSS && CSS.supports ? CSS.supports(prop) : false);
    if (!(supports('backdrop-filter: blur(1px)') || supports('-webkit-backdrop-filter: blur(1px)'))) {
      bg.classList.add('bg-video--no-blur');
    }
  }

  /* ===== Lógica principal ===== */
  function initialDecision() {
    if (state.decided) return;
    state.decided = true;

    maybeDisableBlurIfUnsupported();

    // Preferencias del usuario -> imagen estática directa
    if (prefersReducedData() || prefersReducedMotion()) {
      switchToImageMode('user_preferences');
      return;
    }

    // Condiciones limitadas -> quita overlay desde el inicio
    if (smallScreen() || isMobileUA() || slowNetwork()) {
      removeOverlay('constrained_initial');
    }

    // Si no hay video base, no hay nada que reproducir: usa imagen
    if (!base) {
      switchToImageMode('no_base_video');
      return;
    }

    // Test de autoplay: si falla o se tarda, usamos imagen
    const autoplayTimeoutMs = 2500;
    let resolved = false;

    const timer = setTimeout(() => {
      if (!resolved) switchToImageMode('autoplay_timeout');
    }, autoplayTimeoutMs);

    const tryPlay = base.play();
    if (tryPlay && typeof tryPlay.then === 'function') {
      tryPlay
        .then(() => {
          resolved = true;
          clearTimeout(timer);
          // Reproduce overlay con pequeño retardo si existe y no fue removido
          if (overlay && !state.overlayRemoved) {
            setTimeout(() => {
              overlay.play().catch(() => removeOverlay('overlay_autoplay_fail'));
            }, 300);
          }
        })
        .catch(() => {
          resolved = true;
          clearTimeout(timer);
          switchToImageMode('autoplay_blocked');
        });
    } else {
      // Navegadores antiguos: dejamos que el timeout decida
    }

    // Salvaguardas: errores / stalls tempranos => imagen
    const onError = () => { switchToImageMode('base_error'); cleanup(); };
    const onStall = () => { switchToImageMode('base_stalled'); cleanup(); };
    const onAbort = () => { switchToImageMode('base_abort'); cleanup(); };

    base.addEventListener('error', onError, { once: true });
    base.addEventListener('stalled', onStall, { once: true });
    base.addEventListener('abort', onAbort, { once: true });

    function cleanup() {
      base.removeEventListener('error', onError);
      base.removeEventListener('stalled', onStall);
      base.removeEventListener('abort', onAbort);
    }

    // Pausar al perder foco; reanudar al volver si no estamos en modo imagen
    document.addEventListener('visibilitychange', () => {
      const vids = [base, overlay].filter(Boolean);
      if (document.hidden) {
        vids.forEach((v) => { try { v.pause(); } catch (_) {} });
      } else if (!state.imageMode) {
        vids.forEach((v) => {
          if (v.readyState >= 1) v.play().catch(() => {});
        });
      }
    });

    // Si la red empeora después, quita overlay
    if (conn && typeof conn.addEventListener === 'function') {
      conn.addEventListener('change', () => {
        if (slowNetwork()) removeOverlay('net_slows');
      });
    }

    // Si cambian preferencias del usuario, cambia a imagen
    if (window.matchMedia) {
      const mData = window.matchMedia('(prefers-reduced-data: reduce)');
      const mMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
      const handler = (e) => { if (e.matches) switchToImageMode('user_pref_changed'); };

      if (mData.addEventListener) {
        mData.addEventListener('change', handler);
        mMotion.addEventListener('change', handler);
      } else if (mData.addListener) {
        // Safari viejo
        mData.addListener(handler);
        mMotion.addListener(handler);
      }
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialDecision);
  } else {
    initialDecision();
  }
})();
