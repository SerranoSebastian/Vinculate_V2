"""Mapa único: casillas Personas / Empresas, puntos exactos por empresa, coordenadas y captura rápida."""
import json
from types import SimpleNamespace

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from tests.demo import cliente_demo, sesion_demo
from tests.test_paginas import CLAVE_SESION, _app
from tests.test_territorio import _geojson_sintetico
from vinculate.core import puntos
from vinculate.services import empresas

# Coordenadas sintéticas dentro de la caja de Tlaxcala (no son ubicaciones reales de las empresas).
CATALOGO = [
    {"nombre": "Greenbrier", "sector": "Manufactura", "activo": True, "municipio": "APIZACO", "latitud": 19.4100, "longitud": -98.1400},
    {"nombre": "SIMEC", "sector": "Manufactura", "activo": True, "municipio": "APIZACO", "latitud": 19.4100, "longitud": -98.1400},   # misma ubicación
    {"nombre": "La Luz", "sector": "Textil", "activo": True, "municipio": "TLAXCALA", "latitud": 19.3200, "longitud": -98.2300},
    {"nombre": "Lear Corporation", "sector": "Automotriz", "activo": True, "municipio": None, "latitud": None, "longitud": None, "ubicacion_fuente": None},                                                      # sin coordenadas
    {"nombre": "Providencia", "sector": "Textil", "activo": True, "municipio": "TLAXCALA", "latitud": -98.2, "longitud": 19.3},      # invertidas
]


# ----------------------------------------------------------------------------- núcleo
def test_parseo_y_validacion_de_coordenadas():
    assert puntos.parsear_coordenadas("19.31390, -98.24040") == (19.3139, -98.2404)
    assert puntos.parsear_coordenadas("19.3139 -98.2404") == (19.3139, -98.2404)
    assert puntos.parsear_coordenadas("hola") == (None, None)
    assert puntos.validar_coordenadas(19.3, -98.2) is None
    assert puntos.validar_coordenadas(None, None) is None                      # vacías = sin ubicación (válido)
    assert "juntas" in puntos.validar_coordenadas(19.3, None)
    assert "invertidas" in puntos.validar_coordenadas(-98.2, 19.3)
    assert "signo menos" in puntos.validar_coordenadas(19.3, 98.2)
    assert "fuera de México" in puntos.validar_coordenadas(60.0, 10.0)
    assert puntos.parsear_numero("19,3139") == 19.3139 and puntos.parsear_numero("") is None and puntos.parsear_numero(float("nan")) is None


def test_separacion_y_colores():
    df = pd.DataFrame({"Empresa": ["A", "B", "C"], "Latitud": [19.3, 19.3, 19.4], "Longitud": [-98.2, -98.2, -98.1]})
    s = puntos.separar_superpuestos(df)
    assert s.loc[2, "lat_mapa"] == 19.4 and s.loc[2, "lon_mapa"] == -98.1          # el que está solo no se mueve
    assert (s.loc[0, "lat_mapa"], s.loc[0, "lon_mapa"]) != (s.loc[1, "lat_mapa"], s.loc[1, "lon_mapa"])
    assert abs(s.loc[0, "lat_mapa"] - 19.3) < 0.001                                # solo unos metros
    assert s.loc[0, "Latitud"] == 19.3                                             # el dato real no cambia
    col = puntos.asignar_colores([f"E{i}" for i in range(24)])
    assert len(set(col.values())) == 24                                            # 24 empresas, 24 colores distintos
    assert puntos.color_de_empresa("Greenbrier") == puntos.color_de_empresa("GREENBRIER")
    assert puntos.tamano_marcador(0) < puntos.tamano_marcador(9) <= 22


def test_puntos_validos_separa_sin_coordenadas_e_invalidas():
    d = pd.DataFrame({"Empresa": list("ABCD"), "Latitud": [19.3, None, -98.2, 19.3], "Longitud": [-98.2, None, 19.3, None]})
    ok, sin, mal = puntos.puntos_validos(d)
    assert ok["Empresa"].tolist() == ["A"] and sin["Empresa"].tolist() == ["B"] and sorted(mal["Empresa"]) == ["C", "D"]
    assert mal.set_index("Empresa").loc["C", "Problema"].startswith("La latitud y la longitud parecen")
    assert bool(ok["En Tlaxcala"].iloc[0])


# ----------------------------------------------------------------------------- servicio
def _sesion(catalogo=None, **mods):
    return sesion_demo(cliente_demo(catalogo_empresas=catalogo if catalogo is not None else [dict(c) for c in CATALOGO]), **mods)


