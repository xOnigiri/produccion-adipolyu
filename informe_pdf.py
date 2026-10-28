"""Informe de producción en PDF (hoja A4 horizontal), hecho con ReportLab.

No sabe nada de la web ni de la base de datos: recibe los registros ya
filtrados y los totales de calculos.totales(), y devuelve el PDF en bytes.
Todos los números pasan por formato.py, con el mismo redondeo del historial.
"""

import io
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

import calculos
import formato

HOJA = landscape(A4)
MARGEN = 1.5 * cm
ANCHO_UTIL = HOJA[0] - 2 * MARGEN
ANCHO_LOGO = 6 * cm

# Los mismos colores de la app (los del logo). Las tablas siguen en blanco y gris
# claro para que se lean bien impresas en blanco y negro.
NARANJA = colors.HexColor("#c2470f")  # el naranja del logo, un poco más oscuro
NARANJA_LOGO = colors.HexColor("#dc5212")
VERDE = colors.HexColor("#0b8b48")
GRIS_TITULOS = colors.HexColor("#eef0f3")
CREMA_CALCULADO = colors.HexColor("#fff6ef")
GRIS_BORDE = colors.HexColor("#c4ccd6")
GRIS_TEXTO = colors.HexColor("#616e7c")
AMARILLO_PRUEBA = colors.HexColor("#fff3c4")
MARRON_PRUEBA = colors.HexColor("#7a4f01")

AVISO_PRUEBA = "MODO PRUEBA – DATOS DE EJEMPLO. NO ES UN INFORME REAL"

# (título de la columna, ancho, es número, es calculada)
COLUMNAS = [
    ("Fecha", 2.0, False, False),
    ("Pieza", 2.6, False, False),
    ("Material", 3.4, False, False),
    ("Dureza", 1.5, True, False),
    ("Lona", 1.3, False, False),
    ("Cant.", 1.3, True, False),
    ("Mat. recibido (g)", 2.1, True, False),
    ("Mat. sobrante (g)", 2.1, True, False),
    ("Mat. usado (kg)", 1.9, True, True),
    ("g por pieza", 1.7, True, True),
    ("Lona usada (kg)", 1.9, True, True),
    ("Observaciones", None, False, False),  # el ancho que sobre
]


def _estilo(nombre, **opciones):
    base = {"fontName": "Helvetica", "fontSize": 9, "leading": 11}
    return ParagraphStyle(nombre, **{**base, **opciones})


CELDA = _estilo("celda")
# Títulos de la tabla en blanco sobre naranja
CELDA_TITULO = _estilo("celda_titulo", fontName="Helvetica-Bold", textColor=colors.white)
CELDA_TITULO_NUMERO = _estilo("celda_titulo_numero", fontName="Helvetica-Bold",
                              textColor=colors.white, alignment=TA_RIGHT)
TITULO = _estilo("titulo", fontName="Helvetica-Bold", fontSize=20, leading=24,
                 textColor=NARANJA, alignment=TA_RIGHT)
SUBTITULO = _estilo("subtitulo", fontSize=11, leading=14, alignment=TA_RIGHT)
DETALLE = _estilo("detalle", textColor=GRIS_TEXTO, alignment=TA_RIGHT)
MARCA_SIN_LOGO = _estilo("marca", fontName="Helvetica-Bold", fontSize=24, leading=28,
                         textColor=NARANJA_LOGO)
CIFRA = _estilo("cifra", fontName="Helvetica-Bold", fontSize=22, leading=26,
                textColor=NARANJA, alignment=TA_CENTER)
CIFRA_NOMBRE = _estilo("cifra_nombre", fontSize=10, textColor=GRIS_TEXTO, alignment=TA_CENTER)
SECCION = _estilo("seccion", fontName="Helvetica-Bold", fontSize=11, leading=14,
                  spaceAfter=4)


