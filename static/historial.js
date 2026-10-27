// Muestra los campos "Desde" y "Hasta" solo cuando el periodo es "Elegir fechas".
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
  actualizar();
})();
