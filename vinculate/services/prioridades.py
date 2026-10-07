"""Prioridades y recordatorios + centro de avisos."""
from __future__ import annotations

from datetime import date, datetime, time as hora, timedelta, timezone

from ..auth import servicio as auth_servicio
from ..auth.sesion import Sesion
from ..repositories.admin import RepoAdmin
from ..repositories.errores import ErrorDatos, SinPermiso
from .guardado import ZONA

NIVELES = ("normal", "alta", "urgente")
TIPOS = ("persona", "vacante", "vinculacion", "otro")
ORDEN_NIVEL = {"urgente": 0, "alta": 1, "normal": 2}


def _iso(valor):
    if not valor:
        return None
    try:
        dt = datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def vencida(fila: dict, ahora: datetime | None = None) -> bool:
    """Sin fecha de recordatorio = vigente de inmediato."""
    dt = _iso(fila.get("reminder_at"))
    return True if dt is None else dt <= (ahora or datetime.now(timezone.utc))


def listar(sesion: Sesion, solo_activas: bool = False) -> list[dict]:
    if not sesion.puede("prioridades", "view"):
        return []
    return RepoAdmin(sesion.cliente).prioridades(solo_activas=solo_activas)


def pendientes(sesion: Sesion) -> list[dict]:
    """Prioridades activas cuyo recordatorio ya venció, de la más urgente a la menos."""
    filas = [f for f in listar(sesion, solo_activas=True) if vencida(f)]
    return sorted(filas, key=lambda f: (ORDEN_NIVEL.get(f.get("priority_level"), 3), str(f.get("reminder_at") or "")))


def crear(sesion: Sesion, tipo: str, referencia: str, titulo: str, descripcion: str, nivel: str,
          fecha: date, hora_aviso: hora, repetir_min: int) -> None:
    if not sesion.puede("prioridades", "create"):
        raise SinPermiso("Tu perfil no tiene permiso para crear prioridades.")
    if not (titulo or "").strip():
        raise ValueError("Escribe un título.")
    if nivel not in NIVELES or tipo not in TIPOS:
        raise ValueError("Tipo o nivel inválido.")
    local = datetime.combine(fecha, hora_aviso).replace(tzinfo=ZONA)  # hora de la Ciudad de México
    RepoAdmin(sesion.cliente).crear_prioridad({
        "entity_type": tipo, "entity_id": (referencia or "").strip() or "sin-id", "title": titulo.strip(),
        "description": (descripcion or "").strip() or None, "priority_level": nivel,
        "reminder_at": local.astimezone(timezone.utc).isoformat(), "repeat_minutes": max(1, int(repetir_min)),
        "active": True, "created_by": sesion.user_id,
    })
    auth_servicio.auditar("priority_created", titulo.strip())


def cerrar(sesion: Sesion, prioridad_id: int, titulo: str = "") -> None:
    if not sesion.puede("prioridades", "edit"):
        raise SinPermiso("Tu perfil no tiene permiso para cerrar prioridades.")
    RepoAdmin(sesion.cliente).cerrar_prioridad(prioridad_id)
    auth_servicio.auditar("priority_completed", titulo or str(prioridad_id))


def para_toast(sesion: Sesion, maximo: int = 5, pendientes_ya: list[dict] | None = None) -> list[dict]:
    """Avisos que toca mostrar como toast ahora (respeta `repeat_minutes` por usuario) y los marca como vistos.

    `pendientes_ya` evita repetir la consulta cuando quien llama ya tiene la lista."""
    if not sesion.puede("prioridades", "view"):
        return []
    repo = RepoAdmin(sesion.cliente)
    ahora = datetime.now(timezone.utc)
    salida = []
    for fila in (pendientes_ya if pendientes_ya is not None else pendientes(sesion))[:maximo]:
        cada = max(int(fila.get("repeat_minutes") or 60), 1)
        try:
            visto = _iso(repo.ultimo_aviso(fila["id"], sesion.user_id))
        except ErrorDatos:
            visto = None
        if visto and ahora < visto + timedelta(minutes=cada):
            continue
        salida.append(fila)
        try:
            repo.marcar_aviso(fila["id"], sesion.user_id)
        except ErrorDatos:
            pass
    return salida
