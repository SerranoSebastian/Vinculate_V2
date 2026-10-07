"""Gráficas con el tema de SEDECO y selección (drill-down) para Streamlit."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from ..config.theme import ESCALA_SEDECO, PALETA_SEDECO, tema_grafica
from ..core.constantes import SIN_DATO

CONFIG = {"displayModeBar": False, "responsive": True}


def _conteo(serie: pd.Series, etiqueta: str, columna: str, top: int | None = None, vacio: str = SIN_DATO) -> pd.DataFrame:
    s = serie.fillna("").astype(str).str.strip()
    s = s.mask(s.str.lower().isin(["", "nan", "none", "nat"]), vacio)
    c = s.value_counts()
    if top:
        c = c.head(top)
    out = c.rename_axis(etiqueta).reset_index(name=columna)
    return out


def conteo(serie: pd.Series, etiqueta: str, columna: str, top: int | None = None) -> pd.DataFrame:
    """Frecuencias de una serie, con «Información no disponible» para vacíos (nunca NaN)."""
    return _conteo(serie, etiqueta, columna, top)


def barras_h(df: pd.DataFrame, etiqueta: str, valor: str, titulo: str, alto: int | None = None) -> go.Figure:
    fig = px.bar(df, x=valor, y=etiqueta, orientation="h", text=valor, title=titulo, color=valor,
                 color_continuous_scale=ESCALA_SEDECO)
    fig.update_layout(yaxis={"categoryorder": "total ascending"}, coloraxis_showscale=False)
    fig.update_traces(textposition="outside", cliponaxis=False,
                      hovertemplate="<b>%{y}</b><br>%{x}<extra></extra>")
    return tema_grafica(fig, alto or max(280, 28 * len(df) + 110))


def barras_v(df: pd.DataFrame, x: str, y: str, titulo: str, alto: int = 340, color: str | None = None,
             apiladas: bool = False) -> go.Figure:
    if color:
        fig = px.bar(df, x=x, y=y, color=color, barmode="stack" if apiladas else "group", title=titulo,
                     color_discrete_sequence=PALETA_SEDECO, text=y)
    else:
        fig = px.bar(df, x=x, y=y, text=y, title=titulo, color_discrete_sequence=[PALETA_SEDECO[0]])
    fig.update_traces(textposition="auto")
    return tema_grafica(fig, alto)


def lineas(df: pd.DataFrame, x: str, ys: list[str], titulo: str, alto: int = 340) -> go.Figure:
    fig = px.line(df, x=x, y=ys, markers=True, title=titulo, color_discrete_sequence=PALETA_SEDECO)
    fig.update_layout(legend_title_text="")
    return tema_grafica(fig, alto)


def area(df: pd.DataFrame, x: str, y: str, titulo: str, alto: int = 340) -> go.Figure:
    fig = px.area(df, x=x, y=y, markers=True, title=titulo, color_discrete_sequence=[PALETA_SEDECO[2]])
    return tema_grafica(fig, alto)


def dona(df: pd.DataFrame, etiqueta: str, valor: str, titulo: str, alto: int = 340) -> go.Figure:
    fig = px.pie(df, names=etiqueta, values=valor, hole=0.52, title=titulo, color_discrete_sequence=PALETA_SEDECO)
    fig.update_traces(textinfo="percent+label", hovertemplate="<b>%{label}</b><br>%{value} (%{percent})<extra></extra>")
    return tema_grafica(fig, alto)


def calor(tabla: pd.DataFrame, titulo: str, alto: int = 460) -> go.Figure:
    fig = px.imshow(tabla, text_auto=True, aspect="auto", title=titulo, color_continuous_scale=ESCALA_SEDECO)
    return tema_grafica(fig, alto)


def mostrar(fig: go.Figure, clave: str) -> None:
    st.plotly_chart(fig, key=clave, width="stretch", config=CONFIG)


def mostrar_seleccionable(fig: go.Figure, clave: str, eje: str = "y"):
    """Gráfica de barras con clic: devuelve la etiqueta de la barra elegida (o None) para el drill-down."""
    ev = st.plotly_chart(fig, key=clave, width="stretch", config=CONFIG, on_select="rerun", selection_mode="points")
    try:
        puntos = ev.selection.points if ev and ev.selection else []
    except Exception:  # noqa: BLE001
        puntos = []
    if not puntos:
        return None
    valor = puntos[0].get(eje)
    return None if valor is None else str(valor)
