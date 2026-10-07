"""Vacantes y empresas: análisis, empresas (con ubicación), alta, carga masiva, edición y revisión de vigencia."""
from __future__ import annotations

import io
from datetime import date

import pandas as pd
import streamlit as st

from .. import navegacion
from ..auth.sesion import Sesion, actual
from ..components import charts, ui
from ..core.catalogos_vacantes import AREAS_OPORTUNIDAD, EMPRESAS_SECTOR, PUESTOS_CATALOGO
from ..core.constantes import ESTADOS_VACANTE, SIN_DATO, TIPOS_OPORTUNIDAD, VACANTES_COLS
from ..core.texto import normalizar_texto, texto_vacio
from ..core.ubicacion import MUNICIPIOS_TLAXCALA
from ..core.vacantes import (
    categoria_puesto_vacante, clasificar_vigencia, normalizar_puesto_vacante, tiene_vigencia, vigentes_mask,
)
from ..services import datos, empresas, guardado

SECCIONES = {
    "analisis": "📊 Análisis", "empresas": "🏢 Empresas", "alta": "➕ Nueva vacante", "carga": "📁 Carga Excel/CSV",
    "editar": "✏️ Editar / eliminar", "vigencia": "🕒 Revisión de vigencia",
}
MAX_FILAS = 200


def _lectura_archivo(archivo) -> pd.DataFrame:
    nombre = archivo.name.lower()
    if nombre.endswith(".csv"):
        try:
            return pd.read_csv(archivo, encoding="utf-8-sig", dtype=str)
        except UnicodeDecodeError:
            archivo.seek(0)
            return pd.read_csv(archivo, encoding="latin1", dtype=str)
    if nombre.endswith((".xlsx", ".xls")):
        return pd.read_excel(archivo, dtype=str)
    raise ValueError("Formato no soportado. Usa CSV o Excel.")


def _plantilla_xlsx(columnas: list[str]) -> bytes:
    buf = io.BytesIO()
    pd.DataFrame(columns=columnas).to_excel(buf, index=False)
    return buf.getvalue()


def _catalogo_puestos(df: pd.DataFrame) -> list[str]:
    extra = {x for x in df["Tipo de Vacante"].dropna().astype(str).unique() if x.strip()} if not df.empty else set()
    return sorted(set(PUESTOS_CATALOGO) | extra)


