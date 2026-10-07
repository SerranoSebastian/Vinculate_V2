"""Inicio ejecutivo: indicadores clave, filtros globales, gráficas con clic (drill-down) y detalle."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from ..auth.sesion import Sesion, actual
from ..components import charts, filtros, paneles, ui
from ..core.constantes import SIN_DATO
from ..core.personas import obtener_personas_maestras
from ..core.vacantes import clasificar_vigencia, tiene_vigencia, vigentes_mask
from ..repositories.errores import ErrorDatos
from ..services import datos, disponibilidad
from . import ficha


def _n_unicos(serie: pd.Series) -> int:
    s = serie.fillna("").astype(str).str.strip()
    return int(s[~s.str.lower().isin(["", "nan", "none"])].nunique())


def _kpis_personas(s: Sesion, pf: pd.DataFrame) -> None:
    unicas = int(pf["id_persona_maestro"].nunique()) if not pf.empty else 0
    vinc = len(pf)
    por_persona = pf.groupby("id_persona_maestro").size() if not pf.empty else pd.Series(dtype=int)
    recurrentes = int((por_persona > 1).sum())
    sin_anio = int(pf["año"].isna().sum()) if not pf.empty else 0
    st.markdown("#### 👥 Personas")
    c = st.columns(6)
    ui.kpi("Personas únicas", unicas, "Cuenta cada persona una sola vez", contenedor=c[0])
    ui.kpi("Vinculaciones históricas", vinc, "Cada registro histórico", contenedor=c[1])
    ui.kpi("Personas recurrentes", recurrentes, "Con 2 o más vinculaciones", contenedor=c[2])
    ui.kpi("Vinculaciones por persona", (vinc / unicas) if unicas else None, "Promedio del filtro", contenedor=c[3], decimales=2)
    ui.kpi("Registros sin año", sin_anio, "No se asignan a ningún periodo", contenedor=c[4])
    try:
        disp = disponibilidad.disponibles(s)
    except ErrorDatos:
        disp = None
    ui.kpi("Disponibles para vincular", disp, "Marca manual por persona" if disp is not None else "Se habilita con la migración V008",
           contenedor=c[5], no_disponible=disp is None)


def _kpis_vacantes(vf: pd.DataFrame) -> None:
    st.markdown("#### 💼 Vacantes y empresas")
    con_cierre = tiene_vigencia(vf)
    total = len(vf)
    c = st.columns(5)
    ui.kpi("Vacantes registradas", total, "Registros de puestos", contenedor=c[0])
    if con_cierre:
        vig = int(vigentes_mask(vf).sum()) if total else 0
        ui.kpi("Vacantes vigentes", vig, "Activas y sin cierre vencido", contenedor=c[1])
    else:
        activas = int(vf["Estado"].eq("Activa").sum()) if total else 0
        ui.kpi("Vacantes activas", activas, "La vigencia aún no se puede verificar (falta fecha de cierre)", contenedor=c[1])
    ui.kpi("Empresas con vacantes", _n_unicos(vf["Empresa"]) if total else 0, "Empresas distintas", contenedor=c[2])
    ui.kpi("Puestos distintos", _n_unicos(vf["Tipo de Vacante"]) if total else 0, "Puestos normalizados", contenedor=c[3])
    if con_cierre:
        ui.kpi("Sin fecha de cierre", int(vf["fecha_cierre"].isna().sum()) if total else 0, "Pendientes de definir", contenedor=c[4])
    else:
        ui.kpi("Sin fecha de cierre", None, "Requiere la migración V007", contenedor=c[4], no_disponible=True)


def _kpis_seguimiento(sf: pd.DataFrame) -> None:
    st.markdown("#### 🔗 Seguimiento con empresas")
    total = len(sf)
    c = st.columns(4)
    ui.kpi("Seguimientos", total, "Acciones registradas persona → empresa", contenedor=c[0])
    colocadas = int(sf.loc[sf["estatus"].eq("Colocado"), "id_persona_maestro"].nunique()) if total else 0
    ui.kpi("Personas colocadas", colocadas, "Con al menos una colocación", contenedor=c[1])
    emp = _n_unicos(sf.loc[sf["empresa"].ne("Sin asignar"), "empresa"]) if total else 0
    ui.kpi("Empresas con seguimiento", emp, contenedor=c[2])
    ui.kpi("No vinculados", int(sf["estatus"].eq("No vinculado").sum()) if total else 0, "Seguimientos sin vinculación", contenedor=c[3])


# ------------------------------------------------------------- drill-down
def _detalle_personas(titulo: str, df: pd.DataFrame, clave: str) -> None:
    st.markdown(f"**{titulo}** · {len(df)} persona(s)")
    if df.empty:
        ui.vacio("Sin personas para esta selección.")
        return
    d = df.sort_values("nombre").reset_index(drop=True)
    idx = ui.tabla(d, ["nombre", "id_persona_maestro", "municipio", "carrera", "Institución", "total_vinculaciones"],
                   {"nombre": "Nombre", "id_persona_maestro": "ID", "municipio": "Municipio", "carrera": "Carrera",
                    "total_vinculaciones": "Vinculaciones"}, altura=260, key=f"dt_{clave}", seleccionable=True)
    if idx is not None:
        fila = d.iloc[idx]
        if st.button(f"Abrir ficha de {fila['nombre']}", key=f"fchbtn_{clave}"):
            ficha.dialogo(str(fila["id_persona_maestro"]))


def _detalle_vacantes(titulo: str, df: pd.DataFrame, clave: str) -> None:
    st.markdown(f"**{titulo}** · {len(df)} vacante(s)")
    if df.empty:
        ui.vacio("Sin vacantes para esta selección.")
        return
    ui.tabla(df.sort_values("Fecha", ascending=False), ["ID Vacante", "Fecha", "Empresa", "Tipo de Vacante", "Tipo de Oportunidad", "Estado"],
             fechas=("Fecha",), altura=260, key=f"dv_{clave}")


def render() -> None:
    s = actual()
    ui.encabezado("Inicio ejecutivo", "Personas, vacantes y vinculaciones de SEDECO Tlaxcala en un solo vistazo", "🏠")

    p = datos.personas_dashboard(s) if s.puede("personas", "view") else None
    v = datos.vacantes(s) if s.puede("vacantes", "view") else None
    seg = datos.vinculaciones(s) if s.puede("vinculaciones", "view") else None
    if p is None and v is None and seg is None:
        st.info("Tu cuenta está activa, pero este panel solo muestra los módulos que tu perfil puede consultar. "
                "Usa el menú lateral para entrar a las secciones disponibles.")
        return

    hay_estimado = p is not None and "anio_fuente" in p.columns and bool((p["anio_fuente"] == "imputado").any())
    f = filtros.barra(p, v, hay_estimado)
    n_sel = st.session_state.get("_sel_n", 0)
    selecciones: dict[str, tuple[str, str]] = {}

    pf = filtros.aplicar_personas(p, f) if p is not None else None
    vf = filtros.aplicar_vacantes(v, f) if v is not None else None
    sf = None
    if seg is not None:
        sf = seg
        if f.anios and not sf.empty:
            sf = sf[sf["fecha_vinculacion"].dt.year.isin(f.anios)]

    if pf is not None:
        _kpis_personas(s, pf)
    if vf is not None:
        _kpis_vacantes(vf)
    if sf is not None:
        _kpis_seguimiento(sf)
    ui.explicacion(
        "Registros de Supabase visibles para tu perfil, después de aplicar los filtros activos.",
        "Personas únicas cuenta a cada persona maestra una vez; las vinculaciones históricas cuentan cada registro. "
        "Las vacantes son publicaciones de puestos; los seguimientos son acciones persona → empresa.",
        "Una vacante o un seguimiento no equivale a una contratación. «No disponible» significa que el dato todavía no existe "
        "en la base; nunca se sustituye por un cero.")
    st.divider()

    pestañas = []
    if pf is not None:
        pestañas.append("Personas")
    if vf is not None:
        pestañas.append("Vacantes")
    if sf is not None:
        pestañas.append("Seguimiento")
    tabs = dict(zip(pestañas, st.tabs(pestañas)))

    maestras_f = None
    if pf is not None:
        with tabs["Personas"]:
            if pf.empty:
                ui.vacio()
            else:
                maestras_f = obtener_personas_maestras(pf)
                c1, c2 = st.columns(2)
                with c1:
                    paneles.evolucion_anual(pf, f"g_evo_{n_sel}")
                    ui.explicacion("Año y fecha de cada vinculación histórica.",
                                   "Barras: vinculaciones por año; línea: personas únicas en ese año.",
                                   "Si hay años estimados se muestran con barra rayada: fueron completados en una limpieza histórica "
                                   "y no capturados originalmente. Usa el filtro para excluirlos.")
                with c2:
                    paneles.tipos_vinculacion(pf, f"g_tipo_{n_sel}")
                c3, c4 = st.columns(2)
                with c3:
                    mun = charts.conteo(maestras_f["municipio"], "Municipio", "Personas", top=15)
                    sel = charts.mostrar_seleccionable(charts.barras_h(mun, "Municipio", "Personas", "Personas únicas por municipio / estado (clic para ver el detalle)"),
                                                       f"g_mun_{n_sel}")
                    if sel:
                        selecciones["municipio"] = (sel, f"Personas de {sel}")
                with c4:
                    inst = charts.conteo(maestras_f["Institución"], "Institución", "Personas", top=12)
                    sel = charts.mostrar_seleccionable(charts.barras_h(inst, "Institución", "Personas", "Instituciones (clic para ver el detalle)"),
                                                       f"g_inst_{n_sel}")
                    if sel:
                        selecciones["Institución"] = (sel, f"Personas de {sel}")
                c5, c6 = st.columns(2)
                with c5:
                    car = charts.conteo(maestras_f["carrera"], "Carrera", "Personas", top=12)
                    sel = charts.mostrar_seleccionable(charts.barras_h(car, "Carrera", "Personas", "Carreras (clic para ver el detalle)"),
                                                       f"g_car_{n_sel}")
                    if sel:
                        selecciones["carrera"] = (sel, f"Personas de la carrera {sel}")
                with c6:
                    sx = charts.conteo(maestras_f["sexo"], "Sexo", "Personas")
                    charts.mostrar(charts.dona(sx, "Sexo", "Personas", "Personas únicas por sexo"), f"g_sexo_{n_sel}")
                if "institucion_fuente" in pf.columns and (pf["institucion_fuente"] == "balanceado").any():
                    n_b = int((pf["institucion_fuente"] == "balanceado").sum())
                    ui.nota(f"{n_b} registro(s) tienen la institución asignada por una corrección de balanceo (no capturada por la persona).")
                ui.explicacion("Una fila por persona maestra, con su dato más reciente y completo.",
                               "Distribuye personas únicas por municipio, institución, carrera y sexo.",
                               "«Información no disponible» agrupa a quienes no tienen ese dato. Haz clic en una barra para ver quiénes son.")

    if vf is not None:
        with tabs["Vacantes"]:
            if vf.empty:
                ui.vacio()
            else:
                c1, c2 = st.columns(2)
                with c1:
                    mes = vf[vf["Fecha"].notna()].groupby("Mes").size().reset_index(name="Vacantes").sort_values("Mes")
                    if mes.empty:
                        ui.vacio("Las vacantes del filtro no tienen fecha.")
                    else:
                        charts.mostrar(charts.area(mes, "Mes", "Vacantes", "Vacantes registradas por mes"), f"g_vmes_{n_sel}")
                with c2:
                    vig = clasificar_vigencia(vf).value_counts().rename_axis("Situación").reset_index(name="Vacantes")
                    charts.mostrar(charts.dona(vig, "Situación", "Vacantes", "Situación de las vacantes"), f"g_vvig_{n_sel}")
                emp = charts.conteo(vf["Empresa"], "Empresa", "Vacantes", top=12)
                sel = charts.mostrar_seleccionable(charts.barras_h(emp, "Empresa", "Vacantes", "Empresas con más vacantes (clic para ver el detalle)"),
                                                   f"g_vemp_{n_sel}")
                if sel:
                    selecciones["empresa"] = (sel, f"Vacantes de {sel}")
                if not tiene_vigencia(vf):
                    ui.nota("La vigencia real no se puede calcular porque la base aún no tiene fecha de cierre (migración V007). "
                            "«Activa» no garantiza que la vacante siga abierta.")
                else:
                    ui.nota("Vigente = estado Activa y sin fecha de cierre vencida. «Activa con cierre vencido» necesita revisión.")

    if sf is not None:
        with tabs["Seguimiento"]:
            if sf.empty:
                ui.vacio("Todavía no hay seguimientos registrados para este filtro.")
            else:
                c1, c2 = st.columns(2)
                with c1:
                    est = charts.conteo(sf["estatus"], "Estatus", "Seguimientos")
                    charts.mostrar(charts.dona(est, "Estatus", "Seguimientos", "Seguimientos por estatus"), f"g_sest_{n_sel}")
                with c2:
                    emp = sf[sf["empresa"].ne("Sin asignar")]
                    if emp.empty:
                        ui.vacio("Los seguimientos no tienen empresa asignada.")
                    else:
                        d = charts.conteo(emp["empresa"], "Empresa", "Seguimientos", top=12)
                        charts.mostrar(charts.barras_h(d, "Empresa", "Seguimientos", "Seguimientos por empresa"), f"g_semp_{n_sel}")

    if selecciones:
        st.divider()
        h1, h2 = st.columns([4, 1])
        h1.markdown("### 🔎 Detalle de la selección")
        if h2.button("Quitar selección", key="sel_limpiar", width="stretch"):
            st.session_state["_sel_n"] = n_sel + 1
            st.rerun()
        for campo, (valor, titulo) in selecciones.items():
            if campo == "empresa" and vf is not None:
                _detalle_vacantes(titulo, vf[vf["Empresa"].eq(valor)], f"emp_{n_sel}")
            elif maestras_f is not None:
                col = maestras_f[campo].fillna("").astype(str).str.strip()
                vacio = col.str.lower().isin(["", "nan", "none", "nat"])
                base = maestras_f[vacio] if valor == SIN_DATO else maestras_f[col.eq(valor)]
                _detalle_personas(titulo, base, f"{campo}_{n_sel}")
