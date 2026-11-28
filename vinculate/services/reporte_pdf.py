"""Dibuja el Reporte: gráficas (matplotlib) y PDF (reportlab). Todo en memoria; no escribe archivos ni toca la base de datos.

Reglas de las gráficas: un solo eje, marcas delgadas, rejilla discreta, color por entidad en orden fijo
(guinda, azul, ocre; validados para daltonismo y contraste), etiquetas directas solo donde ayudan y leyenda cuando hay 2 series o más.
"""
from __future__ import annotations

import io
import os
from datetime import datetime
from xml.sax.saxutils import escape

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import MaxNLocator  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.enums import TA_LEFT  # noqa: E402
from reportlab.lib.pagesizes import letter  # noqa: E402
from reportlab.lib.styles import ParagraphStyle  # noqa: E402
from reportlab.lib.units import cm  # noqa: E402
from reportlab.lib.utils import ImageReader  # noqa: E402
from reportlab.pdfbase import pdfmetrics  # noqa: E402
from reportlab.pdfbase.ttfonts import TTFont  # noqa: E402
from reportlab.platypus import (BaseDocTemplate, CondPageBreak, Frame, Image, KeepTogether, PageTemplate,  # noqa: E402
                                Paragraph, Spacer, Table, TableStyle)

from ..config.settings import LOGO_HORIZONTAL
from ..core.constantes import SIN_DATO
from ..core.reportes import Reporte

GUINDA, AZUL, OCRE = "#AF2140", "#0072B2", "#A8761B"  # categóricas en orden fijo (validadas: daltonismo y contraste)
GUINDA_OSC, DORADO, BEIGE = "#62182F", "#D0B786", "#F2E6D3"
TINTA, TINTA_SUAVE, REJILLA = "#1A1A1A", "#5B5148", "#E4DCD0"
DPI = 200
_FUENTES = {"DejaVu": "DejaVuSans.ttf", "DejaVu-Bold": "DejaVuSans-Bold.ttf", "DejaVu-Oblique": "DejaVuSans-Oblique.ttf",
            "DejaVu-BoldOblique": "DejaVuSans-BoldOblique.ttf"}


def _registrar_fuentes() -> None:
    """DejaVu viene dentro de matplotlib: acentos, ñ y flechas se ven bien sin instalar nada."""
    base = os.path.join(matplotlib.get_data_path(), "fonts", "ttf")
    for nombre, archivo in _FUENTES.items():
        if nombre not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(nombre, os.path.join(base, archivo)))
    pdfmetrics.registerFontFamily("DejaVu", normal="DejaVu", bold="DejaVu-Bold", italic="DejaVu-Oblique", boldItalic="DejaVu-BoldOblique")


# ------------------------------------------------------------------ gráficas
def _estilo() -> None:
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8, "axes.edgecolor": REJILLA, "axes.labelcolor": TINTA_SUAVE,
                         "xtick.color": TINTA_SUAVE, "ytick.color": TINTA_SUAVE, "text.color": TINTA, "axes.spines.top": False,
                         "axes.spines.right": False, "axes.titlesize": 9.5, "axes.titleweight": "bold", "axes.titlelocation": "left",
                         "axes.titlecolor": GUINDA_OSC, "figure.facecolor": "white", "axes.facecolor": "white"})


