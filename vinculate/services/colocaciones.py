"""Registrar o quitar la colocación de una persona en una de las empresas a las que fue vinculada (con permiso y auditoría)."""
from __future__ import annotations

from datetime import date

from ..auth import servicio as auth_servicio
from ..auth.sesion import Sesion
from ..core import colocaciones as nucleo
from . import datos
from .guardado import Resultado, editar


def pendientes_de_persona(sesion: Sesion, id_persona: str):
    """Seguimientos de la persona (más reciente primero)."""
    seg = datos.vinculaciones(sesion)
    if seg.empty:
        return seg
    return seg[seg["id_persona_maestro"].eq(id_persona)].sort_values(["fecha_vinculacion", "fecha_actualizacion"], ascending=False, na_position="last")


def registrar(sesion: Sesion, id_vinculacion: str, fecha: date | None, puesto: str = "") -> Resultado:
    """Marca el seguimiento como «Colocado» con su fecha. La persona puede tener varias colocaciones (en fechas distintas)."""
    if not sesion.puede("vinculaciones", "edit"):
        return Resultado(False, "Tu perfil no tiene permiso para registrar colocaciones.")
    seg = datos.vinculaciones(sesion)
    errores = nucleo.errores_colocacion(seg, id_vinculacion, fecha)
    if errores:
        return Resultado(False, errores[0], errores=[{"campo": "fecha_colocacion", "error": e} for e in errores])
    cambios = {"estatus": "Colocado", "fecha_colocacion": fecha}
    if puesto and puesto.strip():
        cambios["tipo_vacante"] = puesto.strip()
    r = editar(sesion, "vinculaciones", id_vinculacion, cambios)
    if r.ok and r.guardados:
        auth_servicio.auditar("colocacion_registrada", f"id={id_vinculacion}; fecha={fecha.isoformat()}")
        r.mensaje = "Colocación registrada."
    return r


def quitar(sesion: Sesion, id_vinculacion: str) -> Resultado:
    """Deshace una colocación registrada por error: el seguimiento vuelve a «Vinculado» y se borra su fecha de colocación."""
    if not sesion.puede("vinculaciones", "edit"):
        return Resultado(False, "Tu perfil no tiene permiso para modificar colocaciones.")
    seg = datos.vinculaciones(sesion)
    fila = seg[seg["id_vinculacion"].eq(id_vinculacion)] if not seg.empty else seg
    if fila.empty or fila.iloc[0]["estatus"] != "Colocado":
        return Resultado(False, "Ese seguimiento no está registrado como colocación.")
    r = editar(sesion, "vinculaciones", id_vinculacion, {"estatus": "Vinculado", "fecha_colocacion": None})
    if r.ok and r.guardados:
        auth_servicio.auditar("colocacion_quitada", f"id={id_vinculacion}")
        r.mensaje = "Colocación quitada: el seguimiento volvió a «Vinculado»."
    return r
