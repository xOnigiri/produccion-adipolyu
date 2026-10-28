"""Pruebas del diseño: tarjetas de números, comparación con la semana pasada,
logo, icono de la pestaña, nombres con mayúscula inicial y coma decimal.

Cada prueba usa una base nueva en una carpeta temporal. Nunca abre produccion.db.
"""

import json
import re
import unittest
from datetime import date, timedelta
from pathlib import Path

import calculos
import formato
import informe_pdf
from app import crear_app
from tests.test_historial import HOY, ConHistorial
from tests.test_informe import texto_del_pdf

LUNES = HOY - timedelta(days=HOY.weekday())
LUNES_PASADO = LUNES - timedelta(days=7)
LUNES_ANTEPASADO = LUNES - timedelta(days=14)


def cifras(html):
    """{nombre de la tarjeta: (valor grande, línea de abajo o None)}."""
    resultado = {}
    for tarjeta in re.findall(r'<div class="cifra">(.*?)</div>', html, re.S):
        nombre = re.search(r'<p class="cifra-nombre">(.*?)</p>', tarjeta).group(1)
        valor = re.search(r'<p class="cifra-valor">(.*?)</p>', tarjeta).group(1)
        antes = re.search(r'<p class="cifra-antes">(.*?)</p>', tarjeta)
        resultado[nombre] = (re.sub(r"<[^>]+>", " ", valor).split(),
                             antes and " ".join(antes.group(1).split()))
    return resultado


class NombreYComaTest(unittest.TestCase):
    def test_mayuscula_inicial_solo_al_mostrar(self):
        self.assertEqual(formato.nombre_visible("jebe natural"), "Jebe natural")
        self.assertEqual(formato.nombre_visible("retén"), "Retén")
        self.assertEqual(formato.nombre_visible("ñandú"), "Ñandú")
        self.assertEqual(formato.nombre_visible(""), "")

    def test_coma_decimal_sin_separador_de_miles(self):
        self.assertEqual(formato.texto_gramos(12345.5), "12345,5")
        self.assertEqual(formato.texto_kg(12345.5), "12,35 kg")


class TarjetasRegistrarTest(ConHistorial):
    def test_esta_semana_con_la_semana_pasada_debajo(self):
        self.insertar(LUNES)  # 50 piezas, 3200,5 g usados
        self.insertar(LUNES, pieza="anillo", cantidad=120, recibido=2000, sobrante=150,
                      lona=None)
        self.insertar(LUNES_PASADO, cantidad=30, recibido=1000, sobrante=100)
        # La papelera no cuenta
        borrado = self.insertar(LUNES, cantidad=999)
        self.cliente.post(f"/registro/{borrado}/borrar")

        html = self.html("/registrar")
        self.assertIn("Esta semana", html)
        self.assertEqual(cifras(html), {
            "Piezas producidas": (["170"], "Semana pasada: 30"),
            "Material usado": (["5,05", "kg"], "Semana pasada: 0,90 kg"),
            "Pedidos": (["2"], "Semana pasada: 1"),
        })

    def test_semana_vacia_muestra_ceros(self):
        self.assertEqual(cifras(self.html("/registrar"))["Piezas producidas"],
                         (["0"], "Semana pasada: 0"))

    def test_al_corregir_no_hay_tarjetas(self):
        registro_id = self.insertar(LUNES)
        html = self.html(f"/registro/{registro_id}/corregir")
        self.assertEqual(cifras(html), {})
        self.assertNotIn("Esta semana", html)


