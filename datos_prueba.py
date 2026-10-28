"""Base de prueba con datos de ejemplo, para el MODO PRUEBA.

Sirve para practicar (corregir, borrar, restaurar) y para mostrar la app a
otras personas sin tocar ni enseñar los registros reales del taller.
Los pedidos de ejemplo son inventados y caen en la semana actual y la pasada.

Para empezar de nuevo con los datos de ejemplo, basta con borrar
produccion_prueba.db: el MODO PRUEBA la vuelve a crear al abrirse.
"""

from datetime import date, timedelta
from pathlib import Path

import base_datos
import calculos
import crear_base

RUTA_PRUEBA = Path(__file__).parent / "produccion_prueba.db"

# (día desde el lunes de la semana pasada, pieza, material, dureza Shore A o None,
#  cantidad, material recibido g, material sobrante g,
#  (lona recibida g, lona sobrante g) o None, observaciones, va a la papelera)
PEDIDOS_DE_EJEMPLO = [
    (0, "retén", "nitrilo", 70, 50, 3600.5, 400, (250, 30), "2 piezas con burbuja", False),
    (1, "anillo", "silicona naranja", None, 120, 2000, 150, None, None, False),
    (2, "soporte", "jebe natural", 60, 30, 4500, 320.5, None, None, False),
    (3, "anillo", "nitrilo", 70, 100, 1700, 90, None, "Anotado dos veces por error", True),
    (4, "amortiguador", "jebe azul", 80, 20, 5200, 480, (600, 75), None, False),
    (5, "anillo", "silicona transparente", None, 200, 1800, 95.5, None, "Pedido urgente", False),
    (7, "retén", "nitrilo", 75, 60, 4300, 250, (300, 40), None, False),
    (7, "anillo", "jebe blanco", None, 150, 1500, 120, None, None, False),
    (8, "soporte", "jebe celeste", 65, 25, 3900, 310, None, "3 piezas con rebaba gruesa",
     False),
    (9, "amortiguador", "jebe natural", 60, 18, 4800, 365.5, (550, 60), None, False),
    (10, "retén", "silicona naranja", None, 80, 2600, 210, None, None, False),
]


class RutaNoPermitida(Exception):
    """Se intentó usar la base real como base de prueba."""


def preparar_base_prueba(ruta=RUTA_PRUEBA, hoy=None):
    """Deja lista la base de prueba. Devuelve (ruta, recién_creada).

    Si no existe, la crea con las listas y los pedidos de ejemplo.
    Si ya existe, la deja como está (solo le agrega columnas nuevas si le faltan).
    """
    ruta = Path(ruta)
    if ruta.resolve() == base_datos.RUTA_POR_DEFECTO.resolve():
        raise RutaNoPermitida("La base de prueba no puede ser produccion.db.")

    recien_creada = not ruta.exists()
    crear_base.crear_base(ruta, informar=False)
    if recien_creada:
        _cargar_ejemplos(ruta, hoy or date.today())
    return ruta, recien_creada


def _cargar_ejemplos(ruta, hoy):
    lunes_pasado = calculos.semana_de(hoy)[0] - timedelta(days=7)
    conexion = base_datos.conectar(ruta)
    try:
        piezas = {
            fila["nombre"]: fila["id"] for fila in base_datos.listar_todas_las_piezas(conexion)
        }
        materiales = {
            fila["nombre"]: fila["id"]
            for fila in base_datos.listar_todos_los_materiales(conexion)
        }
        for pedido in PEDIDOS_DE_EJEMPLO:
            fecha = lunes_pasado + timedelta(days=pedido[0])
            if fecha > hoy:  # nunca fechas futuras
                continue
            registro_id = base_datos.guardar_registro(
                conexion, _registro(fecha, pedido, piezas, materiales)
            )
            if pedido[-1]:  # va a la papelera
                base_datos.enviar_a_papelera(conexion, registro_id)
    finally:
        conexion.close()


def _registro(fecha, pedido, piezas, materiales):
    """Convierte una fila de PEDIDOS_DE_EJEMPLO en un registro listo para guardar.
    piezas / materiales: nombre -> id."""
    _, pieza, material, dureza, cantidad, recibido, sobrante, lona, nota, _ = pedido
    return {
        "fecha": fecha.isoformat(),
        "pieza_id": piezas[pieza],
        "material_id": materiales[material],
        "dureza_shore_a": dureza,
        "lleva_lona": 1 if lona else 0,
        "cantidad": cantidad,
        "material_recibido_g": recibido,
        "material_sobrante_g": sobrante,
        "lona_recibida_g": lona[0] if lona else None,
        "lona_sobrante_g": lona[1] if lona else None,
        "observaciones": nota,
    }
