"""Registro sin vinculación (estatus «Registrada») y colocaciones (varias por persona, distinguidas por fecha)."""
from datetime import date

import pandas as pd
import pytest

from tests.demo import cliente_demo, sesion_demo
from vinculate.core import colocaciones as nucleo
from vinculate.core import mapeo
from vinculate.core.constantes import ESTATUS_REGISTRADA
from vinculate.core.personas import (obtener_personas_maestras, preparar_personas_dashboard, resumen_vinculaciones_por_persona,
                                     solo_vinculaciones)
from vinculate.core.vinculaciones import estado_por_persona
from vinculate.services import colocaciones as servicio


def _fila(i, maestro, estatus):
    return {"id_persona": f"I-{i:05d}-{int(maestro[-4:]):05d}", "id_persona_maestro": maestro, "nombre": f"Persona {maestro}", "sexo": "Mujer",
            "escolaridad": "Superior", "carrera": "Derecho", "institucion": "UATx", "municipio": "Apizaco", "vinculacion": "Atención",
            "fecha_registro": "2026-03-01", "anio": 2026, "estatus_vinculacion": estatus}


@pytest.fixture
def personas():
    filas = [_fila(1, "PER-0001", "Vinculado"), _fila(2, "PER-0001", None), _fila(3, "PER-0002", "Registrada"), _fila(4, "PER-0003", "registrada")]
    return mapeo.a_dataframe("personas", filas)


# ------------------------------------------------------------------ registro sin vinculación
def test_personas_nuevas_conservan_registrada_y_las_viejas_siguen_vinculadas(personas):
    d = preparar_personas_dashboard(personas)
    por_id = dict(zip(d["id_persona"], d["estatus_vinculacion"]))
    assert por_id["I-00001-00001"] == "Vinculado" and por_id["I-00002-00001"] == "Vinculado"   # lo histórico sigue igual
    assert por_id["I-00003-00002"] == ESTATUS_REGISTRADA and por_id["I-00004-00003"] == ESTATUS_REGISTRADA
    assert len(solo_vinculaciones(d)) == 2


def test_registrada_cuenta_como_persona_pero_no_como_vinculacion(personas):
    m = obtener_personas_maestras(personas).set_index("id_persona_maestro")
    assert len(m) == 3
    assert m.loc["PER-0001", "total_vinculaciones"] == 2 and m.loc["PER-0002", "total_vinculaciones"] == 0
    r = resumen_vinculaciones_por_persona(personas)
    assert list(r["id_persona_maestro"]) == ["PER-0001"]            # quien solo está registrada no entra a las estadísticas de vinculación


def test_estado_general_registrada_hasta_que_tiene_seguimiento(personas):
    seg = pd.DataFrame([{"id_vinculacion": "V1", "id_persona_maestro": "PER-0002", "nombre_persona": "x", "empresa": "Greenbrier",
                         "sector_empresa": "", "tipo_vacante": "Soldador", "area_oportunidad": "", "estatus": "Vinculado",
                         "fecha_vinculacion": "2026-04-01", "fecha_colocacion": None, "observaciones": "", "responsable": "r"}])
    sin = estado_por_persona(personas, seg.iloc[0:0]).set_index("id_persona_maestro")["estatus_general"]
    assert sin["PER-0002"] == ESTATUS_REGISTRADA and sin["PER-0001"] == "Vinculado"       # el histórico se queda como estaba
    con = estado_por_persona(personas, seg).set_index("id_persona_maestro")["estatus_general"]
    assert con["PER-0002"] == "Vinculado" and con["PER-0003"] == ESTATUS_REGISTRADA        # al tener seguimiento ya está vinculada


# --------------------------------------------------------------------------- colocaciones
@pytest.fixture
def seg():
    def f(i, estatus, fv, fc=None, maestro="PER-0001", empresa="A"):
        return {"id_vinculacion": f"V{i}", "id_persona_maestro": maestro, "nombre_persona": "x", "empresa": empresa, "tipo_vacante": "Soldador",
                "estatus": estatus, "fecha_vinculacion": pd.Timestamp(fv), "fecha_colocacion": pd.Timestamp(fc) if fc else pd.NaT,
                "fecha_actualizacion": pd.Timestamp("2026-10-01") + pd.Timedelta(days=i)}
    return pd.DataFrame([f(1, "Colocado", "2025-01-10", "2025-02-01", empresa="A"), f(2, "Colocado", "2026-03-01", "2026-04-15", empresa="B"),
                         f(3, "Vinculado", "2026-06-01", empresa="C"), f(4, "No vinculado", "2026-06-02", empresa="D"),
                         f(5, "Colocado", "2026-01-01", "2026-01-20", maestro="PER-0002", empresa="E")])


def test_varias_colocaciones_se_numeran_por_fecha_y_la_ultima_es_vigente(seg):
    c = nucleo.colocaciones(seg)
    p1 = c[c["id_persona_maestro"].eq("PER-0001")]
    assert list(p1["empresa"]) == ["A", "B"] and list(p1["n_colocacion"]) == [1, 2] and list(p1["vigente"]) == [False, True]
    assert c[c["id_persona_maestro"].eq("PER-0002")]["total_colocaciones"].iloc[0] == 1
    assert nucleo.colocaciones(seg.iloc[0:0]).empty


