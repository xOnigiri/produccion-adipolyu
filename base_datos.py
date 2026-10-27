"""Acceso a produccion.db. Es el único archivo de la app que escribe SQL.

La app nunca crea ni modifica las tablas: eso lo hace solo crear_base.py.
"""

import os
import sqlite3
from pathlib import Path

RUTA_POR_DEFECTO = Path(__file__).parent / "produccion.db"

# Permite apuntar la app a una copia de la base (para pruebas) sin tocar la real
VARIABLE_RUTA = "ADIPOLYU_DB"

TABLAS_NECESARIAS = {"piezas", "materiales", "produccion"}

# Columnas que llegaron después de la primera versión de la base
COLUMNAS_NECESARIAS = {"produccion": {"borrado_en"}}


class BaseNoDisponible(Exception):
    """La base no existe o le faltan tablas."""


def ruta_base():
    return Path(os.environ.get(VARIABLE_RUTA, RUTA_POR_DEFECTO))


def conectar(ruta):
    """Abre una base que ya existe. Si no existe, falla en vez de crear una vacía."""
    uri = f"{Path(ruta).resolve().as_uri()}?mode=rw"
    try:
        conexion = sqlite3.connect(uri, uri=True)
    except sqlite3.OperationalError as error:
        raise BaseNoDisponible(
            f"No se encontró la base de datos en {ruta}. "
            "Si es la primera vez, ejecuta crear_base.py."
        ) from error
    conexion.row_factory = sqlite3.Row
    conexion.execute("PRAGMA foreign_keys = ON")
    return conexion


def verificar_base(ruta):
    """Comprueba que la base exista y tenga las 3 tablas con sus columnas nuevas."""
    conexion = conectar(ruta)
    try:
        filas = conexion.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        tablas = {fila["name"] for fila in filas}
        faltan = TABLAS_NECESARIAS - tablas
        if faltan:
            raise BaseNoDisponible(
                f"A la base {ruta} le faltan las tablas: {', '.join(sorted(faltan))}. "
                "Ejecuta crear_base.py."
            )
        for tabla, columnas in COLUMNAS_NECESARIAS.items():
            existentes = {fila["name"] for fila in conexion.execute(f"PRAGMA table_info({tabla})")}
            faltan = columnas - existentes
            if faltan:
                raise BaseNoDisponible(
                    f"A la base {ruta} le faltan columnas nuevas en {tabla}: "
                    f"{', '.join(sorted(faltan))}. Ejecuta crear_base.py "
                    "(agrega lo que falta sin borrar nada)."
                )
    finally:
        conexion.close()


def listar_piezas_activas(conexion, incluir_id=None):
    """Piezas activas. incluir_id suma una pieza desactivada: la de un registro
    antiguo que se está corrigiendo, para que no se pierda al guardar."""
    return conexion.execute(
        "SELECT id, nombre FROM piezas WHERE activo = 1 OR id = ? ORDER BY nombre",
        (incluir_id,),
    ).fetchall()


def listar_materiales_activos(conexion, incluir_id=None):
    """Igual que listar_piezas_activas, para materiales."""
    return conexion.execute(
        "SELECT id, nombre FROM materiales WHERE activo = 1 OR id = ? ORDER BY nombre",
        (incluir_id,),
    ).fetchall()


def listar_todas_las_piezas(conexion):
    """Activas y desactivadas: para filtrar el historial, que tiene registros antiguos."""
    return conexion.execute("SELECT id, nombre FROM piezas ORDER BY nombre").fetchall()


def listar_todos_los_materiales(conexion):
    return conexion.execute("SELECT id, nombre FROM materiales ORDER BY nombre").fetchall()


