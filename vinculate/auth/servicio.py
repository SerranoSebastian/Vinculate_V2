"""Inicio/cierre de sesión, revalidación de perfil, permisos y equipo."""
from __future__ import annotations

import re
import time
from datetime import datetime, timezone

import streamlit as st

from ..config.settings import VERSION_APP
from ..repositories.admin import RepoAdmin
from ..repositories.cliente import nuevo_cliente
from ..repositories.errores import ErrorDatos
from . import dispositivo
from .sesion import Sesion, actual, guardar

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_CLAVES_ESTADO = ("_auth_checked_at", "_device_checked_at", "_cache_ver", "_papelera", "_ping")


class AccesoDenegado(PermissionError):
    """El usuario no puede entrar (perfil inactivo, equipo no autorizado…)."""


def _ahora_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _agente_usuario() -> str | None:
    try:
        return st.context.headers.get("User-Agent")
    except Exception:  # noqa: BLE001
        return None


def _cargar_perfil_y_permisos(repo: RepoAdmin, uid: str) -> tuple[dict, dict]:
    perfil = repo.perfil(uid)
    if not perfil:
        raise AccesoDenegado("Tu cuenta existe en Authentication, pero todavía no tiene un perfil de Vincúlate.")
    if perfil.get("status") != "active":
        raise AccesoDenegado(
            f"Tu perfil está en estado '{perfil.get('status', 'sin definir')}'. Solicita activación a un administrador.")
    permisos = {r["module_key"]: r for r in repo.permisos_de(uid) if r.get("module_key")}
    return perfil, permisos


def _registrar_o_leer_equipo(repo: RepoAdmin, uid: str, did: str, es_admin: bool) -> dict:
    nav, so = dispositivo.describir_navegador(_agente_usuario())
    carga = {"user_id": uid, "device_id": did, "hostname": f"{nav} en {so}", "os_name": so,
             "os_version": nav, "app_version": VERSION_APP}
    existente = repo.equipo(uid, did)
    if existente is None:
        # Un equipo nuevo nace NO autorizado, salvo que quien lo registra sea administrador.
        carga["authorized"] = bool(es_admin)
        return repo.registrar_equipo(carga)
    if existente.get("authorized") or es_admin:
        try:
            carga["last_seen"] = _ahora_iso()
            repo.tocar_equipo(uid, did, carga)
        except ErrorDatos:
            pass
    return existente


def auditar(accion: str, detalle: str = "") -> None:
    """Registro de auditoría de acciones de la app. Nunca interrumpe el flujo."""
    s = actual()
    if not s or not s.cliente:
        return
    try:
        RepoAdmin(s.cliente).registrar_auditoria({
            "user_id": s.user_id, "email": s.email, "action": accion,
            "detail": detalle or None, "device_id": s.device_id,
        })
    except Exception:  # noqa: BLE001
        pass


