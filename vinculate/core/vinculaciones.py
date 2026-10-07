"""Reglas de seguimiento persona → empresa (puras)."""
from __future__ import annotations

from datetime import datetime

import pandas as pd

from .constantes import ESTATUS_VINCULACION, VINCULACIONES_COLS
from .personas import limpiar_personas, obtener_personas_maestras
from .texto import parsear_fechas

_MAPA_ESTATUS = {
    "sin vincular": "No vinculado", "pendiente": "No vinculado", "pendiente de aceptación": "No vinculado",
    "entrevista programada": "No vinculado", "aceptado": "Vinculado", "contratado": "Colocado",
    "colocado": "Colocado", "rechazado": "No vinculado", "baja": "No vinculado",
    "vinculado": "Vinculado", "no vinculado": "No vinculado",
}


def crear_id_vinculacion(total_actual: int, ahora: datetime | None = None) -> str:
    ahora = ahora or datetime.now()
    return f"VIN-{ahora.strftime('%Y%m%d%H%M%S')}-{total_actual + 1}"


def limpiar_vinculaciones(df: pd.DataFrame, personas: pd.DataFrame | None = None,
                          generar_ids: bool = True) -> pd.DataFrame:
    """`generar_ids=False` deja vacíos los IDs faltantes (el servicio de guardado los asigna
    contra los IDs reales de la base)."""
    df = df.copy()
    df.columns = df.columns.astype(str).str.strip()
    # Migración desde el esquema anterior: id_persona se entendía como registro histórico.
    if "id_persona_maestro" not in df.columns:
        df["id_persona_maestro"] = ""
    if "id_registro_origen" not in df.columns:
        df["id_registro_origen"] = df["id_persona"] if "id_persona" in df.columns else ""
    if "id_persona" in df.columns and personas is not None:
        pl = limpiar_personas(personas)
        mapa = pl.drop_duplicates("id_persona").set_index("id_persona")["id_persona_maestro"].to_dict()
        falta = df["id_persona_maestro"].fillna("").astype(str).str.strip().eq("")
        df.loc[falta, "id_persona_maestro"] = df.loc[falta, "id_persona"].astype(str).map(mapa).fillna("")

    if "estatus" not in df.columns:
        df["estatus"] = "Vinculado"
    df["estatus"] = df["estatus"].fillna("").astype(str).str.strip().str.lower().map(_MAPA_ESTATUS).fillna("Vinculado")
    for c in ("fecha_vinculacion", "fecha_colocacion"):
        if c not in df.columns:
            df[c] = None
    if "fecha_respuesta" in df.columns:
        m = df["estatus"].eq("Vinculado") & pd.isna(df["fecha_vinculacion"])
        df.loc[m, "fecha_vinculacion"] = df.loc[m, "fecha_respuesta"]
    for c in VINCULACIONES_COLS:
        if c not in df.columns:
            df[c] = None
    df = df[VINCULACIONES_COLS].copy()
    for col in ["id_vinculacion", "id_persona_maestro", "id_registro_origen", "nombre_persona", "empresa",
                "sector_empresa", "tipo_vacante", "area_oportunidad", "estatus", "observaciones", "responsable"]:
        df[col] = df[col].fillna("").astype(str).str.strip()
    df["fecha_vinculacion"] = parsear_fechas(df["fecha_vinculacion"])
    df["fecha_colocacion"] = parsear_fechas(df["fecha_colocacion"])
    df["fecha_actualizacion"] = df["fecha_actualizacion"].fillna("").astype(str)
    df.loc[df["empresa"].eq(""), "empresa"] = "Sin asignar"
    df.loc[df["tipo_vacante"].eq(""), "tipo_vacante"] = "Sin asignar"
    df.loc[df["responsable"].eq(""), "responsable"] = "SEDECO"
    faltan = df["id_vinculacion"].eq("") | df["id_vinculacion"].str.lower().eq("nan")
    if not generar_ids:
        df.loc[faltan, "id_vinculacion"] = ""
    elif faltan.any():
        base = datetime.now().strftime("%Y%m%d%H%M%S")
        df.loc[faltan, "id_vinculacion"] = [f"VIN-{base}-{i + 1}" for i in range(int(faltan.sum()))]
    return df


