"""Cómo se muestran fechas y pesos en pantalla.

Se usa en el formulario y el historial, y se reutilizará en el informe PDF,
para que todo muestre los números de la misma forma.
"""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from calculos import lona_usada_g, material_usado_g


def redondear(valor, decimales):
    """Redondeo de toda la app: los que terminan en 5 suben (0.745 -> 0.75).

    No se usa el redondeo de Python porque la computadora guarda 0.745 como
    0.74499999… y además lleva los 5 al número par. Aquí se parte del número
    tal como se escribe (str) y se limpia el ruido de las sumas a 9 decimales.
    """
    exacto = Decimal(str(valor)).quantize(Decimal("1e-9"), ROUND_HALF_UP)
    return exacto.quantize(Decimal(1).scaleb(-decimales), ROUND_HALF_UP)


def _sin_ceros_sobrantes(numero):
    """Decimal('3600.50') -> '3600.5' y Decimal('400.00') -> '400'."""
    texto = format(numero, "f")
    return texto.rstrip("0").rstrip(".") if "." in texto else texto


def texto_fecha(fecha_iso):
    """'2026-10-22' -> '22/10/2026'."""
    return date.fromisoformat(fecha_iso).strftime("%d/%m/%Y")


def texto_fecha_hora(texto):
    """'2026-10-27 18:40:12' -> '27/10/2026 18:40'."""
    fecha, _, hora = texto.partition(" ")
    return f"{texto_fecha(fecha)} {hora[:5]}".strip()


def texto_gramos(gramos):
    """3600.5 -> '3600.5' y 400.0 -> '400' (sin ceros sobrantes, hasta 2 decimales)."""
    return _sin_ceros_sobrantes(redondear(gramos, 2))


def numero_kg(gramos):
    """3200.5 g -> '3.20' y 745 g -> '0.75' (sin la unidad, para tablas con '(kg)' arriba)."""
    kilos = Decimal(str(gramos)) / 1000  # división exacta, sin ruido
    return format(redondear(kilos, 2), "f")


def texto_kg(gramos):
    """3200.5 g -> '3.20 kg' y 745 g -> '0.75 kg'."""
    return f"{numero_kg(gramos)} kg"


def numero_g_por_pieza(gramos):
    """64.01 -> '64' y 15.45 -> '15.5' (un decimal basta para el promedio)."""
    return _sin_ceros_sobrantes(redondear(gramos, 1))


def texto_g_por_pieza(gramos):
    """64.01 -> '64 g' y 15.45 -> '15.5 g'."""
    return numero_g_por_pieza(gramos) + " g"


def describir_registro(registro):
    """'22/10/2026 · retén · nitrilo · con lona · 50 unidades · material usado 3.20 kg ...'.
    Recibe una fila de produccion con los nombres de pieza y material ya unidos
    (ver base_datos.obtener_registro)."""
    partes = [
        texto_fecha(registro["fecha"]),
        registro["pieza"],
        registro["material"],
        "con lona" if registro["lleva_lona"] else "sin lona",
        f"{registro['cantidad']} {'unidad' if registro['cantidad'] == 1 else 'unidades'}",
        "material usado " + texto_kg(material_usado_g(registro)),
    ]
    if registro["lleva_lona"]:
        partes.append("lona usada " + texto_kg(lona_usada_g(registro)))
    return " · ".join(partes)


def resumen_registro(registro):
    """Frase que confirma lo guardado."""
    return "Registro guardado: " + describir_registro(registro)
