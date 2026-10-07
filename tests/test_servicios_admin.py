"""Usuarios, permisos, respaldos, prioridades y búsqueda (cliente falso)."""
import io
import zipfile
from datetime import date, datetime, time, timezone

import pandas as pd
import pytest

from tests.fakes import FakeCliente
from tests.test_guardado import _persona, _sesion
from vinculate.repositories.errores import ErrorDatos, SinPermiso
from vinculate.services import busqueda, guardado, prioridades, respaldos, usuarios


@pytest.fixture
def db():
    c = FakeCliente(pks={"app_profiles": "user_id", "app_permissions": "module_key", "app_priorities": "id"})
    c.tablas["personas"] = [
        {"id_persona": "A-00001-00001", "id_persona_maestro": "PER-0001", "nombre": "Luis Ñandú Pérez", "edad": 30,
         "vinculacion": "Atención", "fecha_registro": "2025-03-01", "anio": 2025, "municipio": "Tlaxcala",
         "correo": "luis@x.com", "telefono": "+52 246 111 2233", "estatus_vinculacion": "Vinculado"},
        {"id_persona": "I-00001-00002", "id_persona_maestro": "PER-0002", "nombre": "=CMD() Maliciosa", "edad": 41,
         "vinculacion": "Inserción Laboral", "fecha_registro": "2025-04-01", "anio": 2025, "municipio": "Apizaco",
         "estatus_vinculacion": "Vinculado"},
    ]
    return c


# ----------------------------------------------------------------- usuarios
def test_usuarios_sin_permiso(db):
    s = _sesion(db, personas=("view",))
    with pytest.raises(SinPermiso):
        usuarios.crear_colaborador(s, "a@b.com", "12345678", "A")
    with pytest.raises(SinPermiso):
        usuarios.listar_perfiles(s)


def test_normalizar_permisos_exige_ver():
    out = usuarios.normalizar_permisos([
        {"module_key": "personas", "can_view": False, "can_create": True, "can_edit": True},
        {"module_key": "vacantes", "can_view": True, "can_create": True},
        {"module_key": "inventado", "can_view": True},
    ])
    assert [r["module_key"] for r in out] == ["personas", "vacantes"]
    assert out[0]["can_create"] is False and out[0]["can_edit"] is False
    assert out[1]["can_create"] is True and out[1]["can_delete"] is False


def test_guardar_permisos_verifica_lo_persistido(db):
    s = _sesion(db, usuarios=("view", "edit"))
    # El RPC "responde bien" pero no persiste nada → debe detectarse.
    with pytest.raises(ErrorDatos):
        usuarios.guardar_permisos(s, "uid-9", [{"module_key": "personas", "can_view": True}])
    # Ahora sí persiste.
    def persistir(params):
        db.tablas["app_permissions"] = [{"user_id": params["p_user_id"], **p} for p in params["p_permissions"]]
    db.rpc_respuestas["admin_replace_user_permissions"] = persistir
    out = usuarios.guardar_permisos(s, "uid-9", [{"module_key": "personas", "can_view": True, "can_edit": True}])
    assert out[0]["can_edit"] is True


def test_no_puede_darse_de_baja_a_si_mismo(db):
    s = _sesion(db, usuarios=("view", "delete"))
    with pytest.raises(ValueError):
        usuarios.eliminar_cuenta(s, s.user_id)


def test_actualizar_cuenta_valida(db):
    s = _sesion(db, usuarios=("view", "edit"))
    with pytest.raises(ValueError):
        usuarios.actualizar_cuenta(s, "u", "no-es-correo", "N", "collaborator", "active")
    with pytest.raises(ValueError):
        usuarios.actualizar_cuenta(s, "u", "a@b.com", "N", "superadmin", "active")
    usuarios.actualizar_cuenta(s, "u", "A@B.com", "N", "collaborator", "active")
    assert db.rpcs[-1][1]["p_email"] == "a@b.com"


