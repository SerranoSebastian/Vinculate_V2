"""Carga de datos con caché correcta (sin datos obsoletos ni mezcla entre usuarios).

* `st.cache_data` es GLOBAL entre sesiones. Por eso la llave incluye siempre el id
  del usuario y la HUELLA de la tabla (conteo|máx(actualizado_en)).
* La huella se consulta (barata) como máximo cada 4 s por sesión y se descarta
  explícitamente (`invalidar`) después de cualquier guardado propio.
* Si otra persona guarda, la huella cambia y la siguiente lectura recarga sola.
"""
from __future__ import annotations

import time

import pandas as pd
import streamlit as st

from ..auth.sesion import Sesion
from ..core import mapeo
from ..core.personas import limpiar_personas, obtener_personas_maestras, preparar_personas_dashboard
from ..core.vacantes import preparar_vacantes_dashboard
from ..core.vinculaciones import estado_por_persona, limpiar_vinculaciones
from ..repositories.tablas import RepoTabla

VIGENCIA_HUELLA_S = 4.0
TIPOS = ("personas", "vacantes", "vinculaciones")


def _huella(sesion: Sesion, tipo: str, forzar: bool = False) -> str:
    cache = st.session_state.setdefault("_cache_ver", {})
    ahora = time.monotonic()
    previo = cache.get(tipo)
    if previo and not forzar and ahora - previo[0] < VIGENCIA_HUELLA_S:
        return previo[1]
    ver = RepoTabla(sesion.cliente, tipo).version()
    cache[tipo] = (ahora, ver)
    return ver


def invalidar(*tipos: str) -> None:
    """Descarta la huella en esta sesión; la próxima lectura vuelve a consultar la base."""
    cache = st.session_state.setdefault("_cache_ver", {})
    for t in (tipos or TIPOS):
        cache.pop(t, None)


@st.cache_data(show_spinner=False, max_entries=24, ttl=3600)
def _filas(uid: str, tipo: str, huella: str, _cliente) -> pd.DataFrame:
    """Filas crudas (con nombres históricos). `uid`+`huella` son la llave; `_cliente` no se hashea."""
    return mapeo.a_dataframe(tipo, RepoTabla(_cliente, tipo).listar())


@st.cache_data(show_spinner=False, max_entries=24, ttl=3600)
def _derivado(uid: str, nombre: str, huellas: tuple, _crudos: tuple) -> pd.DataFrame:
    """Cálculos pesados (limpieza, maestras, estatus) memorizados por usuario + huellas."""
    if nombre == "personas":
        return limpiar_personas(_crudos[0])
    if nombre == "personas_dashboard":
        return preparar_personas_dashboard(_crudos[0])
    if nombre == "maestras":
        return obtener_personas_maestras(_crudos[0])
    if nombre == "vacantes":
        return preparar_vacantes_dashboard(_crudos[0])
    if nombre == "vinculaciones":
        return limpiar_vinculaciones(_crudos[0], _crudos[1])
    if nombre == "estado_personas":
        return estado_por_persona(_crudos[0], _crudos[1])
    raise KeyError(nombre)


def crudo(sesion: Sesion, tipo: str) -> pd.DataFrame:
    if not sesion.puede(tipo, "view"):
        return mapeo.a_dataframe(tipo, [])
    return _filas(sesion.user_id, tipo, _huella(sesion, tipo), sesion.cliente).copy()


def personas(sesion: Sesion) -> pd.DataFrame:
    """Personas limpias (una fila por vinculación histórica)."""
    h = _huella(sesion, "personas") if sesion.puede("personas", "view") else "-"
    return _derivado(sesion.user_id, "personas", (h,), (crudo(sesion, "personas"),)).copy()


def personas_dashboard(sesion: Sesion) -> pd.DataFrame:
    h = _huella(sesion, "personas") if sesion.puede("personas", "view") else "-"
    return _derivado(sesion.user_id, "personas_dashboard", (h,), (crudo(sesion, "personas"),)).copy()


def maestras(sesion: Sesion) -> pd.DataFrame:
    h = _huella(sesion, "personas") if sesion.puede("personas", "view") else "-"
    return _derivado(sesion.user_id, "maestras", (h,), (crudo(sesion, "personas"),)).copy()


def vacantes(sesion: Sesion) -> pd.DataFrame:
    h = _huella(sesion, "vacantes") if sesion.puede("vacantes", "view") else "-"
    return _derivado(sesion.user_id, "vacantes", (h,), (crudo(sesion, "vacantes"),)).copy()


def vinculaciones(sesion: Sesion) -> pd.DataFrame:
    hp = _huella(sesion, "personas") if sesion.puede("personas", "view") else "-"
    hv = _huella(sesion, "vinculaciones") if sesion.puede("vinculaciones", "view") else "-"
    return _derivado(sesion.user_id, "vinculaciones", (hp, hv),
                     (crudo(sesion, "vinculaciones"), crudo(sesion, "personas"))).copy()


def estado_personas(sesion: Sesion) -> pd.DataFrame:
    """Persona maestra + estatus general de seguimiento."""
    hp = _huella(sesion, "personas") if sesion.puede("personas", "view") else "-"
    hv = _huella(sesion, "vinculaciones") if sesion.puede("vinculaciones", "view") else "-"
    return _derivado(sesion.user_id, "estado_personas", (hp, hv),
                     (crudo(sesion, "personas"), crudo(sesion, "vinculaciones"))).copy()


def columnas_opcionales_presentes(df: pd.DataFrame, tipo: str) -> set[str]:
    """Columnas SQL opcionales (V005/V007…) que existen en la base (según lo leído)."""
    cfg = mapeo.TABLAS[tipo]
    return {remoto for local, remoto in cfg["opcionales"].items() if local in df.columns}
