"""Mapeo entre los DataFrames de la app (nombres históricos) y las tablas SQL (snake_case).

Puro: convierte DataFrames a filas JSON y viceversa. Sin red ni Streamlit.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

import pandas as pd

from .texto import parsear_fecha

TABLAS: dict[str, dict[str, Any]] = {
    "personas": {
        "table": "personas", "pk": "id_persona", "modulo": "personas",
        "map": {
            "id_persona": "id_persona", "id_persona_maestro": "id_persona_maestro",
            "nombre": "nombre", "sexo": "sexo", "edad": "edad", "escolaridad": "escolaridad",
            "carrera": "carrera", "Institución": "institucion", "id_institucion": "id_institucion",
            "municipio": "municipio", "id_municipio": "id_municipio", "telefono": "telefono",
            "correo": "correo", "grupo_prioritario": "grupo_prioritario", "vinculacion": "vinculacion",
            "fecha_registro": "fecha_registro", "Año": "anio", "area_carrera": "area_carrera",
            "estatus_vinculacion": "estatus_vinculacion",
        },
        # Existen solo tras V005; se leen/escriben únicamente si la columna está en la base.
        "opcionales": {"anio_fuente": "anio_fuente", "institucion_fuente": "institucion_fuente"},
        "integers": {"edad", "anio"}, "dates": {"fecha_registro"},
    },
    "vacantes": {
        "table": "vacantes", "pk": "id_vacante", "modulo": "vacantes",
        "map": {
            "ID Vacante": "id_vacante", "ID Registro Origen": "id_registro_origen",
            "Actividad": "actividad", "Fecha": "fecha", "Empresa": "empresa",
            "Sector Empresa": "sector_empresa", "Puesto Original": "puesto_original",
            "Tipo de Vacante": "tipo_vacante", "Categoría de Puesto": "categoria_puesto",
            "Tipo de Oportunidad": "tipo_oportunidad", "Área de Oportunidad": "area_oportunidad",
            "Descripción": "descripcion", "Requisitos": "requisitos", "Beneficios": "beneficios",
            "Link de la Publicación": "link_publicacion", "Estado": "estado",
        },
        "opcionales": {"fecha_cierre": "fecha_cierre", "municipio_excepcion": "municipio_excepcion"},
        "integers": set(), "dates": {"fecha", "fecha_cierre"},
    },
    "vinculaciones": {
        "table": "vinculaciones", "pk": "id_vinculacion", "modulo": "vinculaciones",
        "map": {
            "id_vinculacion": "id_vinculacion", "id_persona_maestro": "id_persona_maestro",
            "id_registro_origen": "id_registro_origen", "nombre_persona": "nombre_persona",
            "empresa": "empresa", "sector_empresa": "sector_empresa", "tipo_vacante": "tipo_vacante",
            "area_oportunidad": "area_oportunidad", "estatus": "estatus",
            "fecha_vinculacion": "fecha_vinculacion", "fecha_colocacion": "fecha_colocacion",
            "observaciones": "observaciones", "responsable": "responsable",
            "fecha_actualizacion": "fecha_actualizacion",
        },
        "opcionales": {},
        "integers": set(), "dates": {"fecha_vinculacion", "fecha_colocacion"},
    },
    "historial": {
        "table": "historial_cargas", "pk": "id", "modulo": "administracion",
        "map": {
            "fecha_hora": "fecha_hora", "usuario": "usuario", "base": "base", "origen": "origen",
            "archivo_origen": "archivo_origen", "registros_recibidos": "registros_recibidos",
            "registros_guardados": "registros_guardados", "duplicados_actualizados": "duplicados_actualizados",
            "total_final": "total_final",
        },
        "opcionales": {},
        "integers": {"registros_recibidos", "registros_guardados", "duplicados_actualizados", "total_final"},
        "dates": set(),
    },
}


def _escalar(v):
    """Convierte cualquier valor de pandas/numpy a algo serializable (o None)."""
    if v is None:
        return None
    if not isinstance(v, (list, dict)):
        try:
            if pd.isna(v):
                return None
        except (TypeError, ValueError):
            pass
    if isinstance(v, pd.Timestamp):
        return v.isoformat()
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if hasattr(v, "item"):
        try:
            v = v.item()
        except Exception:  # noqa: BLE001
            pass
    if isinstance(v, str):
        s = v.strip()
        return None if s.lower() in {"", "nan", "none", "nat", "<na>"} else s
    return v


def _entero(v, campo: str):
    """Acepta 22, 22.0, numpy.int64, '22' y '22.0'; rechaza decimales reales."""
    v = _escalar(v)
    if v is None:
        return None
    try:
        n = float(v)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"El campo {campo} debe ser entero; se recibió {v!r}.") from exc
    if not n.is_integer():
        raise ValueError(f"El campo {campo} debe ser entero; se recibió {v!r}.")
    return int(n)


def _fecha(v, campo: str):
    """Fecha ISO YYYY-MM-DD apta para columnas DATE."""
    v = _escalar(v)
    if v is None:
        return None
    if isinstance(v, str):
        parsed = parsear_fecha(v)
        if pd.isna(parsed):
            raise ValueError(f"El campo {campo} contiene una fecha inválida: {v!r}.")
        return parsed.date().isoformat()
    if isinstance(v, datetime):
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    parsed = pd.to_datetime(v, errors="coerce")
    if pd.isna(parsed):
        raise ValueError(f"El campo {campo} contiene una fecha inválida: {v!r}.")
    return parsed.date().isoformat()


def columnas_locales(tipo: str, incluir_opcionales: bool = False) -> list[str]:
    cfg = TABLAS[tipo]
    cols = list(cfg["map"].keys())
    if incluir_opcionales:
        cols += list(cfg["opcionales"].keys())
    return cols


def a_filas_sql(tipo: str, df: pd.DataFrame, columnas_extra_ok: set[str] | None = None) -> list[dict]:
    """DataFrame (nombres históricos) → filas listas para PostgREST.

    `columnas_extra_ok`: nombres SQL de columnas opcionales que SÍ existen en la base.
    """
    cfg = TABLAS[tipo]
    mp = dict(cfg["map"])
    for local, remoto in cfg["opcionales"].items():
        if columnas_extra_ok and remoto in columnas_extra_ok:
            mp[local] = remoto
    enteros, fechas = cfg["integers"], cfg["dates"]
    filas = []
    for _, r in df.iterrows():
        fila = {}
        for local, remoto in mp.items():
            if local not in df.columns:
                continue
            valor = r[local]
            if remoto in enteros:
                fila[remoto] = _entero(valor, local)
            elif remoto in fechas:
                fila[remoto] = _fecha(valor, local)
            else:
                fila[remoto] = _escalar(valor)
        filas.append(fila)
    return filas


def a_dataframe(tipo: str, filas: list[dict]) -> pd.DataFrame:
    """Filas de PostgREST → DataFrame con nombres históricos (más opcionales presentes)."""
    cfg = TABLAS[tipo]
    inv = {v: k for k, v in cfg["map"].items()}
    cols = list(cfg["map"].keys())
    if not filas:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(filas)
    extras = [c for c in cfg["opcionales"].values() if c in df.columns]
    df = df.rename(columns=inv)
    for c in cols:
        if c not in df.columns:
            df[c] = ""
    return df[cols + extras]