def iniciar_sesion(email: str, password: str) -> Sesion:
    did = dispositivo.id_dispositivo()
    if not did:
        raise AccesoDenegado("No se pudo identificar este equipo. Recarga la página e inténtalo de nuevo.")
    email = (email or "").strip().lower()
    if not EMAIL_RE.match(email):
        raise ValueError("Escribe un correo electrónico válido.")
    cliente = nuevo_cliente(did)
    try:
        resp = cliente.auth.sign_in_with_password({"email": email, "password": password})
    except Exception as exc:  # noqa: BLE001
        mensaje = str(exc).lower()
        if "invalid login" in mensaje or "invalid_credentials" in mensaje or "invalid credentials" in mensaje:
            raise AccesoDenegado("Correo o contraseña incorrectos.") from exc
        if "email not confirmed" in mensaje:
            raise AccesoDenegado("Tu correo aún no está confirmado. Contacta a un administrador.") from exc
        raise AccesoDenegado("No se pudo iniciar sesión. Revisa tus datos y tu conexión.") from exc
    user = getattr(resp, "user", None)
    if not user:
        raise AccesoDenegado("Correo o contraseña incorrectos.")

    repo = RepoAdmin(cliente)
    uid = str(user.id)
    try:
        perfil, permisos = _cargar_perfil_y_permisos(repo, uid)
        es_admin = perfil.get("role") == "admin"
        equipo = _registrar_o_leer_equipo(repo, uid, did, es_admin)
        sesion = Sesion(user_id=uid, email=user.email or email, perfil=perfil, permisos=permisos,
                        device_id=did, cliente=cliente)
        if not (equipo.get("authorized") or es_admin):
            guardar(sesion)
            auditar("login_device_pending", "Inicio desde un equipo pendiente de autorización")
            raise AccesoDenegado(
                "Este equipo quedó registrado, pero todavía no está autorizado. Un administrador debe "
                "habilitarlo desde Administración → Computadoras.")
    except Exception:
        try:
            cliente.auth.sign_out()
        except Exception:  # noqa: BLE001
            pass
        guardar(None)
        raise
    guardar(sesion)
    st.session_state["_auth_checked_at"] = time.monotonic()
    st.session_state["_device_checked_at"] = time.monotonic()
    auditar("login", "Inicio de sesión correcto")
    return sesion


def revalidar(forzar: bool = False, max_edad_perfil: float = 8, max_edad_equipo: float = 12) -> Sesion:
    """Revalida perfil, permisos y equipo para que un cambio del administrador se aplique sin
    reiniciar sesión. Lanza AccesoDenegado si el acceso ya no está habilitado."""
    s = actual()
    if s is None:
        raise AccesoDenegado("No hay sesión activa.")
    repo = RepoAdmin(s.cliente)
    ahora = time.monotonic()
    try:
        if forzar or ahora - float(st.session_state.get("_auth_checked_at", 0) or 0) >= max_edad_perfil:
            s.perfil, s.permisos = _cargar_perfil_y_permisos(repo, s.user_id)
            st.session_state["_auth_checked_at"] = ahora
        if forzar or ahora - float(st.session_state.get("_device_checked_at", 0) or 0) >= max_edad_equipo:
            equipo = repo.equipo(s.user_id, s.device_id)
            if equipo is None:
                equipo = _registrar_o_leer_equipo(repo, s.user_id, s.device_id, s.es_admin)
            if not (equipo.get("authorized") or s.es_admin):
                raise AccesoDenegado("Este equipo fue bloqueado o todavía no ha sido autorizado por un administrador.")
            try:
                repo.tocar_equipo(s.user_id, s.device_id, {"last_seen": _ahora_iso()})
            except ErrorDatos:
                pass
            st.session_state["_device_checked_at"] = ahora
    except ErrorDatos as exc:
        raise AccesoDenegado(str(exc)) from exc
    guardar(s)
    return s


def cerrar_sesion() -> None:
    auditar("logout", "Cierre de sesión")
    s = actual()
    try:
        if s and s.cliente:
            s.cliente.auth.sign_out()
    except Exception:  # noqa: BLE001
        pass
    guardar(None)
    for k in _CLAVES_ESTADO:
        st.session_state.pop(k, None)
    # El caché de datos es global entre sesiones, pero su llave incluye el id de usuario
    # (ver services/datos.py): otro usuario nunca puede recibir estas entradas.


def validar_contrasena(nueva: str) -> None:
    if len(nueva or "") < 8:
        raise ValueError("La contraseña debe tener al menos 8 caracteres.")
    if len(nueva) > 72:
        raise ValueError("La contraseña no puede superar 72 caracteres.")


def cambiar_contrasena_propia(nueva: str) -> None:
    validar_contrasena(nueva)
    s = actual()
    if not s or not s.cliente:
        raise AccesoDenegado("No hay sesión activa.")
    s.cliente.auth.update_user({"password": nueva})
    auditar("password_changed", "El usuario cambió su contraseña")
