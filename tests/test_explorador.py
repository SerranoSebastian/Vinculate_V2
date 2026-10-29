"""Explorador: filtros por columna (no mezclan coincidencias de otras columnas) y búsqueda solo por nombre/ID."""
import pandas as pd
import pytest

from vinculate.core import explorador as ex


@pytest.fixture
def personas():
    return pd.DataFrame({
        "id_persona_maestro": ["PER-1", "PER-2", "PER-3", "PER-4"],
        "nombre": ["Ana Huamantla Pérez", "Luis Gómez", "Rosa Díaz", "Eva Ruiz"],
        "municipio": ["HUAMANTLA", "Apizaco", "HUAMANTLA", None],
        "sexo": ["Femenino", "Masculino", "Femenino", "Femenino"],
        "carrera": ["Derecho", "Huamantla Tec", "Enfermería", "Derecho"],
        "tipos_vinculacion": ["Empleo", "Empleo, Capacitación", "Capacitación", "Empleo"],
        "años_con_registro": ["2023", "2023, 2024", "2024", ""],
        "telefono": [None, "246", None, None], "correo": [None, None, None, None],
    })


def test_filtro_de_municipio_no_mezcla_otras_columnas(personas):
    r = ex.aplicar(personas, "personas", {"municipio": ["HUAMANTLA"]})
    assert list(r["id_persona_maestro"]) == ["PER-1", "PER-3"]  # PER-2 solo dice Huamantla en la carrera


def test_busqueda_de_texto_solo_mira_nombre_e_id(personas):
    r = ex.aplicar(personas, "personas", {}, "huamantla")
    assert list(r["id_persona_maestro"]) == ["PER-1"]  # no entra por municipio ni por carrera
    assert list(ex.aplicar(personas, "personas", {}, "per-3")["id_persona_maestro"]) == ["PER-3"]
    assert ex.aplicar(personas, "personas", {}, "ruiz eva").shape[0] == 1  # todas las palabras, sin importar el orden


def test_varios_filtros_son_y_varias_opciones_son_o(personas):
    r = ex.aplicar(personas, "personas", {"municipio": ["HUAMANTLA", "Apizaco"], "sexo": ["Femenino"]})
    assert list(r["id_persona_maestro"]) == ["PER-1", "PER-3"]


def test_columnas_con_varios_valores(personas):
    assert list(ex.aplicar(personas, "personas", {"años_con_registro": ["2024"]})["id_persona_maestro"]) == ["PER-2", "PER-3"]
    assert list(ex.aplicar(personas, "personas", {"tipos_vinculacion": ["Capacitación"]})["id_persona_maestro"]) == ["PER-2", "PER-3"]
    assert ex.opciones(personas, "años_con_registro", True) == ["2024", "2023", "Indefinido"]


def test_vacios_se_filtran_como_indefinido(personas):
    assert list(ex.aplicar(personas, "personas", {"municipio": ["Indefinido"]})["id_persona_maestro"]) == ["PER-4"]
    assert ex.opciones(personas, "municipio")[-1] == "Indefinido"


def test_anios_numericos_sin_decimales():
    v = pd.DataFrame({"Año": [2023.0, 2024.0, None], "Empresa": ["A", "B", "C"]})
    assert ex.opciones(v, "Año") == ["2024", "2023", "Indefinido"]
    assert list(ex.aplicar(v, "vacantes", {"Año": ["2023"]})["Empresa"]) == ["A"]


def test_sin_filtros_devuelve_todo_y_df_vacio_no_falla(personas):
    assert len(ex.aplicar(personas, "personas", {"municipio": []}, "")) == 4
    assert ex.aplicar(personas.iloc[0:0], "personas", {"municipio": ["X"]}, "a").empty


def test_cada_base_tiene_texto_y_filtros_definidos():
    for k in ("personas", "historicos", "vacantes", "vinculaciones"):
        assert ex.FILTROS[k] and ex.COLUMNAS_TEXTO[k] and ex.AYUDA_TEXTO[k]


@pytest.mark.apptest
def test_pantalla_filtra_por_municipio():
    from streamlit.testing.v1 import AppTest

    from tests.demo import sesion_demo
    from tests.test_paginas import _app
    from vinculate.auth.sesion import CLAVE_SESION

    def correr(elegir=None):
        at = AppTest.from_function(_app, default_timeout=60)
        at.session_state[CLAVE_SESION] = sesion_demo()
        at.session_state["_pagina_prueba"] = "explorador"
        at.run()
        if elegir:
            caja = at.multiselect(key="exp_f_personas_municipio")
            caja.select(caja.options[0]).run()
        return at

    def coinciden(at):
        return " ".join(m.value for m in at.markdown)

    base = correr()
    assert not base.exception
    filtrado = correr(elegir=True)
    assert not filtrado.exception, [e.value for e in filtrado.exception]
    assert "Filtros activos" in " ".join(c.value for c in filtrado.caption)