@pytest.mark.parametrize("id_,fecha,fragmento", [
    ("V9", date(2026, 7, 1), "ya no existe"), ("V1", date(2026, 7, 1), "ya está registrado"), ("V4", date(2026, 7, 1), "Vinculado"),
    ("V3", None, "fecha"), ("V3", date(2026, 5, 31), "anterior"), ("V3", date(2099, 1, 1), "futura"),
])
def test_validaciones_de_colocacion(seg, id_, fecha, fragmento):
    errores = nucleo.errores_colocacion(seg, id_, fecha, hoy=date(2026, 10, 30))
    assert errores and any(fragmento.lower() in e.lower() for e in errores), errores


def test_no_se_repite_la_fecha_de_otra_colocacion_de_la_misma_persona(seg):
    assert nucleo.errores_colocacion(seg, "V3", date(2026, 4, 15), hoy=date(2026, 10, 30))      # misma fecha que la colocación en B
    assert nucleo.errores_colocacion(seg, "V3", date(2026, 7, 1), hoy=date(2026, 10, 30)) == []


# ------------------------------------------------------------------------ servicio
def _sesion(**mods):
    return sesion_demo(cliente_demo(), admin=False, **({"vinculaciones": ("view", "edit"), "personas": ("view",)} | mods))


def _fila_sql(s, id_):
    return next(f for f in s.cliente.tablas["vinculaciones"] if f["id_vinculacion"] == id_)


def test_registrar_y_quitar_colocacion_con_auditoria(monkeypatch):
    llamadas = []
    monkeypatch.setattr("vinculate.auth.servicio.auditar", lambda accion, detalle="": llamadas.append(accion))
    s = _sesion()
    r = servicio.registrar(s, "VIN-0001", date(2026, 9, 1), "Soldador B")
    assert r.ok and r.guardados == 1, r
    f = _fila_sql(s, "VIN-0001")
    assert f["estatus"] == "Colocado" and str(f["fecha_colocacion"])[:10] == "2026-09-01" and f["tipo_vacante"] == "Soldador B"
    assert "colocacion_registrada" in llamadas
    q = servicio.quitar(s, "VIN-0001")
    assert q.ok, q
    f = _fila_sql(s, "VIN-0001")
    assert f["estatus"] == "Vinculado" and f.get("fecha_colocacion") in (None, "")
    assert "colocacion_quitada" in llamadas


def test_colocacion_exige_permiso_y_no_cambia_nada_si_hay_errores():
    sin = _sesion(vinculaciones=("view",))
    r = servicio.registrar(sin, "VIN-0001", date(2026, 9, 1))
    assert not r.ok and _fila_sql(sin, "VIN-0001")["estatus"] == "Vinculado"
    s = _sesion()
    assert not servicio.registrar(s, "VIN-0001", date(2026, 7, 1)).ok                  # anterior a la vinculación (2026-08-10)
    assert not servicio.registrar(s, "VIN-0003", date(2026, 9, 1)).ok                  # «No vinculado» no se puede colocar
    assert _fila_sql(s, "VIN-0001")["estatus"] == "Vinculado" and _fila_sql(s, "VIN-0003")["estatus"] == "No vinculado"
    assert not servicio.quitar(s, "VIN-0001").ok                                       # no estaba colocada


# ------------------------------------------------------------------------ pantalla
@pytest.mark.apptest
def test_pantalla_colocacion_se_ejecuta_y_solo_con_permiso_de_edicion():
    from streamlit.testing.v1 import AppTest

    from tests.test_paginas import _app
    from vinculate.auth.sesion import CLAVE_SESION

    def correr(s):
        at = AppTest.from_function(_app, default_timeout=60)
        at.session_state[CLAVE_SESION] = s
        at.session_state["_pagina_prueba"] = "vinculaciones"
        at.session_state["vinculaciones_apartado"] = "🏁 Colocación"
        return at.run()

    at = correr(sesion_demo())
    assert not at.exception, [e.value for e in at.exception]
    assert not at.error, [e.value for e in at.error]
    texto = " ".join(m.value for m in at.markdown)
    assert "Registrar una colocación" in texto and "Empresas a las que fue vinculada" in texto
    solo_ver = correr(_sesion(vinculaciones=("view",)))
    assert not solo_ver.exception
    assert "Registrar una colocación" not in " ".join(m.value for m in solo_ver.markdown)


def test_persona_nueva_se_guarda_como_registrada_y_la_asociada_como_vinculada():
    from vinculate.services import guardado

    s = sesion_demo(cliente_demo())
    base = {"nombre": "Nueva Persona Prueba", "sexo": "Mujer", "escolaridad": "Superior", "carrera": "Derecho", "Institución": "UATx",
            "municipio": "Apizaco", "vinculacion": "Atención", "fecha_registro": date(2026, 10, 30), "Año": 2026, "id_persona": ""}
    r = guardado.importar_personas(s, pd.DataFrame([{**base, "id_persona_maestro": "", "estatus_vinculacion": ESTATUS_REGISTRADA}]),
                                   origen="Captura manual", archivo="Captura manual")
    assert r.ok and r.guardados == 1, r
    nueva = next(f for f in s.cliente.tablas["personas"] if f["nombre"] == "Nueva Persona Prueba")
    assert nueva["estatus_vinculacion"] == ESTATUS_REGISTRADA
    assert len(s.cliente.tablas["personas"]) == 61
