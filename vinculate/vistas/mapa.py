"""Mapa territorial único con casillas para elegir qué ver.

* 👥 Personas: se cuentan por MUNICIPIO (campo que ya existe), nunca por dirección. Los municipios se colorean.
* 🏭 Empresas: un punto por empresa en sus COORDENADAS EXACTAS (las que alguien capturó; nada se geocodifica ni se estima).
  Cada empresa tiene su propio color y tamaño según sus vacantes, así las del mismo giro no se confunden.
* Las dos capas se pueden ver juntas o por separado en el mismo mapa. Una empresa sin coordenadas jamás bloquea la página: se lista aparte.
* Los límites municipales vienen de geo/tlaxcala_municipios.geojson (validado). Sin ese archivo, las empresas igual se dibujan.
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
from ..core import puntos
from ..core.constantes import SIN_DATO
from ..core.ridet import region_de_municipio
from ..core.texto import normalizar_texto
from ..repositories.errores import ErrorDatos
from ..services import datos, empresas
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


def _vista(lim, enfoque: str, geojson: dict | None, pts: pd.DataFrame):
    """(centro, zoom) según lo que el usuario quiere acercar: todo el estado, un municipio o una empresa."""
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
    if not pts.empty:
        lm = (pts["Longitud"].min() - 0.03, pts["Latitud"].min() - 0.03, pts["Longitud"].max() + 0.03, pts["Latitud"].max() + 0.03)
        return nucleo.vista_para(lm)
    return _CENTRO_DEFECTO, _ZOOM_DEFECTO


def _figura(conteos: pd.DataFrame | None, geojson: dict | None, pts: pd.DataFrame, colores: dict[str, str], *, estilo: str,
            enfoque: str, titulo: str, mostrar_leyenda: bool) -> go.Figure:
    """UN solo mapa: municipios (coloreados o neutros) + un punto por empresa en sus coordenadas.

    Con el estilo «white-bg» no se descarga nada externo; los fondos CARTO / OpenStreetMap piden sus teselas al navegador.
    Si no cargaran (red bloqueada), los municipios y los puntos se ven igual."""
    lim = nucleo.limites(geojson) if geojson else None
    centro, zoom = _vista(lim, enfoque, geojson, pts)
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
                marker={"size": puntos.tamano_marcador(r["Vacantes"]), "color": colores.get(r["Empresa"], "#444444")},
                customdata=[[r["Empresa"], r["Sector"] or SIN_DATO, r["Municipio"] or SIN_DATO, int(r["Vacantes"]), int(r["Vigentes"]),
                             round(float(r["Latitud"]), 6), round(float(r["Longitud"]), 6)]],
                hovertemplate=("<b>%{customdata[0]}</b><br>%{customdata[1]} · %{customdata[2]}<br>Vacantes: %{customdata[3]} "
                               "(vigentes: %{customdata[4]})<br>%{customdata[5]}, %{customdata[6]}<extra></extra>")))
    fig.update_layout(title=titulo, map={"style": estilo, "center": centro, "zoom": zoom}, uirevision=f"mapa|{enfoque}|{estilo}",
                      legend={"orientation": "v", "x": 1.01, "y": 1, "font": {"size": 11}, "title": {"text": "Empresas (clic oculta/muestra)"}})
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


@ui.protegido
def render() -> None:
    sesion = actual()
    ui.encabezado("Mapa territorial", "Personas por municipio y empresas en su ubicación exacta, en un solo mapa.", "🗺️")
    ver_personas = sesion.puede("personas", "view")
    ver_vacantes = sesion.puede("vacantes", "view")
    if not (ver_personas or ver_vacantes):
        ui.vacio("Tu perfil no tiene acceso a Personas ni a Vacantes, que son los datos que alimentan el mapa.")
        return

    # ---- casillas: qué capas ver
    st.markdown("**Qué quieres ver en el mapa**")
    k1, k2, k3 = st.columns([1, 1, 2])
    capa_personas = k1.checkbox("👥 Personas (por municipio)", value=ver_personas, key="mapa_personas", disabled=not ver_personas,
                                help="Colorea cada municipio según cuántos registros tiene." if ver_personas else "Tu perfil no puede ver Personas.")
    capa_empresas = k2.checkbox("🏭 Empresas (ubicación exacta)", value=ver_vacantes, key="mapa_empresas", disabled=not ver_vacantes,
                                help="Un punto por empresa, en las coordenadas capturadas." if ver_vacantes else "Tu perfil no puede ver Vacantes.")
    capa_personas = capa_personas and ver_personas
    capa_empresas = capa_empresas and ver_vacantes

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

    # ---- opciones
    estilo, enfoque, separar, solo_vigentes, elegidas = "carto-positron", TODO_EL_ESTADO, True, False, None
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
                                help="Si dos empresas tienen EXACTAMENTE las mismas coordenadas, se reparten unos metros en círculo para que "
                                     "ninguna tape a otra. Al pasar el cursor siempre ves las coordenadas reales.")
            elegidas = st.multiselect("Mostrar solo estas empresas", sorted(ok["Empresa"]), key="mapa_filtro_emp", placeholder="Todas")
        opciones_enfoque = [TODO_EL_ESTADO]
        if geo:
            opciones_enfoque += ["Municipio: " + m for m in sorted(f["properties"]["municipio"] for f in geo["features"])]
        if capa_empresas and ok is not None and not ok.empty:
            opciones_enfoque += ["Empresa: " + e for e in sorted(ok["Empresa"])]
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

    # ---- indicadores
    if capa_personas and aviso == "sin_ubicacion":
        st.warning("Todavía no hay municipio capturado para las empresas (o la migración V004 no está aplicada), así que no se pueden "
                   "colorear municipios por vacantes. No se usa ninguna ubicación estimada.")
    if capa_personas and conteos is not None:
        total = int(conteos["Total"].sum() + sum(otros.values()))
        en_mapa = int(conteos["Total"].sum())
        c = st.columns(4)
        ui.kpi("Con municipio de Tlaxcala", en_mapa, ui.fmt_pct(en_mapa, total) + " del total", contenedor=c[0])
        ui.kpi("Fuera de Tlaxcala", otros["Fuera de Tlaxcala"], contenedor=c[1])
        ui.kpi("Sin municipio definido", otros["Sin municipio definido"], "no se dibujan en el mapa", contenedor=c[2])
        ui.kpi("Municipios con registros", int((conteos["Total"] > 0).sum()), "de 60", contenedor=c[3])
        if otros["Ubicación no reconocida"]:
            st.warning(f"{otros['Ubicación no reconocida']} registro(s) tienen una ubicación que no coincide con ningún municipio ni estado del catálogo.")
    if capa_empresas and dir_ is not None:
        c = st.columns(4)
        total_e = len(dir_)
        ui.kpi("Empresas en el mapa", len(ok), f"de {total_e} registradas", contenedor=c[0])
        ui.kpi("Sin coordenadas", len(sin), "no se dibujan", contenedor=c[1])
        ui.kpi("Coordenadas con problema", len(mal), "revísalas abajo" if len(mal) else "", contenedor=c[2])
        ui.kpi("Vacantes vigentes en el mapa", int(pts["Vigentes"].sum()) if not pts.empty else 0, contenedor=c[3])
        if not hay_coords:
            st.info("La base todavía no tiene las columnas de latitud/longitud de empresas (migración V004). Aplícala en Supabase para poder "
                    "dibujar empresas; mientras tanto no se inventa ninguna ubicación.")
        fuera = int((~ok["En Tlaxcala"]).sum()) if not ok.empty else 0
        if fuera:
            st.warning(f"{fuera} empresa(s) tienen coordenadas fuera de Tlaxcala. Si no deberían, revísalas (¿latitud y longitud invertidas?).")

    ui.explicacion("Personas: campo «municipio» de la base. Empresas: latitud y longitud capturadas por tu equipo (Vacantes → Empresas).",
                   "El color de cada municipio es el conteo de registros. Cada empresa es un punto con su propio color, más grande si tiene más vacantes.",
                   "Es la distribución de la base actual, no de la población. Una empresa sin coordenadas no aparece; no se estima su ubicación.")
    if not capa_personas and not capa_empresas:
        ui.vacio("Marca al menos una casilla (Personas o Empresas) para dibujar el mapa.")
        return
    if capa_personas and conteos is not None and conteos["Total"].sum() == 0 and not capa_empresas:
        ui.vacio("Ningún registro tiene un municipio de Tlaxcala identificado con los datos actuales.")
        return
    if capa_empresas and pts.empty and not capa_personas:
        st.info("Todavía no hay empresas con coordenadas capturadas. Captúralas en **Vacantes → Empresas** (edición rápida de coordenadas) "
                "y aparecerán aquí.")

    # ---- el mapa
    titulo = " + ".join(t for t, on in ((CONTAR[medida] + " por municipio", capa_personas and conteos is not None), ("Empresas", capa_empresas)) if on)
    elegido = None
    if geo is not None or not pts.empty:
        if geo is None:
            _como_activar(res)
        ev = st.plotly_chart(_figura(conteos if capa_personas else None, geo, pts, colores, estilo=estilo, enfoque=enfoque,
                                     titulo=titulo, mostrar_leyenda=0 < len(pts) <= 40),
                             key="mapa_unico", width="stretch", config=CONFIG_MAPA, on_select="rerun", selection_mode="points")
        elegido = _seleccion(ev)
        ui.nota("Rueda del ratón para acercar · arrastra para mover · clic en un municipio o una empresa para ver su detalle.")
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
            ui.tabla(tabla, altura=420)
            ui.boton_exportar(sesion, "personas" if medida in ("personas", "historicos") else "vacantes", tabla, f"mapa_{medida}", f"mapa_{medida}")
    if capa_empresas and dir_ is not None and hay_coords:
        if len(sin):
            with st.expander(f"Empresas sin coordenadas ({len(sin)})"):
                ui.nota("No se dibujan hasta que se capturen. Hazlo en Vacantes → Empresas → «Coordenadas exactas (edición rápida)».")
                ui.tabla(sin, ["Empresa", "Sector", "Municipio", "Dirección", "C.P.", "Vacantes"], altura=300)
        if len(mal):
            with st.expander(f"Coordenadas con problema ({len(mal)})", expanded=True):
                ui.tabla(mal, ["Empresa", "Latitud", "Longitud", "Problema"], altura=240)

    # ---- detalle de lo tocado en el mapa
    if elegido and elegido[0] == "empresa" and dir_ is not None:
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


