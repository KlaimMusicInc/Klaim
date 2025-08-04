// static/js/index.js

document.addEventListener("DOMContentLoaded", function () {
  // Efectos hover para KPI
  const kpiCards = document.querySelectorAll(".kpi-card");
  kpiCards.forEach((card) => {
    card.addEventListener("mouseenter", () => {
      card.classList.add("hovered");
    });
    card.addEventListener("mouseleave", () => {
      card.classList.remove("hovered");
    });
  });

  // Paginación activa
  const paginationButtons = document.querySelectorAll(".pagination button");
  paginationButtons.forEach((button) => {
    button.addEventListener("click", () => {
      paginationButtons.forEach((btn) => btn.classList.remove("active"));
      button.classList.add("active");
    });
  });

  // Partículas flotantes
  const particlesContainer = document.getElementById("particles");
  if (particlesContainer) {
    const imagePaths = [
      "/static/images/particle1.png",
      "/static/images/particle2.png",
      "/static/images/particle3.png"
    ];
    const totalParticles = 15;

    for (let i = 0; i < totalParticles; i++) {
      const particle = document.createElement("div");
      particle.className = "particle";
      particle.style.left = `${Math.random() * 100}vw`;
      particle.style.animationDuration = `${4 + Math.random() * 6}s`;
      particle.style.animationDelay = `${Math.random() * 4}s`;
      particle.style.backgroundImage = `url('${imagePaths[i % imagePaths.length]}')`;
      particlesContainer.appendChild(particle);
    }
  }
});