class TarjetasHistorialTest(ConHistorial):
    def setUp(self):
        super().setUp()
        self.insertar(LUNES)  # retén nitrilo, 50 piezas, lona 220 g
        self.insertar(LUNES_PASADO, cantidad=30)
        self.insertar(LUNES_PASADO, pieza="anillo", material="jebe azul", cantidad=7, lona=None)
        self.insertar(LUNES_ANTEPASADO, cantidad=11)

    def test_esta_semana_compara_con_la_pasada(self):
        tarjetas = cifras(self.html("/historial"))
        self.assertEqual(list(tarjetas),
                         ["Piezas producidas", "Material usado", "Lona usada", "Pedidos"])
        self.assertEqual(tarjetas["Piezas producidas"], (["50"], "Semana pasada: 37"))
        self.assertEqual(tarjetas["Lona usada"], (["0,22", "kg"], "Semana pasada: 0,22 kg"))
        self.assertEqual(tarjetas["Pedidos"], (["1"], "Semana pasada: 2"))

    def test_semana_pasada_compara_con_la_anterior(self):
        tarjetas = cifras(self.html("/historial?periodo=pasada"))
        self.assertEqual(tarjetas["Piezas producidas"], (["37"], "Semana anterior: 11"))

    def test_la_comparacion_usa_los_mismos_filtros(self):
        html = self.html(f"/historial?pieza_id={self.piezas['anillo']}")
        self.assertEqual(cifras(html)["Piezas producidas"], (["0"], "Semana pasada: 7"))

    def test_fechas_libres_y_todo_van_sin_comparacion(self):
        for direccion in ("/historial?periodo=todo",
                          f"/historial?periodo=rango&desde={LUNES_ANTEPASADO}&hasta={HOY}"):
            with self.subTest(direccion=direccion):
                tarjetas = cifras(self.html(direccion))
                self.assertEqual(tarjetas["Piezas producidas"], (["98"], None))

    def test_fechas_al_reves_sin_tarjetas(self):
        html = self.html(f"/historial?periodo=rango&desde={HOY}&hasta={LUNES_ANTEPASADO}")
        self.assertEqual(cifras(html), {})


class LogoEIconoTest(ConHistorial):
    def test_logo_del_menu_es_el_mismo_archivo_del_pdf(self):
        respuesta = self.cliente.get("/logo.png")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.mimetype, "image/png")
        self.assertEqual(respuesta.data, Path("logo-adipolyu.png").read_bytes())
        respuesta.close()

    def test_sin_logo_el_menu_dice_adipolyu(self):
        app = crear_app(self.ruta_db, ruta_logo=Path(self.ruta_db).parent / "no-existe.png")
        cliente = app.test_client()
        html = cliente.get("/registrar").get_data(as_text=True)
        self.assertNotIn('src="/logo.png"', html)
        self.assertIn("ADIPOLYU", html)
        self.assertEqual(cliente.get("/logo.png").status_code, 404)

    def test_icono_de_la_pestana(self):
        respuesta = self.cliente.get("/static/icono.png")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.mimetype, "image/png")
        respuesta.close()


class PastillasTest(ConHistorial):
    def test_lona_en_pastillas(self):
        self.insertar(HOY)
        self.insertar(HOY, lona=None)
        html = self.html("/historial")
        self.assertIn('<span class="pastilla pastilla-naranja">Con lona</span>', html)
        self.assertIn('<span class="pastilla pastilla-gris">Sin lona</span>', html)

    def test_papelera_con_boton_restaurar_verde(self):
        registro_id = self.insertar(HOY)
        self.cliente.post(f"/registro/{registro_id}/borrar")
        html = self.html("/papelera")
        self.assertIn('class="tabla tabla-papelera"', html)
        self.assertIn('class="boton boton-pequeno boton-verde">Restaurar</button>', html)


