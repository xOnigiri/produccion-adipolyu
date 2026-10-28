// En el celular el menú se esconde detrás del botón "Menú". En la laptop el botón no se ve.
// (La marca "con-js", que lo deja cerrado de entrada, se pone en base.html antes de dibujar.)
(function () {
  const boton = document.querySelector(".boton-menu");
  const lateral = document.querySelector(".lateral");

  boton.addEventListener("click", function () {
    const abierto = lateral.classList.toggle("menu-abierto");
    boton.setAttribute("aria-expanded", abierto ? "true" : "false");
  });
})();
