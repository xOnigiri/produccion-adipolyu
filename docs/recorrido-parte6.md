# Recorrido del código – Parte 6: respaldo a Google Drive

Explicación en lenguaje sencillo de cómo funciona el botón "Exportar respaldo", con los fragmentos clave y el procedimiento para restaurar un respaldo.
Aprobada el 27/10/2026.

## La idea general: una foto de la base, revisada y guardada en Drive

```
produccion.db ──foto (SQLite)──→ carpeta temporal ──revisión──→ G:\Mi unidad\ADIPOLYU\respaldos-produccion\
                                                                   2026-10-27_18-40-05\
                                                                     produccion_2026-10-27_18-40-05.db
                                                                     (archivos de respaldo_extra.txt)
                                                                     resumen.txt
```

El archivo `.db` que usa la app se queda en la carpeta del proyecto. A Drive solo van **copias**, cada una en una carpeta nueva con la fecha y la hora. Google Drive para escritorio (unidad G:) las sube a la nube en segundo plano.

Los archivos nuevos son `respaldo.py` (toda la lógica, sin nada de la web) y la página `respaldo.html`. `app.py` solo agrega la página, el botón y el aviso de 7 días.

---

## 1. [respaldo.py](../respaldo.py): a dónde va cada respaldo

```python
DRIVE = Destino(CARPETA_DRIVE, UNIDAD_DRIVE, "Google Drive")
PRUEBA = Destino(CARPETA_PRUEBA, CARPETA_PROYECTO, "carpeta de práctica", en_drive=False)
```