class NotificacionesTest(ConHistorial):
    def notificaciones(self, html):
        """Textos de las notificaciones flotantes de la página."""
        caja = html.split('<div class="notificaciones', 1)[1].split("<script", 1)[0]
        return [" ".join(texto.split()) for texto in
                re.findall(r'<p class="notificacion-texto">(.*?)</p>', caja, re.S)]

    def test_exito_flota_con_boton_para_cerrar(self):
        respuesta = self.cliente.post("/registrar", data=self.formulario(), follow_redirects=True)
        html = respuesta.get_data(as_text=True)
        avisos = self.notificaciones(html)
        self.assertEqual(len(avisos), 1)
        self.assertTrue(avisos[0].startswith("Registro guardado:"))
        self.assertIn('aria-live="polite"', html)
        self.assertIn('aria-label="Cerrar aviso"', html)
        # Ya no sale como aviso dentro de la página
        self.assertNotIn("aviso-exito", html)
        self.assertIn("notificaciones.js", html)

    def test_corregido_borrado_y_restaurado_tambien_flotan(self):
        registro_id = self.insertar(HOY)
        pasos = [
            (f"/registro/{registro_id}/corregir", self.formulario(cantidad="48"),
             "Registro corregido:"),
            (f"/registro/{registro_id}/borrar", {}, "Registro enviado a la papelera:"),
            (f"/registro/{registro_id}/restaurar", {}, "Registro restaurado:"),
        ]
        for direccion, datos, inicio in pasos:
            with self.subTest(direccion=direccion):
                html = self.cliente.post(direccion, data=datos, follow_redirects=True
                                         ).get_data(as_text=True)
                avisos = self.notificaciones(html)
                self.assertEqual(len(avisos), 1)
                self.assertTrue(avisos[0].startswith(inicio))

    def test_errores_siguen_en_la_pagina(self):
        html = self.cliente.get("/historial/pdf?periodo=pasada", follow_redirects=True
                                ).get_data(as_text=True)
        self.assertIn('<p class="aviso aviso-error" role="status">No hay registros', html)
        self.assertEqual(self.notificaciones(html), [])
        # Y los errores de cada campo, debajo del campo
        html = self.cliente.post("/registrar", data=self.formulario(cantidad="0")
                                 ).get_data(as_text=True)
        self.assertIn('<p class="error-campo" id="error-cantidad">', html)
        self.assertEqual(self.notificaciones(html), [])

    def test_en_modo_prueba_van_debajo_de_la_franja(self):
        app = crear_app(self.ruta_db, modo_prueba=True)
        html = app.test_client().get("/registrar").get_data(as_text=True)
        self.assertIn('<div class="notificaciones bajo-franja"', html)
        self.assertIn('<div class="notificaciones"', self.html("/registrar"))


