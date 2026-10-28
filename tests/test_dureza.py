"""Pruebas de la dureza de cada pedido: base, formulario, historial,
PDF y MODO PRUEBA.

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
from tests.test_base import columnas_produccion
from tests.test_historial import HOY, ConHistorial
from tests.test_informe import LUNES, ConInforme, texto_del_pdf
from validacion import validar_registro


class BaseSoloAceptaLaListaTest(unittest.TestCase):
    def setUp(self):
        # enterContext la borra sola al terminar cada prueba (Pylint no lo reconoce)
        carpeta = self.enterContext(tempfile.TemporaryDirectory())  # pylint: disable=consider-using-with
        self.ruta = Path(carpeta) / "nueva.db"
        crear_base.crear_base(self.ruta, informar=False)

    def guardar_con_dureza(self, dureza):
        conexion = sqlite3.connect(self.ruta)
        try:
            conexion.execute(
                """INSERT INTO produccion (fecha, pieza_id, material_id, lleva_lona, cantidad,
                       material_recibido_g, material_sobrante_g, dureza_shore_a)
                   VALUES ('2026-10-22', 1, 1, 0, 50, 3600.5, 400, ?)""",
                (dureza,),
            )
            conexion.commit()
        finally:
            conexion.close()

    def test_acepta_vacio_y_las_durezas_de_la_lista(self):
        for dureza in (None, *crear_base.DUREZAS_SHORE_A):
            self.guardar_con_dureza(dureza)

    def test_rechaza_cualquier_otra(self):
        for dureza in (72, 110, 0, -70, 70.5, "dura"):
            with self.subTest(dureza=dureza), self.assertRaises(sqlite3.IntegrityError):
                self.guardar_con_dureza(dureza)


class BaseAntiguaTest(unittest.TestCase):
    """Una base como la de hoy (Parte 7): sin la columna y con un registro."""

    def setUp(self):
        # enterContext la borra sola al terminar cada prueba (Pylint no lo reconoce)
        carpeta = self.enterContext(tempfile.TemporaryDirectory())  # pylint: disable=consider-using-with
        self.carpeta = Path(carpeta)
        self.ruta = self.carpeta / "antigua.db"
        crear_base.crear_base(self.ruta, informar=False)
        conexion = sqlite3.connect(self.ruta)
        conexion.execute("ALTER TABLE produccion DROP COLUMN dureza_shore_a")
        conexion.execute(
            """INSERT INTO produccion (fecha, pieza_id, material_id, lleva_lona, cantidad,
                   material_recibido_g, material_sobrante_g, lona_recibida_g,
                   lona_sobrante_g, observaciones)
               VALUES ('2026-10-22', 1, 2, 1, 50, 3600.5, 400, 250, 30, '2 piezas con burbuja')"""
        )
        conexion.commit()
        conexion.close()

    def filas(self):
        conexion = sqlite3.connect(self.ruta)
        conexion.row_factory = sqlite3.Row
        try:
            return [dict(fila) for fila in conexion.execute("SELECT * FROM produccion")]
        finally:
            conexion.close()

    def test_la_app_no_abre_una_base_sin_la_columna(self):
        with self.assertRaises(base_datos.BaseNoDisponible) as error:
            crear_app(self.ruta)
        self.assertIn("dureza_shore_a", str(error.exception))
        self.assertIn("crear_base.py", str(error.exception))

    def test_crear_base_agrega_la_columna_sin_tocar_los_registros(self):
        antes = self.filas()
        crear_base.crear_base(self.ruta, informar=False)
        despues = self.filas()

        self.assertEqual(len(despues), 1)
        self.assertIsNone(despues[0].pop("dureza_shore_a"))  # sin dato
        self.assertEqual(despues, antes)  # el resto de columnas, idénticas

        # Ejecutarlo otra vez no cambia nada
        crear_base.crear_base(self.ruta, informar=False)
        self.assertEqual(columnas_produccion(self.ruta).count("dureza_shore_a"), 1)
        crear_app(self.ruta)

    def test_la_columna_agregada_tambien_rechaza_valores_raros(self):
        crear_base.crear_base(self.ruta, informar=False)
        conexion = sqlite3.connect(self.ruta)
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                conexion.execute("UPDATE produccion SET dureza_shore_a = 72")
            conexion.execute("UPDATE produccion SET dureza_shore_a = 70")
        finally:
            conexion.close()

    def test_misma_estructura_que_una_base_nueva(self):
        crear_base.crear_base(self.ruta, informar=False)
        nueva = self.carpeta / "nueva.db"
        crear_base.crear_base(nueva, informar=False)

        def info(ruta):
            conexion = sqlite3.connect(ruta)
            try:
                return conexion.execute("PRAGMA table_info(produccion)").fetchall()
            finally:
                conexion.close()

        self.assertEqual(info(self.ruta), info(nueva))


class ValidacionTest(unittest.TestCase):
    FORMULARIO = {
        "fecha": "2026-10-22",
        "pieza_id": "3",
        "material_id": "2",
        "cantidad": "50",
        "material_recibido_g": "3600,5",
        "material_sobrante_g": "400",
    }

    def validar(self, dureza):
        return validar_registro(
            {**self.FORMULARIO, "dureza_shore_a": dureza},
            piezas_validas={3}, materiales_validos={2}, hoy=date(2026, 10, 27),
        )

    def test_vacio_es_sin_dato(self):
        registro, errores = self.validar("")
        self.assertEqual(errores, {})
        self.assertIsNone(registro["dureza_shore_a"])

    def test_sin_el_campo_es_sin_dato(self):
        registro, _ = validar_registro(
            self.FORMULARIO, piezas_validas={3}, materiales_validos={2}, hoy=date(2026, 10, 27)
        )
        self.assertIsNone(registro["dureza_shore_a"])

    def test_durezas_de_la_lista(self):
        for dureza in crear_base.DUREZAS_SHORE_A:
            registro, errores = self.validar(str(dureza))
            self.assertEqual(errores, {})
            self.assertEqual(registro["dureza_shore_a"], dureza)

    def test_otra_dureza_da_error(self):
        for texto in ("72", "110", "70.5", "-70", "dura"):
            with self.subTest(texto=texto):
                registro, errores = self.validar(texto)
                self.assertIsNone(registro)
                self.assertIn("Elige una dureza de la lista", errores["dureza_shore_a"])


class FormularioConDurezaTest(ConHistorial):
    def guardado(self):
        conexion = sqlite3.connect(self.ruta_db)
        try:
            return [fila[0] for fila in conexion.execute(
                "SELECT dureza_shore_a FROM produccion ORDER BY id")]
        finally:
            conexion.close()

    def test_formulario_muestra_la_lista(self):
        html = self.html("/registrar")
        # En el taller se dice solo "Dureza": sin "Shore A" ni "(opcional)"
        self.assertIn('<label for="dureza_shore_a">Dureza</label>', html)
        self.assertNotIn("Shore", html)
        self.assertIn('<option value="">— sin dato —</option>', html)
        for dureza in crear_base.DUREZAS_SHORE_A:
            self.assertIn(f'<option value="{dureza}" >{dureza}</option>', html)
        # Va después de Material y antes de Cantidad
        self.assertLess(html.index('id="material_id"'), html.index('id="dureza_shore_a"'))
        self.assertLess(html.index('id="dureza_shore_a"'), html.index('id="cantidad"'))

    def test_guardar_con_y_sin_dureza(self):
        respuesta = self.cliente.post(
            "/registrar", data=self.formulario(dureza_shore_a="70"), follow_redirects=True
        )
        self.assertIn("Retén · Nitrilo · Dureza 70 · con lona", respuesta.get_data(as_text=True))
        self.cliente.post("/registrar", data=self.formulario(dureza_shore_a=""))
        self.assertEqual(self.guardado(), [70, None])

    def test_dureza_rara_no_guarda(self):
        respuesta = self.cliente.post("/registrar", data=self.formulario(dureza_shore_a="72"))
        self.assertEqual(respuesta.status_code, 422)
        self.assertIn("Elige una dureza de la lista", respuesta.get_data(as_text=True))
        self.assertEqual(self.guardado(), [])

    def test_corregir_muestra_la_dureza_y_la_puede_quitar(self):
        registro_id = self.insertar(HOY, dureza=85)
        html = self.html(f"/registro/{registro_id}/corregir")
        self.assertIn('<option value="85" selected>85</option>', html)

        self.cliente.post(f"/registro/{registro_id}/corregir",
                          data=self.formulario(dureza_shore_a="90"))
        self.assertEqual(self.fila(registro_id)["dureza_shore_a"], 90)
        self.cliente.post(f"/registro/{registro_id}/corregir",
                          data=self.formulario(dureza_shore_a=""))
        self.assertIsNone(self.fila(registro_id)["dureza_shore_a"])

    def test_corregir_sin_dureza_deja_sin_dato_elegido(self):
        registro_id = self.insertar(HOY)
        html = self.html(f"/registro/{registro_id}/corregir")
        self.assertNotIn("selected>", html.split('id="dureza_shore_a"')[1].split("</select>")[0])


class HistorialConDurezaTest(ConHistorial):
    def setUp(self):
        super().setUp()
        self.insertar(HOY, dureza=70, observaciones="con-70")
        self.insertar(HOY, dureza=80, observaciones="con-80")
        self.insertar(HOY, material="silicona naranja", lona=None, observaciones="sin-dureza")

    def test_columna_con_dureza_o_guion(self):
        html = self.html("/historial")
        self.assertIn('<th class="numero">Dureza</th>', html)
        self.assertNotIn("Shore", html)
        # En la tabla la pastilla lleva solo el número (la columna ya dice Dureza);
        # sin dato, un guion
        self.assertIn('<span class="pastilla pastilla-gris">70</span></td>', html)
        self.assertIn('<td class="numero vacio-celda">—</td>', html)

    def test_filtrar_por_dureza(self):
        html = self.html("/historial?dureza=70")
        self.assertIn("con-70", html)
        self.assertNotIn("con-80", html)
        self.assertNotIn("sin-dureza", html)
        self.assertIn("· Dureza 70", html)
        self.assertIn('<option value="70" selected>70</option>', html)

    def test_filtrar_sin_dato(self):
        html = self.html(f"/historial?dureza={base_datos.SIN_DUREZA}")
        self.assertIn("sin-dureza", html)
        self.assertNotIn("con-70", html)
        self.assertIn("· sin dureza anotada", html)

    def test_dureza_que_no_esta_en_la_lista_muestra_todas(self):
        html = self.html("/historial?dureza=72")
        for nota in ("con-70", "con-80", "sin-dureza"):
            self.assertIn(nota, html)

    def test_la_papelera_muestra_la_dureza(self):
        registro_id = self.insertar(HOY, dureza=95)
        self.cliente.post(f"/registro/{registro_id}/borrar")
        html = self.html("/papelera")
        self.assertIn('<span class="pastilla pastilla-gris">95</span></td>', html)
        self.assertNotIn("Shore", html)


class PdfConDurezaTest(ConInforme):
    def setUp(self):
        super().setUp()
        self.insertar(LUNES, dureza=70, observaciones="con-70")
        self.insertar(LUNES, material="silicona naranja", lona=None, observaciones="sin-dureza")

    def test_columna_dureza(self):
        texto = texto_del_pdf(self.pdf().data)
        # El "—" de un pedido sin dureza se revisa en InformeSinWebTest
        self.assertIn("(Dureza)", texto)
        self.assertIn("(70)", texto)

    def test_filtro_en_el_titulo_y_el_nombre(self):
        respuesta = self.pdf("/historial/pdf?dureza=70")
        self.assertIn("_dureza-70.pdf", respuesta.headers["Content-Disposition"])
        texto = texto_del_pdf(respuesta.data)
        self.assertIn("Dureza: 70", texto)
        self.assertNotIn("Shore", texto)
        self.assertIn("con-70", texto)
        self.assertNotIn("sin-dureza", texto)

    def test_filtro_sin_dato(self):
        respuesta = self.pdf(f"/historial/pdf?dureza={base_datos.SIN_DUREZA}")
        self.assertIn("_sin-dureza.pdf", respuesta.headers["Content-Disposition"])
        self.assertIn("Dureza: sin dato", texto_del_pdf(respuesta.data))


class ModoPruebaConDurezaTest(unittest.TestCase):
    def test_algunos_ejemplos_tienen_dureza_y_las_siliconas_no(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta, _ = datos_prueba.preparar_base_prueba(
                Path(carpeta) / "produccion_prueba.db", hoy=date(2026, 10, 27)
            )
            conexion = base_datos.conectar(ruta)
            try:
                filas = conexion.execute(
                    "SELECT materiales.nombre, dureza_shore_a FROM produccion "
                    "JOIN materiales ON materiales.id = material_id"
                ).fetchall()
            finally:
                conexion.close()
        con_dureza = [fila for fila in filas if fila["dureza_shore_a"] is not None]
        self.assertGreater(len(con_dureza), 0)
        self.assertLess(len(con_dureza), len(filas))
        self.assertTrue(all(
            fila["dureza_shore_a"] is None for fila in filas if "silicona" in fila["nombre"]
        ))


if __name__ == "__main__":
    unittest.main()
