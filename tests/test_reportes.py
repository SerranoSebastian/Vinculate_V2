"""Reporte: las cifras coinciden con Inicio, el alcance y el periodo filtran bien, el PDF/Excel se generan y respetan permisos y auditoría."""
import io
import re

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from tests.demo import cliente_demo, sesion_demo
from vinculate.auth.sesion import CLAVE_SESION
from vinculate.core import reportes as nucleo
from vinculate.core.personas import solo_vinculaciones
from vinculate.repositories.errores import SinPermiso
from vinculate.services import datos, reporte_pdf, reportes


@pytest.fixture
def s():
    return sesion_demo()


def _r(s, tipo="general", valor=None, anios=()):
    return reportes.construir(s, tipo, valor, list(anios))


def test_las_cifras_coinciden_con_inicio(s):
    pf = datos.personas_dashboard(s)
    r = _r(s)
    assert r.indicadores["personas"] == pf["id_persona_maestro"].nunique()
    assert r.indicadores["vinculaciones"] == len(solo_vinculaciones(pf))
    assert r.indicadores["colocadas"] == 1 and r.indicadores["colocaciones"] == 1


def test_el_embudo_nunca_crece_hacia_abajo(s):
    for anios in ((), (2024,), (2023, 2026)):
        e = _r(s, anios=anios).embudo["Personas"].tolist()
        assert e == sorted(e, reverse=True)


def test_periodo_filtra_personas_y_vinculaciones(s):
    pf = datos.personas_dashboard(s)
    r = _r(s, anios=[2024])
    sub = pf[pf["año"].eq(2024)]
    assert r.indicadores["personas"] >= sub["id_persona_maestro"].nunique()
    assert r.indicadores["vinculaciones"] == len(solo_vinculaciones(sub))
    assert r.periodo == "2024"
    assert set(r.anual["Año"]) <= {2024, 2026}  # 2026 solo por la fecha de una colocación/seguimiento de prueba


def test_reporte_por_municipio_solo_cuenta_a_esa_gente(s):
    mun = nucleo.opciones(datos.personas_dashboard(s))["municipio"][0]
    g, m = _r(s), _r(s, "municipio", mun)
    assert 0 < m.indicadores["personas"] < g.indicadores["personas"]
    assert m.participacion == round(100 * m.indicadores["personas"] / g.indicadores["personas"], 1)
    assert m.municipios.empty and not m.instituciones.empty
    maestras = datos.maestras(s)
    esperado = int((maestras["municipio"].str.upper() == mun.upper()).sum())
    assert m.indicadores["personas"] == esperado


def test_reporte_por_institucion(s):
    inst = nucleo.opciones(datos.personas_dashboard(s))["institucion"][0]
    r = _r(s, "institucion", inst)
    assert r.instituciones.empty and not r.municipios.empty
    assert inst in r.subtitulo


def test_tipo_invalido_o_sin_valor(s):
    with pytest.raises(ValueError):
        _r(s, "otro")
    with pytest.raises(ValueError):
        _r(s, "municipio", None)


def test_sin_permiso_de_seguimientos_el_reporte_no_trae_colocaciones():
    c = cliente_demo()
    s2 = sesion_demo(c, admin=False, inicio=("view", "export"), personas=("view",))
    r = _r(s2)
    assert not r.colocaciones_disponibles and r.indicadores["tasa_colocacion"] is None
    assert len(r.embudo) == 2 and r.empresas.empty


def test_sin_permiso_de_ver_no_se_construye():
    with pytest.raises(SinPermiso):
        _r(sesion_demo(admin=False))


def test_pdf_valido_con_cuatro_secciones(s):
    r = _r(s)
    datos_b, archivo, mime = reportes.exportar(s, r, "pdf", "Nota con <b>etiquetas</b> & acentos: ñ")
    assert datos_b.startswith(b"%PDF") and mime == "application/pdf" and archivo.endswith(".pdf")
    assert len(re.findall(rb"/Type\s*/Page\b", datos_b)) >= 3


def test_graficas_estan_las_que_tienen_datos(s):
    g = reporte_pdf.graficas(_r(s))
    assert {"embudo", "avance", "tipos", "municipios", "instituciones", "sexo", "escolaridad", "edad"} <= set(g)
    assert all(v.startswith(b"\x89PNG") for v in g.values())


def test_excel_tiene_hojas_y_no_lleva_datos_personales(s):
    r = _r(s)
    datos_b, _, _ = reportes.exportar(s, r, "xlsx")
    hojas = pd.read_excel(io.BytesIO(datos_b), sheet_name=None)
    assert {"Indicadores", "Embudo", "Por año"} <= set(hojas)
    texto = " ".join(str(v) for h in hojas.values() for v in h.to_numpy().ravel())
    for pista in ("example.test", "@", "246"):
        assert pista not in texto
    maestras = datos.maestras(s)
    assert not any(str(n) in texto for n in maestras["nombre"].head(20))


def test_exportar_exige_permiso_y_audita(monkeypatch):
    s_ok = sesion_demo()
    r = _r(s_ok)
    llamadas = []
    monkeypatch.setattr("vinculate.auth.servicio.auditar", lambda accion, detalle="": llamadas.append((accion, detalle)))
    reportes.exportar(s_ok, r, "pdf")
    assert llamadas and llamadas[0][0] == "inicio_reporte" and "tipo=general" in llamadas[0][1]
    sin = sesion_demo(admin=False, inicio=("view",), personas=("view",))
    with pytest.raises(SinPermiso):
        reportes.exportar(sin, _r(sin), "pdf")


def test_no_menciona_imputacion_ni_nombres_en_lecturas(s):
    r = _r(s)
    texto = " ".join(r.lecturas).lower()
    assert "imput" not in texto and "estimad" not in texto
    assert "imput" not in " ".join(nucleo.tablas_excel(r)).lower()


def test_nombre_legible_de_municipios():
    assert nucleo.nombre_legible("SAN PABLO DEL MONTE") == "San Pablo del Monte"
    assert nucleo.nombre_legible("Tlaxcala") == "Tlaxcala"
    assert nucleo.nombre_legible("UATx") == "UATx"


def test_periodo_en_texto():
    assert nucleo.texto_periodo([]) == "Todos los años"
    assert nucleo.texto_periodo([2025]) == "2025"
    assert nucleo.texto_periodo([2023, 2024, 2025]) == "2023 a 2025"
    assert nucleo.texto_periodo([2023, 2025]) == "2023, 2025"


def test_sin_datos_el_reporte_sale_vacio_pero_valido():
    r = nucleo.construir(pd.DataFrame(), None)
    assert r.vacio and r.lecturas == []


# ---------------------------------------------------------------- página
def _app():
    import streamlit as st

    from vinculate.config.theme import aplicar_estilos
    from vinculate.vistas import reporte
    aplicar_estilos()
    reporte.render()


@pytest.mark.apptest
def test_pagina_genera_vista_previa_y_prepara_archivos():
    at = AppTest.from_function(_app, default_timeout=120)
    at.session_state[CLAVE_SESION] = sesion_demo()
    at.run()
    assert not at.exception
    at.button(key="rep_generar").click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert "Lectura rápida" in " ".join(m.value for m in at.markdown)
    at.button(key="rep_prep_pdf").click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert not at.error


@pytest.mark.apptest
def test_pagina_sin_permisos_no_muestra_nada():
    at = AppTest.from_function(_app, default_timeout=60)
    at.session_state[CLAVE_SESION] = sesion_demo(admin=False)
    at.run()
    assert not at.exception
    assert len(at.button) == 0
    assert "example.test" not in " ".join(m.value for m in at.markdown)