# ------------------------------------------------------------------- análisis
def _filtros(df: pd.DataFrame) -> pd.DataFrame:
    out = df
    with st.expander("🎛️ Filtros", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        anios = sorted(df["Año"].dropna().astype(int).unique(), reverse=True)
        sel = c1.multiselect("Año", anios, key="fv_anio", placeholder="Todos")
        if sel:
            out = out[out["Año"].isin(sel)]
        situacion = clasificar_vigencia(out)
        sel = c2.multiselect("Situación", sorted(situacion.unique()), key="fv_sit", placeholder="Todas")
        if sel:
            out = out[clasificar_vigencia(out).isin(sel)]
        sel = c3.multiselect("Tipo de oportunidad", TIPOS_OPORTUNIDAD, key="fv_opo", placeholder="Todos")
        if sel:
            out = out[out["Tipo de Oportunidad"].isin(sel)]
        sel = c4.multiselect("Empresa", sorted(df["Empresa"].dropna().unique()), key="fv_emp", placeholder="Todas")
        if sel:
            out = out[out["Empresa"].isin(sel)]
        c5, c6 = st.columns(2)
        sel = c5.multiselect("Puesto", sorted(df["Tipo de Vacante"].dropna().unique()), key="fv_pue", placeholder="Todos")
        if sel:
            out = out[out["Tipo de Vacante"].isin(sel)]
        fechas = df["Fecha"].dropna()
        if not fechas.empty:
            rango = c6.date_input("Rango de fechas de publicación", value=(), min_value=fechas.min().date(),
                                  max_value=fechas.max().date(), key="fv_rango", format="DD/MM/YYYY")
            if isinstance(rango, (tuple, list)) and len(rango) == 2:
                out = out[(out["Fecha"] >= pd.Timestamp(rango[0])) & (out["Fecha"] <= pd.Timestamp(rango[1]))]
    return out


def _seccion_analisis(s: Sesion) -> None:
    df = datos.vacantes(s)
    if df.empty:
        ui.vacio("No hay vacantes registradas todavía.")
        return
    vf = _filtros(df)
    if vf.empty:
        ui.vacio()
        return
    total = len(vf)
    con_cierre = tiene_vigencia(vf)
    c = st.columns(5)
    ui.kpi("Vacantes", total, "Puestos registrados", contenedor=c[0])
    if con_cierre:
        ui.kpi("Vigentes", int(vigentes_mask(vf).sum()), "Activas y sin cierre vencido", contenedor=c[1])
    else:
        ui.kpi("Activas", int(vf["Estado"].eq("Activa").sum()), "Vigencia no verificable (falta fecha de cierre)", contenedor=c[1])
    ui.kpi("Empresas", int(vf["Empresa"].nunique()), contenedor=c[2])
    ui.kpi("Puestos distintos", int(vf["Tipo de Vacante"].nunique()), contenedor=c[3])
    ui.kpi("Meses con publicación", int(vf["Mes"].nunique()), contenedor=c[4])
    ui.explicacion("Base de vacantes después de los filtros.",
                   "Cada registro es un puesto publicado. Vigente = Activa y sin fecha de cierre vencida.",
                   "Una vacante no equivale a una contratación. Si no hay fecha de cierre, «Activa» no garantiza que siga abierta.")
    vista = st.segmented_control("Vista", ["Resumen", "Tiempo", "Concentración", "Buscador"], default="Resumen",
                                 key="vac_vista", label_visibility="collapsed") or "Resumen"
    if vista == "Resumen":
        c1, c2 = st.columns(2)
        with c1:
            charts.mostrar(charts.barras_h(charts.conteo(vf["Empresa"], "Empresa", "Vacantes", top=12), "Empresa", "Vacantes",
                                           "Empresas con más vacantes"), "va_emp")
        with c2:
            charts.mostrar(charts.barras_h(charts.conteo(vf["Tipo de Vacante"], "Puesto", "Vacantes", top=12), "Puesto", "Vacantes",
                                           "Puestos más frecuentes"), "va_pue")
        c3, c4 = st.columns(2)
        with c3:
            sit = clasificar_vigencia(vf).value_counts().rename_axis("Situación").reset_index(name="Vacantes")
            charts.mostrar(charts.dona(sit, "Situación", "Vacantes", "Situación de las vacantes"), "va_sit")
        with c4:
            cat = charts.conteo(vf["Categoría de Puesto"], "Categoría", "Vacantes", top=10)
            charts.mostrar(charts.barras_h(cat, "Categoría", "Vacantes", "Categorías de puesto"), "va_cat")
    elif vista == "Tiempo":
        con_fecha = vf[vf["Fecha"].notna()]
        if con_fecha.empty:
            ui.vacio("Las vacantes del filtro no tienen fecha.")
        else:
            dia = con_fecha.groupby("Fecha").size().reset_index(name="Vacantes").sort_values("Fecha")
            charts.mostrar(charts.area(dia, "Fecha", "Vacantes", "Publicaciones por fecha"), "va_dia")
            mes = con_fecha.groupby("Mes").size().reset_index(name="Vacantes").sort_values("Mes")
            charts.mostrar(charts.barras_v(mes, "Mes", "Vacantes", "Vacantes registradas por mes"), "va_mes")
            top = con_fecha["Empresa"].value_counts().head(12).index
            tabla = pd.pivot_table(con_fecha[con_fecha["Empresa"].isin(top)], values="Tipo de Vacante", index="Empresa",
                                   columns="Mes", aggfunc="count", fill_value=0)
            if not tabla.empty:
                charts.mostrar(charts.calor(tabla, "Publicaciones por empresa y mes (12 empresas con más vacantes)"), "va_calor")
            sin_fecha = int(vf["Fecha"].isna().sum())
            if sin_fecha:
                ui.nota(f"{sin_fecha} vacante(s) no tienen fecha y no aparecen en estas gráficas.")
    elif vista == "Concentración":
        pct = vf["Empresa"].value_counts(normalize=True).head(10).mul(100).reset_index()
        pct.columns = ["Empresa", "Porcentaje"]
        pct["Porcentaje"] = pct["Porcentaje"].round(1)
        charts.mostrar(charts.barras_v(pct, "Empresa", "Porcentaje", "Concentración de vacantes por empresa (%)"), "va_conc")
        emp = vf["Empresa"].value_counts()
        with st.container(border=True):
            st.markdown("**Informe automático**")
            f_top = vf["Fecha"].value_counts()
            st.markdown(
                f"El filtro contiene **{total}** vacantes de **{emp.size}** empresas. La empresa con más presencia es "
                f"**{emp.index[0]}** ({int(emp.iloc[0])}). El puesto más frecuente es **{vf['Tipo de Vacante'].value_counts().index[0]}**."
                + (f" La fecha con más publicaciones fue **{f_top.index[0].strftime('%d/%m/%Y')}** ({int(f_top.iloc[0])})." if not f_top.empty else ""))
            ui.nota("Es un resumen descriptivo del filtro; no prueba causalidad ni representa todo el mercado laboral.")
    else:
        q = st.text_input("Buscar por empresa, puesto, requisitos, beneficios o descripción", key="va_q")
        vista_df = vf
        if q.strip():
            cols = ["Empresa", "Tipo de Vacante", "Puesto Original", "Requisitos", "Beneficios", "Descripción", "ID Vacante"]
            pajar = vf[cols].astype(str).apply(lambda c: c.map(normalizar_texto)).agg(" ".join, axis=1)
            mask = pd.Series(True, index=vf.index)
            for t in normalizar_texto(q).split():
                mask &= pajar.str.contains(t, regex=False)
            vista_df = vf[mask]
        st.caption(f"{len(vista_df)} vacante(s)")
        cols_t = ["ID Vacante", "Fecha", "Empresa", "Tipo de Vacante", "Tipo de Oportunidad", "Área de Oportunidad", "Estado"]
        if con_cierre:
            cols_t.append("fecha_cierre")
        ui.tabla(vista_df.sort_values("Fecha", ascending=False), cols_t, {"fecha_cierre": "Cierre"}, fechas=("Fecha", "fecha_cierre"), altura=420)
        ui.boton_exportar(s, "vacantes", vista_df, "vacantes", "vac_exp")


# ------------------------------------------------------------------- empresas
def _seccion_empresas(s: Sesion) -> None:
    v = datos.vacantes(s)
    try:
        cat = empresas.catalogo(s)
    except Exception as exc:  # noqa: BLE001
        ui.mostrar_error(exc)
        cat = pd.DataFrame(columns=["nombre", "sector", "activo"])
    res = empresas.resumen(v, cat)
    con_ubic = empresas.tiene_ubicacion(cat)
    total = len(res)
    ubicadas = int((res["Municipio"].astype(str).str.strip() != "").sum()) if total else 0
    c = st.columns(4)
    ui.kpi("Empresas con vacantes", total, contenedor=c[0])
    ui.kpi("Con municipio capturado", ubicadas if con_ubic else None, contenedor=c[1], no_disponible=not con_ubic,
           ayuda="" if con_ubic else "Requiere la migración V004")
    ui.kpi("Sin municipio", (total - ubicadas) if con_ubic else None, "Pendientes de ubicar", contenedor=c[2], no_disponible=not con_ubic)
    ui.kpi("Sectores", int(res["Sector"].replace("", pd.NA).nunique()) if total else 0, contenedor=c[3])
    if not con_ubic:
        st.info("La ubicación de empresas todavía no está habilitada en la base (migración V004). Mientras tanto, el mapa por "
                "municipio usa solo la información de personas, y nada se inventa para las empresas.")
    ui.tabla(res, ["Empresa", "Sector", "Vacantes", "Vigentes", "Puestos distintos", "Municipio", "Ubicación"],
             {"Ubicación": "Fuente de ubicación"}, altura=360)
    ui.boton_exportar(s, "vacantes", res, "empresas", "emp_exp")
    if con_ubic and s.puede("vacantes", "edit") and not res.empty:
        st.markdown("#### Capturar la ubicación de una empresa")
        ui.nota("Registra solo el municipio (y opcionalmente dirección y código postal). No se geocodifica nada automáticamente.")
        pendientes = res[res["Municipio"].astype(str).str.strip() == ""]["Empresa"].tolist()
        todas = res["Empresa"].tolist()
        orden = pendientes + [e for e in todas if e not in pendientes]
        with st.form("form_ubicacion_empresa"):
            c1, c2 = st.columns(2)
            empresa = c1.selectbox("Empresa", orden, format_func=lambda e: e + ("  · sin municipio" if e in pendientes else ""))
            municipio = c2.selectbox("Municipio", [empresas.FUERA_DE_TLAXCALA] + MUNICIPIOS_TLAXCALA, index=1)
            c3, c4 = st.columns([3, 1])
            direccion = c3.text_input("Dirección (opcional)")
            cp = c4.text_input("C.P. (opcional)", max_chars=5)
            enviar = st.form_submit_button("💾 Guardar ubicación", width="stretch")
        if enviar:
            try:
                sector = res.loc[res["Empresa"].eq(empresa), "Sector"].iloc[0] or EMPRESAS_SECTOR.get(empresa)
                empresas.guardar_ubicacion(s, empresa, municipio, direccion, cp, sector)
            except ValueError as exc:
                st.error(str(exc))
            except Exception as exc:  # noqa: BLE001
                ui.mostrar_error(exc)
            else:
                st.success(f"Ubicación de {empresa} guardada.")
                st.rerun()


# ------------------------------------------------------------------------ alta
def _seccion_alta(s: Sesion) -> None:
    df = datos.vacantes(s) if s.puede("vacantes", "view") else pd.DataFrame(columns=["Tipo de Vacante"])
    catalogo = _catalogo_puestos(df)
    extras = guardado.columnas_opcionales(s, "vacantes")
    st.markdown("Cada fila representa **un solo puesto**. El nombre del puesto se homologa para evitar variantes; "
                "*Puesto original* conserva el texto capturado.")
    ui.bloque_deshacer(s, "vacantes")
    with st.form("form_alta_vacante"):
        c1, c2 = st.columns(2)
        with c1:
            actividad = st.text_input("Actividad", value="Publicación de vacantes")
            fecha = st.date_input("Fecha de publicación *", value=None, format="DD/MM/YYYY")
            empresa = st.selectbox("Empresa *", ["Seleccionar..."] + sorted(EMPRESAS_SECTOR.keys()))
            opcion_puesto = st.selectbox("Puesto normalizado *", ["Seleccionar..."] + catalogo + ["Otro / nuevo puesto"])
            puesto_nuevo = st.text_input("Si es otro puesto, escríbelo aquí")
            tipo_op = st.selectbox("Tipo de oportunidad *", TIPOS_OPORTUNIDAD)
            area = st.selectbox("Área de oportunidad", AREAS_OPORTUNIDAD)
        with c2:
            descripcion = st.text_area("Descripción / funciones", help="Actividades y responsabilidades del puesto.")
            requisitos = st.text_area("Requisitos", help="Escolaridad, experiencia, conocimientos, licencias, idiomas…")
            beneficios = st.text_area("Beneficios", help="Sueldo, prestaciones, transporte, comedor, capacitación…")
            link = st.text_input("Link de la publicación")
            estado = st.selectbox("Estado", ESTADOS_VACANTE)
            cierre = None
            if "fecha_cierre" in extras:
                cierre = st.date_input("Fecha de cierre (opcional)", value=None, format="DD/MM/YYYY",
                                       help="Después de esta fecha la vacante deja de contarse como vigente.")
        enviar = st.form_submit_button("💾 Guardar vacante", width="stretch")
    if not enviar:
        return
    puesto = puesto_nuevo.strip() if opcion_puesto == "Otro / nuevo puesto" else opcion_puesto
    if empresa == "Seleccionar...":
        st.error("Selecciona una empresa del catálogo.")
        return
    if puesto in ("Seleccionar...", ""):
        st.error("Selecciona un puesto o escribe uno nuevo.")
        return
    norm = normalizar_puesto_vacante(puesto)
    fila = {"ID Vacante": "", "ID Registro Origen": "", "Actividad": actividad, "Fecha": fecha, "Empresa": empresa,
            "Sector Empresa": EMPRESAS_SECTOR.get(empresa, ""), "Puesto Original": puesto, "Tipo de Vacante": norm,
            "Categoría de Puesto": categoria_puesto_vacante(norm, tipo_op), "Tipo de Oportunidad": tipo_op,
            "Área de Oportunidad": area, "Descripción": descripcion, "Requisitos": requisitos, "Beneficios": beneficios,
            "Link de la Publicación": link, "Estado": estado}
    if "fecha_cierre" in extras:
        fila["fecha_cierre"] = cierre
    try:
        res = guardado.importar_vacantes(s, pd.DataFrame([fila]), origen="Captura manual", archivo="Captura manual")
    except Exception as exc:  # noqa: BLE001
        ui.mostrar_error(exc)
        return
    if res.ok and res.guardados:
        ui.flash(res)
        st.rerun()
    ui.mostrar_resultado(res)


# ------------------------------------------------------------------------ carga
def _seccion_carga(s: Sesion) -> None:
    st.caption("Registra **un puesto por fila**. **Importar nunca sobrescribe**: las vacantes que ya existen (misma fecha, empresa, puesto, "
               "oportunidad, área, link y descripción) se omiten y se te informa cuántas fueron.")
    c1, c2 = st.columns(2)
    c1.download_button("⬇️ Plantilla CSV", pd.DataFrame(columns=VACANTES_COLS).to_csv(index=False).encode("utf-8-sig"),
                       "plantilla_vacantes.csv", "text/csv", width="stretch")
    c2.download_button("⬇️ Plantilla Excel", _plantilla_xlsx(VACANTES_COLS), "plantilla_vacantes.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width="stretch")
    archivo = st.file_uploader("Sube un archivo de vacantes (.csv, .xlsx, .xls)", type=["csv", "xlsx", "xls"], key="carga_vacantes")
    ui.bloque_deshacer(s, "vacantes")
    if not archivo:
        return
    try:
        bruto = _lectura_archivo(archivo)
    except Exception:  # noqa: BLE001
        st.error("No se pudo leer el archivo. Revisa que sea un CSV o Excel válido y que no esté protegido con contraseña.")
        return
    st.dataframe(bruto.head(20), width="stretch", hide_index=True)
    prev = guardado.previsualizar_vacantes(s, bruto)
    if not prev.ok:
        st.error(prev.mensaje)
        if prev.errores:
            st.dataframe(pd.DataFrame(prev.errores), hide_index=True, width="stretch")
        return
    c = st.columns(3)
    ui.kpi("Filas recibidas", prev.recibidos, contenedor=c[0])
    ui.kpi("Se guardarán (nuevas)", prev.nuevos, contenedor=c[1])
    ui.kpi("Se omitirán (ya existen / repetidas)", prev.omitidos, contenedor=c[2])
    for aviso in prev.avisos:
        st.warning(aviso)
    if prev.nuevos == 0:
        st.info("No hay vacantes nuevas que guardar.")
        return
    if st.button(f"Guardar {prev.nuevos} vacante(s) nuevas", type="primary", key="carga_vac_ok"):
        res = guardado.importar_vacantes(s, bruto, origen="Carga archivo", archivo=archivo.name)
        ui.flash(res)
        st.rerun()


# --------------------------------------------------------------- editar / baja
def _seccion_editar(s: Sesion) -> None:
    df = datos.vacantes(s)
    if df.empty:
        ui.vacio("No hay vacantes para editar.")
        return
    extras = guardado.columnas_opcionales(s, "vacantes")
    q = st.text_input("Buscar la vacante (empresa, puesto o ID)", key="vedit_q", placeholder="Ej. VAC-0042 · Textiles · Soldador")
    if not q.strip():
        ui.nota("Escribe algo para buscar. Se muestran hasta 200 vacantes.")
        ui.bloque_papelera(s, "vacantes")
        return
    pajar = df[["ID Vacante", "Empresa", "Tipo de Vacante", "Puesto Original"]].astype(str).apply(lambda c: c.map(normalizar_texto)).agg(" ".join, axis=1)
    mask = pd.Series(True, index=df.index)
    for t in normalizar_texto(q).split():
        mask &= pajar.str.contains(t, regex=False)
    res = df[mask].sort_values("Fecha", ascending=False).reset_index(drop=True).head(MAX_FILAS)
    if res.empty:
        ui.vacio("Ninguna vacante coincide.")
        return
    idx = ui.tabla(res, ["ID Vacante", "Fecha", "Empresa", "Tipo de Vacante", "Estado"], fechas=("Fecha",), altura=240,
                   key="vedit_tabla", seleccionable=True)
    if idx is None:
        ui.nota("Elige una vacante de la tabla.")
        ui.bloque_papelera(s, "vacantes")
        return
    f = res.iloc[idx].to_dict()
    vid = str(f["ID Vacante"])
    st.markdown(f"#### Vacante {vid}")
    st.caption(f"Origen: {f.get('ID Registro Origen') or SIN_DATO} · Texto original del puesto: {f.get('Puesto Original') or SIN_DATO}")
    if s.puede("vacantes", "edit"):
        with st.form(f"form_edit_vac_{vid}"):
            c1, c2 = st.columns(2)
            with c1:
                actividad = st.text_input("Actividad", value=str(f.get("Actividad") or ""))
                fv = pd.to_datetime(f["Fecha"], errors="coerce")
                fecha = st.date_input("Fecha de publicación *", value=None if pd.isna(fv) else fv.date(), format="DD/MM/YYYY")
                emp_ops = sorted(set(EMPRESAS_SECTOR) | {str(f["Empresa"])})
                empresa = st.selectbox("Empresa *", emp_ops, index=emp_ops.index(str(f["Empresa"])))
                pue_ops = sorted(set(PUESTOS_CATALOGO) | {str(f["Tipo de Vacante"])})
                puesto = st.selectbox("Puesto normalizado *", pue_ops, index=pue_ops.index(str(f["Tipo de Vacante"])))
                tipo_op = st.selectbox("Tipo de oportunidad", TIPOS_OPORTUNIDAD,
                                       index=TIPOS_OPORTUNIDAD.index(f["Tipo de Oportunidad"]) if f["Tipo de Oportunidad"] in TIPOS_OPORTUNIDAD else 0)
                a_ops = list(dict.fromkeys(AREAS_OPORTUNIDAD + ([str(f["Área de Oportunidad"])] if str(f["Área de Oportunidad"]) else [])))
                area = st.selectbox("Área de oportunidad", a_ops,
                                    index=a_ops.index(str(f["Área de Oportunidad"])) if str(f["Área de Oportunidad"]) in a_ops else 0)
            with c2:
                descripcion = st.text_area("Descripción / funciones", value=str(f.get("Descripción") or ""))
                requisitos = st.text_area("Requisitos", value=str(f.get("Requisitos") or ""))
                beneficios = st.text_area("Beneficios", value=str(f.get("Beneficios") or ""))
                link = st.text_input("Link de la publicación", value=str(f.get("Link de la Publicación") or ""))
                estado = st.selectbox("Estado", ESTADOS_VACANTE, index=ESTADOS_VACANTE.index(f["Estado"]) if f["Estado"] in ESTADOS_VACANTE else 0)
                cierre = None
                if "fecha_cierre" in extras:
                    fc = pd.to_datetime(f.get("fecha_cierre"), errors="coerce")
                    cierre = st.date_input("Fecha de cierre", value=None if pd.isna(fc) else fc.date(), format="DD/MM/YYYY")
            guardar = st.form_submit_button("💾 Guardar cambios", width="stretch")
        if guardar:
            norm = normalizar_puesto_vacante(puesto)
            nuevos = {"Actividad": actividad, "Fecha": fecha, "Empresa": empresa, "Sector Empresa": EMPRESAS_SECTOR.get(empresa, f.get("Sector Empresa", "")),
                      "Tipo de Vacante": norm, "Categoría de Puesto": categoria_puesto_vacante(norm, tipo_op),
                      "Tipo de Oportunidad": tipo_op, "Área de Oportunidad": area, "Descripción": descripcion,
                      "Requisitos": requisitos, "Beneficios": beneficios, "Link de la Publicación": link, "Estado": estado}
            if "fecha_cierre" in extras:
                nuevos["fecha_cierre"] = cierre
            r = guardado.editar(s, "vacantes", vid, nuevos)
            if r.ok and r.guardados:
                ui.flash(r)
                st.rerun()
            ui.mostrar_resultado(r)
    else:
        ui.nota("Tu perfil puede ver este módulo pero no editar vacantes.")
    if s.puede("vacantes", "delete"):
        st.divider()
        if st.button("🗑️ Eliminar esta vacante", key=f"vdel_{vid}"):
            ui.pedir_confirmacion(f"vdel_{vid}", f"Eliminar la vacante {vid}", guardado.impacto_eliminacion(s, "vacantes", vid), "Eliminar vacante")
        if ui.confirmado(f"vdel_{vid}"):
            ui.flash(guardado.eliminar(s, "vacantes", vid))
            st.rerun()
    ui.bloque_papelera(s, "vacantes")


# ------------------------------------------------------------ revisión vigencia
def _seccion_vigencia(s: Sesion) -> None:
    df = datos.vacantes(s)
    if df.empty:
        ui.vacio("No hay vacantes registradas.")
        return
    st.markdown("Las vacantes **Activas** que llevan mucho tiempo publicadas probablemente ya no están abiertas. Esta revisión las lista "
                "para que decidas, **sin cambiar nada automáticamente**.")
    dias = st.slider("Mostrar vacantes activas publicadas hace más de (días)", 30, 730, 180, step=30, key="vig_dias")
    limite = pd.Timestamp(date.today()) - pd.Timedelta(days=dias)
    activas = df[df["Estado"].eq("Activa")]
    candidatas = activas[activas["Fecha"].isna() | (activas["Fecha"] < limite)].copy()
    if tiene_vigencia(df):
        candidatas = candidatas[candidatas["fecha_cierre"].isna() | (candidatas["fecha_cierre"] < pd.Timestamp(date.today()))]
    c = st.columns(3)
    ui.kpi("Vacantes activas", len(activas), contenedor=c[0])
    ui.kpi("Posiblemente vencidas", len(candidatas), f"Activas con más de {dias} días", contenedor=c[1])
    ui.kpi("Con fecha de cierre", int(df["fecha_cierre"].notna().sum()) if tiene_vigencia(df) else None,
           contenedor=c[2], no_disponible=not tiene_vigencia(df), ayuda="" if tiene_vigencia(df) else "Requiere la migración V007")
    if candidatas.empty:
        st.success("No hay vacantes activas con esa antigüedad.")
        return
    por_anio = candidatas.assign(Año=candidatas["Fecha"].dt.year.astype("Int64").astype(str).replace("<NA>", SIN_DATO)).groupby("Año").size()
    ui.nota("Por año de publicación: " + " · ".join(f"{a}: {n}" for a, n in por_anio.items()))
    ui.tabla(candidatas.sort_values("Fecha"), ["ID Vacante", "Fecha", "Empresa", "Tipo de Vacante", "Estado"], fechas=("Fecha",), altura=300)
    if not s.puede("vacantes", "edit"):
        ui.nota("Tu perfil no puede cambiar el estado de las vacantes.")
        return
    ids = candidatas["ID Vacante"].tolist()
    if st.button(f"Marcar estas {len(ids)} vacantes como Inactivas", key="vig_btn"):
        ui.pedir_confirmacion("vig_masivo", "Marcar vacantes como Inactivas", [
            f"Se cambiará el Estado de {len(ids)} vacantes de «Activa» a «Inactiva».",
            "No se elimina ninguna vacante ni se pierde ningún dato.",
            "Puedes revertirlo editando cada vacante o volviendo a activar desde Editar."], "Marcar como Inactivas")
    if ui.confirmado("vig_masivo"):
        ui.flash(guardado.cambiar_estado_vacantes(s, ids, "Inactiva"))
        st.rerun()


# ----------------------------------------------------------------------- página
@ui.protegido
def render() -> None:
    s = actual()
    ui.encabezado("Vacantes y empresas", "Oferta laboral registrada, empresas, vigencia y captura", "💼")
    ui.mostrar_flash()
    params = navegacion.tomar_parametros("vacantes")
    disponibles = {}
    if s.puede("vacantes", "view"):
        disponibles["analisis"] = SECCIONES["analisis"]
        disponibles["empresas"] = SECCIONES["empresas"]
    if s.puede("vacantes", "create"):
        disponibles["alta"] = SECCIONES["alta"]
        disponibles["carga"] = SECCIONES["carga"]
    if s.puede("vacantes", "edit") or s.puede("vacantes", "delete"):
        disponibles["editar"] = SECCIONES["editar"]
    if s.puede("vacantes", "view") and s.puede("vacantes", "edit"):
        disponibles["vigencia"] = SECCIONES["vigencia"]
    if not disponibles:
        st.warning("Tu perfil no tiene acciones disponibles en este módulo.")
        return
    if params.get("apartado") in disponibles:
        st.session_state["vacantes_apartado"] = disponibles[params["apartado"]]
    etiquetas = list(disponibles.values())
    if st.session_state.get("vacantes_apartado") not in etiquetas:
        st.session_state["vacantes_apartado"] = etiquetas[0]
    elegido = st.segmented_control("Apartado", etiquetas, key="vacantes_apartado", label_visibility="collapsed") or etiquetas[0]
    clave = next(k for k, v in disponibles.items() if v == elegido)
    {"analisis": _seccion_analisis, "empresas": _seccion_empresas, "alta": _seccion_alta, "carga": _seccion_carga,
     "editar": _seccion_editar, "vigencia": _seccion_vigencia}[clave](s)
