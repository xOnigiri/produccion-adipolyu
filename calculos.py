"""Lo que se calcula a partir de los registros y nunca se guarda.

Se calcula al momento para que, si se corrige un dato, todo lo demás se
actualice solo. Lo usan el historial y (en la Parte 5) el informe PDF.
Trabaja siempre en gramos; pasar a kg es cosa de formato.py.
"""

from datetime import timedelta


def material_usado_g(registro):
    return registro["material_recibido_g"] - registro["material_sobrante_g"]


def lona_usada_g(registro):
    """None si el pedido no lleva lona."""
    if not registro["lleva_lona"]:
        return None
    return registro["lona_recibida_g"] - registro["lona_sobrante_g"]


def gramos_por_pieza(registro):
    """Consumo promedio: material usado ÷ cantidad (ej. 3200.5 g ÷ 50 = 64 g)."""
    return material_usado_g(registro) / registro["cantidad"]


def semana_de(fecha):
    """(lunes, domingo) de la semana que contiene la fecha."""
    lunes = fecha - timedelta(days=fecha.weekday())
    return lunes, lunes + timedelta(days=6)


def totales(registros):
    """Totales de un grupo de registros (por ejemplo, los de una semana).

    por_material y por_pieza vienen ordenados por nombre.
    """
    por_material = {}
    por_pieza = {}
    lona_usada = 0.0
    for registro in registros:
        nombre = registro["material"]
        material = por_material.setdefault(
            nombre, {"material": nombre, "usado_g": 0.0, "sobrante_g": 0.0}
        )
        material["usado_g"] += material_usado_g(registro)
        material["sobrante_g"] += registro["material_sobrante_g"]

        por_pieza[registro["pieza"]] = por_pieza.get(registro["pieza"], 0) + registro["cantidad"]

        if registro["lleva_lona"]:
            lona_usada += lona_usada_g(registro)

    return {
        "pedidos": len(registros),
        "piezas": sum(por_pieza.values()),
        "material_usado_g": sum(m["usado_g"] for m in por_material.values()),
        "lona_usada_g": lona_usada,
        "por_material": [por_material[nombre] for nombre in sorted(por_material)],
        "por_pieza": [
            {"pieza": nombre, "cantidad": por_pieza[nombre]} for nombre in sorted(por_pieza)
        ],
    }
