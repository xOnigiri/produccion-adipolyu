"""Reglas del taller para aceptar un registro de producción
y los nombres de piezas y materiales.

No sabe nada de Flask ni de la base de datos: recibe lo que llegó del
formulario (todo es texto) y devuelve los datos limpios o los errores.
Por eso se puede probar sola.
"""

import re
import unicodedata
from dataclasses import dataclass
from datetime import date

from crear_base import DUREZAS_SHORE_A
from formato import texto_gramos

# Límites de sentido común para atrapar errores de tipeo (un cero de más)
MAX_GRAMOS = 1_000_000  # 1000 kg en un solo pedido
MAX_CANTIDAD = 100_000
MAX_OBSERVACIONES = 500
MAX_NOMBRE = 40  # nombre de una pieza o material

# Número con decimales opcionales, ya con la coma cambiada por punto: 3600 o 3600.5
_NUMERO = re.compile(r"-?\d+(\.\d+)?")
_ENTERO = re.compile(r"-?\d+")


@dataclass(frozen=True)
class ParDePesos:
    """Un par recibido/sobrante (material o lona) y cómo nombrarlo en los mensajes."""

    campo_recibido: str
    campo_sobrante: str
    nombre_recibido: str
    nombre_sobrante: str
    recibido_corto: str
    prefijo_vacio: str = "Anota"


MATERIAL = ParDePesos(
    campo_recibido="material_recibido_g",
    campo_sobrante="material_sobrante_g",
    nombre_recibido="el material recibido",
    nombre_sobrante="el material sobrante",
    recibido_corto="el recibido",
)

LONA = ParDePesos(
    campo_recibido="lona_recibida_g",
    campo_sobrante="lona_sobrante_g",
    nombre_recibido="la lona recibida",
    nombre_sobrante="la lona sobrante",
    recibido_corto="la recibida",
    prefijo_vacio="Si el pedido lleva lona, anota",
)


def leer_numero(texto):
    """Convierte '3600,5' o '3600.5' en 3600.5. Devuelve None si no es un número.

    Rechaza a propósito formatos ambiguos como '3.600,5' o '1e3'.
    """
    texto = texto.strip().replace(",", ".")
    if not _NUMERO.fullmatch(texto):
        return None
    return float(texto)


def validar_registro(formulario, piezas_validas, materiales_validos, hoy=None):
    """Revisa un registro enviado desde el formulario.

    piezas_validas / materiales_validos: ids de las opciones activas.
    Devuelve (registro, errores). Si hay errores, registro es None y
    errores es un diccionario {nombre_del_campo: mensaje}.
    """
    hoy = hoy or date.today()
    errores = {}
    registro = {}

    registro["fecha"] = _validar_fecha(formulario, hoy, errores)
    registro["pieza_id"] = _validar_opcion(
        formulario, "pieza_id", piezas_validas, "Elige una pieza de la lista.", errores
    )
    registro["material_id"] = _validar_opcion(
        formulario, "material_id", materiales_validos, "Elige un material de la lista.", errores
    )
    registro["dureza_shore_a"] = _validar_dureza(formulario, errores)
    registro["cantidad"] = _validar_cantidad(formulario, errores)
    registro["material_recibido_g"], registro["material_sobrante_g"] = _validar_par_de_pesos(
        formulario, MATERIAL, errores
    )

    # Si no lleva lona, los campos de lona se ignoran y quedan vacíos
    registro["lleva_lona"] = 1 if formulario.get("lleva_lona") == "si" else 0
    if registro["lleva_lona"]:
        registro["lona_recibida_g"], registro["lona_sobrante_g"] = _validar_par_de_pesos(
            formulario, LONA, errores
        )
    else:
        registro["lona_recibida_g"] = None
        registro["lona_sobrante_g"] = None

    registro["observaciones"] = _validar_observaciones(formulario, errores)

    if errores:
        return None, errores
    return registro, {}


def _validar_fecha(formulario, hoy, errores):
    texto = formulario.get("fecha", "").strip()
    try:
        fecha = date.fromisoformat(texto)
    except ValueError:
        errores["fecha"] = "Elige la fecha del pedido."
        return None
    if fecha > hoy:
        errores["fecha"] = "La fecha no puede ser futura."
        return None
    return fecha.isoformat()


def _validar_opcion(formulario, campo, ids_validos, mensaje, errores):
    texto = formulario.get(campo, "").strip()
    if not texto.isdigit() or int(texto) not in ids_validos:
        errores[campo] = mensaje
        return None
    return int(texto)


def _validar_dureza(formulario, errores):
    """Opcional: vacío = sin dato. Si viene, debe ser una de la lista (60, 65 … 100)."""
    texto = formulario.get("dureza_shore_a", "").strip()
    if not texto:
        return None
    if not texto.isdigit() or int(texto) not in DUREZAS_SHORE_A:
        errores["dureza_shore_a"] = "Elige una dureza de la lista o «— sin dato —»."
        return None
    return int(texto)