def guardar_registro(conexion, registro):
    """Guarda un registro ya validado y devuelve su id."""
    with conexion:  # confirma si todo sale bien; deshace si hay error
        cursor = conexion.execute(
            """
            INSERT INTO produccion (
                fecha, pieza_id, material_id, lleva_lona, cantidad,
                material_recibido_g, material_sobrante_g,
                lona_recibida_g, lona_sobrante_g, observaciones
            ) VALUES (
                :fecha, :pieza_id, :material_id, :lleva_lona, :cantidad,
                :material_recibido_g, :material_sobrante_g,
                :lona_recibida_g, :lona_sobrante_g, :observaciones
            )
            """,
            registro,
        )
    return cursor.lastrowid


_SELECT_CON_NOMBRES = """
    SELECT produccion.*, piezas.nombre AS pieza, materiales.nombre AS material
    FROM produccion
    JOIN piezas ON piezas.id = produccion.pieza_id
    JOIN materiales ON materiales.id = produccion.material_id
"""


def obtener_registro(conexion, registro_id):
    """Un registro con los nombres de su pieza y material (esté o no en la papelera).
    Devuelve None si no existe."""
    return conexion.execute(
        _SELECT_CON_NOMBRES + " WHERE produccion.id = ?", (registro_id,)
    ).fetchone()


def listar_registros(conexion, desde=None, hasta=None, pieza_id=None, material_id=None):
    """Registros vigentes (no los de la papelera), del más reciente al más antiguo.

    desde / hasta: fechas 'AAAA-MM-DD' incluidas; None = sin límite.
    pieza_id / material_id: None = todas / todos.
    """
    condiciones = ["produccion.borrado_en IS NULL"]
    valores = []
    for condicion, valor in (
        ("produccion.fecha >= ?", desde),
        ("produccion.fecha <= ?", hasta),
        ("produccion.pieza_id = ?", pieza_id),
        ("produccion.material_id = ?", material_id),
    ):
        if valor is not None:
            condiciones.append(condicion)
            valores.append(valor)
    # Misma fecha: primero el último que se escribió (id más alto)
    return conexion.execute(
        _SELECT_CON_NOMBRES
        + " WHERE " + " AND ".join(condiciones)
        + " ORDER BY produccion.fecha DESC, produccion.id DESC",
        valores,
    ).fetchall()


def listar_papelera(conexion):
    """Registros en la papelera, del último borrado al primero."""
    return conexion.execute(
        _SELECT_CON_NOMBRES
        + " WHERE produccion.borrado_en IS NOT NULL"
        + " ORDER BY produccion.borrado_en DESC, produccion.id DESC"
    ).fetchall()


def actualizar_registro(conexion, registro_id, registro):
    """Reemplaza los datos de un registro vigente con los ya validados.
    Devuelve True si se corrigió (False si no existe o está en la papelera)."""
    with conexion:
        cursor = conexion.execute(
            """
            UPDATE produccion SET
                fecha = :fecha, pieza_id = :pieza_id, material_id = :material_id,
                lleva_lona = :lleva_lona, cantidad = :cantidad,
                material_recibido_g = :material_recibido_g,
                material_sobrante_g = :material_sobrante_g,
                lona_recibida_g = :lona_recibida_g, lona_sobrante_g = :lona_sobrante_g,
                observaciones = :observaciones
            WHERE id = :id AND borrado_en IS NULL
            """,
            {**registro, "id": registro_id},
        )
    return cursor.rowcount == 1


def enviar_a_papelera(conexion, registro_id):
    """Marca el registro como borrado (no lo elimina). Devuelve True si se movió."""
    with conexion:
        cursor = conexion.execute(
            "UPDATE produccion SET borrado_en = datetime('now', 'localtime') "
            "WHERE id = ? AND borrado_en IS NULL",
            (registro_id,),
        )
    return cursor.rowcount == 1


def restaurar_registro(conexion, registro_id):
    """Saca un registro de la papelera. Devuelve True si se restauró."""
    with conexion:
        cursor = conexion.execute(
            "UPDATE produccion SET borrado_en = NULL WHERE id = ? AND borrado_en IS NOT NULL",
            (registro_id,),
        )
    return cursor.rowcount == 1