def asignar_ids_vinculaciones(df: pd.DataFrame, ids_existentes, ahora: datetime | None = None) -> pd.DataFrame:
    """Asigna id_vinculacion (VIN-AAAAMMDDHHMMSS-n) solo a las filas que no lo traen, sin chocar
    con los IDs reales de la base ni con los del propio archivo."""
    df = df.copy()
    ocupados = set(map(str, ids_existentes)) | {x for x in df["id_vinculacion"] if x}
    base = (ahora or datetime.now()).strftime("%Y%m%d%H%M%S")
    n = len(ocupados)
    for idx in df.index[df["id_vinculacion"].eq("")]:
        while True:
            n += 1
            nuevo = f"VIN-{base}-{n}"
            if nuevo not in ocupados:
                break
        ocupados.add(nuevo)
        df.at[idx, "id_vinculacion"] = nuevo
    return df


def validar_vinculaciones(df: pd.DataFrame) -> list[dict]:
    df = df.reset_index(drop=True)
    errores = []
    for i, fila in df.iterrows():
        if not str(fila.get("id_persona_maestro", "")).strip():
            errores.append({"fila": i + 1, "campo": "id_persona_maestro", "error": "Elige a la persona a la que corresponde el seguimiento."})
        if fila.get("estatus") not in ESTATUS_VINCULACION:
            errores.append({"fila": i + 1, "campo": "estatus", "error": "El estatus debe ser Vinculado, Colocado o No vinculado."})
        fv, fc = fila.get("fecha_vinculacion"), fila.get("fecha_colocacion")
        if pd.notna(fv) and pd.notna(fc) and fc < fv:
            errores.append({"fila": i + 1, "campo": "fecha_colocacion", "error": "La fecha de colocación no puede ser anterior a la de vinculación."})
    return errores


def aplicar_duplicados_vinculaciones(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    df = limpiar_vinculaciones(df).copy()
    antes = len(df)
    # Solo el mismo ID de seguimiento es duplicado: una persona puede tener N seguimientos.
    df = df.drop_duplicates(subset=["id_vinculacion"], keep="last")
    return df, antes - len(df)


def estado_por_persona(personas: pd.DataFrame, seguimientos: pd.DataFrame) -> pd.DataFrame:
    """Una fila por persona maestra con su estatus general de seguimiento.

    Regla (igual que la v5): si existe algún seguimiento 'Colocado', cuenta el
    colocado más reciente; si no, el último seguimiento. Sin seguimientos, la
    persona figura 'Vinculado' (su registro histórico ya es una vinculación).
    """
    maestras = obtener_personas_maestras(personas).copy()
    seg = limpiar_vinculaciones(seguimientos, personas)
    if maestras.empty:
        return maestras
    por_maestro = {k: g for k, g in seg.groupby("id_persona_maestro")}
    filas = []
    for _, p in maestras.iterrows():
        g = por_maestro.get(p["id_persona_maestro"])
        r = p.to_dict()
        if g is None or g.empty:
            r.update({"estatus_general": "Vinculado", "seguimientos_empresa": 0, "empresas_contactadas": 0, "empresa_actual": ""})
        else:
            g = g.sort_values(["fecha_actualizacion", "fecha_vinculacion"], na_position="first")
            coloc = g[g["estatus"].eq("Colocado")]
            if not coloc.empty:
                ult = coloc.sort_values(["fecha_colocacion", "fecha_actualizacion"], na_position="first").iloc[-1]
                estatus_general = "Colocado"
            else:
                ult = g.iloc[-1]
                estatus_general = ult["estatus"]
            r.update({
                "estatus_general": estatus_general,
                "seguimientos_empresa": len(g),
                "empresas_contactadas": g.loc[g["empresa"].ne("Sin asignar"), "empresa"].nunique(),
                "empresa_actual": "" if ult["empresa"] == "Sin asignar" else ult["empresa"],
            })
        filas.append(r)
    return pd.DataFrame(filas)
