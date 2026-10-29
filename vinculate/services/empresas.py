"""Empresas: catálogo, ubicación por municipio (captura manual) y vacantes asociadas."""
from __future__ import annotations

import re
from datetime import datetime, timezone

import pandas as pd

from ..auth import servicio as auth_servicio
from ..auth.sesion import Sesion
from ..core.catalogos_vacantes import EMPRESAS_SECTOR
from ..core.constantes import SIN_DATO
from ..core.puntos import parsear_coordenadas, parsear_numero, validar_coordenadas
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


def tiene_coordenadas(df: pd.DataFrame) -> bool:
    """True si la base ya tiene latitud/longitud en el catálogo de empresas (migración V004)."""
    return "latitud" in df.columns and "longitud" in df.columns


_SIN_SECTOR = {"", "sin dato", "indefinido", "nan", "none"}


def _sector_limpio(valor) -> str:
    s = "" if valor is None else str(valor).strip()
    return "" if s.lower() in _SIN_SECTOR else s


def adicionales(vinculaciones: pd.DataFrame | None = None) -> dict[str, str]:
    """Empresas conocidas aunque no tengan vacantes: la lista fija de la app más las que ya tienen seguimientos de vinculación.

    Devuelve {nombre: sector}. No inventa ubicaciones: solo sirve para que esas empresas se puedan ubicar y aparezcan en el mapa."""
    out = {n: _sector_limpio(s) for n, s in EMPRESAS_SECTOR.items()}
    if vinculaciones is not None and not vinculaciones.empty and "empresa" in vinculaciones.columns:
        vistos = {normalizar_texto(n) for n in out}
        for _, r in vinculaciones.drop_duplicates("empresa").iterrows():
            nombre = str(r["empresa"]).strip()
            if nombre and nombre not in ("Sin asignar", SIN_DATO) and normalizar_texto(nombre) not in vistos:
                out[nombre] = _sector_limpio(r.get("sector_empresa"))
                vistos.add(normalizar_texto(nombre))
    return out


def opciones(sesion: Sesion) -> tuple[list[str], dict[str, str]]:
    """Empresas para elegir en los formularios: la lista fija más las que se dieron de alta en el catálogo. (nombres, {nombre: sector})."""
    sector = dict(EMPRESAS_SECTOR)
    try:
        cat = catalogo(sesion)
    except ErrorDatos:
        cat = pd.DataFrame()
    if not cat.empty and "nombre" in cat.columns:
        existentes = {normalizar_texto(n) for n in sector}
        for _, r in cat.iterrows():
            nombre = str(r["nombre"]).strip()
            if nombre and r.get("activo") is not False and normalizar_texto(nombre) not in existentes:
                sector[nombre] = _sector_limpio(r.get("sector"))
    return sorted(sector, key=str.casefold), sector


def directorio(vacantes: pd.DataFrame, catalogo_df: pd.DataFrame, adicional: dict[str, str] | None = None) -> pd.DataFrame:
    """Una fila por empresa: con vacantes, del catálogo o de `adicional` (empresas conocidas sin vacantes), con su ubicación y
    coordenadas capturadas. Nunca inventa nada."""
    res = resumen(vacantes, catalogo_df)
    cols = ["Empresa", "Sector", "Municipio", "Dirección", "C.P.", "Latitud", "Longitud", "Vacantes", "Vigentes"]
    base = res.reindex(columns=["Empresa", "Sector", "Municipio", "Vacantes", "Vigentes"]).copy()
    base["_clave"] = base["Empresa"].map(normalizar_texto)
    extras = []
    c = None
    if not catalogo_df.empty and "nombre" in catalogo_df.columns:
        c = catalogo_df.assign(_clave=catalogo_df["nombre"].map(normalizar_texto)).drop_duplicates("_clave")
        faltan = c[~c["_clave"].isin(base["_clave"])]
        if not faltan.empty:  # empresas del catálogo que aún no tienen vacantes
            extras.append(pd.DataFrame({"Empresa": faltan["nombre"], "Sector": faltan.get("sector", ""),
                                        "Municipio": faltan["municipio"] if "municipio" in faltan.columns else "",
                                        "Vacantes": 0, "Vigentes": 0, "_clave": faltan["_clave"]}))
    if adicional:
        ya = set(base["_clave"]) | ({*c["_clave"]} if c is not None else set())
        nuevas = [(n, s) for n, s in adicional.items() if normalizar_texto(n) not in ya]
        if nuevas:
            extras.append(pd.DataFrame({"Empresa": [n for n, _ in nuevas], "Sector": [s for _, s in nuevas], "Municipio": "",
                                        "Vacantes": 0, "Vigentes": 0, "_clave": [normalizar_texto(n) for n, _ in nuevas]}))
    if extras:
        base = pd.concat([base, *extras], ignore_index=True)
    if c is not None:
        ci = c.set_index("_clave")
        for destino, origen in (("Dirección", "direccion"), ("C.P.", "codigo_postal"), ("Latitud", "latitud"), ("Longitud", "longitud")):
            base[destino] = base["_clave"].map(ci[origen]) if origen in ci.columns else None
        if "municipio" in ci.columns:  # el municipio capturado en el catálogo manda también para empresas «adicionales»
            vacio = base["Municipio"].fillna("").astype(str).str.strip().isin(["", "nan"])
            base.loc[vacio, "Municipio"] = base.loc[vacio, "_clave"].map(ci["municipio"])
        if "sector" in ci.columns:
            vacio = base["Sector"].fillna("").astype(str).str.strip().isin(["", "nan"])
            base.loc[vacio, "Sector"] = base.loc[vacio, "_clave"].map(ci["sector"])
    else:
        for destino in ("Dirección", "C.P.", "Latitud", "Longitud"):
            base[destino] = None
    for col in ("Sector", "Municipio", "Dirección", "C.P."):
        base[col] = base[col].fillna("").astype(str).replace("nan", "")
    base[["Vacantes", "Vigentes"]] = base[["Vacantes", "Vigentes"]].fillna(0).astype(int)
    return base[cols].sort_values(["Vacantes", "Empresa"], ascending=[False, True]).reset_index(drop=True)


