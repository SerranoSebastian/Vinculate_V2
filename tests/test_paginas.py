"""Humo de interfaz: cada página se ejecuta de verdad dentro del runtime de Streamlit (AppTest) con datos sintéticos."""
import pytest
from streamlit.testing.v1 import AppTest

from tests.demo import cliente_demo, sesion_demo
from vinculate.auth.sesion import CLAVE_SESION

pytestmark = pytest.mark.apptest
PAGINAS = ["inicio", "personas", "vacantes", "vinculaciones", "explorador", "ridet", "mapa", "busqueda", "administracion"]


def _app():
    import streamlit as st

    from vinculate.config.theme import aplicar_estilos
    from vinculate.vistas import administracion, busqueda, explorador, inicio, mapa, personas, ridet, vacantes, vinculaciones

    aplicar_estilos()
    pagina = st.session_state["_pagina_prueba"]
    {"inicio": inicio.render, "personas": personas.render, "vacantes": vacantes.render, "vinculaciones": vinculaciones.render,
     "explorador": explorador.render, "ridet": ridet.render, "mapa": mapa.render, "busqueda": busqueda.render,
     "administracion": administracion.render, "cuenta": administracion.render_cuenta}[pagina]()


def _correr(pagina, sesion):
    at = AppTest.from_function(_app, default_timeout=60)
    at.session_state[CLAVE_SESION] = sesion
    at.session_state["_pagina_prueba"] = pagina
    return at.run()


@pytest.mark.parametrize("pagina", PAGINAS + ["cuenta"])
def test_pagina_se_ejecuta_sin_excepciones(pagina):
    at = _correr(pagina, sesion_demo())
    assert not at.exception, [e.value for e in at.exception]
    assert not at.error, [e.value for e in at.error]


@pytest.mark.parametrize("pagina", ["inicio", "personas", "explorador", "ridet", "mapa", "administracion"])
def test_sin_permisos_no_filtra_datos(pagina):
    """Un colaborador sin ningún permiso ve mensajes claros, nunca datos ni errores."""
    at = _correr(pagina, sesion_demo(admin=False))
    assert not at.exception, [e.value for e in at.exception]
    texto = " ".join(m.value for m in at.markdown)
    assert "example.test" not in texto


def _combinaciones():
    from vinculate.vistas import administracion, personas, ridet, vacantes, vinculaciones
    c = []
    c += [("personas", "personas_apartado", v) for v in personas.SECCIONES.values()]
    c += [("vacantes", "vacantes_apartado", v) for v in vacantes.SECCIONES.values()]
    c += [("vinculaciones", "vinculaciones_apartado", v) for v in vinculaciones.SECCIONES.values()]
    c += [("ridet", "ridet_vista", v) for v in ridet.VISTAS.values()]
    c += [("administracion", "adm_apartado", v[0]) for v in administracion.APARTADOS.values()]
    c += [("mapa", "mapa_capa", k) for k in ("personas", "historicos", "vacantes", "empresas")]
    c += [("explorador", "explorador_base", k) for k in ("personas", "historicos", "vacantes", "vinculaciones")]
    return c


@pytest.mark.parametrize("pagina,clave,valor", _combinaciones())
def test_cada_apartado_se_ejecuta(pagina, clave, valor):
    at = AppTest.from_function(_app, default_timeout=60)
    at.session_state[CLAVE_SESION] = sesion_demo()
    at.session_state["_pagina_prueba"] = pagina
    at.session_state[clave] = valor
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert not at.error, [e.value for e in at.error]


# -------------------------------------------------- mapa con geometría (sintética) validada
@pytest.mark.parametrize("capa", ["personas", "historicos", "vacantes", "empresas"])
def test_mapa_dibuja_coropletico_cuando_hay_geometria_valida(tmp_path, monkeypatch, capa):
    """Con un GeoJSON de 60 cuadritos SINTÉTICOS (no son límites reales) el mapa se dibuja; sin él, no."""
    import json

    from tests.test_territorio import _geojson_sintetico
    from vinculate.vistas import mapa

    archivo = tmp_path / "tlaxcala_municipios.geojson"
    archivo.write_text(json.dumps(_geojson_sintetico()), encoding="utf-8")
    monkeypatch.setattr(mapa, "ARCHIVO_GEO", archivo)
    mapa._geo.clear()
    at = AppTest.from_function(_app, default_timeout=60)
    at.session_state[CLAVE_SESION] = sesion_demo()
    at.session_state["_pagina_prueba"] = "mapa"
    at.session_state["mapa_capa"] = capa
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert not at.error, [e.value for e in at.error]
    avisos = " ".join(w.value for w in at.warning)
    if capa in ("personas", "historicos"):
        assert len(at.get("plotly_chart")) == 1, "con geometría válida debe haber un mapa"
        assert "Cómo activar el mapa" not in " ".join(e.label for e in at.expander)
    else:
        # los datos de prueba no traen municipio de empresa: se dice, no se inventa ninguna ubicación
        assert "Todavía no hay municipio capturado" in avisos and not at.get("plotly_chart")


def test_mapa_sin_geometria_muestra_instrucciones_y_ranking(tmp_path, monkeypatch):
    from vinculate.vistas import mapa

    monkeypatch.setattr(mapa, "ARCHIVO_GEO", tmp_path / "no_existe.geojson")
    mapa._geo.clear()
    at = AppTest.from_function(_app, default_timeout=60)
    at.session_state[CLAVE_SESION] = sesion_demo()
    at.session_state["_pagina_prueba"] = "mapa"
    at.run()
    assert not at.exception and not at.error
    assert "preparar_geometria" in " ".join(m.value for m in at.markdown) + " ".join(i.value for i in at.info)
