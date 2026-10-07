"""Mapa territorial por municipio (Etapa 1: agregación por municipio, sin geocodificación).

* Personas y vacantes se cuentan por MUNICIPIO (campo que ya existe), nunca por dirección.
* El mapa se dibuja solo con geometría oficial validada (geo/tlaxcala_municipios.geojson). Sin ese
  archivo la página funciona igual: muestra el ranking de los 60 municipios y cómo activar el mapa.
* Nada depende de latitud/longitud: un registro sin coordenadas jamás bloquea esta página.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ..auth.sesion import Sesion, actual
from ..components import charts, ui
from ..config.settings import GEO
from ..config.theme import ESCALA_SEDECO, tema_grafica
from ..core import mapa as nucleo
from ..core.ridet import region_de_municipio
from ..core.texto import normalizar_texto
from ..repositories.errores import ErrorDatos
from ..services import datos, empresas
from . import ficha

ARCHIVO_GEO = GEO / "tlaxcala_municipios.geojson"
CAPAS = {
    "personas": "Personas únicas",
    "historicos": "Vinculaciones históricas",
    "vacantes": "Vacantes (municipio de la empresa)",
    "empresas": "Empresas con vacantes",
}


@st.cache_data(show_spinner=False)
def _geo(firma: tuple):
    """Geometría validada (se vuelve a leer solo si el archivo cambia: la firma es mtime+tamaño)."""
    return nucleo.cargar_geojson(ARCHIVO_GEO)


def _firma_geo() -> tuple:
    try:
        st_ = ARCHIVO_GEO.stat()
        return (st_.st_mtime_ns, st_.st_size)
    except OSError:
        return ()


def _municipio_de_vacantes(sesion: Sesion, vac: pd.DataFrame) -> tuple[pd.DataFrame, bool]:
    """Vacantes con su municipio (excepción de la vacante > municipio de la empresa). Segundo valor: hay datos de ubicación."""
    if vac.empty:
        return vac.assign(_municipio=pd.Series(dtype=str)), False
    try:
        cat = empresas.catalogo(sesion)
    except ErrorDatos:
        cat = pd.DataFrame()
    por_empresa = {}
    if empresas.tiene_ubicacion(cat) and not cat.empty:
        por_empresa = {normalizar_texto(r["nombre"]): str(r["municipio"]).strip() for _, r in cat.iterrows()
                       if str(r.get("municipio") or "").strip() and str(r.get("municipio")).lower() != "nan"}
    v = vac.copy()
    v["_municipio"] = v["Empresa"].map(lambda e: por_empresa.get(normalizar_texto(e), ""))
    if "municipio_excepcion" in v.columns:
        exc = v["municipio_excepcion"].fillna("").astype(str).str.strip()
        v["_municipio"] = exc.where(exc.ne("") & exc.str.lower().ne("nan"), v["_municipio"])
    return v, bool(por_empresa) or ("municipio_excepcion" in v.columns and v["_municipio"].ne("").any())


def _serie_capa(sesion: Sesion, capa: str):
    """(serie de municipios, detalle de filas para el drill-down, columnas a mostrar, nota de cobertura)."""
    if capa == "personas":
        m = datos.maestras(sesion)
        return m["municipio"] if not m.empty else pd.Series(dtype=str), m, ["id_persona_maestro", "nombre", "carrera", "Institución"], ""
    if capa == "historicos":
        p = datos.personas(sesion)
        return p["municipio"] if not p.empty else pd.Series(dtype=str), p, ["id_persona", "nombre", "vinculacion", "Año"], ""
    vac = datos.vacantes(sesion)
    v, hay = _municipio_de_vacantes(sesion, vac)
    if vac.empty:
        return pd.Series(dtype=str), v, [], ""
    if not hay:
        return pd.Series(dtype=str), v, [], "sin_ubicacion"
    if capa == "empresas":
        u = v.drop_duplicates("Empresa")
        return u["_municipio"], u, ["Empresa", "Sector Empresa"], ""
    return v["_municipio"], v, ["ID Vacante", "Empresa", "Tipo de Vacante", "Estado"], ""


def _figura(conteos: pd.DataFrame, geojson: dict, titulo: str) -> go.Figure:
    """Mapa de coropletas SIN descargas externas: usa el estilo «white-bg» (fondo blanco incluido en Plotly),
    así funciona aunque la red bloquee CDNs o servidores de teselas. No dibuja nada fuera de los 60 polígonos."""
    lim = nucleo.limites(geojson)
    centro, zoom = nucleo.vista_para(lim) if lim else ({"lon": -98.2, "lat": 19.4}, 8.5)
    fig = go.Figure(go.Choroplethmap(
        geojson=geojson, locations=conteos["Municipio"], z=conteos["Total"], featureidkey="properties.municipio",
        colorscale=[[i / (len(ESCALA_SEDECO) - 1), c] for i, c in enumerate(ESCALA_SEDECO)], zmin=0,
        marker={"line": {"color": "#FFFFFF", "width": 0.8}, "opacity": 0.92}, colorbar={"title": "Total"},
        hovertemplate="<b>%{location}</b><br>Total: %{z}<extra></extra>"))
    fig.update_layout(title=titulo, map={"style": "white-bg", "center": centro, "zoom": zoom})
    return tema_grafica(fig, 560)


def _seleccion(ev) -> str | None:
    try:
        pts = ev.selection.points if ev and ev.selection else []
    except Exception:  # noqa: BLE001
        pts = []
    return str(pts[0].get("location")) if pts and pts[0].get("location") else None


def _como_activar(res) -> None:
    if res is not None and not res.ok:
        st.error("El archivo de geometría existe, pero NO pasó la validación, así que el mapa no se dibuja:", icon="⚠️")
        for p in res.problemas[:8]:
            st.write("• " + p)
    else:
        st.info("El mapa dibujado se activa cuando el repositorio incluye la geometría oficial de los municipios de Tlaxcala "
                "(INEGI). Mientras tanto puedes ver el ranking por municipio, que usa exactamente los mismos datos.", icon="🗺️")
    with st.expander("Cómo activar el mapa"):
        st.markdown(
            "1. Descarga la capa de **municipios** del Marco Geoestadístico de INEGI y conviértela a GeoJSON (QGIS o mapshaper.org).\n"
            "2. Ejecuta `python scripts/preparar_geometria.py ARCHIVO.geojson`: filtra Tlaxcala (entidad 29), exige los **60** municipios "
            "y escribe `geo/tlaxcala_municipios.geojson`.\n"
            "3. Sube ese archivo al repositorio y vuelve a desplegar. No hace falta cambiar código."
        )


@ui.protegido
def render() -> None:
    sesion = actual()
    ui.encabezado("Mapa territorial", "Dónde están las personas y las oportunidades, por municipio de Tlaxcala.", "🗺️")
    capas = {k: v for k, v in CAPAS.items() if sesion.puede("personas" if k in ("personas", "historicos") else "vacantes", "view")}
    if not capas:
        ui.vacio("Tu perfil no tiene acceso a Personas ni a Vacantes, que son los datos que alimentan el mapa.")
        return
    capa = st.segmented_control("Capa", list(capas), format_func=lambda k: capas[k], default=next(iter(capas)),
                                key="mapa_capa", label_visibility="collapsed") or next(iter(capas))
    serie, detalle, cols, aviso = _serie_capa(sesion, capa)
    if aviso == "sin_ubicacion":
        st.warning("Todavía no hay municipio capturado para las empresas (o la migración V004 no está aplicada), así que no se puede ubicar "
                   "ninguna vacante. Captura el municipio en Vacantes → Empresas; no se usa ninguna ubicación estimada.")
        return
    conteos, otros = nucleo.conteos_por_municipio(serie)
    total = int(conteos["Total"].sum() + sum(otros.values()))
    en_mapa = int(conteos["Total"].sum())

    c = st.columns(4)
    ui.kpi("Con municipio de Tlaxcala", en_mapa, ui.fmt_pct(en_mapa, total) + " del total", contenedor=c[0])
    ui.kpi("Fuera de Tlaxcala", otros["Fuera de Tlaxcala"], contenedor=c[1])
    ui.kpi("Sin municipio definido", otros["Sin municipio definido"], "no se dibujan en el mapa", contenedor=c[2])
    ui.kpi("Municipios con registros", int((conteos["Total"] > 0).sum()), "de 60", contenedor=c[3])
    if otros["Ubicación no reconocida"]:
        st.warning(f"{otros['Ubicación no reconocida']} registro(s) tienen una ubicación que no coincide con ningún municipio ni estado del catálogo.")
    ui.explicacion("Campo «municipio» de la base (personas) o municipio capturado de la empresa / excepción de la vacante (vacantes).",
                   "Cuenta registros por municipio de Tlaxcala. Lo que no tiene municipio o está fuera del estado se informa aparte, no se reparte.",
                   "Un color más intenso es más registros en ese municipio. Es una distribución de la base actual, no de la población del municipio.")
    if conteos["Total"].sum() == 0:
        ui.vacio("Ningún registro tiene un municipio de Tlaxcala identificado con los datos actuales.")
        return

    res = _geo(_firma_geo())
    elegido = None
    if res is not None and res.ok:
        ev = st.plotly_chart(_figura(conteos, res.geojson, CAPAS[capa] + " por municipio"), key=f"mapa_{capa}", width="stretch",
                             config=charts.CONFIG, on_select="rerun", selection_mode="points")
        elegido = _seleccion(ev)
        ui.nota("Haz clic en un municipio para ver sus registros.")
    else:
        _como_activar(res)
        top = conteos[conteos["Total"] > 0].sort_values("Total", ascending=False).head(20)
        sel = charts.mostrar_seleccionable(charts.barras_h(top.rename(columns={"Total": "Total"}), "Municipio", "Total",
                                                           "Municipios con más registros (clic para ver el detalle)"), f"mapa_rank_{capa}")
        elegido = sel

    tabla = conteos.assign(**{"Región RIDET": conteos["Municipio"].map(lambda m: region_de_municipio(m) or "")})
    tabla = tabla.sort_values(["Total", "Municipio"], ascending=[False, True]).reset_index(drop=True)
    with st.expander("Tabla completa de los 60 municipios"):
        ui.tabla(tabla, altura=420)
        ui.boton_exportar(sesion, "personas" if capa in ("personas", "historicos") else "vacantes", tabla,
                          f"mapa_{capa}", f"mapa_{capa}")

    if elegido:
        st.markdown(f"#### {elegido.title()}")
        col_mun = "municipio" if capa in ("personas", "historicos") else "_municipio"
        filas = detalle[detalle[col_mun].map(lambda v: nucleo.clasificar_ubicacion(v)[1]).eq(elegido)]
        ui.nota(f"{len(filas)} registro(s) · Región RIDET: {region_de_municipio(elegido) or 'Información no disponible'}")
        idx = ui.tabla(filas.reset_index(drop=True), cols, altura=300, key=f"mapa_det_{capa}", seleccionable=capa == "personas")
        if idx is not None and capa == "personas":
            fila = filas.reset_index(drop=True).iloc[idx]
            if st.button(f"Abrir ficha de {fila['nombre']}", key="mapa_ficha"):
                ficha.dialogo(str(fila["id_persona_maestro"]))
