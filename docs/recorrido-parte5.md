# Recorrido del código – Parte 5: informe de producción en PDF

Explicación en lenguaje sencillo de cómo se genera el informe en PDF, con los fragmentos clave de cada archivo.
Aprobada el 27/10/2026.

## La idea general: el PDF es "lo que se ve en el historial, en papel"

```
                         ┌─→ historial.html   (pantalla)
historial (filtros) ─ app._consultar ─┤
                         └─→ informe_pdf.py   (hoja A4 horizontal) → descarga .pdf

calculos.totales()  → las mismas cuentas para los dos
formato.py          → el mismo redondeo para los dos
```

El botón **"Descargar PDF"** usa el periodo y los filtros que se están viendo en ese momento. No hay una pantalla aparte para elegir la semana: se elige en el historial, se revisa y se descarga.

El único archivo nuevo es `informe_pdf.py`. Las librerías nuevas son **ReportLab** (arma el PDF) y **Pillow** (lee la imagen del logo), anotadas en `requirements.txt`.

---

## 1. [app.py](../app.py): una sola consulta para la pantalla y el PDF

**La consulta compartida** ([app.py:214](../app.py#L214)):

```python
def _consultar(args):
    filtros = _leer_filtros(args, date.today())
    ...
    registros = base_datos.listar_registros(_conexion(), desde=..., hasta=..., pieza_id=..., material_id=...)
    return filtros, registros, calculos.totales(registros)
```

La usan el historial y la descarga del PDF. Como la consulta es la misma, el PDF **no puede** mostrar otros pedidos ni otros totales que la pantalla, y los registros de la papelera quedan fuera de los dos.

**La descarga** ([app.py:182-211](../app.py#L182-L211)):

- **Sin registros, no hay PDF:** en el historial el botón aparece gris ("No hay registros para el informe"). Si igual se abre la dirección, la app vuelve al historial con un aviso.
- **Sin logo, el PDF sale igual:** pone "ADIPOLYU" en texto y deja un aviso en la ventana negra.
- **Título según el periodo** ([app.py:236](../app.py#L236)): "Producción de la semana" con "Lunes 19/10/2026 al domingo 25/10/2026", o "Producción del … al …", o "todos los registros". Debajo, los filtros elegidos y el número de pedidos.
- **Nombre del archivo** ([app.py:276](../app.py#L276)): `produccion_2026-10-19_al_2026-10-25.pdf`, con la pieza y el material si se filtraron (`_reten_nitrilo`). Las fechas van en formato año-mes-día para que, en una carpeta, los informes se ordenen solos. Las tildes y espacios se quitan ("silicona naranja" → `silicona-naranja`) para que el nombre funcione en cualquier sistema.

## 2. [informe_pdf.py](../informe_pdf.py): cómo se arma la hoja

Este archivo **no sabe nada de la web ni de la base de datos**: recibe los pedidos y los totales ya calculados y devuelve el PDF. Por eso se puede probar solo.

```python
contenido = [
    _encabezado(textos, ruta_logo),   # logo a la izquierda, título a la derecha
    HRFlowable(...),                  # línea azul
    _recuadro_resumen(totales),       # 3 cifras grandes
    _tabla_pedidos(registros, totales),
    _resumenes(totales),              # por material y por pieza, lado a lado
]
```

([informe_pdf.py:107-117](../informe_pdf.py#L107-L117)). ReportLab va colocando cada bloque uno debajo del otro y, si no entra, pasa a la hoja siguiente.

- **Recuadro de 3 cifras** ([informe_pdf.py:154](../informe_pdf.py#L154)): piezas producidas, kg de material usado y kg de lona usada. Es lo primero que se lee.
- **Tabla de pedidos** ([informe_pdf.py:203](../informe_pdf.py#L203)): las mismas columnas del historial, pero de la lona solo va la **usada**, para que la hoja horizontal no se sature. Las columnas calculadas llevan el mismo fondo celeste de la pantalla y la última fila es el TOTAL.
- **Títulos en cada hoja** ([informe_pdf.py:237](../informe_pdf.py#L237)): `repeatRows=1` repite la fila de títulos si la tabla pasa a otra hoja, como "Imprimir títulos" en Excel.
- **Resúmenes que no se cortan** ([informe_pdf.py:275](../informe_pdf.py#L275)): `KeepTogether` obliga a que "Por material" y "Por pieza" queden completos en la misma hoja. En "Por material", la lona aparece como una línea aparte (usada y sobrante), separada con una raya azul porque no es un material del pedido.

**"Página X de Y"** ([informe_pdf.py:328](../informe_pdf.py#L328)): el total de hojas solo se conoce al terminar. Por eso las hojas se guardan en memoria y el pie se escribe al final, en todas a la vez.

## 3. [formato.py](../formato.py) y [calculos.py](../calculos.py): pequeños agregados

- **`numero_kg`** y **`numero_g_por_pieza`** ([formato.py:46-60](../formato.py#L46-L60)) devuelven el número sin la unidad ("3.20" en vez de "3.20 kg"), porque en la tabla del PDF la unidad ya va en el título de la columna. `texto_kg` ahora se apoya en `numero_kg`: el redondeo sigue escrito una sola vez.
- **`totales()`** suma también la **lona sobrante** y avisa si hubo algún pedido con lona (`con_lona`). Con eso, el historial muestra la misma línea de lona que el PDF.

## 4. MODO PRUEBA en el PDF

Un informe de ejemplo nunca debe pasar por uno real:

1. **Franja amarilla** arriba de cada hoja: "MODO PRUEBA – DATOS DE EJEMPLO. NO ES UN INFORME REAL".
2. **Marca de agua** "DATOS DE EJEMPLO" en diagonal, en rojo muy suave. Va encima de todo para que el fondo de las tablas no la tape, y es transparente para que se pueda leer.
3. **Nombre del archivo** con el prefijo `PRUEBA_`.

## 5. [tests/test_informe.py](../tests/test_informe.py): las pruebas

Son **85 pruebas** en total (16 nuevas). La más importante comprueba que **el PDF y el historial muestran las mismas cifras** ([test_informe.py:66](../tests/test_informe.py#L66)):

```python
for cifra in ("190", "9.77 kg", "0.75 kg"):
    self.assertIn(cifra, historial)
    self.assertIn(cifra, texto)
self.assertNotIn("0.74", texto)   # el redondeo de los 5 hacia arriba también vale en el PDF
```

Para eso, `texto_del_pdf()` abre el PDF por dentro (las hojas vienen comprimidas) y extrae lo que tiene escrito, sin instalar otra librería. Otras pruebas revisan que la papelera no entre al informe, que los filtros lleguen al PDF y a su nombre, que sin registros no se genere, que funcione sin logo y que el MODO PRUEBA marque cada hoja. Igual que antes, todas usan bases temporales y Pylint da 10/10.

---

## Decisiones técnicas destacadas

1. **Una sola consulta para pantalla y PDF:** el historial y el informe comparten filtros, cálculos y redondeo, así que nunca pueden mostrar números distintos. Una prueba automática lo comprueba leyendo el texto del PDF.
2. **Generador de PDF independiente:** `informe_pdf.py` no conoce la web ni la base de datos; recibe datos y devuelve bytes. Es fácil de probar y se podrá reutilizar (por ejemplo, para enviar el informe por otro medio).
3. **Informe que se adapta a cualquier periodo:** semana, rango de fechas o todo, con o sin filtros; el título y el nombre del archivo se forman solos y las fechas en el nombre permiten ordenar los informes en una carpeta.
4. **Diseño pensado para imprimir:** A4 horizontal, títulos repetidos en cada hoja, resúmenes que no se parten y "Página X de Y".
5. **Tolerante a fallos:** sin logo o sin registros, la app no se cae; avisa y sigue funcionando.
6. **Informes de prueba imposibles de confundir:** franja, marca de agua y prefijo en el nombre cuando se genera desde el MODO PRUEBA.
