"""RIDET — Regiones Integrales para el Desarrollo Dual de Tlaxcala (lógica pura, sin Streamlit).

Fuente de TODO lo que está aquí: el documento oficial `assets/documentos/RIDET.pdf`.
  * Cifras por región y municipios de cada región: encabezados del documento.
  * Empresas por región: extraídas con `scripts/extraer_ridet.py` y validadas contra los totales
    que el documento imprime (referencia/ridet_empresas.csv).

Nada se infiere por cercanía ni por parecido dudoso: cuando una empresa no se puede ubicar con
certeza, queda «Pendiente de asignar» y se captura a mano (municipio) desde la app.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from .texto import normalizar_texto, texto_vacio

PENDIENTE = "Pendiente de asignar"
METODO_EXACTO = "Coincide con el RIDET"
METODO_PARCIAL = "Coincidencia parcial (revisar)"
METODO_ALIAS = "Alias de la versión anterior"
METODO_MUNICIPIO = "Por municipio capturado"
METODO_AMBIGUA = "Ambigua: aparece en varias regiones"
METODO_NINGUNO = "Sin coincidencia"

# Encabezados del documento (municipios, sectores, empresas, instituciones públicas de EMS).
REGIONES = [
    {"region": "Región Norte", "cabecera": "Tlaxco", "municipios": 4, "sectores": 9, "empresas": 20, "ems": 12},
    {"region": "Región Oriente", "cabecera": "Huamantla", "municipios": 7, "sectores": 8, "empresas": 39, "ems": 17},
    {"region": "Región Poniente", "cabecera": "Calpulalpan", "municipios": 6, "sectores": 7, "empresas": 13, "ems": 10},
    {"region": "Región Centro-Norte", "cabecera": "Apizaco", "municipios": 10, "sectores": 12, "empresas": 75, "ems": 17},
    {"region": "Región Centro-Sur", "cabecera": "Tlaxcala", "municipios": 12, "sectores": 9, "empresas": 82, "ems": 23},
    {"region": "Región Sur", "cabecera": "Zacatelco", "municipios": 20, "sectores": 11, "empresas": 78, "ems": 24},
]
NOMBRES_REGION = [r["region"] for r in REGIONES]

# Municipios de cada región (nombres del catálogo de la app).
REGION_MUNICIPIOS: dict[str, list[str]] = {
    "Región Norte": ["TLAXCO", "ATLANGATEPEC", "EMILIANO ZAPATA", "LÁZARO CÁRDENAS"],
    "Región Oriente": ["HUAMANTLA", "EL CARMEN TEQUEXQUITLA", "CUAPIAXTLA", "IXTENCO", "TERRENATE",
                       "ZITLALTEPEC DE TRINIDAD SÁNCHEZ SANTOS", "SAN JOSÉ TEACALCO",
                       "ALTZAYANCA"],  # ← ver NOTA_OBSERVACION
    "Región Poniente": ["CALPULALPAN", "ESPAÑITA", "HUEYOTLIPAN", "SANCTORUM DE LÁZARO CÁRDENAS",
                        "NANACAMILPA DE MARIANO ARISTA", "BENITO JUÁREZ"],
    "Región Centro-Norte": ["APIZACO", "XALOSTOC", "CUAXOMULCO", "MUÑOZ DE DOMINGO ARENAS", "TETLA DE LA SOLIDARIDAD",
                            "TOCATLÁN", "TZOMPANTEPEC", "XALTOCAN", "YAUHQUEMECAN", "SAN LUCAS TECOPILCO"],
    "Región Centro-Sur": ["TLAXCALA", "AMAXAC DE GUERRERO", "APETATITLÁN DE ANTONIO CARVAJAL", "CHIAUTEMPAN",
                          "CONTLA DE JUAN CUAMATZI", "PANOTLA", "SANTA CRUZ TLAXCALA", "TOTOLAC",
                          "LA MAGDALENA TLALTELULCO", "SAN DAMIÁN TEXOLOC", "SAN FRANCISCO TETLANOHCAN",
                          "SANTA ISABEL XILOXOXTLA"],
    "Región Sur": ["ZACATELCO", "IXTACUIXTLA DE MARIANO MATAMOROS", "MAZATECOCHCO DE JOSÉ MARÍA MORELOS",
                   "ACUAMANALA DE MIGUEL HIDALGO", "TEOLOCHOLCO", "PAPALOTLA DE XICOHTÉNCATL", "XICOHTZINCO",
                   "SAN PABLO DEL MONTE", "TENANCINGO", "TEPETITLA DE LARDIZÁBAL", "NATIVITAS", "TEPEYANCO",
                   "TETLATLAHUCA", "SAN JERÓNIMO ZACUALPAN", "SAN JUAN HUACTZINCO", "SAN LORENZO AXOCOMANITLA",
                   "SANTA ANA NOPALUCAN", "SANTA APOLONIA TEACALCO", "SANTA CATARINA AYOMETLA", "SANTA CRUZ QUILEHTLA"],
}
NOTA_OBSERVACION = (
    "El encabezado de la Región Oriente dice «7 municipios» y no nombra a Altzayanca (Atltzayanca), pero el cuerpo del "
    "documento sí le asigna a esa región una zona urbana, una empresa (ARCOMEX) y dos planteles de educación media superior. "
    "Por eso aquí se cuenta en Oriente: así los 60 municipios de Tlaxcala quedan en una región. Conviene confirmarlo con quien "
    "elaboró el RIDET."
)
MUNICIPIO_REGION: dict[str, str] = {normalizar_texto(m): r for r, ms in REGION_MUNICIPIOS.items() for m in ms}

# Alias explícitos (nombre usado en vacantes → nombre del RIDET). Solo los de la versión anterior.
ALIAS_EMPRESAS = {"SEBNMX": "SE BORDNETZE"}

IMAGENES_GENERALES = ["01_portada.png", "02_descripcion.png", "03_regiones.png"]
IMAGENES_REGION = {
    "Región Norte": ["04_norte.png"],
    "Región Oriente": ["05_oriente.png"],
    "Región Poniente": ["06_poniente.png"],
    "Región Centro-Norte": ["07_centro_norte_1.png", "08_centro_norte_2.png"],
    "Región Centro-Sur": ["09_centro_sur_1.png", "10_centro_sur_2.png"],
    "Región Sur": ["11_sur_1.png", "12_sur_2.png"],
}

_RUIDO = {"de", "del", "la", "el", "los", "las", "y", "e", "s", "a", "c", "v", "sa", "cv", "rl", "sapi",
          "mexico", "mx", "planta", "grupo"}


def region_de_municipio(municipio) -> str | None:
    """Región RIDET de un municipio de Tlaxcala (None si no es uno de los 60 o está vacío)."""
    if texto_vacio(municipio):
        return None
    return MUNICIPIO_REGION.get(normalizar_texto(municipio))


def _letras(valor) -> str:
    return re.sub(r"[^a-z0-9]+", " ", normalizar_texto(valor)).strip()


def _tokens(valor) -> frozenset[str]:
    return frozenset(t for t in _letras(valor).split() if t not in _RUIDO)


def cargar_referencia(ruta: Path | str) -> pd.DataFrame:
    """Empresas del RIDET (region, empresa, pagina) o un DataFrame vacío si el archivo no existe."""
    ruta = Path(ruta)
    if not ruta.exists():
        return pd.DataFrame(columns=["region", "empresa", "pagina"])
    df = pd.read_csv(ruta, dtype=str, keep_default_na=False)
    return df[["region", "empresa", "pagina"]]


def _preparar_referencia(ref: pd.DataFrame) -> list[tuple[str, str, str, str, frozenset[str]]]:
    return [(r.region, r.empresa, _letras(r.empresa), _letras(r.empresa).replace(" ", ""), _tokens(r.empresa))
            for r in ref.itertuples(index=False)]


def _unica_region(candidatas: list[tuple]) -> tuple[str | None, str]:
    regiones = sorted({c[0] for c in candidatas})
    nombres = sorted({c[1] for c in candidatas})
    return (regiones[0] if len(regiones) == 1 else None), "; ".join(nombres[:3])


def clasificar_empresa(nombre, ref_prep: list[tuple], municipio=None) -> dict:
    """Región de UNA empresa y con qué criterio se obtuvo. Orden de confianza:
    municipio capturado → coincidencia exacta → alias → coincidencia parcial → pendiente."""
    res = {"empresa": nombre, "region": PENDIENTE, "metodo": METODO_NINGUNO, "coincide_con": ""}
    region_mun = region_de_municipio(municipio)
    if region_mun:
        return {**res, "region": region_mun, "metodo": METODO_MUNICIPIO, "coincide_con": str(municipio)}
    if texto_vacio(nombre):
        return res
    letras = _letras(nombre)
    compacto = letras.replace(" ", "")
    if not compacto:
        return res

    exactas = [r for r in ref_prep if r[2] == letras or r[3] == compacto]
    if exactas:
        region, con = _unica_region(exactas)
        if region:
            return {**res, "region": region, "metodo": METODO_EXACTO, "coincide_con": con}
        return {**res, "metodo": METODO_AMBIGUA, "coincide_con": con}

    alias = ALIAS_EMPRESAS.get(letras.upper()) or ALIAS_EMPRESAS.get(str(nombre).strip().upper())
    if alias:
        al = _letras(alias)
        hit = [r for r in ref_prep if r[2] == al]
        region, con = _unica_region(hit) if hit else (None, "")
        if region:
            return {**res, "region": region, "metodo": METODO_ALIAS, "coincide_con": con}

    toks = _tokens(nombre)
    if toks:
        parciales = []
        for r in ref_prep:
            t = r[4]
            if not t:
                continue
            menor, mayor = (toks, t) if len(toks) <= len(t) else (t, toks)
            if not menor <= mayor:
                continue
            if len(menor) >= 2 or (len(menor) == 1 and len(next(iter(menor))) >= 5):
                parciales.append(r)
        if parciales:
            region, con = _unica_region(parciales)
            if region:
                return {**res, "region": region, "metodo": METODO_PARCIAL, "coincide_con": con}
            return {**res, "metodo": METODO_AMBIGUA, "coincide_con": con}
    return res


def clasificar_empresas(empresas, ref: pd.DataFrame, municipios: dict[str, str] | None = None) -> pd.DataFrame:
    """Una fila por empresa distinta: empresa, region, metodo, coincide_con.

    `municipios` = {nombre de empresa: municipio capturado} (catálogo de empresas, migración V004).
    """
    prep = _preparar_referencia(ref)
    municipios = municipios or {}
    vistos, filas = set(), []
    for e in empresas:
        if texto_vacio(e) or str(e).strip() in vistos:
            continue
        vistos.add(str(e).strip())
        filas.append(clasificar_empresa(str(e).strip(), prep, municipios.get(str(e).strip())))
    return pd.DataFrame(filas, columns=["empresa", "region", "metodo", "coincide_con"])


def resumen_regiones() -> pd.DataFrame:
    df = pd.DataFrame(REGIONES).rename(columns={
        "region": "Región", "cabecera": "Cabecera", "municipios": "Municipios", "sectores": "Sectores",
        "empresas": "Empresas", "ems": "Instituciones EMS"})
    return df
