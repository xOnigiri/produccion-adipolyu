# Recorrido del código – Parte 3: formulario para registrar producción

Explicación en lenguaje sencillo de cómo funciona el formulario, con los fragmentos clave de cada archivo.
Aprobada el 27/10/2026.

## La idea general: el viaje de un registro

Cuando aprietas "Guardar registro", el pedido pasa por **cuatro estaciones**, como una pieza que pasa del moldeo al acabado:

```
Navegador            →  app.py            →  validacion.py     →  base_datos.py
(formulario.js,         (recibe y decide)    (revisa reglas)      (guarda en
 registrar.html)                                                   produccion.db)
                     ←  formato.py: arma el mensaje verde de vuelta
```

Cada archivo tiene **un solo trabajo**. Por eso es fácil de mantener: si mañana cambia una regla del taller, solo se toca `validacion.py`.

---

## 1. [registrar.html](../templates/registrar.html): lo que ves

Es el formulario, escrito en HTML. Lo más interesante es que los cuatro campos de gramos usan **un solo molde** (en programación se llama "macro"):

```html
{% macro campo_gramos(campo, etiqueta, obligatorio=true) %}
  <input type="text" inputmode="decimal"
         pattern="\d+([.,]\d+)?"
         value="{{ valores[campo] or '' }}" ...>
```

- **Un molde, cuatro piezas:** material recibido, material sobrante, lona recibida y lona sobrante salen del mismo molde. Si cambio cómo se ve un campo de gramos, cambia en los cuatro.
- **`pattern`:** el navegador solo deja pasar números con coma o punto. Por eso escribir "tres mil" no llega ni a enviarse.
- **`value="{{ valores[campo] }}"`:** cuando hay un error, la página se vuelve a armar con lo que ya escribiste. Por eso no pierdes nada.
- **`inputmode="decimal"`:** en celular abriría el teclado numérico. Queda listo para cuando la app pase a la nube.

[base.html](../templates/base.html) es el **marco común**: el encabezado azul y el espacio para los mensajes verde y rojo. El historial y el informe lo van a reutilizar.

## 2. [formulario.js](../static/formulario.js): lo único que se mueve

```js
function actualizar() {
  const llevaLona = casilla.checked;
  seccion.hidden = !llevaLona;
  campos.forEach(function (campo) {
    campo.required = llevaLona;
    if (!llevaLona) { campo.value = ""; }
  });
}
```

En sencillo: **si la casilla de lona está marcada, se muestra la sección de lona y sus campos pasan a ser obligatorios. Si no lo está, se esconde y se vacía.** Así nunca se guarda un pedido "sin lona" con gramos de lona anotados por error.

## 3. [app.py](../app.py): el que recibe y decide