def generar_informe(registros, totales, textos, modo_prueba=False, ruta_logo=None):
    """Devuelve el PDF en bytes.

    textos: diccionario con "titulo", "subtitulo", "detalle" (filtros y n.º de
    pedidos) y "generado_en" (fecha y hora para el pie de página).
    ruta_logo: si no existe, en su lugar se escribe "ADIPOLYU".
    """
    memoria = io.BytesIO()
    documento = SimpleDocTemplate(
        memoria,
        pagesize=HOJA,
        leftMargin=MARGEN,
        rightMargin=MARGEN,
        topMargin=MARGEN + (0.9 * cm if modo_prueba else 0),
        bottomMargin=MARGEN,
        title=f"{textos['titulo']} – {textos['subtitulo']}",
        author="Adipolyu",
    )

    def decorar_pagina(lienzo, _documento):
        if modo_prueba:
            _dibujar_franja_de_prueba(lienzo)

    contenido = [
        _encabezado(textos, ruta_logo),
        Spacer(1, 0.25 * cm),
        HRFlowable(width="100%", thickness=1.2, color=VERDE),
        Spacer(1, 0.35 * cm),
        _recuadro_resumen(totales),
        Spacer(1, 0.45 * cm),
        _tabla_pedidos(registros, totales),
        Spacer(1, 0.6 * cm),
        _resumenes(totales),
    ]
    pie = f"Producción Adipolyu · Generado el {textos['generado_en']}"
    if modo_prueba:
        pie += " · " + AVISO_PRUEBA
    documento.build(
        contenido,
        onFirstPage=decorar_pagina,
        onLaterPages=decorar_pagina,
        canvasmaker=_lienzo_con_pie(pie, marca_de_agua=modo_prueba),
    )
    return memoria.getvalue()


def _encabezado(textos, ruta_logo):
    """Logo a la izquierda; título, periodo y filtros a la derecha."""
    if ruta_logo and Path(ruta_logo).is_file():
        logo = Image(str(ruta_logo))
        # Mismo ancho siempre, alto proporcional (el logo es alargado)
        logo.drawHeight = ANCHO_LOGO * logo.imageHeight / logo.imageWidth
        logo.drawWidth = ANCHO_LOGO
    else:
        logo = Paragraph("ADIPOLYU", MARCA_SIN_LOGO)

    titulos = [
        Paragraph(escape(textos["titulo"]), TITULO),
        Paragraph(escape(textos["subtitulo"]), SUBTITULO),
        Paragraph(escape(textos["detalle"]), DETALLE),
    ]
    tabla = Table([[logo, titulos]], colWidths=[ANCHO_LOGO + 0.5 * cm, None])
    tabla.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    return tabla


def _recuadro_resumen(totales):
    """Las 3 cifras grandes: piezas, material usado y lona usada."""
    cifras = [
        (str(totales["piezas"]), "piezas producidas"),
        (formato.texto_kg(totales["material_usado_g"]), "de material usado"),
        (formato.texto_kg(totales["lona_usada_g"]), "de lona usada"),
    ]
    fila = [[Paragraph(cifra, CIFRA), Paragraph(nombre, CIFRA_NOMBRE)] for cifra, nombre in cifras]
    tabla = Table([fila], colWidths=[ANCHO_UTIL / 3] * 3)
    tabla.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 1, NARANJA),
        ("LINEBEFORE", (1, 0), (-1, -1), 0.5, GRIS_BORDE),
        ("BACKGROUND", (0, 0), (-1, -1), CREMA_CALCULADO),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return tabla


