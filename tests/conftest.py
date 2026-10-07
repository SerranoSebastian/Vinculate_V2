import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))


class _Estado(dict):
    def __getattr__(self, k):
        try:
            return self[k]
        except KeyError as exc:
            raise AttributeError(k) from exc

    def __setattr__(self, k, v):
        self[k] = v


@pytest.fixture(autouse=True)
def estado_sesion(request, monkeypatch):
    """Sustituye st.session_state por un dict normal (las pruebas unitarias no corren dentro de Streamlit).

    Las pruebas marcadas `apptest` SÍ corren dentro del runtime real (streamlit.testing), así que no se tocan."""
    import streamlit as st

    if request.node.get_closest_marker("apptest"):
        yield None
        return
    monkeypatch.setattr(st, "session_state", _Estado())
    yield st.session_state


@pytest.fixture(autouse=True)
def limpiar_cache():
    import streamlit as st

    st.cache_data.clear()
    yield
