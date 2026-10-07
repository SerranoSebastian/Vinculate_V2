"""Vinculaciones: seguimiento persona → empresa (alta, edición, estadísticas, historial, exportación)."""
from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from .. import navegacion
from ..auth.sesion import Sesion, actual
from ..components import charts, ui
from ..core.catalogos_vacantes import AREAS_OPORTUNIDAD, EMPRESAS_CATALOGO, EMPRESAS_SECTOR, PUESTOS_CATALOGO
from ..core.constantes import ESTATUS_NUEVO, ESTATUS_VINCULACION, SIN_DATO
from ..core.texto import normalizar_texto, texto_vacio
from ..core.vacantes import vigentes_mask
from ..services import datos, guardado
from . import ficha

SECCIONES = {
    "nuevo": "➕ Nuevo seguimiento", "editar": "✏️ Editar / eliminar", "estadisticas": "📊 Estadísticas",
    "historial": "👤 Historial de una persona", "exportar": "⬇️ Exportar",
}
MAX_FILAS = 200


def _opciones_con_legacy(catalogo, valor_actual, especiales=()):
    opciones = list(dict.fromkeys([*especiales, *catalogo]))
    v = str(valor_actual or "").strip()
    if v and v not in opciones and v not in {"Sin asignar", "nan", "None"}:
        opciones.append(v)
    return opciones


def _indice(opciones, valor, default=0):
    try:
        return opciones.index(valor)
    except ValueError:
        return default


def _etiqueta(m: pd.Series) -> str:
    return f"{m['nombre']} — {m['id_persona_maestro']} — {int(m['total_vinculaciones'])} vinculación(es) histórica(s)"


def _kpis(estado: pd.DataFrame, seg: pd.DataFrame) -> None:
    c = st.columns(7)
    ui.kpi("Personas únicas", len(estado), contenedor=c[0])
    ui.kpi("Vinculaciones históricas", int(estado["total_vinculaciones"].sum()) if not estado.empty else 0, contenedor=c[1])
    ui.kpi("Vinculados", int(estado["estatus_general"].eq("Vinculado").sum()) if not estado.empty else 0, contenedor=c[2])
    ui.kpi("Colocados", int(estado["estatus_general"].eq("Colocado").sum()) if not estado.empty else 0, contenedor=c[3])
    ui.kpi("No vinculados", int(estado["estatus_general"].eq("No vinculado").sum()) if not estado.empty else 0, contenedor=c[4])
    ui.kpi("Seguimientos", len(seg), contenedor=c[5])
    ui.kpi("Empresas", int(seg.loc[seg["empresa"].ne("Sin asignar"), "empresa"].nunique()) if not seg.empty else 0, contenedor=c[6])
    ui.explicacion("Personas, vinculaciones históricas y seguimientos con empresas de la base central.",
                   "El estatus de cada persona sale de su seguimiento más reciente (o de su colocación más reciente si tiene alguna).",
                   "Las vinculaciones históricas son registros de persona; los seguimientos y empresas miden actividad operativa, "
                   "no contrataciones por sí solos. Una persona sin seguimientos figura «Vinculado» porque su registro histórico ya lo es.")


