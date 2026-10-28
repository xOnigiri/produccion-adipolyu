"""Pruebas del informe en PDF.

Cada prueba usa una base nueva en una carpeta temporal. Nunca abre produccion.db.
"""

import base64
import re
import unittest
import zlib
from datetime import date, timedelta
from pathlib import Path

import calculos
import informe_pdf
from app import _para_nombre_de_archivo, crear_app
from tests.test_historial import HOY, ConHistorial

LUNES = HOY - timedelta(days=HOY.weekday())


def texto_del_pdf(pdf):
    """Todo lo que el PDF escribe en sus hojas, para buscar cifras.

    ReportLab guarda cada hoja comprimida (zlib) y escrita en ASCII85, que
    termina en '~>'. Aquí se deshacen las dos cosas. Las letras con tilde
    vienen como códigos (\\363 = ó) en la tabla de letras de Windows (cp1252).
    """
    partes = []
    for bloque in re.findall(rb"stream\r?\n(.*?)endstream", pdf, re.S):
        try:
            partes.append(zlib.decompress(base64.a85decode(bloque.strip().removesuffix(b"~>"))))
        except (ValueError, zlib.error):
            pass  # otro tipo de contenido (por ejemplo, la imagen del logo)
    texto = b"\n".join(partes)
    texto = re.sub(rb"\\([0-7]{3})", lambda codigo: bytes([int(codigo.group(1), 8)]), texto)
    return texto.decode("cp1252", errors="replace")


class ConInforme(ConHistorial):
    def pdf(self, direccion="/historial/pdf"):
        respuesta = self.cliente.get(direccion)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.mimetype, "application/pdf")
        self.assertTrue(respuesta.data.startswith(b"%PDF"))
        return respuesta

    def semana_de_ejemplo(self):
        """Lona de la semana: 525 g + 220 g usados = 0,75 kg; sobrante 75 + 30 g."""
        self.insertar(LUNES, material="jebe azul", pieza="amortiguador", cantidad=20,
                      recibido=5200, sobrante=480, lona=(600, 75))
        self.insertar(LUNES, observaciones="2 piezas con burbuja")
        self.insertar(LUNES, pieza="anillo", material="silicona naranja", cantidad=120,
                      recibido=2000, sobrante=150, lona=None)


class DescargarPdfTest(ConInforme):
    def test_descarga_con_nombre_de_la_semana(self):
        self.semana_de_ejemplo()
        respuesta = self.pdf()
        domingo = LUNES + timedelta(days=6)
        self.assertEqual(
            respuesta.headers["Content-Disposition"],
            f"attachment; filename=produccion_{LUNES}_al_{domingo}.pdf",
        )

    def test_mismas_cifras_que_el_historial(self):
        self.semana_de_ejemplo()
        historial = self.html("/historial")
        texto = texto_del_pdf(self.pdf().data)
        # Recuadro de arriba: piezas, material usado y lona usada
        for cifra in ("190", "9,77", "0,75"):
            self.assertIn(cifra, historial)
            self.assertIn(cifra, texto)
        # Filas (sin la unidad, que va en el título de la columna) y resúmenes
        for cifra in ("3600,5", "3,20", "64", "0,53", "0,22", "4,72", "1,85", "0,11"):
            self.assertIn(cifra, texto)
        self.assertNotIn("0,74", texto)
        self.assertIn("Producción de la semana", texto)
        self.assertIn("burbuja", texto)

    def test_la_papelera_no_entra_al_informe(self):
        self.insertar(LUNES)
        borrado = self.insertar(LUNES, cantidad=999)
        self.cliente.post(f"/registro/{borrado}/borrar")
        texto = texto_del_pdf(self.pdf().data)
        self.assertNotIn("999", texto)
        self.assertIn("1 pedido", texto)

    def test_respeta_los_filtros_y_los_pone_en_el_nombre(self):
        self.insertar(date(2026, 10, 5), observaciones="va")
        self.insertar(date(2026, 10, 6), pieza="anillo", observaciones="no va")
        respuesta = self.pdf(
            f"/historial/pdf?periodo=rango&desde=2026-10-01&hasta=2026-10-31"
            f"&pieza_id={self.piezas['retén']}&material_id={self.materiales['nitrilo']}"
        )
        self.assertIn(
            "filename=produccion_2026-10-01_al_2026-10-31_reten_nitrilo.pdf",
            respuesta.headers["Content-Disposition"],
        )
        texto = texto_del_pdf(respuesta.data)
        self.assertIn("Producción del 01/10/2026 al 31/10/2026", texto)
        self.assertIn("1 pedido", texto)

    def test_todo_usa_las_fechas_del_primer_y_ultimo_pedido(self):
        self.insertar(date(2026, 9, 3))
        self.insertar(date(2026, 10, 5))
        respuesta = self.pdf("/historial/pdf?periodo=todo")
        self.assertIn("produccion_2026-09-03_al_2026-10-05.pdf",
                      respuesta.headers["Content-Disposition"])
        self.assertIn("Pedidos del 03/09/2026 al 05/10/2026", texto_del_pdf(respuesta.data))

    def test_sin_registros_no_hay_pdf(self):
        respuesta = self.cliente.get("/historial/pdf?periodo=pasada")
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta.headers["Location"], "/historial?periodo=pasada")
        html = self.html("/historial?periodo=pasada")
        self.assertIn("no se generó el informe", html)
        self.assertIn("No hay registros para el informe", html)
        self.assertNotIn("Descargar PDF", html)

    def test_boton_del_historial_lleva_los_mismos_filtros(self):
        self.insertar(LUNES)
        html = self.html(f"/historial?periodo=esta&material_id={self.materiales['nitrilo']}")
        self.assertIn(
            f'href="/historial/pdf?periodo=esta&amp;material_id={self.materiales["nitrilo"]}"',
            html,
        )

    def test_historial_muestra_la_linea_de_lona(self):
        self.semana_de_ejemplo()
        html = " ".join(self.html("/historial").split())
        self.assertIn('<tr class="fila-lona"> <td>Lona</td> <td class="numero">0,75 kg</td> '
                      '<td class="numero">0,11 kg</td>', html)