def test_directorio_une_catalogo_y_vacantes_sin_inventar():
    s = _sesion()
    from vinculate.services import datos
    d = empresas.directorio(datos.vacantes(s), empresas.catalogo(s))
    assert {"Empresa", "Latitud", "Longitud", "Vacantes", "Vigentes"} <= set(d.columns)
    assert set(CATALOGO_NOMBRES) <= set(d["Empresa"])
    lear = d[d["Empresa"] == "Lear Corporation"].iloc[0]
    assert pd.isna(lear["Latitud"]) and pd.isna(lear["Longitud"])                  # nada inventado


CATALOGO_NOMBRES = [c["nombre"] for c in CATALOGO]


def test_guardar_coordenadas_valida_y_audita():
    s = _sesion()
    empresas.guardar_coordenadas(s, "Lear Corporation", "19,3500", "-98,2000")
    fila = [c for c in s.cliente.tablas["catalogo_empresas"] if c["nombre"] == "Lear Corporation"][0]
    assert (fila["latitud"], fila["longitud"]) == (19.35, -98.2) and fila["ubicacion_fuente"] == "manual"
    for lat, lon in ((-98.2, 19.35), (19.3, None), (60, 10)):
        with pytest.raises(ValueError):
            empresas.guardar_coordenadas(s, "Lear Corporation", lat, lon)
    empresas.guardar_coordenadas(s, "Lear Corporation", None, None)               # borrar
    assert [c for c in s.cliente.tablas["catalogo_empresas"] if c["nombre"] == "Lear Corporation"][0]["latitud"] is None


def test_guardar_coordenadas_exige_permiso():
    from vinculate.repositories.errores import SinPermiso
    s = sesion_demo(cliente_demo(catalogo_empresas=[dict(c) for c in CATALOGO]), admin=False, vacantes=("view",))
    with pytest.raises(SinPermiso):
        empresas.guardar_coordenadas(s, "Lear Corporation", 19.3, -98.2)


def test_edicion_rapida_guarda_solo_lo_que_cambio_y_acepta_pegado_de_google_maps():
    s = _sesion()
    from vinculate.services import datos
    d = empresas.directorio(datos.vacantes(s), empresas.catalogo(s))
    base = d[["Empresa", "Sector", "Municipio", "Latitud", "Longitud"]].copy()
    ed = base.assign(**{"Pegar (lat, lon)": ""})
    ed.loc[ed["Empresa"] == "Lear Corporation", "Pegar (lat, lon)"] = "19.31390, -98.24040"      # copiado de Google Maps
    ed.loc[ed["Empresa"] == "La Luz", "Latitud"] = 60.0                                          # inválida
    ed.loc[ed["Empresa"] == "SIMEC", "Pegar (lat, lon)"] = "basura"
    guardadas, errores = empresas.guardar_coordenadas_lote(s, base, ed)
    assert guardadas == ["Lear Corporation"]
    assert len(errores) == 2 and any("La Luz" in e for e in errores) and any("SIMEC" in e and "19.31390" in e for e in errores)
    fila = [c for c in s.cliente.tablas["catalogo_empresas"] if c["nombre"] == "Lear Corporation"][0]
    assert (fila["latitud"], fila["longitud"]) == (19.3139, -98.2404)
    # sin cambios → no escribe nada
    assert empresas.guardar_coordenadas_lote(s, base, base.assign(**{"Pegar (lat, lon)": ""})) == ([], [])


# ----------------------------------------------------------------------------- figura y selección
def _pts():
    from vinculate.services import datos
    s = _sesion()
    d = empresas.directorio(datos.vacantes(s), empresas.catalogo(s))
    ok, _, _ = puntos.puntos_validos(d)
    return puntos.separar_superpuestos(ok), puntos.asignar_colores(ok["Empresa"].tolist())


def test_figura_un_punto_por_empresa_con_color_propio():
    from vinculate.vistas import mapa
    pts, colores = _pts()
    geo = mapa.nucleo.validar_geojson(_geojson_sintetico()).geojson
    fig = mapa._figura(None, geo, pts, colores, estilo="white-bg", enfoque=mapa.TODO_EL_ESTADO, titulo="t", mostrar_leyenda=True)
    tipos = [t.type for t in fig.data]
    assert tipos[0] == "choroplethmap" and tipos.count("scattermap") == 1 + len(pts)       # contorno + un trace por empresa
    nombres = [t.name for t in fig.data if t.type == "scattermap" and t.name]
    assert sorted(nombres) == sorted(pts["Empresa"])
    assert len({t.marker.color for t in fig.data if t.type == "scattermap" and t.name}) == len(pts)
    # hover con la coordenada REAL (no la separada visualmente)
    greenbrier = [t for t in fig.data if t.name == "Greenbrier"][0]
    assert greenbrier.customdata[0][-2:] == (19.41, -98.14) or list(greenbrier.customdata[0][-2:]) == [19.41, -98.14]


