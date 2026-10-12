"""Unificación de variantes de redacción y agrupación SOLO para visualizaciones (Python puro).

Nada de esto cambia los datos guardados: se usa al DIBUJAR gráficas para que «MASCULINO» y «Masculino»
cuenten como una sola categoría, y para que las gráficas de tipo de vinculación agrupen en dos bloques
sin perder la división original en las tablas, filtros, fichas y exportaciones.
"""
from __future__ import annotations

import pandas as pd

from .constantes import SIN_DATO
from .texto import normalizar_texto

# Sinónimos inequívocos (clave = texto normalizado: minúsculas, sin acentos).
SINONIMOS = {
    "masculino": "Masculino", "hombre": "Masculino",
    "femenino": "Femenino", "mujer": "Femenino",
}

# Todas las formas en que aparece «no hay dato» (texto normalizado: minúsculas, sin acentos). Se muestran SIEMPRE como SIN_DATO.
NULOS_EQUIVALENTES = {
    "", "nan", "none", "nat", "null", "<na>", "n/a", "s/d",
    "indefinido", "indefinida", "sin informacion", "sin dato", "sin datos", "sin especificar",
    "informacion no disponible", "no disponible", "no definido",
}

# Agrupación visual del tipo de vinculación (los datos conservan los cuatro tipos).
GRUPO_FORMACION = "Inserción Educativa"
GRUPO_ATENCION = "Inserción laboral"
GRUPOS_VISUALES = {
    "practicas profesionales": GRUPO_FORMACION,
    "servicio social": GRUPO_FORMACION,
    "atencion": GRUPO_ATENCION,
    "insercion laboral": GRUPO_ATENCION,
}


def es_nulo(valor) -> bool:
    """True si el valor es vacío o cualquiera de las formas de «sin dato» (Indefinido, Sin información, Sin dato…)."""
    return normalizar_texto(valor) in NULOS_EQUIVALENTES


def homologar_nulos(serie: pd.Series, etiqueta: str = SIN_DATO) -> pd.Series:
    """Serie lista para MOSTRAR: todo faltante pasa a una sola etiqueta; el resto queda igual. No modifica los datos guardados."""
    s = serie.astype("object")
    return s.where(~s.map(es_nulo), etiqueta)


_vacio = es_nulo


def _mejor_variante(variantes: pd.Series, clave: str) -> str:
    """Elige la redacción que se muestra: la más natural (no TODO MAYÚSCULAS ni todo minúsculas) y, a igualdad, la más frecuente."""
    if clave in SINONIMOS:
        return SINONIMOS[clave]
    siglas = " " not in clave and len(clave) <= 5  # «IPN», «CBTIS»: se respetan las mayúsculas
    conteo = variantes.value_counts()

    def puntaje(v: str):
        natural = v[:1].isupper() and not v.isupper() and not v.islower()
        return (v.isupper() if siglas else natural, int(conteo[v]), v)
    return max(conteo.index, key=puntaje)


def unificar_variantes(serie: pd.Series) -> pd.Series:
    """Serie con la misma redacción para valores que solo difieren en mayúsculas, acentos o espacios. Vacíos intactos."""
    s = serie.astype("object")
    texto = s.where(~s.map(_vacio), "").astype(str).str.strip()
    claves = texto.map(normalizar_texto)
    con_valor = claves.ne("")
    if not con_valor.any():
        return texto
    elegidas = {k: _mejor_variante(texto[con_valor & claves.eq(k)], k) for k in claves[con_valor].unique()}
    return texto.where(~con_valor, claves.map(elegidas))


def agrupar_tipo_vinculacion(serie: pd.Series) -> pd.Series:
    """Para gráficas: Prácticas+Servicio social → un bloque; Atención+Inserción laboral → otro. Lo demás queda igual."""
    s = homologar_nulos(serie.fillna("").astype(str).str.strip())
    agrupado = s.map(normalizar_texto).map(GRUPOS_VISUALES)
    return agrupado.where(agrupado.notna(), s)
