"""Pruebas de seguridad de las migraciones SQL contra un PostgreSQL REAL.

No tocan Supabase: construyen una base local con una emulación mínima de
Supabase (tests/sql/00_supabase_stub.sql), el esquema base y datos sintéticos.

Cómo ejecutarlas (necesitas un PostgreSQL 14+ local con un usuario que pueda
crear bases de datos):

    export VINCULATE_TEST_PG="host=localhost port=5432 user=postgres"
    pytest tests/test_sql_migraciones.py -v

Sin la variable, las pruebas se omiten (no fallan).
"""
from __future__ import annotations

import json
import os
import re
import uuid
from contextlib import contextmanager
from pathlib import Path

import pytest

psycopg = pytest.importorskip("psycopg")

CONN_INFO = os.environ.get("VINCULATE_TEST_PG", "").strip()
pytestmark = pytest.mark.skipif(not CONN_INFO, reason="Define VINCULATE_TEST_PG para correr pruebas SQL")

ROOT = Path(__file__).resolve().parents[1]
SQL_DIR = ROOT / "tests" / "sql"
MIG = ROOT / "supabase" / "migrations"
SCHEMA = ROOT / "supabase" / "schema" / "00_esquema_base.sql"

ADMIN = "a0000000-0000-0000-0000-000000000001"
DELEG = "a0000000-0000-0000-0000-000000000002"
LECTOR = "a0000000-0000-0000-0000-000000000003"
CAPTURA = "a0000000-0000-0000-0000-000000000004"
SOLOINICIO = "a0000000-0000-0000-0000-000000000005"
BAJA = "a0000000-0000-0000-0000-000000000006"


def _connect(dbname="postgres", autocommit=True):
    return psycopg.connect(CONN_INFO, dbname=dbname, autocommit=autocommit)


def _run_file(dbname, path: Path):
    with _connect(dbname) as conn:
        conn.execute(path.read_text(encoding="utf-8"))


def _new_db(prefix: str) -> str:
    name = f"vt_{prefix}_{uuid.uuid4().hex[:8]}"
    with _connect() as conn:
        conn.execute(f'create database "{name}"')
    return name


def _drop_db(name: str):
    with _connect() as conn:
        conn.execute(f'drop database if exists "{name}" with (force)')


def _build(prefix: str, migrations=()) -> str:
    db = _new_db(prefix)
    _run_file(db, SQL_DIR / "00_supabase_stub.sql")
    _run_file(db, SCHEMA)
    _run_file(db, SQL_DIR / "01_seed_sintetico.sql")
    for m in migrations:
        _run_file(db, MIG / m)
    return db


@contextmanager
def as_user(db, uid=None, role="authenticated", headers=None):
    """Simula una petición de Supabase (JWT + encabezados) y revierte al salir."""
    conn = _connect(db, autocommit=False)
    try:
        cur = conn.cursor()
        cur.execute(f"set local role {role}")
        claims = {"role": role}
        if uid:
            claims["sub"] = uid
        cur.execute("select set_config('request.jwt.claims', %s, true)", (json.dumps(claims),))
        if headers:
            cur.execute("select set_config('request.headers', %s, true)", (json.dumps(headers),))
        yield cur
    finally:
        conn.rollback()
        conn.close()


def scalar(db, sql, params=None):
    with _connect(db) as conn:
        row = conn.execute(sql, params).fetchone()
        return row[0] if row else None


@pytest.fixture(scope="module")
def db_base():
    db = _build("base")
    yield db
    _drop_db(db)


@pytest.fixture(scope="module")
def db_v1():
    db = _build("v1", ["V001_cierre_brechas.sql"])
    yield db
    _drop_db(db)


@pytest.fixture(scope="module")
def db_v123():
    db = _build("v123", ["V001_cierre_brechas.sql", "V002_rls_por_permiso.sql", "V003_auditoria_servidor.sql"])
    yield db
    _drop_db(db)


# ---------------------------------------------------------------------------
# Estado ANTERIOR: documenta que las brechas existían (si esto fallara, la
# migración V001 ya no tendría sentido).
# ---------------------------------------------------------------------------
class TestBaseVulnerable:
    def test_anon_lee_personas(self, db_base):
        with as_user(db_base, role="anon") as cur:
            cur.execute("select count(*) from public.personas")
            assert cur.fetchone()[0] == 3

    def test_delegado_se_hace_admin(self, db_base):
        with as_user(db_base, DELEG) as cur:
            cur.execute("update public.app_profiles set role='admin' where user_id=%s", (DELEG,))
            assert cur.rowcount == 1

    def test_delegado_reinicia_password_de_admin(self, db_base):
        with as_user(db_base, DELEG) as cur:
            cur.execute("select public.admin_finalize_collaborator('admin@prueba.test','Nueva-Clave-9','x')")
            assert cur.fetchone()[0] == uuid.UUID(ADMIN)

    def test_lector_borra_personas(self, db_base):
        with as_user(db_base, LECTOR) as cur:
            cur.execute("delete from public.personas where id_persona='I-00001-00001'")
            assert cur.rowcount == 1


# ---------------------------------------------------------------------------
# V001
# ---------------------------------------------------------------------------
def _err(cur, sql, params=None):
    try:
        cur.execute(sql, params)
    except psycopg.Error as exc:
        return str(exc)
    return None


