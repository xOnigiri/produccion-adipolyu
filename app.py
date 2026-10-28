"""Página web para registrar la producción del taller Adipolyu.

Arranque:  .venv\\Scripts\\python app.py   (o doble clic en "Iniciar app.bat")
Luego abrir http://127.0.0.1:5000 en el navegador.

Modo prueba:  .venv\\Scripts\\python app.py --modo-prueba   (o "Iniciar modo prueba.bat")
Usa produccion_prueba.db con datos de ejemplo, en http://127.0.0.1:5001.
Nunca abre produccion.db.
"""

import io
import re
import secrets
import socket
import sqlite3
import sys
import threading
import unicodedata
import webbrowser
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from flask import (
    Blueprint,
    Flask,
    abort,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from markupsafe import Markup

import base_datos
import calculos
import crear_base
import datos_prueba
import formato
import informe_pdf
import respaldo
from validacion import MAX_NOMBRE, validar_nombre, validar_registro

# 127.0.0.1 = solo esta laptop; nadie más en la red puede abrir la app
HOST = "127.0.0.1"
PUERTO = 5000
# Otro puerto para el modo prueba: así nunca se confunde con la app real abierta
PUERTO_PRUEBA = 5001

RUTA_LOGO = Path(__file__).parent / "logo-adipolyu.png"

PERIODOS = {
    "esta": "Esta semana",
    "pasada": "Semana pasada",
    "rango": "Elegir fechas",
    "todo": "Todo",
}

rutas = Blueprint("produccion", __name__)


@dataclass(frozen=True)
class Lista:
    """Una de las dos listas de la página "Listas" y cómo nombrarla en los mensajes."""

    tabla: str
    titulo: str
    singular: str
    femenino: bool
    ejemplo: str

    def genero(self, raiz):
        """'activ' -> 'activa' (pieza) o 'activo' (material)."""
        return raiz + ("a" if self.femenino else "o")

    @property
    def la(self):
        return "la" if self.femenino else "el"

    @property
    def una(self):
        return "una" if self.femenino else "un"

    @property
    def aviso_ultimo(self):
        """Por qué no se puede desactivar el último activo."""
        return (
            f"Debe quedar al menos {self.una} {self.singular} {self.genero('activ')}. "
            f"Agrega o reactiva {self.genero('otr')} primero."
        )


LISTAS = {
    "piezas": Lista("piezas", "Piezas", "pieza", True, "buje"),
    "materiales": Lista("materiales", "Materiales", "material", False, "jebe negro"),
}


def crear_app(ruta_db=None, modo_prueba=False, ruta_logo=RUTA_LOGO):
    """Arma la app. Las pruebas le pasan la ruta de una base de prueba."""
    app = Flask(__name__)
    app.config["RUTA_DB"] = ruta_db or base_datos.ruta_base()
    app.config["MODO_PRUEBA"] = modo_prueba
    app.config["RUTA_LOGO"] = ruta_logo
    # A dónde va el respaldo según la base: Drive (real), práctica (modo prueba) o ninguno
    (
        app.config["DESTINO_RESPALDO"],
        app.config["ESTADO_RESPALDO"],
        app.config["LISTA_EXTRA_RESPALDO"],
    ) = respaldo.configuracion(app.config["RUTA_DB"], modo_prueba)
    # Firma los mensajes de "registro guardado"; se renueva en cada arranque
    app.secret_key = secrets.token_hex(16)

    base_datos.verificar_base(app.config["RUTA_DB"])

    app.register_blueprint(rutas)
    app.teardown_appcontext(_cerrar_conexion)

    # Para usar en las páginas: {{ registro.fecha|fecha }}, {{ gramos|kg }}, etc.
    app.jinja_env.filters.update(
        fecha=formato.texto_fecha,
        fecha_hora=formato.texto_fecha_hora,
        gramos=lambda gramos: formato.texto_gramos(gramos) + " g",
        kg=formato.texto_kg,
        numero_kg=formato.numero_kg,
        nombre=formato.nombre_visible,
        g_por_pieza=formato.texto_g_por_pieza,
        material_usado=calculos.material_usado_g,
        lona_usada=calculos.lona_usada_g,
        gramos_por_pieza=calculos.gramos_por_pieza,
        dureza=formato.texto_dureza,
        uso=_texto_uso,
    )
    app.jinja_env.globals["max_nombre"] = MAX_NOMBRE
    app.jinja_env.globals["durezas"] = crear_base.DUREZAS_SHORE_A
    app.jinja_env.globals["sin_dureza"] = base_datos.SIN_DUREZA
    app.context_processor(lambda: {
        "modo_prueba": app.config["MODO_PRUEBA"],
        # Sin el archivo del logo, el menú muestra "ADIPOLYU" en texto
        "hay_logo": Path(app.config["RUTA_LOGO"]).is_file(),
    })
    app.context_processor(_aviso_respaldo)
    return app


def _conexion():
    """Una conexión a la base por cada visita a la página; se cierra al terminar."""
    if "conexion" not in g:
        g.conexion = base_datos.conectar(current_app.config["RUTA_DB"])
    return g.conexion


def _cerrar_conexion(_error):
    conexion = g.pop("conexion", None)
    if conexion is not None:
        conexion.close()


@rutas.get("/")
def inicio():
    return redirect(url_for(".registrar"))


@rutas.get("/logo.png")
def logo():
    """El mismo archivo que usa el PDF, para el menú (un solo logo en la carpeta)."""
    ruta = Path(current_app.config["RUTA_LOGO"])
    if not ruta.is_file():
        abort(404)
    return send_file(ruta, mimetype="image/png")


@rutas.get("/registrar")
def registrar():
    # Después de guardar se vuelve aquí con la misma fecha, para el siguiente pedido
    fecha = request.args.get("fecha", "")
    valores = {"fecha": fecha if _es_fecha_permitida(fecha) else date.today().isoformat()}
    return _mostrar_formulario(valores, errores={})


@rutas.post("/registrar")
def guardar():
    piezas = base_datos.listar_piezas_activas(_conexion())
    materiales = base_datos.listar_materiales_activos(_conexion())

    registro, errores = validar_registro(
        request.form,
        piezas_validas={pieza["id"] for pieza in piezas},
        materiales_validos={material["id"] for material in materiales},
    )
    if errores:
        return _mostrar_formulario(request.form, errores, piezas, materiales)

    try:
        registro_id = base_datos.guardar_registro(_conexion(), registro)
    except sqlite3.IntegrityError:
        # Tercera capa: la base rechazó algo que pasó la validación
        errores = {
            "general": "La base de datos rechazó el registro porque algún dato no cuadra. "
            "Revisa los valores e inténtalo de nuevo."
        }
        return _mostrar_formulario(request.form, errores, piezas, materiales)

    flash(formato.resumen_registro(base_datos.obtener_registro(_conexion(), registro_id)), "exito")
    # Redirigir evita que F5 vuelva a enviar el formulario y duplique el registro
    return redirect(url_for(".registrar", fecha=registro["fecha"]))


def _mostrar_formulario(valores, errores, piezas=None, materiales=None, corrigiendo=None):
    """corrigiendo: el registro que se está corrigiendo; None si es uno nuevo."""
    if piezas is None:
        piezas = base_datos.listar_piezas_activas(_conexion())
    if materiales is None:
        materiales = base_datos.listar_materiales_activos(_conexion())
    hoy = date.today()
    pagina = render_template(
        "registrar.html",
        piezas=piezas,
        materiales=materiales,
        valores=valores,
        errores=errores,
        hoy=hoy.isoformat(),
        corrigiendo=corrigiendo,
        volver=_destino_volver(),
        # Tarjetas de "Esta semana" (no se muestran al corregir)
        semana=None if corrigiendo else _totales_semana(hoy),
        comparacion=None if corrigiendo else _comparacion("Semana pasada", hoy - timedelta(days=7)),
    )
    return pagina, 422 if errores else 200


def _totales_semana(dia, **filtros):
    """Totales de la semana (lunes a domingo) que contiene ese día, sin la papelera."""
    lunes, domingo = calculos.semana_de(dia)
    registros = base_datos.listar_registros(
        _conexion(), desde=lunes.isoformat(), hasta=domingo.isoformat(), **filtros
    )
    return calculos.totales(registros)


def _comparacion(etiqueta, dia, **filtros):
    """Lo que va en la línea pequeña debajo de cada tarjeta: 'Semana pasada: 180'."""
    return {"etiqueta": etiqueta, "totales": _totales_semana(dia, **filtros)}


@rutas.get("/historial")
def historial():
    filtros, registros, totales = _consultar(request.args)
    return render_template(
        "historial.html",
        registros=registros,
        totales=totales,
        comparacion=_comparacion_historial(filtros),
        filtros=filtros,
        periodos=PERIODOS,
        piezas=base_datos.listar_todas_las_piezas(_conexion()),
        materiales=base_datos.listar_todos_los_materiales(_conexion()),
        hoy=date.today().isoformat(),
        # Corregir y borrar vuelven aquí, con los mismos filtros
        aqui=request.full_path,
        # El PDF sale de lo mismo que se está viendo
        url_pdf=url_for(".descargar_pdf", **request.args.to_dict()),
    )


@rutas.get("/historial/pdf")
def descargar_pdf():
    filtros, registros, totales = _consultar(request.args)
    if not registros:
        flash("No hay registros en este periodo, así que no se generó el informe.", "error")
        return redirect(url_for(".historial", **request.args.to_dict()))

    ruta_logo = current_app.config["RUTA_LOGO"]
    if not Path(ruta_logo).is_file():
        current_app.logger.warning(
            "No se encontró el logo en %s. El PDF lleva 'ADIPOLYU' en su lugar.", ruta_logo
        )

    pieza = _nombre_elegido(base_datos.listar_todas_las_piezas(_conexion()), filtros["pieza_id"])
    material = _nombre_elegido(
        base_datos.listar_todos_los_materiales(_conexion()), filtros["material_id"]
    )
    pdf = informe_pdf.generar_informe(
        registros,
        totales,
        _textos_informe(filtros, registros, totales, pieza, material),
        modo_prueba=current_app.config["MODO_PRUEBA"],
        ruta_logo=ruta_logo,
    )
    return send_file(
        io.BytesIO(pdf),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=_nombre_archivo_pdf(filtros, registros, pieza, material),
    )


def _comparacion_historial(filtros):
    """La semana anterior a la que se ve, con los mismos filtros de pieza, material
    y dureza. Solo tiene sentido si se está viendo una semana; con fechas libres
    o "Todo" no hay con qué comparar y las tarjetas van sin esa línea."""
    if filtros["error"] or filtros["periodo"] not in ("esta", "pasada"):
        return None
    etiqueta = "Semana pasada" if filtros["periodo"] == "esta" else "Semana anterior"
    return _comparacion(
        etiqueta,
        date.fromisoformat(filtros["desde"]) - timedelta(days=7),
        pieza_id=filtros["pieza_id"],
        material_id=filtros["material_id"],
        dureza=filtros["dureza"],
    )


def _texto_filtro_dureza(dureza):
    """'Dureza: 70', 'Dureza: sin dato' o None si se ven todas."""
    if dureza is None:
        return None
    if dureza == base_datos.SIN_DUREZA:
        return "Dureza: sin dato"
    return f"Dureza: {dureza}"


def _consultar(args):
    """Lo que comparten el historial y el PDF: filtros, registros vigentes
    (sin la papelera) y totales. Así los dos muestran siempre lo mismo."""
    filtros = _leer_filtros(args, date.today())
    if filtros["error"]:
        registros = []
    else:
        registros = base_datos.listar_registros(
            _conexion(),
            desde=filtros["desde"],
            hasta=filtros["hasta"],
            pieza_id=filtros["pieza_id"],
            material_id=filtros["material_id"],
            dureza=filtros["dureza"],
        )
    return filtros, registros, calculos.totales(registros)


def _nombre_elegido(opciones, elegido_id):
    """Nombre de la pieza o material del filtro; None si son todas."""
    return next((fila["nombre"] for fila in opciones if fila["id"] == elegido_id), None)


def _textos_informe(filtros, registros, totales, pieza, material):
    # Fechas reales del primer y último pedido, para periodos sin límite
    primera = formato.texto_fecha(registros[-1]["fecha"])
    ultima = formato.texto_fecha(registros[0]["fecha"])
    desde, hasta = filtros["desde"], filtros["hasta"]

    if filtros["periodo"] in ("esta", "pasada"):
        titulo = "Producción de la semana"
        subtitulo = (
            f"Lunes {formato.texto_fecha(desde)} al domingo {formato.texto_fecha(hasta)}"
        )
    elif desde and hasta:
        titulo = f"Producción del {formato.texto_fecha(desde)} al {formato.texto_fecha(hasta)}"
        subtitulo = f"Pedidos del {primera} al {ultima}"
    elif desde:
        titulo = f"Producción desde el {formato.texto_fecha(desde)}"
        subtitulo = f"Pedidos del {primera} al {ultima}"
    elif hasta:
        titulo = f"Producción hasta el {formato.texto_fecha(hasta)}"
        subtitulo = f"Pedidos del {primera} al {ultima}"
    else:
        titulo = "Producción: todos los registros"
        subtitulo = f"Pedidos del {primera} al {ultima}"

    elegidos = [
        texto
        for texto in (
            pieza and f"Pieza: {formato.nombre_visible(pieza)}",
            material and f"Material: {formato.nombre_visible(material)}",
            _texto_filtro_dureza(filtros["dureza"]),
        )
        if texto
    ]
    elegido = " · ".join(elegidos) if elegidos else "Todas las piezas y materiales"
    pedidos = totales["pedidos"]
    return {
        "titulo": titulo,
        "subtitulo": subtitulo,
        "detalle": f"{elegido} · {pedidos} {'pedido' if pedidos == 1 else 'pedidos'}",
        "generado_en": datetime.now().strftime("%d/%m/%Y %H:%M"),
    }


def _nombre_archivo_pdf(filtros, registros, pieza, material):
    """produccion_2026-10-19_al_2026-10-25.pdf (las fechas al revés se ordenan solas)."""
    desde = filtros["desde"] or registros[-1]["fecha"]
    hasta = filtros["hasta"] or registros[0]["fecha"]
    partes = ["produccion", desde, "al", hasta]
    partes += [_para_nombre_de_archivo(nombre) for nombre in (pieza, material) if nombre]
    if filtros["dureza"] == base_datos.SIN_DUREZA:
        partes.append("sin-dureza")
    elif filtros["dureza"] is not None:
        partes.append(f"dureza-{filtros['dureza']}")
    nombre = "_".join(partes) + ".pdf"
    return "PRUEBA_" + nombre if current_app.config["MODO_PRUEBA"] else nombre


def _para_nombre_de_archivo(texto):
    """'silicona naranja' -> 'silicona-naranja' y 'retén' -> 'reten'."""
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", sin_tildes.lower()).strip("-")


@rutas.route("/registro/<int:registro_id>/corregir", methods=["GET", "POST"])
def corregir(registro_id):
    actual = _registro_vigente(registro_id)
    if actual is None:
        return redirect(_destino_volver())

    # La pieza y el material del registro siguen en la lista aunque se hayan desactivado
    piezas = base_datos.listar_piezas_activas(_conexion(), incluir_id=actual["pieza_id"])
    materiales = base_datos.listar_materiales_activos(
        _conexion(), incluir_id=actual["material_id"]
    )

    if request.method == "GET":
        return _mostrar_formulario(_valores_de(actual), {}, piezas, materiales, actual)

    # Las mismas reglas que al registrar
    registro, errores = validar_registro(
        request.form,
        piezas_validas={pieza["id"] for pieza in piezas},
        materiales_validos={material["id"] for material in materiales},
    )
    if not errores:
        try:
            base_datos.actualizar_registro(_conexion(), registro_id, registro)
        except sqlite3.IntegrityError:
            errores = {
                "general": "La base de datos rechazó los cambios porque algún dato no cuadra. "
                "Revisa los valores e inténtalo de nuevo."
            }
    if errores:
        return _mostrar_formulario(request.form, errores, piezas, materiales, actual)

    corregido = base_datos.obtener_registro(_conexion(), registro_id)
    flash("Registro corregido: " + formato.describir_registro(corregido), "exito")
    return redirect(_destino_volver())


@rutas.get("/registro/<int:registro_id>/borrar")
def confirmar_borrado(registro_id):
    registro = _registro_vigente(registro_id)
    if registro is None:
        return redirect(_destino_volver())
    return render_template(
        "confirmar_borrado.html",
        registro=registro,
        descripcion=formato.describir_registro(registro),
        volver=_destino_volver(),
    )


@rutas.post("/registro/<int:registro_id>/borrar")
def borrar(registro_id):
    registro = base_datos.obtener_registro(_conexion(), registro_id)
    if registro is not None and base_datos.enviar_a_papelera(_conexion(), registro_id):
        flash(
            "Registro enviado a la papelera: " + formato.describir_registro(registro)
            + ". Si fue un error, puedes restaurarlo desde la Papelera.",
            "exito",
        )
    return redirect(_destino_volver())


@rutas.get("/papelera")
def papelera():
    return render_template("papelera.html", registros=base_datos.listar_papelera(_conexion()))


@rutas.post("/registro/<int:registro_id>/restaurar")
def restaurar(registro_id):
    if base_datos.restaurar_registro(_conexion(), registro_id):
        registro = base_datos.obtener_registro(_conexion(), registro_id)
        flash(
            "Registro restaurado: " + formato.describir_registro(registro)
            + ". Ya aparece otra vez en el historial.",
            "exito",
        )
    return redirect(url_for(".papelera"))


@rutas.get("/listas")
def listas():
    return _mostrar_listas()


def _mostrar_listas(errores=None, escritos=None):
    """errores / escritos: {tipo: ...} de la lista donde no se pudo agregar."""
    errores = errores or {}
    pagina = render_template(
        "listas.html",
        listas=[
            (tipo, lista, base_datos.listar_con_uso(_conexion(), lista.tabla))
            for tipo, lista in LISTAS.items()
        ],
        errores=errores,
        escritos=escritos or {},
    )
    return pagina, 422 if errores else 200


@rutas.post("/listas/<tipo>/agregar")
def agregar_a_lista(tipo):
    lista = _lista(tipo)
    escrito = request.form.get("nombre", "")
    filas = base_datos.listar_con_uso(_conexion(), lista.tabla)
    nombre, error, repetido = validar_nombre(escrito, filas)
    if error is None:
        try:
            base_datos.agregar_a_lista(_conexion(), lista.tabla, nombre)
        except sqlite3.IntegrityError:
            error = "La base de datos rechazó el nombre porque ya existe. Revisa la lista."
    if error:
        return _mostrar_listas({tipo: {"mensaje": error, "repetido": repetido}}, {tipo: escrito})

    flash(
        Markup("Se agregó {} {} {}. Ya aparece en el formulario de registro.").format(
            lista.la, lista.singular, formato.nombre_en_negrita(nombre)
        ),
        "exito",
    )
    return redirect(url_for(".listas"))


@rutas.route("/listas/<tipo>/<int:elemento_id>/nombre", methods=["GET", "POST"])
def corregir_nombre(tipo, elemento_id):
    """Dos pasos: primero se escribe y se revisa; luego se confirma viendo
    a cuántos registros afecta."""
    lista = _lista(tipo)
    filas, actual = _buscar(lista, elemento_id)
    if actual is None:
        return redirect(url_for(".listas"))

    # Al guardar vuelve a minúsculas (validacion.limpiar_nombre)
    escrito = request.form.get("nombre", formato.nombre_visible(actual["nombre"]))
    nombre = error = None
    if request.method == "POST":
        nombre, error, _ = validar_nombre(escrito, filas, propio=actual)
        if error is None and request.form.get("paso") == "confirmar":
            try:
                base_datos.renombrar(_conexion(), lista.tabla, elemento_id, nombre)
            except sqlite3.IntegrityError:
                error = "La base de datos rechazó el nombre porque ya existe. Revisa la lista."
            else:
                usado = actual["registros"] or actual["en_papelera"]
                flash(
                    Markup("Nombre corregido: {} → {}.{}").format(
                        formato.nombre_en_negrita(actual["nombre"]),
                        formato.nombre_en_negrita(nombre),
                        f" Ya se ve así en {_texto_uso(actual)}." if usado else "",
                    ),
                    "exito",
                )
                return redirect(url_for(".listas"))

    pagina = render_template(
        "corregir_nombre.html",
        tipo=tipo,
        lista=lista,
        actual=actual,
        escrito=escrito,
        error=error,
        # Si el nombre pasó la revisión, se muestra la confirmación
        nuevo=None if error else nombre,
    )
    return pagina, 422 if error else 200


@rutas.post("/listas/<tipo>/<int:elemento_id>/desactivar")
def desactivar(tipo, elemento_id):
    lista = _lista(tipo)
    _, fila = _buscar(lista, elemento_id)
    if fila is None:
        return redirect(url_for(".listas"))

    if base_datos.desactivar(_conexion(), lista.tabla, elemento_id):
        usado = fila["registros"] or fila["en_papelera"]
        flash(
            Markup("{} quedó {}: ya no aparece en el formulario de registro.{}").format(
                formato.nombre_en_negrita(fila["nombre"]),
                lista.genero("inactiv"),
                f" Sus registros ({_texto_uso(fila)}) siguen en el historial y en los "
                "informes." if usado else "",
            ),
            "exito",
        )
    elif fila["activo"]:
        flash(lista.aviso_ultimo, "error")
    return redirect(url_for(".listas"))


@rutas.post("/listas/<tipo>/<int:elemento_id>/reactivar")
def reactivar(tipo, elemento_id):
    lista = _lista(tipo)
    _, fila = _buscar(lista, elemento_id)
    if fila is not None and base_datos.reactivar(_conexion(), lista.tabla, elemento_id):
        flash(
            Markup("{} está {} otra vez: ya aparece en el formulario de registro.").format(
                formato.nombre_en_negrita(fila["nombre"]), lista.genero("activ")
            ),
            "exito",
        )
    return redirect(url_for(".listas"))


def _lista(tipo):
    if tipo not in LISTAS:
        abort(404)
    return LISTAS[tipo]


def _buscar(lista, elemento_id):
    """Toda la lista y la fila buscada, o None (con un aviso) si no existe."""
    filas = base_datos.listar_con_uso(_conexion(), lista.tabla)
    fila = next((fila for fila in filas if fila["id"] == elemento_id), None)
    if fila is None:
        flash(f"Ese nombre no está en la lista de {lista.titulo.lower()}.", "error")
    return filas, fila


def _texto_uso(fila):
    """'12 registros', '1 registro (y 1 en la papelera)' o 'ningún registro'."""
    vigentes, en_papelera = fila["registros"], fila["en_papelera"]
    if not vigentes and not en_papelera:
        return "ningún registro"
    texto = f"{vigentes} {'registro' if vigentes == 1 else 'registros'}"
    if en_papelera:
        texto += f" (y {en_papelera} en la papelera)"
    return texto


@rutas.get("/respaldo")
def pagina_respaldo():
    destino = current_app.config["DESTINO_RESPALDO"]
    estado = current_app.config["ESTADO_RESPALDO"]
    ultimo = respaldo.ultimo_respaldo(estado) if estado else None
    return render_template(
        "respaldo.html",
        destino=destino,
        # Solo se mira si la carpeta existe; abrir la página no escribe nada
        disponible=destino is not None and destino.unidad.is_dir(),
        ultimo=ultimo,
        dias=(date.today() - ultimo[0].date()).days if ultimo else None,
        dias_aviso=respaldo.DIAS_AVISO,
        extras=[ruta.name for ruta in respaldo.leer_extras(
            current_app.config["LISTA_EXTRA_RESPALDO"])],
        ruta_db=current_app.config["RUTA_DB"],
    )


@rutas.post("/respaldo")
def exportar_respaldo():
    destino = current_app.config["DESTINO_RESPALDO"]
    if destino is None:
        flash("El respaldo está desactivado porque la app está usando una copia de la base.",
              "error")
        return redirect(url_for(".pagina_respaldo"))

    try:
        resultado = respaldo.hacer_respaldo(
            current_app.config["RUTA_DB"],
            destino,
            respaldo.leer_extras(current_app.config["LISTA_EXTRA_RESPALDO"]),
        )
    except respaldo.RespaldoFallido as error:
        current_app.logger.warning("Respaldo no realizado: %s", error)
        flash(str(error), "error")
        return redirect(url_for(".pagina_respaldo"))

    conteo = resultado.conteo
    extras = f" · también: {', '.join(resultado.extras)}" if resultado.extras else ""
    flash(
        f"Respaldo verificado en {resultado.carpeta} · {conteo['registros']} "
        f"{'registro' if conteo['registros'] == 1 else 'registros'} "
        f"({conteo['en_papelera']} en la papelera) · lista de {conteo['piezas']} piezas "
        f"y {conteo['materiales']} materiales{extras}.",
        "exito",
    )
    if destino.en_drive:
        flash("Google Drive lo subirá a la nube en unos minutos: espera a que el icono de "
              "Drive termine antes de apagar la laptop.", "exito")
    else:
        flash("MODO PRUEBA: respaldo de práctica guardado en la laptop; "
              "no se envió a Google Drive.", "advertencia")
    if resultado.extras_faltantes:
        flash("No se encontraron estos archivos, así que no se respaldaron: "
              + ", ".join(resultado.extras_faltantes) + ". La base sí se respaldó.",
              "advertencia")

    try:
        respaldo.anotar_respaldo(current_app.config["ESTADO_RESPALDO"], resultado)
    except OSError as error:
        flash(f"El respaldo está bien, pero no se pudo anotar su fecha ({error}). "
              "El aviso de 7 días podría seguir apareciendo.", "advertencia")
    return redirect(url_for(".pagina_respaldo"))


def _aviso_respaldo():
    """Franja en todas las páginas si pasaron 7 días o más sin respaldo (o nunca hubo)."""
    estado = current_app.config["ESTADO_RESPALDO"]
    if estado is None or request.endpoint in ("produccion.pagina_respaldo",
                                              "produccion.exportar_respaldo"):
        return {"aviso_respaldo": None}
    ultimo = respaldo.ultimo_respaldo(estado)
    if ultimo is None:
        return {"aviso_respaldo": "Todavía no hay ningún respaldo."}
    dias = (date.today() - ultimo[0].date()).days
    if dias < respaldo.DIAS_AVISO:
        return {"aviso_respaldo": None}
    return {"aviso_respaldo": f"Último respaldo: hace {dias} días."}


def _registro_vigente(registro_id):
    """El registro, o None (con un aviso) si no existe o está en la papelera."""
    registro = base_datos.obtener_registro(_conexion(), registro_id)
    if registro is None:
        flash("Ese registro no existe.", "error")
        return None
    if registro["borrado_en"] is not None:
        flash(
            "Ese registro está en la papelera. Restáuralo desde la Papelera "
            "para verlo en el historial o corregirlo.",
            "error",
        )
        return None
    return registro


def _valores_de(registro):
    """Un registro guardado, convertido en lo que muestra el formulario."""

    def gramos(valor):
        # Tal como está guardado, sin redondear: 3600.5 -> '3600,5' y 400.0 -> '400'
        return "" if valor is None else str(valor).removesuffix(".0").replace(".", ",")

    return {
        "fecha": registro["fecha"],
        "pieza_id": str(registro["pieza_id"]),
        "material_id": str(registro["material_id"]),
        "dureza_shore_a": "" if registro["dureza_shore_a"] is None
        else str(registro["dureza_shore_a"]),
        "cantidad": str(registro["cantidad"]),
        "material_recibido_g": gramos(registro["material_recibido_g"]),
        "material_sobrante_g": gramos(registro["material_sobrante_g"]),
        "lleva_lona": "si" if registro["lleva_lona"] else "",
        "lona_recibida_g": gramos(registro["lona_recibida_g"]),
        "lona_sobrante_g": gramos(registro["lona_sobrante_g"]),
        "observaciones": registro["observaciones"] or "",
    }


def _destino_volver():
    """A dónde regresar después de corregir o borrar: el historial con los filtros
    que tenía. Solo se acepta una dirección del propio historial."""
    volver = request.values.get("volver", "")
    if volver.startswith("/historial"):
        return volver
    return url_for(".historial")


def _leer_filtros(args, hoy):
    """Convierte lo elegido en la barra de filtros en fechas e ids."""
    periodo = args.get("periodo", "esta")
    if periodo not in PERIODOS:
        periodo = "esta"

    filtros = {
        "periodo": periodo,
        "desde": None,
        "hasta": None,
        "pieza_id": _leer_id(args.get("pieza_id")),
        "material_id": _leer_id(args.get("material_id")),
        "dureza": _leer_dureza(args.get("dureza")),
        "descripcion": "Todas las fechas",
        "error": None,
    }

    if periodo in ("esta", "pasada"):
        dia = hoy if periodo == "esta" else hoy - timedelta(days=7)
        lunes, domingo = calculos.semana_de(dia)
        filtros["desde"], filtros["hasta"] = lunes.isoformat(), domingo.isoformat()
        filtros["descripcion"] = (
            f"Semana del lunes {formato.texto_fecha(filtros['desde'])} "
            f"al domingo {formato.texto_fecha(filtros['hasta'])}"
        )
    elif periodo == "rango":
        desde = filtros["desde"] = _leer_fecha(args.get("desde"))
        hasta = filtros["hasta"] = _leer_fecha(args.get("hasta"))
        if desde and hasta:
            filtros["descripcion"] = (
                f"Del {formato.texto_fecha(desde)} al {formato.texto_fecha(hasta)}"
            )
            if desde > hasta:
                filtros["error"] = (
                    Markup("La fecha <strong>Desde</strong> es posterior a "
                           "<strong>Hasta</strong>. Cámbialas para ver los registros.")
                )
        elif desde:
            filtros["descripcion"] = f"Desde el {formato.texto_fecha(desde)}"
        elif hasta:
            filtros["descripcion"] = f"Hasta el {formato.texto_fecha(hasta)}"
    return filtros


def _leer_id(texto):
    return int(texto) if texto and texto.isdigit() else None


def _leer_dureza(texto):
    """'70' -> 70; 'sin-dato' se deja igual; cualquier otra cosa = todas (None)."""
    if texto == base_datos.SIN_DUREZA:
        return texto
    dureza = _leer_id(texto)
    return dureza if dureza in crear_base.DUREZAS_SHORE_A else None


def _leer_fecha(texto):
    try:
        return date.fromisoformat(texto or "").isoformat()
    except ValueError:
        return None


def _es_fecha_permitida(texto):
    try:
        return date.fromisoformat(texto) <= date.today()
    except ValueError:
        return False


def _app_ya_abierta(puerto):
    try:
        with socket.create_connection((HOST, puerto), timeout=0.5):
            return True
    except OSError:
        return False


def main():
    abrir_navegador = "--abrir-navegador" in sys.argv
    modo_prueba = "--modo-prueba" in sys.argv
    puerto = PUERTO_PRUEBA if modo_prueba else PUERTO
    direccion = f"http://{HOST}:{puerto}/registrar"

    if _app_ya_abierta(puerto):
        print("La app ya está abierta en otra ventana.")
        if abrir_navegador:
            webbrowser.open(direccion)
        return

    try:
        if modo_prueba:
            ruta, recien_creada = datos_prueba.preparar_base_prueba()
            print("*** MODO PRUEBA: datos de ejemplo. Tus registros reales no se tocan. ***")
            if recien_creada:
                print("Se creó la base de prueba con datos de ejemplo.")
            app = crear_app(ruta, modo_prueba=True)
        else:
            app = crear_app()
    except base_datos.BaseNoDisponible as error:
        print(f"No se puede iniciar la app: {error}")
        sys.exit(1)

    print(f"Base de datos: {app.config['RUTA_DB']}")
    print(f"App abierta en {direccion}")
    print("Para cerrarla, cierra esta ventana (o presiona Ctrl + C).")

    if abrir_navegador:
        # Espera un segundo a que la app arranque antes de abrir la página
        threading.Timer(1.0, webbrowser.open, args=[direccion]).start()
    app.run(host=HOST, port=puerto)


if __name__ == "__main__":
    main()
