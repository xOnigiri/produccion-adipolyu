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
    """Comprueba que la base exista y tenga las 3 tablas."""
    conexion = conectar(ruta)
    try:
        filas = conexion.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        tablas = {fila["name"] for fila in filas}
    finally:
        conexion.close()
    faltan = TABLAS_NECESARIAS - tablas
    if faltan:
        raise BaseNoDisponible(
            f"A la base {ruta} le faltan las tablas: {', '.join(sorted(faltan))}. "
            "Ejecuta crear_base.py."
        )


def listar_piezas_activas(conexion):
    return conexion.execute(
        "SELECT id, nombre FROM piezas WHERE activo = 1 ORDER BY nombre"
    ).fetchall()


def listar_materiales_activos(conexion):
    return conexion.execute(
        "SELECT id, nombre FROM materiales WHERE activo = 1 ORDER BY nombre"
    ).fetchall()


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


def obtener_registro(conexion, registro_id):
    """Un registro con los nombres de su pieza y material."""
    return conexion.execute(
        """
        SELECT produccion.*, piezas.nombre AS pieza, materiales.nombre AS material
        FROM produccion
        JOIN piezas ON piezas.id = produccion.pieza_id
        JOIN materiales ON materiales.id = produccion.material_id
        WHERE produccion.id = ?
        """,
        (registro_id,),
    ).fetchone()