def filas_de_pedidos(registros, totales):
    """Las filas de la tabla como textos: una por pedido y la fila TOTAL al final."""
    filas = []
    for registro in registros:
        lona = calculos.lona_usada_g(registro)
        filas.append([
            formato.texto_fecha(registro["fecha"]),
            formato.nombre_visible(registro["pieza"]),
            formato.nombre_visible(registro["material"]),
            formato.texto_dureza(registro["dureza_shore_a"]),
            "Sí" if registro["lleva_lona"] else "No",
            str(registro["cantidad"]),
            formato.texto_gramos(registro["material_recibido_g"]),
            formato.texto_gramos(registro["material_sobrante_g"]),
            formato.numero_kg(calculos.material_usado_g(registro)),
            formato.numero_g_por_pieza(calculos.gramos_por_pieza(registro)),
            "—" if lona is None else formato.numero_kg(lona),
            registro["observaciones"] or "",
        ])
    filas.append([
        "TOTAL", "", "", "", "",
        str(totales["piezas"]),
        "", "",
        formato.numero_kg(totales["material_usado_g"]),
        "",
        formato.numero_kg(totales["lona_usada_g"]),
        "",
    ])
    return filas


def _tabla_pedidos(registros, totales):
    otras = sum(ancho for _, ancho, _, _ in COLUMNAS if ancho) * cm
    anchos = [ancho * cm if ancho else ANCHO_UTIL - otras for _, ancho, _, _ in COLUMNAS]

    titulos = [
        Paragraph(nombre, CELDA_TITULO_NUMERO if es_numero else CELDA_TITULO)
        for nombre, _, es_numero, _ in COLUMNAS
    ]
    filas = filas_de_pedidos(registros, totales)
    # Pieza, material y observaciones bajan de línea si son largas
    for fila in filas[:-1]:
        for indice in (1, 2, len(COLUMNAS) - 1):
            fila[indice] = Paragraph(escape(fila[indice]), CELDA)

    ultima = len(filas)  # la fila TOTAL (la 0 es la de títulos)
    estilo = [
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.4, GRIS_BORDE),
        ("BACKGROUND", (0, 0), (-1, 0), NARANJA),
        ("ROWBACKGROUNDS", (0, 1), (-1, ultima - 1), [colors.white, colors.HexColor("#f8f9fb")]),
        ("BACKGROUND", (0, ultima), (-1, ultima), GRIS_TITULOS),
        ("FONTNAME", (0, ultima), (-1, ultima), "Helvetica-Bold"),
        ("LINEABOVE", (0, ultima), (-1, ultima), 1, NARANJA),
    ]
    for columna, (_, _, es_numero, es_calculada) in enumerate(COLUMNAS):
        if es_numero:
            estilo.append(("ALIGN", (columna, 1), (columna, -1), "RIGHT"))
        if es_calculada:
            estilo.append(("BACKGROUND", (columna, 1), (columna, ultima - 1), CREMA_CALCULADO))

    # repeatRows=1: si la tabla pasa a otra hoja, los títulos se repiten
    tabla = Table([titulos, *filas], colWidths=anchos, repeatRows=1)
    tabla.setStyle(TableStyle(estilo))
    return tabla


def _resumenes(totales):
    """Por material (con la lona como una línea más) y por pieza, lado a lado."""
    por_material = [["Material", "Usado (kg)", "Sobrante (kg)"]]
    for fila in totales["por_material"]:
        por_material.append([
            formato.nombre_visible(fila["material"]), formato.numero_kg(fila["usado_g"]),
            formato.numero_kg(fila["sobrante_g"]),
        ])
    if totales["con_lona"]:
        por_material.append([
            "Lona", formato.numero_kg(totales["lona_usada_g"]),
            formato.numero_kg(totales["lona_sobrante_g"]),
        ])

    por_pieza = [["Pieza", "Unidades"]]
    por_pieza += [
        [formato.nombre_visible(fila["pieza"]), str(fila["cantidad"])]
        for fila in totales["por_pieza"]
    ]
    por_pieza.append(["Total", str(totales["piezas"])])

    ancho = ANCHO_UTIL / 2 - 0.5 * cm
    tabla_material = _tabla_resumen(por_material, [ancho * 0.5, ancho * 0.25, ancho * 0.25],
                                    lona_al_final=totales["con_lona"])
    tabla_pieza = _tabla_resumen(por_pieza, [ancho * 0.6, ancho * 0.4], total_al_final=True)

    lado_a_lado = Table(
        [[Paragraph("Por material", SECCION), Paragraph("Por pieza", SECCION)],
         [tabla_material, tabla_pieza]],
        colWidths=[ANCHO_UTIL / 2] * 2,
    )
    lado_a_lado.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
    ]))
    # Los resúmenes no se cortan entre dos hojas
    return KeepTogether([lado_a_lado])


