# Recorrido del código – Parte 7: administrar piezas y materiales

Explicación en lenguaje sencillo de la página "Listas", con los fragmentos clave.
Aprobada el 27/10/2026.

## La idea general: nombres que se corrigen, nunca se borran

```
piezas / materiales        produccion
id  nombre    activo       id  pieza_id ...
3   retén     1      ←──── 15  3
```

Cada registro guarda el **número** (id) de su pieza y su material, no el nombre. Por eso corregir un nombre lo cambia en todo el historial y en los PDF sin reescribir ningún registro. Para quitar un nombre del formulario, se **desactiva** (`activo = 0`): sus registros antiguos se siguen viendo.

La estructura de la base no cambia en esta parte: no se agrega ninguna tabla ni columna.

---

## 1. [validacion.py](../validacion.py): limpiar el nombre y detectar duplicados

```python
def limpiar_nombre(texto):
    return " ".join(unicodedata.normalize("NFC", texto).split()).lower()
```

([validacion.py:211](../validacion.py#L211)). Así se guarda un nombre: sin espacios de más y en minúsculas. `"  Silicona   NARANJA "` → `"silicona naranja"`.

`clave_nombre()` ([validacion.py:216](../validacion.py#L216)) prepara la versión que se compara para detectar duplicados. Además de limpiar el nombre, le quita las tildes: "Retén", " RETEN " y "reten" dan la misma clave, `reten`. La ñ se respeta ("caña" no es "cana").

`validar_nombre()` ([validacion.py:229](../validacion.py#L229)) usa esa clave:

```python
es_el_mismo = propio is not None and fila["id"] == propio["id"]
if not es_el_mismo and clave_nombre(fila["nombre"]) == clave:
    return None, f"Ya existe «{fila['nombre']}».", fila
```

Al corregir un nombre, la comparación salta el propio nombre. Por eso "reten" → "retén" se permite: es la misma pieza. Si el nombre repetido está inactivo, la página ofrece reactivarlo.

La base tiene una segunda barrera (`UNIQUE COLLATE NOCASE`), pero esa no reconoce tildes ni mayúsculas acentuadas. Por eso la revisión principal se hace en Python.

## 2. [base_datos.py](../base_datos.py): uso, cambios y la regla del último activo

`listar_con_uso()` ([base_datos.py:108](../base_datos.py#L108)) trae toda la lista con dos conteos: registros vigentes y registros en la papelera.

```sql
COUNT(produccion.id) - COUNT(produccion.borrado_en) AS registros,
COUNT(produccion.borrado_en) AS en_papelera
```

`desactivar()` ([base_datos.py:144](../base_datos.py#L144)) hace la comprobación del último activo **dentro de la misma orden**. No hay un momento entre "contar" y "desactivar" en el que algo pueda cambiar:

```sql
UPDATE {tabla} SET activo = 0
WHERE id = ? AND activo = 1
  AND (SELECT COUNT(*) FROM {tabla} WHERE activo = 1) > 1
```

Las funciones solo aceptan las tablas `piezas` y `materiales` (`_tabla_de_lista()`, [base_datos.py:102](../base_datos.py#L102)), porque el nombre de la tabla va dentro del SQL. Ninguna función borra filas.

## 3. [app.py](../app.py): las páginas

| Dirección | Qué hace |
|---|---|
| `/listas` | Las dos listas con estado y uso ([app.py:420](../app.py#L420)) |
| `/listas/<tipo>/agregar` | Agrega un nombre limpio y revisado ([app.py:440](../app.py#L440)) |
| `/listas/<tipo>/<id>/nombre` | Corregir en dos pasos: revisar y confirmar ([app.py:462](../app.py#L462)) |
| `/listas/<tipo>/<id>/desactivar` | Lo saca del formulario ([app.py:502](../app.py#L502)) |
| `/listas/<tipo>/<id>/reactivar` | Lo devuelve al formulario ([app.py:523](../app.py#L523)) |

`<tipo>` solo puede ser `piezas` o `materiales`. Cualquier otro valor da "no encontrado".

La clase `Lista` ([app.py:65](../app.py#L65)) guarda cómo nombrar cada lista en los mensajes ("la pieza… activa" / "el material… activo"). Así una sola página sirve para las dos.

**Corregir en dos pasos:** el primer envío (`paso=revisar`) solo valida y muestra *«reten» → «retén» · Afecta a 3 registros (y 1 en la papelera)*. Solo el segundo envío (`paso=confirmar`) guarda, y vuelve a validar antes.

## 4. Las páginas: [listas.html](../templates/listas.html) y [corregir_nombre.html](../templates/corregir_nombre.html)

- Las activas aparecen primero y las inactivas en gris.
- La columna Registros muestra el número y, debajo, "+1 en papelera".
- En el último activo, en lugar de "Desactivar" aparece el aviso *"Debe quedar al menos una pieza activa. Agrega o reactiva otra primero."*
- En el historial, los filtros marcan los nombres inactivos: "retén (inactiva)".

## 5. [crear_base.py](../crear_base.py): las listas iniciales no reaparecen

```python
def cargar_lista_inicial(conexion, tabla, nombres):
    if conexion.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0]:
        return 0
```

([crear_base.py:93](../crear_base.py#L93)). Antes, `crear_base.py` agregaba cualquier nombre inicial que faltara. Como el MODO PRUEBA lo ejecuta en cada arranque, un nombre corregido ("jebe azul" → "jebe azul marino") habría vuelto a aparecer. Ahora las listas iniciales se cargan solo en una lista vacía, es decir, en una base nueva.

## 6. Pruebas automáticas

Son **137 pruebas** (30 nuevas en [tests/test_listas.py](../tests/test_listas.py)), todas sobre bases temporales:

```python
def test_corregir_solo_la_tilde_reten_a_reten_con_tilde(self):
    self.ejecutar("UPDATE piezas SET nombre = 'reten' WHERE nombre = 'retén'")
    ...
    self.assertEqual(self.pieza(id_reten)["nombre"], "retén")
```

Revisan:
- Duplicados con tildes, mayúsculas y espacios.
- La ñ.
- La oferta de reactivar un nombre inactivo repetido.
- La confirmación con conteo antes de guardar.
- Que el registro siga apuntando a la misma pieza.
- Que una pieza inactiva siga en el historial, el filtro, el PDF y en la corrección de registros antiguos.
- El último activo, también enviando el botón a mano.
- Que ninguna acción borre filas.
- Que `crear_base.py` no devuelva un nombre corregido.

Pylint da 10/10.

---

## Decisiones técnicas destacadas

1. **Referencias por id:** corregir un nombre no reescribe registros. El historial y los informes quedan siempre coherentes.
2. **Desactivar en vez de borrar:** ningún registro antiguo queda huérfano y todo cambio es reversible.
3. **Duplicados según cómo se lee, no según cómo se escribe:** mayúsculas, tildes y espacios no crean nombres distintos. Corregir solo la tilde del propio nombre sí se permite.
4. **Confirmación informada:** antes de corregir un nombre se muestra a cuántos registros afecta.
5. **Reglas en la base, no solo en la pantalla:** el último activo se protege en la misma orden SQL, y la base rechaza duplicados como segunda barrera.
6. **Arranques sin efectos secundarios:** volver a ejecutar `crear_base.py` nunca deshace cambios hechos desde la página.