([respaldo.py:54-55](../respaldo.py#L54-L55)). `configuracion()` ([respaldo.py:81](../respaldo.py#L81)) elige el destino según la base que usa la app:

| La app usa… | El respaldo va a… |
|---|---|
| `produccion.db` (la base real) | Google Drive, con los archivos de `respaldo_extra.txt` |
| MODO PRUEBA | `respaldos\prueba\` en la laptop; nunca a Drive |
| Cualquier otra copia | Ningún lado: el botón queda desactivado |

Además, `hacer_respaldo()` ([respaldo.py:104](../respaldo.py#L104)) se niega a enviar a Drive cualquier base que no sea `produccion.db`, aunque se lo pidan.

## 2. La foto: copia segura con la app abierta

```python
origen.execute("BEGIN")
conteo = _contar(origen)
origen.backup(copia)
```

([respaldo.py:154-175](../respaldo.py#L154-L175)). No se copia el archivo como con Ctrl+C, porque si justo se guarda un pedido, la copia podría quedar a medias. Se usa la **copia oficial de SQLite** (*backup*), y el conteo de filas y la copia ocurren dentro de una misma lectura: mientras dura ese instante, nadie puede dejar un pedido guardado a medias.

La foto se toma en una carpeta temporal de la laptop, porque SQLite trabaja mal directamente sobre la unidad virtual de Drive.

## 3. La revisión: sana e idéntica

Antes de copiar a Drive, `_revisar_foto()` ([respaldo.py:190](../respaldo.py#L190)) comprueba:
1. Que tenga las 3 tablas y la columna de la papelera.
2. La revisión interna de SQLite (`PRAGMA integrity_check`) da "ok".
3. Que tenga la **misma cantidad de filas** que la base original (piezas, materiales, registros y los de la papelera).

Después de copiar, `_copiar_verificando()` ([respaldo.py:249](../respaldo.py#L249)) **vuelve a leer el archivo desde G:** y compara su huella SHA-256 (un código que cambia si cambia un solo byte) con la del original. Si no coinciden, el respaldo se da por fallido.

## 4. Nunca sobrescribir, nunca salir de la carpeta

- **Carpeta nueva cada vez** ([respaldo.py:207](../respaldo.py#L207)): mientras se copia se llama `2026-10-27_18-40-05_EN-CURSO`. Si todo se verifica, se renombra a `2026-10-27_18-40-05`. Si algo falla, queda como `_FALLIDO`. No se borra nada.
- **Mismo segundo, otro nombre:** un doble clic crea `..._2` en vez de reemplazar el primero.
- **Archivos que no se pisan** ([respaldo.py:269](../respaldo.py#L269)): se escriben en modo `"xb"`, que falla si el archivo ya existe.
- **Barrera** ([respaldo.py:296](../respaldo.py#L296)): antes de cada escritura o cambio de nombre, `_comprobar_dentro()` verifica que el destino quede dentro de `respaldos-produccion`. Nada fuera de esa subcarpeta (por ejemplo, otros archivos de `ADIPOLYU`) puede modificarse.
- **En Drive solo se crea la última carpeta** ([respaldo.py:219](../respaldo.py#L219)): si `G:\Mi unidad` o `ADIPOLYU` no existen, la app avisa y no crea nada.
- **Uno a la vez:** un candado evita dos respaldos simultáneos.

## 5. Archivos adicionales y resumen

`respaldo_extra.txt` es un archivo local (fuera de Git) con un archivo por línea, por ejemplo, notas del proyecto que no se versionan. Cada uno se copia y se verifica por huella. Si alguno no existe, se avisa en amarillo, pero la base sí se respalda.

`resumen.txt` anota la fecha, el equipo, cuántos registros tiene la copia (vigentes y en la papelera), la revisión de SQLite y las huellas de cada archivo. Sirve para comprobar una restauración.

## 6. [app.py](../app.py) y [respaldo.html](../templates/respaldo.html): la página y los avisos

| Dirección | Qué hace |
|---|---|
| `/respaldo` (abrir) | Muestra destino (✔ Disponible / ✖ No disponible), último respaldo y qué se guarda. No escribe nada ([app.py:379](../app.py#L379)) |
| `/respaldo` (botón) | Hace el respaldo y muestra el resultado ([app.py:395](../app.py#L395)) |

**Mensajes:**
- Verde: "Respaldo verificado en … · 12 registros (1 en la papelera) · …", más el recordatorio de esperar a que Drive termine de subirlo.
- Rojo: el motivo exacto. Por ejemplo, "Google Drive no está disponible… Abre Google Drive para escritorio, inicia sesión… No se hizo el respaldo."
- Amarillo: en MODO PRUEBA, "respaldo de práctica… no se envió a Google Drive".

**Aviso de 7 días** ([app.py:442](../app.py#L442)): si pasaron 7 días o más desde el último respaldo verificado (o nunca hubo uno), aparece una franja naranja en todas las páginas, con un enlace a Respaldo. La fecha se anota en `respaldos\ultimo_respaldo.txt`, en la laptop: el aviso funciona aunque Drive esté cerrado y no se cambia la estructura de la base.

## 7. Pruebas automáticas

Son **107 pruebas** (22 nuevas en [tests/test_respaldo.py](../tests/test_respaldo.py)). Usan un "Drive falso" en carpetas temporales, con una carpeta `ADIPOLYU` y un video de ejemplo:

```python
def test_no_toca_nada_de_adipolyu_fuera_de_respaldos(self):
    self.respaldar()
    self.respaldar(ahora=AHORA + timedelta(minutes=1))
    self.assertEqual(sorted(ruta.name for ruta in self.adipolyu.iterdir()),
                     ["ADIPOLYU_animacion.mp4", "respaldos-produccion"])
```

Revisan también: Drive cerrado (error y nada escrito), carpeta ADIPOLYU ausente (no se crea nada), dos respaldos en el mismo segundo, una copia dañada a propósito (queda `_FALLIDO`), un respaldo mientras otro programa está guardando un pedido, que el MODO PRUEBA nunca use Drive y el aviso de 7 días. Pylint da 10/10.

---

## Cómo restaurar un respaldo (procedimiento manual)

La app **no restaura nada sola**. Si algún día hace falta:

1. **Cierra la app** (las ventanas negras de "Iniciar app.bat" y del modo prueba).
2. En la carpeta del proyecto, **mueve** el `produccion.db` actual a `respaldos\` y renómbralo `produccion_reemplazada_AAAA-MM-DD.db`. No lo borres: es la red de seguridad si se elige el respaldo equivocado.
3. Abre `G:\Mi unidad\ADIPOLYU\respaldos-produccion\` y elige la carpeta del respaldo. Usa una sin `_EN-CURSO` ni `_FALLIDO`.
4. **Copia** su archivo `produccion_….db` a la carpeta del proyecto y renómbralo exactamente `produccion.db`.
5. (Recomendado) Ábrelo en DB Browser for SQLite y compara la cantidad de registros con su `resumen.txt`.
6. Abre la app y revisa el historial y la papelera.
7. Si también se perdieron los archivos adicionales, cópialos desde la misma carpeta del respaldo a la carpeta del proyecto.

---

## Decisiones técnicas destacadas

1. **Copia en caliente con la API oficial de SQLite:** la foto es coherente aunque la app esté abierta y alguien esté guardando un pedido.
2. **Verificación de punta a punta:** la integridad de SQLite, la misma cantidad de filas y la huella SHA-256 releída desde el destino. Un respaldo solo se da por bueno si pasa las tres.
3. **Escritura sin sobrescribir y en dos pasos:** carpeta `_EN-CURSO` que se renombra al terminar, archivos creados en modo exclusivo y fallos marcados como `_FALLIDO` sin borrar nada.
4. **Alcance limitado por diseño:** toda escritura pasa por una barrera que solo permite la subcarpeta de respaldos. En Drive no se crean carpetas superiores.
5. **Separación de entornos:** la base real va a Drive, el MODO PRUEBA a una carpeta local y cualquier otra copia no se respalda.
6. **Fallos visibles:** Drive cerrado, carpeta ausente o copia distinta generan un mensaje claro. Nunca se informa "listo" sin verificación.
7. **Restauración manual y documentada:** la app nunca reemplaza la base por su cuenta.