class TestV001:
    def test_anon_sin_acceso(self, db_v1):
        with as_user(db_v1, role="anon") as cur:
            msg = _err(cur, "select count(*) from public.personas")
            assert msg and "permission denied" in msg

    def test_anon_sin_rpc(self, db_v1):
        with as_user(db_v1, role="anon") as cur:
            msg = _err(cur, "select public.admin_set_user_password(%s,'12345678')", (LECTOR,))
            assert msg and "permission denied" in msg

    def test_sin_politicas_anon(self, db_v1):
        assert scalar(db_v1, "select count(*) from pg_policies where 'anon' = any(roles)") == 0

    def test_login_normal_sigue_funcionando(self, db_v1):
        with as_user(db_v1, LECTOR) as cur:
            cur.execute("select role,status from public.app_profiles where user_id=%s", (LECTOR,))
            assert cur.fetchone() == ("collaborator", "active")
            cur.execute("select module_key from public.app_permissions where user_id=%s", (LECTOR,))
            assert {r[0] for r in cur.fetchall()} == {"inicio", "personas"}

    def test_delegado_no_se_hace_admin_directo(self, db_v1):
        with as_user(db_v1, DELEG) as cur:
            cur.execute("update public.app_profiles set role='admin' where user_id=%s", (DELEG,))
            assert cur.rowcount == 0  # RLS lo filtra

    def test_delegado_no_inserta_permisos_directo(self, db_v1):
        with as_user(db_v1, DELEG) as cur:
            msg = _err(cur, "insert into public.app_permissions(user_id,module_key,can_view) values (%s,'ridet',true)", (DELEG,))
            assert msg and "row-level security" in msg

    def test_delegado_no_reinicia_password_de_admin(self, db_v1):
        with as_user(db_v1, DELEG) as cur:
            msg = _err(cur, "select public.admin_finalize_collaborator('admin@prueba.test','Nueva-Clave-9','x')")
            assert msg and "administrador" in msg

    def test_delegado_no_cambia_password_de_admin(self, db_v1):
        with as_user(db_v1, DELEG) as cur:
            msg = _err(cur, "select public.admin_set_user_password(%s,'Nueva-Clave-9')", (ADMIN,))
            assert msg and "administrador" in msg

    def test_delegado_si_cambia_password_de_colaborador(self, db_v1):
        with as_user(db_v1, DELEG) as cur:
            assert _err(cur, "select public.admin_set_user_password(%s,'Nueva-Clave-9')", (LECTOR,)) is None

    def test_delegado_no_da_rol_admin(self, db_v1):
        with as_user(db_v1, DELEG) as cur:
            msg = _err(cur, "select public.admin_update_user_account(%s,'lector@prueba.test','Lector','admin','active')", (LECTOR,))
            assert msg and "rol de administrador" in msg

    def test_delegado_no_modifica_su_cuenta(self, db_v1):
        with as_user(db_v1, DELEG) as cur:
            msg = _err(cur, "select public.admin_update_user_account(%s,'deleg@prueba.test','D','collaborator','active')", (DELEG,))
            assert msg and "propia cuenta" in msg

    def test_delegado_no_toca_cuenta_admin(self, db_v1):
        with as_user(db_v1, DELEG) as cur:
            msg = _err(cur, "select public.admin_update_user_account(%s,'admin@prueba.test','A','collaborator','disabled')", (ADMIN,))
            assert msg and "administrador" in msg

    def test_delegado_no_borra_admin(self, db_v1):
        with as_user(db_v1, DELEG) as cur:
            msg = _err(cur, "select public.admin_delete_user_account(%s)", (ADMIN,))
            assert msg and "administrador" in msg

    def test_delegado_no_otorga_lo_que_no_tiene(self, db_v1):
        perms = json.dumps([{"module_key": "personas", "can_view": True, "can_delete": True}])
        with as_user(db_v1, DELEG) as cur:
            msg = _err(cur, "select public.admin_replace_user_permissions(%s,%s::jsonb)", (LECTOR, perms))
            assert msg and "no tienes" in msg

    def test_delegado_otorga_lo_que_si_tiene(self, db_v1):
        perms = json.dumps([{"module_key": "personas", "can_view": True}, {"module_key": "inicio", "can_view": True}])
        with as_user(db_v1, DELEG) as cur:
            assert _err(cur, "select public.admin_replace_user_permissions(%s,%s::jsonb)", (LECTOR, perms)) is None

    def test_delegado_no_edita_sus_permisos(self, db_v1):
        perms = json.dumps([{"module_key": "personas", "can_view": True}])
        with as_user(db_v1, DELEG) as cur:
            msg = _err(cur, "select public.admin_replace_user_permissions(%s,%s::jsonb)", (DELEG, perms))
            assert msg and "propios permisos" in msg

    def test_admin_conserva_todas_sus_capacidades(self, db_v1):
        perms = json.dumps([{"module_key": "personas", "can_view": True, "can_edit": True, "can_delete": True}])
        with as_user(db_v1, ADMIN) as cur:
            assert _err(cur, "select public.admin_replace_user_permissions(%s,%s::jsonb)", (CAPTURA, perms)) is None
            cur.execute("savepoint s")
            assert _err(cur, "select public.admin_update_user_account(%s,'lector@prueba.test','Lector','admin','active')", (LECTOR,)) is None
            cur.execute("select role from public.app_profiles where user_id=%s", (LECTOR,))
            assert cur.fetchone()[0] == "admin"

    def test_ultimo_admin_protegido(self, db_v1):
        with as_user(db_v1, ADMIN) as cur:
            msg = _err(cur, "select public.admin_update_user_account(%s,'admin@prueba.test','A','collaborator','active')", (ADMIN,))
            assert msg  # ya sea por "último administrador" o por regla de cuenta propia

    def test_borrar_cuenta_conserva_auditoria(self, db_v1):
        with as_user(db_v1, ADMIN) as cur:
            cur.execute("insert into public.app_audit_log(user_id,email,action) values (%s,'captura@prueba.test','probe')", (ADMIN,))
            cur.execute("insert into public.app_audit_log(user_id,email,action) select %s,'x','probe2'", (ADMIN,))
        # usar la cuenta CAPTURA: registrar auditoría como ella y luego borrarla como admin
        conn = _connect(db_v1, autocommit=False)
        try:
            cur = conn.cursor()
            cur.execute("insert into public.app_audit_log(user_id,email,action) values (%s,'captura@prueba.test','probe-captura')", (CAPTURA,))
            cur.execute("set local role authenticated")
            cur.execute("select set_config('request.jwt.claims', %s, true)", (json.dumps({"sub": ADMIN, "role": "authenticated"}),))
            cur.execute("select public.admin_delete_user_account(%s)", (CAPTURA,))
            cur.execute("reset role")
            cur.execute("select user_id, email from public.app_audit_log where action='probe-captura'")
            row = cur.fetchone()
            assert row == (None, "captura@prueba.test")
        finally:
            conn.rollback()
            conn.close()

    def test_equipo_no_se_autoriza_solo(self, db_v1):
        with as_user(db_v1, CAPTURA) as cur:
            msg = _err(cur, "insert into public.app_devices(user_id,device_id,authorized) values (%s,'nuevo-1',true)", (CAPTURA,))
            assert msg and "row-level security" in msg
            cur.execute("rollback")
        with as_user(db_v1, CAPTURA) as cur:
            assert _err(cur, "insert into public.app_devices(user_id,device_id,authorized) values (%s,'nuevo-1',false)", (CAPTURA,)) is None

    def test_equipo_no_cambia_identidad(self, db_v1):
        with as_user(db_v1, LECTOR) as cur:
            msg = _err(cur, "update public.app_devices set device_id='otro' where device_id='dev-lector-ok'")
            assert msg and "identificador" in msg

    def test_equipo_autorizado_actualiza_last_seen(self, db_v1):
        with as_user(db_v1, LECTOR) as cur:
            cur.execute("update public.app_devices set last_seen=now(), hostname='h' where device_id='dev-lector-ok'")
            assert cur.rowcount == 1

    def test_delegado_con_dispositivos_edit_autoriza(self, db_v1):
        with as_user(db_v1, DELEG) as cur:
            cur.execute("update public.app_devices set authorized=true where device_id='dev-lector-pend'")
            assert cur.rowcount == 1

    def test_lector_no_autoriza_equipos(self, db_v1):
        with as_user(db_v1, LECTOR) as cur:
            # su equipo pendiente no es actualizable por política (authorized=false)
            cur.execute("update public.app_devices set authorized=true where device_id='dev-lector-pend'")
            assert cur.rowcount == 0

    def test_sql_editor_no_se_bloquea(self, db_v1):
        # Mantenimiento directo (sin JWT): la guardia no estorba
        with _connect(db_v1) as conn:
            conn.execute("update public.app_devices set authorized=true where device_id='dev-lector-pend'")