class AnimacionesTest(ConHistorial):
    def test_guardar_dice_guardando(self):
        self.assertIn('data-enviando="Guardando…">Guardar registro</button>',
                      self.html("/registrar"))
        registro_id = self.insertar(HOY)
        self.assertIn('data-enviando="Guardando…">Guardar cambios</button>',
                      self.html(f"/registro/{registro_id}/corregir"))
        script = Path("static/formulario.js").read_text(encoding="utf-8")
        self.assertIn("boton.disabled = true", script)
        self.assertIn("dataset.enviando", script)

    def test_respeta_reducir_movimiento(self):
        estilos = Path("static/estilos.css").read_text(encoding="utf-8")
        regla = estilos.split("@media (prefers-reduced-motion: reduce)", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("animation-duration: 0.01ms !important", regla)
        self.assertIn("transition-duration: 0.01ms !important", regla)

    def test_sin_transicion_entre_paginas(self):
        # Se probó y se quitó: el menú cambia directo
        estilos = Path("static/estilos.css").read_text(encoding="utf-8")
        self.assertNotIn("view-transition", estilos)
        self.assertNotIn("scale(", estilos)
        self.assertNotIn("resaltado-menu", self.html("/registrar"))

    def test_notificacion_dura_diez_segundos(self):
        script = Path("static/notificaciones.js").read_text(encoding="utf-8")
        self.assertIn("const DURACION = 10000;", script)
        self.assertIn('"mouseenter", pausar', script)


class PrecargaTest(ConHistorial):
    def reglas(self, html):
        texto = html.split('<script type="speculationrules">', 1)[1].split("</script>", 1)[0]
        return json.loads(texto)

    def test_solo_los_enlaces_del_menu_y_solo_traer_la_pagina(self):
        reglas = self.reglas(self.html("/historial"))
        # "prefetch" trae la página sin ejecutarla; nada de "prerender"
        self.assertEqual(list(reglas), ["prefetch"])
        self.assertEqual(reglas["prefetch"], [{
            "where": {"and": [
                {"selector_matches": "#menu a[href]"},
                {"not": {"selector_matches": "#menu a.activo"}},
            ]},
            "eagerness": "moderate",
        }])

    def test_el_menu_solo_tiene_enlaces_que_muestran(self):
        # Lo que se precarga: enlaces normales a páginas que solo muestran datos
        html = self.html("/registrar")
        menu = html.split('<nav id="menu"', 1)[1].split("</nav>", 1)[0]
        self.assertNotIn("<form", menu)
        self.assertNotIn("<button", menu)
        enlaces = re.findall(r'<a href="([^"]+)"', menu)
        self.assertEqual(enlaces, ["/registrar", "/historial", "/papelera", "/listas", "/respaldo"])
        for direccion in enlaces:
            with self.subTest(direccion=direccion):
                self.assertEqual(self.cliente.get(direccion).status_code, 200)


class SinParpadeoTest(ConHistorial):
    """Lo que se oculta llega ya oculto desde el servidor: el JavaScript solo
    actúa cuando se cambia algo, así nada aparece y desaparece al abrir la página."""

    def test_fechas_del_historial_ocultas_salvo_elegir_fechas(self):
        for periodo in ("esta", "pasada", "todo"):
            with self.subTest(periodo=periodo):
                html = self.html(f"/historial?periodo={periodo}")
                self.assertEqual(html.count('<div class="campo campo-rango" hidden>'), 2)
        html = self.html(f"/historial?periodo=rango&desde={LUNES_ANTEPASADO}")
        self.assertEqual(html.count('<div class="campo campo-rango" >'), 2)
        self.assertNotIn("campo-rango\" hidden", html)

    def test_lona_oculta_si_no_lleva(self):
        html = self.html("/registrar")
        self.assertIn('<fieldset id="seccion-lona" class="seccion-lona" hidden>', html)
        sin_lona = self.insertar(HOY, lona=None)
        html = self.html(f"/registro/{sin_lona}/corregir")
        self.assertIn('<fieldset id="seccion-lona" class="seccion-lona" hidden>', html)

    def test_lona_visible_y_obligatoria_si_lleva(self):
        con_lona = self.insertar(HOY)
        html = self.html(f"/registro/{con_lona}/corregir")
        self.assertIn('<fieldset id="seccion-lona" class="seccion-lona" >', html)
        seccion = html.split('id="seccion-lona"', 1)[1].split("</fieldset>", 1)[0]
        self.assertEqual(seccion.count("required"), 2)
        self.assertIn('value="250"', seccion)

    def test_error_sin_lona_no_devuelve_lona_escondida(self):
        # Sin lona marcada, lo escrito en lona no vuelve en campos ocultos
        respuesta = self.cliente.post("/registrar", data=self.formulario(
            lleva_lona="", lona_recibida_g="250", cantidad="0"))
        seccion = respuesta.get_data(as_text=True).split('id="seccion-lona"', 1)[1]
        seccion = seccion.split("</fieldset>", 1)[0]
        self.assertNotIn('value="250"', seccion)
        self.assertNotIn("required", seccion)

    def test_menu_del_celular_cerrado_antes_de_dibujar(self):
        html = self.html("/registrar")
        cabeza = html.split("</head>", 1)[0]
        self.assertIn('document.documentElement.classList.add("con-js")', cabeza)

    def test_los_scripts_no_ocultan_al_cargar(self):
        for archivo in ("historial.js", "formulario.js"):
            with self.subTest(archivo=archivo):
                script = Path("static", archivo).read_text(encoding="utf-8")
                self.assertNotIn("\n  actualizar();", script)
                self.assertIn('addEventListener("change", actualizar)', script)


class NombresEnNegritaTest(ConHistorial):
    """En los mensajes, los nombres van en negrita (sin comillas «»), siempre escapados."""

    def test_desactivar_y_reactivar(self):
        id_soporte = self.piezas["soporte"]
        html = self.cliente.post(f"/listas/piezas/{id_soporte}/desactivar",
                                 follow_redirects=True).get_data(as_text=True)
        self.assertIn("<strong>Soporte</strong> quedó inactiva: ya no aparece", html)
        html = self.cliente.post(f"/listas/piezas/{id_soporte}/reactivar",
                                 follow_redirects=True).get_data(as_text=True)
        self.assertIn("<strong>Soporte</strong> está activa otra vez", html)

    def test_un_nombre_con_html_se_muestra_como_texto(self):
        html = self.cliente.post("/listas/piezas/agregar", data={"nombre": "<b>Raro</b> & co"},
                                 follow_redirects=True).get_data(as_text=True)
        self.assertIn("<strong>&lt;b&gt;raro&lt;/b&gt; &amp; co</strong>", html)
        self.assertNotIn("<b>raro</b>", html)
        # El repetido, en el mensaje de error
        html = self.cliente.post("/listas/piezas/agregar", data={"nombre": "<B>RARO</B> & CO"}
                                 ).get_data(as_text=True)
        self.assertIn("Ya existe <strong>&lt;b&gt;raro&lt;/b&gt; &amp; co</strong>.", html)
        self.assertNotIn("<b>raro</b>", html)

    def test_fechas_al_reves_en_negrita(self):
        html = self.html(f"/historial?periodo=rango&desde={HOY}&hasta={LUNES_ANTEPASADO}")
        self.assertIn("La fecha <strong>Desde</strong> es posterior a <strong>Hasta</strong>",
                      html)

    def test_ninguna_pagina_usa_comillas(self):
        registro_id = self.insertar(HOY)
        for direccion in ("/registrar", "/historial", "/papelera", "/listas", "/respaldo",
                          f"/registro/{registro_id}/corregir",
                          f"/registro/{registro_id}/borrar",
                          f"/listas/piezas/{self.piezas['retén']}/nombre"):
            with self.subTest(direccion=direccion):
                html = self.html(direccion)
                self.assertNotIn("«", html)
                self.assertNotIn("»", html)


class BotonesDeListasTest(ConHistorial):
    def test_botones_pequenos_sin_subrayado(self):
        html = self.html("/listas")
        self.assertIn('class="boton-chico boton-chico-gris">', html)
        self.assertIn('class="boton-chico boton-chico-rojo">Desactivar', html)
        self.assertIn('class="boton-chico boton-chico-verde">Reactivar', html)  # pieza retirada
        self.assertNotIn('class="enlace', html)
        estilos = Path("static/estilos.css").read_text(encoding="utf-8")
        regla = estilos.split(".boton-chico {", 1)[1].split("}", 1)[0]
        self.assertIn("text-decoration: none;", regla)

    def test_el_nombre_para_lectores_va_sin_negrita_ni_comillas(self):
        html = " ".join(self.html("/listas").split())
        self.assertIn('Corregir nombre<span class="solo-lector"> de la pieza Retén</span>', html)
        self.assertIn('Desactivar<span class="solo-lector"> el material Nitrilo</span>', html)
        self.assertIn('Reactivar<span class="solo-lector"> la pieza Pieza retirada</span>', html)

    def test_corregir_nombre_lleva_el_lapiz(self):
        html = self.html("/listas")
        boton = html.split('class="boton-chico boton-chico-gris">', 1)[1].split("</a>", 1)[0]
        self.assertIn('<svg class="icono"', boton)


class PdfConNombresTest(ConHistorial):
    def test_titulo_y_tablas_con_mayuscula_y_nombre_de_archivo_igual(self):
        self.insertar(date(2026, 10, 5))
        respuesta = self.cliente.get(
            f"/historial/pdf?periodo=todo&pieza_id={self.piezas['retén']}"
            f"&material_id={self.materiales['silicona naranja']}"
        )
        # Sin pedidos de silicona naranja no hay PDF; con nitrilo sí
        self.assertEqual(respuesta.status_code, 302)
        respuesta = self.cliente.get(
            f"/historial/pdf?periodo=todo&pieza_id={self.piezas['retén']}"
            f"&material_id={self.materiales['nitrilo']}"
        )
        self.assertIn("_reten_nitrilo.pdf", respuesta.headers["Content-Disposition"])
        texto = texto_del_pdf(respuesta.data)
        self.assertIn("Pieza: Retén · Material: Nitrilo", texto)

    def test_resumenes_con_mayuscula(self):
        registros = [{
            "fecha": "2026-10-22", "pieza": "retén", "material": "jebe natural",
            "dureza_shore_a": None, "lleva_lona": 0,
            "cantidad": 50, "material_recibido_g": 3600.5, "material_sobrante_g": 400.0,
            "lona_recibida_g": None, "lona_sobrante_g": None, "observaciones": None,
        }]
        pdf = informe_pdf.generar_informe(
            registros, calculos.totales(registros),
            {"titulo": "T", "subtitulo": "S", "detalle": "D", "generado_en": "27/10/2026 18:40"},
        )
        texto = texto_del_pdf(pdf)
        self.assertIn("(Jebe natural)", texto)
        self.assertNotIn("(jebe natural)", texto)


if __name__ == "__main__":
    unittest.main()
