"""RIDET, mapa por municipio, estado del sistema, empresas y disponibilidad."""
import json

import pandas as pd
import pytest

from tests.demo import cliente_demo, sesion_demo
from vinculate.config.settings import RAIZ
from vinculate.core import mapa, ridet
from vinculate.core.texto import normalizar_texto
from vinculate.core.ubicacion import MUNICIPIOS_TLAXCALA

REFERENCIA = RAIZ / "referencia" / "ridet_empresas.csv"


# ------------------------------------------------------------------------- RIDET
def test_los_60_municipios_estan_en_una_sola_region():
    asignados = [normalizar_texto(m) for ms in ridet.REGION_MUNICIPIOS.values() for m in ms]
    assert len(asignados) == len(set(asignados)) == 60
    assert set(asignados) == {normalizar_texto(m) for m in MUNICIPIOS_TLAXCALA}


def test_referencia_coincide_con_los_totales_del_documento():
    ref = ridet.cargar_referencia(REFERENCIA)
    por_region = ref.groupby("region").size().to_dict()
    assert por_region == {r["region"]: r["empresas"] for r in ridet.REGIONES}
    assert len(ref) == 307
    assert not ref["empresa"].str.contains(r"\(\s*$|^\s*$", regex=True).any()


def test_clasificacion_por_nombre_exacto_parcial_y_alias():
    ref = ridet.cargar_referencia(REFERENCIA)
    t = ridet.clasificar_empresas(["Greenbrier", "Gonac", "SEBNMX", "Grupo R.D.A", "Vetrotex", "Empresa Inventada SA"], ref).set_index("empresa")
    assert t.loc["Greenbrier", "region"] == "Región Centro-Norte" and t.loc["Greenbrier", "metodo"] == ridet.METODO_EXACTO
    assert t.loc["Gonac", "region"] == "Región Oriente" and t.loc["Gonac", "metodo"] == ridet.METODO_PARCIAL
    assert t.loc["SEBNMX", "region"] == "Región Sur" and t.loc["SEBNMX", "metodo"] == ridet.METODO_ALIAS
    assert t.loc["Grupo R.D.A", "region"] == "Región Centro-Norte"
    assert t.loc["Vetrotex", "region"] == "Región Centro-Norte"
    assert t.loc["Empresa Inventada SA", "region"] == ridet.PENDIENTE


def test_empresa_en_varias_regiones_no_se_asigna_sola():
    ref = ridet.cargar_referencia(REFERENCIA)
    t = ridet.clasificar_empresas(["Lear Corporation"], ref).iloc[0]
    assert t["region"] == ridet.PENDIENTE and t["metodo"] == ridet.METODO_AMBIGUA


def test_el_municipio_capturado_manda_sobre_el_nombre():
    ref = ridet.cargar_referencia(REFERENCIA)
    t = ridet.clasificar_empresas(["Greenbrier", "Stripseel"], ref, {"Greenbrier": "HUAMANTLA", "Stripseel": "Fuera de Tlaxcala"}).set_index("empresa")
    assert t.loc["Greenbrier", "region"] == "Región Oriente" and t.loc["Greenbrier", "metodo"] == ridet.METODO_MUNICIPIO
    assert t.loc["Stripseel", "region"] == ridet.PENDIENTE      # fuera del estado: no pertenece a ninguna región RIDET


def test_nombres_cortos_no_coinciden_por_parecido():
    ref = ridet.cargar_referencia(REFERENCIA)
    t = ridet.clasificar_empresas(["DB", "XYZ Industrial"], ref)
    assert (t["region"] == ridet.PENDIENTE).all()


