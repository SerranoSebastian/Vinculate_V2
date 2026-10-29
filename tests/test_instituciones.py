"""Instituciones educativas: directorio, captura (solo administración), figura del mapa y pantallas."""
import json
from types import SimpleNamespace

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from tests.demo import cliente_demo, sesion_demo
from tests.test_paginas import CLAVE_SESION, _app
from tests.test_territorio import _geojson_sintetico
from vinculate.core import puntos
from vinculate.repositories.errores import SinPermiso
from vinculate.services import datos, instituciones

# Coordenadas sintéticas dentro de la caja de Tlaxcala (no son ubicaciones reales).
CATALOGO = [
    {"nombre": "UATx", "activo": True, "tipo": "Universidad", "municipio": "TLAXCALA", "latitud": 19.3200, "longitud": -98.2300},
    {"nombre": "UPTx", "activo": True, "tipo": "Universidad", "municipio": "TLAXCALA", "latitud": 19.3200, "longitud": -98.2300},   # misma ubicación
    {"nombre": "UTT", "activo": True, "tipo": None, "municipio": None, "latitud": None, "longitud": None},                           # sin coordenadas
    {"nombre": "ITA", "activo": True, "tipo": "Escuela", "municipio": "APIZACO", "latitud": -98.2, "longitud": 19.3},                # invertidas
]


def _sesion(catalogo=None, admin=True, **mods):
    c = cliente_demo(catalogo_instituciones=[dict(x) for x in (CATALOGO if catalogo is None else catalogo)])
    c.pks["catalogo_instituciones"] = "nombre"
    return sesion_demo(c, admin=admin, **mods)


def test_directorio_solo_instituciones_con_personas_y_sin_inventar():
    s = _sesion()
    d = instituciones.directorio(datos.personas(s), instituciones.catalogo(s))
    assert set(d["Institución"]) <= {"UATx", "UPTx", "UTT", "ITA", "UNAM"}
    assert (d["Personas"] > 0).all()
    utt = d[d["Institución"] == "UTT"].iloc[0]
    assert pd.isna(utt["Latitud"]) and utt["Tipo"] == ""                          # nada inventado
    unam = d[d["Institución"] == "UNAM"]                                          # no está en el catálogo: aparece, sin ubicación
    assert unam.empty or pd.isna(unam.iloc[0]["Latitud"])


def test_directorio_cuenta_personas_distintas_y_excluye_sin_dato():
    p = pd.DataFrame({"Institución": ["A", "A", "A", "Indefinido", "", "B"], "id_persona_maestro": ["P1", "P1", "P2", "P3", "P4", "P5"],
                      "institucion_fuente": ["registrado", "registrado", "balanceado", "registrado", "registrado", "registrado"]})
    d = instituciones.directorio(p, pd.DataFrame(columns=["nombre", "activo"]))
    assert d.set_index("Institución")["Personas"].to_dict() == {"A": 2, "B": 1}
    assert d.set_index("Institución")["Asignadas por balanceo"].to_dict() == {"A": 1, "B": 0}


def test_habilitada_detecta_columnas_faltantes():
    from tests.fakes import FakeAPIError
    s = _sesion()
    assert instituciones.habilitada(s) is True
    s.cliente.fallo_siguiente = (("catalogo_instituciones", "select"), FakeAPIError("42703", "column catalogo_instituciones.latitud does not exist"))
    assert instituciones.habilitada(s) is False                                                   # sin V011
    assert instituciones.habilitada(_sesion(catalogo=[])) is True                                 # catálogo vacío: no hay muestra


def test_guardar_valida_audita_y_borra():
    s = _sesion()
    instituciones.guardar(s, "UTT", "Escuela", "APIZACO", "19,4100", "-98,1400")
    fila = [c for c in s.cliente.tablas["catalogo_instituciones"] if c["nombre"] == "UTT"][0]
    assert (fila["tipo"], fila["municipio"], fila["latitud"], fila["longitud"], fila["ubicacion_fuente"]) == ("Escuela", "APIZACO", 19.41, -98.14, "manual")
    for args in (("UTT", "Banco", "", None, None), ("UTT", "", "Marte", None, None), ("UTT", "", "", -98.2, 19.35), ("UTT", "", "", 19.3, None)):
        with pytest.raises(ValueError):
            instituciones.guardar(s, *args)
    with pytest.raises(ValueError):
        instituciones.guardar(s, "UTT", "", "", None, None, codigo_postal="90")
    instituciones.guardar(s, "UTT", "Escuela", "APIZACO", None, None)                 # borrar coordenadas
    assert [c for c in s.cliente.tablas["catalogo_instituciones"] if c["nombre"] == "UTT"][0]["latitud"] is None


