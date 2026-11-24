"""Mide qué tan bien funciona la imputación proporcional con tus propios datos (sirve para justificarla en el informe).

Uso:   python scripts/evaluar_imputacion.py ARCHIVO.csv [--columnas carrera Institución] [--oculto 0.2] [--repeticiones 30]
       (también acepta .xlsx; necesita las columnas id_persona_maestro y, de preferencia, fecha_registro)

Cómo mide: toma a las personas que SÍ tienen el dato, esconde al azar una parte (por defecto 20 %), deja que el método
les complete el dato y compara con el valor real que se escondió. Repite varias veces y promedia. Devuelve, por columna:
  - Acierto individual: % de personas a las que el método les puso justo su valor real.
  - Referencia al azar: lo esperado si se adivina con la misma distribución (suma de proporciones al cuadrado).
  - Referencia «siempre la moda»: acierto de poner a todos el valor más frecuente.
  - Diferencia máxima de proporciones: qué tanto cambia la distribución del conjunto (en puntos porcentuales).
Lectura: el acierto individual de un reparto proporcional es modesto por naturaleza; lo importante es que la distribución
del conjunto casi no cambia (diferencia cercana a 0), que es lo que usan las estadísticas.
Los datos no salen de tu computadora y el script no escribe nada en la base.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from vinculate.core.imputacion import clave_persona, imputar_proporcional  # noqa: E402
from vinculate.core.normalizacion import es_nulo  # noqa: E402

NO_CATEGORICAS = {"id_persona", "id_persona_maestro", "nombre", "telefono", "correo", "fecha_registro", "Año", "año", "edad",
                  "datos_imputados", "estatus_vinculacion"}


def leer(ruta: str) -> pd.DataFrame:
    p = Path(ruta)
    df = pd.read_excel(p, dtype=str) if p.suffix.lower() in (".xlsx", ".xls") else pd.read_csv(p, dtype=str, keep_default_na=False)
    if "id_persona" not in df.columns:
        df["id_persona"] = [f"fila-{i}" for i in range(len(df))]
    if "fecha_registro" in df.columns:
        df["fecha_registro"] = pd.to_datetime(df["fecha_registro"], errors="coerce", dayfirst=True)
    else:
        df["fecha_registro"] = pd.NaT
    return df


def evaluar(df: pd.DataFrame, col: str, oculto: float, repeticiones: int) -> dict | None:
    df = df.copy()
    df["_k"] = clave_persona(df)
    falta = df[col].map(es_nulo)
    base = df[~falta].sort_values("fecha_registro").groupby("_k")[col].last()      # un valor conocido por persona
    if len(base) < 20 or base.nunique() < 2:
        return None
    p = base.value_counts(normalize=True)
    aciertos, difs = [], []
    for semilla in range(repeticiones):
        rng = np.random.default_rng(semilla)
        escondidas = set(rng.choice(base.index.to_numpy(), size=max(1, int(len(base) * oculto)), replace=False))
        prueba = df.copy()
        prueba.loc[prueba["_k"].isin(escondidas), col] = ""
        res = imputar_proporcional(prueba, [col])
        nuevo = res.sort_values("fecha_registro").groupby("_k")[col].last()
        aciertos.append(float((nuevo.loc[list(escondidas)] == base.loc[list(escondidas)]).mean()))
        q = nuevo.loc[base.index].value_counts(normalize=True)
        difs.append(float((q.reindex(p.index).fillna(0) - p).abs().max()))
    return {"Columna": col, "Personas con dato": len(base), "Acierto individual": f"{100 * np.mean(aciertos):.1f} %",
            "Referencia al azar": f"{100 * float((p ** 2).sum()):.1f} %", "Referencia «siempre la moda»": f"{100 * float(p.iloc[0]):.1f} %",
            "Diferencia máxima de proporciones": f"{100 * np.mean(difs):.2f} pp"}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("archivo")
    ap.add_argument("--columnas", nargs="*")
    ap.add_argument("--oculto", type=float, default=0.2)
    ap.add_argument("--repeticiones", type=int, default=30)
    a = ap.parse_args()
    df = leer(a.archivo)
    cols = a.columnas or [c for c in df.columns if c not in NO_CATEGORICAS and not c.startswith("_")]
    filas = [r for r in (evaluar(df, c, a.oculto, a.repeticiones) for c in cols if c in df.columns) if r]
    print(pd.DataFrame(filas).to_string(index=False) if filas else "Ninguna columna tiene suficientes datos conocidos para evaluar.")


if __name__ == "__main__":
    main()
