// Notificaciones flotantes de éxito: se cierran solas a los 10 segundos o con la X.
// Mientras el mouse (o el teclado) está encima, no se cierran; al salir, siguen
// con el tiempo que les quedaba.
(function () {
  const DURACION = 10000;

  document.querySelectorAll(".notificacion").forEach(function (aviso) {
    let restante = DURACION;
    let inicio = 0;
    let temporizador = null;
    let corriendo = false;

    function cerrar() {
      clearTimeout(temporizador);
      corriendo = false;
      aviso.classList.add("saliendo");
      // Se quita al terminar la animación de salida (o enseguida si no hay animación)
      aviso.addEventListener("animationend", function () { aviso.remove(); });
      setTimeout(function () { aviso.remove(); }, 400);
    }

    function seguir() {
      // Sigue en pausa si todavía tiene el mouse o el teclado encima
      if (corriendo || aviso.matches(":hover") || aviso.contains(document.activeElement)) {
        return;
      }
      corriendo = true;
      inicio = Date.now();
      temporizador = setTimeout(cerrar, restante);
    }

    function pausar() {
      if (!corriendo) {
        return;
      }
      corriendo = false;
      clearTimeout(temporizador);
      // Al salir le quedan al menos 2 segundos, para alcanzar a leer el final
      restante = Math.max(restante - (Date.now() - inicio), 2000);
    }

    aviso.addEventListener("mouseenter", pausar);
    aviso.addEventListener("mouseleave", seguir);
    aviso.addEventListener("focusin", pausar);
    aviso.addEventListener("focusout", function () {
      // El foco se mueve después de este evento: se espera un instante para revisar dónde quedó
      setTimeout(seguir, 0);
    });
    aviso.querySelector(".notificacion-cerrar").addEventListener("click", cerrar);
    seguir();
  });
})();
