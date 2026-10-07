"""Extrae del PDF oficial RIDET la lista de empresas por región, para REVISIÓN humana.

Uso:
    python scripts/extraer_ridet.py assets/documentos/RIDET.pdf referencia/ridet_empresas.csv

Requiere la herramienta `pdftotext` (paquete poppler-utils). Se usa el modo `-raw`, que respeta
el orden de lectura mejor que `-layout` en este documento de columnas entrelazadas.

Garantías y límites (importa leerlos):
  * La REGIÓN de cada empresa es confiable: cada página del PDF pertenece a una sola región.
  * El script VALIDA el resultado contra los totales que el propio documento imprime
    ("20 EMPRESAS", "39 EMPRESAS", ...). Si no coinciden, termina con error y no escribe nada.
  * NO se infiere el municipio ni el parque industrial: en el PDF el encabezado de cada zona queda
    ambiguo respecto de las empresas que le siguen. El municipio se captura a mano en la app.
"""
from __future__ import annotations

import csv
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

REGIONES = {  # clave normalizada del encabezado → nombre oficial
    "norte": "Región Norte", "oriente": "Región Oriente", "poniente": "Región Poniente",
    "centro norte": "Región Centro-Norte", "centro sur": "Región Centro-Sur", "sur": "Región Sur",
}
TOTALES_DOCUMENTO = {  # "N EMPRESAS" impreso en el PDF para cada región
    "Región Norte": 20, "Región Oriente": 39, "Región Poniente": 13,
    "Región Centro-Norte": 75, "Región Centro-Sur": 82, "Región Sur": 78,
}
MUNICIPIOS_EMS = {  # encabezados de municipio de la lista de educación media superior (no son empresas)
    "TLAXCO", "ATLANGATEPEC", "EMILIANO ZAPATA", "LAZARO CARDENAS", "HUAMANTLA", "EL CARMEN TEQUEXQUITLA",
    "TERRENATE", "ZITLALTEPEC", "CUAPIAXTLA", "IXTENCO", "ATLTZAYANCA", "CALPULALPAN", "ESPAÑITA", "SANCTORUM",
    "NANACAMILPA", "APIZACO", "XALOZTOC", "CUAXOMULCO", "MUÑOZ DE DOMINGO ARENAS", "TETLA DE LA SOLIDARIDAD",
    "TETLA DE LA SOLARIDAD", "TOCATLAN", "TZOMPANTEPEC", "YAUHQUEMEHCAN", "TECOPILCO", "SAN LUCAS TECOPILCO",
    "AMAXAC DE GUERRERO", "APETATITLAN DE ANTONIO CARVAJAL", "CHIAUTEMPAN", "CHIAHUTEMPAN",
    "CONTLA DE JUAN CUAMATZI", "CONTLA", "PANOTLA", "SANTA CRUZ TLAXCALA", "TOTOLAC", "LA MAGDALENA TLALTELULCO",
    "VILLA ALTA TEPETITLA", "TEXOLOC", "TLAXCALA", "TETLANOHCAN", "SANTA ISABEL XILOXOXTLA", "ZACATELCO",
    "IXTACUIXTLA DE MARIANO DE MATAMOROS", "IXTLACUIXTLA", "MAZATECOCHCO DE JOSE MARIA MORELOS",
    "PAPALOTLA DE XICOHTENCATL", "XICOHTZINCO", "TENANCINGO", "TEPETITLA DE LARDIZABAL", "NATIVITAS",
    "TEPEYANCO", "SAN JUAN HUACTZINCO", "SANTA ANA NOPALUCAN", "SANTA APOLONOA TEACALCO", "SAN ISIDRO BUENSUCESO",
    "SAN PABLO DEL MONTE", "TEOLOCHOLCO", "AYOMETLA", "SAN LORENZO AXOCOMANITLA", "SAN JERONIMO ZACUALPAN",
}
PREFIJOS_EMS = ("PLANTEL", "EMSAD", "TBC", "CBTA", "EXT CBTA", "CETIS", "CONALEP", "CECYTE", "COBAT", "DGETI")


def normalizar(t: str) -> str:
    t = unicodedata.normalize("NFKD", t or "")
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^A-Za-z0-9&@ ]+", " ", t)).strip().upper()