class LogoYModoPruebaTest(ConInforme):
    def test_sin_logo_se_genera_igual(self):
        self.insertar(LUNES)
        app = crear_app(self.ruta_db, ruta_logo=Path(self.ruta_db).parent / "no-existe.png")
        with self.assertLogs(app.logger, "WARNING") as aviso:
            respuesta = app.test_client().get("/historial/pdf")
        self.assertIn("No se encontró el logo", aviso.output[0])
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("ADIPOLYU", texto_del_pdf(respuesta.data))

    def test_con_logo_lleva_la_imagen(self):
        self.insertar(LUNES)
        self.assertIn(b"/Subtype /Image", self.pdf().data)

    def test_informe_real_sin_marcas_de_prueba(self):
        self.insertar(LUNES)
        self.assertNotIn("DATOS DE EJEMPLO", texto_del_pdf(self.pdf().data))

    def test_modo_prueba_marca_cada_hoja_y_el_nombre(self):
        # 40 pedidos: la tabla ocupa varias hojas
        for dia in range(40):
            self.insertar(date(2026, 9, 1) + timedelta(days=dia))
        app = crear_app(self.ruta_db, modo_prueba=True)
        respuesta = app.test_client().get("/historial/pdf?periodo=todo")
        self.assertTrue(
            respuesta.headers["Content-Disposition"].startswith("attachment; filename=PRUEBA_")
        )
        texto = texto_del_pdf(respuesta.data)
        hojas = texto.count("Página ")
        self.assertGreater(hojas, 1)
        self.assertEqual(texto.count("(DATOS DE EJEMPLO)"), hojas)  # marca de agua
        self.assertGreaterEqual(texto.count("NO ES UN INFORME REAL"), hojas)  # franja
        self.assertIn(f"Página 1 de {hojas}", texto)


class InformeSinWebTest(unittest.TestCase):
    """informe_pdf.py se puede usar solo, sin la app ni la base."""

    def test_filas_de_la_tabla(self):
        registros = [{
            "fecha": "2026-10-22", "pieza": "retén", "material": "nitrilo",
            "dureza_shore_a": 70, "lleva_lona": 0,
            "cantidad": 50, "material_recibido_g": 3600.5, "material_sobrante_g": 400.0,
            "lona_recibida_g": None, "lona_sobrante_g": None, "observaciones": None,
        }]
        filas = informe_pdf.filas_de_pedidos(registros, calculos.totales(registros))
        self.assertEqual(
            filas[0],
            ["22/10/2026", "Retén", "Nitrilo", "70", "No", "50", "3600,5", "400", "3,20", "64",
             "—", ""],
        )
        self.assertEqual(len(filas[0]), len(informe_pdf.COLUMNAS))
        self.assertEqual(len(filas[-1]), len(informe_pdf.COLUMNAS))
        self.assertEqual(filas[-1][0], "TOTAL")
        self.assertEqual(filas[-1][8], "3,20")

    def test_sin_dureza_muestra_guion(self):
        registros = [{
            "fecha": "2026-10-22", "pieza": "anillo", "material": "silicona naranja",
            "dureza_shore_a": None, "lleva_lona": 0,
            "cantidad": 120, "material_recibido_g": 2000, "material_sobrante_g": 150,
            "lona_recibida_g": None, "lona_sobrante_g": None, "observaciones": None,
        }]
        filas = informe_pdf.filas_de_pedidos(registros, calculos.totales(registros))
        self.assertEqual(filas[0][3], "—")
        self.assertEqual(informe_pdf.COLUMNAS[3][0], "Dureza")

    def test_nombre_de_archivo_sin_tildes_ni_espacios(self):
        self.assertEqual(_para_nombre_de_archivo("retén"), "reten")
        self.assertEqual(_para_nombre_de_archivo("silicona naranja"), "silicona-naranja")


if __name__ == "__main__":
    unittest.main()
