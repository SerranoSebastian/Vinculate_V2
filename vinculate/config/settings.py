"""Configuración de la aplicación: credenciales de Supabase y rutas.

La app SOLO usa la llave pública (anon / publishable). Una llave service_role
o secret NUNCA debe llegar aquí: si se detecta, la app se niega a arrancar.
"""
from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
ASSETS = RAIZ / "assets"
GEO = RAIZ / "geo"
LOGO_HORIZONTAL = ASSETS / "identidad" / "tlaxcala_sedeco_horizontal.jpeg"
LOGO_PORTADA = ASSETS / "identidad" / "tlaxcala_sedeco_portada.jpeg"
VERSION_APP = "2.0.0"


class ConfiguracionInvalida(RuntimeError):
    """Falta configuración o es insegura."""


@dataclass(frozen=True)
class SupabaseCfg:
    url: str
    key: str


def es_llave_secreta(key: str) -> bool:
    """True si la llave parece ser service_role / secret (jamás debe usarse en la app)."""
    k = (key or "").strip()
    if k.startswith("sb_secret_"):
        return True
    partes = k.split(".")
    if len(partes) == 3:
        try:
            relleno = "=" * (-len(partes[1]) % 4)
            payload = json.loads(base64.urlsafe_b64decode(partes[1] + relleno))
            return str(payload.get("role", "")).lower() == "service_role"
        except Exception:  # noqa: BLE001
            return False
    return False


def _leer_secretos() -> tuple[str, str]:
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_KEY", "").strip()
    try:
        import streamlit as st

        sec = st.secrets.get("supabase", {})
        url = str(sec.get("url", url)).strip()
        key = str(sec.get("key", key)).strip()
    except Exception:  # noqa: BLE001 — sin secrets.toml
        pass
    return url, key


def supabase_cfg() -> SupabaseCfg:
    url, key = _leer_secretos()
    if not url or not key:
        raise ConfiguracionInvalida(
            "Supabase no está configurado. Agrega [supabase] url y key (llave PÚBLICA anon/publishable) "
            "en los Secrets de Streamlit o en .streamlit/secrets.toml."
        )
    if es_llave_secreta(key):
        raise ConfiguracionInvalida(
            "La llave configurada es una llave SECRETA (service_role). Por seguridad la aplicación no "
            "arranca con ella: usa únicamente la llave pública anon/publishable."
        )
    if not url.startswith("https://") and not url.startswith("http://localhost"):
        raise ConfiguracionInvalida("La URL de Supabase debe comenzar con https://")
    return SupabaseCfg(url=url.rstrip("/"), key=key)