def test_guardar_crea_la_fila_si_la_institucion_no_estaba_en_el_catalogo():
    s = _sesion()
    instituciones.guardar(s, "UNAM", "Universidad", "", 19.3, -98.2)
    assert [c["nombre"] for c in s.cliente.tablas["catalogo_instituciones"]].count("UNAM") == 1


def test_solo_administracion_puede_capturar():
    s = _sesion(admin=False, personas=("view", "edit"), vacantes=("view", "edit"))
    with pytest.raises(SinPermiso):
        instituciones.guardar(s, "UTT", "Escuela", "", 19.3, -98.2)
    s2 = _sesion(admin=False, administracion=("view", "edit"))
    instituciones.guardar(s2, "UTT", "Escuela", "", 19.3, -98.2)                     # con administracion.edit sí


def test_edicion_rapida_guarda_solo_lo_que_cambio():
    s = _sesion()
    d = instituciones.directorio(datos.personas(s), instituciones.catalogo(s))
    base = d.copy()
    ed = base[["Institución", "Personas", "Tipo", "Municipio", "Latitud", "Longitud"]].assign(**{"Pegar (lat, lon)": ""})
    ed.loc[ed["Institución"] == "UTT", "Pegar (lat, lon)"] = "19.31390, -98.24040"      # copiado de Google Maps
    ed.loc[ed["Institución"] == "UTT", "Tipo"] = "Escuela"
    ed.loc[ed["Institución"] == "UATx", "Latitud"] = 60.0                               # inválida
    guardadas, errores = instituciones.guardar_lote(s, base, ed)
    assert guardadas == ["UTT"] and len(errores) == 1 and "UATx" in errores[0]
    fila = [c for c in s.cliente.tablas["catalogo_instituciones"] if c["nombre"] == "UTT"][0]
    assert (fila["latitud"], fila["longitud"], fila["tipo"]) == (19.3139, -98.2404, "Escuela")
    sin_cambios = base[["Institución", "Personas", "Tipo", "Municipio", "Latitud", "Longitud"]].assign(**{"Pegar (lat, lon)": ""})
    assert instituciones.guardar_lote(s, base, sin_cambios) == ([], [])


def test_paleta_de_instituciones_distinta_a_la_de_empresas():
    assert not set(puntos.PALETA_INSTITUCIONES) & set(puntos.PALETA_EMPRESAS)
    col = puntos.asignar_colores([f"I{i}" for i in range(20)], puntos.PALETA_INSTITUCIONES)
    assert len(set(col.values())) == 20


# ------------------------------------------------------------------ figura y selección
def _pts_inst():
    s = _sesion()
    d = instituciones.directorio(datos.personas(s), instituciones.catalogo(s))
    ok, _, _ = puntos.puntos_validos(d)
    return puntos.separar_superpuestos(ok, col="Institución"), puntos.asignar_colores(ok["Institución"].tolist(), puntos.PALETA_INSTITUCIONES)


def test_figura_dibuja_instituciones_con_contorno_oscuro_y_hover_real():
    from vinculate.vistas import mapa
    inst, colores = _pts_inst()
    geo = mapa.nucleo.validar_geojson(_geojson_sintetico()).geojson
    fig = mapa._figura(None, geo, pd.DataFrame(), {}, estilo="white-bg", enfoque=mapa.TODO_EL_ESTADO, titulo="t", mostrar_leyenda=True,
                       inst=inst, colores_inst=colores)
    nombres = [t.name for t in fig.data if t.type == "scattermap" and t.name]
    assert sorted(nombres) == sorted("🏫 " + n for n in inst["Institución"])
    assert any(t.marker.color == "#1B1B1B" for t in fig.data if t.type == "scattermap")       # contorno oscuro
    uatx = [t for t in fig.data if t.name == "🏫 UATx"][0]
    assert list(uatx.customdata[0][:2]) == [mapa.ETIQUETA_INST, "UATx"] and list(uatx.customdata[0][-2:]) == [19.32, -98.23]


