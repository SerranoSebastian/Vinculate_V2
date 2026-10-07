"""Exportaciones y respaldos EN MEMORIA (nada se escribe en el disco del servidor).

En Streamlit Cloud el sistema de archivos es efímero, así que el respaldo es una descarga bajo
demanda. El respaldo técnico usa los nombres de columna reales de Supabase (reimportable); las
exportaciones desde las pantallas usan los nombres históricos de la plataforma.
"""
from __future__ import annotations

import io
import re
import zipfile

import pandas as pd

from ..auth import servicio as auth_servicio
from ..auth.sesion import Sesion
from ..repositories.errores import SinPermiso
from ..repositories.tablas import RepoTabla
from .guardado import NOMBRES, ahora_mx

MIME = {"csv": "text/csv", "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "zip": "application/zip"}
_NUMERICO = re.compile(r"^[+-]?[\d\s().,-]+$")


def _neutralizar(valor):
    """Evita inyección de fórmulas al abrir en Excel, sin alterar teléfonos ni números."""
    if isinstance(valor, str) and valor[:1] in "=@+-" and not _NUMERICO.match(valor):
        return "'" + valor
    return valor


def neutralizar_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for c in df.columns:
        if df[c].dtype == object or pd.api.types.is_string_dtype(df[c]):
            df[c] = df[c].map(_neutralizar)
    return df


def _sin_zona(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for c in df.columns:
        if isinstance(df[c].dtype, pd.DatetimeTZDtype):
            df[c] = df[c].dt.tz_localize(None)
    return df


def a_bytes(df: pd.DataFrame, formato: str, hoja: str = "Datos", neutralizar: bool = True) -> bytes:
    df = _sin_zona(neutralizar_df(df) if neutralizar else df)
    if formato == "csv":
        return df.to_csv(index=False).encode("utf-8-sig")
    if formato == "xlsx":
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            df.to_excel(w, index=False, sheet_name=hoja[:31])
        return buf.getvalue()
    raise ValueError("Formato no soportado.")


def exportar_df(sesion: Sesion, modulo: str, df: pd.DataFrame, nombre: str, formato: str = "csv") -> tuple[bytes, str, str]:
    """Exportación de lo que el usuario ya está viendo (filtrado). Exige <módulo>.export y audita."""
    if not sesion.puede(modulo, "export"):
        raise SinPermiso("Tu perfil no tiene permiso para exportar este módulo.")
    datos = a_bytes(df, formato, hoja=nombre)
    archivo = f"{nombre}_{ahora_mx().strftime('%Y%m%d_%H%M')}.{formato}"
    auth_servicio.auditar(f"{modulo}_exportacion", f"archivo={archivo}; filas={len(df)}; formato={formato}")
    return datos, archivo, MIME[formato]


def tablas_respaldables(sesion: Sesion) -> list[str]:
    if not sesion.puede("respaldos", "export"):
        return []
    return [t for t in ("personas", "vacantes", "vinculaciones") if sesion.puede(t, "view")]


def respaldo_zip(sesion: Sesion) -> tuple[bytes, str, dict[str, int]]:
    """ZIP con un CSV por tabla (columnas reales de la base) + LEEME. Exige respaldos.export y ver cada tabla."""
    if not sesion.puede("respaldos", "export"):
        raise SinPermiso("Tu perfil no tiene permiso para generar respaldos.")
    tablas = tablas_respaldables(sesion)
    if not tablas:
        raise SinPermiso("Tu perfil no puede consultar ninguna tabla respaldable.")
    marca = ahora_mx()
    conteos: dict[str, int] = {}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for t in tablas:
            filas = RepoTabla(sesion.cliente, t).listar()
            conteos[t] = len(filas)
            df = pd.DataFrame(filas)
            z.writestr(f"{t}.csv", df.to_csv(index=False).encode("utf-8-sig"))
        leeme = [f"Respaldo de Vincúlate SEDECO — {marca.strftime('%Y-%m-%d %H:%M')} (hora de la Ciudad de México)",
                 f"Generado por: {sesion.email}", "",
                 *[f"{NOMBRES[t]}: {n} registros ({t}.csv)" for t, n in conteos.items()], "",
                 "Contiene datos personales: guárdalo en un lugar seguro y no lo subas a repositorios públicos.",
                 "Los CSV usan los nombres reales de las columnas de Supabase y se pueden reimportar desde el panel de Supabase."]
        z.writestr("LEEME.txt", "\n".join(leeme))
    archivo = f"respaldo_vinculate_{marca.strftime('%Y%m%d_%H%M')}.zip"
    auth_servicio.auditar("respaldo_generado", f"tablas={','.join(tablas)}; registros={sum(conteos.values())}")
    return buf.getvalue(), archivo, conteos
