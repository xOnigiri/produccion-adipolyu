"""Pruebas de los cálculos y del formato de números (no usan base de datos)."""

import unittest
from datetime import date

from calculos import gramos_por_pieza, lona_usada_g, material_usado_g, semana_de, totales
from formato import (
    numero_g_por_pieza,
    numero_kg,
    redondear,
    texto_fecha_hora,
    texto_g_por_pieza,
    texto_gramos,
    texto_kg,
)


def registro(**cambios):
    """Retén de nitrilo con lona: 3600.5 g recibidos, 400 g sobrantes, 50 unidades."""
    datos = {
        "pieza": "retén",
        "material": "nitrilo",
        "lleva_lona": 1,
        "cantidad": 50,
        "material_recibido_g": 3600.5,
        "material_sobrante_g": 400.0,
        "lona_recibida_g": 250.0,
        "lona_sobrante_g": 30.0,
    }
    datos.update(cambios)
    return datos


SIN_LONA = {"lleva_lona": 0, "lona_recibida_g": None, "lona_sobrante_g": None}


class CalculosPorRegistroTest(unittest.TestCase):
    def test_material_usado(self):
        self.assertEqual(material_usado_g(registro()), 3200.5)

    def test_lona_usada(self):
        self.assertEqual(lona_usada_g(registro()), 220)

    def test_sin_lona_no_hay_lona_usada(self):
        self.assertIsNone(lona_usada_g(registro(**SIN_LONA)))

    def test_gramos_por_pieza(self):
        self.assertAlmostEqual(gramos_por_pieza(registro()), 64.01)
        self.assertEqual(texto_g_por_pieza(gramos_por_pieza(registro())), "64 g")
        self.assertEqual(texto_g_por_pieza(1850 / 120), "15.4 g")


class SemanaTest(unittest.TestCase):
    def test_semana_va_de_lunes_a_domingo(self):
        lunes, domingo = date(2026, 10, 26), date(2026, 11, 1)
        for dia in range(26, 32):
            self.assertEqual(semana_de(date(2026, 10, dia)), (lunes, domingo))
        self.assertEqual(semana_de(domingo), (lunes, domingo))

    def test_lunes_empieza_semana_nueva(self):
        self.assertEqual(semana_de(date(2026, 11, 2))[0], date(2026, 11, 2))


class TotalesTest(unittest.TestCase):
    def test_totales_por_material_y_pieza(self):
        resultado = totales(
            [
                registro(),
                registro(cantidad=30, material_recibido_g=1000, material_sobrante_g=100,
                         **SIN_LONA),
                registro(pieza="anillo", material="silicona naranja", cantidad=120,
                         material_recibido_g=2000, material_sobrante_g=150, **SIN_LONA),
            ]
        )
        self.assertEqual(resultado["pedidos"], 3)
        self.assertEqual(resultado["piezas"], 200)
        self.assertAlmostEqual(resultado["material_usado_g"], 3200.5 + 900 + 1850)
        self.assertEqual(resultado["lona_usada_g"], 220)
        self.assertEqual(
            resultado["por_material"],
            [
                {"material": "nitrilo", "usado_g": 4100.5, "sobrante_g": 500},
                {"material": "silicona naranja", "usado_g": 1850, "sobrante_g": 150},
            ],
        )
        self.assertEqual(
            resultado["por_pieza"],
            [{"pieza": "anillo", "cantidad": 120}, {"pieza": "retén", "cantidad": 80}],
        )

    def test_lona_usada_y_sobrante_del_periodo(self):
        resultado = totales([
            registro(lona_recibida_g=600, lona_sobrante_g=75),
            registro(),
            registro(**SIN_LONA),
        ])
        self.assertTrue(resultado["con_lona"])
        self.assertEqual(resultado["lona_usada_g"], 745)
        self.assertEqual(resultado["lona_sobrante_g"], 105)
        self.assertEqual(texto_kg(resultado["lona_sobrante_g"]), "0.11 kg")
        self.assertFalse(totales([registro(**SIN_LONA)])["con_lona"])

    def test_sin_registros(self):
        resultado = totales([])
        self.assertEqual(resultado["pedidos"], 0)
        self.assertEqual(resultado["material_usado_g"], 0)
        self.assertEqual(resultado["por_material"], [])


class FormatoTest(unittest.TestCase):
    def test_fecha_hora(self):
        self.assertEqual(texto_fecha_hora("2026-10-27 18:40:12"), "27/10/2026 18:40")


class RedondeoTest(unittest.TestCase):
    """Los valores terminados en 5 siempre suben, en filas y en totales."""

    def test_kg_terminados_en_5_suben(self):
        casos = {
            745: "0.75 kg",  # la computadora lo guarda como 0.74499999…
            525: "0.53 kg",
            125: "0.13 kg",  # Python lo llevaría al par: 0.12
            5: "0.01 kg",
            3200.5: "3.20 kg",
            220: "0.22 kg",
            0: "0.00 kg",
        }
        for gramos, esperado in casos.items():
            with self.subTest(gramos=gramos):
                self.assertEqual(texto_kg(gramos), esperado)

    def test_total_de_la_semana_pasada_cuadra(self):
        # Lona de la semana pasada del MODO PRUEBA: 525 g + 220 g = 745 g
        filas = [
            registro(lona_recibida_g=600, lona_sobrante_g=75),
            registro(lona_recibida_g=250, lona_sobrante_g=30),
        ]
        self.assertEqual([texto_kg(lona_usada_g(fila)) for fila in filas], ["0.53 kg", "0.22 kg"])
        self.assertEqual(texto_kg(totales(filas)["lona_usada_g"]), "0.75 kg")

    def test_sumas_con_ruido_de_la_computadora(self):
        # 0.1 + 0.2 da 0.30000000000000004 en la computadora
        self.assertEqual(texto_kg((0.1 + 0.2) * 1000), "0.30 kg")
        # 1234.4 + 1.1 da 1235.4999999999998; debe tratarse como 1235.5
        self.assertEqual(texto_kg(1234.4 + 1.1), "1.24 kg")
        self.assertEqual(texto_gramos(1234.4 + 1.1), "1235.5")

    def test_gramos_y_g_por_pieza(self):
        self.assertEqual(texto_gramos(3600.5), "3600.5")
        self.assertEqual(texto_gramos(400.0), "400")
        self.assertEqual(texto_gramos(3600.125), "3600.13")
        self.assertEqual(texto_g_por_pieza(15.45), "15.5 g")
        self.assertEqual(texto_g_por_pieza(0.25), "0.3 g")
        self.assertEqual(texto_g_por_pieza(64.01), "64 g")

    def test_numeros_sin_unidad_para_el_pdf(self):
        self.assertEqual(numero_kg(745), "0.75")
        self.assertEqual(numero_kg(3200.5), "3.20")
        self.assertEqual(numero_g_por_pieza(15.45), "15.5")
        self.assertEqual(numero_g_por_pieza(64.01), "64")

    def test_redondear(self):
        self.assertEqual(str(redondear(2.5, 0)), "3")
        self.assertEqual(str(redondear(0.745, 2)), "0.75")


if __name__ == "__main__":
    unittest.main()
