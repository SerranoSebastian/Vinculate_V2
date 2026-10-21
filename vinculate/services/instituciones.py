"""Instituciones educativas: directorio (solo las que ya tienen personas), tipo y ubicación exacta (captura manual)."""
from __future__ import annotations

import re

import pandas as pd

from ..auth import servicio as auth_servicio
from ..auth.sesion import Sesion
from ..core.constantes import SIN_DATO
from ..core.puntos import parsear_coordenadas, parsear_numero, validar_coordenadas
from ..core.texto import normalizar_texto
from ..core.ubicacion import MUNICIPIOS_TLAXCALA
from ..repositories.catalogos import RepoInstituciones
from ..repositories.errores import ErrorDatos, SinPermiso

FUERA_DE_TLAXCALA = "Fuera de Tlaxcala"
TIPOS = ("Universidad", "Escuela")
COLUMNAS = ["Institución", "Tipo", "Municipio", "Dirección", "C.P.", "Latitud", "Longitud", "Personas", "Asignadas por balanceo"]


def catalogo(sesion: Sesion) -> pd.DataFrame:
    df = pd.DataFrame(RepoInstituciones(sesion.cliente).listar())
    if df.empty:
        df = pd.DataFrame(columns=["nombre", "activo"])
    return df


def tiene_coordenadas(df: pd.DataFrame) -> bool:
    """True si la base ya tiene las columnas de ubicación de instituciones (migración V011)."""
    return "latitud" in df.columns and "longitud" in df.columns


def habilitada(sesion: Sesion) -> bool:
    """True si la migración V011 ya está aplicada en la base."""
    return RepoInstituciones(sesion.cliente).columnas_de_ubicacion()


def _vacio(valor) -> bool:
    return valor is None or str(valor).strip() == "" or str(valor).strip().lower() in ("nan", "none", "nat") or str(valor).strip() == SIN_DATO


def directorio(personas: pd.DataFrame, catalogo_df: pd.DataFrame) -> pd.DataFrame:
    """Una fila por institución que YA tiene al menos una persona asociada, con su tipo y ubicación si alguien las capturó.

    Nunca inventa nada: lo que no está capturado queda vacío. «Personas» cuenta personas distintas."""
    if personas.empty or "Institución" not in personas.columns:
        return pd.DataFrame(columns=COLUMNAS)
    p = personas[~personas["Institución"].map(_vacio)].copy()
    if p.empty:
        return pd.DataFrame(columns=COLUMNAS)
    p["_clave"] = p["Institución"].astype(str).map(normalizar_texto)
    col_id = "id_persona_maestro" if "id_persona_maestro" in p.columns else "Institución"
    p["_bal"] = p["institucion_fuente"].eq("balanceado") if "institucion_fuente" in p.columns else False
    g = p.groupby("_clave").agg(Institución=("Institución", lambda s: s.astype(str).mode().iloc[0]),
                                Personas=(col_id, "nunique"), **{"Asignadas por balanceo": ("_bal", "sum")}).reset_index()
    g["Asignadas por balanceo"] = g["Asignadas por balanceo"].astype(int)
    if not catalogo_df.empty and "nombre" in catalogo_df.columns:
        c = catalogo_df.assign(_clave=catalogo_df["nombre"].astype(str).map(normalizar_texto)).drop_duplicates("_clave").set_index("_clave")
        for destino, origen in (("Tipo", "tipo"), ("Municipio", "municipio"), ("Dirección", "direccion"), ("C.P.", "codigo_postal"),
                                ("Latitud", "latitud"), ("Longitud", "longitud")):
            g[destino] = g["_clave"].map(c[origen]) if origen in c.columns else None
    else:
        for destino in ("Tipo", "Municipio", "Dirección", "C.P.", "Latitud", "Longitud"):
            g[destino] = None
    for col in ("Tipo", "Municipio", "Dirección", "C.P."):
        g[col] = g[col].fillna("").astype(str).replace("nan", "")
    return g[COLUMNAS].sort_values(["Personas", "Institución"], ascending=[False, True]).reset_index(drop=True)