class TestV001Rollback:
    def test_rollback_restaura_estado_anterior(self, db_base):
        db = _build("v1rb", ["V001_cierre_brechas.sql", "V001_rollback.sql"])
        try:
            q_pol = ("select tablename, policyname, cmd, roles::text, qual, with_check from pg_policies "
                     "where schemaname='public' order by tablename, policyname")
            q_fn = ("select proname, pg_get_functiondef(oid) from pg_proc "
                    "where pronamespace='public'::regnamespace and proname like 'admin\\_%' order by 1")
            with _connect(db_base) as a, _connect(db) as b:
                assert a.execute(q_pol).fetchall() == b.execute(q_pol).fetchall()
                assert a.execute(q_fn).fetchall() == b.execute(q_fn).fetchall()
            with as_user(db, role="anon") as cur:
                cur.execute("select count(*) from public.personas")
                assert cur.fetchone()[0] == 3
        finally:
            _drop_db(db)


# ---------------------------------------------------------------------------
# V002 — RLS por permiso
# ---------------------------------------------------------------------------
NUEVA = ("insert into public.personas(id_persona,id_persona_maestro,nombre) "
         "values ('I-99999-99999','PER-9999','PRUEBA NUEVA')")


class TestV002:
    def test_sin_politicas_for_all(self, db_v123):
        assert scalar(db_v123, "select count(*) from pg_policies where schemaname='public' and cmd='ALL' "
                               "and tablename in ('personas','vacantes','vinculaciones','historial_cargas')") == 0

    def test_lector_lee_pero_no_escribe(self, db_v123):
        with as_user(db_v123, LECTOR) as cur:
            cur.execute("select count(*) from public.personas")
            assert cur.fetchone()[0] == 3
            assert "row-level security" in (_err(cur, NUEVA) or "")
            cur.execute("rollback")
        with as_user(db_v123, LECTOR) as cur:
            cur.execute("update public.personas set nombre='X' where id_persona='I-00001-00001'")
            assert cur.rowcount == 0
            cur.execute("delete from public.personas where id_persona='I-00001-00001'")
            assert cur.rowcount == 0

    def test_captura_crea_pero_no_edita_ni_borra(self, db_v123):
        with as_user(db_v123, CAPTURA) as cur:
            assert _err(cur, NUEVA) is None
            cur.execute("update public.personas set nombre='X' where id_persona='I-00001-00001'")
            assert cur.rowcount == 0
            cur.execute("delete from public.personas where id_persona='I-00001-00001'")
            assert cur.rowcount == 0

    def test_upsert_masivo_antiguo_falla_para_captura(self, db_v123):
        # El upsert (insert … on conflict do update) necesita INSERT *y* UPDATE: por eso la v2 guarda dirigido
        sql = ("insert into public.personas(id_persona,id_persona_maestro,nombre) values ('I-00001-00001','PER-0001','CAMBIADO') "
               "on conflict (id_persona) do update set nombre=excluded.nombre")
        with as_user(db_v123, CAPTURA) as cur:
            assert _err(cur, sql)

    def test_sin_permiso_no_ve_nada(self, db_v123):
        with as_user(db_v123, SOLOINICIO) as cur:
            cur.execute("select count(*) from public.personas")
            assert cur.fetchone()[0] == 0
            cur.execute("select count(*) from public.vacantes")
            assert cur.fetchone()[0] == 0

    def test_usuario_dado_de_baja_no_ve_nada(self, db_v123):
        with as_user(db_v123, BAJA) as cur:
            cur.execute("select count(*) from public.personas")
            assert cur.fetchone()[0] == 0
            assert "row-level security" in (_err(cur, NUEVA) or "")

    def test_admin_todo(self, db_v123):
        with as_user(db_v123, ADMIN) as cur:
            assert _err(cur, NUEVA) is None
            cur.execute("update public.personas set nombre='X' where id_persona='I-99999-99999'")
            assert cur.rowcount == 1
            cur.execute("delete from public.personas where id_persona='I-99999-99999'")
            assert cur.rowcount == 1

    def test_catalogos_lectura_activos_escritura_con_permiso(self, db_v123):
        with as_user(db_v123, LECTOR) as cur:
            cur.execute("select count(*) from public.catalogo_carreras")
            assert cur.fetchone()[0] >= 0
            assert "row-level security" in (_err(cur, "insert into public.catalogo_carreras(nombre) values ('Nueva')") or "")

    def test_historial_requiere_permiso_de_captura(self, db_v123):
        ins = "insert into public.historial_cargas(fecha_hora,usuario,base) values ('2026-01-01','u','personas')"
        with as_user(db_v123, LECTOR) as cur:
            assert "row-level security" in (_err(cur, ins) or "")
        with as_user(db_v123, CAPTURA) as cur:
            assert _err(cur, ins) is None

    def test_compuerta_de_equipo_apagada_por_defecto(self, db_v123):
        assert scalar(db_v123, "select value from public.app_settings where key='enforce_device_rls'") == "false"

    def test_compuerta_de_equipo_encendida(self, db_v123):
        with _connect(db_v123) as conn:
            conn.execute("update public.app_settings set value='true' where key='enforce_device_rls'")
        try:
            with as_user(db_v123, LECTOR, headers={"x-device-id": "dev-lector-ok"}) as cur:
                cur.execute("select count(*) from public.personas")
                assert cur.fetchone()[0] == 3
            with as_user(db_v123, LECTOR, headers={"x-device-id": "dev-lector-pend"}) as cur:
                cur.execute("select count(*) from public.personas")
                assert cur.fetchone()[0] == 0
            with as_user(db_v123, LECTOR) as cur:   # sin encabezado
                cur.execute("select count(*) from public.personas")
                assert cur.fetchone()[0] == 0
            with as_user(db_v123, ADMIN) as cur:    # el admin no queda fuera
                cur.execute("select count(*) from public.personas")
                assert cur.fetchone()[0] == 3
        finally:
            with _connect(db_v123) as conn:
                conn.execute("update public.app_settings set value='false' where key='enforce_device_rls'")

    def test_solo_admin_cambia_app_settings(self, db_v123):
        with as_user(db_v123, DELEG) as cur:
            cur.execute("update public.app_settings set value='true' where key='enforce_device_rls'")
            assert cur.rowcount == 0
        with as_user(db_v123, ADMIN) as cur:
            cur.execute("update public.app_settings set value='false' where key='enforce_device_rls'")
            assert cur.rowcount == 1

    def test_rollback_v3_v2(self):
        db = _build("v2rb", ["V001_cierre_brechas.sql", "V002_rls_por_permiso.sql", "V003_auditoria_servidor.sql",
                             "V003_rollback.sql", "V002_rollback.sql"])
        try:
            assert scalar(db, "select count(*) from pg_policies where policyname='personas_auth_all'") == 1
            assert scalar(db, "select to_regclass('public.app_settings')::text") is None
            assert scalar(db, "select count(*) from public.personas") == 3
        finally:
            _drop_db(db)


