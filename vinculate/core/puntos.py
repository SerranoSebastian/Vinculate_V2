"""Puntos exactos de empresas en el mapa (Python puro, sin Streamlit ni Supabase).

* Solo se dibuja lo que alguien CAPTURÓ: una empresa sin latitud/longitud no aparece como punto y se informa aparte.
  Nada se geocodifica ni se estima.
* Cada empresa tiene su propio color (estable: depende de su nombre, no de qué otras estén visibles).
* Si varias empresas comparten exactamente la misma ubicación (mismo parque industrial, mismo edificio), se pueden
  separar VISUALMENTE unos metros en círculo para que ninguna tape a otra. Es solo un ajuste de dibujo: el dato
  guardado y el que muestra el cursor siguen siendo las coordenadas reales.
"""
from __future__ import annotations

import math
import re
import zlib

import pandas as pd

from .texto import normalizar_texto

# Límites que acepta la base (V004) y caja aproximada de Tlaxcala (solo para avisar, no para bloquear).
LAT_MIN, LAT_MAX = 14.0, 33.0
LON_MIN, LON_MAX = -119.0, -86.0
TLAXCALA_LAT = (19.05, 19.80)
TLAXCALA_LON = (-98.80, -97.55)

# 24 colores bien distintos entre sí (Plotly «Dark24»), para diferenciar empresas aunque sean del mismo giro.
PALETA_EMPRESAS = [
    "#2E91E5", "#E15F99", "#1CA71C", "#FB0D0D", "#DA16FF", "#222A2A", "#B68100", "#750D86", "#EB663B", "#511CFB",
    "#00A08B", "#FB00D1", "#FC0080", "#B2828D", "#6C7C32", "#778AAE", "#862A16", "#A777F1", "#620042", "#1616A7",
    "#DA60CA", "#6C4516", "#0D2A63", "#AF0038",
]


def parsear_numero(valor) -> float | None:
    """Número desde texto con coma decimal o espacios; None si está vacío o no es número."""
    if valor is None:
        return None
    try:
        if pd.isna(valor):
            return None
    except (TypeError, ValueError):
        pass
    t = str(valor).strip().replace("°", "").replace(" ", "")
    if t == "" or t.lower() in ("nan", "none", "null"):
        return None
    if t.count(",") == 1 and t.count(".") == 0:
        t = t.replace(",", ".")
    try:
        x = float(t)
    except ValueError:
        return None
    return x if math.isfinite(x) else None


def parsear_coordenadas(texto: str) -> tuple[float | None, float | None]:
    """«19.31390, -98.24040» (lo que copia Google Maps) → (lat, lon). (None, None) si no se reconoce."""
    if texto is None:
        return None, None
    nums = re.findall(r"-?\d+(?:\.\d+)?", str(texto).replace(",", " , ").replace("°", " "))
    if len(nums) != 2:
        return None, None
    return float(nums[0]), float(nums[1])


def validar_coordenadas(lat, lon) -> str | None:
    """None si son válidas; si no, el mensaje (en español) de qué corregir. Ambas vacías es válido (= sin ubicación)."""
    la, lo = parsear_numero(lat), parsear_numero(lon)
    if la is None and lo is None:
        return None
    if (la is None) != (lo is None):
        return "Captura latitud y longitud juntas, o deja las dos vacías."
    if not (LAT_MIN <= la <= LAT_MAX) or not (LON_MIN <= lo <= LON_MAX):
        if LAT_MIN <= lo <= LAT_MAX and LON_MIN <= la <= LON_MAX:
            return "La latitud y la longitud parecen estar invertidas (en Tlaxcala la latitud es ≈ 19.3 y la longitud ≈ −98.2)."
        if la > 0 and lo > 0 and 86 <= lo <= 119:
            return "La longitud de México es NEGATIVA (≈ −98.2). Falta el signo menos."
        return "Las coordenadas están fuera de México. En Tlaxcala la latitud es ≈ 19.3 y la longitud ≈ −98.2."
    return None


def dentro_de_tlaxcala(lat: float, lon: float) -> bool:
    return TLAXCALA_LAT[0] <= lat <= TLAXCALA_LAT[1] and TLAXCALA_LON[0] <= lon <= TLAXCALA_LON[1]


def puntos_validos(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Separa empresas en (con punto válido, sin coordenadas, con coordenadas inválidas). Usa columnas `Latitud`/`Longitud`."""
    if df.empty or "Latitud" not in df.columns:
        vacio = df.iloc[0:0].copy()
        return vacio, df.copy(), vacio
    d = df.copy()
    d["_lat"] = d["Latitud"].map(parsear_numero)
    d["_lon"] = d["Longitud"].map(parsear_numero)
    sin = d["_lat"].isna() & d["_lon"].isna()
    err = d.apply(lambda r: validar_coordenadas(r["_lat"], r["_lon"]), axis=1)
    invalido = ~sin & err.notna()
    ok = d[~sin & ~invalido].copy()
    ok["Latitud"], ok["Longitud"] = ok["_lat"].astype(float), ok["_lon"].astype(float)
    ok["En Tlaxcala"] = [dentro_de_tlaxcala(a, b) for a, b in zip(ok["Latitud"], ok["Longitud"])]
    bad = d[invalido].assign(Problema=err[invalido])
    return ok.drop(columns=["_lat", "_lon"]), d[sin].drop(columns=["_lat", "_lon"]), bad.drop(columns=["_lat", "_lon"])


def color_de_empresa(nombre: str) -> str:
    """Color estable por nombre (mismo nombre → mismo color siempre)."""
    return PALETA_EMPRESAS[zlib.crc32(normalizar_texto(nombre).encode("utf-8")) % len(PALETA_EMPRESAS)]


def asignar_colores(nombres: list[str]) -> dict[str, str]:
    """Un color por empresa, sin repetir mientras haya colores libres (24). Orden estable por nombre normalizado."""
    orden = sorted(dict.fromkeys(nombres), key=normalizar_texto)
    return {n: PALETA_EMPRESAS[i % len(PALETA_EMPRESAS)] for i, n in enumerate(orden)}


def separar_superpuestos(df: pd.DataFrame, metros: float = 40.0) -> pd.DataFrame:
    """Agrega `lat_mapa`/`lon_mapa`: igual a la real, salvo las empresas que comparten la misma ubicación, que se reparten en
    un círculo (radio crece con la cantidad). Solo para dibujar."""
    d = df.copy()
    d["lat_mapa"], d["lon_mapa"] = d["Latitud"], d["Longitud"]
    if d.empty:
        return d
    clave = list(zip(d["Latitud"].round(5), d["Longitud"].round(5)))
    d["_g"] = clave
    for _, grupo in d.groupby("_g"):
        n = len(grupo)
        if n < 2:
            continue
        radio = metros * (1 + (n - 1) // 6)
        for i, idx in enumerate(grupo.sort_values("Empresa").index):
            ang = 2 * math.pi * i / n
            lat0 = float(d.at[idx, "Latitud"])
            d.at[idx, "lat_mapa"] = lat0 + (radio * math.sin(ang)) / 111_320
            d.at[idx, "lon_mapa"] = float(d.at[idx, "Longitud"]) + (radio * math.cos(ang)) / (111_320 * math.cos(math.radians(lat0)))
    return d.drop(columns=["_g"])


def tamano_marcador(vacantes: int | float) -> float:
    """Tamaño del punto: crece suave con las vacantes (mín. 11 px, máx. 22 px)."""
    v = max(int(vacantes or 0), 0)
    return round(min(22.0, 11.0 + 2.2 * math.sqrt(v)), 1)