# ---------------------------------------------------------------- respaldos
def test_exportar_df_requiere_permiso_y_neutraliza_formulas(db):
    df = pd.DataFrame({"nombre": ["=CMD()", "+52 246 111 2233", "@x", "Ana", "-5"], "n": [1, 2, 3, 4, 5]})
    s = _sesion(db, personas=("view",))
    with pytest.raises(SinPermiso):
        respaldos.exportar_df(s, "personas", df, "personas")
    s2 = _sesion(db, personas=("view", "export"))
    datos, nombre, mime = respaldos.exportar_df(s2, "personas", df, "personas", "csv")
    texto = datos.decode("utf-8-sig")
    assert "'=CMD()" in texto and "'@x" in texto
    assert "+52 246 111 2233" in texto and "'+52" not in texto and "'-5" not in texto
    assert nombre.endswith(".csv") and mime == "text/csv"
    xlsx, _, _ = respaldos.exportar_df(s2, "personas", df, "personas", "xlsx")
    assert pd.read_excel(io.BytesIO(xlsx)).shape == (5, 2)


def test_respaldo_zip(db):
    s = _sesion(db, personas=("view",), respaldos=("view", "export"))
    datos, nombre, conteos = respaldos.respaldo_zip(s)
    assert conteos == {"personas": 2}
    z = zipfile.ZipFile(io.BytesIO(datos))
    assert set(z.namelist()) == {"personas.csv", "LEEME.txt"}
    assert "datos personales" in z.read("LEEME.txt").decode()
    s2 = _sesion(db, personas=("view",))
    with pytest.raises(SinPermiso):
        respaldos.respaldo_zip(s2)


# -------------------------------------------------------------- prioridades
def test_prioridades_vencidas_y_orden(db):
    ahora = datetime.now(timezone.utc)
    db.tablas["app_priorities"] = [
        {"id": 1, "title": "futura", "priority_level": "urgente", "active": True,
         "reminder_at": (ahora.replace(year=ahora.year + 1)).isoformat()},
        {"id": 2, "title": "normal vencida", "priority_level": "normal", "active": True, "reminder_at": "2020-01-01T00:00:00+00:00"},
        {"id": 3, "title": "urgente sin fecha", "priority_level": "urgente", "active": True, "reminder_at": None},
        {"id": 4, "title": "cerrada", "priority_level": "urgente", "active": False, "reminder_at": None},
    ]
    s = _sesion(db, prioridades=("view",))
    assert [p["title"] for p in prioridades.pendientes(s)] == ["urgente sin fecha", "normal vencida"]


def test_prioridad_crea_en_hora_de_mexico(db):
    s = _sesion(db, prioridades=("view", "create"))
    prioridades.crear(s, "otro", "", "Llamar a empresa", "", "alta", date(2026, 10, 7), time(9, 0), 30)
    fila = db.tablas["app_priorities"][0]
    assert fila["reminder_at"].startswith("2026-10-07T15:00:00")  # CDMX = UTC-6 (sin horario de verano)
    assert fila["entity_id"] == "sin-id" and fila["created_by"] == s.user_id


def test_toast_respeta_repeticion(db):
    db.tablas["app_priorities"] = [{"id": 1, "title": "x", "priority_level": "alta", "active": True,
                                    "reminder_at": None, "repeat_minutes": 60}]
    s = _sesion(db, prioridades=("view",))
    assert len(prioridades.para_toast(s)) == 1
    assert len(prioridades.para_toast(s)) == 0  # ya se mostró hace menos de 60 min


# ----------------------------------------------------------------- búsqueda
def test_busqueda_sin_acentos_y_por_modulo(db):
    s = _sesion(db, personas=("view",))
    r = busqueda.buscar(s, "nandu")
    assert list(r) == ["personas"] and len(r["personas"]) == 1
    assert r["personas"].iloc[0]["id_persona_maestro"] == "PER-0001"
    assert busqueda.buscar(s, "luis 246")["personas"].shape[0] == 1
    assert busqueda.buscar(s, "luis inexistente")["personas"].empty
    assert busqueda.buscar(s, "a") == {}  # muy corto


def test_busqueda_no_ve_lo_que_no_puede(db):
    s = _sesion(db, vacantes=("view",))
    r = busqueda.buscar(s, "luis")
    assert "personas" not in r