# ---------------------------------------------------------------------------
# V003 — auditoría en servidor
# ---------------------------------------------------------------------------
class TestV003:
    def test_insert_update_delete_quedan_auditados(self, db_v123):
        with as_user(db_v123, ADMIN, headers={"x-device-id": "dev-admin"}) as cur:
            cur.execute(NUEVA)
            cur.execute("update public.personas set nombre='OTRO', municipio='APIZACO' where id_persona='I-99999-99999'")
            cur.execute("delete from public.personas where id_persona='I-99999-99999'")
            cur.execute("reset role")
            cur.execute("select action, detail, email, device_id from public.app_audit_log where detail like 'personas I-99999-99999%' order by id")
            rows = cur.fetchall()
        assert [r[0] for r in rows] == ["srv_insert", "srv_update", "srv_delete"]
        assert "columnas: municipio, nombre" in rows[1][1]
        assert "OTRO" not in rows[1][1]           # no se copian valores
        assert rows[0][2] == "admin@prueba.test" and rows[0][3] == "dev-admin"

    def test_update_sin_cambios_no_audita(self, db_v123):
        with as_user(db_v123, ADMIN) as cur:
            cur.execute("update public.personas set nombre=nombre where id_persona='I-00001-00001'")
            cur.execute("reset role")
            cur.execute("select count(*) from public.app_audit_log where detail like 'personas I-00001-00001%'")
            assert cur.fetchone()[0] == 0

    def test_actualizado_en_avanza(self, db_v123):
        before = scalar(db_v123, "select actualizado_en from public.vacantes where id_vacante='VAC-0001'")
        with as_user(db_v123, ADMIN) as cur:
            cur.execute("update public.vacantes set estado='Inactiva' where id_vacante='VAC-0001'")
            cur.execute("reset role")
            cur.execute("select actualizado_en from public.vacantes where id_vacante='VAC-0001'")
            after = cur.fetchone()[0]
        assert after > before

    def test_usuario_no_puede_borrar_auditoria(self, db_v123):
        # Hay privilegio de tabla (Supabase otorga ALL por defecto) pero ninguna política
        # DELETE: RLS lo deniega en silencio, ni siquiera un administrador borra auditoría.
        with as_user(db_v123, ADMIN) as cur:
            cur.execute("insert into public.app_audit_log(user_id,email,action) values (%s,'admin@prueba.test','probe')", (ADMIN,))
            cur.execute("delete from public.app_audit_log")
            assert cur.rowcount == 0
            cur.execute("update public.app_audit_log set action='alterada'")
            assert cur.rowcount == 0

    def test_v003_exige_v002(self):
        db = _build("v3solo", ["V001_cierre_brechas.sql"])
        try:
            with pytest.raises(psycopg.Error):
                _run_file(db, MIG / "V003_auditoria_servidor.sql")
        finally:
            _drop_db(db)


