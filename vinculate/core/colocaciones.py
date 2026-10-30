"""Colocaciones: cada seguimiento con estatus «Colocado» es una colocación de la persona en esa empresa.

Una persona puede tener varias colocaciones a lo largo del tiempo; se distinguen por su fecha (la más reciente es la vigente).
"""
from __future__ import annotations

from datetime import date

import pandas as pd

COLUMNAS = ["id_vinculacion", "id_persona_maestro", "nombre_persona", "empresa", "tipo_vacante", "fecha_vinculacion",
            "fecha_colocacion", "n_colocacion", "total_colocaciones", "vigente"]


def colocaciones(seg: pd.DataFrame) -> pd.DataFrame:
    """Una fila por colocación, numerada por persona en orden de fecha (1 = la primera). Sin fecha va antes (se desconoce cuándo fue)."""
    if seg is None or seg.empty:
        return pd.DataFrame(columns=COLUMNAS)
    c = seg[seg["estatus"].eq("Colocado")].copy()
    if c.empty:
        return pd.DataFrame(columns=COLUMNAS)
    c = c.sort_values(["id_persona_maestro", "fecha_colocacion", "fecha_actualizacion"], na_position="first", kind="stable")
    g = c.groupby("id_persona_maestro")
    c["n_colocacion"] = g.cumcount() + 1
    c["total_colocaciones"] = g["id_vinculacion"].transform("count")
    c["vigente"] = c["n_colocacion"].eq(c["total_colocaciones"])
    return c[COLUMNAS].reset_index(drop=True)


def errores_colocacion(seg: pd.DataFrame, id_vinculacion: str, fecha: date | None, hoy: date | None = None) -> list[str]:
    """Motivos por los que NO se puede registrar la colocación (lista vacía = se puede)."""
    hoy = hoy or date.today()
    fila = seg[seg["id_vinculacion"].eq(id_vinculacion)] if not seg.empty else seg
    if fila.empty:
        return ["Ese seguimiento ya no existe. Actualiza la lista."]
    f = fila.iloc[0]
    if f["estatus"] == "Colocado":
        return ["Ese seguimiento ya está registrado como colocación. Para cambiar su fecha usa «Editar / eliminar»."]
    if f["estatus"] != "Vinculado":
        return ["Solo se puede colocar a una persona en un seguimiento con estatus «Vinculado»."]
    if fecha is None:
        return ["Indica la fecha de colocación."]
    errores = []
    if fecha > hoy:
        errores.append("La fecha de colocación no puede ser futura.")
    fv = pd.to_datetime(f.get("fecha_vinculacion"), errors="coerce")
    if pd.notna(fv) and pd.Timestamp(fecha) < fv.normalize():
        errores.append("La fecha de colocación no puede ser anterior a la fecha de vinculación.")
    otras = colocaciones(seg[seg["id_persona_maestro"].eq(f["id_persona_maestro"])])
    if not otras.empty and (pd.to_datetime(otras["fecha_colocacion"], errors="coerce").dt.date == fecha).any():
        errores.append("Esa persona ya tiene otra colocación con la misma fecha. Las colocaciones se distinguen por fecha: revisa la fecha.")
    return errores
