"""Paneles de gráficas compartidos entre varias vistas."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from ..config.theme import PALETA_SEDECO, tema_grafica
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
