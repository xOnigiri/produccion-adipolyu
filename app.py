"""Página web para registrar la producción del taller Adipolyu.

Arranque:  .venv\\Scripts\\python app.py   (o doble clic en "Iniciar app.bat")
Luego abrir http://127.0.0.1:5000 en el navegador.

Modo prueba:  .venv\\Scripts\\python app.py --modo-prueba   (o "Iniciar modo prueba.bat")
Usa produccion_prueba.db con datos de ejemplo, en http://127.0.0.1:5001.
Nunca abre produccion.db.
"""

import secrets
import socket
import sqlite3
import sys
import threading
import webbrowser
from datetime import date, timedelta

from flask import (
    Blueprint,
    Flask,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    url_for,
)

import base_datos
import calculos
import datos_prueba
import formato
from validacion import validar_registro

# 127.0.0.1 = solo esta laptop; nadie más en la red puede abrir la app
HOST = "127.0.0.1"
PUERTO = 5000
# Otro puerto para el modo prueba: así nunca se confunde con la app real abierta
PUERTO_PRUEBA = 5001

PERIODOS = {
    "esta": "Esta semana",
    "pasada": "Semana pasada",
    "rango": "Elegir fechas",
    "todo": "Todo",
}

rutas = Blueprint("produccion", __name__)


def crear_app(ruta_db=None, modo_prueba=False):
    """Arma la app. Las pruebas le pasan la ruta de una base de prueba."""
    app = Flask(__name__)
    app.config["RUTA_DB"] = ruta_db or base_datos.ruta_base()
    app.config["MODO_PRUEBA"] = modo_prueba
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
        g_por_pieza=formato.texto_g_por_pieza,
        material_usado=calculos.material_usado_g,
        lona_usada=calculos.lona_usada_g,
        gramos_por_pieza=calculos.gramos_por_pieza,
    )
    app.context_processor(lambda: {"modo_prueba": app.config["MODO_PRUEBA"]})
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
    pagina = render_template(
        "registrar.html",
        piezas=piezas,
        materiales=materiales,
        valores=valores,
        errores=errores,
        hoy=date.today().isoformat(),
        corrigiendo=corrigiendo,
        volver=_destino_volver(),
    )
    return pagina, 422 if errores else 200


@rutas.get("/historial")
def historial():
    filtros = _leer_filtros(request.args, date.today())
    if filtros["error"]:
        registros = []
    else:
        registros = base_datos.listar_registros(
            _conexion(),
            desde=filtros["desde"],
            hasta=filtros["hasta"],
            pieza_id=filtros["pieza_id"],
            material_id=filtros["material_id"],
        )
    return render_template(
        "historial.html",
        registros=registros,
        totales=calculos.totales(registros),
        filtros=filtros,
        periodos=PERIODOS,
        piezas=base_datos.listar_todas_las_piezas(_conexion()),
        materiales=base_datos.listar_todos_los_materiales(_conexion()),
        hoy=date.today().isoformat(),
        # Corregir y borrar vuelven aquí, con los mismos filtros
        aqui=request.full_path,
    )


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
        # Tal como está guardado, sin redondear: 3600.5 -> '3600.5' y 400.0 -> '400'
        return "" if valor is None else str(valor).removesuffix(".0")

    return {
        "fecha": registro["fecha"],
        "pieza_id": str(registro["pieza_id"]),
        "material_id": str(registro["material_id"]),
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
                    "La fecha «desde» es posterior a «hasta». Cámbialas para ver los registros."
                )
        elif desde:
            filtros["descripcion"] = f"Desde el {formato.texto_fecha(desde)}"
        elif hasta:
            filtros["descripcion"] = f"Hasta el {formato.texto_fecha(hasta)}"
    return filtros


def _leer_id(texto):
    return int(texto) if texto and texto.isdigit() else None


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
