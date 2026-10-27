# Recorrido del código – Parte 4: historial, corregir, borrar y papelera

Explicación en lenguaje sencillo de cómo funcionan el historial, la corrección y el borrado de registros, con los fragmentos clave de cada archivo.
Aprobada el 27/10/2026.

## La idea general: tres caminos para un registro guardado

Una vez guardado, un pedido puede **verse**, **corregirse** o **ir a la papelera** (y volver de ella):

```
                      ┌─ Ver ──────→ historial.html  (tabla, filtros, totales)
                      │
produccion.db ─ app.py┼─ Corregir ─→ registrar.html  (el mismo formulario, ya lleno)
                      │                → validacion.py (las mismas reglas)
                      │
                      └─ Borrar ───→ confirmar_borrado.html → Papelera ⇄ Restaurar

calculos.py: usado, lona usada, g por pieza, totales   (se calcula, no se guarda)
formato.py:  cómo se muestra cada número               (redondeo único para toda la app)
```

Igual que en la Parte 3, cada archivo tiene **un solo trabajo**. Los archivos nuevos son `calculos.py` (las cuentas) y `datos_prueba.py` (el MODO PRUEBA). El resto creció sin cambiar su función.

---

## 1. [crear_base.py](../crear_base.py): la papelera sin perder datos

La papelera necesita una columna nueva en `produccion`: **`borrado_en`**. Si está vacía, el registro está vigente. Si tiene fecha y hora, está en la papelera.