# ---------------------------------------------------------------------------
# V004 · V005 · V007 · V008 — columnas nuevas, origen del dato, vigencia y disponibilidad
# ---------------------------------------------------------------------------
MIGS_1A3 = ["V001_cierre_brechas.sql", "V002_rls_por_permiso.sql", "V003_auditoria_servidor.sql"]
MIGS_4A8 = ["V004_ubicacion_empresas.sql", "V005_origen_del_dato.sql", "V007_vigencia_vacantes.sql", "V008_disponibilidad_personas.sql"]
EDITOR = "a0000000-0000-0000-0000-0000000000e1"


def _err(cur, sql, params=None):
    """Ejecuta y devuelve el mensaje de error (o None). Usa un savepoint para no abortar la transacción."""
    cur.execute("savepoint sp")
    try:
        cur.execute(sql, params)
        cur.execute("release savepoint sp")
        return None
    except psycopg.Error as exc:
        cur.execute("rollback to savepoint sp")
        return str(exc)


@pytest.fixture(scope="module")
def db_todo():
    db = _build("todo", MIGS_1A3 + MIGS_4A8)
    with _connect(db) as conn:  # un editor de personas (el seed no trae uno)
        conn.execute("insert into auth.users(id,email,encrypted_password,email_confirmed_at) values (%s,'editor@prueba.test','x',now())", (EDITOR,))
        conn.execute("insert into public.app_profiles(user_id,email,display_name,role,status) values (%s,'editor@prueba.test','Editor','collaborator','active')", (EDITOR,))
        conn.execute("insert into public.app_permissions(user_id,module_key,can_view,can_create,can_edit,can_delete,can_export) "
                     "values (%s,'personas',true,true,true,false,false),(%s,'vacantes',true,true,true,false,false)", (EDITOR, EDITOR))
    yield db
    _drop_db(db)


class TestV004:
    def test_columnas_nuevas_y_datos_intactos(self, db_todo):
        assert scalar(db_todo, "select count(*) from information_schema.columns where table_schema='public' and table_name='catalogo_empresas' "
                               "and column_name in ('municipio','cve_mun','direccion','codigo_postal','latitud','longitud','ubicacion_fuente','ubicacion_actualizada')") == 8
        assert scalar(db_todo, "select count(*) from information_schema.columns where table_schema='public' and table_name='vacantes' and column_name='municipio_excepcion'") == 1
        assert scalar(db_todo, "select count(*) from public.personas") == 3
        assert scalar(db_todo, "select count(*) from public.vacantes where municipio_excepcion is not null") == 0

    def test_restricciones_de_ubicacion(self, db_todo):
        with as_user(db_todo, ADMIN) as cur:
            ins = "insert into public.catalogo_empresas(nombre,municipio,{c}) values ('E-{n}','APIZACO',%s)"
            assert _err(cur, ins.format(c="codigo_postal", n=1), ("123",)) is not None          # CP de 3 dígitos
            assert _err(cur, ins.format(c="codigo_postal", n=2), ("90000",)) is None            # CP válido
            assert _err(cur, "insert into public.catalogo_empresas(nombre,latitud) values ('E-3', 19.3)") is not None   # solo una coordenada
            assert _err(cur, "insert into public.catalogo_empresas(nombre,latitud,longitud) values ('E-4', 60, -98)") is not None   # fuera de México
            assert _err(cur, "insert into public.catalogo_empresas(nombre,latitud,longitud) values ('E-5', 19.3, -98.2)") is None
            assert _err(cur, "insert into public.catalogo_empresas(nombre,ubicacion_fuente) values ('E-6','inventada')") is not None
            assert _err(cur, "insert into public.catalogo_empresas(nombre,ubicacion_fuente) values ('E-7','manual')") is None

    def test_rls_de_catalogo_empresas_no_cambia(self, db_todo):
        with as_user(db_todo, LECTOR) as cur:   # lector: ve el catálogo, no escribe
            assert _err(cur, "insert into public.catalogo_empresas(nombre,municipio) values ('X','APIZACO')") is not None
        with as_user(db_todo, EDITOR) as cur:   # vacantes·editar actualiza la ubicación
            cur.execute("insert into public.catalogo_empresas(nombre) values ('EMPRESA PRUEBA SA') on conflict do nothing")
            cur.execute("update public.catalogo_empresas set municipio='APIZACO', ubicacion_fuente='manual' where nombre='EMPRESA PRUEBA SA'")
            assert cur.rowcount == 1

    def test_cve_mun_exige_tres_digitos(self, db_todo):
        with as_user(db_todo, ADMIN) as cur:
            assert _err(cur, "insert into public.catalogo_municipios_tlaxcala(nombre,cve_mun) values ('PRUEBA UNO','5')") is not None
            assert _err(cur, "insert into public.catalogo_municipios_tlaxcala(nombre,cve_mun) values ('PRUEBA DOS','005')") is None

    def test_rollback_v4(self):
        db = _build("v4rb", MIGS_1A3 + ["V004_ubicacion_empresas.sql", "V004_rollback.sql"])
        try:
            assert scalar(db, "select count(*) from information_schema.columns where table_schema='public' and table_name='catalogo_empresas' and column_name='municipio'") == 0
            assert scalar(db, "select count(*) from public.vacantes") == 2
        finally:
            _drop_db(db)

    def test_v4_se_puede_aplicar_dos_veces(self, db_todo):
        _run_file(db_todo, MIG / "V004_ubicacion_empresas.sql")   # idempotente: no falla ni duplica

    def test_sql_de_claves_inegi_generado_por_el_script(self, tmp_path):
        """El SQL que escribe scripts/preparar_geometria.py rellena cve_mun solo donde está vacío."""
        import sys
        sys.path.insert(0, str(ROOT / "scripts"))
        sys.path.insert(0, str(ROOT))
        from preparar_geometria import sql_cve_mun
        from vinculate.core.mapa import validar_geojson
        from vinculate.core.ubicacion import MUNICIPIOS_TLAXCALA
        feats = [{"type": "Feature", "properties": {"CVE_ENT": "29", "CVE_MUN": f"{i + 1:03d}", "NOMGEO": n.title()},
                  "geometry": {"type": "Polygon", "coordinates": [[[i, 0], [i + 1, 0], [i + 1, 1], [i, 0]]]}}
                 for i, n in enumerate(MUNICIPIOS_TLAXCALA)]
        res = validar_geojson({"type": "FeatureCollection", "features": feats})
        assert res.ok
        sql = sql_cve_mun(res.geojson)
        archivo = tmp_path / "cve.sql"
        archivo.write_text(sql, encoding="utf-8")
        db = _build("cvemun", MIGS_1A3 + ["V004_ubicacion_empresas.sql"])
        try:
            with _connect(db) as con:
                for n in MUNICIPIOS_TLAXCALA:
                    con.execute("insert into public.catalogo_municipios_tlaxcala(nombre) values (%s) on conflict do nothing", (n,))
                con.execute("update public.catalogo_municipios_tlaxcala set cve_mun='999' where nombre=%s", (MUNICIPIOS_TLAXCALA[0],))
            _run_file(db, archivo)
            assert scalar(db, "select count(*) from public.catalogo_municipios_tlaxcala where cve_mun is not null") == 60
            assert scalar(db, "select cve_mun from public.catalogo_municipios_tlaxcala where nombre=%s", (MUNICIPIOS_TLAXCALA[0],)) == "999"   # no pisa lo ya capturado
            assert scalar(db, "select cve_mun from public.catalogo_municipios_tlaxcala where nombre=%s", (MUNICIPIOS_TLAXCALA[1],)) == "002"
        finally:
            _drop_db(db)


