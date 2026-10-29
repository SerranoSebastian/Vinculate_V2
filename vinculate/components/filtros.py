"""Filtros globales del Inicio ejecutivo (personas + vacantes) con estado en session_state."""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd
import streamlit as st

from ..core.constantes import ESTADOS_VACANTE, TIPOS_OPORTUNIDAD
from ..core.normalizacion import homologar_nulos
from ..core.ubicacion import OPCIONES_UBICACION_FILTRO

CLAVES = ("fi_anios", "fi_municipios", "fi_tipos", "fi_sexos", "fi_oportunidad", "fi_estados", "fi_solo_registrados")


@dataclass
class FiltrosInicio:
    anios: list[int] = field(default_factory=list)
    municipios: list[str] = field(default_factory=list)
    tipos: list[str] = field(default_factory=list)
    sexos: list[str] = field(default_factory=list)
    oportunidad: list[str] = field(default_factory=list)
    estados: list[str] = field(default_factory=list)

    def etiquetas(self) -> list[str]:
        out = []
        if self.anios:
            out.append("Año: " + ", ".join(map(str, self.anios)))
        if self.municipios:
            out.append("Municipio: " + ", ".join(self.municipios))
        if self.tipos:
            out.append("Vinculación: " + ", ".join(self.tipos))
        if self.sexos:
            out.append("Sexo: " + ", ".join(self.sexos))
        if self.oportunidad:
            out.append("Oportunidad: " + ", ".join(self.oportunidad))
        if self.estados:
            out.append("Estado de vacante: " + ", ".join(self.estados))
        return out


def _vals(serie: pd.Series) -> list[str]:
    return sorted(set(homologar_nulos(serie.fillna("").astype(str).str.strip())))


def _limpiar() -> None:
    for k in CLAVES:
        st.session_state.pop(k, None)


def barra(personas: pd.DataFrame | None, vacantes: pd.DataFrame | None) -> FiltrosInicio:
    """Dibuja los filtros y devuelve su estado. Cualquiera de los dos DataFrames puede ser None (sin permiso)."""
    anios: set[int] = set()
    if personas is not None and not personas.empty:
        anios |= set(personas["año"].dropna().astype(int))
    if vacantes is not None and not vacantes.empty:
        anios |= set(vacantes["Año"].dropna().astype(int))
    f = FiltrosInicio()
    with st.expander("🎛️ Filtros", expanded=False):
        c1, c2, c3 = st.columns(3)
        f.anios = c1.multiselect("Año", sorted(anios, reverse=True), key="fi_anios", placeholder="Todos los años")
        if personas is not None:
            presentes = [m for m in _vals(personas["municipio"]) if m not in OPCIONES_UBICACION_FILTRO]
            f.municipios = c2.multiselect("Municipio / estado", list(OPCIONES_UBICACION_FILTRO) + presentes,
                                          key="fi_municipios", placeholder="Todos")
            f.tipos = c3.multiselect("Tipo de vinculación", _vals(personas["vinculacion"]), key="fi_tipos", placeholder="Todos")
            c4, c5, c6 = st.columns(3)
            f.sexos = c4.multiselect("Sexo", _vals(personas["sexo"]), key="fi_sexos", placeholder="Todos")
        else:
            c4, c5, c6 = st.columns(3)
        if vacantes is not None:
            f.oportunidad = c5.multiselect("Tipo de oportunidad", TIPOS_OPORTUNIDAD, key="fi_oportunidad", placeholder="Todas")
            f.estados = c6.multiselect("Estado de la vacante", ESTADOS_VACANTE, key="fi_estados", placeholder="Todos")
        st.button("Limpiar filtros", on_click=_limpiar, key="fi_limpiar")
    if f.etiquetas():
        st.caption("Filtros activos → " + " · ".join(f.etiquetas()))
    return f


def aplicar_personas(df: pd.DataFrame, f: FiltrosInicio) -> pd.DataFrame:
    if df.empty:
        return df
    if f.anios:
        df = df[df["año"].isin(f.anios)]
    if f.municipios:
        df = df[homologar_nulos(df["municipio"]).isin(f.municipios)]
    if f.tipos:
        df = df[homologar_nulos(df["vinculacion"]).isin(f.tipos)]
    if f.sexos:
        df = df[homologar_nulos(df["sexo"]).isin(f.sexos)]
    return df


def aplicar_vacantes(df: pd.DataFrame, f: FiltrosInicio) -> pd.DataFrame:
    if df.empty:
        return df
    if f.anios:
        df = df[df["Año"].isin(f.anios)]
    if f.oportunidad:
        df = df[df["Tipo de Oportunidad"].isin(f.oportunidad)]
    if f.estados:
        df = df[df["Estado"].isin(f.estados)]
    return df