def _tabla_resumen(filas, anchos, lona_al_final=False, total_al_final=False):
    tabla = Table(filas, colWidths=anchos)
    estilo = [
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.4, GRIS_BORDE),
        ("BACKGROUND", (0, 0), (-1, 0), NARANJA),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
    ]
    if lona_al_final:
        # La lona no es un material del pedido: se separa con una línea
        estilo += [("LINEABOVE", (0, -1), (-1, -1), 1, NARANJA),
                   ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Oblique")]
    if total_al_final:
        estilo += [("LINEABOVE", (0, -1), (-1, -1), 1, NARANJA),
                   ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                   ("BACKGROUND", (0, -1), (-1, -1), GRIS_TITULOS)]
    tabla.setStyle(TableStyle(estilo))
    return tabla


def _dibujar_franja_de_prueba(lienzo):
    """Franja amarilla arriba de cada hoja."""
    ancho, alto = HOJA
    lienzo.saveState()
    alto_franja = 0.9 * cm
    lienzo.setFillColor(AMARILLO_PRUEBA)
    lienzo.setStrokeColor(MARRON_PRUEBA)
    lienzo.rect(MARGEN, alto - MARGEN - alto_franja + 0.3 * cm, ANCHO_UTIL, alto_franja,
                fill=1, stroke=1)
    lienzo.setFillColor(MARRON_PRUEBA)
    lienzo.setFont("Helvetica-Bold", 12)
    lienzo.drawCentredString(ancho / 2, alto - MARGEN - alto_franja / 2 + 0.15 * cm, AVISO_PRUEBA)
    lienzo.restoreState()


def _dibujar_marca_de_agua(lienzo):
    """'DATOS DE EJEMPLO' en diagonal. Va encima de todo (si fuera debajo, el fondo
    de las tablas la taparía), en rojo semitransparente para no impedir leer."""
    ancho, alto = HOJA
    lienzo.saveState()
    lienzo.setFillColor(colors.HexColor("#c62828"), alpha=0.13)
    lienzo.setFont("Helvetica-Bold", 76)
    lienzo.translate(ancho / 2, alto / 2)
    lienzo.rotate(25)
    lienzo.drawCentredString(0, -27, "DATOS DE EJEMPLO")
    lienzo.restoreState()


def _lienzo_con_pie(texto_pie, marca_de_agua=False):
    """Lienzo que, al terminar, escribe en cada hoja el pie y 'Página X de Y'
    (y la marca de agua del MODO PRUEBA, si corresponde).

    El total de hojas solo se conoce al final, por eso las hojas se guardan
    y el pie se dibuja al cerrar el documento, encima del contenido.
    """

    # Pylint pide redefinir funciones de dibujo de ReportLab que aquí no se usan
    class LienzoConPie(canvas.Canvas):  # pylint: disable=abstract-method
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._hojas = []

        # El nombre lo pone ReportLab, no sigue el estilo de Python
        def showPage(self):  # pylint: disable=invalid-name
            self._hojas.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            total = len(self._hojas)
            for hoja in self._hojas:
                self.__dict__.update(hoja)
                if marca_de_agua:
                    _dibujar_marca_de_agua(self)
                self._dibujar_pie(total)
                super().showPage()
            super().save()

        def _dibujar_pie(self, total):
            ancho, _ = HOJA
            self.saveState()
            self.setFont("Helvetica", 8)
            self.setFillColor(GRIS_TEXTO)
            self.drawString(MARGEN, MARGEN - 0.7 * cm, texto_pie)
            self.drawRightString(ancho - MARGEN, MARGEN - 0.7 * cm,
                                 f"Página {self._pageNumber} de {total}")
            self.restoreState()

    return LienzoConPie
