"""Prepara `geo/tlaxcala_municipios.geojson` a partir de la geometría oficial de INEGI.

Uso:
    python scripts/preparar_geometria.py ENTRADA.geojson [salida.geojson] [--decimales 4]

ENTRADA puede ser el GeoJSON de municipios de todo el país o solo de Tlaxcala. Dónde obtenerlo:
  Marco Geoestadístico (INEGI) → https://www.inegi.org.mx/temas/mg/  (capa «municipios», clave de entidad 29).
  Si INEGI lo entrega como Shapefile, conviértelo primero a GeoJSON (QGIS: «Exportar → GeoJSON», o
  mapshaper.org: arrastra el .shp y exporta «GeoJSON»; en mapshaper puedes simplificar al 10 %).

El script:
  1. se queda solo con la entidad 29,
  2. redondea coordenadas (archivo más ligero),
  3. valida que sean EXACTAMENTE los 60 municipios (cada nombre se compara con el catálogo de la app),
  4. escribe el archivo SOLO si todo coincide; si no, lista los problemas y no escribe nada.
  5. si todos los municipios traen su clave de 3 dígitos, escribe también `geo/cve_mun_municipios.sql`
     (UPDATE de catalogo_municipios_tlaxcala.cve_mun; requiere V004; no toca filas que ya tengan clave distinta).
No requiere librerías externas.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vinculate.core.mapa import ENTIDAD_TLAXCALA, validar_geojson  # noqa: E402


def _redondear(coords, d: int):
    if isinstance(coords, (int, float)):
        return round(coords, d)
    return [_redondear(c, d) for c in coords]


def _entidad(props: dict) -> str:
    for k in ("CVE_ENT", "cve_ent", "CVEENT"):
        if props.get(k) not in (None, ""):
            return str(props[k]).zfill(2)
    for k in ("CVEGEO", "cvegeo"):
        if props.get(k):
            return str(props[k])[:2]
    return ""


def sql_cve_mun(geojson: dict) -> str | None:
    """UPDATE de claves INEGI por nombre de catálogo; None si algún municipio no trae clave válida."""
    claves = {}
    for ft in geojson["features"]:
        p = ft["properties"]
        cve = str(p.get("cve_mun") or "").strip()
        if not (len(cve) == 3 and cve.isdigit()):
            return None
        claves[p["municipio"]] = cve
    filas = ",\n".join(f"  ('{n.replace(chr(39), chr(39) * 2)}', '{c}')" for n, c in sorted(claves.items(), key=lambda x: x[1]))
    return (
        "-- Claves INEGI (CVE_MUN) de los 60 municipios de Tlaxcala. Requiere V004. Solo rellena donde cve_mun es NULL.\n"
        "begin;\n"
        "update public.catalogo_municipios_tlaxcala m set cve_mun = v.cve\n"
        "from (values\n" + filas + "\n) as v(nombre, cve)\n"
        "where m.nombre = v.nombre and m.cve_mun is null;\n"
        "-- Verificación: debe devolver 60 (o menos si el catálogo de tu base no tiene todos).\n"
        "select count(*) as municipios_con_clave from public.catalogo_municipios_tlaxcala where cve_mun is not null;\n"
        "commit;\n"
    )


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 2
    entrada = Path(argv[0])
    salida = Path(argv[1]) if len(argv) > 1 and not argv[1].startswith("--") else Path("geo/tlaxcala_municipios.geojson")
    decimales = int(argv[argv.index("--decimales") + 1]) if "--decimales" in argv else 4
    with open(entrada, encoding="utf-8") as f:
        gj = json.load(f)
    feats = []
    for ft in gj.get("features", []):
        ent = _entidad(ft.get("properties") or {})
        if ent and ent != ENTIDAD_TLAXCALA:
            continue
        g = ft.get("geometry") or {}
        if g.get("coordinates"):
            g = {**g, "coordinates": _redondear(g["coordinates"], decimales)}
        feats.append({**ft, "geometry": g})
    res = validar_geojson({"type": "FeatureCollection", "features": feats})
    if not res.ok:
        print("El archivo NO pasó la validación; no se escribió nada:")
        for p in res.problemas:
            print("  -", p)
        return 1
    salida.parent.mkdir(parents=True, exist_ok=True)
    with open(salida, "w", encoding="utf-8") as f:
        json.dump(res.geojson, f, ensure_ascii=False, separators=(",", ":"))
    print(f"OK: {len(res.geojson['features'])} municipios → {salida} ({salida.stat().st_size / 1024:.0f} KB)")
    sql = sql_cve_mun(res.geojson)
    if sql:
        destino_sql = salida.parent / "cve_mun_municipios.sql"
        destino_sql.write_text(sql, encoding="utf-8")
        print(f"Claves INEGI → {destino_sql}  (ejecútalo en el SQL Editor de Supabase después de V004)")
    else:
        print("Aviso: el archivo no trae la clave de municipio (CVE_MUN) de todos; no se generó el SQL de claves.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
