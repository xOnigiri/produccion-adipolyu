"""Pruebas de la página "Listas": agregar, corregir nombre, desactivar y reactivar
piezas y materiales.

Cada prueba usa una base nueva en una carpeta temporal. Nunca abre produccion.db.
"""

import sqlite3
import unittest
from datetime import date

import crear_base
from tests.test_historial import ConHistorial
from validacion import MAX_NOMBRE, clave_nombre, limpiar_nombre, validar_nombre

HOY = date.today()


class NombresTest(unittest.TestCase):
    """Reglas de los nombres, sin base de datos."""

    LISTA = [
        {"id": 1, "nombre": "retén", "activo": 1},
        {"id": 2, "nombre": "soporte", "activo": 1},
        {"id": 3, "nombre": "jebe azul", "activo": 0},
    ]

    def test_limpia_espacios_y_guarda_en_minusculas(self):
        self.assertEqual(limpiar_nombre("  Silicona   NARANJA "), "silicona naranja")
        self.assertEqual(limpiar_nombre("RETÉN"), "retén")

    def test_mayusculas_tildes_y_espacios_cuentan_como_el_mismo(self):
        for escrito in ("Retén", "retén ", " RETEN ", "reten", "RETÉN"):
            with self.subTest(escrito=escrito):
                self.assertEqual(clave_nombre(escrito), "reten")

    def test_la_enie_no_es_una_n(self):
        self.assertNotEqual(clave_nombre("caña"), clave_nombre("cana"))

    def test_nuevo_repetido_se_rechaza(self):
        for escrito in ("Retén", " reten ", "SOPORTE"):
            with self.subTest(escrito=escrito):
                nombre, error, repetido = validar_nombre(escrito, self.LISTA)
                self.assertIsNone(nombre)
                self.assertIn("Ya existe", error)
                self.assertIsNotNone(repetido)

    def test_repetido_inactivo_se_informa(self):
        _, error, repetido = validar_nombre("Jebe  Azul", self.LISTA)
        self.assertEqual(error, "Ya existe «jebe azul».")
        self.assertEqual(repetido["id"], 3)

    def test_nuevo_valido(self):
        self.assertEqual(validar_nombre("  Buje ", self.LISTA), ("buje", None, None))

    def test_vacio_y_demasiado_largo(self):
        self.assertEqual(validar_nombre("   ", self.LISTA)[1], "Escribe el nombre.")
        self.assertIn(str(MAX_NOMBRE), validar_nombre("a" * (MAX_NOMBRE + 1), self.LISTA)[1])

    def test_corregir_solo_tildes_o_mayusculas_se_permite(self):
        lista = [{"id": 1, "nombre": "reten", "activo": 1}, *self.LISTA[1:]]
        for escrito in ("retén", "Retén", " RETÉN "):
            with self.subTest(escrito=escrito):
                self.assertEqual(
                    validar_nombre(escrito, lista, propio=lista[0]), ("retén", None, None)
                )

    def test_corregir_al_nombre_de_otro_se_rechaza(self):
        nombre, error, repetido = validar_nombre("Retén", self.LISTA, propio=self.LISTA[1])
        self.assertIsNone(nombre)
        self.assertEqual(error, "Ya existe «retén».")
        self.assertEqual(repetido["id"], 1)

    def test_corregir_al_mismo_nombre_no_hace_nada(self):
        _, error, _ = validar_nombre(" Retén ".lower(), self.LISTA, propio=self.LISTA[0])
        self.assertIn("mismo nombre", error)


class ConListas(ConHistorial):
    """Ayudas comunes: la página y la base de datos juntas."""

    def consultar(self, sql, *valores):
        conexion = sqlite3.connect(self.ruta_db)
        conexion.row_factory = sqlite3.Row
        try:
            return conexion.execute(sql, valores).fetchall()
        finally:
            conexion.close()

    def ejecutar(self, sql, *valores):
        conexion = sqlite3.connect(self.ruta_db)
        try:
            conexion.execute(sql, valores)
            conexion.commit()
        finally:
            conexion.close()

    def pieza(self, pieza_id):
        return self.consultar("SELECT * FROM piezas WHERE id = ?", pieza_id)[0]

    def total_filas(self):
        return {
            tabla: self.consultar(f"SELECT COUNT(*) AS n FROM {tabla}")[0]["n"]
            for tabla in ("piezas", "materiales", "produccion")
        }

    def opciones_del_formulario(self):
        return self.html("/registrar")


