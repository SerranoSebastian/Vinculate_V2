"""Catálogo único de ubicación: Tlaxcala por municipio; resto del país por estado."""
from __future__ import annotations

import pandas as pd

from .texto import normalizar_texto

MUNICIPIOS_TLAXCALA = [
    "ACUAMANALA DE MIGUEL HIDALGO", "ALTZAYANCA", "AMAXAC DE GUERRERO",
    "APETATITLÁN DE ANTONIO CARVAJAL", "APIZACO", "ATLANGATEPEC", "BENITO JUÁREZ",
    "CALPULALPAN", "CHIAUTEMPAN", "CONTLA DE JUAN CUAMATZI", "CUAPIAXTLA", "CUAXOMULCO",
    "EL CARMEN TEQUEXQUITLA", "EMILIANO ZAPATA", "ESPAÑITA", "HUAMANTLA", "HUEYOTLIPAN",
    "IXTACUIXTLA DE MARIANO MATAMOROS", "IXTENCO", "LA MAGDALENA TLALTELULCO",
    "LÁZARO CÁRDENAS", "MAZATECOCHCO DE JOSÉ MARÍA MORELOS", "MUÑOZ DE DOMINGO ARENAS",
    "NANACAMILPA DE MARIANO ARISTA", "NATIVITAS", "PANOTLA", "PAPALOTLA DE XICOHTÉNCATL",
    "SAN DAMIÁN TEXOLOC", "SAN FRANCISCO TETLANOHCAN", "SAN JERÓNIMO ZACUALPAN",
    "SAN JOSÉ TEACALCO", "SAN JUAN HUACTZINCO", "SAN LORENZO AXOCOMANITLA",
    "SAN LUCAS TECOPILCO", "SAN PABLO DEL MONTE", "SANCTORUM DE LÁZARO CÁRDENAS",
    "SANTA ANA NOPALUCAN", "SANTA APOLONIA TEACALCO", "SANTA CATARINA AYOMETLA",
    "SANTA CRUZ QUILEHTLA", "SANTA CRUZ TLAXCALA", "SANTA ISABEL XILOXOXTLA",
    "TENANCINGO", "TEOLOCHOLCO", "TEPETITLA DE LARDIZÁBAL", "TEPEYANCO", "TERRENATE",
    "TETLA DE LA SOLIDARIDAD", "TETLATLAHUCA", "TLAXCALA", "TLAXCO", "TOCATLÁN", "TOTOLAC",
    "TZOMPANTEPEC", "XALOSTOC", "XALTOCAN", "XICOHTZINCO", "YAUHQUEMECAN", "ZACATELCO",
    "ZITLALTEPEC DE TRINIDAD SÁNCHEZ SANTOS",
]

ESTADOS_MEXICO_SIN_TLAXCALA = [
    "AGUASCALIENTES", "BAJA CALIFORNIA", "BAJA CALIFORNIA SUR", "CAMPECHE",
    "CHIAPAS", "CHIHUAHUA", "CIUDAD DE MÉXICO", "COAHUILA", "COLIMA", "DURANGO",
    "GUANAJUATO", "GUERRERO", "HIDALGO", "JALISCO", "ESTADO DE MÉXICO",
    "MICHOACÁN", "MORELOS", "NAYARIT", "NUEVO LEÓN", "OAXACA", "PUEBLA",
    "QUERÉTARO", "QUINTANA ROO", "SAN LUIS POTOSÍ", "SINALOA", "SONORA",
    "TABASCO", "TAMAULIPAS", "VERACRUZ", "YUCATÁN", "ZACATECAS",
]

OPCIONES_UBICACION_CAPTURA = [""] + MUNICIPIOS_TLAXCALA + ESTADOS_MEXICO_SIN_TLAXCALA + ["Indefinido"]
OPCIONES_UBICACION_FILTRO = MUNICIPIOS_TLAXCALA + ESTADOS_MEXICO_SIN_TLAXCALA + ["Otro Estado", "Indefinido", "Sin dato"]

_MAPA_CATALOGO = {normalizar_texto(x): x for x in MUNICIPIOS_TLAXCALA + ESTADOS_MEXICO_SIN_TLAXCALA}
_ALIASES = {
    "estado de mexico": "ESTADO DE MÉXICO",
    "mexico": "ESTADO DE MÉXICO",
    "cdmx": "CIUDAD DE MÉXICO",
    "ciudad de mexico": "CIUDAD DE MÉXICO",
    "coahuila de zaragoza": "COAHUILA",
    "michoacan de ocampo": "MICHOACÁN",
    "veracruz de ignacio de la llave": "VERACRUZ",
    "sanctórum de lazaro cardenas": "SANCTORUM DE LÁZARO CÁRDENAS",
    "sanctorum de lazaro cardenas": "SANCTORUM DE LÁZARO CÁRDENAS",
    "yauhquemehcan": "YAUHQUEMECAN",
    "xaloztoc": "XALOSTOC",
}


def normalizar_ubicacion_mexico(valor) -> str:
    """Etiqueta canónica. Vacío sigue siendo vacío (no se convierte en Indefinido)."""
    if valor is None or pd.isna(valor) or str(valor).strip() == "":
        return ""
    original = str(valor).strip()
    key = normalizar_texto(original)
    if key == "indefinido":
        return "Indefinido"
    if key == "otro estado":
        return "Otro Estado"
    if key in _ALIASES:
        return _ALIASES[key]
    return _MAPA_CATALOGO.get(key, original)


def opciones_ubicacion(valor_actual="", incluir_legacy: bool = True) -> list[str]:
    """Opciones para un selectbox, conservando un valor histórico desconocido."""
    actual = normalizar_ubicacion_mexico(valor_actual)
    opciones = list(OPCIONES_UBICACION_CAPTURA)
    if incluir_legacy and actual and actual not in opciones:
        opciones.append(actual)
    return opciones


def es_municipio_tlaxcala(valor) -> bool:
    return normalizar_ubicacion_mexico(valor) in MUNICIPIOS_TLAXCALA