def _validar_cantidad(formulario, errores):
    texto = formulario.get("cantidad", "").strip()
    if not texto:
        errores["cantidad"] = "Anota la cantidad de piezas producidas."
        return None
    if not _ENTERO.fullmatch(texto):
        if leer_numero(texto) is not None:
            errores["cantidad"] = "La cantidad debe ser un número entero de piezas."
        else:
            errores["cantidad"] = "Escribe la cantidad solo con números, por ejemplo 50."
        return None
    cantidad = int(texto)
    if cantidad <= 0:
        errores["cantidad"] = "La cantidad debe ser mayor que 0."
        return None
    if cantidad > MAX_CANTIDAD:
        errores["cantidad"] = (
            f"La cantidad parece demasiado grande ({cantidad}). Revisa si sobra un cero."
        )
        return None
    return cantidad


def _validar_par_de_pesos(formulario, par, errores):
    """Valida recibido y sobrante, y que el sobrante no supere lo recibido."""
    recibido = _validar_gramos(
        formulario, par.campo_recibido, par.nombre_recibido, par.prefijo_vacio, errores
    )
    if recibido == 0:
        errores[par.campo_recibido] = f"{_mayuscula(par.nombre_recibido)} debe ser mayor que 0."
        recibido = None

    sobrante = _validar_gramos(
        formulario, par.campo_sobrante, par.nombre_sobrante, par.prefijo_vacio, errores
    )
    if recibido is not None and sobrante is not None and sobrante > recibido:
        errores[par.campo_sobrante] = (
            f"{_mayuscula(par.nombre_sobrante)} ({texto_gramos(sobrante)} g) no puede ser "
            f"mayor que {par.recibido_corto} ({texto_gramos(recibido)} g)."
        )
        sobrante = None
    return recibido, sobrante


def _validar_gramos(formulario, campo, nombre, prefijo_vacio, errores):
    """Lee un peso en gramos (acepta coma o punto). Permite 0; no permite negativos."""
    texto = formulario.get(campo, "").strip()
    if not texto:
        errores[campo] = f"{prefijo_vacio} {nombre} en gramos (ejemplo: 3600,5)."
        return None
    gramos = leer_numero(texto)
    if gramos is None:
        errores[campo] = (
            f"Escribe {nombre} solo con números, con coma o punto decimal (ejemplo: 3600,5)."
        )
        return None
    if gramos < 0:
        errores[campo] = f"{_mayuscula(nombre)} no puede ser menor que 0."
        return None
    if gramos > MAX_GRAMOS:
        errores[campo] = (
            f"{_mayuscula(nombre)} parece demasiado grande ({texto_gramos(gramos)} g). "
            "Revisa si sobra un cero."
        )
        return None
    return gramos


def _validar_observaciones(formulario, errores):
    texto = formulario.get("observaciones", "").strip()
    if len(texto) > MAX_OBSERVACIONES:
        errores["observaciones"] = (
            f"Las observaciones pueden tener hasta {MAX_OBSERVACIONES} caracteres."
        )
        return None
    return texto or None


def _mayuscula(texto):
    return texto[0].upper() + texto[1:]


def limpiar_nombre(texto):
    """Cómo se guarda un nombre: '  Silicona   NARANJA ' -> 'silicona naranja'."""
    return " ".join(unicodedata.normalize("NFC", texto).split()).lower()


def clave_nombre(texto):
    """Lo que se compara para detectar duplicados: sin mayúsculas, sin espacios
    de más y sin tildes ('Retén', ' RETEN ' y 'reten' -> 'reten'). La ñ se respeta."""
    letras = []
    for letra in unicodedata.normalize("NFD", limpiar_nombre(texto)):
        # En la forma NFD la tilde va aparte: 'é' = 'e' + tilde; 'ñ' = 'n' + virgulilla
        es_enie = letra == "̃" and letras and letras[-1] == "n"
        if unicodedata.combining(letra) and not es_enie:
            continue
        letras.append(letra)
    return unicodedata.normalize("NFC", "".join(letras))


def validar_nombre(texto, existentes, propio=None):
    """Revisa el nombre de una pieza o material nuevo, o el corregido.

    existentes: toda la lista (activos e inactivos), con id y nombre.
    propio: el que se está corrigiendo; None si es nuevo. Puede cambiar solo en
    tildes o mayúsculas ('reten' -> 'retén') porque sigue siendo el mismo.
    Devuelve (nombre, error, repetido); repetido es el que ya usa ese nombre.
    """
    nombre = limpiar_nombre(texto)
    if not nombre:
        return None, "Escribe el nombre.", None
    if len(nombre) > MAX_NOMBRE:
        return None, f"El nombre puede tener hasta {MAX_NOMBRE} caracteres.", None
    if propio is not None and nombre == propio["nombre"]:
        return None, "Es el mismo nombre que ya tiene. Escribe el nombre corregido.", None

    clave = clave_nombre(nombre)
    for fila in existentes:
        es_el_mismo = propio is not None and fila["id"] == propio["id"]
        if not es_el_mismo and clave_nombre(fila["nombre"]) == clave:
            return None, f"Ya existe «{fila['nombre']}».", fila
    return nombre, None, None