Una base que ya está en uso no se puede recrear, así que la columna se agrega con un **cambio controlado** ([crear_base.py:75-88](../crear_base.py#L75-L88)):

```python
COLUMNAS_NUEVAS = [
    ("produccion", "borrado_en", "TEXT"),  # Parte 4: papelera
]

def agregar_columnas_nuevas(conexion):
    for tabla, columna, tipo in COLUMNAS_NUEVAS:
        existentes = {fila[1] for fila in conexion.execute(f"PRAGMA table_info({tabla})")}
        if columna not in existentes:
            conexion.execute(f"ALTER TABLE {tabla} ADD COLUMN {columna} {tipo}")
```

- **Solo agrega lo que falta.** Si la columna ya existe, no hace nada. Por eso `crear_base.py` se puede ejecutar las veces que sea.
- **Los registros existentes no cambian:** reciben la columna vacía, es decir, "vigentes".
- **Lista ordenada de cambios:** si en el futuro llega otra columna (por ejemplo, piezas defectuosas), se agrega una línea a `COLUMNAS_NUEVAS`. Es una versión mínima de lo que en la industria se llama *migraciones*.
- **Se puede aplicar a una copia:** `python crear_base.py copia.db`. Así se probó primero sobre copias y luego sobre la base real.

Del otro lado, [base_datos.py:44](../base_datos.py#L44) revisa al arrancar que la columna exista. Si alguien abre la app con una base antigua, la app **se detiene con un aviso** ("ejecuta crear_base.py") en vez de fallar a la mitad.

## 2. [base_datos.py](../base_datos.py): leer, corregir, mover a la papelera

**Borrar no elimina, marca** ([base_datos.py:186](../base_datos.py#L186)):

```python
UPDATE produccion SET borrado_en = datetime('now', 'localtime')
WHERE id = ? AND borrado_en IS NULL
```

El pedido sigue en la base, solo marcado. **Restaurar** hace lo contrario: vuelve a dejar `borrado_en` vacío. El `AND borrado_en IS NULL` evita que un doble clic "vuelva a borrar" y cambie la hora del primer borrado.

**El historial solo ve lo vigente** ([base_datos.py:131](../base_datos.py#L131)):

```python
condiciones = ["produccion.borrado_en IS NULL"]
for condicion, valor in (("produccion.fecha >= ?", desde), ("produccion.fecha <= ?", hasta),
                         ("produccion.pieza_id = ?", pieza_id), ...):
    if valor is not None:
        condiciones.append(condicion)
...
" ORDER BY produccion.fecha DESC, produccion.id DESC"
```

- Cada filtro se agrega **solo si se eligió**. "Todas las piezas" simplemente no agrega la condición de pieza.
- **Orden:** primero la fecha más reciente. Si dos pedidos tienen la misma fecha, va primero el último que se escribió (el número `id` más alto).
- Los valores van separados de la orden SQL (`?`), igual que en la Parte 3, como protección contra la *inyección SQL*.

**Corregir no pierde piezas retiradas** ([base_datos.py:69](../base_datos.py#L69)):

```python
"SELECT id, nombre FROM piezas WHERE activo = 1 OR id = ? ORDER BY nombre"
```

Cuando en la Parte 7 se desactive una pieza, los registros antiguos que la usan seguirán corrigiéndose sin que la pieza desaparezca de la lista. `OR id = ?` agrega solo esa pieza, solo para ese registro.

## 3. [calculos.py](../calculos.py): las cuentas del taller

```python
def material_usado_g(registro):
    return registro["material_recibido_g"] - registro["material_sobrante_g"]

def gramos_por_pieza(registro):
    return material_usado_g(registro) / registro["cantidad"]   # 3200.5 ÷ 50 = 64 g

def semana_de(fecha):
    lunes = fecha - timedelta(days=fecha.weekday())
    return lunes, lunes + timedelta(days=6)                     # lunes a domingo
```

`totales()` ([calculos.py:33](../calculos.py#L33)) recorre los registros de un periodo y devuelve el número de pedidos, las piezas, los kg usados de material y lona, y dos resúmenes: **por material** (usado y sobrante) y **por pieza** (unidades).

- **Nada de esto se guarda.** Si se corrige un dato, todos los cálculos se actualizan en la siguiente visita.
- **Trabaja siempre en gramos.** Pasar a kg es tarea de `formato.py`.
- El informe PDF de la Parte 5 **reutilizará `totales()` tal cual**. Así, el historial y el PDF nunca pueden mostrar números distintos.

## 4. [formato.py](../formato.py): un solo redondeo para toda la app

**El problema:** la computadora guarda 0.745 como 0.74499999…, y además Python redondea los 5 hacia el número par. Por eso un total de lona de 745 g aparecía como 0.74 kg, mientras las filas (525 g → 0.53 y 220 g → 0.22) sumaban 0.75.

**La solución** ([formato.py:13](../formato.py#L13)):

```python
def redondear(valor, decimales):
    exacto = Decimal(str(valor)).quantize(Decimal("1e-9"), ROUND_HALF_UP)
    return exacto.quantize(Decimal(1).scaleb(-decimales), ROUND_HALF_UP)
```

En sencillo:
1. **`Decimal(str(valor))`** parte del número tal como se escribe ("0.745"), no de su versión interna aproximada.
2. **Primer redondeo, a 9 decimales:** limpia el "ruido" de las sumas. Por ejemplo, 1234.4 + 1.1 da 1235.4999999999998 en la computadora y aquí vuelve a ser 1235.5.
3. **`ROUND_HALF_UP`:** los valores terminados en 5 siempre suben, como se enseña en el colegio.

Todos los textos de números usan esta función: `texto_kg` (0.75 kg), `texto_gramos` (3600.5 g) y `texto_g_por_pieza` (15.5 g). La regla vive en **un solo lugar** y el PDF la heredará.

El total del periodo se calcula con los gramos exactos y se redondea al final, no sumando los kg ya redondeados de cada fila. Es la forma correcta de no acumular errores.

`describir_registro()` ([formato.py:57](../formato.py#L57)) arma la frase "22/10/2026 · retén · nitrilo · con lona · 50 unidades · material usado 3.20 kg". La usan el mensaje de "Registro guardado", el de "Registro corregido", la confirmación de borrado y la papelera.

## 5. [app.py](../app.py): las páginas nuevas

| Dirección | Qué hace |
|---|---|
| `/historial` | Tabla con filtros y totales ([app.py:154](../app.py#L154)) |
| `/registro/15/corregir` | Formulario lleno con el registro 15; al enviarlo, guarda los cambios ([app.py:181](../app.py#L181)) |
| `/registro/15/borrar` | Pantalla "¿Borrar este registro?"; al confirmar, lo envía a la papelera ([app.py:218-240](../app.py#L218-L240)) |
| `/papelera` | Registros borrados, con el botón Restaurar ([app.py:243](../app.py#L243)) |

**Corregir usa las mismas reglas que registrar** ([app.py:181](../app.py#L181)):

```python
registro, errores = validar_registro(request.form, piezas_validas=..., materiales_validos=...)
if not errores:
    base_datos.actualizar_registro(_conexion(), registro_id, registro)
```

Es la **misma función** `validar_registro` de la Parte 3. No existe una "versión para corregir" de las reglas, así que nunca pueden quedar distintas.

**Volver al mismo filtro** ([app.py:297](../app.py#L297)): al corregir o borrar desde, por ejemplo, "Semana pasada + nitrilo", la app regresa a esa misma vista. La dirección de regreso viaja con el formulario y la app **solo acepta direcciones del propio historial**. Una dirección externa se ignora y lleva al historial normal.

**Mostrar no es borrar:** abrir `/registro/15/borrar` solo muestra la pregunta. Borrar ocurre únicamente al apretar "Sí, borrar", que envía el formulario (método POST). Así, un enlace abierto por error o una página precargada por el navegador nunca borran nada.

**Filtros tolerantes** ([app.py:306](../app.py#L306)): si la dirección trae algo raro (un periodo que no existe, letras en vez de un número), la app usa el valor por defecto en vez de fallar. Si "desde" es posterior a "hasta", muestra un aviso en rojo.

## 6. [historial.html](../templates/historial.html) y [estilos.css](../static/estilos.css): la tabla tipo Excel

- **Columnas:** Acciones · Fecha · Pieza · Material · Lona · Cant. · Mat. recibido · Mat. sobrante · **Mat. usado** · **g por pieza** · Lona recibida · Lona sobrante · **Lona usada** · Observaciones.
- **Unidades:** recibido y sobrante en **gramos**, como los marca la balanza (3600.5 g). Usado en **kg** y consumo por pieza en **g**. Los totales del periodo, en **kg**.
- Las columnas calculadas tienen un **fondo celeste suave**, para distinguir lo que se escribió de lo que calcula la app.
- Sin lona, las tres columnas de lona muestran "—".

**Acciones siempre visibles** ([estilos.css:417](../static/estilos.css#L417)):

```css
.tabla .acciones {
  position: sticky;
  left: 0;
  background: var(--tarjeta);
}
```

Es el equivalente a **"Inmovilizar primera columna" en Excel**. Corregir y Borrar van al inicio de la fila y, aunque la tabla se desplace a la derecha en una ventana angosta, esa columna se queda en su lugar. Necesita fondo propio para tapar las columnas que pasan por debajo. Las observaciones largas bajan de línea (`overflow-wrap: anywhere`) en vez de estirar la tabla.

**Formulario reutilizado:** [registrar.html](../templates/registrar.html) sirve para registrar y para corregir. Si recibe un registro (`corrigiendo`), cambia el título, el botón ("Guardar cambios") y agrega "Cancelar". Un solo formulario significa que cualquier mejora futura aplica a los dos usos.

**Menú** ([base.html](../templates/base.html)): Registrar · Historial · Papelera, con la página actual resaltada.

## 7. [datos_prueba.py](../datos_prueba.py) e [Iniciar modo prueba.bat](../Iniciar%20modo%20prueba.bat): el MODO PRUEBA

Sirve para practicar (corregir, borrar, restaurar) y para mostrar la app **sin tocar ni enseñar los registros reales**.

```python
def preparar_base_prueba(ruta=RUTA_PRUEBA, hoy=None):
    if ruta.resolve() == base_datos.RUTA_POR_DEFECTO.resolve():
        raise RutaNoPermitida("La base de prueba no puede ser produccion.db.")
```

Tiene **cuatro barreras** para no confundirse con la app real:
1. **Otro archivo:** `produccion_prueba.db`. La función se niega a usar `produccion.db`, aunque se lo pidan.
2. **Otro puerto:** 5001 en vez de 5000. Las dos apps pueden estar abiertas a la vez sin mezclarse.
3. **Franja amarilla** "MODO PRUEBA" en todas las páginas y "[PRUEBA]" en la pestaña del navegador.
4. **Ventana negra con fondo amarillo** y un título que dice MODO PRUEBA.

Los pedidos de ejemplo son inventados y se calculan **a partir del día de hoy**: siempre caen en la semana actual y la pasada, sin fechas futuras. Uno de ellos viene en la papelera para poder probar "Restaurar". Para volver al inicio, basta con borrar `produccion_prueba.db`: el MODO PRUEBA la vuelve a crear.

## 8. [tests/](../tests/): las pruebas automáticas

Son **69 pruebas** (25 de la Parte 3 y 44 nuevas). Se ejecutan con `.venv\Scripts\python -m unittest`. Algunos casos:

```python
def test_total_redondea_igual_que_las_filas(self):
    # Filas: 525 g -> 0.53 kg y 220 g -> 0.22 kg. Total: 745 g -> 0.75 kg (no 0.74)
    self.insertar(HOY, material="jebe azul", lona=(600, 75))
    self.insertar(HOY)
    html = self.html("/historial")
    self.assertIn("0.75 kg", html)
    self.assertNotIn("0.74 kg", html)
```

- **`test_calculos.py`:** cuentas, semana de lunes a domingo, totales y todos los casos de redondeo.
- **`test_historial.py`:** ver, filtros, corregir (con las mismas reglas que registrar), borrar, papelera y restaurar.
- **`test_base.py`:** que la columna `borrado_en` se agregue sin tocar los registros, que la app no abra una base antigua y que el MODO PRUEBA nunca use la base real.

Todas trabajan sobre **bases temporales** que se borran solas al terminar (`enterContext`). Una clase común, `PruebaConBase`, prepara esa base para las pruebas de páginas, así la preparación no se repite en cada archivo. Además, el código pasa el revisor de estilo **Pylint con 10/10**. Solo se desactivó la regla que exige un comentario de explicación (docstring) en cada función, porque el proyecto los usa donde el nombre no basta.

---

## Decisiones técnicas destacadas

1. **Borrado lógico (papelera recuperable):** borrar marca el registro con fecha y hora en vez de eliminarlo. Un error se deshace con un clic, y los registros borrados quedan fuera del historial y de los totales.
2. **Cambio de estructura sin pérdida de datos:** la columna nueva se agrega con un cambio controlado que solo añade lo que falta, se puede repetir sin riesgo y se probó primero sobre copias. Al arrancar, la app comprueba que la base tenga la estructura esperada.
3. **Una sola fuente de verdad:** las reglas de validación, los cálculos (`calculos.py`) y el redondeo (`formato.redondear`) están escritos una vez y los reutilizan el registro, la corrección, el historial y el futuro informe PDF.
4. **Redondeo decimal exacto:** se usa aritmética decimal con redondeo de los 5 hacia arriba, en vez del redondeo binario de la computadora, para que los totales cuadren con lo que se ve.
5. **Acciones seguras:** borrar y restaurar solo ocurren al confirmar (POST), nunca al abrir un enlace. La dirección de regreso solo acepta páginas del propio historial.
6. **Entorno de demostración aislado:** el MODO PRUEBA usa otra base, otro puerto y avisos visibles, y tiene un bloqueo que impide apuntarlo a los datos reales.
7. **Tabla usable en cualquier ancho:** la columna de acciones queda fija a la izquierda, como "inmovilizar columna" en una hoja de cálculo.
