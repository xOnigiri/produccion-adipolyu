# Recorrido del código – Dureza (Shore A) por pedido

Explicación en lenguaje sencillo del campo de dureza, con los fragmentos clave.
Aprobado el 27/10/2026.

## La idea general

Cada pedido puede llevar la dureza del material en Shore A. Es **opcional**, porque en la silicona casi nunca se conoce. Solo se aceptan 60, 65, 70, 75, 80, 85, 90, 95 y 100. Si no hay dato, la app muestra "—".

---

## 1. [crear_base.py](../crear_base.py): la regla vive en la base

```python
DUREZAS_SHORE_A = (60, 65, 70, 75, 80, 85, 90, 95, 100)

DEFINICION_DUREZA = (
    "INTEGER CHECK (dureza_shore_a IS NULL OR dureza_shore_a IN ("
    + ", ".join(str(dureza) for dureza in DUREZAS_SHORE_A)
    + "))"
)
```

([crear_base.py:32](../crear_base.py#L32)). La lista de durezas se escribe una sola vez y de ahí salen la regla de la base, la validación y las listas desplegables. La base rechaza un 72 aunque alguien lo escriba a mano desde DB Browser.

La columna se agrega con el mismo mecanismo de la papelera ([crear_base.py:90](../crear_base.py#L90)): `crear_base.py` la añade solo si falta, vacía, y no toca los registros existentes. En una base nueva va al final de la tabla ([crear_base.py:70](../crear_base.py#L70)), igual que en una base antigua que la recibe después. Así las dos quedan con la misma estructura.

La app no abre una base sin esta columna (`COLUMNAS_NECESARIAS`, [base_datos.py:18](../base_datos.py#L18)). En ese caso indica que hay que ejecutar `crear_base.py`.

## 2. [validacion.py](../validacion.py): vacío o uno de la lista

```python
texto = formulario.get("dureza_shore_a", "").strip()
if not texto:
    return None
if not texto.isdigit() or int(texto) not in DUREZAS_SHORE_A:
    errores["dureza_shore_a"] = "Elige una dureza de la lista o «— sin dato —»."
```

([validacion.py:131](../validacion.py#L131)). Esta es la primera barrera, con un mensaje claro debajo del campo. La segunda barrera es la regla de la base.

## 3. Formulario, historial y papelera

- **Formulario** ([registrar.html:92](../templates/registrar.html#L92)): lista "Dureza (Shore A)" debajo de Material, con "— sin dato —" elegido de entrada. Al corregir un pedido aparece elegida la dureza guardada.
- **Mensaje de confirmación** (`describir_registro()`, [formato.py:72](../formato.py#L72)): incluye "70 Shore A" solo si el pedido tiene dureza.
- **Historial y papelera:** columna "Dureza (Shore A)" junto a Material, con "—" en gris si no hay dato (`texto_dureza()`, [formato.py:67](../formato.py#L67)).

## 4. Filtro por dureza

```python
if dureza == SIN_DUREZA:
    condiciones.append("produccion.dureza_shore_a IS NULL")
```

`listar_registros()` ([base_datos.py:209](../base_datos.py#L209)) acepta una dureza (solo los de 70, por ejemplo) o `"sin-dato"` (solo los que no la tienen). En el historial ([historial.html:53](../templates/historial.html#L53)), el filtro se combina con el periodo, la pieza y el material. Los totales se calculan sobre lo filtrado.

`_leer_dureza()` ([app.py:756](../app.py#L756)) ignora un valor que no está en la lista, por ejemplo `?dureza=72` escrito a mano en la dirección: en ese caso se muestran todas.

## 5. PDF

- Columna **"Dureza"** después de Material ([informe_pdf.py:53](../informe_pdf.py#L53)). Para hacerle espacio, Observaciones se angosta un poco.
- Con el filtro activo, el encabezado lo indica ("Dureza: 70 Shore A" o "Dureza: sin dato", [app.py:267](../app.py#L267)) y el nombre del archivo también: `..._shore-a-70.pdf` o `..._sin-dureza.pdf` ([app.py:351](../app.py#L351)).

## 6. MODO PRUEBA

En los pedidos de ejemplo ([datos_prueba.py:23](../datos_prueba.py#L23)), varios llevan dureza (60 a 80) y las siliconas quedan sin dato. Así se pueden ver los dos casos y probar el filtro.

## 7. Cambio en la base real

Se siguió el método de la papelera:
1. Copia de seguridad con huella SHA-256 verificada.
2. Ensayo en otra copia: se agregó la columna y se comprobó que piezas, materiales y registros quedaran idénticos, que la base no tuviera daños y que se rechazara 72 y se aceptara 70.
3. Recién entonces se agregó a la base real y se volvió a comparar con la copia de seguridad.

## 8. Pruebas automáticas

Son **162 pruebas** (25 nuevas en [tests/test_dureza.py](../tests/test_dureza.py)), todas sobre bases temporales. Revisan:
- Que la base acepte vacío y la lista, y rechace 72, 110, 70.5 o texto.
- Que una base antigua reciba la columna sin perder datos y quede igual a una base nueva.
- La validación.
- Guardar, corregir y quitar la dureza.
- La columna y el filtro del historial (incluido "sin dato").
- La papelera.
- La columna, el encabezado y el nombre del PDF.
- Los ejemplos del MODO PRUEBA.

Pylint no da avisos.

---

## Decisiones técnicas destacadas

1. **Una sola lista de durezas:** la regla de la base, la validación y los menús salen del mismo lugar, así que nunca se contradicen.
2. **Reglas en la base, no solo en la pantalla:** la base rechaza valores fuera de la lista aunque se escriban por fuera de la app.
3. **Vacío en vez de cero:** "sin dato" se guarda vacío, distinto de cualquier dureza real, y se puede filtrar aparte.
4. **Cambio de estructura sin riesgo:** copia de seguridad verificada, ensayo en copia y comparación fila por fila antes y después de tocar la base real.
5. **Misma estructura en bases nuevas y antiguas:** la columna va al final en ambos casos.
6. **Filtro coherente en pantalla y PDF:** el informe usa exactamente los mismos filtros que el historial y lo indica en el título y en el nombre del archivo.
