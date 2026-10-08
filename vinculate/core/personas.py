"""Reglas de negocio de personas (puras: sin Streamlit, sin acceso a archivos ni red).

Modelo (se conserva tal cual de la v5):
  * Cada fila de `personas` es una VINCULACIÓN HISTÓRICA (id_persona: I-/A-/P-/S-…).
  * Una PERSONA es el grupo de filas con el mismo `id_persona_maestro` (PER-0001).
"""
from __future__ import annotations

import pandas as pd

from .constantes import (
    ALIASES_PERSONAS, PERSONAS_COLS, PERSONAS_COLS_OPCIONALES, PREFIJOS_VINCULACION,
    TIPOS_VINCULACION,
)
from .normalizacion import SINONIMOS
from .texto import normalizar_texto, parsear_fechas, texto_vacio
from .ubicacion import normalizar_ubicacion_mexico

_COLUMNAS_TEXTO = [
    "id_persona", "id_persona_maestro", "nombre", "sexo", "escolaridad", "carrera",
    "Institución", "id_institucion", "municipio", "id_municipio", "telefono", "correo",
    "grupo_prioritario", "vinculacion", "Año", "area_carrera", "estatus_vinculacion",
]
GRUPOS_EDAD_BINS = [0, 17, 24, 29, 39, 49, 59, 100]
GRUPOS_EDAD_LABELS = ["Menor de 18", "18 a 24", "25 a 29", "30 a 39", "40 a 49", "50 a 59", "60 o más"]


def _renombrar_aliases(df: pd.DataFrame) -> pd.DataFrame:
    ren, existentes = {}, set(df.columns)
    for c in df.columns:
        key = c.strip().lower()
        if key in ALIASES_PERSONAS:
            destino = ALIASES_PERSONAS[key]
            # No renombrar si el destino oficial ya existe (evita columnas duplicadas).
            if c != destino and destino not in existentes:
                ren[c] = destino
                existentes.add(destino)
    return df.rename(columns=ren)


def siguiente_numero_maestro(serie) -> int:
    nums = pd.to_numeric(pd.Series(serie, dtype=str).str.extract(r"PER-(\d+)", expand=False), errors="coerce")
    return int(nums.max()) + 1 if nums.notna().any() else 1


def siguiente_numero_general_vinculacion(serie) -> int:
    nums = pd.to_numeric(pd.Series(serie, dtype=str).str.extract(r"-(\d+)$", expand=False), errors="coerce")
    return int(nums.max()) + 1 if nums.notna().any() else 1


def siguiente_numero_tipo(serie, prefijo: str) -> int:
    nums = pd.to_numeric(pd.Series(serie, dtype=str).str.extract(rf"^{prefijo}-(\d+)-", expand=False), errors="coerce")
    return int(nums.max()) + 1 if nums.notna().any() else 1


def _redaccion_sexo(valor: str) -> str:
    return SINONIMOS.get(normalizar_texto(valor), valor)


def _primera_mayuscula(valor: str) -> str:
    """«superior» → «Superior». No toca el resto (ni siglas ni nombres propios)."""
    return valor[:1].upper() + valor[1:] if valor and valor[0].islower() else valor


