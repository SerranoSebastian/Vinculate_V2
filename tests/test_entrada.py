"""Flujo completo del archivo principal: configuración, inicio de sesión, menú por permisos y cierre de sesión."""
from pathlib import Path
from types import SimpleNamespace

import pytest
from streamlit.testing.v1 import AppTest

from tests.demo import cliente_demo, permisos

pytestmark = pytest.mark.apptest
DEVICE = "22222222-2222-4222-8222-222222222222"
APP = str(Path(__file__).resolve().parents[1] / "streamlit_app.py")


def _cliente(rol="admin", mods=None, autorizado=True):
    c = cliente_demo()
    uid = "u-admin" if rol == "admin" else "u-col"
    c.auth = SimpleNamespace(
        sign_in_with_password=lambda cred: SimpleNamespace(user=SimpleNamespace(id=uid, email=cred["email"])),
        sign_out=lambda: None, update_user=lambda d: None)
    if rol != "admin":
        c.tablas["app_permissions"] = [{"user_id": uid, **{k: v for k, v in p.items()}} for p in permisos(**(mods or {})).values()]
    c.tablas["app_devices"] = [] if not autorizado else [
        {"user_id": uid, "device_id": DEVICE, "hostname": "Chrome", "os_name": "Windows", "app_version": "2.0.0",
         "authorized": True, "last_seen": "2026-10-01T10:00:00+00:00"}]
    return c


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://demo.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "sb_publishable_demo")

    def montar(cliente):
        monkeypatch.setattr("vinculate.auth.servicio.nuevo_cliente", lambda did=None: cliente)
        at = AppTest.from_file(APP, default_timeout=60)
        at.session_state["_device_id_forzado"] = DEVICE
        return at
    return montar


def test_sin_configuracion_explica_que_hacer(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_KEY", raising=False)
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    assert any("Supabase no está configurado" in e.value for e in at.error)


def test_llave_service_role_bloquea_el_arranque(monkeypatch):
    import base64, json
    payload = base64.urlsafe_b64encode(json.dumps({"role": "service_role"}).encode()).decode().rstrip("=")
    monkeypatch.setenv("SUPABASE_URL", "https://demo.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", f"aaa.{payload}.bbb")
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert any("SECRETA" in e.value for e in at.error)
    assert not at.text_input  # ni siquiera se muestra el formulario de acceso


def test_login_correcto_admin_llega_al_inicio(app):
    at = app(_cliente("admin")).run()
    assert not at.exception and at.text_input  # formulario de acceso
    at.text_input[0].set_value("admin@sedeco.test")
    at.text_input[1].set_value("secreta123")
    at.button[0].click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert not at.error, [e.value for e in at.error]
    assert any("Inicio ejecutivo" in m.value for m in at.main.markdown)
    assert any(b.label == "Cerrar sesión" for b in at.sidebar.button)


def test_cerrar_sesion_vuelve_al_login(app):
    at = app(_cliente("admin")).run()
    at.text_input[0].set_value("admin@sedeco.test")
    at.text_input[1].set_value("secreta123")
    at.button[0].click().run()
    next(b for b in at.sidebar.button if b.label == "Cerrar sesión").click().run()
    assert not at.exception and at.text_input  # de nuevo el formulario de acceso


def test_colaborador_sin_modulos_solo_ve_su_cuenta(app):
    at = app(_cliente("colaborador", mods={})).run()
    at.text_input[0].set_value("col@sedeco.test")
    at.text_input[1].set_value("secreta123")
    at.button[0].click().run()
    assert not at.exception, [e.value for e in at.exception]
    textos = " ".join(m.value for m in at.main.markdown)
    assert "Mi cuenta" in textos and "example.test" not in textos


def test_login_incorrecto_no_entra(app, monkeypatch):
    c = _cliente("admin")

    def falla(cred):
        raise Exception("Invalid login credentials")
    c.auth.sign_in_with_password = falla
    at = app(c).run()
    at.text_input[0].set_value("admin@sedeco.test")
    at.text_input[1].set_value("mala")
    at.button[0].click().run()
    assert any("incorrectos" in e.value for e in at.error)


def test_equipo_no_autorizado_no_entra(app):
    at = app(_cliente("colaborador", mods={"inicio": ("view",)}, autorizado=False)).run()
    at.text_input[0].set_value("col@sedeco.test")
    at.text_input[1].set_value("secreta123")
    at.button[0].click().run()
    assert any("no está autorizado" in e.value for e in at.error)


def test_bloqueo_tras_cinco_intentos(app):
    c = _cliente("admin")

    def falla(cred):
        raise Exception("Invalid login credentials")
    c.auth.sign_in_with_password = falla
    at = app(c).run()
    for _ in range(5):
        at.text_input[0].set_value("admin@sedeco.test")
        at.text_input[1].set_value("mala")
        at.button[0].click().run()
    assert any("Demasiados intentos" in w.value for w in at.warning)
    assert not at.text_input