# ------------------------------------------------------------------ nuevo
def _seccion_nuevo(s: Sesion, preseleccion: str | None) -> None:
    personas_df = datos.personas(s) if s.puede("personas", "view") else pd.DataFrame()
    if personas_df.empty:
        st.info("Para registrar un seguimiento tu perfil necesita poder consultar personas, y debe haber personas registradas.")
        return
    maestras = datos.maestras(s).sort_values(["nombre", "id_persona_maestro"]).reset_index(drop=True)
    ids = list(maestras["id_persona_maestro"])
    i = st.selectbox("Persona", list(maestras.index), index=ids.index(preseleccion) if preseleccion in ids else 0,
                     format_func=lambda k: _etiqueta(maestras.loc[k]), key="seg_persona_nueva")
    persona = maestras.loc[i]
    mid = persona["id_persona_maestro"]
    vacantes = datos.vacantes(s) if s.puede("vacantes", "view") else pd.DataFrame()
    vigentes = vacantes[vigentes_mask(vacantes)].reset_index(drop=True) if not vacantes.empty else vacantes
    modo = st.radio("Empresa y puesto", ["Elegir de los catálogos", "Elegir una vacante vigente"], horizontal=True, key="seg_modo_nuevo")
    hist = personas_df[personas_df["id_persona_maestro"].eq(mid)]
    ui.bloque_deshacer(s, "vinculaciones")
    with st.form("form_seg_nuevo"):
        origen = st.selectbox("Vinculación histórica de origen (opcional)", [""] + hist["id_persona"].tolist(),
                              format_func=lambda x: "Sin asociación específica" if x == "" else f"{x} — {hist.loc[hist['id_persona'].eq(x), 'vinculacion'].iloc[0]}")
        if modo.endswith("vigente") and not vigentes.empty:
            vi = st.selectbox("Vacante vigente", list(vigentes.index),
                              format_func=lambda k: f"{vigentes.loc[k, 'Empresa']} — {vigentes.loc[k, 'Tipo de Vacante']}")
            fv = vigentes.loc[vi]
            empresa, puesto = str(fv["Empresa"]), str(fv["Tipo de Vacante"])
            sector = str(fv.get("Sector Empresa") or "") or EMPRESAS_SECTOR.get(empresa, "")
            area = str(fv.get("Área de Oportunidad") or "") or "Otro / Sin dato"
            st.caption(f"🏢 {empresa} · {sector or SIN_DATO} · {puesto} · {area}")
        else:
            if modo.endswith("vigente"):
                st.info("No hay vacantes vigentes (o tu perfil no puede consultarlas); usa los catálogos.")
            c1, c2 = st.columns(2)
            empresa = c1.selectbox("Empresa", EMPRESAS_CATALOGO)
            puesto = c1.selectbox("Puesto", PUESTOS_CATALOGO)
            area = c2.selectbox("Área de oportunidad", AREAS_OPORTUNIDAD)
            sector = EMPRESAS_SECTOR.get(empresa, "")
            c2.caption("El sector se asigna según la empresa elegida.")
        c1, c2 = st.columns(2)
        estatus = c1.selectbox("Estatus", ESTATUS_NUEVO)
        responsable = c1.text_input("Responsable", value=s.nombre)
        vinc = c2.date_input("Fecha de vinculación", value=date.today(), format="DD/MM/YYYY",
                             help="Solo se guarda cuando el estatus es «Vinculado».")
        obs = c2.text_area("Observaciones")
        enviar = st.form_submit_button("💾 Guardar seguimiento", width="stretch")
    if not enviar:
        return
    fila = {"id_persona_maestro": mid, "id_registro_origen": origen, "nombre_persona": persona["nombre"], "empresa": empresa,
            "sector_empresa": sector, "tipo_vacante": puesto, "area_oportunidad": area, "estatus": estatus,
            "fecha_vinculacion": vinc if estatus == "Vinculado" else None, "fecha_colocacion": None,
            "observaciones": obs, "responsable": responsable}
    res = guardado.importar_vinculaciones(s, pd.DataFrame([fila]), origen="Captura manual", archivo="Captura manual")
    if res.ok and res.guardados:
        ui.flash(res)
        st.rerun()
    ui.mostrar_resultado(res)