class PaginaListasTest(ConListas):
    def test_muestra_las_dos_listas_con_estado_y_uso(self):
        self.insertar(HOY)
        self.insertar(HOY)
        en_papelera = self.insertar(HOY)
        self.cliente.post(f"/registro/{en_papelera}/borrar")

        html = self.html("/listas")
        self.assertIn("<h2>Piezas", html)
        self.assertIn("<h2>Materiales", html)
        self.assertIn("· 4 activas", html)
        self.assertIn("· 7 activos", html)
        self.assertIn("+1 en papelera", html)
        # La pieza desactivada sale en gris, con su estado y el botón para reactivarla
        self.assertIn('<tr class="fila-inactiva">\n              <td>pieza retirada</td>', html)
        self.assertIn(f"/listas/piezas/{self.piezas['pieza retirada']}/reactivar", html)

    def test_el_menu_lleva_a_listas(self):
        html = self.html("/registrar")
        self.assertIn('href="/listas"', html)
        self.assertIn('class="activo" aria-current="page">Listas', self.html("/listas"))

    def test_lista_desconocida(self):
        self.assertEqual(self.cliente.post("/listas/clientes/agregar").status_code, 404)


class AgregarTest(ConListas):
    def test_agregar_limpia_el_nombre_y_aparece_en_el_formulario(self):
        respuesta = self.cliente.post("/listas/piezas/agregar", data={"nombre": "  Buje   GRANDE "})
        self.assertEqual(respuesta.status_code, 302)
        # El aviso verde sale en la página siguiente
        self.assertIn("Se agregó la pieza «buje grande»", self.html("/listas"))
        fila = self.consultar("SELECT * FROM piezas WHERE nombre = 'buje grande'")[0]
        self.assertEqual(fila["activo"], 1)
        self.assertIn(f'<option value="{fila["id"]}" >buje grande</option>',
                      self.opciones_del_formulario())

    def test_agregar_material(self):
        self.cliente.post("/listas/materiales/agregar", data={"nombre": "Jebe Negro"})
        self.assertEqual(len(self.consultar(
            "SELECT * FROM materiales WHERE nombre = 'jebe negro'")), 1)
        self.assertIn("Se agregó el material «jebe negro»", self.html("/listas"))

    def test_agregar_duplicado_no_guarda_nada(self):
        antes = self.total_filas()
        for escrito in ("Retén", " reten", "RETEN", "anillo "):
            with self.subTest(escrito=escrito):
                respuesta = self.cliente.post("/listas/piezas/agregar", data={"nombre": escrito})
                self.assertEqual(respuesta.status_code, 422)
                self.assertIn("Ya existe «", respuesta.get_data(as_text=True))
        self.assertEqual(self.total_filas(), antes)

    def test_agregar_duplicado_de_un_inactivo_ofrece_reactivarlo(self):
        respuesta = self.cliente.post("/listas/piezas/agregar", data={"nombre": "Pieza Retirada"})
        html = respuesta.get_data(as_text=True)
        self.assertEqual(respuesta.status_code, 422)
        self.assertIn("Está inactiva.", html)
        self.assertIn("Reactivar «pieza retirada»", html)
        # Lo escrito se conserva en la casilla
        self.assertIn('value="Pieza Retirada"', html)

    def test_agregar_vacio(self):
        respuesta = self.cliente.post("/listas/materiales/agregar", data={"nombre": "  "})
        self.assertEqual(respuesta.status_code, 422)
        self.assertIn("Escribe el nombre.", respuesta.get_data(as_text=True))


