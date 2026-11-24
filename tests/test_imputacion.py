"""Imputación proporcional: reparte los datos faltantes según la distribución de quienes sí tienen el dato, sin tocar lo capturado."""
import random

import pandas as pd
import pytest

from tests.demo import cliente_demo, pers, sesion_demo
from vinculate.core import mapeo
from vinculate.core.imputacion import imputar_proporcional, resumen_imputacion
from vinculate.core.personas import obtener_personas_maestras, preparar_personas_dashboard
from vinculate.services import datos


def _filas(n_derecho=60, n_conta=40, n_sin=10, municipio="Apizaco", **extra):
    filas = []
    for i in range(1, n_derecho + n_conta + n_sin + 1):
        carrera = "Derecho" if i <= n_derecho else "Contaduría" if i <= n_derecho + n_conta else ""
        filas.append({"id_persona": f"I-{i:05d}-{i:05d}", "id_persona_maestro": f"PER-{i:04d}", "nombre": f"Persona {i}", "sexo": "Mujer",
                      "escolaridad": "Superior", "carrera": carrera, "institucion": "UATx", "municipio": municipio, "vinculacion": "Atención",
                      "fecha_registro": "2026-03-01", "anio": 2026, "estatus_vinculacion": "Vinculado", **extra})
    return filas


def _df(filas):
    return mapeo.a_dataframe("personas", filas)


def test_reparte_en_la_misma_proporcion_que_los_datos_conocidos():
    d = preparar_personas_dashboard(_df(_filas()))
    imp = d[d["carrera_imputado"]]
    assert len(imp) == 10 and imp["carrera"].value_counts().to_dict() == {"Derecho": 6, "Contaduría": 4}   # 60 % / 40 % de 10
    assert d["carrera"].value_counts().to_dict() == {"Derecho": 66, "Contaduría": 44}
    assert not d.loc[~d["carrera_imputado"], "carrera"].isin(["", "Indefinido"]).any()


def test_no_toca_lo_capturado_y_no_inventa_columnas_sin_datos():
    antes = _df(_filas())
    d = preparar_personas_dashboard(antes)
    capturado = d[~d["carrera_imputado"]]
    assert set(capturado["carrera"]) == {"Derecho", "Contaduría"}
    assert not d["sexo_imputado"].any() and not d["escolaridad_imputado"].any()
    assert d["datos_imputados"].eq("carrera").sum() == 10


def test_municipio_tambien_se_completa_con_la_distribucion_conocida():
    filas = []
    for i in range(1, 101):
        f = _filas(1, 0, 0)[0]
        f.update(id_persona=f"I-{i:05d}-{i:05d}", id_persona_maestro=f"PER-{i:04d}", municipio="APIZACO" if i <= 40 else "HUAMANTLA" if i <= 80 else "")
        filas.append(f)
    d = preparar_personas_dashboard(_df(filas))
    assert d["municipio_imputado"].sum() == 20 and d["municipio"].value_counts().to_dict() == {"APIZACO": 50, "HUAMANTLA": 50}


def test_es_determinista_y_no_depende_del_orden_de_las_filas():
    filas = _filas()
    a = preparar_personas_dashboard(_df(filas)).set_index("id_persona")["carrera"]
    random.Random(3).shuffle(filas)
    b = preparar_personas_dashboard(_df(filas)).set_index("id_persona")["carrera"]
    assert a.sort_index().equals(b.sort_index())


def test_si_la_persona_tiene_el_dato_en_otro_registro_se_usa_ese():
    filas = _filas(10, 10, 0)
    extra = dict(filas[0], id_persona="I-99999-00001", carrera="", fecha_registro="2026-06-01")   # misma persona, otro registro sin carrera
    d = preparar_personas_dashboard(_df(filas + [extra]))
    fila = d[d["id_persona"].eq("I-99999-00001")].iloc[0]
    assert fila["carrera"] == "Derecho" and not fila["carrera_imputado"]


def test_edad_numerica_sale_de_la_distribucion_conocida():
    filas = _filas(30, 0, 0)
    for i, f in enumerate(filas):
        f["edad"] = 20 + (i % 5)            # 20..24
    for f in filas[:6]:
        f["edad"] = None
    d = preparar_personas_dashboard(_df(filas))
    assert d["edad"].notna().all() and d.loc[d["edad_imputado"], "edad"].between(20, 24).all()
    assert d["edad_imputado"].sum() == 6


def test_se_puede_apagar_y_entonces_queda_tal_como_se_capturo():
    d = preparar_personas_dashboard(_df(_filas()), imputar=False)
    assert "carrera_imputado" not in d.columns and d["carrera"].eq("").sum() == 10
    m = obtener_personas_maestras(_df(_filas()), imputar=False)
    assert m["carrera"].eq("").sum() == 10


