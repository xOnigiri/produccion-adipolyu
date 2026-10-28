"""Pruebas del formulario completo (página + base de datos).

Cada prueba usa una base nueva en una carpeta temporal, armada con las mismas
tablas y listas de crear_base.py. Nunca abre produccion.db.
"""

import re
import sqlite3
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

import base_datos
import crear_base
from app import crear_app


def crear_base_de_prueba(ruta):
    conexion = sqlite3.connect(ruta)
    try:
        conexion.executescript(crear_base.ESQUEMA)
        conexion.executemany(
            "INSERT INTO piezas (nombre) VALUES (?)",
            [(nombre,) for nombre in crear_base.PIEZAS_INICIALES],
        )
        conexion.executemany(
            "INSERT INTO materiales (nombre) VALUES (?)",
            [(nombre,) for nombre in crear_base.MATERIALES_INICIALES],
        )
        # Una pieza desactivada que no debe aparecer en el formulario
        conexion.execute("INSERT INTO piezas (nombre, activo) VALUES ('pieza retirada', 0)")
        conexion.commit()
    finally:
        conexion.close()


class PruebaConBase(unittest.TestCase):
    """Preparación común de las pruebas de páginas: una base temporal nueva
    (se borra sola al terminar) y un navegador de prueba."""

    def setUp(self):
        # enterContext la borra sola al terminar cada prueba (Pylint no lo reconoce)
        carpeta = self.enterContext(tempfile.TemporaryDirectory())  # pylint: disable=consider-using-with
        self.ruta_db = Path(carpeta) / "prueba.db"
        crear_base_de_prueba(self.ruta_db)

        app = crear_app(self.ruta_db)
        app.config["TESTING"] = True
        self.cliente = app.test_client()

        conexion = sqlite3.connect(self.ruta_db)
        try:
            # nombre -> id, para escribir las pruebas con nombres del taller
            self.piezas = dict(conexion.execute("SELECT nombre, id FROM piezas"))
            self.materiales = dict(conexion.execute("SELECT nombre, id FROM materiales"))
        finally:
            conexion.close()

    def opcion_resaltada(self, html):
        """Nombres de las opciones del menú resaltadas (debe haber una sola).
        Entre el enlace y el nombre va el icono."""
        return re.findall(
            r'class="activo" aria-current="page">\s*<svg.*?</svg>\s*<span>([^<]+)</span>',
            html, re.S,
        )


class FormularioTest(PruebaConBase):
    def setUp(self):
        super().setUp()
        self.id_reten = self.piezas["retén"]
        self.id_nitrilo = self.materiales["nitrilo"]
        self.id_retirada = self.piezas["pieza retirada"]

    def registros(self):
        conexion = sqlite3.connect(self.ruta_db)
        conexion.row_factory = sqlite3.Row
        try:
            return conexion.execute("SELECT * FROM produccion ORDER BY id").fetchall()
        finally:
            conexion.close()

    def pedido(self, **cambios):
        datos = {
            "fecha": "2026-10-22",
            "pieza_id": str(self.id_reten),
            "material_id": str(self.id_nitrilo),
            "cantidad": "50",
            "material_recibido_g": "3600,5",
            "material_sobrante_g": "400",
            "lleva_lona": "si",
            "lona_recibida_g": "250",
            "lona_sobrante_g": "30",
            "observaciones": "2 piezas con burbuja",
        }
        datos.update(cambios)
        return datos

    def test_inicio_lleva_al_formulario(self):
        respuesta = self.cliente.get("/")
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(respuesta.headers["Location"].endswith("/registrar"))

    def test_formulario_muestra_listas_activas_y_fecha_de_hoy(self):
        html = self.cliente.get("/registrar").get_data(as_text=True)
        # Con mayúscula inicial al mostrarlos, aunque se guarden en minúsculas
        self.assertIn(">Retén</option>", html)
        self.assertIn(">Silicona transparente</option>", html)
        self.assertNotIn("Pieza retirada", html)
        self.assertIn(f'value="{date.today().isoformat()}"', html)

    def test_guardar_pedido_valido(self):
        respuesta = self.cliente.post("/registrar", data=self.pedido())
        self.assertEqual(respuesta.status_code, 302)
        # Vuelve al formulario con la misma fecha
        self.assertTrue(respuesta.headers["Location"].endswith("/registrar?fecha=2026-10-22"))

        filas = self.registros()
        self.assertEqual(len(filas), 1)
        self.assertEqual(filas[0]["material_recibido_g"], 3600.5)
        self.assertEqual(filas[0]["lona_sobrante_g"], 30)
        self.assertEqual(filas[0]["observaciones"], "2 piezas con burbuja")

        html = self.cliente.get(respuesta.headers["Location"]).get_data(as_text=True)
        self.assertIn(
            "Registro guardado: 22/10/2026 · Retén · Nitrilo · con lona · 50 unidades · "
            "material usado 3,20 kg · lona usada 0,22 kg",
            html,
        )
        self.assertIn('value="2026-10-22"', html)

    def test_pedido_sin_lona_guarda_lona_vacia(self):
        self.cliente.post("/registrar", data=self.pedido(lleva_lona="", lona_recibida_g="250"))
        fila = self.registros()[0]
        self.assertEqual(fila["lleva_lona"], 0)
        self.assertIsNone(fila["lona_recibida_g"])

    def test_error_no_guarda_y_conserva_lo_escrito(self):
        respuesta = self.cliente.post("/registrar", data=self.pedido(material_sobrante_g="4000"))
        self.assertEqual(respuesta.status_code, 422)
        self.assertEqual(self.registros(), [])

        html = respuesta.get_data(as_text=True)
        self.assertIn("No se guardó el registro", html)
        self.assertIn("no puede ser mayor que el recibido (3600,5 g)", html)
        self.assertIn('value="3600,5"', html)
        self.assertIn("2 piezas con burbuja", html)
        self.assertIn("checked", html)

    def test_no_acepta_pieza_desactivada(self):
        respuesta = self.cliente.post(
            "/registrar", data=self.pedido(pieza_id=str(self.id_retirada))
        )
        self.assertEqual(respuesta.status_code, 422)
        self.assertEqual(self.registros(), [])

    def test_fecha_futura_en_la_direccion_se_ignora(self):
        manana = (date.today() + timedelta(days=1)).isoformat()
        html = self.cliente.get(f"/registrar?fecha={manana}").get_data(as_text=True)
        self.assertIn(f'value="{date.today().isoformat()}"', html)


class BaseFaltanteTest(unittest.TestCase):
    def test_no_crea_una_base_vacia(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "no_existe.db"
            with self.assertRaises(base_datos.BaseNoDisponible):
                crear_app(ruta)
            self.assertFalse(ruta.exists())


if __name__ == "__main__":
    unittest.main()
