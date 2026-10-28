"""Pruebas del respaldo.

Todo se hace en carpetas temporales: una de ellas hace de "G:\\Mi unidad".
Nunca abre produccion.db ni escribe en Google Drive.
"""

import hashlib
import sqlite3
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest import mock

import datos_prueba
import respaldo
from app import crear_app
from tests.test_app import crear_base_de_prueba

AHORA = datetime(2026, 10, 27, 18, 40, 5)


def huella(ruta):
    return hashlib.sha256(Path(ruta).read_bytes()).hexdigest()


def todo_lo_que_hay(carpeta):
    return sorted(str(ruta.relative_to(carpeta)) for ruta in Path(carpeta).rglob("*"))


class ConDriveFalso(unittest.TestCase):
    """Una base de prueba con un pedido y un "Drive" en una carpeta temporal,
    con la carpeta ADIPOLYU y un video que no se debe tocar."""

    def setUp(self):
        # enterContext la borra sola al terminar cada prueba (Pylint no lo reconoce)
        self.carpeta = Path(self.enterContext(tempfile.TemporaryDirectory()))  # pylint: disable=consider-using-with
        self.ruta_db = self.carpeta / "produccion.db"
        crear_base_de_prueba(self.ruta_db)
        self.ejecutar(
            """INSERT INTO produccion (fecha, pieza_id, material_id, lleva_lona, cantidad,
                   material_recibido_g, material_sobrante_g)
               VALUES ('2026-10-22', 1, 1, 0, 50, 3600.5, 400)"""
        )

        self.unidad = self.carpeta / "Mi unidad"
        self.adipolyu = self.unidad / "ADIPOLYU"
        self.adipolyu.mkdir(parents=True)
        self.video = self.adipolyu / "ADIPOLYU_animacion.mp4"
        self.video.write_bytes(b"video de ejemplo")
        self.destino = respaldo.Destino(
            self.adipolyu / "respaldos-produccion", self.unidad, "Google Drive"
        )
        # Para estas pruebas, la base "real" es la temporal
        self.enterContext(mock.patch.object(respaldo, "RUTA_REAL", self.ruta_db))

        self.notas = self.carpeta / "notas.md"
        self.notas.write_text("Notas del proyecto", encoding="utf-8")

    def ejecutar(self, sql):
        conexion = sqlite3.connect(self.ruta_db)
        try:
            conexion.execute(sql)
            conexion.commit()
        finally:
            conexion.close()

    def respaldar(self, extras=(), ahora=AHORA):
        return respaldo.hacer_respaldo(self.ruta_db, self.destino, extras, ahora)