def test_sin_ningun_dato_conocido_no_falla_ni_inventa():
    d = imputar_proporcional(preparar_personas_dashboard(_df(_filas(0, 0, 5)), imputar=False))
    assert d["carrera"].eq("").all() and not d["carrera_imputado"].any()


def test_maestras_marcan_que_se_imputo_y_el_resumen_cuenta_personas():
    d = preparar_personas_dashboard(_df(_filas()))
    m = obtener_personas_maestras(d)
    assert len(m) == 110 and m["carrera_imputado"].sum() == 10
    assert (m.loc[m["carrera_imputado"], "datos_imputados"] == "carrera").all()
    r = resumen_imputacion(d).set_index("Columna")
    assert r.loc["carrera", "Completadas"] == 10 and r.loc["carrera", "Con dato capturado"] == 100 and r.loc["carrera", "% completadas"] == 9.1


def test_los_formularios_usan_personas_sin_imputar():
    filas = pers()
    for f in filas:
        if f["id_persona_maestro"] in ("PER-0001", "PER-0002", "PER-0003"):   # el demo repite personas: se vacía TODA su carrera
            f["carrera"] = ""
    s = sesion_demo(cliente_demo(personas=filas))
    assert datos.maestras(s)["carrera"].map(lambda v: str(v).strip() in ("", "Indefinido")).sum() == 0     # estadísticas: completadas
    reales = datos.maestras_reales(s)
    assert "carrera_imputado" not in reales.columns or not reales["carrera_imputado"].any()
    assert reales["carrera"].map(lambda v: str(v).strip() == "").sum() > 0                                 # formularios: lo capturado


def _textos_visibles(at) -> str:
    partes = [m.value for m in at.markdown] + [c.value for c in at.caption] + [e.label for e in at.expander]
    partes += [str(c) for df in at.dataframe for c in df.value.columns]
    return " ".join(partes).lower()


@pytest.mark.apptest
@pytest.mark.parametrize("pagina", ["inicio", "personas", "explorador"])
def test_la_plataforma_no_menciona_la_imputacion(pagina):
    """Los datos completados se explican de forma verbal: en pantalla no debe aparecer ninguna marca ni aviso."""
    from streamlit.testing.v1 import AppTest

    from tests.test_paginas import _app
    from vinculate.auth.sesion import CLAVE_SESION

    filas = pers()
    for f in filas:
        if f["id_persona_maestro"] in ("PER-0001", "PER-0002", "PER-0003"):
            f["carrera"] = ""
    for base in ("personas", "historicos") if pagina == "explorador" else ("personas",):
        at = AppTest.from_function(_app, default_timeout=60)
        at.session_state[CLAVE_SESION] = sesion_demo(cliente_demo(personas=filas))
        at.session_state["_pagina_prueba"] = pagina
        if pagina == "explorador":
            at.session_state["explorador_base"] = base
        if pagina == "personas":
            at.session_state["personas_apartado"] = "👤 Directorio y ficha"
        at.run()
        assert not at.exception, [e.value for e in at.exception]
        assert "imput" not in _textos_visibles(at) and "completad" not in _textos_visibles(at)


def test_la_ficha_no_marca_datos_imputados():
    from vinculate.vistas import explorador, ficha

    assert "datos_imputados" not in sum(explorador.COLS_VISTA.values(), [])
    assert not hasattr(ficha, "_valor_perfil")


def test_cambiar_la_configuracion_descarta_lo_memorizado(monkeypatch):
    """Si se cambian las columnas imputables, las pantallas no deben seguir mostrando datos procesados con la configuración vieja."""
    filas = pers()
    for f in filas:
        if f["id_persona_maestro"] in ("PER-0001", "PER-0002", "PER-0003"):
            f["municipio"] = ""
    s = sesion_demo(cliente_demo(personas=filas))
    from vinculate.core import constantes
    from vinculate.services import datos as d

    def configurar(cols):
        for modulo in ("vinculate.services.datos", "vinculate.core.imputacion", "vinculate.core.personas"):
            monkeypatch.setattr(f"{modulo}.COLUMNAS_IMPUTABLES", cols)

    configurar([c for c in constantes.COLUMNAS_IMPUTABLES if c != "municipio"])
    sin = d.maestras(s)
    assert sin["municipio"].map(lambda v: str(v).strip() in ("", "Indefinido")).sum() > 0
    configurar(constantes.COLUMNAS_IMPUTABLES)
    con = d.maestras(s)
    assert con["municipio"].map(lambda v: str(v).strip() in ("", "Indefinido")).sum() == 0
