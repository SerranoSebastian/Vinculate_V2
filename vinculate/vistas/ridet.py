"""Análisis territorial RIDET: regiones, empresas del documento oficial y vacantes clasificadas por región."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from .. import navegacion
from ..auth.sesion import Sesion, actual
from ..components import charts, ui
from ..config.settings import ASSETS, RAIZ
from ..core import ridet as nucleo
from ..core.texto import normalizar_texto
from ..repositories.errores import ErrorDatos
from ..services import datos, empresas

IMG = ASSETS / "ridet"
PDF = ASSETS / "documentos" / "RIDET.pdf"
REFERENCIA = RAIZ / "referencia" / "ridet_empresas.csv"
VISTAS = {"general": "🏠 General", "regiones": "🗂️ Regiones", "empresas": "🏭 Empresas y vacantes",
          "estadisticas": "📊 Estadísticas", "documento": "📄 Documento oficial"}
_CLASE_METODO = {nucleo.METODO_EXACTO: "ok", nucleo.METODO_MUNICIPIO: "ok", nucleo.METODO_ALIAS: "est",
                 nucleo.METODO_PARCIAL: "est", nucleo.METODO_AMBIGUA: "no", nucleo.METODO_NINGUNO: "no"}


@st.cache_data(show_spinner=False)
def _referencia() -> pd.DataFrame:
    """Empresas del documento (archivo estático del repositorio; no contiene datos personales)."""
    return nucleo.cargar_referencia(REFERENCIA)


# ------------------------------------------------------------- visor de imágenes
def _visor(nombres: list[str], clave: str) -> None:
    existentes = [n for n in nombres if (IMG / n).exists()]
    if not existentes:
        ui.vacio("No se encontraron las imágenes de esta sección en assets/ridet/.")
        return
    llave = f"{clave}_i"
    st.session_state[llave] = min(int(st.session_state.get(llave, 0)), len(existentes) - 1)
    if len(existentes) > 1:
        a, b, c = st.columns([1, 4, 1])
        if a.button("◀ Anterior", key=f"{clave}_ant", width="stretch"):
            st.session_state[llave] = (st.session_state[llave] - 1) % len(existentes)
        if c.button("Siguiente ▶", key=f"{clave}_sig", width="stretch"):
            st.session_state[llave] = (st.session_state[llave] + 1) % len(existentes)
        b.markdown(f"<div style='text-align:center' class='vc-nota'>Imagen {st.session_state[llave] + 1} de {len(existentes)}</div>",
                   unsafe_allow_html=True)
    st.image(str(IMG / existentes[st.session_state[llave]]), width="stretch")


# ---------------------------------------------------------------- clasificación
def _municipios_capturados(sesion: Sesion) -> tuple[dict[str, str], bool]:
    """{empresa: municipio} del catálogo (V004). Segundo valor: si la base ya tiene la columna."""
    try:
        cat = empresas.catalogo(sesion)
    except ErrorDatos:
        return {}, False
    if not empresas.tiene_ubicacion(cat):
        return {}, False
    cat = cat[cat["municipio"].fillna("").astype(str).str.strip().ne("")]
    return {str(r["nombre"]).strip(): str(r["municipio"]).strip() for _, r in cat.iterrows()}, True


def _clasificar(sesion: Sesion):
    vac = datos.vacantes(sesion)
    municipios, hay_columna = _municipios_capturados(sesion)
    tabla = nucleo.clasificar_empresas(vac["Empresa"].tolist() if not vac.empty else [], _referencia(), municipios)
    if not vac.empty:
        n_vac = vac.groupby(vac["Empresa"].astype(str).str.strip()).size()
        tabla["Vacantes"] = tabla["empresa"].map(n_vac).fillna(0).astype(int)
    return vac, tabla, hay_columna


# -------------------------------------------------------------------- secciones
def _general() -> None:
    st.markdown("Consulta las seis regiones económicas, sus municipios, empresas e instituciones de educación media superior "
                "según el documento oficial RIDET.")
    _visor(nucleo.IMAGENES_GENERALES, "ridet_general")
    st.markdown("##### Resumen por región")
    ui.tabla(nucleo.resumen_regiones())
    ui.explicacion("Encabezados de cada región del documento oficial RIDET (assets/documentos/RIDET.pdf).",
                   "Municipios, sectores industriales, empresas e instituciones públicas de educación media superior que el documento reporta por región.",
                   "Son cifras del documento, no conteos de la base de vacantes ni de personas.")
    with st.expander("⚠️ Observación sobre los municipios del documento"):
        st.write(nucleo.NOTA_OBSERVACION)


def _regiones() -> None:
    region = st.selectbox("Región", nucleo.NOMBRES_REGION, key="ridet_region")
    fila = next(r for r in nucleo.REGIONES if r["region"] == region)
    c = st.columns(4)
    ui.kpi("Municipios (según el encabezado)", fila["municipios"], contenedor=c[0])
    ui.kpi("Empresas", fila["empresas"], contenedor=c[1])
    ui.kpi("Sectores industriales", fila["sectores"], contenedor=c[2])
    ui.kpi("Instituciones públicas de EMS", fila["ems"], contenedor=c[3])
    st.caption(f"Cabecera regional: {fila['cabecera']}")
    st.markdown("**Municipios de la región:** " + ", ".join(m.title() for m in nucleo.REGION_MUNICIPIOS[region]))
    ref = _referencia()
    if not ref.empty:
        lista = ref[ref["region"] == region]
        with st.expander(f"Empresas que el documento lista en esta región ({len(lista)})"):
            ui.tabla(lista, ["empresa", "pagina"], {"empresa": "Empresa", "pagina": "Página del PDF"}, altura=320)
    _visor(nucleo.IMAGENES_REGION[region], f"ridet_{normalizar_texto(region).replace(' ', '_')}")


def _empresas_y_vacantes(sesion: Sesion) -> None:
    if not sesion.puede("vacantes", "view"):
        ui.vacio("Esta sección cruza el RIDET con la base de vacantes y tu perfil no tiene acceso a Vacantes.")
        return
    vac, tabla, hay_columna = _clasificar(sesion)
    if vac.empty:
        ui.vacio("Todavía no hay vacantes registradas.")
        return
    asignadas = int((tabla["region"] != nucleo.PENDIENTE).sum())
    c = st.columns(3)
    ui.kpi("Empresas con vacantes", len(tabla), contenedor=c[0])
    ui.kpi("Con región asignada", asignadas, ui.fmt_pct(asignadas, len(tabla)) + " de las empresas", contenedor=c[1])
    ui.kpi("Pendientes de asignar", len(tabla) - asignadas, "requieren captura de municipio", contenedor=c[2])
    ui.explicacion("Catálogo de vacantes cruzado con las empresas del documento RIDET (nombre) y, si existe, con el municipio capturado de la empresa.",
                   "Asigna cada empresa a una región RIDET y dice con qué criterio lo hizo.",
                   "«Coincide con el RIDET» es una coincidencia exacta de nombre. «Parcial» o «alias» conviene revisarlas. Una empresa que aparece "
                   "en varias regiones (p. ej. con varias plantas) NO se asigna sola: queda pendiente hasta capturar su municipio.")

    t = tabla.copy()
    t["Criterio"] = t["metodo"]
    ui.tabla(t.sort_values(["region", "Vacantes"], ascending=[True, False]),
             ["empresa", "region", "Criterio", "coincide_con", "Vacantes"],
             {"empresa": "Empresa", "region": "Región", "coincide_con": "Coincide con (RIDET)"}, altura=360)

    pend = tabla[tabla["region"] == nucleo.PENDIENTE]
    if not pend.empty:
        with st.container(border=True):
            st.markdown(f"**{len(pend)} empresa(s) pendiente(s):** " + ", ".join(pend["empresa"]))
            if not hay_columna:
                st.warning("La base todavía no tiene las columnas de ubicación de empresas (migración V004). "
                           "Aplícala en Supabase para poder capturar el municipio de cada empresa.")
            elif sesion.puede("vacantes", "edit") and navegacion.existe("vacantes"):
                if st.button("Capturar el municipio de estas empresas →", key="ridet_ir_empresas"):
                    navegacion.ir_a("vacantes", apartado="empresas")
            else:
                ui.nota("Pide a alguien con permiso de edición en Vacantes que capture el municipio de estas empresas.")

    st.markdown("##### Vacantes por región")
    region_de = dict(zip(tabla["empresa"], tabla["region"]))
    v = vac.copy()
    v["Región RIDET"] = v["Empresa"].astype(str).str.strip().map(region_de).fillna(nucleo.PENDIENTE)
    c1, c2 = st.columns(2)
    reg = c1.selectbox("Región", ["Todas", *nucleo.NOMBRES_REGION, nucleo.PENDIENTE], key="ridet_f_region")
    emp = c2.selectbox("Empresa", ["Todas", *sorted(v["Empresa"].dropna().astype(str).unique())], key="ridet_f_empresa")
    if reg != "Todas":
        v = v[v["Región RIDET"] == reg]
    if emp != "Todas":
        v = v[v["Empresa"] == emp]
    ui.tabla(v, ["ID Vacante", "Empresa", "Región RIDET", "Tipo de Vacante", "Tipo de Oportunidad", "Estado", "Fecha"],
             fechas=("Fecha",), altura=380)
    ui.boton_exportar(sesion, "ridet", v, "vacantes_por_region_ridet", "ridet_vacantes")


def _estadisticas(sesion: Sesion) -> None:
    res = nucleo.resumen_regiones()
    c = st.columns(4)
    ui.kpi("Regiones", len(res), contenedor=c[0])
    ui.kpi("Empresas reportadas", int(res["Empresas"].sum()), "suma de los encabezados del documento", contenedor=c[1])
    ui.kpi("Sectores (suma por región)", int(res["Sectores"].sum()), "un sector puede repetirse entre regiones", contenedor=c[2])
    ui.kpi("Instituciones de EMS", int(res["Instituciones EMS"].sum()), contenedor=c[3])
    charts.mostrar(charts.barras_h(res.rename(columns={"Región": "Región"})[["Región", "Empresas"]], "Región", "Empresas",
                                   "Empresas por región según el documento RIDET", alto=320), "ridet_empresas_region")
    ui.explicacion("Encabezados del documento oficial RIDET.", "Compara cuántas empresas reporta el documento en cada región.",
                   "Una barra mayor es una región con más empresas en el inventario del documento; no mide empleo ni vacantes.")
    if not sesion.puede("vacantes", "view"):
        return
    vac, tabla, _ = _clasificar(sesion)
    if vac.empty or tabla.empty:
        return
    por_region = tabla.groupby("region")["Vacantes"].sum().reset_index().rename(columns={"region": "Región", "Vacantes": "Vacantes"})
    por_region = por_region[por_region["Vacantes"] > 0]
    charts.mostrar(charts.barras_h(por_region, "Región", "Vacantes", "Vacantes registradas por región (las pendientes se muestran aparte)", alto=320),
                   "ridet_vacantes_region")
    ui.explicacion("Vacantes de la base, con cada empresa asignada a una región.",
                   "Cuenta vacantes por región asignada; «Pendiente de asignar» agrupa a las empresas que aún no se pueden ubicar.",
                   "Es un reflejo de las vacantes registradas, no del empleo real de cada región.")


def _documento() -> None:
    st.caption("El PDF es la fuente institucional. Las imágenes de las otras pestañas permiten consultarlo más rápido.")
    if not PDF.exists():
        ui.vacio("No se encontró assets/documentos/RIDET.pdf en el repositorio.")
        return
    mb = PDF.stat().st_size / 1024 / 1024
    if st.button(f"Preparar descarga del PDF ({mb:.0f} MB)", key="ridet_prep_pdf"):
        st.session_state["_ridet_pdf"] = True
    if st.session_state.get("_ridet_pdf"):
        st.download_button("⬇️ Descargar RIDET.pdf", PDF.read_bytes(), "RIDET.pdf", "application/pdf", key="ridet_dl_pdf")


@ui.protegido
def render() -> None:
    sesion = actual()
    ui.encabezado("Regiones Integrales para el Desarrollo Dual de Tlaxcala (RIDET)",
                  "Seis regiones económicas, sus empresas y su relación con las vacantes del sistema.", "🧭")
    etiquetas = list(VISTAS.values())
    elegido = st.segmented_control("Vista", etiquetas, default=etiquetas[0], key="ridet_vista", label_visibility="collapsed") or etiquetas[0]
    clave = next(k for k, v in VISTAS.items() if v == elegido)
    if clave == "general":
        _general()
    elif clave == "regiones":
        _regiones()
    elif clave == "empresas":
        _empresas_y_vacantes(sesion)
    elif clave == "estadisticas":
        _estadisticas(sesion)
    else:
        _documento()
