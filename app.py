"""Página web para registrar la producción del taller Adipolyu.

Arranque:  .venv\\Scripts\\python app.py   (o doble clic en "Iniciar app.bat")
Luego abrir http://127.0.0.1:5000 en el navegador.
"""

import secrets
import socket
import sqlite3
import sys
import threading
import webbrowser
from datetime import date

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
from formato import resumen_registro
from validacion import validar_registro

# 127.0.0.1 = solo esta laptop; nadie más en la red puede abrir la app
HOST = "127.0.0.1"
PUERTO = 5000

rutas = Blueprint("produccion", __name__)


def crear_app(ruta_db=None):
    """Arma la app. Las pruebas le pasan la ruta de una base de prueba."""
    app = Flask(__name__)
    app.config["RUTA_DB"] = ruta_db or base_datos.ruta_base()
    # Firma los mensajes de "registro guardado"; se renueva en cada arranque
    app.secret_key = secrets.token_hex(16)

    base_datos.verificar_base(app.config["RUTA_DB"])

    app.register_blueprint(rutas)
    app.teardown_appcontext(_cerrar_conexion)
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

    flash(resumen_registro(base_datos.obtener_registro(_conexion(), registro_id)), "exito")
    # Redirigir evita que F5 vuelva a enviar el formulario y duplique el registro
    return redirect(url_for(".registrar", fecha=registro["fecha"]))


def _mostrar_formulario(valores, errores, piezas=None, materiales=None):
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
    )
    return pagina, 422 if errores else 200


def _es_fecha_permitida(texto):
    try:
        return date.fromisoformat(texto) <= date.today()
    except ValueError:
        return False


def _app_ya_abierta():
    try:
        with socket.create_connection((HOST, PUERTO), timeout=0.5):
            return True
    except OSError:
        return False


def main():
    abrir_navegador = "--abrir-navegador" in sys.argv
    direccion = f"http://{HOST}:{PUERTO}/registrar"

    if _app_ya_abierta():
        print("La app ya está abierta en otra ventana.")
        if abrir_navegador:
            webbrowser.open(direccion)
        return

    try:
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
    app.run(host=HOST, port=PUERTO)


if __name__ == "__main__":
    main()