# ----------------------------------------------------------------- editar
def _seccion_editar(s: Sesion) -> None:
    seg = datos.vinculaciones(s)
    if seg.empty:
        ui.vacio("Todavía no hay seguimientos.")
        return
    q = st.text_input("Buscar el seguimiento (persona, empresa o ID)", key="sed_q")
    base = seg
    if q.strip():
        pajar = seg[["id_vinculacion", "nombre_persona", "empresa", "id_persona_maestro"]].astype(str).apply(lambda c: c.map(normalizar_texto)).agg(" ".join, axis=1)
        mask = pd.Series(True, index=seg.index)
        for t in normalizar_texto(q).split():
            mask &= pajar.str.contains(t, regex=False)
        base = seg[mask]
    base = base.sort_values("fecha_actualizacion", ascending=False).reset_index(drop=True).head(MAX_FILAS)
    idx = ui.tabla(base, ["id_vinculacion", "nombre_persona", "empresa", "estatus", "fecha_vinculacion"],
                   {"id_vinculacion": "ID", "nombre_persona": "Persona", "empresa": "Empresa", "estatus": "Estatus",
                    "fecha_vinculacion": "Vinculación"}, fechas=("fecha_vinculacion",), altura=240, key="sed_tabla", seleccionable=True)
    if idx is None:
        ui.nota("Elige un seguimiento de la tabla.")
        ui.bloque_papelera(s, "vinculaciones")
        return
    f = base.iloc[idx].to_dict()
    sid = str(f["id_vinculacion"])
    st.markdown(f"#### Seguimiento {sid}")
    if s.puede("vinculaciones", "edit"):
        empresas_ops = _opciones_con_legacy(EMPRESAS_CATALOGO, f["empresa"])
        puestos_ops = _opciones_con_legacy(PUESTOS_CATALOGO, f["tipo_vacante"])
        areas_ops = _opciones_con_legacy(AREAS_OPORTUNIDAD, f.get("area_oportunidad", ""), especiales=("Otro / Sin dato",))
        with st.form(f"form_seg_edit_{sid}"):
            c1, c2 = st.columns(2)
            with c1:
                st.text_input("Persona maestra (no editable)", value=f"{f['nombre_persona']} — {f['id_persona_maestro']}", disabled=True)
                empresa = st.selectbox("Empresa", empresas_ops, index=_indice(empresas_ops, str(f["empresa"])))
                puesto = st.selectbox("Puesto", puestos_ops, index=_indice(puestos_ops, str(f["tipo_vacante"])))
                area = st.selectbox("Área de oportunidad", areas_ops, index=_indice(areas_ops, str(f.get("area_oportunidad") or "Otro / Sin dato")))
            with c2:
                estatus = st.selectbox("Estatus", ESTATUS_VINCULACION, index=_indice(ESTATUS_VINCULACION, str(f["estatus"])))
                fv = pd.to_datetime(f["fecha_vinculacion"], errors="coerce")
                vinc = st.date_input("Fecha de vinculación", value=None if pd.isna(fv) else fv.date(), format="DD/MM/YYYY")
                fc = pd.to_datetime(f.get("fecha_colocacion"), errors="coerce")
                coloc = st.date_input("Fecha de colocación (solo si el estatus es Colocado)", value=None if pd.isna(fc) else fc.date(), format="DD/MM/YYYY")
                obs = st.text_area("Observaciones", value="" if texto_vacio(f["observaciones"]) else str(f["observaciones"]))
                resp = st.text_input("Responsable", value=str(f["responsable"]))
            guardar = st.form_submit_button("💾 Guardar cambios", width="stretch")
        if guardar:
            nuevos = {"empresa": empresa, "sector_empresa": EMPRESAS_SECTOR.get(empresa, f.get("sector_empresa", "")),
                      "tipo_vacante": puesto, "area_oportunidad": area, "estatus": estatus, "fecha_vinculacion": vinc,
                      "fecha_colocacion": coloc if estatus == "Colocado" else None, "observaciones": obs, "responsable": resp}
            r = guardado.editar(s, "vinculaciones", sid, nuevos)
            if r.ok and r.guardados:
                ui.flash(r)
                st.rerun()
            ui.mostrar_resultado(r)
    else:
        ui.nota("Tu perfil puede ver este módulo pero no editar seguimientos.")
    if s.puede("vinculaciones", "delete"):
        st.divider()
        if st.button("🗑️ Eliminar este seguimiento", key=f"sdel_{sid}"):
            ui.pedir_confirmacion(f"sdel_{sid}", f"Eliminar el seguimiento {sid}", guardado.impacto_eliminacion(s, "vinculaciones", sid),
                                  "Eliminar seguimiento")
        if ui.confirmado(f"sdel_{sid}"):
            ui.flash(guardado.eliminar(s, "vinculaciones", sid))
            st.rerun()
    ui.bloque_papelera(s, "vinculaciones")


