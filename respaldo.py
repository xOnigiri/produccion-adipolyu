"""Respaldo de la base de producción en una carpeta de Google Drive.

Cada respaldo es una carpeta nueva, con la fecha y la hora en el nombre:
    2026-10-27_18-40-05\\
        produccion_2026-10-27_18-40-05.db
        (los archivos listados en respaldo_extra.txt, si existe)
        resumen.txt

Pasos: foto de la base con la copia oficial de SQLite (sirve aunque la app
esté abierta), revisión de la foto, copia al destino y comparación de huellas
(SHA-256) leyendo de vuelta lo copiado. Nunca sobrescribe ni borra nada, y
solo escribe dentro de la carpeta de respaldos.

No sabe nada de la web: lo usa app.py.
"""

import hashlib
import os
import socket
import sqlite3
import tempfile
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import base_datos

CARPETA_PROYECTO = Path(__file__).parent
RUTA_REAL = base_datos.RUTA_POR_DEFECTO

UNIDAD_DRIVE = Path("G:/Mi unidad")
CARPETA_DRIVE = UNIDAD_DRIVE / "ADIPOLYU" / "respaldos-produccion"
CARPETA_PRUEBA = CARPETA_PROYECTO / "respaldos" / "prueba"

# Dónde se anota la fecha del último respaldo (archivos locales, fuera de Git)
ESTADO_REAL = CARPETA_PROYECTO / "respaldos" / "ultimo_respaldo.txt"
ESTADO_PRUEBA = CARPETA_PROYECTO / "respaldos" / "ultimo_respaldo_prueba.txt"

# Archivos adicionales a respaldar: uno por línea, relativos a la carpeta del proyecto
LISTA_EXTRA = CARPETA_PROYECTO / "respaldo_extra.txt"

DIAS_AVISO = 7


@dataclass(frozen=True)
class Destino:
    carpeta: Path  # donde se crean los respaldos; es lo único que se crea
    unidad: Path  # tiene que existir; nunca se crea (G:\Mi unidad)
    nombre: str  # para los mensajes
    en_drive: bool = True


DRIVE = Destino(CARPETA_DRIVE, UNIDAD_DRIVE, "Google Drive")
PRUEBA = Destino(CARPETA_PRUEBA, CARPETA_PROYECTO, "carpeta de práctica", en_drive=False)


@dataclass
class Resultado:
    carpeta: Path
    archivo_db: Path
    conteo: dict
    hecho_en: datetime
    extras: list = field(default_factory=list)  # nombres copiados
    extras_faltantes: list = field(default_factory=list)  # nombres que no se encontraron


class RespaldoFallido(Exception):
    """El respaldo no se hizo o no se pudo verificar. El mensaje dice por qué."""


class RespaldoNoPermitido(RespaldoFallido):
    """Se intentó respaldar en Drive algo que no es la base real, o escribir fuera
    de la carpeta de respaldos."""


# Un respaldo a la vez (por ejemplo, si se aprieta el botón dos veces)
_EN_CURSO = threading.Lock()


def configuracion(ruta_db, modo_prueba):
    """(destino, archivo de estado, lista de extras) según la base que usa la app.

    MODO PRUEBA: carpeta de práctica en la laptop, sin extras; nunca Drive.
    Base real: Google Drive, con los extras de respaldo_extra.txt.
    Otra base (una copia, las pruebas automáticas): respaldo desactivado.
    """
    if modo_prueba:
        return PRUEBA, ESTADO_PRUEBA, None
    if Path(ruta_db).resolve() == RUTA_REAL.resolve():
        return DRIVE, ESTADO_REAL, LISTA_EXTRA
    return None, None, None


def leer_extras(lista):
    """Rutas listadas en respaldo_extra.txt. Sin lista, no hay extras.
    Las líneas vacías y las que empiezan con # no cuentan."""
    if lista is None or not Path(lista).is_file():
        return []
    lineas = (linea.strip() for linea in Path(lista).read_text(encoding="utf-8").splitlines())
    return [Path(lista).parent / linea for linea in lineas if linea and not linea.startswith("#")]


def hacer_respaldo(ruta_db, destino, extras=(), ahora=None):
    """Hace un respaldo completo y verificado. Devuelve un Resultado o lanza
    RespaldoFallido con un mensaje para mostrar tal cual."""
    ruta_db = Path(ruta_db)
    if destino.en_drive and ruta_db.resolve() != RUTA_REAL.resolve():
        raise RespaldoNoPermitido(
            f"Solo {RUTA_REAL.name} se respalda en Google Drive; esta app usa {ruta_db}."
        )
    # Sin "with": si ya hay uno en curso, se avisa en vez de esperar
    if not _EN_CURSO.acquire(blocking=False):  # pylint: disable=consider-using-with
        raise RespaldoFallido("Ya se está haciendo un respaldo. Espera unos segundos.")
    try:
        return _respaldar(ruta_db, destino, list(extras), ahora or datetime.now())
    finally:
        _EN_CURSO.release()


