// Muestra los campos de lona solo cuando el pedido lleva lona.
// Si se desmarca, se ocultan y se vacían para no guardar lona por error.
(function () {
  const casilla = document.getElementById("lleva_lona");
  const seccion = document.getElementById("seccion-lona");
  const campos = seccion.querySelectorAll("input");

  function actualizar() {
    const llevaLona = casilla.checked;
    seccion.hidden = !llevaLona;
    campos.forEach(function (campo) {
      campo.required = llevaLona;
      if (!llevaLona) {
        campo.value = "";
      }
    });
  }

  casilla.addEventListener("change", actualizar);
  actualizar();
})();
