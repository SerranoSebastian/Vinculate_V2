"""Búsqueda global (personas, vacantes, vinculaciones) sobre los datos que RLS ya dejó ver al usuario."""
from __future__ import annotations

import pandas as pd

from ..auth.sesion import Sesion
from ..core.texto import normalizar_texto
from . import datos

MINIMO = 2
LIMITE_POR_TIPO = 50

# Columnas donde se busca (nombres históricos) y columnas que se muestran.
_CAMPOS = {
    "personas": (["id_persona", "id_persona_maestro", "nombre", "correo", "telefono", "carrera", "Institución", "municipio"],
                 ["id_persona_maestro", "nombre", "municipio", "carrera", "Institución", "vinculacion", "Año"]),
    "vacantes": (["ID Vacante", "Empresa", "Tipo de Vacante", "Puesto Original", "Área de Oportunidad", "Sector Empresa"],
                 ["ID Vacante", "Empresa", "Tipo de Vacante", "Tipo de Oportunidad", "Estado", "Fecha"]),
    "vinculaciones": (["id_vinculacion", "id_persona_maestro", "nombre_persona", "empresa", "tipo_vacante"],
                      ["id_vinculacion", "id_persona_maestro", "nombre_persona", "empresa", "estatus", "fecha_vinculacion"]),
}


def _filtrar(df: pd.DataFrame, columnas: list[str], terminos: list[str]) -> pd.DataFrame:
    if df.empty:
        return df
    cols = [c for c in columnas if c in df.columns]
    if not cols:
        return df.iloc[0:0]
    pajar = df[cols].astype(str).apply(lambda s: s.map(normalizar_texto)).agg(" ".join, axis=1)
    mask = pd.Series(True, index=df.index)
    for t in terminos:  # todos los términos deben aparecer (en cualquier campo)
        mask &= pajar.str.contains(t, regex=False)
    return df[mask]


def buscar(sesion: Sesion, texto: str, limite: int = LIMITE_POR_TIPO) -> dict[str, pd.DataFrame]:
    """{tipo: DataFrame} solo con los módulos que el usuario puede consultar."""
    terminos = [t for t in normalizar_texto(texto).split(" ") if t]
    if not terminos or sum(len(t) for t in terminos) < MINIMO:
        return {}
    origen = {"personas": datos.personas, "vacantes": datos.vacantes, "vinculaciones": datos.vinculaciones}
    salida: dict[str, pd.DataFrame] = {}
    for tipo, (buscar_en, mostrar) in _CAMPOS.items():
        if not sesion.puede(tipo, "view"):
            continue
        df = origen[tipo](sesion)
        hit = _filtrar(df, buscar_en, terminos)
        if tipo == "personas" and not hit.empty:
            # Una fila por persona (la búsqueda es de personas, no de cada vinculación histórica).
            hit = hit.sort_values("fecha_registro", na_position="first").drop_duplicates("id_persona_maestro", keep="last")
        salida[tipo] = hit[[c for c in mostrar if c in hit.columns]].head(limite).reset_index(drop=True)
    return salida
