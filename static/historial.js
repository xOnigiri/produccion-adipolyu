// Muestra los campos "Desde" y "Hasta" solo cuando el periodo es "Elegir fechas".
// La página ya llega con ellos ocultos o visibles según el periodo; esto solo
// actúa cuando se cambia el periodo.
(function () {
  const periodo = document.getElementById("periodo");
  const camposRango = document.querySelectorAll(".campo-rango");

  function actualizar() {
    const elegirFechas = periodo.value === "rango";
    camposRango.forEach(function (campo) {
      campo.hidden = !elegirFechas;
    });
  }

  periodo.addEventListener("change", actualizar);
  // Al volver con "Atrás", el navegador puede devolver el periodo que estaba
  // elegido a mano: se ajusta solo si no coincide (si coincide, no cambia nada)
  window.addEventListener("pageshow", actualizar);
})();
