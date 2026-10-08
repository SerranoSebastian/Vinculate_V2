"""Mapa territorial por municipio: validación de la geometría y conteos (lógica pura).

El mapa SOLO se dibuja con geometría oficial validada (INEGI, entidad 29, 60 municipios). Si no hay
archivo, o no pasa la validación, la página lo dice y muestra la tabla/ranking; nunca se dibuja un
mapa aproximado ni se inventan coordenadas.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from .texto import normalizar_texto, texto_vacio
from .ubicacion import ESTADOS_MEXICO_SIN_TLAXCALA, MUNICIPIOS_TLAXCALA, normalizar_ubicacion_mexico

ENTIDAD_TLAXCALA = "29"
TOTAL_MUNICIPIOS = 60
# Variantes de escritura de INEGI que difieren del catálogo de la app.
ALIAS_GEO = {
    "xaloztoc": "XALOSTOC",
    "yauhquemehcan": "YAUHQUEMECAN",
    "atltzayanca": "ALTZAYANCA",
    "ziltlaltepec": "ZITLALTEPEC DE TRINIDAD SÁNCHEZ SANTOS",
    "ziltlaltepec de trinidad sanchez santos": "ZITLALTEPEC DE TRINIDAD SÁNCHEZ SANTOS",
    "zitlaltepec": "ZITLALTEPEC DE TRINIDAD SÁNCHEZ SANTOS",
    "ixtacuixtla": "IXTACUIXTLA DE MARIANO MATAMOROS",
}
_CLAVES_ENT = ("CVE_ENT", "cve_ent", "CVEENT")
_CLAVES_MUN = ("CVE_MUN", "cve_mun", "CVEMUN")
_CLAVES_GEO = ("CVEGEO", "cvegeo")
_CLAVES_NOMBRE = ("NOMGEO", "nomgeo", "NOM_MUN", "nom_mun", "NOMBRE", "nombre", "NAME", "name", "municipio")
_CATALOGO = {normalizar_texto(m): m for m in MUNICIPIOS_TLAXCALA}
_ESTADOS = {normalizar_texto(e) for e in ESTADOS_MEXICO_SIN_TLAXCALA} | {"otro estado"}


@dataclass
class ResultadoGeo:
    ok: bool
    problemas: list[str] = field(default_factory=list)
    geojson: dict | None = None            # normalizado: properties.municipio = nombre del catálogo
    detalle: dict[str, str] = field(default_factory=dict)  # nombre en el archivo → nombre del catálogo


def _primero(props: dict, claves) -> str:
    for c in claves:
        if c in props and not texto_vacio(props[c]):
            return str(props[c]).strip()
    return ""


def _a_catalogo(nombre_geo: str, usados: set[str]) -> str | None:
    n = normalizar_texto(nombre_geo)
    if n in ALIAS_GEO:
        return ALIAS_GEO[n]
    if n in _CATALOGO:
        return _CATALOGO[n]
    cand = [v for k, v in _CATALOGO.items() if (k.startswith(n) or n.startswith(k)) and v not in usados]
    return cand[0] if len(cand) == 1 and len(n) >= 5 else None


def validar_geojson(gj) -> ResultadoGeo:
    """Acepta un GeoJSON (dict) y devuelve la versión normalizada o la lista exacta de problemas."""
    if not isinstance(gj, dict) or gj.get("type") != "FeatureCollection" or not isinstance(gj.get("features"), list):
        return ResultadoGeo(False, ["El archivo no es un GeoJSON de tipo FeatureCollection."])
    problemas: list[str] = []
    nuevos, usados, detalle = [], set(), {}
    for i, f in enumerate(gj["features"]):
        props = (f or {}).get("properties") or {}
        geom = (f or {}).get("geometry") or {}
        if geom.get("type") not in ("Polygon", "MultiPolygon") or not geom.get("coordinates"):
            problemas.append(f"El elemento {i + 1} no tiene geometría de polígono.")
            continue
        cve_geo = _primero(props, _CLAVES_GEO)
        cve_ent = _primero(props, _CLAVES_ENT) or (cve_geo[:2] if len(cve_geo) >= 2 else "")
        if cve_ent and cve_ent.zfill(2) != ENTIDAD_TLAXCALA:
            problemas.append(f"El elemento {i + 1} es de la entidad {cve_ent}, no de Tlaxcala (29). Filtra el archivo antes de usarlo.")
            continue
        nombre_geo = _primero(props, _CLAVES_NOMBRE)
        cat = _a_catalogo(nombre_geo, usados) if nombre_geo else None
        if not cat:
            problemas.append(f"No se reconoce el municipio «{nombre_geo or 'sin nombre'}» (elemento {i + 1}). "
                             "Agrégalo a ALIAS_GEO en vinculate/core/mapa.py si es solo otra forma de escribirlo.")
            continue
        if cat in usados:
            problemas.append(f"El municipio «{cat}» aparece más de una vez.")
            continue
        usados.add(cat)
        detalle[nombre_geo] = cat
        cve_mun = _primero(props, _CLAVES_MUN) or (cve_geo[2:5] if len(cve_geo) >= 5 else "")
        nuevos.append({"type": "Feature", "geometry": geom,
                       "properties": {"municipio": cat, "cve_ent": ENTIDAD_TLAXCALA, "cve_mun": cve_mun}})
    if not problemas and len(nuevos) != TOTAL_MUNICIPIOS:
        faltan = sorted(set(MUNICIPIOS_TLAXCALA) - usados)
        problemas.append(f"Se esperaban {TOTAL_MUNICIPIOS} municipios y el archivo trae {len(nuevos)}. "
                         f"Faltan: {', '.join(faltan[:8])}{'…' if len(faltan) > 8 else ''}.")
    if problemas:
        return ResultadoGeo(False, problemas, None, detalle)
    return ResultadoGeo(True, [], {"type": "FeatureCollection", "features": nuevos}, detalle)


def _coordenadas(c):
    if c and isinstance(c[0], (int, float)):
        yield c
    else:
        for x in c:
            yield from _coordenadas(x)


def limites(geojson: dict) -> tuple[float, float, float, float] | None:
    """(lon_min, lat_min, lon_max, lat_max) de todas las geometrías, o None si no hay coordenadas."""
    lons, lats = [], []
    for ft in (geojson or {}).get("features", []):
        for lon, lat, *_ in _coordenadas((ft.get("geometry") or {}).get("coordinates") or []):
            lons.append(lon)
            lats.append(lat)
    return (min(lons), min(lats), max(lons), max(lats)) if lons else None


def vista_para(lim: tuple[float, float, float, float], ancho_px: int = 900, alto_px: int = 560) -> tuple[dict, float]:
    """Centro y zoom (escala de teselas de 512 px, como MapLibre) para que `lim` quepa completo con margen."""
    lon0, lat0, lon1, lat1 = lim
    centro = {"lon": (lon0 + lon1) / 2, "lat": (lat0 + lat1) / 2}
    dlon = max(lon1 - lon0, 1e-6)
    # un grado de latitud ocupa 1/cos(lat) más en la proyección Mercator
    dlat = max((lat1 - lat0) / max(math.cos(math.radians(centro["lat"])), 0.2), 1e-6)
    zoom = min(math.log2(ancho_px * 360 / (512 * dlon)), math.log2(alto_px * 360 / (512 * dlat)))
    return centro, round(max(0.0, min(zoom - 0.25, 18.0)), 2)


def cargar_geojson(ruta: Path | str) -> ResultadoGeo | None:
    """None si el archivo no existe (mapa no activado); si existe, se valida."""
    ruta = Path(ruta)
    if not ruta.exists():
        return None
    try:
        with open(ruta, encoding="utf-8") as f:
            return validar_geojson(json.load(f))
    except (OSError, ValueError) as exc:
        return ResultadoGeo(False, [f"No se pudo leer {ruta.name}: {exc}"])


def clasificar_ubicacion(valor) -> tuple[str, str]:
    """('municipio', NOMBRE) | ('estado', NOMBRE) | ('sin_dato', '') | ('otro', texto)."""
    if texto_vacio(valor):
        return "sin_dato", ""
    canon = normalizar_ubicacion_mexico(valor)
    n = normalizar_texto(canon)
    if n in ("indefinido", "sin dato", "informacion no disponible"):
        return "sin_dato", ""
    if canon in MUNICIPIOS_TLAXCALA:
        return "municipio", canon
    if n in _ESTADOS:
        return "estado", canon
    return "otro", str(valor).strip()


def conteos_por_municipio(valores: pd.Series) -> tuple[pd.DataFrame, dict[str, int]]:
    """Conteo de los 60 municipios (incluye ceros) y un resumen de lo que NO es municipio de Tlaxcala."""
    base = pd.Series(0, index=pd.Index(MUNICIPIOS_TLAXCALA, name="Municipio"), dtype="int64")
    otros = {"Fuera de Tlaxcala": 0, "Sin municipio definido": 0, "Ubicación no reconocida": 0}
    for v in valores:
        tipo, nombre = clasificar_ubicacion(v)
        if tipo == "municipio":
            base[nombre] += 1
        elif tipo == "estado":
            otros["Fuera de Tlaxcala"] += 1
        elif tipo == "sin_dato":
            otros["Sin municipio definido"] += 1
        else:
            otros["Ubicación no reconocida"] += 1
    return base.reset_index(name="Total"), otros
