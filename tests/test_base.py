"""Pruebas del cambio de la base (columna de la papelera) y del MODO PRUEBA.

Todo se hace en carpetas temporales. Nunca abre produccion.db.
"""

import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path

import base_datos
import crear_base
import datos_prueba
from app import crear_app


def columnas_produccion(ruta):
    conexion = sqlite3.connect(ruta)
    try:
        return [fila[1] for fila in conexion.execute("PRAGMA table_info(produccion)")]
    finally:
        conexion.close()


class ColumnaPapeleraTest(unittest.TestCase):
    def setUp(self):
        # enterContext la borra sola al terminar cada prueba (Pylint no lo reconoce)
        carpeta = self.enterContext(tempfile.TemporaryDirectory())  # pylint: disable=consider-using-with
        self.ruta = Path(carpeta) / "antigua.db"

        # Una base como la de la Parte 3: sin borrado_en y con un registro
        crear_base.crear_base(self.ruta, informar=False)
        conexion = sqlite3.connect(self.ruta)
        conexion.execute("ALTER TABLE produccion DROP COLUMN borrado_en")
        conexion.execute(
            """INSERT INTO produccion (fecha, pieza_id, material_id, lleva_lona, cantidad,
                   material_recibido_g, material_sobrante_g)
               VALUES ('2026-10-22', 1, 1, 0, 50, 3600.5, 400)"""
        )
        conexion.commit()
        conexion.close()

    def test_la_app_no_abre_una_base_sin_la_columna(self):
        with self.assertRaises(base_datos.BaseNoDisponible) as error:
            crear_app(self.ruta)
        self.assertIn("borrado_en", str(error.exception))
        self.assertIn("crear_base.py", str(error.exception))

    def test_crear_base_agrega_la_columna_sin_tocar_los_registros(self):
        self.assertNotIn("borrado_en", columnas_produccion(self.ruta))
        crear_base.crear_base(self.ruta, informar=False)
        self.assertIn("borrado_en", columnas_produccion(self.ruta))

        conexion = sqlite3.connect(self.ruta)
        conexion.row_factory = sqlite3.Row
        filas = conexion.execute("SELECT * FROM produccion").fetchall()
        conexion.close()
        self.assertEqual(len(filas), 1)
        self.assertEqual(filas[0]["material_recibido_g"], 3600.5)
        self.assertIsNone(filas[0]["borrado_en"])  # vigente, no en la papelera

        # Ejecutarlo otra vez no cambia nada
        crear_base.crear_base(self.ruta, informar=False)
        self.assertEqual(columnas_produccion(self.ruta).count("borrado_en"), 1)
        crear_app(self.ruta)


class ModoPruebaTest(unittest.TestCase):
    def setUp(self):
        # enterContext la borra sola al terminar cada prueba (Pylint no lo reconoce)
        carpeta = self.enterContext(tempfile.TemporaryDirectory())  # pylint: disable=consider-using-with
        self.ruta = Path(carpeta) / "produccion_prueba.db"

    def test_nunca_usa_la_base_real(self):
        with self.assertRaises(datos_prueba.RutaNoPermitida):
            datos_prueba.preparar_base_prueba(base_datos.RUTA_POR_DEFECTO)

    def test_crea_datos_de_ejemplo_sin_fechas_futuras(self):
        hoy = date(2026, 10, 27)  # martes
        ruta, recien_creada = datos_prueba.preparar_base_prueba(self.ruta, hoy=hoy)
        self.assertTrue(recien_creada)

        conexion = base_datos.conectar(ruta)
        try:
            vigentes = base_datos.listar_registros(conexion)
            papelera = base_datos.listar_papelera(conexion)
        finally:
            conexion.close()
        self.assertEqual(len(papelera), 1)
        # 6 de la semana pasada (uno en la papelera) + lunes y martes de esta semana
        self.assertEqual(len(vigentes), 8)
        self.assertTrue(all(fila["fecha"] <= "2026-10-27" for fila in vigentes))

    def test_si_ya_existe_no_la_recrea(self):
        datos_prueba.preparar_base_prueba(self.ruta, hoy=date(2026, 10, 27))
        conexion = sqlite3.connect(self.ruta)
        conexion.execute("DELETE FROM produccion")
        conexion.commit()
        conexion.close()

        _, recien_creada = datos_prueba.preparar_base_prueba(self.ruta)
        self.assertFalse(recien_creada)
        conexion = sqlite3.connect(self.ruta)
        self.assertEqual(conexion.execute("SELECT COUNT(*) FROM produccion").fetchone()[0], 0)
        conexion.close()

    def test_la_franja_de_modo_prueba_se_ve(self):
        datos_prueba.preparar_base_prueba(self.ruta)
        app = crear_app(self.ruta, modo_prueba=True)
        html = app.test_client().get("/historial").get_data(as_text=True)
        self.assertIn("MODO PRUEBA", html)
        self.assertIn("<title>[PRUEBA]", html)


if __name__ == "__main__":
    unittest.main()