class TestV005:
    def test_migracion_real_no_cambia_datos_y_deja_una_fila_de_auditoria(self, db_todo):
        # Los IDs reales no existen en la base sintética: no etiqueta nada, pero la migración corre completa.
        assert scalar(db_todo, "select count(*) from public.personas where anio_fuente <> 'registrado' or institucion_fuente <> 'registrado'") == 0
        assert scalar(db_todo, "select count(*) from public.app_audit_log where action='migration_V005'") == 1
        assert scalar(db_todo, "select count(*) from public.app_audit_log where action='srv_update'") == 0   # sin ruido por fila

    def test_valores_por_defecto_y_restricciones(self, db_todo):
        assert scalar(db_todo, "select count(*) from public.personas where anio_fuente='registrado' and institucion_fuente='registrado'") == 3
        with as_user(db_todo, ADMIN) as cur:
            assert _err(cur, "update public.personas set anio_fuente='inventado' where id_persona='I-00001-00001'") is not None
            assert _err(cur, "update public.personas set institucion_fuente='otra' where id_persona='I-00001-00001'") is not None
            assert _err(cur, "update public.personas set anio_fuente='imputado' where id_persona='I-00001-00001'") is None

    def test_generador_etiqueta_solo_filas_que_coinciden(self, tmp_path):
        import csv
        import subprocess
        import sys
        d = tmp_path / "csv"
        d.mkdir()

        def escribir(nombre, cabecera, filas):
            with open(d / nombre, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(cabecera)
                w.writerows(filas)
        escribir("IMPUTACION_ANIOS_HISTORICOS_20260901.csv", ["id_persona", "nombre", "Año_imputado"],
                 [["I-00001-00001", "x", "2025"], ["P-00001-00002", "x", "2019"]])   # el 2.º ya no coincide (2025 ≠ 2019)
        escribir("CORRECCIONES_ACADEMICAS_BALANCEADAS_20260901.csv", ["id_persona", "nombre", "institucion_nueva"],
                 [["I-00001-00001", "x", "UPTx"], ["A-00001-00003", "x", "Otra"]])    # el 2.º no coincide
        escribir("CORRECCIONES_OFERTA_ACADEMICA_VERIFICADA_20260901.csv", ["id_persona", "nombre", "institucion_nueva"],
                 [["P-00001-00002", "x", "UATx"]])
        sql = tmp_path / "V005_prueba.sql"
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "generar_v005.py"), str(d), "--destino", str(sql)], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        texto = sql.read_text(encoding="utf-8")
        assert "x" not in texto.split("values", 1)[1].split("as v")[0].replace("'x'", "")  # sin nombres en el SQL
        db = _build("v5sint", MIGS_1A3)
        try:
            _run_file(db, sql)
            filas = {r[0]: r[1:] for r in _consultar(db, "select id_persona, anio_fuente, institucion_fuente from public.personas")}
            assert filas["I-00001-00001"] == ("imputado", "balanceado")
            assert filas["P-00001-00002"] == ("registrado", "balanceado")     # año distinto → no se etiqueta; institución sí
            assert filas["A-00001-00003"] == ("registrado", "registrado")     # institución distinta → no se etiqueta
            assert scalar(db, "select count(*) from public.app_audit_log where action='srv_update'") == 0
            assert scalar(db, "select anio from public.personas where id_persona='P-00001-00002'") == 2025   # ningún dato cambió
            # se puede volver a ejecutar sin efectos secundarios
            _run_file(db, sql)
            assert scalar(db, "select count(*) from public.personas where anio_fuente='imputado'") == 1
        finally:
            _drop_db(db)

    def test_rollback_v5_conserva_los_datos(self):
        db = _build("v5rb", MIGS_1A3 + ["V005_origen_del_dato.sql", "V005_rollback.sql"])
        try:
            assert scalar(db, "select count(*) from information_schema.columns where table_schema='public' and table_name='personas' and column_name like '%_fuente'") == 0
            assert scalar(db, "select count(*) from public.personas") == 3
        finally:
            _drop_db(db)


