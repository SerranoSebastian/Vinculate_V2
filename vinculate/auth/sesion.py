"""Sesión autenticada y permisos (módulo × acción), espejo de has_permission() en SQL."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..core.constantes import ACTIONS, MODULES

CLAVE_SESION = "_sesion_v2"


@dataclass
class Sesion:
    user_id: str
    email: str
    perfil: dict[str, Any]
    permisos: dict[str, dict[str, Any]]
    device_id: str
    cliente: Any = field(repr=False, default=None)

    @property
    def nombre(self) -> str:
        return str(self.perfil.get("display_name") or self.email or "Usuario")

    @property
    def activa(self) -> bool:
        return self.perfil.get("status") == "active"

    @property
    def es_admin(self) -> bool:
        return self.perfil.get("role") == "admin" and self.activa

    def puede(self, modulo: str, accion: str = "view") -> bool:
        if modulo not in MODULES or accion not in ACTIONS:
            return False
        if self.es_admin:
            return True
        if not self.activa:
            return False
        return bool(self.permisos.get(modulo, {}).get(f"can_{accion}", False))

    def puede_alguna(self, modulo: str, acciones=("create", "edit", "delete")) -> bool:
        return any(self.puede(modulo, a) for a in acciones)

    def modulos_visibles(self) -> list[str]:
        return [m for m in MODULES if self.puede(m, "view")]


def actual() -> Sesion | None:
    import streamlit as st

    return st.session_state.get(CLAVE_SESION)


def guardar(sesion: Sesion | None) -> None:
    import streamlit as st

    if sesion is None:
        st.session_state.pop(CLAVE_SESION, None)
    else:
        st.session_state[CLAVE_SESION] = sesion


def puede(modulo: str, accion: str = "view") -> bool:
    s = actual()
    return bool(s and s.puede(modulo, accion))


def requerir(modulo: str, accion: str = "view") -> Sesion:
    """Corta la página si el usuario no tiene el permiso (no basta con ocultar el menú)."""
    import streamlit as st

    s = actual()
    if not s or not s.puede(modulo, accion):
        st.error("Tu perfil no tiene permiso para ver o realizar esto.")
        st.stop()
    return s
