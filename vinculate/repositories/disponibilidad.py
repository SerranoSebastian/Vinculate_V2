"""Disponibilidad MANUAL de una persona para ser vinculada (decisión D3; tabla creada por V008)."""
from __future__ import annotations

from datetime import datetime, timezone

from .errores import traducir

TABLA = "persona_disponibilidad"


def _no_existe(exc: Exception) -> bool:
    codigo = str(getattr(exc, "code", "") or "")
    texto = str(getattr(exc, "message", "") or exc).lower()
    return codigo in {"PGRST205", "42P01"} or "could not find the table" in texto or "does not exist" in texto


class RepoDisponibilidad:
    def __init__(self, cliente):
        self.c = cliente

    def listar(self) -> list[dict] | None:
        """Filas, o None si la tabla todavía no existe (V008 sin aplicar)."""
        try:
            return self.c.table(TABLA).select("*").execute().data or []
        except Exception as exc:  # noqa: BLE001
            if _no_existe(exc):
                return None
            raise traducir(exc, "la consulta de disponibilidad") from exc

    def guardar(self, id_maestro: str, disponible: bool, nota: str | None, usuario: str) -> None:
        try:
            self.c.table(TABLA).upsert({
                "id_persona_maestro": id_maestro, "disponible": bool(disponible), "nota": (nota or "").strip() or None,
                "actualizado_por": usuario, "actualizado_en": datetime.now(timezone.utc).isoformat(),
            }, on_conflict="id_persona_maestro").execute()
        except Exception as exc:  # noqa: BLE001
            raise traducir(exc, "el cambio de disponibilidad") from exc