def test_figura_acerca_a_una_institucion():
    from vinculate.vistas import mapa
    inst, colores = _pts_inst()
    fig = mapa._figura(None, None, pd.DataFrame(), {}, estilo="carto-positron", enfoque="Institución: UATx", titulo="t", mostrar_leyenda=False,
                       inst=inst, colores_inst=colores)
    assert fig.layout.map.zoom == 15.0 and abs(fig.layout.map.center.lat - 19.32) < 1e-6


def test_seleccion_distingue_institucion():
    from vinculate.vistas import mapa
    ev = lambda p: SimpleNamespace(selection=SimpleNamespace(points=[p]))
    assert mapa._seleccion(ev({"customdata": [mapa.ETIQUETA_INST, "UATx", "Universidad"]})) == ("institucion", "UATx")
    assert mapa._seleccion(ev({"customdata": ["Greenbrier", "x"]})) == ("empresa", "Greenbrier")


# ------------------------------------------------------------------ páginas
def _pagina(tmp_path, monkeypatch, pagina, sesion):
    from vinculate.vistas import mapa
    archivo = tmp_path / "tlaxcala_municipios.geojson"
    archivo.write_text(json.dumps(_geojson_sintetico()), encoding="utf-8")
    monkeypatch.setattr(mapa, "ARCHIVO_GEO", archivo)
    mapa._geo.clear()
    at = AppTest.from_function(_app, default_timeout=60)
    at.session_state[CLAVE_SESION] = sesion
    at.session_state["_pagina_prueba"] = pagina
    return at


@pytest.mark.apptest
def test_mapa_con_casilla_de_instituciones(tmp_path, monkeypatch):
    at = _pagina(tmp_path, monkeypatch, "mapa", _sesion()).run()
    assert not at.exception and not at.error
    assert at.checkbox(key="mapa_instituciones").value is False                       # apagada de inicio
    at.checkbox(key="mapa_instituciones").check().run()
    assert not at.exception and not at.error and len(at.get("plotly_chart")) == 1
    etiquetas = " ".join(e.label for e in at.expander)
    assert "Instituciones sin coordenadas" in etiquetas and "con problema" in etiquetas
    # solo instituciones
    at.checkbox(key="mapa_personas").uncheck()
    at.checkbox(key="mapa_empresas").uncheck().run()
    assert not at.exception and len(at.get("plotly_chart")) == 1


@pytest.mark.apptest
def test_mapa_sin_columnas_v011_se_explica_sin_romper(tmp_path, monkeypatch):
    monkeypatch.setattr(instituciones, "habilitada", lambda s: False)
    at = _pagina(tmp_path, monkeypatch, "mapa", _sesion(catalogo=[{"nombre": "UATx", "activo": True}])).run()
    at.checkbox(key="mapa_instituciones").check().run()
    assert not at.exception and not at.error
    assert "migración V011" in " ".join(i.value for i in at.info)


@pytest.mark.apptest
def test_administracion_instituciones_muestra_indicadores_y_editor(tmp_path, monkeypatch):
    at = _pagina(tmp_path, monkeypatch, "administracion", _sesion()).run()
    at.session_state["adm_apartado"] = "🏫 Instituciones"
    at.run()
    assert not at.exception and not at.error, [e.value for e in at.exception]
    etiquetas = [m.label for m in at.metric] if at.metric else []
    texto = " ".join(m.value for m in at.markdown)
    assert "Instituciones con personas" in texto and "Tipo y ubicación exacta" in texto


# ------------------------------------------------------------------ empresas sin vacantes y alta de empresas
def _sesion_emp(catalogo=None, **mods):
    c = cliente_demo(catalogo_empresas=catalogo if catalogo is not None else [{"nombre": "Greenbrier", "sector": "Manufactura", "activo": True,
                                                                              "municipio": "APIZACO", "latitud": 19.41, "longitud": -98.14}])
    return sesion_demo(c, **mods)