def _es_encabezado(linea: str) -> bool:
    n = normalizar(linea)
    if not n:
        return True
    claves = ("INDUSTRIA", "SERVICIOS PARA", "TI Y AUTOMATIZACION", "ARTESANIAS", "ZONA URBANA", "CORREDOR",
              "CIUDAD INDUSTRIAL", "PARQUE INDUSTRIAL", "DESARROLLO INDUSTRIAL", "VESTA PARK", "AMPLIACION CIX",
              "MEDIA SUPERIOR", "MUNICIPIOS", "SECTORES INDUSTRIALES", "EMPRESAS", "INSTITUCIONES", "REGION ")
    return any(n.startswith(c) or c in n for c in claves)


def _terminos_sector_incompleto(linea: str) -> bool:
    n = normalizar(linea)
    return n.startswith(("INDUSTRIA", "SERVICIOS PARA")) and n.split()[-1] in {"DEL", "DE", "Y", "LA", "PARA", "METAL", "TEXTIL", "EL", "LOS"}


def paginas_raw(pdf: Path) -> list[str]:
    salida = subprocess.run(["pdftotext", "-raw", str(pdf), "-"], capture_output=True, text=True, check=True).stdout
    return salida.split("\f")


def extraer(pdf: Path) -> tuple[list[dict], dict[str, int]]:
    filas: list[dict] = []
    region = None
    for npag, pagina in enumerate(paginas_raw(pdf), start=1):
        lineas = [l.strip() for l in pagina.splitlines()]
        for l in lineas:  # la región de la página: el PRIMER encabezado "Región X (Cabecera: …)"
            m = re.match(r"^Regi[oó]n\s+(.+?)\s*\(Cabecera", l, flags=re.I)
            if m:
                clave = normalizar(m.group(1)).lower().replace("cento", "centro")
                region = REGIONES.get(clave, region)
                break
        if region is None:
            continue
        ultimo = None  # índice del último elemento numerado (para unir líneas partidas)
        en_ems = False
        parentesis_abiertos = 0
        previa_encabezado_incompleta = False
        for l in lineas:
            if not l:
                continue
            if previa_encabezado_incompleta:        # segunda mitad de un sector partido en dos líneas
                previa_encabezado_incompleta = False
                if not re.match(r"^\d+\s*\.", l):
                    continue
            m = re.match(r"^(\d+)\s*\.\s*(.+)$", l)
            if m:
                nombre = m.group(2).strip()
                parentesis_abiertos = max(0, nombre.count("(") - nombre.count(")"))
                if normalizar(nombre).startswith(PREFIJOS_EMS):
                    ultimo = None
                    continue
                if nombre.strip(". ") == "" or len(normalizar(nombre)) < 2:
                    ultimo = None
                    continue
                filas.append({"region": region, "empresa": nombre.rstrip(". ").strip(), "pagina": npag})
                ultimo = len(filas) - 1
                continue
            if parentesis_abiertos > 0:             # nombre partido dentro de paréntesis (empresa o plantel de EMS)
                parentesis_abiertos = max(0, parentesis_abiertos + l.count("(") - l.count(")"))
                if ultimo is not None:
                    filas[ultimo]["empresa"] = (filas[ultimo]["empresa"] + " " + l.strip()).strip()
                continue
            n = normalizar(l)
            if n.startswith("MEDIA SUPERIOR"):
                en_ems = True
                ultimo = None
                continue
            if _es_encabezado(l):
                previa_encabezado_incompleta = _terminos_sector_incompleto(l)
                ultimo = None
                continue
            if n in MUNICIPIOS_EMS or re.fullmatch(r"[\d ]+", n):
                ultimo = None
                continue
            if ultimo is not None:                  # continuación del nombre de la empresa anterior
                filas[ultimo]["empresa"] = (filas[ultimo]["empresa"] + " " + l.strip()).strip()
    conteo: dict[str, int] = {}
    for f in filas:
        conteo[f["region"]] = conteo.get(f["region"], 0) + 1
    return filas, conteo


def main(pdf: str, destino: str) -> int:
    filas, conteo = extraer(Path(pdf))
    ok = True
    for region, esperado in TOTALES_DOCUMENTO.items():
        obtenido = conteo.get(region, 0)
        marca = "OK " if obtenido == esperado else "ERR"
        ok &= obtenido == esperado
        print(f"{marca} {region:<22} extraídas={obtenido:>3}  documento={esperado:>3}")
    if not ok:
        print("\nLos totales no coinciden con los que imprime el documento. No se escribió ningún archivo.")
        return 1
    Path(destino).parent.mkdir(parents=True, exist_ok=True)
    with open(destino, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["region", "empresa", "pagina"])
        w.writeheader()
        w.writerows(filas)
    print(f"\n{len(filas)} empresas escritas en {destino}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2]))
