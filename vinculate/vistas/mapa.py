"""Mapa territorial único con casillas para elegir qué ver.

* 👥 Personas: se cuentan por MUNICIPIO (campo que ya existe), nunca por dirección. Los municipios se colorean.
* 🏭 Empresas: un punto por empresa en sus COORDENADAS EXACTAS (las que alguien capturó; nada se geocodifica ni se estima).
  Cada empresa tiene su propio color y tamaño según sus vacantes, así las del mismo giro no se confunden.
* 🏫 Instituciones educativas: un punto por universidad o escuela que ya tiene personas asociadas, en las coordenadas que administración
  capturó. Cada institución tiene su color (paleta distinta a la de empresas) y un contorno oscuro; se pueden filtrar por tipo.
* Las capas se pueden ver juntas o por separado en el mismo mapa. Una empresa sin coordenadas jamás bloquea la página: se lista aparte.
* Los límites municipales vienen de geo/tlaxcala_municipios.geojson (validado). Sin ese archivo, las empresas igual se dibujan.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ..auth.sesion import Sesion, actual
from ..components import charts, ui
from ..config import ayudas
from ..config.settings import GEO
from ..config.theme import ESCALA_SEDECO, tema_grafica
from ..core import mapa as nucleo
from ..core import puntos
from ..core.constantes import SIN_DATO
from ..core.ridet import region_de_municipio
from ..core.texto import normalizar_texto
from ..repositories.errores import ErrorDatos
from ..services import datos, empresas, instituciones
from . import ficha

ARCHIVO_GEO = GEO / "tlaxcala_municipios.geojson"
CONTAR = {
    "personas": "Personas únicas",
    "historicos": "Vinculaciones históricas",
    "vacantes": "Vacantes (municipio de la empresa)",
}
FONDOS = {
    "carto-positron": "Claro (CARTO)",
    "open-street-map": "Calles (OpenStreetMap)",
    "white-bg": "Sin fondo (blanco)",
}
TODO_EL_ESTADO = "Todo Tlaxcala"
CONFIG_MAPA = {**charts.CONFIG, "displayModeBar": "hover", "scrollZoom": True, "displaylogo": False,
               "modeBarButtonsToRemove": ["select2d", "lasso2d"]}
ETIQUETA_INST = "§inst"   # primer dato de customdata de los puntos de instituciones (los de empresas llevan el nombre)
_CENTRO_DEFECTO, _ZOOM_DEFECTO = {"lon": -98.2, "lat": 19.4}, 8.5


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


def _vista(lim, enfoque: str, geojson: dict | None, pts: pd.DataFrame, inst: pd.DataFrame | None = None):
    """(centro, zoom) según lo que el usuario quiere acercar: todo el estado, un municipio, una empresa o una institución."""
    inst = pd.DataFrame() if inst is None else inst
    if enfoque.startswith("Institución: "):
        fila = inst[inst["Institución"].eq(enfoque[13:])]
        if not fila.empty:
            return {"lon": float(fila.iloc[0]["Longitud"]), "lat": float(fila.iloc[0]["Latitud"])}, 15.0
    if enfoque.startswith("Empresa: "):
        fila = pts[pts["Empresa"].eq(enfoque[9:])]
        if not fila.empty:
            return {"lon": float(fila.iloc[0]["Longitud"]), "lat": float(fila.iloc[0]["Latitud"])}, 15.0
    if enfoque.startswith("Municipio: ") and geojson:
        sub = {"features": [f for f in geojson["features"] if f["properties"]["municipio"] == enfoque[11:]]}
        lm = nucleo.limites(sub)
        if lm:
            return nucleo.vista_para(lm)
    if lim:
        return nucleo.vista_para(lim)
    todos = pd.concat([x[["Latitud", "Longitud"]] for x in (pts, inst) if not x.empty], ignore_index=True) if (not pts.empty or not inst.empty) else None
    if todos is not None:
        lm = (todos["Longitud"].min() - 0.03, todos["Latitud"].min() - 0.03, todos["Longitud"].max() + 0.03, todos["Latitud"].max() + 0.03)
        return nucleo.vista_para(lm)
    return _CENTRO_DEFECTO, _ZOOM_DEFECTO


def _figura(conteos: pd.DataFrame | None, geojson: dict | None, pts: pd.DataFrame, colores: dict[str, str], *, estilo: str,
            enfoque: str, titulo: str, mostrar_leyenda: bool, inst: pd.DataFrame | None = None,
            colores_inst: dict[str, str] | None = None) -> go.Figure:
    """UN solo mapa: municipios (coloreados o neutros) + un punto por empresa en sus coordenadas.

    Con el estilo «white-bg» no se descarga nada externo; los fondos CARTO / OpenStreetMap piden sus teselas al navegador.
    Si no cargaran (red bloqueada), los municipios y los puntos se ven igual."""
    lim = nucleo.limites(geojson) if geojson else None
    inst = pd.DataFrame() if inst is None else inst
    colores_inst = colores_inst or {}
    centro, zoom = _vista(lim, enfoque, geojson, pts, inst)
    fig = go.Figure()
    con_fondo = estilo != "white-bg"
    if geojson:
        if conteos is not None:
            fig.add_trace(go.Choroplethmap(
                geojson=geojson, locations=conteos["Municipio"], z=conteos["Total"], featureidkey="properties.municipio",
                colorscale=[[i / (len(ESCALA_SEDECO) - 1), c] for i, c in enumerate(ESCALA_SEDECO)], zmin=0,
                marker={"line": {"color": "#FFFFFF", "width": 0.8}, "opacity": 0.72 if con_fondo else 0.92},
                colorbar={"title": "Total", "orientation": "h", "x": 0.01, "xanchor": "left", "y": 0.02, "len": 0.3, "thickness": 10},
                hovertemplate="<b>%{location}</b><br>Total: %{z}<extra></extra>", name="Municipios", showlegend=False))
        else:  # sin capa de personas: municipios solo como referencia (gris claro)
            nombres = [f["properties"]["municipio"] for f in geojson["features"]]
            fig.add_trace(go.Choroplethmap(
                geojson=geojson, locations=nombres, z=[0] * len(nombres), featureidkey="properties.municipio",
                colorscale=[[0, "#EFEAE0"], [1, "#EFEAE0"]], showscale=False,
                marker={"line": {"color": "#9A8F7A", "width": 0.8}, "opacity": 0.45 if con_fondo else 0.9},
                hovertemplate="<b>%{location}</b><extra></extra>", name="Municipios", showlegend=False))
    if not pts.empty:
        # contorno blanco bajo cada punto (no se puede hacer clic en él) para que se distinga sobre cualquier fondo
        fig.add_trace(go.Scattermap(lat=pts["lat_mapa"], lon=pts["lon_mapa"], mode="markers", hoverinfo="skip", showlegend=False,
                                    marker={"size": [puntos.tamano_marcador(v) + 5 for v in pts["Vacantes"]], "color": "#FFFFFF", "opacity": 0.95}))
        for _, r in pts.iterrows():
            fig.add_trace(go.Scattermap(
                lat=[r["lat_mapa"]], lon=[r["lon_mapa"]], mode="markers", name=str(r["Empresa"]), showlegend=mostrar_leyenda,
                legendgroup="empresas", legendgrouptitle_text="Empresas",
                marker={"size": puntos.tamano_marcador(r["Vacantes"]), "color": colores.get(r["Empresa"], "#444444")},
                customdata=[[r["Empresa"], r["Sector"] or SIN_DATO, r["Municipio"] or SIN_DATO, int(r["Vacantes"]), int(r["Vigentes"]),
                             round(float(r["Latitud"]), 6), round(float(r["Longitud"]), 6)]],
                hovertemplate=("<b>%{customdata[0]}</b><br>%{customdata[1]} · %{customdata[2]}<br>Vacantes: %{customdata[3]} "
                               "(vigentes: %{customdata[4]})<br>%{customdata[5]}, %{customdata[6]}<extra></extra>")))
    if not inst.empty:
        # contorno OSCURO bajo cada institución: así se distingue de las empresas (que llevan contorno blanco) aunque coincidan los colores
        fig.add_trace(go.Scattermap(lat=inst["lat_mapa"], lon=inst["lon_mapa"], mode="markers", hoverinfo="skip", showlegend=False,
                                    marker={"size": [puntos.tamano_marcador(v) + 7 for v in inst["Personas"]], "color": "#1B1B1B", "opacity": 0.95}))
        for _, r in inst.iterrows():
            fig.add_trace(go.Scattermap(
                lat=[r["lat_mapa"]], lon=[r["lon_mapa"]], mode="markers", name="🏫 " + str(r["Institución"]), showlegend=mostrar_leyenda,
                legendgroup="instituciones", legendgrouptitle_text="Instituciones educativas",
                marker={"size": puntos.tamano_marcador(r["Personas"]), "color": colores_inst.get(r["Institución"], "#444444")},
                customdata=[[ETIQUETA_INST, r["Institución"], r["Tipo"] or SIN_DATO, r["Municipio"] or SIN_DATO, int(r["Personas"]),
                             round(float(r["Latitud"]), 6), round(float(r["Longitud"]), 6)]],
                hovertemplate=("🏫 <b>%{customdata[1]}</b><br>%{customdata[2]} · %{customdata[3]}<br>Personas: %{customdata[4]}"
                               "<br>%{customdata[5]}, %{customdata[6]}<extra></extra>")))
    fig.update_layout(title=titulo, map={"style": estilo, "center": centro, "zoom": zoom}, uirevision=f"mapa|{enfoque}|{estilo}",
                      legend={"orientation": "v", "x": 1.01, "y": 1, "font": {"size": 11}, "title": {"text": "Clic oculta/muestra"}})
    return tema_grafica(fig, 640)


def _seleccion(ev) -> tuple[str, str] | None:
    """('municipio', NOMBRE) o ('empresa', NOMBRE) según lo que se tocó en el mapa; None si nada."""
    try:
        pts = ev.selection.points if ev and ev.selection else []
    except Exception:  # noqa: BLE001
        pts = []
    if not pts:
        return None
    p = pts[0]
    cd = p.get("customdata")
    if cd and isinstance(cd, (list, tuple)) and len(cd) > 1 and cd[0] == ETIQUETA_INST:
        return "institucion", str(cd[1])
    if cd:
        return "empresa", str(cd[0] if isinstance(cd, (list, tuple)) else cd)
    if p.get("location"):
        return "municipio", str(p["location"])
    return None


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


def _bloque_empresas(sesion: Sesion):
    """(directorio, puntos válidos, sin coordenadas, con problema, hay columnas V004)."""
    vac = datos.vacantes(sesion)
    try:
        cat = empresas.catalogo(sesion)
    except ErrorDatos:
        cat = pd.DataFrame()
    dir_ = empresas.directorio(vac, cat)
    if not empresas.tiene_coordenadas(cat):
        return dir_, dir_.iloc[0:0], dir_, dir_.iloc[0:0], False
    ok, sin, mal = puntos.puntos_validos(dir_)
    return dir_, ok, sin, mal, True


def _bloque_instituciones(sesion: Sesion):
    """(directorio, puntos válidos, sin coordenadas, con problema, hay columnas V011) de las instituciones con personas."""
    pers = datos.personas(sesion)
    try:
        cat = instituciones.catalogo(sesion)
    except ErrorDatos:
        cat = pd.DataFrame()
    dir_ = instituciones.directorio(pers, cat)
    if not instituciones.habilitada(sesion):
        return dir_, dir_.iloc[0:0], dir_, dir_.iloc[0:0], False
    ok, sin, mal = puntos.puntos_validos(dir_)
    return dir_, ok, sin, mal, True


@ui.protegido
def render() -> None:
    sesion = actual()
    ui.encabezado("Mapa territorial", "Personas por municipio, empresas e instituciones educativas en su ubicación exacta, en un solo mapa.", "🗺️")
    ver_personas = sesion.puede("personas", "view")
    ver_vacantes = sesion.puede("vacantes", "view")
    if not (ver_personas or ver_vacantes):
        ui.vacio("Tu perfil no tiene acceso a Personas ni a Vacantes, que son los datos que alimentan el mapa.")
        return

    # ---- casillas: qué capas ver
    st.markdown("**Qué quieres ver en el mapa**")
    k1, k2, k3, k4 = st.columns([1, 1, 1, 1])
    capa_personas = k1.checkbox("👥 Personas (por municipio)", value=ver_personas, key="mapa_personas", disabled=not ver_personas,
                                help=ayudas.texto("mapa.casilla_personas") if ver_personas else "Tu perfil no puede ver Personas.")
    capa_empresas = k2.checkbox("🏭 Empresas (ubicación exacta)", value=ver_vacantes, key="mapa_empresas", disabled=not ver_vacantes,
                                help=ayudas.texto("mapa.casilla_empresas") if ver_vacantes else "Tu perfil no puede ver Vacantes.")
    capa_inst = k3.checkbox("🏫 Instituciones educativas", value=False, key="mapa_instituciones", disabled=not ver_personas,
                            help=ayudas.texto("mapa.casilla_instituciones") if ver_personas else "Tu perfil no puede ver Personas.")
    capa_personas = capa_personas and ver_personas
    capa_empresas = capa_empresas and ver_vacantes
    capa_inst = capa_inst and ver_personas

    # ---- datos de cada capa
    medida = st.session_state.get("mapa_contar", "personas")
    if medida not in CONTAR or (medida == "vacantes" and not ver_vacantes) or (medida != "vacantes" and not ver_personas):
        medida = "personas" if ver_personas else "vacantes"
    serie = detalle = cols = None
    aviso, conteos, otros = "", None, {}
    if capa_personas:
        serie, detalle, cols, aviso = _serie_capa(sesion, medida)
        if aviso != "sin_ubicacion":
            conteos, otros = nucleo.conteos_por_municipio(serie)
    dir_ = ok = sin = mal = None
    hay_coords = True
    if capa_empresas:
        dir_, ok, sin, mal, hay_coords = _bloque_empresas(sesion)

    dir_i = ok_i = sin_i = mal_i = None
    hay_cols_i = True
    if capa_inst:
        dir_i, ok_i, sin_i, mal_i, hay_cols_i = _bloque_instituciones(sesion)

    # ---- opciones
    estilo, enfoque, separar, solo_vigentes, elegidas = "carto-positron", TODO_EL_ESTADO, True, False, None
    tipos_i, elegidas_i = list(instituciones.TIPOS), None
    res = _geo(_firma_geo())
    geo = res.geojson if (res is not None and res.ok) else None
    with st.expander("⚙️ Opciones del mapa", expanded=False):
        o1, o2 = st.columns(2)
        if capa_personas:
            medida = o1.selectbox("Colorear municipios por", [m for m in CONTAR if (m == "vacantes" and ver_vacantes) or (m != "vacantes" and ver_personas)],
                                  format_func=lambda m: CONTAR[m], key="mapa_contar")
        estilo = o2.selectbox("Fondo del mapa", list(FONDOS), format_func=lambda f: FONDOS[f], key="mapa_fondo")
        if capa_empresas and ok is not None and not ok.empty:
            e1, e2 = st.columns(2)
            solo_vigentes = e1.toggle("Solo empresas con vacantes vigentes", key="mapa_solo_vigentes")
            separar = e2.toggle("Separar empresas que comparten ubicación (solo visual)", value=True, key="mapa_separar",
                                help=ayudas.texto("mapa.separar_empresas"))
            elegidas = st.multiselect("Mostrar solo estas empresas", sorted(ok["Empresa"]), key="mapa_filtro_emp", placeholder="Todas")
        if capa_inst and ok_i is not None and not ok_i.empty:
            i1, i2 = st.columns(2)
            tipos_i = i1.multiselect("Tipos de institución", list(instituciones.TIPOS), default=list(instituciones.TIPOS), key="mapa_tipos_inst",
                                     help=ayudas.texto("mapa.tipos_institucion"))
            elegidas_i = i2.multiselect("Mostrar solo estas instituciones", sorted(ok_i["Institución"]), key="mapa_filtro_inst", placeholder="Todas")
        opciones_enfoque = [TODO_EL_ESTADO]
        if geo:
            opciones_enfoque += ["Municipio: " + m for m in sorted(f["properties"]["municipio"] for f in geo["features"])]
        if capa_empresas and ok is not None and not ok.empty:
            opciones_enfoque += ["Empresa: " + e for e in sorted(ok["Empresa"])]
        if capa_inst and ok_i is not None and not ok_i.empty:
            opciones_enfoque += ["Institución: " + e for e in sorted(ok_i["Institución"])]
        enfoque = st.selectbox("Acercar a", opciones_enfoque, key="mapa_enfocar")

    # ---- empresas visibles
    pts = pd.DataFrame()
    colores: dict[str, str] = {}
    if capa_empresas and ok is not None and not ok.empty:
        colores = puntos.asignar_colores(ok["Empresa"].tolist())  # colores fijos aunque se filtren
        pts = ok
        if solo_vigentes:
            pts = pts[pts["Vigentes"] > 0]
        if elegidas:
            pts = pts[pts["Empresa"].isin(elegidas)]
        pts = puntos.separar_superpuestos(pts) if separar else pts.assign(lat_mapa=pts["Latitud"], lon_mapa=pts["Longitud"])

    # ---- instituciones visibles
    pts_i = pd.DataFrame()
    colores_i: dict[str, str] = {}
    if capa_inst and ok_i is not None and not ok_i.empty:
        colores_i = puntos.asignar_colores(ok_i["Institución"].tolist(), puntos.PALETA_INSTITUCIONES)  # colores fijos aunque se filtren
        pts_i = ok_i
        if tipos_i != list(instituciones.TIPOS):
            pts_i = pts_i[pts_i["Tipo"].isin(tipos_i)]
        if elegidas_i:
            pts_i = pts_i[pts_i["Institución"].isin(elegidas_i)]
        pts_i = puntos.separar_superpuestos(pts_i, col="Institución")

    # ---- indicadores
    if capa_personas and aviso == "sin_ubicacion":
        st.warning("Todavía no hay municipio capturado para las empresas (o la migración V004 no está aplicada), así que no se pueden "
                   "colorear municipios por vacantes. No se usa ninguna ubicación estimada.")
    if capa_personas and conteos is not None:
        total = int(conteos["Total"].sum() + sum(otros.values()))
        en_mapa = int(conteos["Total"].sum())
        c = st.columns(4)
        ui.kpi("Con municipio de Tlaxcala", en_mapa, ui.fmt_pct(en_mapa, total) + " del total", contenedor=c[0], info="mapa.con_municipio")
        ui.kpi("Fuera de Tlaxcala", otros["Fuera de Tlaxcala"], contenedor=c[1], info="mapa.fuera_de_tlaxcala")
        ui.kpi("Sin municipio definido", otros["Sin municipio definido"], "no se dibujan en el mapa", contenedor=c[2], info="mapa.sin_municipio")
        ui.kpi("Municipios con registros", int((conteos["Total"] > 0).sum()), "de 60", contenedor=c[3], info="mapa.municipios_con_registros")
        if otros["Ubicación no reconocida"]:
            st.warning(f"{otros['Ubicación no reconocida']} registro(s) tienen una ubicación que no coincide con ningún municipio ni estado del catálogo.")
    if capa_empresas and dir_ is not None:
        c = st.columns(4)
        total_e = len(dir_)
        ui.kpi("Empresas en el mapa", len(ok), f"de {total_e} registradas", contenedor=c[0], info="mapa.empresas_en_mapa")
        ui.kpi("Sin coordenadas", len(sin), "no se dibujan", contenedor=c[1], info="mapa.sin_coordenadas")
        ui.kpi("Coordenadas con problema", len(mal), "revísalas abajo" if len(mal) else "", contenedor=c[2], info="mapa.coordenadas_con_problema")
        ui.kpi("Vacantes vigentes en el mapa", int(pts["Vigentes"].sum()) if not pts.empty else 0, contenedor=c[3],
               info="mapa.vacantes_vigentes_en_mapa")
        if not hay_coords:
            st.info("La base todavía no tiene las columnas de latitud/longitud de empresas (migración V004). Aplícala en Supabase para poder "
                    "dibujar empresas; mientras tanto no se inventa ninguna ubicación.")
        fuera = int((~ok["En Tlaxcala"]).sum()) if not ok.empty else 0
        if fuera:
            st.warning(f"{fuera} empresa(s) tienen coordenadas fuera de Tlaxcala. Si no deberían, revísalas (¿latitud y longitud invertidas?).")

    if capa_inst and dir_i is not None:
        c = st.columns(4)
        ui.kpi("Instituciones en el mapa", len(ok_i), f"de {len(dir_i)} con personas", contenedor=c[0], info="mapa.instituciones_en_mapa")
        ui.kpi("Instituciones sin coordenadas", len(sin_i), "no se dibujan", contenedor=c[1], info="mapa.inst_sin_coordenadas")
        ui.kpi("Instituciones con problema", len(mal_i), "coordenadas inválidas" if len(mal_i) else "", contenedor=c[2], info="mapa.inst_con_problema")
        ui.kpi("Personas en las instituciones mostradas", int(pts_i["Personas"].sum()) if not pts_i.empty else 0, contenedor=c[3],
               info="mapa.inst_personas_en_mapa")
        if not hay_cols_i:
            st.info("La base todavía no tiene las columnas de ubicación de instituciones (migración V011). Aplícala en Supabase para poder "
                    "dibujarlas; mientras tanto no se inventa ninguna ubicación.")
        fuera_i = int((~ok_i["En Tlaxcala"]).sum()) if not ok_i.empty else 0
        if fuera_i:
            st.warning(f"{fuera_i} institución(es) tienen coordenadas fuera de Tlaxcala. Si no deberían, corrígelas en Administración → Instituciones.")

    if not (capa_personas or capa_empresas or capa_inst):
        ui.vacio("Marca al menos una casilla (Personas, Empresas o Instituciones) para dibujar el mapa.")
        return
    if capa_personas and conteos is not None and conteos["Total"].sum() == 0 and not capa_empresas:
        ui.vacio("Ningún registro tiene un municipio de Tlaxcala identificado con los datos actuales.")
        return
    if capa_inst and pts_i.empty and not capa_personas and not capa_empresas:
        st.info("Todavía no hay instituciones con coordenadas capturadas. Administración las captura en **Administración → Instituciones** "
                "y aparecerán aquí.")
    if capa_empresas and pts.empty and not capa_personas:
        st.info("Todavía no hay empresas con coordenadas capturadas. Captúralas en **Vacantes → Empresas** (edición rápida de coordenadas) "
                "y aparecerán aquí.")

    # ---- el mapa
    titulo = " + ".join(t for t, on in ((CONTAR[medida] + " por municipio", capa_personas and conteos is not None), ("Empresas", capa_empresas),
                                        ("Instituciones educativas", capa_inst)) if on)
    elegido = None
    if geo is not None or not pts.empty or not pts_i.empty:
        if geo is None:
            _como_activar(res)
        ui.ayuda_grafica("mapa.grafica_mapa", fila_propia=True)
        ev = st.plotly_chart(_figura(conteos if capa_personas else None, geo, pts, colores, estilo=estilo, enfoque=enfoque,
                                     titulo=titulo, mostrar_leyenda=0 < len(pts) + len(pts_i) <= 40, inst=pts_i, colores_inst=colores_i),
                             key="mapa_unico", width="stretch", config=CONFIG_MAPA, on_select="rerun", selection_mode="points")
        elegido = _seleccion(ev)
        ui.nota("Rueda del ratón para acercar · arrastra para mover · clic en un municipio, una empresa o una institución para ver su detalle.")
    else:
        _como_activar(res)
        if conteos is not None:
            top = conteos[conteos["Total"] > 0].sort_values("Total", ascending=False).head(20)
            elegido_rank = charts.mostrar_seleccionable(charts.barras_h(top, "Municipio", "Total",
                                                                        "Municipios con más registros (clic para ver el detalle)"), f"mapa_rank_{medida}")
            elegido = ("municipio", elegido_rank) if elegido_rank else None

    # ---- tablas de apoyo
    if capa_personas and conteos is not None:
        tabla = conteos.assign(**{"Región RIDET": conteos["Municipio"].map(lambda m: region_de_municipio(m) or "")})
        tabla = tabla.sort_values(["Total", "Municipio"], ascending=[False, True]).reset_index(drop=True)
        with st.expander("Tabla completa de los 60 municipios"):
            ui.ayuda_grafica("mapa.tabla_municipios", fila_propia=True)
            ui.tabla(tabla, altura=420)
            ui.boton_exportar(sesion, "personas" if medida in ("personas", "historicos") else "vacantes", tabla, f"mapa_{medida}", f"mapa_{medida}")
    if capa_empresas and dir_ is not None and hay_coords:
        if len(sin):
            with st.expander(f"Empresas sin coordenadas ({len(sin)})"):
                ui.ayuda_grafica("mapa.tabla_sin_coordenadas", fila_propia=True)
                ui.nota("No se dibujan hasta que se capturen. Hazlo en Vacantes → Empresas → «Coordenadas exactas (edición rápida)».")
                ui.tabla(sin, ["Empresa", "Sector", "Municipio", "Dirección", "C.P.", "Vacantes"], altura=300)
        if len(mal):
            with st.expander(f"Coordenadas con problema ({len(mal)})", expanded=True):
                ui.ayuda_grafica("mapa.tabla_con_problema", fila_propia=True)
                ui.tabla(mal, ["Empresa", "Latitud", "Longitud", "Problema"], altura=240)

    if capa_inst and dir_i is not None and hay_cols_i:
        if len(sin_i):
            with st.expander(f"Instituciones sin coordenadas ({len(sin_i)})"):
                ui.ayuda_grafica("mapa.tabla_inst_sin_coordenadas", fila_propia=True)
                ui.nota("No se dibujan hasta que administración capture sus coordenadas en Administración → Instituciones.")
                ui.tabla(sin_i, ["Institución", "Tipo", "Municipio", "Personas"], altura=300)
        if len(mal_i):
            with st.expander(f"Instituciones con coordenadas con problema ({len(mal_i)})", expanded=True):
                ui.ayuda_grafica("mapa.tabla_inst_con_problema", fila_propia=True)
                ui.tabla(mal_i, ["Institución", "Latitud", "Longitud", "Problema"], altura=240)

    # ---- detalle de lo tocado en el mapa
    if elegido and elegido[0] == "institucion" and dir_i is not None:
        _detalle_institucion(sesion, elegido[1], dir_i)
    elif elegido and elegido[0] == "empresa" and dir_ is not None:
        _detalle_empresa(sesion, elegido[1], dir_)
    elif elegido and elegido[0] == "municipio" and capa_personas and detalle is not None:
        mun = elegido[1]
        st.markdown(f"#### {mun.title()}")
        col_mun = "municipio" if medida in ("personas", "historicos") else "_municipio"
        filas = detalle[detalle[col_mun].map(lambda v: nucleo.clasificar_ubicacion(v)[1]).eq(mun)]
        ui.nota(f"{len(filas)} registro(s) · Región RIDET: {region_de_municipio(mun) or SIN_DATO}")
        idx = ui.tabla(filas.reset_index(drop=True), cols, altura=300, key=f"mapa_det_{medida}", seleccionable=medida == "personas")
        if idx is not None and medida == "personas":
            fila = filas.reset_index(drop=True).iloc[idx]
            if st.button(f"Abrir ficha de {fila['nombre']}", key="mapa_ficha"):
                ficha.dialogo(str(fila["id_persona_maestro"]))


def _detalle_empresa(sesion: Sesion, nombre: str, dir_: pd.DataFrame) -> None:
    fila = dir_[dir_["Empresa"].eq(nombre)]
    if fila.empty:
        return
    f = fila.iloc[0]
    st.markdown(f"#### 🏭 {nombre}")
    partes = [f["Sector"] or SIN_DATO, f["Municipio"] or SIN_DATO]
    if f["Dirección"]:
        partes.append(f["Dirección"] + (f" (C.P. {f['C.P.']})" if f["C.P."] else ""))
    ui.nota(" · ".join(partes) + f" · Coordenadas: {f['Latitud']}, {f['Longitud']}")
    vac = datos.vacantes(sesion)
    mias = vac[vac["Empresa"].map(normalizar_texto).eq(normalizar_texto(nombre))] if not vac.empty else vac
    if mias.empty:
        ui.vacio("Esta empresa no tiene vacantes registradas.")
    else:
        ui.tabla(mias.sort_values("Fecha", ascending=False), ["ID Vacante", "Fecha", "Tipo de Vacante", "Tipo de Oportunidad", "Estado"], altura=300)




def _detalle_institucion(sesion: Sesion, nombre: str, dir_: pd.DataFrame) -> None:
    fila = dir_[dir_["Institución"].eq(nombre)]
    if fila.empty:
        return
    f = fila.iloc[0]
    st.markdown(f"#### 🏫 {nombre}")
    partes = [f["Tipo"] or SIN_DATO, f["Municipio"] or SIN_DATO]
    if f["Dirección"]:
        partes.append(f["Dirección"] + (f" (C.P. {f['C.P.']})" if f["C.P."] else ""))
    ui.nota(" · ".join(partes) + f" · Coordenadas: {f['Latitud']}, {f['Longitud']} · Personas: {int(f['Personas'])}")
    pers = datos.personas(sesion)
    mias = pers[pers["Institución"].astype(str).map(normalizar_texto).eq(normalizar_texto(nombre))] if not pers.empty else pers
    if mias.empty:
        ui.vacio("Esta institución no tiene personas asociadas.")
        return
    cols = [c for c in ("id_persona_maestro", "nombre", "carrera", "escolaridad", "municipio") if c in mias.columns]
    ui.tabla(mias.drop_duplicates("id_persona_maestro") if "id_persona_maestro" in mias.columns else mias, cols, altura=300)