def test_figura_funciona_sin_geometria_y_con_acercar_a_empresa():
    from vinculate.vistas import mapa
    pts, colores = _pts()
    fig = mapa._figura(None, None, pts, colores, estilo="carto-positron", enfoque="Empresa: La Luz", titulo="t", mostrar_leyenda=False)
    assert fig.layout.map.zoom == 15.0 and abs(fig.layout.map.center.lat - 19.32) < 1e-6
    assert fig.layout.map.style == "carto-positron"


def test_seleccion_distingue_empresa_y_municipio():
    from vinculate.vistas import mapa
    ev = lambda p: SimpleNamespace(selection=SimpleNamespace(points=[p]))
    assert mapa._seleccion(ev({"customdata": ["Greenbrier", "x"]})) == ("empresa", "Greenbrier")
    assert mapa._seleccion(ev({"location": "APIZACO"})) == ("municipio", "APIZACO")
    assert mapa._seleccion(SimpleNamespace(selection=SimpleNamespace(points=[]))) is None


# ----------------------------------------------------------------------------- página completa
def _pagina(tmp_path, monkeypatch, catalogo=None, sesion=None):
    from vinculate.vistas import mapa
    archivo = tmp_path / "tlaxcala_municipios.geojson"
    archivo.write_text(json.dumps(_geojson_sintetico()), encoding="utf-8")
    monkeypatch.setattr(mapa, "ARCHIVO_GEO", archivo)
    mapa._geo.clear()
    at = AppTest.from_function(_app, default_timeout=60)
    at.session_state[CLAVE_SESION] = sesion or _sesion(catalogo)
    at.session_state["_pagina_prueba"] = "mapa"
    return at


@pytest.mark.apptest
def test_pagina_tiene_casillas_y_un_solo_mapa(tmp_path, monkeypatch):
    at = _pagina(tmp_path, monkeypatch).run()
    assert not at.exception and not at.error
    assert at.checkbox(key="mapa_personas").value and at.checkbox(key="mapa_empresas").value
    assert len(at.get("plotly_chart")) == 1
    # solo empresas
    at.checkbox(key="mapa_personas").uncheck().run()
    assert not at.exception and len(at.get("plotly_chart")) == 1
    # solo personas
    at.checkbox(key="mapa_personas").check()
    at.checkbox(key="mapa_empresas").uncheck().run()
    assert not at.exception and len(at.get("plotly_chart")) == 1
    # ninguna → mensaje, sin gráfica
    at.checkbox(key="mapa_personas").uncheck().run()
    assert not at.get("plotly_chart") and "Marca al menos una casilla" in " ".join([e.value for e in at.markdown] + [e.value for e in at.info])


@pytest.mark.apptest
def test_empresas_sin_coordenadas_se_listan_aparte_y_las_invalidas_se_avisan(tmp_path, monkeypatch):
    at = _pagina(tmp_path, monkeypatch).run()
    etiquetas = " ".join(e.label for e in at.expander)
    assert "Empresas sin coordenadas" in etiquetas and "Coordenadas con problema" in etiquetas


@pytest.mark.apptest
def test_sin_columnas_de_coordenadas_se_explica_sin_romper(tmp_path, monkeypatch):
    base = [{"nombre": "Greenbrier", "sector": "Manufactura", "activo": True}]
    at = _pagina(tmp_path, monkeypatch, catalogo=base).run()
    assert not at.exception and not at.error
    assert "migración V004" in " ".join([i.value for i in at.info] + [w.value for w in at.warning])


@pytest.mark.apptest
def test_colaborador_solo_con_vacantes_no_ve_la_casilla_de_personas(tmp_path, monkeypatch):
    s = sesion_demo(cliente_demo(catalogo_empresas=[dict(c) for c in CATALOGO]), admin=False, vacantes=("view",), ridet=("view",))
    at = _pagina(tmp_path, monkeypatch, sesion=s).run()
    assert not at.exception and not at.error
    assert at.checkbox(key="mapa_personas").disabled and not at.checkbox(key="mapa_personas").value
    assert at.checkbox(key="mapa_empresas").value
