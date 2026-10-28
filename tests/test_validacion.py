"""Pruebas de las reglas del taller (no usan base de datos)."""

import unittest
from datetime import date

from validacion import leer_numero, validar_registro

HOY = date(2026, 10, 27)
PIEZAS = {1, 2, 3, 4}
MATERIALES = {1, 2, 3, 4, 5, 6, 7}


def formulario(**cambios):
    """Un pedido válido (retén de nitrilo sin lona) con los cambios indicados."""
    datos = {
        "fecha": "2026-10-22",
        "pieza_id": "3",
        "material_id": "2",
        "cantidad": "50",
        "material_recibido_g": "3600.5",
        "material_sobrante_g": "400",
        "observaciones": "",
    }
    datos.update(cambios)
    return datos


def validar(datos):
    return validar_registro(datos, PIEZAS, MATERIALES, hoy=HOY)


class LeerNumeroTest(unittest.TestCase):
    def test_coma_y_punto_son_lo_mismo(self):
        self.assertEqual(leer_numero("3600,5"), 3600.5)
        self.assertEqual(leer_numero("3600.5"), 3600.5)
        self.assertEqual(leer_numero(" 400 "), 400.0)

    def test_rechaza_formatos_ambiguos_o_raros(self):
        for texto in ["3.600,5", "1e3", "nan", "inf", "abc", "", "3600,", ",5"]:
            with self.subTest(texto=texto):
                self.assertIsNone(leer_numero(texto))


class RegistroValidoTest(unittest.TestCase):
    def test_pedido_sin_lona(self):
        registro, errores = validar(formulario())
        self.assertEqual(errores, {})
        self.assertEqual(registro["fecha"], "2026-10-22")
        self.assertEqual(registro["pieza_id"], 3)
        self.assertEqual(registro["cantidad"], 50)
        self.assertEqual(registro["material_recibido_g"], 3600.5)
        self.assertEqual(registro["lleva_lona"], 0)
        self.assertIsNone(registro["lona_recibida_g"])
        self.assertIsNone(registro["observaciones"])

    def test_pedido_con_lona_y_coma_decimal(self):
        registro, errores = validar(
            formulario(
                material_recibido_g="3600,5",
                lleva_lona="si",
                lona_recibida_g="250",
                lona_sobrante_g="30,5",
                observaciones="  2 piezas con burbuja  ",
            )
        )
        self.assertEqual(errores, {})
        self.assertEqual(registro["material_recibido_g"], 3600.5)
        self.assertEqual(registro["lleva_lona"], 1)
        self.assertEqual(registro["lona_sobrante_g"], 30.5)
        self.assertEqual(registro["observaciones"], "2 piezas con burbuja")

    def test_sobrante_cero_e_igual_a_recibido_son_validos(self):
        for sobrante in ["0", "3600.5"]:
            with self.subTest(sobrante=sobrante):
                _, errores = validar(formulario(material_sobrante_g=sobrante))
                self.assertEqual(errores, {})

    def test_fecha_de_hoy_es_valida(self):
        _, errores = validar(formulario(fecha="2026-10-27"))
        self.assertEqual(errores, {})

    def test_sin_lona_ignora_valores_de_lona(self):
        registro, errores = validar(formulario(lona_recibida_g="250", lona_sobrante_g="30"))
        self.assertEqual(errores, {})
        self.assertIsNone(registro["lona_recibida_g"])
        self.assertIsNone(registro["lona_sobrante_g"])


class RegistroConErroresTest(unittest.TestCase):
    # Se llama como los assert de unittest a propósito
    def assertError(self, datos, campo, contiene):  # pylint: disable=invalid-name
        registro, errores = validar(datos)
        self.assertIsNone(registro)
        self.assertIn(campo, errores)
        self.assertIn(contiene, errores[campo])

    def test_sobrante_mayor_que_recibido(self):
        self.assertError(
            formulario(material_sobrante_g="4000"),
            "material_sobrante_g",
            "El material sobrante (4000 g) no puede ser mayor que el recibido (3600,5 g).",
        )

    def test_lona_sobrante_mayor_que_recibida(self):
        self.assertError(
            formulario(lleva_lona="si", lona_recibida_g="250", lona_sobrante_g="300"),
            "lona_sobrante_g",
            "La lona sobrante (300 g) no puede ser mayor que la recibida (250 g).",
        )

    def test_lona_marcada_sin_datos(self):
        _, errores = validar(formulario(lleva_lona="si"))
        self.assertIn("Si el pedido lleva lona, anota la lona recibida", errores["lona_recibida_g"])
        self.assertIn("Si el pedido lleva lona, anota la lona sobrante", errores["lona_sobrante_g"])

    def test_material_recibido_cero(self):
        self.assertError(
            formulario(material_recibido_g="0"),
            "material_recibido_g",
            "El material recibido debe ser mayor que 0.",
        )

    def test_pesos_negativos_o_con_letras(self):
        self.assertError(
            formulario(material_sobrante_g="-5"), "material_sobrante_g", "menor que 0"
        )
        self.assertError(
            formulario(material_recibido_g="tres mil"), "material_recibido_g", "solo con números"
        )

    def test_peso_demasiado_grande(self):
        self.assertError(
            formulario(material_recibido_g="36005000"), "material_recibido_g", "sobra un cero"
        )

    def test_cantidad(self):
        casos = {
            "0": "mayor que 0",
            "-3": "mayor que 0",
            "12.5": "número entero",
            "12,5": "número entero",
            "abc": "solo con números",
            "": "Anota la cantidad",
        }
        for texto, mensaje in casos.items():
            with self.subTest(cantidad=texto):
                self.assertError(formulario(cantidad=texto), "cantidad", mensaje)

    def test_fecha_futura_o_invalida(self):
        self.assertError(formulario(fecha="2026-10-28"), "fecha", "no puede ser futura")
        self.assertError(formulario(fecha=""), "fecha", "Elige la fecha")
        self.assertError(formulario(fecha="2026-02-30"), "fecha", "Elige la fecha")

    def test_pieza_o_material_fuera_de_la_lista(self):
        self.assertError(formulario(pieza_id=""), "pieza_id", "Elige una pieza")
        self.assertError(formulario(pieza_id="99"), "pieza_id", "Elige una pieza")
        self.assertError(formulario(material_id="x"), "material_id", "Elige un material")

    def test_observaciones_muy_largas(self):
        self.assertError(formulario(observaciones="a" * 501), "observaciones", "500 caracteres")


if __name__ == "__main__":
    unittest.main()
