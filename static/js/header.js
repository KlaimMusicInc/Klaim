/* ---- Toggle Menu with Animation ---- */
function toggleMenu() {
  const burger = document.getElementById('burger');
  const nav    = document.getElementById('sideNav');

  burger.classList.toggle('open');
  nav.classList.toggle('open');

  // Ripple effect on burger
  if (burger.classList.contains('open')) {
    const ripple = document.createElement('span');
    ripple.style.cssText = `
      position: absolute;
      width: 60px;
      height: 60px;
      background: rgba(79, 195, 247, 0.3);
      border-radius: 50%;
      pointer-events: none;
      transform: translate(-50%, -50%) scale(0);
      animation: ripple 0.6s ease-out;
    `;
    burger.appendChild(ripple);
    setTimeout(() => {
      ripple.style.transform = 'translate(-50%, -50%) scale(1)';
      ripple.style.opacity   = '0';
    }, 10);
    setTimeout(() => ripple.remove(), 600);
  }
}

/* ---- Advanced Dropdown with Animation ---- */
function toggleDropdown(e) {
  e.stopPropagation();
  const dropdown = e.currentTarget.parentElement;
  const isOpen   = dropdown.classList.contains('open');

  // Close others
  document.querySelectorAll('.dropdown.open').forEach(d => {
    if (d !== dropdown) d.classList.remove('open');
  });

  dropdown.classList.toggle('open');

  if (!isOpen) {
    const menu = dropdown.querySelector('.dropdown-menu');
    menu.style.opacity   = '0';
    menu.style.transform = 'translateY(-10px)';
    setTimeout(() => {
      menu.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
      menu.style.opacity    = '1';
      menu.style.transform  = 'translateY(0)';
    }, 10);
  }
}

/* Close menu when clicking outside */
document.addEventListener('click', e => {
  const nav    = document.getElementById('sideNav');
  const burger = document.getElementById('burger');
  if (nav.classList.contains('open') && !nav.contains(e.target) && !burger.contains(e.target)) {
    toggleMenu();
  }
});

/* Close dropdowns when clicking outside */
document.addEventListener('click', e => {
  if (!e.target.closest('.dropdown')) {
    document.querySelectorAll('.dropdown.open').forEach(d => d.classList.remove('open'));
  }
});

/* Ripple Effect on Nav Items */
document.querySelectorAll('.side-nav a, .dropdown-btn').forEach(item => {
  item.addEventListener('click', function(e) {
    if (this.href || this.classList.contains('dropdown-btn')) {
      const rect = this.getBoundingClientRect();
      const x    = e.clientX - rect.left;
      const y    = e.clientY - rect.top;
      const ripple = document.createElement('span');
      ripple.style.cssText = `
        position: absolute;
        width: 20px;
        height: 20px;
        background: rgba(79, 195, 247, 0.6);
        border-radius: 50%;
        pointer-events: none;
        transform: translate(-50%, -50%) scale(0);
        animation: ripple 0.6s ease-out;
        top: ${y}px;
        left: ${x}px;
      `;
      this.appendChild(ripple);
      setTimeout(() => {
        ripple.style.transform = 'translate(-50%, -50%) scale(10)';
        ripple.style.opacity   = '0';
      }, 10);
      setTimeout(() => ripple.remove(), 600);
    }
  });
});