def limpiar_personas(df: pd.DataFrame, generar_ids: bool = True) -> pd.DataFrame:
    """Normaliza tipos sin destruir la diferencia entre vacío e 'Indefinido'.

    `generar_ids=False` deja vacíos los IDs faltantes (el servicio de guardado los asigna
    contra los IDs reales de la base para evitar colisiones).
    """
    df = df.copy()
    df.columns = df.columns.astype(str).str.strip()
    df = _renombrar_aliases(df)

    if not df.empty:
        tiene_datos = df.apply(lambda col: col.map(lambda v: pd.notna(v) and str(v).strip() != "")).any(axis=1)
        df = df.loc[tiene_datos].copy()

    opcionales = [c for c in PERSONAS_COLS_OPCIONALES if c in df.columns]
    for c in PERSONAS_COLS:
        if c not in df.columns:
            df[c] = None
    df = df[PERSONAS_COLS + opcionales]

    for col in _COLUMNAS_TEXTO + opcionales:
        df[col] = (
            df[col].astype("object").where(pd.notna(df[col]), "").astype(str).str.strip()
            .str.replace(r"\.0$", "", regex=True)
        )
    df["correo"] = df["correo"].str.lower()
    df["sexo"] = df["sexo"].map(_redaccion_sexo)          # «MASCULINO», «masculino» → «Masculino»
    df["escolaridad"] = df["escolaridad"].map(_primera_mayuscula)
    df["municipio"] = df["municipio"].apply(normalizar_ubicacion_mexico)
    # Todo registro histórico representa una vinculación confirmada en el esquema actual.
    df["estatus_vinculacion"] = "Vinculado"
    df["edad"] = pd.to_numeric(df["edad"], errors="coerce")
    df["fecha_registro"] = parsear_fechas(df["fecha_registro"])

    # Año explícito se conserva; si está vacío y hay fecha, se deriva de la fecha.
    anio_fecha = df["fecha_registro"].dt.year.astype("Int64").astype(str).replace("<NA>", "")
    vacio = df["Año"].eq("") | df["Año"].str.lower().isin(["nan", "none"])
    df.loc[vacio, "Año"] = anio_fecha[vacio]

    # IDs faltantes: se generan sin colapsar registros repetidos.
    faltan_maestro = df["id_persona_maestro"].eq("") | df["id_persona_maestro"].str.lower().eq("nan")
    if generar_ids and faltan_maestro.any():
        inicio = siguiente_numero_maestro(df.loc[~faltan_maestro, "id_persona_maestro"])
        df.loc[faltan_maestro, "id_persona_maestro"] = [f"PER-{inicio + i:04d}" for i in range(int(faltan_maestro.sum()))]

    faltan_registro = df["id_persona"].eq("") | df["id_persona"].str.lower().eq("nan")
    if generar_ids and faltan_registro.any():
        general = siguiente_numero_general_vinculacion(df.loc[~faltan_registro, "id_persona"])
        contadores = {
            t: siguiente_numero_tipo(df.loc[~faltan_registro, "id_persona"], PREFIJOS_VINCULACION[t])
            for t in TIPOS_VINCULACION
        }
        nuevos = []
        for _, r in df.loc[faltan_registro].iterrows():
            tipo = r["vinculacion"] if r["vinculacion"] in PREFIJOS_VINCULACION else "Atención"
            nuevos.append(f"{PREFIJOS_VINCULACION[tipo]}-{contadores[tipo]:05d}-{general:05d}")
            contadores[tipo] += 1
            general += 1
        df.loc[faltan_registro, "id_persona"] = nuevos
    if not generar_ids:
        for c in ("id_persona", "id_persona_maestro"):
            df.loc[df[c].str.lower().eq("nan"), c] = ""
    return df


def asignar_ids_personas(df: pd.DataFrame, ids_existentes, maestros_existentes) -> pd.DataFrame:
    """Asigna id_persona / id_persona_maestro SOLO a las filas que no los traen, tomando como
    base los IDs reales de la base de datos (no solo los del archivo)."""
    df = df.copy()
    usados = set(map(str, ids_existentes)) | {x for x in df["id_persona"] if x}
    base = pd.Series(sorted(usados), dtype=str)
    general = siguiente_numero_general_vinculacion(base)
    contadores = {t: siguiente_numero_tipo(base, PREFIJOS_VINCULACION[t]) for t in TIPOS_VINCULACION}
    maestros = set(map(str, maestros_existentes)) | {x for x in df["id_persona_maestro"] if x}
    n_maestro = siguiente_numero_maestro(pd.Series(sorted(maestros), dtype=str))
    for idx in df.index:
        if df.at[idx, "id_persona"] == "":
            tipo = df.at[idx, "vinculacion"] if df.at[idx, "vinculacion"] in PREFIJOS_VINCULACION else "Atención"
            df.at[idx, "id_persona"] = f"{PREFIJOS_VINCULACION[tipo]}-{contadores[tipo]:05d}-{general:05d}"
            contadores[tipo] += 1
            general += 1
        if df.at[idx, "id_persona_maestro"] == "":
            df.at[idx, "id_persona_maestro"] = f"PER-{n_maestro:04d}"
            n_maestro += 1
    return df


def generar_id_registro_vinculacion(df: pd.DataFrame, tipo: str) -> str:
    df = limpiar_personas(df)
    pref = PREFIJOS_VINCULACION.get(tipo, "A")
    return f"{pref}-{siguiente_numero_tipo(df['id_persona'], pref):05d}-{siguiente_numero_general_vinculacion(df['id_persona']):05d}"


