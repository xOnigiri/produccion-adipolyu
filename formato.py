"""Cómo se muestran fechas y pesos en pantalla.

Se usa en el formulario y se reutilizará en el historial y el informe PDF,
para que todo muestre los números de la misma forma.
"""

from datetime import date


def texto_fecha(fecha_iso):
    """'2026-10-22' -> '22/10/2026'."""
    return date.fromisoformat(fecha_iso).strftime("%d/%m/%Y")


def texto_gramos(gramos):
    """3600.5 -> '3600.5' y 400.0 -> '400' (sin ceros sobrantes)."""
    return f"{gramos:.2f}".rstrip("0").rstrip(".")


def texto_kg(gramos):
    """3200.5 g -> '3.20 kg'."""
    return f"{gramos / 1000:.2f} kg"


def resumen_registro(registro):
    """Frase que confirma lo guardado. Recibe una fila de produccion con los
    nombres de pieza y material ya unidos (ver base_datos.obtener_registro)."""
    partes = [
        texto_fecha(registro["fecha"]),
        registro["pieza"],
        registro["material"],
        "con lona" if registro["lleva_lona"] else "sin lona",
        f"{registro['cantidad']} {'unidad' if registro['cantidad'] == 1 else 'unidades'}",
        "material usado "
        + texto_kg(registro["material_recibido_g"] - registro["material_sobrante_g"]),
    ]
    if registro["lleva_lona"]:
        partes.append(
            "lona usada " + texto_kg(registro["lona_recibida_g"] - registro["lona_sobrante_g"])
        )
    return "Registro guardado: " + " · ".join(partes)
