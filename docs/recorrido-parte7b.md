# Recorrido del código – Parte 7b: diseño

Explicación en lenguaje sencillo del nuevo aspecto de la app, con los fragmentos clave.
Aprobada el 28/10/2026.

## La idea general

Solo cambia **cómo se ve** la app: la base de datos y la forma de guardar no se tocan. Se usan los colores del logo (naranja y verde), un menú lateral con el logo, tarjetas con números grandes y tablas limpias con estados en "pastillas" de color. Las pantallas se adaptan al celular y no dependen de internet: no hay fuentes ni librerías externas.

---

## 1. [estilos.css](../static/estilos.css): colores y estructura

```css
--naranja-logo: #dc5212;     /* solo en cifras grandes y detalles */
--principal: #c2470f;        /* botones con texto blanco */
--principal-texto: #a63c0c;  /* enlaces y textos pequeños */
```

([estilos.css:14](../static/estilos.css#L14)). El naranja del logo sobre blanco se lee bien en letras grandes, pero no en textos pequeños. Por eso cada uso tiene su propio tono, un poco más oscuro donde hace falta.

- **Menú lateral fijo** en la laptop. Por debajo de 900 px pasa a ser una barra arriba con un botón "Menú" ([estilos.css:1166](../static/estilos.css#L1166)).
- **Tarjetas de números** ([estilos.css:255](../static/estilos.css#L255)): cifra grande en naranja y unidad pequeña en gris.
- **Pastillas:** gris para lona y dureza, verde para "Activo", gris tenue para "Inactivo" y ámbar para "Toca hacer respaldo".
- **Botones pequeños con borde** ([estilos.css:956](../static/estilos.css#L956)): Corregir nombre, Desactivar, Reactivar y Hacer respaldo ahora. Ya no hay enlaces subrayados que funcionen como botones.
- **Transiciones suaves** de color al pasar el mouse por botones, filas y menú.

## 2. [base.html](../templates/base.html) y [_iconos.html](../templates/_iconos.html): el marco común

- **Logo:** `/logo.png` ([app.py:169](../app.py#L169)) sirve el mismo archivo que usa el PDF, así hay un solo logo en la carpeta. Si falta, el menú escribe "ADIPOLYU".
- **Icono de la pestaña:** [static/icono.png](../static/icono.png), el hexágono recortado del logo, con fondo transparente.
- **Iconos de línea** dibujados en SVG dentro de la propia app: los del menú, y el lápiz y la papelera de cada fila del historial. Los botones de icono muestran "Corregir" o "Borrar" al pasar el mouse y llevan un texto oculto para lectores de pantalla ("Corregir el pedido del 22/10/2026").

## 3. Tarjetas de "Esta semana" y comparación

```python
def _totales_semana(dia, **filtros):
    lunes, domingo = calculos.semana_de(dia)
    registros = base_datos.listar_registros(...)
    return calculos.totales(registros)
```

([app.py:236](../app.py#L236)). Reutiliza las mismas funciones del historial, sin la papelera.

- **Registrar** muestra piezas, kg de material y pedidos de esta semana.
- **Historial** muestra piezas, kg de material, kg de lona y pedidos del periodo elegido.
- Debajo de cada cifra va "Semana pasada: …" (o "Semana anterior: …" si se está viendo la semana pasada), con los mismos filtros de pieza, material y dureza ([app.py:302](../app.py#L302)).
- Con fechas libres o "Todo" no hay una semana con qué comparar, así que la línea no aparece.

Las tarjetas se arman con un solo molde ([_cifras.html:14](../templates/_cifras.html#L14)).

## 4. [formato.py](../formato.py): coma decimal, mayúscula inicial y negrita

```python
def _con_coma(texto):
    return texto.replace(".", ",")

def nombre_visible(nombre):
    return nombre[:1].upper() + nombre[1:]

def nombre_en_negrita(nombre):
    return Markup("<strong>{}</strong>").format(nombre_visible(nombre))
```

([formato.py:32](../formato.py#L32)).

- **Coma decimal:** todos los números de la app y del PDF pasan por aquí, así que la coma aparece en todas partes ("3600,5 g", "3,20 kg") con la misma regla de redondeo de siempre. La app no usa separador de miles, por eso el punto solo puede ser el decimal.
- **Mayúscula inicial:** "jebe natural" se muestra como "Jebe natural". En la base sigue en minúsculas.
- **Negrita en los mensajes:** los nombres van en negrita y sin comillas ("**Soporte** está activa otra vez…"). `Markup` escapa el texto: un nombre como `<b>x</b>` se muestra tal cual y no se interpreta como HTML. En el PDF y en los textos para lectores de pantalla el nombre va normal.

## 5. Dureza sin "Shore A"

En pantalla y en el PDF se dice solo **"Dureza"**. En la tabla la pastilla lleva solo el número, porque la columna ya dice "Dureza". En el mensaje de confirmación y en el resumen de filtros se lee "Dureza 70". El PDF filtrado se llama `…_dureza-70.pdf`. La columna de la base conserva su nombre técnico, `dureza_shore_a`, para no cambiar la estructura de la base.

## 6. Notificaciones y "Guardando…"

- **Mensajes de éxito** (guardado, corregido, borrado, restaurado, respaldo): salen como una notificación flotante arriba a la derecha ([base.html:95](../templates/base.html#L95)), sobre el título y las tarjetas, no sobre el formulario.
  - [notificaciones.js](../static/notificaciones.js) las cierra a los 10 segundos, pero no mientras el mouse o el teclado están encima. También tienen una X para cerrarlas.
- **Errores y advertencias** siguen fijos en la página, porque piden atención. Los errores de cada campo, debajo del campo.
- **Guardar:** al enviar, el botón dice "Guardando…" y se desactiva ([formulario.js](../static/formulario.js)). Así un doble clic no guarda el pedido dos veces. Si se vuelve con "Atrás", el botón queda listo otra vez.
- **"Reducir movimiento":** si el sistema lo pide, nada se desliza ni se desvanece ([estilos.css:1154](../static/estilos.css#L1154)).

## 7. Sin parpadeos y con precarga

- **Lo que debe estar oculto llega ya oculto desde el servidor.** Esto vale para las fechas "Desde/Hasta" del historial ([historial.html:31](../templates/historial.html#L31)) y la sección de lona ([registrar.html:134](../templates/registrar.html#L134)). El JavaScript solo actúa al cambiar el periodo o la casilla, y al volver con "Atrás".
- **El menú del celular** empieza cerrado gracias a una marca que se pone antes de dibujar la página ([base.html:12](../templates/base.html#L12)).
- **Precarga** ([base.html:17](../templates/base.html#L17)): al dejar el mouse sobre una opción del menú, Chrome y Edge piden esa página por adelantado.
  - Solo se aplica a los enlaces del menú, que únicamente muestran datos, nunca a formularios.
  - Solo trae la página, sin ejecutarla.
  - Los demás navegadores lo ignoran.

## 8. PDF

Títulos en naranja oscuro y encabezados de tabla con letra blanca sobre naranja ([informe_pdf.py:39](../informe_pdf.py#L39)), con una línea verde bajo el título. Las tablas siguen en blanco y gris claro para que se lean bien impresas en blanco y negro. Nombres con mayúscula inicial y coma decimal, igual que en pantalla. El nombre del archivo no cambia.

## 9. Pruebas automáticas

Son **204 pruebas** (antes 162), todas sobre bases temporales. Hay 40 nuevas en [tests/test_diseno.py](../tests/test_diseno.py) y 2 en archivos que ya existían. Revisan:
- Las tarjetas y su comparación: semana pasada, semana anterior, mismos filtros, sin comparación con fechas libres y sin contar la papelera.
- El logo (y el texto cuando falta) y el icono de la pestaña.
- Las pastillas, los botones de icono con su texto oculto y los botones pequeños de Listas.
- Coma decimal y mayúscula inicial en pantalla y en el PDF.
- La negrita escapada, con un nombre que contiene HTML, y que ninguna pantalla use comillas «».
- Las notificaciones flotantes frente a los avisos fijos, el "Guardando…" y la regla de "reducir movimiento".
- La precarga, limitada a los enlaces del menú.
- Que lo oculto llegue oculto desde el servidor.

Las pruebas anteriores se ajustaron a la coma, las mayúsculas y la negrita. Pylint no da avisos en los archivos de esta parte.

---

## Decisiones técnicas destacadas

1. **Colores del logo con contraste suficiente:** el naranja original solo en cifras grandes; tonos más oscuros en botones y textos pequeños.
2. **Formato en un solo lugar:** coma decimal, mayúscula inicial y negrita salen de `formato.py`, así que la pantalla, los mensajes y el PDF nunca se contradicen.
3. **Solo se muestra distinto, no se guarda distinto:** los nombres siguen en minúsculas en la base, y la columna de dureza conserva su nombre técnico.
4. **Mensajes seguros:** los nombres escritos por el usuario se escapan antes de mostrarse en negrita.
5. **Lo que se ve al cargar lo decide el servidor:** el JavaScript solo reacciona a cambios, así no hay parpadeos.
6. **Mejoras que no rompen nada:** la precarga y la regla de "reducir movimiento" se ignoran sin errores donde no se soportan, y sin JavaScript el menú sigue visible.
7. **Protección contra doble envío:** "Guardando…" evita pedidos duplicados por doble clic.
8. **Se probó y se descartó** la animación entre páginas (*View Transitions*): casi no se notaba y retrasaba los clics. La navegación directa con precarga resultó más rápida.
9. **Sin dependencias externas:** iconos en SVG propio y fuentes del sistema; la app funciona sin internet.
