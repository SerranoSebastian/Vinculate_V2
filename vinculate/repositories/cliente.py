"""Fábrica de clientes de Supabase.

* Cliente público: solo para iniciar sesión (Auth).
* Cliente de usuario: el mismo cliente tras iniciar sesión; todas las consultas
  viajan con el JWT del usuario, de modo que RLS aplica de verdad. Envía además
  el encabezado `x-device-id` con el identificador del navegador (decisión D2).
"""
from __future__ import annotations

from supabase import ClientOptions, create_client

from ..config.settings import supabase_cfg

ENCABEZADO_EQUIPO = "x-device-id"


def nuevo_cliente(device_id: str | None = None):
    cfg = supabase_cfg()
    headers = {ENCABEZADO_EQUIPO: device_id} if device_id else {}
    return create_client(cfg.url, cfg.key, options=ClientOptions(headers=headers))