def _png(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=DPI, bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    return buf.getvalue()


def _corto(texto, n: int = 34) -> str:
    t = str(texto)
    return t if len(t) <= n else t[: n - 1].rstrip() + "…"


def _miles(v) -> str:
    return f"{int(v):,}"


def _personas(n) -> str:
    return f"{_miles(n)} " + ("persona" if int(n) == 1 else "personas")


def grafica_embudo(r: Reporte, ancho: float, alto: float) -> bytes:
    _estilo()
    fig, ax = plt.subplots(figsize=(ancho, alto))
    e = r.embudo
    n = len(e)
    maximo = max(float(e["Personas"].max()), 1.0)
    ys = list(range(n))[::-1]
    for y, (_, f), alfa in zip(ys, e.iterrows(), (0.45, 0.72, 1.0)[:n] if n == 3 else (0.55, 1.0)):
        ax.barh(y, f["Personas"], height=0.55, color=GUINDA, alpha=alfa)
        pct = f["Porcentaje de las atendidas"]
        etiqueta = _personas(f["Personas"]) + (f"  ·  {pct}% de las atendidas" if pct is not None and y != ys[0] else "")
        ax.text(f["Personas"] + maximo * 0.015, y, etiqueta, va="center", fontsize=8.5, color=TINTA)
    ax.set_yticks(ys, [str(x) for x in e["Etapa"]])
    ax.set_xlim(0, maximo * 1.55)
    ax.xaxis.set_visible(False)
    ax.spines["bottom"].set_visible(False)
    ax.tick_params(axis="y", length=0, labelsize=9)
    ax.set_title("Del primer contacto a la colocación")
    return _png(fig)


def grafica_avance(r: Reporte, ancho: float, alto: float) -> bytes:
    _estilo()
    a = r.anual
    fig, ax = plt.subplots(figsize=(ancho, alto))
    series = [("Personas atendidas", GUINDA, "o"), ("Vinculaciones", AZUL, "s")]
    if r.colocaciones_disponibles:
        series.append(("Colocaciones", OCRE, "^"))
    x = list(range(len(a)))
    if len(a) == 1:  # con un solo año no hay línea: barras agrupadas
        w = 0.8 / len(series)
        for k, (col, color, _) in enumerate(series):
            ax.bar(k * w - 0.4 + w / 2, a[col].iloc[0], width=w * 0.9, color=color, label=col)
            ax.text(k * w - 0.4 + w / 2, a[col].iloc[0], _miles(a[col].iloc[0]), ha="center", va="bottom", fontsize=8)
        ax.set_xticks([0], [str(int(a["Año"].iloc[0]))])
        ax.set_xlim(-0.6, 0.6)
    else:
        for col, color, marca in series:
            ax.plot(x, a[col], color=color, marker=marca, markersize=5, linewidth=2, label=col)
            ax.annotate(_miles(a[col].iloc[-1]), (x[-1], a[col].iloc[-1]), textcoords="offset points", xytext=(6, 0),
                        va="center", fontsize=8, color=color, fontweight="bold")
        ax.set_xticks(x, [str(int(v)) for v in a["Año"]])
        ax.set_xlim(-0.2, len(a) - 1 + 0.45)
    ax.set_ylim(bottom=0)
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    ax.grid(axis="y", color=REJILLA, linewidth=0.7)
    ax.set_axisbelow(True)
    ax.tick_params(axis="both", length=0)
    ax.legend(frameon=False, loc="upper center", ncol=len(series), fontsize=8, bbox_to_anchor=(0.5, -0.1))
    ax.set_title("Avance por año")
    return _png(fig)


def grafica_acumulado(r: Reporte, ancho: float, alto: float) -> bytes:
    _estilo()
    a = r.anual
    fig, ax = plt.subplots(figsize=(ancho, alto))
    x = list(range(len(a)))
    ax.fill_between(x, a["Colocaciones acumuladas"], color=OCRE, alpha=0.18, linewidth=0)
    ax.plot(x, a["Colocaciones acumuladas"], color=OCRE, marker="^", markersize=5, linewidth=2)
    ax.annotate(_miles(a["Colocaciones acumuladas"].iloc[-1]), (x[-1], a["Colocaciones acumuladas"].iloc[-1]), textcoords="offset points",
                xytext=(0, 7), ha="center", fontsize=8.5, color=OCRE, fontweight="bold")
    ax.set_xticks(x, [str(int(v)) for v in a["Año"]])
    ax.set_ylim(0, max(float(a["Colocaciones acumuladas"].max()), 1) * 1.25)
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    ax.grid(axis="y", color=REJILLA, linewidth=0.7)
    ax.set_axisbelow(True)
    ax.tick_params(axis="both", length=0)
    ax.set_title("Colocaciones acumuladas")
    return _png(fig)


def grafica_barras(df: pd.DataFrame, etiqueta: str, valor: str, titulo: str, ancho: float, alto: float, color: str = GUINDA,
                   notas: pd.Series | None = None, max_etiqueta: int = 26) -> bytes:
    """Barras horizontales ordenadas; el valor va al final de cada barra (y una nota opcional, p. ej. «3 colocadas»).
    El tamaño de la figura es el de la página, para que la letra salga a su tamaño real."""
    _estilo()
    d = df.copy().reset_index(drop=True)
    n = len(d)
    hueco = max(n, 3)  # con pocas categorías las barras no se vuelven enormes
    fig, ax = plt.subplots(figsize=(ancho, alto))
    ys = [hueco - 1 - k for k in range(n)]
    maximo = max(float(d[valor].max()), 1.0)
    colores = [("#A59A8E" if str(v) == SIN_DATO else color) for v in d[etiqueta]]
    ax.barh(ys, d[valor], height=0.62, color=colores)
    for y, (i, f) in zip(ys, d.iterrows()):
        texto = _miles(f[valor]) + (f"  ·  {notas.iloc[i]}" if notas is not None and notas.iloc[i] else "")
        ax.text(f[valor] + maximo * 0.015, y, texto, va="center", fontsize=7.8)
    ax.set_yticks(ys, [_corto(v, max_etiqueta) for v in d[etiqueta]])
    ax.set_ylim(-0.6, hueco - 0.4)
    ax.set_xlim(0, maximo * (1.4 if notas is not None else 1.2))
    ax.xaxis.set_visible(False)
    ax.spines["bottom"].set_visible(False)
    ax.tick_params(axis="y", length=0, labelsize=7.8)
    ax.set_title(titulo)
    return _png(fig)


# ------------------------------------------------------------------ PDF
def _estilos() -> dict[str, ParagraphStyle]:
    base = dict(fontName="DejaVu", textColor=colors.HexColor(TINTA), leading=13, fontSize=9, alignment=TA_LEFT)
    return {
        "titulo": ParagraphStyle("titulo", **{**base, "fontName": "DejaVu-Bold", "fontSize": 26, "leading": 30, "textColor": colors.HexColor(GUINDA_OSC)}),
        "sub": ParagraphStyle("sub", **{**base, "fontSize": 12, "leading": 16, "textColor": colors.HexColor(TINTA_SUAVE)}),
        "h2": ParagraphStyle("h2", **{**base, "fontName": "DejaVu-Bold", "fontSize": 13, "leading": 17, "textColor": colors.HexColor(GUINDA_OSC), "spaceBefore": 6, "spaceAfter": 3}),
        "cuerpo": ParagraphStyle("cuerpo", **base),
        "punto": ParagraphStyle("punto", **{**base, "leftIndent": 12, "bulletIndent": 0, "spaceAfter": 3}),
        "nota": ParagraphStyle("nota", **{**base, "fontSize": 7.8, "leading": 10.5, "textColor": colors.HexColor(TINTA_SUAVE)}),
        "kpi_v": ParagraphStyle("kpi_v", **{**base, "fontName": "DejaVu-Bold", "fontSize": 19, "leading": 22, "textColor": colors.HexColor(GUINDA_OSC)}),
        "kpi_e": ParagraphStyle("kpi_e", **{**base, "fontSize": 7.6, "leading": 9.5, "textColor": colors.HexColor(TINTA_SUAVE)}),
    }


def _img(png: bytes, ancho_cm: float) -> Image:
    w, h = ImageReader(io.BytesIO(png)).getSize()
    return Image(io.BytesIO(png), width=ancho_cm * cm, height=ancho_cm * cm * h / w)


def _kpis(r: Reporte, st: dict) -> Table:
    i = r.indicadores
    pct = lambda v: "—" if v is None else f"{v}%"  # noqa: E731
    celdas = [("Personas atendidas", _miles(i["personas"])), ("Con al menos una vinculación", _miles(i["vinculadas"])),
              ("Vinculaciones", _miles(i["vinculaciones"])), ("Empresas con vinculación", _miles(i["empresas"]))]
    if r.colocaciones_disponibles:
        celdas += [("Personas colocadas", _miles(i["colocadas"])), ("Colocaciones", _miles(i["colocaciones"])),
                   ("Tasa de colocación", pct(i["tasa_colocacion"])), ("Personas recurrentes", _miles(i["recurrentes"]))]
    else:
        celdas += [("Personas recurrentes", _miles(i["recurrentes"]))]
    filas, fila = [], []
    for etiqueta, valor in celdas:
        fila.append([Paragraph(valor, st["kpi_v"]), Paragraph(etiqueta, st["kpi_e"])])
        if len(fila) == 4:
            filas.append(fila)
            fila = []
    if fila:
        filas.append(fila + [""] * (4 - len(fila)))
    t = Table(filas, colWidths=[4.55 * cm] * 4, rowHeights=[1.9 * cm] * len(filas))
    estilo = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 6),
              ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FBF7F1")),
              ("LINEABOVE", (0, 0), (-1, -1), 2.2, colors.HexColor(GUINDA)),
              ("LINEBEFORE", (1, 0), (-1, -1), 4, colors.white), ("LINEBELOW", (0, 0), (-1, -2), 4, colors.white)]
    for fi, f in enumerate(filas):
        for ci, c in enumerate(f):
            if c == "":
                estilo.append(("BACKGROUND", (ci, fi), (ci, fi), colors.white))
                estilo.append(("LINEABOVE", (ci, fi), (ci, fi), 0, colors.white))
    t.setStyle(TableStyle(estilo))
    return t


