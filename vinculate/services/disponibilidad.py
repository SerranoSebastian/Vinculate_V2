"""Disponibilidad manual por persona (D3). Sin V008 la función queda oculta: no se inventa ninguna regla."""
from __future__ import annotations

import time

import pandas as pd
import streamlit as st

from ..auth import servicio as auth_servicio
from ..auth.sesion import Sesion
from ..repositories.disponibilidad import RepoDisponibilidad
from ..repositories.errores import SinPermiso

_CLAVE = "_disp_cache"
VIGENCIA_S = 20.0


def estado(sesion: Sesion) -> pd.DataFrame | None:
    """DataFrame (id_persona_maestro, disponible, nota, …) o None si la tabla no existe todavía."""
    if not sesion.puede("personas", "view"):
        return None
    previo = st.session_state.get(_CLAVE)
    if previo and time.monotonic() - previo[0] < VIGENCIA_S:
        return previo[1]
    filas = RepoDisponibilidad(sesion.cliente).listar()
    df = None if filas is None else pd.DataFrame(filas, columns=["id_persona_maestro", "disponible", "nota",
                                                                 "actualizado_por", "actualizado_en"])
    st.session_state[_CLAVE] = (time.monotonic(), df)
    return df


def disponibles(sesion: Sesion) -> int | None:
    """Personas marcadas manualmente como disponibles, o None si la función no está habilitada."""
    df = estado(sesion)
    return None if df is None else int(df["disponible"].fillna(False).astype(bool).sum())


def guardar(sesion: Sesion, id_maestro: str, disponible: bool, nota: str = "") -> None:
    if not sesion.puede("personas", "edit"):
        raise SinPermiso("Tu perfil no tiene permiso para editar personas.")
    RepoDisponibilidad(sesion.cliente).guardar(id_maestro, disponible, nota, sesion.email)
    st.session_state.pop(_CLAVE, None)
    auth_servicio.auditar("persona_disponibilidad", f"id={id_maestro}; disponible={bool(disponible)}")