def guardar(sesion: Sesion, institucion: str, tipo: str, municipio: str, latitud, longitud,
            direccion: str = "", codigo_postal: str = "") -> None:
    """Guarda tipo, municipio y coordenadas de una institución (las vacías se guardan como «sin dato»). Solo administración."""
    if not sesion.puede("administracion", "edit"):
        raise SinPermiso("Solo administración puede capturar la ubicación de las instituciones.")
    institucion = (institucion or "").strip()
    if not institucion:
        raise ValueError("Elige una institución.")
    tipo = (tipo or "").strip()
    if tipo and tipo not in TIPOS:
        raise ValueError("El tipo debe ser «Universidad» o «Escuela».")
    municipio = (municipio or "").strip()
    if municipio and municipio not in MUNICIPIOS_TLAXCALA and municipio != FUERA_DE_TLAXCALA:
        raise ValueError("Elige uno de los 60 municipios de Tlaxcala o «Fuera de Tlaxcala».")
    cp = (codigo_postal or "").strip()
    if cp and not re.fullmatch(r"\d{5}", cp):
        raise ValueError("El código postal debe tener 5 dígitos.")
    problema = validar_coordenadas(latitud, longitud)
    if problema:
        raise ValueError(problema)
    lat, lon = parsear_numero(latitud), parsear_numero(longitud)
    repo = RepoInstituciones(sesion.cliente)
    previa = repo.obtener(institucion)
    if previa is not None and "latitud" not in previa:
        raise ErrorDatos("La base todavía no tiene las columnas de ubicación de instituciones. Aplica la migración V011 en Supabase.")
    carga = {"tipo": tipo or None, "municipio": municipio or None, "direccion": (direccion or "").strip() or None,
             "codigo_postal": cp or None, "latitud": lat, "longitud": lon, "ubicacion_fuente": "manual"}
    repo.guardar_ubicacion(institucion, carga)
    auth_servicio.auditar("institucion_ubicacion", f"institucion={institucion}; tipo={tipo or 'sin tipo'}; "
                          + ("coordenadas borradas" if lat is None else "coordenadas capturadas"))


def guardar_lote(sesion: Sesion, base: pd.DataFrame, editado: pd.DataFrame,
                 col_pegado: str = "Pegar (lat, lon)") -> tuple[list[str], list[str]]:
    """Compara la tabla original con la editada y guarda SOLO las filas que cambiaron (tipo, municipio o coordenadas).

    La celda «pegar» (p. ej. «19.31390, -98.24040» de Google Maps) tiene prioridad sobre latitud/longitud.
    Devuelve (instituciones guardadas, errores). Una fila con error no impide guardar las demás."""
    guardadas, errores = [], []
    orig = base.set_index("Institución")
    for _, f in editado.iterrows():
        nombre = f["Institución"]
        pegado = f.get(col_pegado)
        if pegado is not None and not pd.isna(pegado) and str(pegado).strip():
            lat, lon = parsear_coordenadas(str(pegado))
            if lat is None:
                errores.append(f"{nombre}: no pude leer «{pegado}». Usa el formato 19.31390, -98.24040.")
                continue
        else:
            lat, lon = parsear_numero(f.get("Latitud")), parsear_numero(f.get("Longitud"))
        tipo = "" if _vacio(f.get("Tipo")) else str(f["Tipo"])
        municipio = "" if _vacio(f.get("Municipio")) else str(f["Municipio"])
        o = orig.loc[nombre]
        antes = (parsear_numero(o["Latitud"]), parsear_numero(o["Longitud"]), "" if _vacio(o["Tipo"]) else str(o["Tipo"]),
                 "" if _vacio(o["Municipio"]) else str(o["Municipio"]))
        if (lat, lon, tipo, municipio) == antes:
            continue
        try:
            guardar(sesion, nombre, tipo, municipio, lat, lon, direccion=str(o["Dirección"] or ""), codigo_postal=str(o["C.P."] or ""))
            guardadas.append(nombre)
        except (ValueError, ErrorDatos, SinPermiso) as exc:
            errores.append(f"{nombre}: {exc}")
    return guardadas, errores
