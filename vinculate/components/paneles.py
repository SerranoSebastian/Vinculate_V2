"""Paneles de gráficas compartidos entre varias vistas."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ..config.theme import PALETA_SEDECO, tema_grafica
from ..core.constantes import IMPUTAR_DATOS_FALTANTES
from ..core.imputacion import resumen_imputacion
from ..core.normalizacion import agrupar_tipo_vinculacion
from ..core.personas import solo_vinculaciones
from . import charts


def tabla_anual(pf: pd.DataFrame) -> pd.DataFrame:
    """Por año: personas únicas, vinculaciones, promedio y personas recurrentes (solo registros con año)."""
    con = solo_vinculaciones(pf)
    con = con[con["año"].notna()]
    filas = []
    for anio, g in con.groupby("año"):
        por_persona = g.groupby("id_persona_maestro").size()
        filas.append({"Año": int(anio), "Personas únicas": int(g["id_persona_maestro"].nunique()),
                      "Vinculaciones": int(len(g)),
                      "Promedio por persona": round(len(g) / max(g["id_persona_maestro"].nunique(), 1), 2),
                      "Personas recurrentes": int((por_persona > 1).sum())})
    return pd.DataFrame(filas, columns=["Año", "Personas únicas", "Vinculaciones", "Promedio por persona", "Personas recurrentes"]).sort_values("Año")


def evolucion_anual(pf: pd.DataFrame, clave: str) -> bool:
    """Barras de vinculaciones por año + línea de personas únicas. False si no hay datos."""
    con = solo_vinculaciones(pf)  # solo cuentan las personas que ya tienen una vinculación
    con = con[con["año"].notna()]
    if con.empty:
        from . import ui
        ui.vacio("No hay registros con año para mostrar la evolución.")
        return False
    anual = con.groupby("año").agg(vinculaciones=("id_persona", "count"), personas=("id_persona_maestro", "nunique")).reset_index()
    anual["año"] = anual["año"].astype(int)
    fig = go.Figure()
    fig.add_bar(x=anual["año"], y=anual["vinculaciones"], name="Vinculaciones", marker_color=PALETA_SEDECO[0])
    fig.add_scatter(x=anual["año"], y=anual["personas"], name="Personas únicas", mode="lines+markers",
                    line={"color": PALETA_SEDECO[4], "width": 3})
    fig.update_layout(title="Evolución anual: vinculaciones y personas únicas", xaxis={"type": "category"},
                      legend={"orientation": "h", "y": -0.2})
    charts.mostrar(tema_grafica(fig, 380), clave)
    return True


def tipos_vinculacion(pf: pd.DataFrame, clave: str) -> None:
    d = charts.conteo(agrupar_tipo_vinculacion(solo_vinculaciones(pf)["vinculacion"]), "Tipo", "Vinculaciones")
    charts.mostrar(charts.dona(d, "Tipo", "Vinculaciones", "Vinculaciones por tipo", 380), clave)


def nota_imputacion(personas: pd.DataFrame | None) -> None:
    """Aviso plegable que explica cómo se completaron los datos faltantes y cuántos casos fueron (si los hubo)."""
    if not IMPUTAR_DATOS_FALTANTES or personas is None or personas.empty or "datos_imputados" not in personas.columns:
        return
    res = resumen_imputacion(personas)
    res = res[res["Completadas"] > 0]
    if res.empty:
        return
    from . import ui
    with st.expander("ℹ️ Datos faltantes completados (imputación proporcional)"):
        st.markdown(
            "Cuando a una persona le falta un dato (por ejemplo la carrera o la institución), en las estadísticas se completa repartiendo esos casos "
            "en la **misma proporción** que tienen las personas que sí lo tienen: *personas con ese valor ÷ personas con dato conocido*. "
            "Si una persona tiene el dato en otro de sus registros, se usa ese y no se imputa.  \n"
            "Sirve para totales y gráficas; el valor asignado a una persona en particular no es un dato capturado por ella. "
            "Se indica como «imputado» en su ficha, en el Explorador y en la columna «Datos completados», y **no se guarda en la base**.")
        ui.tabla(res, altura=min(60 + 36 * len(res), 320))