class HacerRespaldoTest(ConDriveFalso):
    def test_respaldo_completo_y_verificado(self):
        resultado = self.respaldar([self.notas])

        carpeta = self.destino.carpeta / "2026-10-27_18-40-05"
        self.assertEqual(resultado.carpeta, carpeta)
        self.assertEqual(
            sorted(ruta.name for ruta in carpeta.iterdir()),
            ["notas.md", "produccion_2026-10-27_18-40-05.db", "resumen.txt"],
        )
        self.assertEqual(huella(carpeta / "notas.md"), huella(self.notas))
        self.assertEqual(resultado.conteo["registros"], 1)

        # La copia se abre, está sana y tiene el pedido
        conexion = sqlite3.connect(resultado.archivo_db)
        try:
            self.assertEqual(conexion.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(
                conexion.execute("SELECT material_recibido_g FROM produccion").fetchone()[0],
                3600.5,
            )
        finally:
            conexion.close()

        resumen = (carpeta / "resumen.txt").read_text(encoding="utf-8")
        self.assertIn("Registros de producción: 1 (1 vigentes, 0 en la papelera)", resumen)
        self.assertIn(huella(resultado.archivo_db), resumen)

    def test_sin_drive_avisa_y_no_escribe_nada(self):
        antes = todo_lo_que_hay(self.carpeta)
        self.destino = respaldo.Destino(
            self.carpeta / "G-cerrado" / "ADIPOLYU" / "respaldos-produccion",
            self.carpeta / "G-cerrado", "Google Drive",
        )
        with self.assertRaisesRegex(respaldo.RespaldoFallido,
                                    "Google Drive no está disponible.*inicia sesión"):
            self.respaldar()
        self.assertEqual(todo_lo_que_hay(self.carpeta), antes)

    def test_sin_carpeta_adipolyu_no_crea_nada(self):
        self.video.unlink()
        self.adipolyu.rmdir()
        with self.assertRaisesRegex(respaldo.RespaldoFallido, "No se creó nada"):
            self.respaldar()
        self.assertEqual(list(self.unidad.iterdir()), [])

    def test_no_toca_nada_de_adipolyu_fuera_de_respaldos(self):
        huella_video = huella(self.video)
        self.respaldar()
        self.respaldar(ahora=AHORA + timedelta(minutes=1))
        self.assertEqual(sorted(ruta.name for ruta in self.adipolyu.iterdir()),
                         ["ADIPOLYU_animacion.mp4", "respaldos-produccion"])
        self.assertEqual(huella(self.video), huella_video)

    def test_barrera_no_escribe_fuera_de_la_carpeta_de_respaldos(self):
        with self.assertRaises(respaldo.RespaldoNoPermitido):
            respaldo._escribir(self.adipolyu / "intruso.txt", "x", self.destino)  # pylint: disable=protected-access
        with self.assertRaises(respaldo.RespaldoNoPermitido):
            respaldo._escribir(self.destino.carpeta / ".." / "intruso.txt", "x", self.destino)  # pylint: disable=protected-access
        self.assertFalse((self.adipolyu / "intruso.txt").exists())

    def test_mismo_segundo_no_sobrescribe(self):
        primero = self.respaldar()
        huella_primero = huella(primero.archivo_db)
        self.ejecutar("UPDATE produccion SET cantidad = 60")
        segundo = self.respaldar()

        self.assertEqual(segundo.carpeta.name, "2026-10-27_18-40-05_2")
        self.assertEqual(segundo.archivo_db.name, "produccion_2026-10-27_18-40-05_2.db")
        self.assertEqual(huella(primero.archivo_db), huella_primero)

    def test_copia_alterada_queda_como_fallida(self):
        with mock.patch.object(respaldo, "_leer_copia", return_value=b"copia danada"):
            with self.assertRaisesRegex(respaldo.RespaldoFallido, "no es idéntica"):
                self.respaldar()
        nombres = [ruta.name for ruta in self.destino.carpeta.iterdir()]
        self.assertEqual(nombres, ["2026-10-27_18-40-05_FALLIDO"])

        # El siguiente respaldo no reutiliza el nombre de la carpeta fallida
        self.assertEqual(self.respaldar().carpeta.name, "2026-10-27_18-40-05_2")

    def test_respaldo_mientras_se_guarda_un_pedido(self):
        # Otra conexión está guardando un pedido y todavía no termina
        escritor = sqlite3.connect(self.ruta_db)
        try:
            escritor.execute("BEGIN IMMEDIATE")
            escritor.execute(
                """INSERT INTO produccion (fecha, pieza_id, material_id, lleva_lona, cantidad,
                       material_recibido_g, material_sobrante_g)
                   VALUES ('2026-10-23', 1, 1, 0, 10, 500, 20)"""
            )
            resultado = self.respaldar()
            escritor.commit()
        finally:
            escritor.close()
        # La foto tiene solo lo que ya estaba guardado, completo y sano
        self.assertEqual(resultado.conteo["registros"], 1)

    def test_cuenta_la_papelera(self):
        self.ejecutar("UPDATE produccion SET borrado_en = '2026-10-27 10:00:00'")
        resultado = self.respaldar()
        self.assertEqual(resultado.conteo["registros"], 1)
        self.assertEqual(resultado.conteo["en_papelera"], 1)

    def test_extra_que_falta_avisa_pero_respalda_la_base(self):
        resultado = self.respaldar([self.notas, self.carpeta / "no-existe.md"])
        self.assertEqual(resultado.extras, ["notas.md"])
        self.assertEqual(resultado.extras_faltantes, ["no-existe.md"])
        self.assertTrue(resultado.archivo_db.is_file())

    def test_drive_solo_para_la_base_real(self):
        otra = self.carpeta / "copia.db"
        otra.write_bytes(self.ruta_db.read_bytes())
        with self.assertRaises(respaldo.RespaldoNoPermitido):
            respaldo.hacer_respaldo(otra, self.destino, ahora=AHORA)
        self.assertFalse(self.destino.carpeta.exists())

    def test_lista_de_extras(self):
        lista = self.carpeta / "respaldo_extra.txt"
        lista.write_text("# comentario\nnotas.md\n\n", encoding="utf-8")
        self.assertEqual(respaldo.leer_extras(lista), [self.notas])
        self.assertEqual(respaldo.leer_extras(self.carpeta / "no-existe.txt"), [])
        self.assertEqual(respaldo.leer_extras(None), [])

    def test_estado_del_ultimo_respaldo(self):
        estado = self.carpeta / "estado" / "ultimo_respaldo.txt"
        self.assertIsNone(respaldo.ultimo_respaldo(estado))
        resultado = self.respaldar()
        respaldo.anotar_respaldo(estado, resultado)
        self.assertEqual(respaldo.ultimo_respaldo(estado), (AHORA, str(resultado.carpeta)))
        estado.write_text("cualquier cosa", encoding="utf-8")
        self.assertIsNone(respaldo.ultimo_respaldo(estado))


class ModoPruebaTest(unittest.TestCase):
    def test_modo_prueba_nunca_usa_drive(self):
        for ruta in (datos_prueba.RUTA_PRUEBA, respaldo.RUTA_REAL):
            destino, estado, lista = respaldo.configuracion(ruta, modo_prueba=True)
            self.assertIs(destino, respaldo.PRUEBA)
            self.assertFalse(destino.en_drive)
            self.assertFalse(destino.carpeta.is_relative_to(respaldo.UNIDAD_DRIVE))
            self.assertNotEqual(estado, respaldo.ESTADO_REAL)
            self.assertIsNone(lista)  # sin archivos extra

    def test_base_real_va_a_drive_y_las_copias_a_ningun_lado(self):
        self.assertIs(respaldo.configuracion(respaldo.RUTA_REAL, False)[0], respaldo.DRIVE)
        self.assertEqual(respaldo.configuracion(Path("otra.db"), False), (None, None, None))

    def test_prueba_no_puede_ir_a_drive(self):
        # Aunque alguien le pase el destino de Drive a la base de prueba
        with self.assertRaises(respaldo.RespaldoNoPermitido):
            respaldo.hacer_respaldo(datos_prueba.RUTA_PRUEBA, respaldo.DRIVE)


class PaginaRespaldoTest(ConDriveFalso):
    def setUp(self):
        super().setUp()
        self.app = crear_app(self.ruta_db)
        self.app.config["TESTING"] = True
        self.estado = self.carpeta / "ultimo_respaldo.txt"
        # Antes de cualquier visita: el destino es el "Drive" temporal, nunca G:
        self.app.config.update(
            DESTINO_RESPALDO=self.destino,
            ESTADO_RESPALDO=self.estado,
            LISTA_EXTRA_RESPALDO=None,
        )
        self.cliente = self.app.test_client()

    def html(self, direccion):
        respuesta = self.cliente.get(direccion, follow_redirects=True)
        self.assertEqual(respuesta.status_code, 200)
        return respuesta.get_data(as_text=True)

    def test_abrir_la_pagina_no_escribe_nada(self):
        antes = todo_lo_que_hay(self.carpeta)
        html = self.html("/respaldo")
        self.assertIn("Exportar respaldo ahora", html)
        self.assertIn("✔ Disponible", html)
        self.assertEqual(todo_lo_que_hay(self.carpeta), antes)

    def test_boton_hace_el_respaldo_y_lo_anota(self):
        respuesta = self.cliente.post("/respaldo", follow_redirects=True)
        html = respuesta.get_data(as_text=True)
        self.assertIn("Respaldo verificado en", html)
        self.assertIn("1 registro (0 en la papelera)", html)
        self.assertIn("Google Drive lo subirá a la nube", html)
        self.assertEqual(len(list(self.destino.carpeta.iterdir())), 1)
        self.assertIsNotNone(respaldo.ultimo_respaldo(self.estado))

    def test_drive_cerrado_muestra_error_claro(self):
        self.app.config["DESTINO_RESPALDO"] = respaldo.Destino(
            self.carpeta / "G-cerrado" / "respaldos", self.carpeta / "G-cerrado", "Google Drive"
        )
        self.assertIn("✖ No disponible", self.html("/respaldo"))
        html = self.cliente.post("/respaldo", follow_redirects=True).get_data(as_text=True)
        self.assertIn("Google Drive no está disponible", html)
        self.assertIn("No se hizo el respaldo", html)
        self.assertIsNone(respaldo.ultimo_respaldo(self.estado))

    def test_aviso_de_siete_dias(self):
        self.assertIn("Todavía no hay ningún respaldo", self.html("/historial"))

        hace = datetime.combine(date.today() - timedelta(days=8), datetime.min.time())
        self.estado.write_text(f"{hace.isoformat()}\ncarpeta\n", encoding="utf-8")
        self.assertIn("Último respaldo: hace 8 días", self.html("/registrar"))

        hace = datetime.combine(date.today() - timedelta(days=2), datetime.min.time())
        self.estado.write_text(f"{hace.isoformat()}\ncarpeta\n", encoding="utf-8")
        self.assertNotIn("franja-respaldo", self.html("/historial"))

    def test_sin_aviso_en_la_propia_pagina_de_respaldo(self):
        self.assertNotIn("franja-respaldo", self.html("/respaldo"))

    def test_copia_de_la_base_desactiva_el_respaldo(self):
        copia = self.carpeta / "copia.db"  # una base que no es la real
        copia.write_bytes(self.ruta_db.read_bytes())
        app = crear_app(copia)
        self.assertIsNone(app.config["DESTINO_RESPALDO"])
        app.config["TESTING"] = True
        cliente = app.test_client()
        self.assertIn("El respaldo está desactivado",
                      cliente.get("/respaldo").get_data(as_text=True))
        self.assertNotIn("franja-respaldo", cliente.get("/historial").get_data(as_text=True))
        html = cliente.post("/respaldo", follow_redirects=True).get_data(as_text=True)
        self.assertIn("El respaldo está desactivado", html)


if __name__ == "__main__":
    unittest.main()
