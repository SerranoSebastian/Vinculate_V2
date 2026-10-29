"""Filtros del Explorador: cada filtro mira UNA columna (no todo el texto de la fila), para no mezclar coincidencias de otras columnas."""
from __future__ import annotations

import pandas as pd

from .constantes import SIN_DATO
from .normalizacion import homologar_nulos
from .texto import normalizar_texto

# (columna, etiqueta, multivalor). «multivalor» = la celda trae varios valores separados por coma ("2023, 2024").
FILTROS: dict[str, list[tuple[str, str, bool]]] = {
    "personas": [
        ("municipio", "Municipio / estado", False), ("sexo", "Sexo", False), ("escolaridad", "Escolaridad", False),
        ("carrera", "Carrera", False), ("Institución", "Institución", False), ("grupo_prioritario", "Grupo prioritario", False),
        ("tipos_vinculacion", "Tipo de vinculación", True), ("años_con_registro", "Año de registro", True),
    ],
    "historicos": [
        ("municipio", "Municipio / estado", False), ("sexo", "Sexo", False), ("escolaridad", "Escolaridad", False),
        ("carrera", "Carrera", False), ("Institución", "Institución", False), ("vinculacion", "Tipo de vinculación", False),
        ("estatus_vinculacion", "Estatus", False), ("Año", "Año", False),
    ],
    "vacantes": [
        ("Empresa", "Empresa", False), ("Sector Empresa", "Sector", False), ("Tipo de Vacante", "Tipo de vacante", False),
        ("Tipo de Oportunidad", "Tipo de oportunidad", False), ("Área de Oportunidad", "Área de oportunidad", False),
        ("Estado", "Estado", False), ("Año", "Año", False),
    ],
    "vinculaciones": [
        ("empresa", "Empresa", False), ("sector_empresa", "Sector", False), ("tipo_vacante", "Tipo de vacante", False),
        ("estatus", "Estatus", False), ("responsable", "Responsable", False),
    ],
}

# La búsqueda de texto solo mira identificadores y nombres, no municipio, carrera ni el resto de columnas.
COLUMNAS_TEXTO: dict[str, list[str]] = {
    "personas": ["id_persona_maestro", "nombre", "telefono", "correo"],
    "historicos": ["id_persona", "id_persona_maestro", "nombre"],
    "vacantes": ["ID Vacante", "Empresa", "Puesto Original"],
    "vinculaciones": ["id_vinculacion", "id_persona_maestro", "nombre_persona", "empresa"],
}
AYUDA_TEXTO = {
    "personas": "Nombre, ID, teléfono o correo",
    "historicos": "Nombre o ID de la persona",
    "vacantes": "Empresa, puesto o ID de la vacante",
    "vinculaciones": "Persona, empresa o ID",
}


def _como_texto(serie: pd.Series) -> pd.Series:
    """Valores legibles: los años numéricos sin «.0» y los vacíos como «Indefinido»."""
    if pd.api.types.is_numeric_dtype(serie):
        s = serie.map(lambda v: "" if pd.isna(v) else (str(int(v)) if float(v).is_integer() else str(v)))
    else:
        s = serie.fillna("").astype(str).str.strip()
    return homologar_nulos(s)


def _partes(valor: str) -> list[str]:
    return [p.strip() for p in str(valor).split(",") if p.strip()] or [SIN_DATO]


def opciones(df: pd.DataFrame, col: str, multivalor: bool = False) -> list[str]:
    """Valores existentes de la columna, ordenados (años de mayor a menor)."""
    if col not in df.columns or df.empty:
        return []
    valores = _como_texto(df[col])
    if multivalor:
        valores = pd.Series([p for v in valores for p in _partes(v)])
    unicos = set(valores)
    if all(v.isdigit() for v in unicos if v != SIN_DATO):
        return sorted(unicos - {SIN_DATO}, key=int, reverse=True) + ([SIN_DATO] if SIN_DATO in unicos else [])
    return sorted(unicos - {SIN_DATO}, key=normalizar_texto) + ([SIN_DATO] if SIN_DATO in unicos else [])


def aplicar(df: pd.DataFrame, clave: str, elegidos: dict[str, list[str]], texto: str = "") -> pd.DataFrame:
    """Filtra por columna (varias opciones de una misma columna = «o»; columnas distintas = «y») y por texto en identificadores/nombres."""
    if df.empty:
        return df
    mask = pd.Series(True, index=df.index)
    for col, etiqueta, multivalor in FILTROS.get(clave, []):
        sel = elegidos.get(col) or []
        if not sel or col not in df.columns:
            continue
        valores = _como_texto(df[col])
        if multivalor:
            mask &= valores.map(lambda v: any(p in sel for p in _partes(v)))
        else:
            mask &= valores.isin(sel)
    terminos = [t for t in normalizar_texto(texto).split(" ") if t]
    if terminos:
        cols = [c for c in COLUMNAS_TEXTO.get(clave, []) if c in df.columns]
        if cols:
            pajar = df[cols].astype(str).apply(lambda s: s.map(normalizar_texto)).agg(" ".join, axis=1)
            for t in terminos:
                mask &= pajar.str.contains(t, regex=False)
        else:
            mask &= False
    return df[mask]