def test_directorio_incluye_empresas_conocidas_sin_vacantes_y_las_ubica_si_tienen_coordenadas():
    from vinculate.services import empresas
    s = _sesion_emp([{"nombre": "Greenbrier", "sector": "Manufactura", "activo": True, "municipio": "APIZACO", "latitud": 19.41, "longitud": -98.14},
                     {"nombre": "Dow", "sector": "Industria Química", "activo": True, "municipio": "TLAXCALA", "latitud": 19.32, "longitud": -98.23}])
    vinc = pd.DataFrame({"empresa": ["Empresa Solo Seguimiento", "Sin asignar"], "sector_empresa": ["Textil", ""]})
    adic = empresas.adicionales(vinc)
    assert "Dow" in adic and "Empresa Solo Seguimiento" in adic and "Sin asignar" not in adic     # lista fija + seguimientos
    d = empresas.directorio(datos.vacantes(s), empresas.catalogo(s), adic)
    assert d["Empresa"].is_unique
    dow = d[d["Empresa"] == "Dow"].iloc[0]
    assert dow["Vacantes"] == 0 and (dow["Latitud"], dow["Longitud"]) == (19.32, -98.23)          # sin vacantes, pero con su ubicación
    assert d[d["Empresa"] == "Empresa Solo Seguimiento"].iloc[0]["Sector"] == "Textil"
    ok, sin, _ = puntos.puntos_validos(d)
    assert "Dow" in set(ok["Empresa"]) and "Empresa Solo Seguimiento" in set(sin["Empresa"])
    # sin la lista adicional, sigue funcionando como antes
    assert len(empresas.directorio(datos.vacantes(s), empresas.catalogo(s))) <= len(d)


def test_crear_empresa_valida_duplicados_y_permiso():
    from vinculate.repositories.errores import SinPermiso
    from vinculate.services import empresas
    s = _sesion_emp()
    conocidas = ["Greenbrier", "Dow"]
    empresas.crear(s, "  Textiles   Nuevos SA ", "Textil", "APIZACO", "Calle 1", "90300", 19.4, -98.1, conocidas=conocidas)
    fila = [c for c in s.cliente.tablas["catalogo_empresas"] if c["nombre"] == "Textiles Nuevos SA"][0]
    assert (fila["sector"], fila["municipio"], fila["latitud"], fila["ubicacion_fuente"], fila["activo"]) == ("Textil", "APIZACO", 19.4, "manual", True)
    empresas.crear(s, "Solo Nombre", conocidas=conocidas)                                           # sin ubicación: solo nombre y sector
    f2 = [c for c in s.cliente.tablas["catalogo_empresas"] if c["nombre"] == "Solo Nombre"][0]
    assert "latitud" not in f2 and f2["sector"] is None
    casos = [dict(nombre=""), dict(nombre="dów"), dict(nombre="GREENBRIER"), dict(nombre="Otra", municipio="Marte"),
             dict(nombre="Otra", codigo_postal="12"), dict(nombre="Otra", latitud=-98.2, longitud=19.4), dict(nombre="Otra", latitud=19.4)]
    for caso in casos:
        with pytest.raises(ValueError):
            empresas.crear(s, conocidas=conocidas, **caso)
    sin_permiso = _sesion_emp(admin=False, vacantes=("view", "edit"))
    with pytest.raises(SinPermiso):
        empresas.crear(sin_permiso, "Otra Empresa")
    s_ok = _sesion_emp(admin=False, vacantes=("view", "create"))
    empresas.crear(s_ok, "Otra Empresa")                                                            # vacantes.create basta (como la RLS)


def test_opciones_incluye_empresas_dadas_de_alta():
    from vinculate.services import empresas
    s = _sesion_emp([{"nombre": "Empresa Nueva Mia", "sector": "Textil", "activo": True}, {"nombre": "Inactiva SA", "sector": "X", "activo": False}])
    nombres, sector = empresas.opciones(s)
    assert "Empresa Nueva Mia" in nombres and sector["Empresa Nueva Mia"] == "Textil" and "Inactiva SA" not in nombres
    assert "Dow" in nombres                                                                           # la lista fija sigue ahí


@pytest.mark.apptest
def test_pagina_empresas_tiene_alta_y_muestra_empresas_sin_vacantes(tmp_path, monkeypatch):
    at = _pagina(tmp_path, monkeypatch, "vacantes", _sesion_emp()).run()
    at.session_state["vacantes_apartado"] = "🏢 Empresas"
    at.run()
    assert not at.exception and not at.error, [e.value for e in at.exception]
    assert any("Agregar una empresa nueva" in e.label for e in at.expander)