class CorregirNombreTest(ConListas):
    def test_corregir_pide_confirmacion_con_el_conteo_antes_de_guardar(self):
        id_reten = self.piezas["retén"]
        for _ in range(3):
            self.insertar(HOY)
        borrado = self.insertar(HOY)
        self.cliente.post(f"/registro/{borrado}/borrar")

        respuesta = self.cliente.post(
            f"/listas/piezas/{id_reten}/nombre", data={"nombre": "Retén Grande", "paso": "revisar"}
        )
        html = respuesta.get_data(as_text=True)
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("«retén» → «retén grande»", html)
        self.assertIn("Afecta a <strong>3 registros (y 1 en la papelera)</strong>", html)
        self.assertIn('name="paso" value="confirmar"', html)
        # Todavía no cambió nada
        self.assertEqual(self.pieza(id_reten)["nombre"], "retén")

    def test_corregir_confirmado_cambia_el_nombre_en_todos_los_registros(self):
        id_reten = self.piezas["retén"]
        registro_id = self.insertar(HOY)
        respuesta = self.cliente.post(
            f"/listas/piezas/{id_reten}/nombre",
            data={"nombre": "retén grande", "paso": "confirmar"},
        )
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("Nombre corregido: «retén» → «retén grande». Ya se ve así en 1 registro.",
                      self.html("/listas"))
        self.assertEqual(self.pieza(id_reten)["nombre"], "retén grande")
        # El registro sigue apuntando a la misma pieza: no se reescribió
        self.assertEqual(self.fila(registro_id)["pieza_id"], id_reten)
        self.assertIn("<td>retén grande</td>", self.html("/historial"))

    def test_corregir_solo_la_tilde_reten_a_reten_con_tilde(self):
        # Una pieza escrita sin tilde por error
        self.ejecutar("UPDATE piezas SET nombre = 'reten' WHERE nombre = 'retén'")
        id_reten = self.piezas["retén"]
        self.insertar(HOY)

        revisar = self.cliente.post(
            f"/listas/piezas/{id_reten}/nombre", data={"nombre": "Retén", "paso": "revisar"}
        )
        self.assertEqual(revisar.status_code, 200)
        self.assertIn("«reten» → «retén»", revisar.get_data(as_text=True))

        confirmar = self.cliente.post(
            f"/listas/piezas/{id_reten}/nombre", data={"nombre": "retén", "paso": "confirmar"}
        )
        self.assertEqual(confirmar.status_code, 302)
        self.assertEqual(self.pieza(id_reten)["nombre"], "retén")

    def test_corregir_al_nombre_de_otra_pieza_se_rechaza(self):
        id_soporte = self.piezas["soporte"]
        for paso in ("revisar", "confirmar"):
            with self.subTest(paso=paso):
                respuesta = self.cliente.post(
                    f"/listas/piezas/{id_soporte}/nombre", data={"nombre": "RETEN", "paso": paso}
                )
                self.assertEqual(respuesta.status_code, 422)
                self.assertIn("Ya existe «retén».", respuesta.get_data(as_text=True))
        self.assertEqual(self.pieza(id_soporte)["nombre"], "soporte")

    def test_corregir_muestra_el_nombre_actual(self):
        html = self.html(f"/listas/materiales/{self.materiales['nitrilo']}/nombre")
        self.assertIn("Nombre actual: <strong>«nitrilo»</strong> · usado en ningún registro.", html)

    def test_corregir_algo_que_no_existe(self):
        respuesta = self.cliente.get("/listas/piezas/999/nombre", follow_redirects=True)
        self.assertIn("Ese nombre no está en la lista de piezas.", respuesta.get_data(as_text=True))