def crear(sesion: Sesion, nombre: str, sector: str = "", municipio: str = "", direccion: str = "", codigo_postal: str = "",
          latitud=None, longitud=None, conocidas=()) -> None:
    """Da de alta una empresa nueva en el catálogo (con o sin ubicación). Falla si el nombre ya existe (sin importar mayúsculas ni acentos)."""
    if not sesion.puede("vacantes", "create"):
        raise SinPermiso("Tu perfil no tiene permiso para dar de alta empresas.")
    nombre = " ".join((nombre or "").split())
    if not nombre:
        raise ValueError("Escribe el nombre de la empresa.")
    if normalizar_texto(nombre) in {normalizar_texto(x) for x in conocidas}:
        raise ValueError("Esa empresa ya está en la lista. Para ubicarla usa «Coordenadas exactas (edición rápida)».")
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
    repo = RepoEmpresas(sesion.cliente)
    if repo.obtener(nombre) is not None:
        raise ValueError("Esa empresa ya está en el catálogo.")
    carga = {"nombre": nombre, "sector": (sector or "").strip() or None, "activo": True}
    if municipio or (direccion or "").strip() or cp or lat is not None:
        carga.update({"municipio": municipio or None, "direccion": (direccion or "").strip() or None, "codigo_postal": cp or None,
                      "latitud": lat, "longitud": lon, "ubicacion_fuente": "manual",
                      "ubicacion_actualizada": datetime.now(timezone.utc).isoformat()})
    repo.crear(carga)
    auth_servicio.auditar("empresa_creada", f"empresa={nombre}")


def guardar_coordenadas(sesion: Sesion, empresa: str, latitud, longitud, sector: str | None = None) -> None:
    """Guarda (o borra, si ambas vienen vacías) las coordenadas exactas de una empresa. Valida igual que la base (V004)."""
    if not sesion.puede("vacantes", "edit"):
        raise SinPermiso("Tu perfil no tiene permiso para editar empresas y vacantes.")
    empresa = (empresa or "").strip()
    if not empresa:
        raise ValueError("Elige una empresa.")
    problema = validar_coordenadas(latitud, longitud)
    if problema:
        raise ValueError(problema)
    lat, lon = parsear_numero(latitud), parsear_numero(longitud)
    repo = RepoEmpresas(sesion.cliente)
    previa = repo.obtener(empresa)
    if previa is not None and "latitud" not in previa:
        raise ErrorDatos("La base todavía no tiene las columnas de ubicación de empresas. Aplica la migración V004 en Supabase.")
    carga = {"latitud": lat, "longitud": lon}
    if (previa or {}).get("ubicacion_fuente") in (None, ""):
        carga["ubicacion_fuente"] = "manual"
    repo.guardar_ubicacion(empresa, sector, carga)
    auth_servicio.auditar("empresa_coordenadas", f"empresa={empresa}; " + ("coordenadas borradas" if lat is None else "coordenadas capturadas"))


def guardar_coordenadas_lote(sesion: Sesion, base: pd.DataFrame, editado: pd.DataFrame,
                             col_pegado: str = "Pegar (lat, lon)") -> tuple[list[str], list[str]]:
    """Compara la tabla original con la editada y guarda SOLO las filas que cambiaron.

    Si la celda «pegar» trae algo (p. ej. «19.31390, -98.24040» copiado de Google Maps), tiene prioridad sobre latitud/longitud.
    Devuelve (empresas guardadas, mensajes de error por empresa). Una fila con error no impide guardar las demás."""
    guardadas, errores = [], []
    orig = base.set_index("Empresa")
    sectores = base.set_index("Empresa")["Sector"].to_dict() if "Sector" in base.columns else {}
    for _, f in editado.iterrows():
        nombre = f["Empresa"]
        pegado = f.get(col_pegado)
        if pegado is not None and not pd.isna(pegado) and str(pegado).strip():
            lat, lon = parsear_coordenadas(str(pegado))
            if lat is None:
                errores.append(f"{nombre}: no pude leer «{pegado}». Usa el formato 19.31390, -98.24040.")
                continue
        else:
            lat, lon = parsear_numero(f.get("Latitud")), parsear_numero(f.get("Longitud"))
        antes = (parsear_numero(orig.at[nombre, "Latitud"]), parsear_numero(orig.at[nombre, "Longitud"]))
        if (lat, lon) == antes:
            continue
        try:
            guardar_coordenadas(sesion, nombre, lat, lon, sectores.get(nombre) or None)
            guardadas.append(nombre)
        except (ValueError, ErrorDatos, SinPermiso) as exc:
            errores.append(f"{nombre}: {exc}")
    return guardadas, errores