def _consultar(db, sql, params=None):
    with _connect(db) as conn:
        return conn.execute(sql, params).fetchall()


class TestV007:
    def test_fecha_cierre_coherente_con_la_fecha_de_publicacion(self, db_todo):
        with as_user(db_todo, ADMIN) as cur:
            assert _err(cur, "update public.vacantes set fecha_cierre='2025-12-31' where id_vacante='VAC-0001'") is not None   # cierre antes de publicar
            assert _err(cur, "update public.vacantes set fecha_cierre='2026-12-31' where id_vacante='VAC-0001'") is None

    def test_no_rechaza_ni_modifica_filas_historicas(self, db_todo):
        assert scalar(db_todo, "select count(*) from public.vacantes where fecha_cierre is not null") == 0
        with as_user(db_todo, ADMIN) as cur:
            assert _err(cur, "update public.vacantes set estado='Inactiva' where id_vacante='VAC-0002'") is None

    def test_rollback_v7(self):
        db = _build("v7rb", ["V007_vigencia_vacantes.sql", "V007_rollback.sql"])
        try:
            assert scalar(db, "select count(*) from information_schema.columns where table_schema='public' and table_name='vacantes' and column_name='fecha_cierre'") == 0
        finally:
            _drop_db(db)


class TestV008:
    def test_rls_por_accion(self, db_todo):
        ins = "insert into public.persona_disponibilidad(id_persona_maestro,disponible,nota,actualizado_por) values ('PER-0001',true,'ok','x')"
        with as_user(db_todo, LECTOR) as cur:       # ver sí, escribir no
            cur.execute("select count(*) from public.persona_disponibilidad")
            assert "row-level security" in (_err(cur, ins) or "")
        with as_user(db_todo, SOLOINICIO) as cur:   # sin personas·ver no ve nada
            cur.execute("select count(*) from public.persona_disponibilidad")
            assert cur.fetchone()[0] == 0
        with as_user(db_todo, EDITOR) as cur:       # personas·editar: alta y cambio (upsert de la app)
            assert _err(cur, ins) is None
            cur.execute("insert into public.persona_disponibilidad(id_persona_maestro,disponible) values ('PER-0001',false) "
                        "on conflict (id_persona_maestro) do update set disponible=excluded.disponible")
            cur.execute("select disponible from public.persona_disponibilidad where id_persona_maestro='PER-0001'")
            assert cur.fetchone()[0] is False
            cur.execute("delete from public.persona_disponibilidad where id_persona_maestro='PER-0001'")
            assert cur.rowcount == 0                # eliminar requiere personas·eliminar

    def test_anon_no_ve_nada(self, db_todo):
        with as_user(db_todo, role="anon") as cur:
            assert "permission denied" in (_err(cur, "select count(*) from public.persona_disponibilidad") or "")

    def test_id_con_formato_valido(self, db_todo):
        with as_user(db_todo, ADMIN) as cur:
            assert _err(cur, "insert into public.persona_disponibilidad(id_persona_maestro,disponible) values ('cualquiera',true)") is not None

    def test_auditoria_servidor_conectada(self, db_todo):
        with as_user(db_todo, ADMIN) as cur:
            cur.execute("insert into public.persona_disponibilidad(id_persona_maestro,disponible) values ('PER-0002',true)")
            cur.execute("select count(*) from public.app_audit_log where action='srv_insert' and detail like 'persona_disponibilidad PER-0002%'")
            assert cur.fetchone()[0] == 1

    def test_compuerta_de_equipo_tambien_aplica(self, db_todo):
        with _connect(db_todo) as conn:
            conn.execute("update public.app_settings set value='true' where key='enforce_device_rls'")
        try:
            with as_user(db_todo, LECTOR, headers={"x-device-id": "dev-lector-pend"}) as cur:
                cur.execute("select count(*) from public.persona_disponibilidad")
                assert cur.fetchone()[0] == 0
        finally:
            with _connect(db_todo) as conn:
                conn.execute("update public.app_settings set value='false' where key='enforce_device_rls'")

    def test_v8_exige_v2(self):
        db = _build("v8solo", ["V001_cierre_brechas.sql"])
        try:
            with pytest.raises(psycopg.Error):
                _run_file(db, MIG / "V008_disponibilidad_personas.sql")
        finally:
            _drop_db(db)

    def test_rollback_v8(self):
        db = _build("v8rb", MIGS_1A3 + ["V008_disponibilidad_personas.sql", "V008_rollback.sql"])
        try:
            assert scalar(db, "select to_regclass('public.persona_disponibilidad')::text") is None
        finally:
            _drop_db(db)


