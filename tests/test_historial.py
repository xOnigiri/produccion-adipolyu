"""Pruebas del historial, corregir, borrar (papelera) y restaurar.

Cada prueba usa una base nueva en una carpeta temporal. Nunca abre produccion.db.
"""

import re
import sqlite3
import unittest
from datetime import date, timedelta

from app import _leer_filtros
from tests.test_app import PruebaConBase

HOY = date.today()

# Un retén de nitrilo con lona: 3600.5 g recibidos, 400 g sobrantes, 50 unidades
PEDIDO = {
    "pieza": "retén",
    "material": "nitrilo",
    "cantidad": 50,
    "recibido": 3600.5,
    "sobrante": 400,
    "lona": (250, 30),
    "observaciones": None,
    "dureza": None,
}


class ConHistorial(PruebaConBase):
    """Ayudas comunes de las pruebas de este archivo."""

    def insertar(self, fecha, **cambios):
        """Guarda directo en la base un PEDIDO con los cambios indicados."""
        pedido = {**PEDIDO, **cambios}
        lona = pedido["lona"]
        conexion = sqlite3.connect(self.ruta_db)
        try:
            cursor = conexion.execute(
                """INSERT INTO produccion (fecha, pieza_id, material_id, lleva_lona, cantidad,
                       material_recibido_g, material_sobrante_g, lona_recibida_g,
                       lona_sobrante_g, observaciones, dureza_shore_a)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    fecha.isoformat(),
                    self.piezas[pedido["pieza"]],
                    self.materiales[pedido["material"]],
                    1 if lona else 0,
                    pedido["cantidad"],
                    pedido["recibido"],
                    pedido["sobrante"],
                    lona[0] if lona else None,
                    lona[1] if lona else None,
                    pedido["observaciones"],
                    pedido["dureza"],
                ),
            )
            conexion.commit()
            return cursor.lastrowid
        finally:
            conexion.close()

    def fila(self, registro_id):
        conexion = sqlite3.connect(self.ruta_db)
        conexion.row_factory = sqlite3.Row
        try:
            return conexion.execute(
                "SELECT * FROM produccion WHERE id = ?", (registro_id,)
            ).fetchone()
        finally:
            conexion.close()

    def html(self, direccion):
        respuesta = self.cliente.get(direccion)
        self.assertEqual(respuesta.status_code, 200)
        return respuesta.get_data(as_text=True)

    def formulario(self, **cambios):
        datos = {
            "fecha": HOY.isoformat(),
            "pieza_id": str(self.piezas["retén"]),
            "material_id": str(self.materiales["nitrilo"]),
            "cantidad": "50",
            "material_recibido_g": "3600,5",
            "material_sobrante_g": "400",
            "lleva_lona": "si",
            "lona_recibida_g": "250",
            "lona_sobrante_g": "30",
            "observaciones": "",
        }
        datos.update(cambios)
        return datos


class VerHistorialTest(ConHistorial):
    def test_historial_vacio(self):
        html = self.html("/historial")
        self.assertIn("No hay registros en este periodo", html)
        self.assertIn('class="activo" aria-current="page">Historial', html)

    def test_muestra_columnas_en_gramos_y_kg(self):
        self.insertar(HOY, observaciones="2 piezas con burbuja")
        html = self.html("/historial")
        for texto in ("3600.5 g", "400 g", "3.20 kg", "64 g", "250 g", "30 g", "0.22 kg",
                      "2 piezas con burbuja", "retén", "nitrilo"):
            self.assertIn(texto, html)

    def test_acciones_van_al_inicio_de_cada_fila(self):
        self.insertar(HOY)
        self.insertar(HOY - timedelta(days=1))
        html = self.html("/historial?periodo=todo")
        # Las 2 filas de pedidos empiezan con la celda de acciones (con Corregir y Borrar)
        filas = re.findall(r'<tr>\s*<td class="acciones">\s*<a [^>]*>Corregir</a>\s*<a ', html)
        self.assertEqual(len(filas), 2)

    def test_sin_lona_muestra_guion(self):
        self.insertar(HOY, lona=None, dureza=70)
        html = self.html("/historial")
        self.assertEqual(html.count('vacio-celda">—'), 3)

    def test_orden_mas_reciente_primero(self):
        ayer = HOY - timedelta(days=1)
        self.insertar(ayer, observaciones="ayer-1")
        self.insertar(HOY, observaciones="hoy")
        self.insertar(ayer, observaciones="ayer-2")
        html = self.html("/historial?periodo=todo")
        posiciones = [html.index(nota) for nota in ("hoy", "ayer-2", "ayer-1")]
        self.assertEqual(posiciones, sorted(posiciones))

    def test_totales_del_periodo_en_kg(self):
        self.insertar(HOY)  # 3200.5 g usados, 220 g de lona
        self.insertar(HOY, pieza="anillo", material="silicona naranja", cantidad=120,
                      recibido=2000, sobrante=150, lona=None)
        html = self.html("/historial")
        self.assertIn("170", html)  # 50 + 120 piezas
        self.assertIn("5.05 kg", html)  # 3200.5 + 1850 g
        self.assertIn("0.22 kg", html)
        self.assertIn("1.85 kg", html)  # silicona naranja usada
        self.assertIn("0.15 kg", html)  # silicona naranja sobrante

    def test_total_redondea_igual_que_las_filas(self):
        # Filas: 525 g -> 0.53 kg y 220 g -> 0.22 kg. Total: 745 g -> 0.75 kg (no 0.74)
        self.insertar(HOY, material="jebe azul", lona=(600, 75))
        self.insertar(HOY)
        html = self.html("/historial")
        self.assertIn("0.53 kg", html)
        self.assertIn("0.22 kg", html)
        self.assertIn("0.75 kg", html)
        self.assertNotIn("0.74 kg", html)

    def test_menu_en_todas_las_paginas(self):
        for direccion in ("/registrar", "/historial", "/papelera"):
            html = self.html(direccion)
            for enlace in ("Registrar", "Historial", "Papelera"):
                self.assertIn(f">{enlace}</a>", html)
            self.assertNotIn("MODO PRUEBA", html)


class FiltrosTest(ConHistorial):
    def test_por_defecto_solo_esta_semana(self):
        lunes = HOY - timedelta(days=HOY.weekday())
        self.insertar(lunes, observaciones="de esta semana")
        self.insertar(lunes - timedelta(days=1), observaciones="del domingo pasado")
        html = self.html("/historial")
        self.assertIn("de esta semana", html)
        self.assertNotIn("del domingo pasado", html)
        self.assertIn(f"Semana del lunes {lunes:%d/%m/%Y}", html)

        html = self.html("/historial?periodo=pasada")
        self.assertIn("del domingo pasado", html)
        self.assertNotIn("de esta semana", html)

    def test_filtro_por_rango_pieza_y_material(self):
        self.insertar(date(2026, 10, 5), observaciones="retén nitrilo octubre")
        self.insertar(date(2026, 10, 6), pieza="anillo", observaciones="anillo nitrilo")
        self.insertar(date(2026, 10, 7), material="jebe azul", observaciones="retén azul")
        self.insertar(date(2026, 9, 30), observaciones="retén septiembre")

        html = self.html(
            "/historial?periodo=rango&desde=2026-10-01&hasta=2026-10-31"
            f"&pieza_id={self.piezas['retén']}&material_id={self.materiales['nitrilo']}"
        )
        self.assertIn("retén nitrilo octubre", html)
        for fuera in ("anillo nitrilo", "retén azul", "retén septiembre"):
            self.assertNotIn(fuera, html)
        self.assertIn(
            "Del 01/10/2026 al 31/10/2026</strong> · retén · nitrilo · 1 pedido",
            " ".join(html.split()),
        )

    def test_rango_al_reves_avisa(self):
        self.insertar(date(2026, 10, 5))
        html = self.html("/historial?periodo=rango&desde=2026-10-31&hasta=2026-10-01")
        self.assertIn("es posterior a", html)
        self.assertNotIn("3600.5 g", html)

    def test_filtros_raros_no_rompen_la_pagina(self):
        self.html("/historial?periodo=xyz&pieza_id=abc&desde=no-es-fecha")

    def test_leer_filtros_semana_pasada(self):
        filtros = _leer_filtros({"periodo": "pasada"}, date(2026, 10, 27))
        self.assertEqual((filtros["desde"], filtros["hasta"]), ("2026-10-19", "2026-10-25"))


class CorregirTest(ConHistorial):
    def test_corregir_muestra_formulario_lleno(self):
        registro_id = self.insertar(date(2026, 10, 22), observaciones="2 piezas con burbuja")
        html = self.html(f"/registro/{registro_id}/corregir")
        self.assertIn("Corregir registro", html)
        self.assertIn("Estás corrigiendo el pedido del 22/10/2026 · retén · nitrilo", html)
        self.assertIn('value="2026-10-22"', html)
        self.assertIn('value="3600.5"', html)
        self.assertIn('value="400"', html)
        self.assertIn("checked", html)
        self.assertIn("2 piezas con burbuja", html)
        self.assertIn("Guardar cambios", html)

    def test_corregir_muestra_los_gramos_sin_redondear(self):
        registro_id = self.insertar(HOY, recibido=3600.125)
        self.assertIn('value="3600.125"', self.html(f"/registro/{registro_id}/corregir"))

    def test_corregir_guarda_y_vuelve_al_historial_con_filtros(self):
        registro_id = self.insertar(HOY)
        volver = "/historial?periodo=todo"
        respuesta = self.cliente.post(
            f"/registro/{registro_id}/corregir",
            data=self.formulario(cantidad="48", lleva_lona="", volver=volver),
        )
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta.headers["Location"], volver)

        fila = self.fila(registro_id)
        self.assertEqual(fila["cantidad"], 48)
        self.assertEqual(fila["lleva_lona"], 0)
        self.assertIsNone(fila["lona_recibida_g"])

        html = self.html(volver)
        self.assertIn("Registro corregido:", html)
        self.assertIn("48 unidades", html)

    def test_corregir_aplica_las_mismas_reglas(self):
        registro_id = self.insertar(HOY)
        manana = (HOY + timedelta(days=1)).isoformat()
        casos = [
            ({"material_sobrante_g": "4000"}, "no puede ser mayor que el recibido"),
            ({"lona_sobrante_g": ""}, "Si el pedido lleva lona, anota la lona sobrante"),
            ({"cantidad": "0"}, "La cantidad debe ser mayor que 0"),
            ({"fecha": manana}, "La fecha no puede ser futura"),
        ]
        for cambio, mensaje in casos:
            with self.subTest(cambio=cambio):
                respuesta = self.cliente.post(
                    f"/registro/{registro_id}/corregir", data=self.formulario(**cambio)
                )
                self.assertEqual(respuesta.status_code, 422)
                html = respuesta.get_data(as_text=True)
                self.assertIn("No se guardaron los cambios", html)
                self.assertIn(mensaje, html)
        # El registro quedó como estaba
        self.assertEqual(self.fila(registro_id)["material_sobrante_g"], 400)

    def test_corregir_registro_con_pieza_desactivada(self):
        registro_id = self.insertar(HOY, pieza="pieza retirada")
        html = self.html(f"/registro/{registro_id}/corregir")
        self.assertIn("pieza retirada", html)

        respuesta = self.cliente.post(
            f"/registro/{registro_id}/corregir",
            data=self.formulario(pieza_id=str(self.piezas["pieza retirada"]), cantidad="7"),
        )
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(self.fila(registro_id)["cantidad"], 7)

        # Pero en un registro nuevo no aparece
        self.assertNotIn(">pieza retirada</option>", self.html("/registrar"))

    def test_corregir_registro_inexistente(self):
        respuesta = self.cliente.get("/registro/999/corregir", follow_redirects=True)
        self.assertIn("Ese registro no existe", respuesta.get_data(as_text=True))

    def test_volver_solo_acepta_el_historial(self):
        registro_id = self.insertar(HOY)
        respuesta = self.cliente.post(
            f"/registro/{registro_id}/corregir",
            data=self.formulario(volver="https://otro-sitio.com/"),
        )
        self.assertEqual(respuesta.headers["Location"], "/historial")


class BorrarTest(ConHistorial):
    def test_confirmacion_dice_que_registro_se_borra(self):
        registro_id = self.insertar(date(2026, 10, 22))
        html = self.html(f"/registro/{registro_id}/borrar")
        self.assertIn("¿Borrar este registro?", html)
        self.assertIn(
            "22/10/2026 · retén · nitrilo · con lona · 50 unidades · material usado 3.20 kg", html
        )
        self.assertIn("Sí, borrar", html)
        self.assertIn("No, volver", html)
        # Solo mostrar la confirmación no borra nada
        self.assertIsNone(self.fila(registro_id)["borrado_en"])

    def test_borrar_envia_a_papelera_y_restaurar_lo_devuelve(self):
        registro_id = self.insertar(HOY, observaciones="pedido de prueba")

        respuesta = self.cliente.post(f"/registro/{registro_id}/borrar", follow_redirects=True)
        html = respuesta.get_data(as_text=True)
        self.assertIn("Registro enviado a la papelera", html)
        self.assertIn("No hay registros en este periodo", html)

        # Sigue en la base, solo marcado
        self.assertIsNotNone(self.fila(registro_id)["borrado_en"])

        papelera = self.html("/papelera")
        self.assertIn("pedido de prueba", papelera)
        self.assertIn("Restaurar", papelera)

        respuesta = self.cliente.post(f"/registro/{registro_id}/restaurar", follow_redirects=True)
        html = respuesta.get_data(as_text=True)
        self.assertIn("Registro restaurado", html)
        self.assertIn("La papelera está vacía", html)
        self.assertIsNone(self.fila(registro_id)["borrado_en"])
        self.assertIn("pedido de prueba", self.html("/historial"))

    def test_papelera_no_cuenta_en_totales(self):
        self.insertar(HOY)
        borrado = self.insertar(HOY, cantidad=999)
        self.cliente.post(f"/registro/{borrado}/borrar", follow_redirects=True)
        html = self.html("/historial")  # ya sin el mensaje verde, que menciona el 999
        self.assertNotIn("999", html)
        self.assertIn("1 pedido", html)

    def test_registro_en_papelera_no_se_corrige_ni_se_borra_dos_veces(self):
        registro_id = self.insertar(HOY)
        self.cliente.post(f"/registro/{registro_id}/borrar")
        primera_vez = self.fila(registro_id)["borrado_en"]

        respuesta = self.cliente.get(f"/registro/{registro_id}/corregir", follow_redirects=True)
        self.assertIn("Ese registro está en la papelera", respuesta.get_data(as_text=True))
        self.cliente.post(f"/registro/{registro_id}/corregir", data=self.formulario(cantidad="1"))
        self.assertEqual(self.fila(registro_id)["cantidad"], 50)

        self.cliente.post(f"/registro/{registro_id}/borrar")
        self.assertEqual(self.fila(registro_id)["borrado_en"], primera_vez)


if __name__ == "__main__":
    unittest.main()
