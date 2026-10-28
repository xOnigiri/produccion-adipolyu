"""Crea la base de datos produccion.db con sus 3 tablas y las listas iniciales.

Se puede ejecutar varias veces sin riesgo: nunca borra ni sobrescribe datos.
Solo crea las tablas que falten, agrega las columnas nuevas que falten
(como borrado_en, de la papelera, o dureza_shore_a) y carga las piezas/materiales iniciales
en una lista vacía. Una lista que ya tiene nombres no se toca: así no
reaparece un nombre corregido o desactivado desde la página "Listas".

Uso:  python crear_base.py            (base real, produccion.db)
      python crear_base.py otra.db    (otra base, por ejemplo una copia)
"""

import sqlite3
import sys
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

# Durezas que se pueden anotar en un pedido (opcional). La base rechaza cualquier otra.
DUREZAS_SHORE_A = (60, 65, 70, 75, 80, 85, 90, 95, 100)

DEFINICION_DUREZA = (
    "INTEGER CHECK (dureza_shore_a IS NULL OR dureza_shore_a IN ("
    + ", ".join(str(dureza) for dureza in DUREZAS_SHORE_A)
    + "))"
)

ESQUEMA = f"""
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
    -- Vacío = registro vigente. Con fecha y hora = está en la papelera
    borrado_en          TEXT,
    -- Vacío = sin dato. Va al final, igual que en una base antigua que la recibe después
    dureza_shore_a      {DEFINICION_DUREZA},

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

# Columnas que se agregaron después de crear la base, en el orden en que llegaron.
# Una base antigua las recibe vacías; los registros que ya tiene no cambian.
COLUMNAS_NUEVAS = [
    ("produccion", "borrado_en", "TEXT"),  # Parte 4: papelera
    ("produccion", "dureza_shore_a", DEFINICION_DUREZA),  # dureza del material
]


def agregar_columnas_nuevas(conexion):
    """Agrega a una base antigua las columnas que le falten. Devuelve sus nombres."""
    agregadas = []
    for tabla, columna, tipo in COLUMNAS_NUEVAS:
        existentes = {fila[1] for fila in conexion.execute(f"PRAGMA table_info({tabla})")}
        if columna not in existentes:
            conexion.execute(f"ALTER TABLE {tabla} ADD COLUMN {columna} {tipo}")
            agregadas.append(columna)
    return agregadas


def cargar_lista_inicial(conexion, tabla, nombres):
    """Carga los nombres iniciales solo si la lista está vacía. Devuelve cuántos agregó."""
    if conexion.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0]:
        return 0
    conexion.executemany(f"INSERT INTO {tabla} (nombre) VALUES (?)", [(nombre,) for nombre in nombres])
    return len(nombres)


def crear_base(ruta=RUTA_DB, informar=True):
    ruta = Path(ruta)
    ya_existia = ruta.exists()

    conexion = sqlite3.connect(ruta)
    try:
        conexion.execute("PRAGMA foreign_keys = ON")
        conexion.executescript(ESQUEMA)
        columnas_agregadas = agregar_columnas_nuevas(conexion)

        nuevas_piezas = cargar_lista_inicial(conexion, "piezas", PIEZAS_INICIALES)
        nuevos_materiales = cargar_lista_inicial(conexion, "materiales", MATERIALES_INICIALES)
        conexion.commit()

        total_piezas = conexion.execute("SELECT COUNT(*) FROM piezas").fetchone()[0]
        total_materiales = conexion.execute("SELECT COUNT(*) FROM materiales").fetchone()[0]
        total_registros = conexion.execute("SELECT COUNT(*) FROM produccion").fetchone()[0]
    finally:
        conexion.close()

    if not informar:
        return
    if ya_existia:
        print(f"La base ya existía en {ruta}. No se borró nada.")
    else:
        print(f"Base creada en {ruta}")
    for columna in columnas_agregadas:
        print(f"Columna nueva agregada: {columna} (los registros existentes no cambian)")
    print(f"Piezas: {total_piezas} ({nuevas_piezas} agregadas ahora)")
    print(f"Materiales: {total_materiales} ({nuevos_materiales} agregados ahora)")
    print(f"Registros de producción: {total_registros}")


if __name__ == "__main__":
    crear_base(sys.argv[1] if len(sys.argv) > 1 else RUTA_DB)