Es como el **encargado del taller**: no hace el trabajo fino, pero decide a quién pasar cada cosa. El fragmento clave es lo que pasa al apretar "Guardar" ([app.py:79-103](../app.py#L79-L103)):

```python
registro, errores = validar_registro(request.form, ...)
if errores:
    return _mostrar_formulario(request.form, errores, ...)

registro_id = base_datos.guardar_registro(_conexion(), registro)

flash(resumen_registro(...), "exito")
return redirect(url_for(".registrar", fecha=registro["fecha"]))
```

Paso a paso:
1. **Manda revisar** lo que llegó a `validacion.py`.
2. **Si hay errores,** devuelve el formulario con los mensajes rojos y tus datos intactos. No se guarda nada.
3. **Si todo está bien,** manda guardar a `base_datos.py`.
4. **Prepara el mensaje verde** (`flash`) y te **redirige** al formulario con la misma fecha.

**¿Por qué redirigir?** Si la página quedara como "resultado de un envío", apretar F5 volvería a enviar el formulario y **duplicaría el pedido**. Al redirigir, F5 solo recarga un formulario vacío. Es una técnica estándar con nombre propio: *Post/Redirect/Get*.

Hay una **tercera red de seguridad** ([app.py:93](../app.py#L93)): si algo pasara la revisión pero la base lo rechazara por sus propias reglas de la Parte 2, la app no se cae. Muestra "La base de datos rechazó el registro…".

**Arranque seguro** ([app.py:38](../app.py#L38)): `crear_app` revisa que `produccion.db` exista y tenga las 3 tablas **antes** de abrir la página. Si no, se detiene con un aviso.

## 4. [validacion.py](../validacion.py): el control de calidad

Es la **revisión de defectos** antes de guardar. Recibe todo como texto, porque así llega del navegador, y devuelve dos cosas: el registro limpio o la lista de errores.

**La coma o punto decimal** ([validacion.py:54](../validacion.py#L54)):

```python
def leer_numero(texto):
    texto = texto.strip().replace(",", ".")
    if not _NUMERO.fullmatch(texto):
        return None
    return float(texto)
```

Cambia la coma por punto y luego exige la forma "números, opcionalmente punto y más números". Rechaza a propósito cosas ambiguas como `3.600,5`, porque no se sabe si son 3600,5 o 3,6.

**Material y lona usan la misma revisión** ([validacion.py:36-51](../validacion.py#L36-L51)):

```python
MATERIAL = ParDePesos(campo_recibido="material_recibido_g", ...,
                      recibido_corto="el recibido")
LONA     = ParDePesos(campo_recibido="lona_recibida_g", ...,
                      recibido_corto="la recibida",
                      prefijo_vacio="Si el pedido lleva lona, anota")
```

Material y lona tienen la misma lógica: recibido, sobrante y "el sobrante no puede ser mayor". Por eso la regla está escrita **una sola vez** ([validacion.py:149](../validacion.py#L149)) y se le pasa una "ficha" que dice cómo nombrar cada uno en los mensajes ("el material" o "la lona"). Si mañana agregan otro insumo con recibido y sobrante, basta con una ficha nueva.

**Por qué este archivo no sabe nada de la web ni de la base:** así se puede probar solo, con miles de casos en menos de un segundo.

## 5. [base_datos.py](../base_datos.py): el único que toca la base

Toda la comunicación con `produccion.db` pasa por aquí. Dos fragmentos importantes:

**Nunca crea una base vacía** ([base_datos.py:28](../base_datos.py#L28)):

```python
uri = f"{Path(ruta).resolve().as_uri()}?mode=rw"
```

Por defecto, si SQLite no encuentra el archivo, **crea uno nuevo vacío sin avisar**. Eso sería peligroso: abrirías la app, verías todo vacío y pensarías que perdiste tus datos. `mode=rw` significa "solo abre si ya existe". Si no existe, falla y avisa.

**Guarda todo o nada** ([base_datos.py:71](../base_datos.py#L71)):

```python
with conexion:  # confirma si todo sale bien; deshace si hay error
    conexion.execute("INSERT INTO produccion (...) VALUES (:fecha, ...)", registro)
```

Esto se llama **transacción**. Si algo falla a la mitad, no queda un registro "a medias". Además, los datos van como `:fecha`, `:cantidad`, etc., separados de la orden SQL. Esa es la práctica profesional contra un tipo de ataque llamado *inyección SQL*: lo que escribas en "Observaciones" nunca se interpreta como una orden.

**La variable `ADIPOLYU_DB`** ([base_datos.py:22](../base_datos.py#L22)) permite apuntar la app a una copia. Así se hicieron las pruebas sin tocar la base real.

## 6. [formato.py](../formato.py): cómo se muestran los números

```python
def texto_kg(gramos):
    return f"{gramos / 1000:.2f} kg"      # 3200.5 g → "3.20 kg"
```

Aquí se calcula el **material usado** (recibido − sobrante) y se convierte a kg. Se calcula al momento, nunca se guarda: así, si en la Parte 4 corriges un dato, todo se recalcula solo. Está separado porque el historial y el PDF lo van a reutilizar. Aquí mismo se hará el cambio a "coma en toda la app" que quedó anotado como idea pendiente.

## 7. [Iniciar app.bat](../Iniciar%20app.bat) y el arranque

El `.bat` entra a la carpeta del proyecto, revisa que exista `.venv` y ejecuta la app con la opción `--abrir-navegador`. Dentro de `app.py` ([app.py:137](../app.py#L137)) hay dos detalles:
- **Antes de arrancar,** revisa si la app ya está abierta. Si lo está, solo abre el navegador en vez de fallar.
- **Espera un segundo** antes de abrir el navegador, para que la página no aparezca "no disponible".

## 8. [tests/](../tests/): las pruebas automáticas

Son 25 pruebas que se ejecutan con `.venv\Scripts\python -m unittest`. Por ejemplo:

```python
def test_sobrante_mayor_que_recibido(self):
    self.assertError(
        formulario(material_sobrante_g="4000"),
        "material_sobrante_g",
        "El material sobrante (4000 g) no puede ser mayor que el recibido (3600.5 g).",
    )
```

Cada prueba es un **caso del taller escrito como verificación**. Si en una parte futura un cambio rompe, por ejemplo, la regla del sobrante, esta prueba falla y se ve antes de que llegue al uso real. Las pruebas de la página completa crean una **base temporal** con las mismas tablas de `crear_base.py`, así que nunca tocan `produccion.db`.

---

## Decisiones técnicas destacadas

1. **Separación en capas:** pantalla, lógica de control, reglas de negocio y acceso a datos están en archivos distintos, cada uno con una sola responsabilidad.
2. **Validación en tres niveles:** en el navegador, en el servidor y con restricciones en la base de datos.
3. **Patrón Post/Redirect/Get:** recargar la página después de guardar no duplica registros.
4. **Protección de los datos reales:** la base nunca se recrea por accidente, y las pruebas automáticas corren sobre una base temporal, nunca sobre los datos reales.
5. **Valores derivados calculados al mostrar:** el material usado y los kg no se guardan, se calculan cada vez, para que nunca queden descuadrados.