def _respaldar(ruta_db, destino, extras, ahora):
    # La foto se toma y se revisa en la laptop: SQLite trabaja mal sobre la unidad de Drive
    with tempfile.TemporaryDirectory() as temporal:
        foto = Path(temporal) / "foto.db"
        conteo = _tomar_foto(ruta_db, foto)
        _revisar_foto(foto, conteo)

        # Desde aquí se escribe en el destino
        trabajo, nombre = _preparar_carpeta(destino, ahora)
        resultado = Resultado(trabajo, trabajo / f"produccion_{nombre}.db", conteo, ahora)
        try:
            huellas = {
                resultado.archivo_db.name: _copiar_verificando(foto, resultado.archivo_db, destino)
            }
            for extra in extras:
                if not extra.is_file():
                    resultado.extras_faltantes.append(extra.name)
                    continue
                huellas[extra.name] = _copiar_verificando(extra, trabajo / extra.name, destino)
                resultado.extras.append(extra.name)
            _escribir(trabajo / "resumen.txt", _texto_resumen(ruta_db, resultado, huellas), destino)
        except (OSError, RespaldoFallido) as error:
            _marcar_fallida(trabajo, nombre, destino)
            raise RespaldoFallido(
                f"El respaldo falló y no es válido: {error} "
                f"La carpeta quedó como {nombre}_FALLIDO en {destino.carpeta}."
            ) from error

    resultado.carpeta = _renombrar(trabajo, destino.carpeta / nombre, destino)
    resultado.archivo_db = resultado.carpeta / resultado.archivo_db.name
    return resultado


def _tomar_foto(ruta_db, foto):
    """Copia oficial de SQLite (backup). Se cuenta y se copia dentro de una misma
    lectura: mientras dura (un instante), nadie puede guardar a medias."""
    try:
        origen = sqlite3.connect(f"{ruta_db.resolve().as_uri()}?mode=ro", uri=True,
                                 isolation_level=None)
    except sqlite3.OperationalError as error:
        raise RespaldoFallido(f"No se pudo abrir la base {ruta_db}: {error}") from error
    try:
        origen.execute("BEGIN")
        conteo = _contar(origen)
        copia = sqlite3.connect(foto)
        try:
            origen.backup(copia)
        finally:
            copia.close()
        origen.execute("COMMIT")
        return conteo
    except sqlite3.Error as error:
        raise RespaldoFallido(f"No se pudo copiar la base: {error}") from error
    finally:
        origen.close()


def _contar(conexion):
    def filas(consulta):
        return conexion.execute(consulta).fetchone()[0]

    return {
        "piezas": filas("SELECT COUNT(*) FROM piezas"),
        "materiales": filas("SELECT COUNT(*) FROM materiales"),
        "registros": filas("SELECT COUNT(*) FROM produccion"),
        "en_papelera": filas("SELECT COUNT(*) FROM produccion WHERE borrado_en IS NOT NULL"),
    }


def _revisar_foto(foto, conteo):
    """Integridad de SQLite, estructura completa y la misma cantidad de filas."""
    try:
        base_datos.verificar_base(foto)
    except base_datos.BaseNoDisponible as error:
        raise RespaldoFallido(f"La copia no tiene la estructura esperada: {error}") from error
    conexion = sqlite3.connect(foto)
    try:
        revision = conexion.execute("PRAGMA integrity_check").fetchone()[0]
        if revision != "ok":
            raise RespaldoFallido(f"La copia no pasó la revisión de SQLite: {revision}")
        if _contar(conexion) != conteo:
            raise RespaldoFallido("La copia no tiene la misma cantidad de filas que la base.")
    finally:
        conexion.close()


def _preparar_carpeta(destino, ahora):
    """Crea la carpeta del respaldo con el nombre '..._EN-CURSO'. Devuelve
    (carpeta, nombre final). Nunca reutiliza una carpeta que ya existe."""
    if not destino.unidad.is_dir():
        ayuda = "Abre Google Drive para escritorio, inicia sesión y vuelve a intentarlo. " \
            if destino.en_drive else ""
        raise RespaldoFallido(
            f"{destino.nombre} no está disponible (no se encuentra {destino.unidad}). "
            f"{ayuda}No se hizo el respaldo."
        )
    try:
        # En Drive solo se crea la última carpeta (respaldos-produccion), nunca las de arriba
        destino.carpeta.mkdir(parents=not destino.en_drive, exist_ok=True)
    except FileNotFoundError as error:
        raise RespaldoFallido(
            f"No se encontró la carpeta {destino.carpeta.parent}. "
            "No se creó nada y no se hizo el respaldo."
        ) from error
    except OSError as error:
        raise RespaldoFallido(
            f"No se pudo crear la carpeta {destino.carpeta}: {error}. No se hizo el respaldo."
        ) from error

    base = ahora.strftime("%Y-%m-%d_%H-%M-%S")  # Windows no permite ":" en los nombres
    for numero in range(1, 100):
        nombre = base if numero == 1 else f"{base}_{numero}"
        if any((destino.carpeta / (nombre + fin)).exists() for fin in ("", "_FALLIDO")):
            continue
        trabajo = destino.carpeta / f"{nombre}_EN-CURSO"
        _comprobar_dentro(trabajo, destino)
        try:
            trabajo.mkdir()  # falla si ya existe
        except FileExistsError:
            continue
        except OSError as error:
            raise RespaldoFallido(
                f"No se pudo crear la carpeta del respaldo en {destino.carpeta}: {error}"
            ) from error
        return trabajo, nombre
    raise RespaldoFallido("Hay demasiados respaldos con la misma hora. Espera un momento.")