def generar_id_persona_maestro(df: pd.DataFrame) -> str:
    df = limpiar_personas(df)
    return f"PER-{siguiente_numero_maestro(df['id_persona_maestro']):04d}"


def preparar_personas_dashboard(df: pd.DataFrame) -> pd.DataFrame:
    df = limpiar_personas(df)
    df["mes"] = df["fecha_registro"].dt.to_period("M").astype(str).replace("NaT", "")
    df["año"] = pd.to_numeric(df["Año"], errors="coerce").astype("Int64")
    df["grupo_edad"] = pd.cut(df["edad"], bins=GRUPOS_EDAD_BINS, labels=GRUPOS_EDAD_LABELS)
    return df


_COLS_PERSONA = ["nombre", "sexo", "edad", "escolaridad", "carrera", "Institución", "municipio",
                 "telefono", "correo", "grupo_prioritario", "area_carrera"]


def obtener_personas_maestras(df: pd.DataFrame) -> pd.DataFrame:
    """Una fila por persona maestra, con el dato más informativo/reciente disponible."""
    df = preparar_personas_dashboard(df).copy()
    if df.empty:
        return df
    df["_fecha_ord"] = df["fecha_registro"].fillna(pd.Timestamp("1900-01-01"))
    df = df.sort_values(["id_persona_maestro", "_fecha_ord"], kind="stable")
    filas = []
    for _, g in df.groupby("id_persona_maestro", dropna=False):
        base = g.iloc[-1].copy()
        for col in _COLS_PERSONA:
            validos = g[col].dropna().astype(str)
            validos = validos[~validos.str.strip().str.lower().isin(["", "nan", "none", "indefinido"])]
            if len(validos):
                base[col] = validos.iloc[-1]
        base["total_vinculaciones"] = len(g)
        base["primera_fecha"] = g["fecha_registro"].min()
        base["ultima_fecha"] = g["fecha_registro"].max()
        base["tipos_vinculacion"] = ", ".join(sorted({x for x in g["vinculacion"] if str(x).strip()}))
        anios = pd.to_numeric(g["Año"], errors="coerce").dropna().astype(int)
        base["años_con_registro"] = ", ".join(map(str, sorted(anios.unique())))
        filas.append(base)
    out = pd.DataFrame(filas).drop(columns=["_fecha_ord"], errors="ignore")
    return out.reset_index(drop=True)


def resumen_vinculaciones_por_persona(df: pd.DataFrame) -> pd.DataFrame:
    df = preparar_personas_dashboard(df)
    if df.empty:
        return pd.DataFrame(columns=["id_persona_maestro", "nombre", "total_vinculaciones", "primera_fecha", "ultima_fecha"])
    nombres = obtener_personas_maestras(df).set_index("id_persona_maestro")["nombre"]
    res = df.groupby("id_persona_maestro").agg(
        total_vinculaciones=("id_persona", "count"),
        primera_fecha=("fecha_registro", "min"),
        ultima_fecha=("fecha_registro", "max"),
    ).reset_index()
    res["nombre"] = res["id_persona_maestro"].map(nombres)
    return res[["id_persona_maestro", "nombre", "total_vinculaciones", "primera_fecha", "ultima_fecha"]].sort_values(
        ["total_vinculaciones", "nombre"], ascending=[False, True]
    )


def validar_personas(df: pd.DataFrame) -> list[dict]:
    df = limpiar_personas(df)
    errores = []
    for i, fila in df.reset_index(drop=True).iterrows():
        if texto_vacio(fila.get("nombre")):
            errores.append({"fila": i + 1, "campo": "nombre", "error": "El nombre es obligatorio."})
        if texto_vacio(fila.get("id_persona_maestro")):
            errores.append({"fila": i + 1, "campo": "id_persona_maestro", "error": "Cada registro debe asociarse a una persona maestra."})
        edad = fila.get("edad")
        if pd.notna(edad) and (edad <= 0 or edad > 120):
            errores.append({"fila": i + 1, "campo": "edad", "error": "La edad debe estar entre 1 y 120."})
    return errores


def aplicar_duplicados_personas(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Solo un ID de registro idéntico es duplicado. Nombres repetidos son vinculaciones válidas."""
    df = limpiar_personas(df).copy()
    antes = len(df)
    df = df.drop_duplicates(subset=["id_persona"], keep="last")
    return df, antes - len(df)
