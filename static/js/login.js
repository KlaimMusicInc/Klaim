// static/js/login.js

// Lista de imágenes de partículas desde tu carpeta static
const particleImages = [
  "/static/images/particles/capital.png",
  "/static/images/particles/accordion.png",
  "/static/images/particles/piano.png",
  "/static/images/particles/krachapp.png",
  "/static/images/particles/guitar.png",
  "/static/images/particles/microphone.png",
  "/static/images/particles/money-bag.png",
  "/static/images/particles/money.png",
  "/static/images/particles/Cash.png"
];

document.addEventListener('DOMContentLoaded', () => {
  const particlesContainer = document.getElementById('particles');
  const particleCount = 20;
  const loadedImages = [];
  let imagesLoaded = 0;

  // Precargar imágenes
  particleImages.forEach(src => {
    const img = new Image();
    img.src = src;
    img.onload = () => {
      imagesLoaded++;
      if (imagesLoaded === particleImages.length) {
        createParticles();
      }
    };
    loadedImages.push(img);
  });

  function createParticles() {
    for (let i = 0; i < particleCount; i++) {
      const particle = document.createElement('div');
      particle.classList.add('particle');
      const randomImage = loadedImages[Math.floor(Math.random() * loadedImages.length)];
      const size     = Math.random() * 40 + 30;    // 30px a 70px
      const posX     = Math.random() * 100;        // 0% a 100%
      const delay    = Math.random() * 10;         // 0s a 10s
      const duration = Math.random() * 20 + 10;    // 10s a 30s
      const rotation = Math.random() * 360;        // 0° a 360°
      const opacity  = Math.random() * 0.5 + 0.5;  // 0.5 a 1

      particle.style.width            = `${size}px`;
      particle.style.height           = `${size}px`;
      particle.style.left             = `${posX}%`;
      particle.style.bottom           = `-${size}px`;
      particle.style.animationDelay    = `${delay}s`;
      particle.style.animationDuration = `${duration}s`;
      particle.style.transform         = `rotate(${rotation}deg)`;
      particle.style.opacity           = opacity;
      particle.style.backgroundImage   = `url("${randomImage.src}")`;

      particlesContainer.appendChild(particle);
    }
  }

  // Efecto 3D tilt en la tarjeta
  const card = document.querySelector('.login-container .card');
  if (!card) return;

  card.addEventListener('mousemove', e => {
    const xAxis = (window.innerWidth / 2 - e.pageX) / 15;
    const yAxis = (window.innerHeight / 2 - e.pageY) / 15;
    card.style.transform = `rotateY(${xAxis}deg) rotateX(${yAxis}deg)`;
  });

  card.addEventListener('mouseenter', () => {
    card.style.transition = 'none';
  });

  card.addEventListener('mouseleave', () => {
    card.style.transition = 'all 0.5s ease';
    card.style.transform = 'rotateY(0deg) rotateX(0deg)';
  });
});