# ----------------------------------------------------------- estadísticas
def _seccion_estadisticas(s: Sesion, estado: pd.DataFrame, seg: pd.DataFrame) -> None:
    if estado.empty:
        ui.vacio("Sin información para mostrar.")
        return
    personas_df = datos.personas(s) if s.puede("personas", "view") else pd.DataFrame(columns=["id_persona_maestro"])
    c1, c2 = st.columns(2)
    with c1:
        charts.mostrar(charts.dona(charts.conteo(estado["estatus_general"], "Estatus", "Personas"), "Estatus", "Personas",
                                   "Estatus actual por persona"), "vs_estatus")
    with c2:
        if not personas_df.empty:
            hist = personas_df.groupby("id_persona_maestro").size().value_counts().sort_index().reset_index()
            hist.columns = ["Vinculaciones", "Personas"]
            hist["Vinculaciones"] = hist["Vinculaciones"].astype(str)
            charts.mostrar(charts.barras_v(hist, "Vinculaciones", "Personas", "Vinculaciones históricas por persona"), "vs_hist")
    if not seg.empty:
        con = seg.assign(Año=seg["fecha_vinculacion"].dt.year.astype("Int64")).dropna(subset=["Año"])
        if not con.empty:
            anual = con.groupby(["Año", "estatus"]).size().reset_index(name="Seguimientos")
            anual["Año"] = anual["Año"].astype(str)
            charts.mostrar(charts.barras_v(anual, "Año", "Seguimientos", "Seguimientos por año y estatus", color="estatus"), "vs_anual")
        c3, c4 = st.columns(2)
        with c3:
            emp = seg[seg["empresa"].ne("Sin asignar")]
            if not emp.empty:
                charts.mostrar(charts.barras_h(charts.conteo(emp["empresa"], "Empresa", "Seguimientos", top=15), "Empresa", "Seguimientos",
                                               "Seguimientos por empresa"), "vs_emp")
        with c4:
            pue = seg[seg["tipo_vacante"].ne("Sin asignar")]
            if not pue.empty:
                charts.mostrar(charts.barras_h(charts.conteo(pue["tipo_vacante"], "Puesto", "Seguimientos", top=15), "Puesto", "Seguimientos",
                                               "Seguimientos por puesto"), "vs_pue")
    st.markdown("### Colocaciones")
    colocados = estado[estado["estatus_general"].eq("Colocado")]
    base_vinc = max(int(estado["estatus_general"].isin(["Vinculado", "Colocado"]).sum()), 1)
    seg_col = seg[seg["estatus"].eq("Colocado")] if not seg.empty else seg
    k = st.columns(4)
    ui.kpi("Personas colocadas", len(colocados), contenedor=k[0])
    ui.kpi("Registros de colocación", len(seg_col), contenedor=k[1])
    ui.kpi("Empresas con colocación", int(seg_col.loc[seg_col["empresa"].ne("Sin asignar"), "empresa"].nunique()) if not seg_col.empty else 0, contenedor=k[2])
    ui.kpi("Tasa sobre personas vinculadas", ui.fmt_pct(len(colocados), base_vinc), "Colocadas ÷ personas vinculadas", contenedor=k[3])
    if not colocados.empty:
        a, b = st.columns(2)
        with a:
            charts.mostrar(charts.dona(charts.conteo(colocados["sexo"], "Sexo", "Personas"), "Sexo", "Personas", "Colocadas por sexo"), "vs_csexo")
        with b:
            charts.mostrar(charts.barras_h(charts.conteo(colocados["municipio"], "Municipio", "Personas", top=15), "Municipio", "Personas",
                                           "Colocadas por municipio"), "vs_cmun")
    ui.tabla(estado, ["id_persona_maestro", "nombre", "total_vinculaciones", "estatus_general", "seguimientos_empresa", "empresas_contactadas", "empresa_actual"],
             {"id_persona_maestro": "ID", "nombre": "Nombre", "total_vinculaciones": "Vinculaciones", "estatus_general": "Estatus",
              "seguimientos_empresa": "Seguimientos", "empresas_contactadas": "Empresas", "empresa_actual": "Empresa actual"}, altura=360)