# ------------------------------------------------------------------------- mapa
def _geojson_sintetico(n=60, entidad="29", omitir=None):
    """60 cuadritos SINTÉTICOS (no son límites reales): solo sirven para probar la validación y el dibujo."""
    nombres = [m for m in MUNICIPIOS_TLAXCALA if m != omitir]
    feats = []
    for i, nom in enumerate(nombres[:n]):
        x, y = (i % 10) * 0.1, (i // 10) * 0.1
        feats.append({"type": "Feature", "properties": {"CVE_ENT": entidad, "CVE_MUN": f"{i + 1:03d}", "NOMGEO": nom.title()},
                      "geometry": {"type": "Polygon", "coordinates": [[[x, y], [x + .1, y], [x + .1, y + .1], [x, y + .1], [x, y]]]}})
    return {"type": "FeatureCollection", "features": feats}


def test_limites_y_vista_del_mapa():
    r = mapa.validar_geojson(_geojson_sintetico())
    lim = mapa.limites(r.geojson)
    assert lim == (0.0, 0.0, 1.0, 0.6)
    centro, zoom = mapa.vista_para(lim)
    assert centro == {"lon": 0.5, "lat": 0.3} and 0 < zoom < 18
    # Tlaxcala real: ~1.1° de ancho debe caber a un zoom regional (no mundial ni de calle)
    assert 8 < mapa.vista_para((-98.7, 19.1, -97.6, 19.7))[1] < 10
    assert mapa.limites({"features": []}) is None


def test_figura_del_mapa_no_depende_de_servidores_externos():
    """Choroplethmap con estilo white-bg: sin teselas ni topojson descargado desde un CDN."""
    from vinculate.vistas import mapa as vista
    r = mapa.validar_geojson(_geojson_sintetico())
    import pandas as pd
    fig = vista._figura(pd.DataFrame({"Municipio": ["APIZACO", "TLAXCALA"], "Total": [3, 1]}), r.geojson, "t")
    assert fig.data[0].type == "choroplethmap" and fig.layout.map.style == "white-bg"


def test_geojson_valido_con_60_municipios():
    r = mapa.validar_geojson(_geojson_sintetico())
    assert r.ok and len(r.geojson["features"]) == 60
    assert {f["properties"]["municipio"] for f in r.geojson["features"]} == set(MUNICIPIOS_TLAXCALA)


def test_geojson_con_variantes_de_inegi():
    gj = _geojson_sintetico()
    for f in gj["features"]:
        if f["properties"]["NOMGEO"].upper() == "XALOSTOC":
            f["properties"]["NOMGEO"] = "Xaloztoc"
        if f["properties"]["NOMGEO"].upper().startswith("ZITLALTEPEC"):
            f["properties"]["NOMGEO"] = "Ziltlaltépec"
    assert mapa.validar_geojson(gj).ok


@pytest.mark.parametrize("cambio,texto", [
    (lambda g: g["features"].pop(), "Se esperaban 60"),
    (lambda g: g["features"][0]["properties"].update(CVE_ENT="21"), "no de Tlaxcala"),
    (lambda g: g["features"][0]["properties"].update(NOMGEO="Narnia"), "No se reconoce"),
    (lambda g: g["features"][1]["properties"].update(NOMGEO=g["features"][0]["properties"]["NOMGEO"]), "más de una vez"),
    (lambda g: g["features"][0].update(geometry={"type": "Point", "coordinates": [0, 0]}), "polígono"),
])
def test_geojson_invalido_se_rechaza_con_motivo(cambio, texto):
    gj = _geojson_sintetico()
    cambio(gj)
    r = mapa.validar_geojson(gj)
    assert not r.ok and any(texto in p for p in r.problemas)


def test_no_es_featurecollection():
    assert not mapa.validar_geojson({"type": "Feature"}).ok
    assert not mapa.validar_geojson([]).ok


def test_cargar_sin_archivo_es_none_y_con_json_roto_informa(tmp_path):
    assert mapa.cargar_geojson(tmp_path / "no_existe.geojson") is None
    roto = tmp_path / "x.geojson"
    roto.write_text("{no es json", encoding="utf-8")
    assert not mapa.cargar_geojson(roto).ok
    bueno = tmp_path / "ok.geojson"
    bueno.write_text(json.dumps(_geojson_sintetico()), encoding="utf-8")
    assert mapa.cargar_geojson(bueno).ok


def test_conteos_por_municipio_separa_lo_que_no_es_municipio():
    serie = pd.Series(["APIZACO", "apizaco", "Tlaxcala", "PUEBLA", "", None, "Indefinido", "Narnia"])
    t, otros = mapa.conteos_por_municipio(serie)
    assert len(t) == 60 and t.set_index("Municipio").loc["APIZACO", "Total"] == 2
    assert otros == {"Fuera de Tlaxcala": 1, "Sin municipio definido": 3, "Ubicación no reconocida": 1}
    assert int(t["Total"].sum()) + sum(otros.values()) == 8     # nada se pierde ni se inventa


def test_script_de_geometria_filtra_entidad_y_exige_60(tmp_path):
    import subprocess
    import sys
    gj = _geojson_sintetico()
    gj["features"] += [{"type": "Feature", "properties": {"CVE_ENT": "21", "CVE_MUN": "001", "NOMGEO": "Puebla"},
                        "geometry": {"type": "Polygon", "coordinates": [[[5, 5], [6, 5], [6, 6], [5, 5]]]}}]
    entrada, salida = tmp_path / "pais.geojson", tmp_path / "geo" / "tlaxcala_municipios.geojson"
    entrada.write_text(json.dumps(gj), encoding="utf-8")
    script = str(RAIZ / "scripts" / "preparar_geometria.py")
    r = subprocess.run([sys.executable, script, str(entrada), str(salida)], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert mapa.cargar_geojson(salida).ok
    sql = (salida.parent / "cve_mun_municipios.sql").read_text(encoding="utf-8")
    assert sql.count("('") == 60 and "where m.nombre = v.nombre and m.cve_mun is null" in sql
    gj["features"] = gj["features"][:50]
    entrada.write_text(json.dumps(gj), encoding="utf-8")
    salida.unlink()
    r = subprocess.run([sys.executable, script, str(entrada), str(salida)], capture_output=True, text=True)
    assert r.returncode == 1 and not salida.exists()        # no escribe nada si no son exactamente 60


# ------------------------------------------------------------- estado del sistema
def test_migraciones_detectadas_segun_columnas():
    from vinculate.services import estado
    c = cliente_demo()
    c.tablas_faltantes.add("persona_disponibilidad")  # V008 sin aplicar: la tabla no existe
    s = sesion_demo(c)
    m = {x.clave: x.aplicada for x in estado.migraciones(s)}
    assert m["V005"] is False and m["V007"] is False and m["V004"] is False and m["V008"] is False
    c.tablas["personas"][0].update(anio_fuente="registrado", institucion_fuente="registrado")
    c.tablas["vacantes"][0].update(fecha_cierre=None, municipio_excepcion=None)
    c.tablas["catalogo_empresas"][0].update(municipio=None)
    c.tablas_faltantes.discard("persona_disponibilidad")
    m = {x.clave: x.aplicada for x in estado.migraciones(s)}
    assert m["V005"] is True and m["V007"] is True and m["V004"] is True and m["V008"] is True


def test_empresa_resumen_y_guardado_de_ubicacion():
    from vinculate.services import empresas
    c = cliente_demo()
    c.tablas["catalogo_empresas"][0].update(municipio=None, direccion=None, codigo_postal=None, ubicacion_fuente=None)
    s = sesion_demo(c)
    empresas.guardar_ubicacion(s, "Greenbrier", "APIZACO", "Calle 1", "90300")
    fila = c.tablas["catalogo_empresas"][0]
    assert fila["municipio"] == "APIZACO" and fila["ubicacion_fuente"] == "manual" and fila["codigo_postal"] == "90300"
    with pytest.raises(ValueError):
        empresas.guardar_ubicacion(s, "Greenbrier", "NARNIA")
    with pytest.raises(ValueError):
        empresas.guardar_ubicacion(s, "Greenbrier", "APIZACO", codigo_postal="12")


def test_disponibilidad_manual(estado_sesion):
    from vinculate.services import disponibilidad
    c = cliente_demo()
    s = sesion_demo(c)
    assert disponibilidad.disponibles(s) is None or disponibilidad.disponibles(s) == 0
    c.tablas["persona_disponibilidad"] = []
    estado_sesion.clear()
    assert disponibilidad.disponibles(s) == 0
    disponibilidad.guardar(s, "PER-0001", True, "llamar el lunes")
    estado_sesion.clear()
    assert disponibilidad.disponibles(s) == 1
