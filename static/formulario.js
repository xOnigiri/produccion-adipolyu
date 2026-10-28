// Muestra los campos de lona solo cuando el pedido lleva lona.
// Si se desmarca, se ocultan y se vacían para no guardar lona por error.
// La página ya llega con la sección oculta o visible según el pedido; esto
// solo actúa cuando se marca o desmarca la casilla.
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
  // Al volver con "Atrás", el navegador puede devolver la casilla como estaba
  // marcada a mano: se ajusta solo si no coincide (si coincide, no cambia nada)
  window.addEventListener("pageshow", actualizar);
})();

// Al enviar, el botón dice "Guardando…" y se desactiva: un doble clic no guarda
// el pedido dos veces. (Si falta un campo obligatorio, el navegador no envía nada
// y el botón no cambia.)
(function () {
  const formulario = document.querySelector("form.formulario");
  const boton = formulario.querySelector("button[type=submit]");
  const textoOriginal = boton.textContent;
  let enviado = false;

  formulario.addEventListener("submit", function (evento) {
    if (enviado) {
      evento.preventDefault();
      return;
    }
    enviado = true;
    boton.disabled = true;
    boton.textContent = boton.dataset.enviando;
  });

  // Al volver con "Atrás", el navegador puede mostrar la página tal como quedó:
  // se deja el botón listo otra vez
  window.addEventListener("pageshow", function () {
    enviado = false;
    boton.disabled = false;
    boton.textContent = textoOriginal;
  });
})();