# --------------------------------------------------------------- historial
def _seccion_historial(s: Sesion, preseleccion: str | None) -> None:
    if not s.puede("personas", "view"):
        st.info("Para ver el historial de una persona tu perfil necesita poder consultar personas.")
        return
    m = datos.maestras(s).sort_values(["nombre", "id_persona_maestro"]).reset_index(drop=True)
    if m.empty:
        ui.vacio("Todavía no hay personas.")
        return
    ids = list(m["id_persona_maestro"])
    i = st.selectbox("Persona", list(m.index), index=ids.index(preseleccion) if preseleccion in ids else 0,
                     format_func=lambda k: _etiqueta(m.loc[k]), key="seg_hist_persona")
    ficha.contenido(s, ids[i])


# ----------------------------------------------------------------- página
@ui.protegido
def render() -> None:
    s = actual()
    ui.encabezado("Vinculaciones", "Seguimiento de cada persona con las empresas y vacantes", "🔗")
    ui.mostrar_flash()
    params = navegacion.tomar_parametros("vinculaciones")
    seg = datos.vinculaciones(s) if s.puede("vinculaciones", "view") else pd.DataFrame()
    estado = datos.estado_personas(s) if s.puede("personas", "view") else pd.DataFrame()
    if s.puede("vinculaciones", "view") and s.puede("personas", "view"):
        _kpis(estado, seg)

    disponibles = {}
    if s.puede("vinculaciones", "create"):
        disponibles["nuevo"] = SECCIONES["nuevo"]
    if s.puede("vinculaciones", "edit") or s.puede("vinculaciones", "delete"):
        disponibles["editar"] = SECCIONES["editar"]
    if s.puede("vinculaciones", "view"):
        disponibles["estadisticas"] = SECCIONES["estadisticas"]
        disponibles["historial"] = SECCIONES["historial"]
    if s.puede("vinculaciones", "export"):
        disponibles["exportar"] = SECCIONES["exportar"]
    if not disponibles:
        st.warning("Tu perfil no tiene acciones disponibles en este módulo.")
        return
    if params.get("apartado") in disponibles:
        st.session_state["vinculaciones_apartado"] = disponibles[params["apartado"]]
    etiquetas = list(disponibles.values())
    if st.session_state.get("vinculaciones_apartado") not in etiquetas:
        st.session_state["vinculaciones_apartado"] = etiquetas[0]
    elegido = st.segmented_control("Apartado", etiquetas, key="vinculaciones_apartado", label_visibility="collapsed") or etiquetas[0]
    clave = next(k for k, v in disponibles.items() if v == elegido)
    persona = params.get("persona")
    if clave == "nuevo":
        _seccion_nuevo(s, persona)
    elif clave == "editar":
        _seccion_editar(s)
    elif clave == "estadisticas":
        _seccion_estadisticas(s, estado, seg)
    elif clave == "historial":
        _seccion_historial(s, persona)
    else:
        ui.tabla(seg, ["id_vinculacion", "nombre_persona", "empresa", "tipo_vacante", "estatus", "fecha_vinculacion", "fecha_colocacion", "responsable"],
                 fechas=("fecha_vinculacion", "fecha_colocacion"), altura=360)
        ui.boton_exportar(s, "vinculaciones", seg, "seguimientos_vinculacion", "seg_exp")
