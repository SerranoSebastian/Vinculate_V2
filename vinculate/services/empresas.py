"""Empresas: catálogo, ubicación por municipio (captura manual) y vacantes asociadas."""
from __future__ import annotations

import re

import pandas as pd

from ..auth import servicio as auth_servicio
from ..auth.sesion import Sesion
from ..core.texto import normalizar_texto
from ..core.ubicacion import MUNICIPIOS_TLAXCALA
from ..repositories.catalogos import RepoEmpresas
from ..repositories.errores import ErrorDatos, SinPermiso

FUERA_DE_TLAXCALA = "Fuera de Tlaxcala"
COLS_UBICACION = ["municipio", "direccion", "codigo_postal", "ubicacion_fuente"]


def catalogo(sesion: Sesion) -> pd.DataFrame:
    """Catálogo de empresas tal como está en la base (con ubicación si V004 ya se aplicó)."""
    df = pd.DataFrame(RepoEmpresas(sesion.cliente).listar())
    if df.empty:
        df = pd.DataFrame(columns=["nombre", "sector", "activo"])
    return df


def tiene_ubicacion(df: pd.DataFrame) -> bool:
    """True si la base ya tiene las columnas de ubicación (migración V004)."""
    return "municipio" in df.columns


def resumen(vacantes: pd.DataFrame, catalogo_df: pd.DataFrame) -> pd.DataFrame:
    """Una fila por empresa con vacantes, y su ubicación si existe. Nunca inventa un municipio."""
    if vacantes.empty:
        return pd.DataFrame(columns=["Empresa", "Vacantes", "Vigentes", "Puestos distintos", "Sector", "Municipio", "Ubicación"])
    v = vacantes.copy()
    v["_clave"] = v["Empresa"].map(normalizar_texto)
    g = v.groupby("_clave").agg(Empresa=("Empresa", lambda s: s.mode().iloc[0]), Vacantes=("ID Vacante", "count"),
                                Activas=("Estado", lambda s: int((s == "Activa").sum())),
                                **{"Puestos distintos": ("Tipo de Vacante", "nunique")},
                                Sector=("Sector Empresa", lambda s: next((x for x in s if str(x).strip()), ""))).reset_index()
    if "fecha_cierre" in v.columns:
        from ..core.vacantes import vigentes_mask
        vig = v.assign(_v=vigentes_mask(v)).groupby("_clave")["_v"].sum().astype(int)
        g["Vigentes"] = g["_clave"].map(vig).fillna(0).astype(int)
    else:
        g["Vigentes"] = g["Activas"]
    g = g.drop(columns=["Activas"])
    if tiene_ubicacion(catalogo_df) and not catalogo_df.empty:
        c = catalogo_df.assign(_clave=catalogo_df["nombre"].map(normalizar_texto)).drop_duplicates("_clave").set_index("_clave")
        g["Municipio"] = g["_clave"].map(c["municipio"]).fillna("")
        g["Ubicación"] = g["_clave"].map(c.get("ubicacion_fuente", pd.Series(dtype=str))).fillna("")
    else:
        g["Municipio"] = ""
        g["Ubicación"] = ""
    return g.drop(columns=["_clave"]).sort_values(["Vacantes", "Empresa"], ascending=[False, True]).reset_index(drop=True)


def guardar_ubicacion(sesion: Sesion, empresa: str, municipio: str, direccion: str = "", codigo_postal: str = "",
                      sector: str | None = None) -> None:
    if not sesion.puede("vacantes", "edit"):
        raise SinPermiso("Tu perfil no tiene permiso para editar empresas y vacantes.")
    empresa = (empresa or "").strip()
    if not empresa:
        raise ValueError("Elige una empresa.")
    if municipio not in MUNICIPIOS_TLAXCALA and municipio != FUERA_DE_TLAXCALA:
        raise ValueError("Elige uno de los 60 municipios de Tlaxcala o «Fuera de Tlaxcala».")
    cp = (codigo_postal or "").strip()
    if cp and not re.fullmatch(r"\d{5}", cp):
        raise ValueError("El código postal debe tener 5 dígitos.")
    carga = {"municipio": municipio, "direccion": (direccion or "").strip() or None,
             "codigo_postal": cp or None, "ubicacion_fuente": "manual"}
    repo = RepoEmpresas(sesion.cliente)
    previa = repo.obtener(empresa)
    if previa is not None and "municipio" not in previa:
        raise ErrorDatos("La base todavía no tiene las columnas de ubicación de empresas. Aplica la migración V004 en Supabase.")
    repo.guardar_ubicacion(empresa, sector, carga)
    auth_servicio.auditar("empresa_ubicacion", f"empresa={empresa}; municipio={municipio}")
