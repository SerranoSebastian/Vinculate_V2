"""Imputación proporcional de datos faltantes (carrera, institución, sexo, etc.).

Método (probabilidad frecuencial o empírica, «distribución proporcional»):
  1. Se cuenta cuántas PERSONAS tienen cada valor conocido de la columna (cada persona cuenta una sola vez).
  2. La proporción de un valor es: personas con ese valor ÷ personas con dato conocido.
  3. A las personas sin dato se les reparte la columna según esas proporciones: si el 20 % de quienes sí tienen dato
     estudió «Derecho», aproximadamente el 20 % de quienes no lo tienen recibe «Derecho».
  4. El reparto es determinista (siempre da lo mismo con los mismos datos) y exacto (a ±1 persona por valor):
     se ordena a las personas sin dato con un código estable derivado de su ID y se asignan en tramos de la distribución.
  5. Si una persona sí tiene el dato en otro de sus registros, se usa ese dato real y no se imputa nada.

Límites que conviene conocer: el reparto conserva la distribución del conjunto, así que sirve para totales y gráficas;
el valor asignado a una persona en particular NO es un hecho sobre ella. Por eso cada valor imputado queda marcado
(columnas «<columna>_imputado» y «datos_imputados») y nada de esto se guarda en la base: solo se calcula al consultar.
Para volver a ver los datos tal como se capturaron basta poner IMPUTAR_DATOS_FALTANTES = False en core/constantes.py.
"""
from __future__ import annotations

import hashlib

import pandas as pd

from .constantes import COLUMNAS_IMPUTABLES
from .normalizacion import es_nulo

NUMERICAS = {"edad"}


def clave_persona(df: pd.DataFrame) -> pd.Series:
    """Una clave por persona: su ID de persona; si falta, el ID del registro; si también falta, la fila."""
    mid = df["id_persona_maestro"].fillna("").astype(str).str.strip()
    rid = df["id_persona"].fillna("").astype(str).str.strip()
    fila = pd.Series(["fila-" + str(i) for i in range(len(df))], index=df.index)
    return mid.where(mid.ne(""), rid.where(rid.ne(""), fila))


def _faltante(serie: pd.Series, numerica: bool) -> pd.Series:
    return serie.isna() if numerica else serie.map(es_nulo)


def _orden_estable(claves: list[str], columna: str) -> list[str]:
    """Orden pseudoaleatorio pero fijo: no depende del orden de captura ni cambia entre ejecuciones."""
    return sorted(claves, key=lambda k: hashlib.sha1(f"{columna}|{k}".encode()).hexdigest())


def _repartir(conocidos: pd.Series, sin_dato: list[str], columna: str, numerica: bool) -> dict[str, object]:
    """Asigna un valor a cada persona sin dato siguiendo la distribución de `conocidos` (un valor por persona)."""
    n = len(sin_dato)
    if n == 0 or conocidos.empty:
        return {}
    orden = _orden_estable(sin_dato, columna)
    if numerica:
        valores = sorted(conocidos.astype(float))
        return {k: valores[min(int(((i + 0.5) / n) * len(valores)), len(valores) - 1)] for i, k in enumerate(orden)}
    cuentas = conocidos.value_counts()
    cuentas = cuentas.iloc[sorted(range(len(cuentas)), key=lambda j: (-int(cuentas.iloc[j]), str(cuentas.index[j])))]
    acumulado = (cuentas.cumsum() / cuentas.sum()).tolist()
    categorias = list(cuentas.index)
    out = {}
    for i, k in enumerate(orden):
        q = (i + 0.5) / n
        j = next((x for x, a in enumerate(acumulado) if a > q), len(categorias) - 1)
        out[k] = categorias[j]
    return out


def imputar_proporcional(df: pd.DataFrame, columnas: list[str] | None = None) -> pd.DataFrame:
    """Devuelve una copia con los datos faltantes completados y marcados. No modifica `df`."""
    out = df.copy()
    if out.empty:
        return out
    cols = [c for c in (columnas or COLUMNAS_IMPUTABLES) if c in out.columns]
    clave = clave_persona(out)
    orden_cron = out["fecha_registro"].fillna(pd.Timestamp("1900-01-01")) if "fecha_registro" in out.columns else pd.Series(0, index=out.index)
    posicion = orden_cron.to_numpy().argsort(kind="stable")  # el dato conocido más reciente de cada persona
    for c in cols:
        numerica = c in NUMERICAS
        falta = _faltante(out[c], numerica)
        marca = pd.Series(False, index=out.index)
        if falta.any():
            reales = out.iloc[posicion][~falta.iloc[posicion]]
            por_persona = reales.groupby(clave.iloc[posicion][~falta.iloc[posicion]])[c].last()
            personas_sin_dato = sorted(set(clave[falta]) - set(por_persona.index))
            asignado = _repartir(por_persona, personas_sin_dato, c, numerica)
            valor = clave[falta].map(lambda k: por_persona[k] if k in por_persona.index else asignado.get(k))
            tiene = valor.notna()
            idx = valor.index[tiene]
            out.loc[idx, c] = valor[tiene].values
            marca.loc[idx] = ~clave.loc[idx].isin(por_persona.index)
        out[f"{c}_imputado"] = marca
    marcas = [f"{c}_imputado" for c in cols]
    out["datos_imputados"] = out[marcas].apply(lambda f: ", ".join(c for c, m in zip(cols, f) if m), axis=1) if marcas else ""
    return out


def resumen_imputacion(df: pd.DataFrame) -> pd.DataFrame:
    """Tabla para justificar el método: por columna, cuántas personas tenían dato y a cuántas se les completó."""
    if df is None or df.empty or "id_persona" not in df.columns:
        return pd.DataFrame(columns=["Columna", "Personas", "Con dato capturado", "Completadas", "% completadas"])
    clave = clave_persona(df)
    total = int(clave.nunique())
    filas = []
    for c in COLUMNAS_IMPUTABLES:
        m = f"{c}_imputado"
        if m not in df.columns:
            continue
        imp = int(clave[df[m]].nunique())
        filas.append({"Columna": c, "Personas": total, "Con dato capturado": total - imp, "Completadas": imp,
                      "% completadas": round(100 * imp / total, 1) if total else 0.0})
    return pd.DataFrame(filas)