class ActivarDesactivarTest(ConListas):
    def test_desactivar_lo_saca_del_formulario_pero_no_del_historial(self):
        id_reten = self.piezas["retén"]
        registro_id = self.insertar(HOY)

        self.cliente.post(f"/listas/piezas/{id_reten}/desactivar")
        self.assertIn("Sus registros (1 registro) siguen en el historial", self.html("/listas"))
        self.assertEqual(self.pieza(id_reten)["activo"], 0)
        self.assertNotIn(">retén</option>", self.opciones_del_formulario())

        historial = self.html("/historial")
        self.assertIn("<td>retén</td>", historial)
        self.assertIn(">retén (inactiva)</option>", historial)
        # Filtrar por la pieza inactiva y sacar su PDF sigue funcionando
        self.assertIn("<td>retén</td>", self.html(f"/historial?pieza_id={id_reten}"))
        pdf = self.cliente.get(f"/historial/pdf?pieza_id={id_reten}")
        self.assertEqual(pdf.mimetype, "application/pdf")
        # Al corregir un registro antiguo, su pieza sigue en la lista
        self.assertIn(">retén</option>", self.html(f"/registro/{registro_id}/corregir"))

    def test_reactivar_lo_devuelve_al_formulario(self):
        id_retirada = self.piezas["pieza retirada"]
        self.cliente.post(f"/listas/piezas/{id_retirada}/reactivar")
        self.assertEqual(self.pieza(id_retirada)["activo"], 1)
        self.assertIn(">pieza retirada</option>", self.opciones_del_formulario())

    def test_no_se_desactiva_el_ultimo_material_activo(self):
        id_nitrilo = self.materiales["nitrilo"]
        self.ejecutar("UPDATE materiales SET activo = 0 WHERE id != ?", id_nitrilo)

        html = self.html("/listas")
        self.assertNotIn(f"/listas/materiales/{id_nitrilo}/desactivar", html)
        self.assertIn("Debe quedar al menos un material activo. Agrega o reactiva otro primero.",
                      html)

        # Aunque alguien envíe el botón de todos modos, la base no lo permite
        respuesta = self.cliente.post(f"/listas/materiales/{id_nitrilo}/desactivar",
                                      follow_redirects=True)
        self.assertIn("aviso-error", respuesta.get_data(as_text=True))
        self.assertEqual(self.consultar(
            "SELECT activo FROM materiales WHERE id = ?", id_nitrilo)[0]["activo"], 1)

    def test_no_se_desactiva_la_ultima_pieza_activa(self):
        id_anillo = self.piezas["anillo"]
        self.ejecutar("UPDATE piezas SET activo = 0 WHERE id != ?", id_anillo)
        self.cliente.post(f"/listas/piezas/{id_anillo}/desactivar")
        self.assertEqual(self.pieza(id_anillo)["activo"], 1)
        self.assertIn("Debe quedar al menos una pieza activa. Agrega o reactiva otra primero.",
                      self.html("/listas"))


class NadaSeBorraTest(ConListas):
    def test_nunca_se_borra_nada(self):
        self.insertar(HOY)
        antes = self.total_filas()
        id_reten = self.piezas["retén"]
        self.cliente.post(f"/listas/piezas/{id_reten}/desactivar")
        self.cliente.post(f"/listas/piezas/{id_reten}/reactivar")
        self.cliente.post(f"/listas/piezas/{id_reten}/nombre",
                          data={"nombre": "retén x", "paso": "confirmar"})
        self.assertEqual(self.total_filas(), antes)
        # No existe ninguna dirección para borrar
        self.assertEqual(self.cliente.post(f"/listas/piezas/{id_reten}/borrar").status_code, 404)

    def test_crear_base_no_devuelve_un_nombre_corregido(self):
        # El MODO PRUEBA ejecuta crear_base en cada arranque
        id_azul = self.materiales["jebe azul"]
        self.cliente.post(f"/listas/materiales/{id_azul}/nombre",
                          data={"nombre": "jebe azul marino", "paso": "confirmar"})
        crear_base.crear_base(self.ruta_db, informar=False)
        nombres = {fila["nombre"] for fila in self.consultar("SELECT nombre FROM materiales")}
        self.assertIn("jebe azul marino", nombres)
        self.assertNotIn("jebe azul", nombres)


if __name__ == "__main__":
    unittest.main()