def _copiar_verificando(origen, copia, destino):
    """Copia sin sobrescribir y vuelve a leer lo copiado: la huella tiene que ser
    idéntica. Devuelve la huella."""
    datos = origen.read_bytes()
    huella = hashlib.sha256(datos).hexdigest()
    _escribir(copia, datos, destino)
    if hashlib.sha256(_leer_copia(copia)).hexdigest() != huella:
        raise RespaldoFallido(f"La copia de {origen.name} no es idéntica al original.")
    return huella


def _leer_copia(ruta):
    return ruta.read_bytes()


def _escribir(ruta, contenido, destino):
    _comprobar_dentro(ruta, destino)
    if isinstance(contenido, str):
        contenido = contenido.encode("utf-8")
    # "x": falla si el archivo ya existe, así nunca se sobrescribe nada
    with open(ruta, "xb") as archivo:
        archivo.write(contenido)
        archivo.flush()
        os.fsync(archivo.fileno())


def _renombrar(carpeta, nueva, destino):
    _comprobar_dentro(nueva, destino)
    if nueva.exists():
        raise RespaldoFallido(f"Ya existe {nueva}; no se sobrescribe.")
    try:
        return carpeta.rename(nueva)
    except OSError as error:
        raise RespaldoFallido(
            f"El respaldo se copió y verificó, pero no se pudo renombrar {carpeta.name}: {error}"
        ) from error


def _marcar_fallida(trabajo, nombre, destino):
    """Renombra la carpeta a '..._FALLIDO'. No borra nada. Si tampoco se puede
    (por ejemplo, Drive se cerró), queda como '..._EN-CURSO'."""
    try:
        _renombrar(trabajo, destino.carpeta / f"{nombre}_FALLIDO", destino)
    except RespaldoFallido:
        pass


def _comprobar_dentro(ruta, destino):
    """Barrera: nada se escribe fuera de la carpeta de respaldos."""
    carpeta = destino.carpeta.resolve()
    ruta = Path(ruta).resolve()
    if ruta == carpeta or not ruta.is_relative_to(carpeta):
        raise RespaldoNoPermitido(f"No se permite escribir en {ruta}.")


def _texto_resumen(ruta_db, resultado, huellas):
    conteo = resultado.conteo
    lineas = [
        "Respaldo de la base de producción Adipolyu",
        f"Hecho el: {resultado.hecho_en.strftime('%d/%m/%Y %H:%M:%S')}",
        f"Equipo: {socket.gethostname()}",
        f"Base original: {ruta_db.resolve()}",
        "",
        f"Registros de producción: {conteo['registros']} "
        f"({conteo['registros'] - conteo['en_papelera']} vigentes, "
        f"{conteo['en_papelera']} en la papelera)",
        f"Lista de piezas: {conteo['piezas']} · Lista de materiales: {conteo['materiales']}",
        "Revisión de SQLite (integrity_check): ok",
        "",
        "Huellas SHA-256 (comprobadas leyendo de vuelta cada copia):",
        *(f"  {nombre}  {huella}" for nombre, huella in huellas.items()),
    ]
    if resultado.extras_faltantes:
        lineas += ["", "No encontrados (no se respaldaron):",
                   *(f"  {nombre}" for nombre in resultado.extras_faltantes)]
    return "\n".join(lineas) + "\n"


def anotar_respaldo(ruta_estado, resultado):
    """Guarda la fecha del último respaldo verificado, para el aviso de 7 días."""
    ruta_estado = Path(ruta_estado)
    ruta_estado.parent.mkdir(parents=True, exist_ok=True)
    ruta_estado.write_text(
        f"{resultado.hecho_en.isoformat(timespec='seconds')}\n{resultado.carpeta}\n",
        encoding="utf-8",
    )


def ultimo_respaldo(ruta_estado):
    """(fecha y hora, carpeta) del último respaldo; None si no hay o no se entiende."""
    try:
        lineas = Path(ruta_estado).read_text(encoding="utf-8").splitlines()
        return datetime.fromisoformat(lineas[0]), (lineas[1] if len(lineas) > 1 else "")
    except (OSError, ValueError, IndexError):
        return None
