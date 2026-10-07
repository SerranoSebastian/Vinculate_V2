"""Utilidades de texto puras."""
from __future__ import annotations

import unicodedata

import pandas as pd

from .constantes import SIN_DATO

_VACIOS = {"", "nan", "none", "nat", "<na>", "null"}


def texto_vacio(valor) -> bool:
    """True si el valor es nulo o una representación textual de "nada"."""
    if valor is None:
        return True
    try:
        if pd.isna(valor):
            return True
    except (TypeError, ValueError):
        pass
    return str(valor).strip().lower() in _VACIOS


def normalizar_texto(valor) -> str:
    """Minúsculas, sin acentos y con espacios colapsados (para comparar)."""
    if valor is None:
        return ""
    try:
        if pd.isna(valor):
            return ""
    except (TypeError, ValueError):
        pass
    texto = str(valor).strip().lower()
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("utf-8")
    return " ".join(texto.split())


def visible(valor, vacio: str = SIN_DATO) -> str:
    """Texto seguro para mostrar: nunca NaN/None/NaT."""
    if texto_vacio(valor):
        return vacio
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return str(valor)


def fecha_visible(valor, formato: str = "%d/%m/%Y", vacio: str = SIN_DATO) -> str:
    """Fecha dd/mm/aaaa o el texto de dato faltante."""
    if texto_vacio(valor):
        return vacio
    try:
        f = pd.to_datetime(valor, errors="coerce")
    except Exception:  # noqa: BLE001
        return vacio
    return vacio if pd.isna(f) else f.strftime(formato)


def parsear_fechas(serie) -> pd.Series:
    """Convierte a fecha sin ambigüedad: primero ISO (AAAA-MM-DD…), y solo si no lo es, día/mes/año.

    Equivale a `pd.to_datetime(..., dayfirst=True, errors="coerce")` pero sin el aviso de pandas
    para fechas ISO y sin leer "2026-04-03" como 4 de marzo.
    """
    s = serie if isinstance(serie, pd.Series) else pd.Series(serie)
    if pd.api.types.is_datetime64_any_dtype(s):
        out = pd.to_datetime(s, errors="coerce")
    else:
        out = pd.to_datetime(s, format="ISO8601", errors="coerce")
        vacio = s.isna() | s.astype(str).str.strip().eq("")
        faltan = out.isna() & ~vacio
        if faltan.any():
            out = out.copy()
            out[faltan] = pd.to_datetime(s[faltan], dayfirst=True, errors="coerce")
    if getattr(out.dt, "tz", None) is not None:
        out = out.dt.tz_localize(None)
    return out


def parsear_fecha(valor):
    """Versión escalar de `parsear_fechas` (devuelve Timestamp o NaT)."""
    return parsear_fechas(pd.Series([valor])).iloc[0]
