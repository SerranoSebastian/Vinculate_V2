"""Repositorio de las tablas administrativas (perfiles, permisos, equipos, auditoría,
prioridades, ajustes) y de los RPC SECURITY DEFINER."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .errores import traducir


def _ejecutar(consulta, contexto: str):
    try:
        return consulta.execute()
    except Exception as exc:  # noqa: BLE001
        raise traducir(exc, contexto) from exc


class RepoAdmin:
    def __init__(self, cliente):
        self.c = cliente

    # --- perfil y permisos propios (login) -----------------------------------
    def perfil(self, uid: str) -> dict | None:
        r = _ejecutar(self.c.table("app_profiles").select("*").eq("user_id", uid).limit(1), "la consulta de tu perfil")
        return (r.data or [None])[0]

    def permisos_de(self, uid: str) -> list[dict]:
        r = _ejecutar(self.c.table("app_permissions").select("*").eq("user_id", uid), "la consulta de permisos")
        return r.data or []

    # --- usuarios -------------------------------------------------------------
    def perfiles(self) -> list[dict]:
        r = _ejecutar(self.c.table("app_profiles").select("*").order("created_at"), "la consulta de usuarios")
        return r.data or []

    def perfil_por_email(self, email: str) -> dict | None:
        r = _ejecutar(self.c.table("app_profiles").select("user_id,email,status").eq("email", email).limit(1), "la consulta de usuarios")
        return (r.data or [None])[0]

    def rpc(self, nombre: str, parametros: dict) -> Any:
        r = _ejecutar(self.c.rpc(nombre, parametros), "la operación administrativa")
        return getattr(r, "data", None)

    # --- equipos --------------------------------------------------------------
    def equipos(self) -> list[dict]:
        r = _ejecutar(self.c.table("app_devices").select("*").order("last_seen", desc=True), "la consulta de equipos")
        return r.data or []

    def equipo(self, uid: str, device_id: str) -> dict | None:
        r = _ejecutar(self.c.table("app_devices").select("*").eq("user_id", uid).eq("device_id", device_id).limit(1), "la consulta de equipos")
        return (r.data or [None])[0]

    def registrar_equipo(self, carga: dict) -> dict:
        r = _ejecutar(self.c.table("app_devices").insert(carga), "el registro del equipo")
        return (r.data or [carga])[0]

    def tocar_equipo(self, uid: str, device_id: str, carga: dict) -> dict | None:
        r = _ejecutar(self.c.table("app_devices").update(carga).eq("user_id", uid).eq("device_id", device_id), "la actualización del equipo")
        return (r.data or [None])[0]

    def autorizar_equipo(self, uid: str, device_id: str, autorizado: bool) -> None:
        _ejecutar(self.c.table("app_devices").update({"authorized": autorizado}).eq("user_id", uid).eq("device_id", device_id), "la autorización del equipo")

    # --- auditoría ------------------------------------------------------------
    def registrar_auditoria(self, carga: dict) -> None:
        _ejecutar(self.c.table("app_audit_log").insert(carga), "el registro de auditoría")

    def auditoria(self, limite: int = 500) -> list[dict]:
        r = _ejecutar(self.c.table("app_audit_log").select("*").order("created_at", desc=True).limit(limite), "la consulta de auditoría")
        return r.data or []

    # --- prioridades ----------------------------------------------------------
    def prioridades(self, solo_activas: bool = False) -> list[dict]:
        q = self.c.table("app_priorities").select("*")
        if solo_activas:
            q = q.eq("active", True)
        return _ejecutar(q.order("created_at", desc=True), "la consulta de prioridades").data or []

    def crear_prioridad(self, carga: dict) -> None:
        _ejecutar(self.c.table("app_priorities").insert(carga), "el alta de la prioridad")

    def cerrar_prioridad(self, prioridad_id: int) -> None:
        _ejecutar(self.c.table("app_priorities").update(
            {"active": False, "completed_at": datetime.now(timezone.utc).isoformat()}).eq("id", prioridad_id),
            "el cierre de la prioridad")

    def ultimo_aviso(self, prioridad_id: int, uid: str) -> str | None:
        r = _ejecutar(self.c.table("app_priority_notifications").select("last_seen_at")
                      .eq("priority_id", prioridad_id).eq("user_id", uid).limit(1), "la consulta de avisos")
        return (r.data or [{}])[0].get("last_seen_at") if r.data else None

    def marcar_aviso(self, prioridad_id: int, uid: str) -> None:
        _ejecutar(self.c.table("app_priority_notifications").upsert({
            "priority_id": prioridad_id, "user_id": uid,
            "last_seen_at": datetime.now(timezone.utc).isoformat(),
        }, on_conflict="priority_id,user_id"), "el registro del aviso")

    # --- ajustes (V002) -------------------------------------------------------
    def ajuste(self, clave: str) -> str | None:
        try:
            r = self.c.table("app_settings").select("value").eq("key", clave).limit(1).execute()
        except Exception:  # noqa: BLE001 — la tabla puede no existir si V002 no se aplicó
            return None
        return (r.data or [{}])[0].get("value") if r.data else None

    def guardar_ajuste(self, clave: str, valor: str) -> None:
        _ejecutar(self.c.table("app_settings").update({"value": valor, "updated_at": datetime.now(timezone.utc).isoformat()}).eq("key", clave), "el cambio de ajuste")

    # --- historial ------------------------------------------------------------
    def historial(self, limite: int = 500) -> list[dict]:
        r = _ejecutar(self.c.table("historial_cargas").select("*").order("id", desc=True).limit(limite), "la consulta del historial")
        return r.data or []

    def registrar_historial(self, carga: dict) -> None:
        _ejecutar(self.c.table("historial_cargas").insert(carga), "el registro del historial")
