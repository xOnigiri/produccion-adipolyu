"""Crea la base de datos produccion.db con sus 3 tablas y las listas iniciales.

Se puede ejecutar varias veces sin riesgo: nunca borra ni sobrescribe datos.
Solo crea las tablas que falten y agrega las piezas/materiales que no existan.
"""

import sqlite3
from pathlib import Path

RUTA_DB = Path(__file__).parent / "produccion.db"

PIEZAS_INICIALES = ["anillo", "soporte", "retén", "amortiguador"]

MATERIALES_INICIALES = [
    "jebe natural",
    "nitrilo",
    "silicona naranja",
    "silicona transparente",
    "jebe blanco",
    "jebe azul",
    "jebe celeste",
]

ESQUEMA = """
CREATE TABLE IF NOT EXISTS piezas (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    activo INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1))
);

CREATE TABLE IF NOT EXISTS materiales (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    activo INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1))
);

CREATE TABLE IF NOT EXISTS produccion (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    -- Fecha en formato AAAA-MM-DD; se rechaza una fecha inválida
    fecha               TEXT    NOT NULL CHECK (date(fecha) IS NOT NULL AND fecha = date(fecha)),
    pieza_id            INTEGER NOT NULL REFERENCES piezas (id) ON DELETE RESTRICT,
    material_id         INTEGER NOT NULL REFERENCES materiales (id) ON DELETE RESTRICT,
    lleva_lona          INTEGER NOT NULL CHECK (lleva_lona IN (0, 1)),
    cantidad            INTEGER NOT NULL CHECK (cantidad > 0),
    material_recibido_g REAL    NOT NULL CHECK (material_recibido_g >= 0),
    material_sobrante_g REAL    NOT NULL CHECK (material_sobrante_g >= 0),
    lona_recibida_g     REAL,
    lona_sobrante_g     REAL,
    observaciones       TEXT,
    registrado_en       TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),

    CHECK (material_sobrante_g <= material_recibido_g),
    -- Sin lona: campos de lona vacíos. Con lona: ambos llenos y sobrante <= recibida
    CHECK (
        (lleva_lona = 0 AND lona_recibida_g IS NULL AND lona_sobrante_g IS NULL)
        OR
        (lleva_lona = 1
         AND lona_recibida_g IS NOT NULL
         AND lona_sobrante_g IS NOT NULL
         AND lona_sobrante_g >= 0
         AND lona_sobrante_g <= lona_recibida_g)
    )
);
"""


def crear_base():
    ya_existia = RUTA_DB.exists()

    conexion = sqlite3.connect(RUTA_DB)
    try:
        conexion.execute("PRAGMA foreign_keys = ON")
        conexion.executescript(ESQUEMA)

        # INSERT OR IGNORE: si el nombre ya está, no lo duplica
        nuevas_piezas = 0
        for nombre in PIEZAS_INICIALES:
            cursor = conexion.execute(
                "INSERT OR IGNORE INTO piezas (nombre) VALUES (?)", (nombre,)
            )
            nuevas_piezas += cursor.rowcount

        nuevos_materiales = 0
        for nombre in MATERIALES_INICIALES:
            cursor = conexion.execute(
                "INSERT OR IGNORE INTO materiales (nombre) VALUES (?)", (nombre,)
            )
            nuevos_materiales += cursor.rowcount

        conexion.commit()

        total_piezas = conexion.execute("SELECT COUNT(*) FROM piezas").fetchone()[0]
        total_materiales = conexion.execute("SELECT COUNT(*) FROM materiales").fetchone()[0]
        total_registros = conexion.execute("SELECT COUNT(*) FROM produccion").fetchone()[0]
    finally:
        conexion.close()

    if ya_existia:
        print(f"La base ya existía en {RUTA_DB}. No se borró nada.")
    else:
        print(f"Base creada en {RUTA_DB}")
    print(f"Piezas: {total_piezas} ({nuevas_piezas} agregadas ahora)")
    print(f"Materiales: {total_materiales} ({nuevos_materiales} agregados ahora)")
    print(f"Registros de producción: {total_registros}")


if __name__ == "__main__":
    crear_base()