def _tabla_empresas(df: pd.DataFrame, colocaciones: bool, st: dict) -> Table:
    cab = ["Empresa", "Vinculaciones", "Personas"] + (["Colocaciones"] if colocaciones else [])
    filas = [cab] + [[_corto(f["Empresa"], 44), _miles(f["Vinculaciones"]), _miles(f["Personas"])] + ([_miles(f["Colocaciones"])] if colocaciones else [])
                     for _, f in df.iterrows()]
    t = Table(filas, colWidths=[8.2 * cm] + [3.1 * cm] * (len(cab) - 1), repeatRows=1)
    t.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, -1), "DejaVu"), ("FONTSIZE", (0, 0), (-1, -1), 8),
                           ("FONTNAME", (0, 0), (-1, 0), "DejaVu-Bold"), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                           ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(GUINDA_OSC)), ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                           ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FBF7F1")]),
                           ("LINEBELOW", (0, -1), (-1, -1), 0.6, colors.HexColor(DORADO)),
                           ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5)]))
    return t


def _lado_a_lado(izq: bytes, der: bytes, ancho_cm: float = 8.7) -> Table:
    t = Table([[_img(izq, ancho_cm), _img(der, ancho_cm)]], colWidths=[9.2 * cm, 9.2 * cm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    return t


def _alto_barras(n: int, minimo: float = 1.1) -> float:
    return max(minimo, 0.23 * max(n, 3) + 0.5)


def _notas_colocadas(df: pd.DataFrame, r: Reporte):
    return df["Colocadas"].map(lambda v: f"{_miles(v)} colocada(s)" if v else "") if r.colocaciones_disponibles else None


def graficas(r: Reporte) -> dict[str, bytes]:
    """Todas las gráficas del reporte (PNG). Las usan por igual la vista previa de la página y el PDF. Solo trae las que tienen datos."""
    g: dict[str, bytes] = {}
    if r.vacio:
        return g
    g["embudo"] = grafica_embudo(r, 7.24, 0.55 + 0.5 * len(r.embudo))
    if not r.anual.empty:
        g["avance"] = grafica_avance(r, 7.24, 2.9)
        if r.colocaciones_disponibles and r.anual["Colocaciones"].sum() > 0:
            g["acumulado"] = grafica_acumulado(r, 3.43, 2.2)
    if not r.tipos_vinculacion.empty:
        g["tipos"] = grafica_barras(r.tipos_vinculacion, "Tipo", "Vinculaciones", "Vinculaciones por tipo", 3.43, 2.2, max_etiqueta=24)
    if not r.municipios.empty:
        g["municipios"] = grafica_barras(r.municipios, "Municipio", "Personas", "Personas atendidas por municipio", 7.24,
                                         _alto_barras(len(r.municipios)), notas=_notas_colocadas(r.municipios, r), max_etiqueta=40)
    if not r.instituciones.empty:
        g["instituciones"] = grafica_barras(r.instituciones, "Institución", "Personas", "Instituciones de origen", 7.24,
                                            _alto_barras(len(r.instituciones)), notas=_notas_colocadas(r.instituciones, r), max_etiqueta=40)
    for clave, nombre in (("sexo", "Sexo"), ("escolaridad", "Escolaridad"), ("edad", "Edad"), ("prioritario", "Grupo prioritario")):
        t = r.perfil.get(nombre)
        if t is not None and not t.empty:
            g[clave] = grafica_barras(t, t.columns[0], "Personas", nombre, 3.43, _alto_barras(len(t), 1.3), color=AZUL)
    return g


def _contenido(r: Reporte, nota: str, st: dict) -> list:
    g = graficas(r)
    h = []
    ancho = 18.4
    # ---- Página 1: portada + cifras
    h += [Spacer(1, 0.2 * cm), Paragraph("Reporte", st["titulo"]), Paragraph(escape(r.subtitulo), st["sub"]),
          Paragraph(f"Periodo: {escape(r.periodo)}", st["sub"]), Spacer(1, 0.5 * cm)]
    if r.vacio:
        h += [Paragraph("No hay información para el periodo y la selección elegidos.", st["cuerpo"])]
        return h
    h += [_kpis(r, st), Spacer(1, 0.4 * cm), Paragraph("Lectura rápida", st["h2"])]
    h += [Paragraph(escape(t), st["punto"], bulletText="•") for t in r.lecturas]
    h += [Spacer(1, 0.3 * cm), _img(g["embudo"], ancho)]
    if r.colocaciones_disponibles and r.indicadores["colocadas"] == 0:
        h += [Paragraph("Aún no hay colocaciones registradas en este periodo; el último escalón del embudo aparecerá cuando se registren.", st["nota"])]

    # ---- Página 2: avance
    h += [CondPageBreak(9 * cm), Spacer(1, 0.4 * cm), Paragraph("Avance en el tiempo", st["h2"])]
    if "avance" not in g:
        h += [Paragraph("Los registros de este periodo no tienen año, por eso no se puede mostrar su evolución.", st["cuerpo"])]
    else:
        h += [_img(g["avance"], ancho), Spacer(1, 0.3 * cm)]
        if "acumulado" in g and "tipos" in g:
            h += [_lado_a_lado(g["acumulado"], g["tipos"])]
        elif "tipos" in g or "acumulado" in g:
            h += [_img(g.get("tipos") or g["acumulado"], 9.0)]
        h += [Spacer(1, 0.2 * cm), Paragraph("Cada línea cuenta sus propios registros: las personas atendidas se cuentan por su año de registro, "
                                             "las vinculaciones por su año y las colocaciones por la fecha en que ocurrieron.", st["nota"])]

    # ---- Página 3: dónde y a quién
    h += [CondPageBreak(8 * cm), Spacer(1, 0.4 * cm), Paragraph("Dónde está el impacto y a quién se atendió", st["h2"])]
    if "municipios" in g:
        h += [_img(g["municipios"], ancho)]
    perfil = [g[k] for k in ("sexo", "escolaridad", "edad", "prioritario") if k in g]
    for a in range(0, len(perfil), 2):
        h += [Spacer(1, 0.2 * cm), _lado_a_lado(perfil[a], perfil[a + 1]) if a + 1 < len(perfil) else _img(perfil[a], 9.0)]

    # ---- Página 4: de dónde vienen y a dónde van
    h += [CondPageBreak(8 * cm), Spacer(1, 0.4 * cm), Paragraph("De dónde vienen y a dónde van", st["h2"])]
    if "instituciones" in g:
        h += [_img(g["instituciones"], ancho)]
    elif r.tipo == "institucion":
        h += [Paragraph(f"Este reporte es de una sola institución: {escape(str(r.valor))}.", st["cuerpo"])]
    if not r.empresas.empty:
        h += [Spacer(1, 0.3 * cm), Paragraph("Empresas con más personas vinculadas y colocadas", st["h2"]),
              _tabla_empresas(r.empresas, r.colocaciones_disponibles, st)]
    else:
        h += [Spacer(1, 0.3 * cm), Paragraph("Todavía no hay seguimientos con empresa para este periodo.", st["cuerpo"])]

    if nota.strip():
        h += [Spacer(1, 0.4 * cm), KeepTogether([Paragraph("Nota", st["h2"]), Paragraph(escape(nota.strip()).replace("\n", "<br/>"), st["cuerpo"])])]
    h += [Spacer(1, 0.5 * cm), KeepTogether([Paragraph("Cómo leer este reporte", st["h2"]),
          Paragraph("Una persona se cuenta una sola vez, aunque tenga varias vinculaciones. «Vinculada» es la persona con al menos una vinculación. "
                    "«Colocada» es la persona que quedó contratada en una de las empresas con las que se le vinculó. "
                    "La tasa de colocación es el porcentaje de personas vinculadas que ya fueron colocadas. "
                    "Los registros históricos anteriores al control de colocaciones cuentan como vinculaciones; las colocaciones se contabilizan "
                    "desde que se empezaron a registrar en la plataforma. Todas las cifras son agregadas: el reporte no incluye nombres ni datos de contacto.", st["nota"])])]
    return h


def generar_pdf(r: Reporte, *, generado_por: str, ahora: datetime, nota: str = "") -> bytes:
    """PDF del reporte (tamaño carta) en memoria."""
    _registrar_fuentes()
    st = _estilos()
    buf = io.BytesIO()
    doc = BaseDocTemplate(buf, pagesize=letter, leftMargin=1.6 * cm, rightMargin=1.6 * cm, topMargin=2.5 * cm, bottomMargin=1.8 * cm,
                          title=f"Reporte - {r.subtitulo}", author="Vincúlate SEDECO", subject=f"Periodo: {r.periodo}")
    ancho_p, alto_p = letter

    def decorar(canvas, _doc):
        canvas.saveState()
        if LOGO_HORIZONTAL.exists():
            canvas.drawImage(str(LOGO_HORIZONTAL), 1.6 * cm, alto_p - 1.9 * cm, width=7.2 * cm, height=7.2 * cm * 184 / 1600, mask="auto")
        canvas.setFont("DejaVu", 7.5)
        canvas.setFillColor(colors.HexColor(TINTA_SUAVE))
        canvas.drawRightString(ancho_p - 1.6 * cm, alto_p - 1.5 * cm, "Vincúlate SEDECO · Reporte")
        canvas.setStrokeColor(colors.HexColor(DORADO))
        canvas.setLineWidth(0.8)
        canvas.line(1.6 * cm, alto_p - 2.1 * cm, ancho_p - 1.6 * cm, alto_p - 2.1 * cm)
        canvas.line(1.6 * cm, 1.4 * cm, ancho_p - 1.6 * cm, 1.4 * cm)
        canvas.drawString(1.6 * cm, 0.95 * cm, f"Generado el {ahora.strftime('%d/%m/%Y %H:%M')} por {generado_por}")
        canvas.drawRightString(ancho_p - 1.6 * cm, 0.95 * cm, f"Página {_doc.page}")
        canvas.restoreState()

    marco = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="m", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id="p", frames=[marco], onPage=decorar)])
    doc.build(_contenido(r, nota, st))
    return buf.getvalue()