class TestV009:
    def _db(self, nombre, extra):
        db = _build(nombre, MIGS_1A3)
        with _connect(db) as conn:
            conn.execute("update public.personas set sexo='MASCULINO', escolaridad='superior' where id_persona='I-00001-00001'")
            conn.execute("update public.personas set sexo='mujer' where id_persona='P-00001-00002'")
            conn.execute("update public.personas set sexo='Otro', escolaridad='' where id_persona='A-00001-00003'")
        self.auditoria_previa = scalar(db, "select count(*) from public.app_audit_log where action='srv_update'")
        for f in extra:
            _run_file(db, MIG / f)
        return db

    def test_unifica_y_respalda_y_no_toca_lo_demas(self):
        db = self._db("v9", ["V009_unificar_redaccion.sql"])
        try:
            assert scalar(db, "select sexo from public.personas where id_persona='I-00001-00001'") == "Masculino"
            assert scalar(db, "select escolaridad from public.personas where id_persona='I-00001-00001'") == "Superior"
            assert scalar(db, "select sexo from public.personas where id_persona='P-00001-00002'") == "Femenino"
            assert scalar(db, "select sexo from public.personas where id_persona='A-00001-00003'") == "Otro"   # otro valor: intacto
            n = scalar(db, "select count(*) from public.respaldo_v009_redaccion")
            assert n >= 3     # las 3 filas preparadas aquí (+ lo que traiga el seed sintético)
            assert scalar(db, "select count(*) from public.app_audit_log where action='migration_V009'") == 1
            assert scalar(db, "select count(*) from public.app_audit_log where action='srv_update'") == self.auditoria_previa  # sin ruido por fila
            _run_file(db, MIG / "V009_unificar_redaccion.sql")        # idempotente
            assert scalar(db, "select count(*) from public.respaldo_v009_redaccion") == n
        finally:
            _drop_db(db)

    def test_rollback_restaura_los_valores_originales(self):
        db = self._db("v9rb", ["V009_unificar_redaccion.sql", "V009_rollback.sql"])
        try:
            assert scalar(db, "select sexo from public.personas where id_persona='I-00001-00001'") == "MASCULINO"
            assert scalar(db, "select escolaridad from public.personas where id_persona='I-00001-00001'") == "superior"
            assert scalar(db, "select sexo from public.personas where id_persona='P-00001-00002'") == "mujer"
        finally:
            _drop_db(db)

    def test_respaldo_solo_para_administradores(self):
        db = self._db("v9rls", ["V009_unificar_redaccion.sql"])
        try:
            with as_user(db, LECTOR) as cur:
                cur.execute("select count(*) from public.respaldo_v009_redaccion")
                assert cur.fetchone()[0] == 0
            with as_user(db, role="anon") as cur:
                assert "permission denied" in (_err(cur, "select count(*) from public.respaldo_v009_redaccion") or "")
        finally:
            _drop_db(db)


class TestCadenaCompleta:
    def test_aplicar_todo_y_revertir_todo_deja_la_base_como_estaba(self):
        db = _build("cadena", MIGS_1A3 + MIGS_4A8 + ["V008_rollback.sql", "V007_rollback.sql", "V005_rollback.sql", "V004_rollback.sql"])
        try:
            assert scalar(db, "select count(*) from public.personas") == 3
            assert scalar(db, "select count(*) from public.vacantes") == 2
            assert scalar(db, "select count(*) from information_schema.columns where table_schema='public' and "
                              "((table_name='personas' and column_name in ('anio_fuente','institucion_fuente')) or "
                              " (table_name='vacantes' and column_name in ('fecha_cierre','municipio_excepcion')) or "
                              " (table_name='catalogo_empresas' and column_name in ('municipio','latitud','longitud')) or "
                              " (table_name='catalogo_municipios_tlaxcala' and column_name='cve_mun'))") == 0
            assert scalar(db, "select to_regclass('public.persona_disponibilidad')::text") is None
        finally:
            _drop_db(db)


class TestPrimerAdministrador:
    PLACEHOLDER = "CAMBIA_ESTE_CORREO@ejemplo.com"

    def _db_vacia(self):
        db = _new_db("admin1")
        _run_file(db, SQL_DIR / "00_supabase_stub.sql")
        _run_file(db, SCHEMA)          # sin seed: no hay perfiles
        _run_file(db, MIG / "V001_cierre_brechas.sql")
        return db

    def _script(self, correo):
        return (ROOT / "supabase" / "schema" / "01_primer_administrador.sql").read_text(encoding="utf-8").replace(self.PLACEHOLDER, correo)

    def test_crea_admin_con_los_12_modulos_y_se_cierra(self):
        db = self._db_vacia()
        try:
            with _connect(db) as con:
                con.execute("insert into auth.users(id,email,encrypted_password,email_confirmed_at) values "
                            "('b0000000-0000-0000-0000-000000000001','Jefe@Sedeco.Test','x',now())")
                con.execute(self._script("jefe@sedeco.test"))
            assert scalar(db, "select role||'/'||status from public.app_profiles") == "admin/active"
            assert scalar(db, "select count(*) from public.app_permissions where can_view and can_create and can_edit and can_delete and can_export") == 12
            with _connect(db) as con, pytest.raises(psycopg.Error, match="Ya existen perfiles"):
                con.execute(self._script("jefe@sedeco.test"))
        finally:
            _drop_db(db)

    def test_sin_usuario_en_authentication_no_hace_nada(self):
        db = self._db_vacia()
        try:
            with _connect(db) as con, pytest.raises(psycopg.Error, match="No existe ningún usuario"):
                con.execute((ROOT / "supabase" / "schema" / "01_primer_administrador.sql").read_text(encoding="utf-8"))  # correo de ejemplo sin cambiar
            assert scalar(db, "select count(*) from public.app_profiles") == 0
        finally:
            _drop_db(db)


class TestConsultasDeVerificacionDocumentadas:
    """Las consultas que docs/MIGRACIONES.md manda ejecutar para V001 y V003 deben dar lo que la guía promete."""

    def test_v001_anon_sin_acceso(self, db_todo):
        assert scalar(db_todo, "select has_table_privilege('anon','public.personas','select')") is False

    def test_v003_seis_disparadores(self, db_todo):
        assert scalar(db_todo, "select count(*) from pg_trigger where not tgisinternal and (tgname like 'trg_audit_%' or tgname like 'trg_touch_%') "
                               "and tgrelid in ('public.personas'::regclass,'public.vacantes'::regclass,'public.vinculaciones'::regclass)") == 6
