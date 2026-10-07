"""Registro de páginas para navegar entre vistas (st.switch_page) sin acoplarlas entre sí."""
from __future__ import annotations

import streamlit as st

_PAGINAS = "_paginas"
_PARAMS = "_nav_params"


def registrar(paginas: dict) -> None:
    st.session_state[_PAGINAS] = paginas


def existe(clave: str) -> bool:
    return clave in st.session_state.get(_PAGINAS, {})


def ir_a(clave: str, **parametros) -> None:
    """Cambia de página dejando parámetros (p. ej. la persona elegida) para que la otra vista los lea."""
    paginas = st.session_state.get(_PAGINAS, {})
    if clave not in paginas:
        st.warning("Tu perfil no tiene acceso a esa sección.")
        return
    st.session_state[_PARAMS] = {"destino": clave, **parametros}
    st.switch_page(paginas[clave])


def tomar_parametros(clave: str) -> dict:
    """Parámetros pendientes para la página `clave` (se consumen una sola vez)."""
    p = st.session_state.get(_PARAMS)
    if p and p.get("destino") == clave:
        st.session_state.pop(_PARAMS, None)
        return {k: v for k, v in p.items() if k != "destino"}
    return {}
