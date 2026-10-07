"""Personas: análisis, directorio con ficha integral, alta, carga masiva y edición/baja."""
from __future__ import annotations

import io
from datetime import date

import pandas as pd
import streamlit as st

from .. import navegacion
from ..auth.sesion import Sesion, actual
from ..components import charts, paneles, ui
from ..core.catalogos_academicos import (
    ESCOLARIDADES, GRUPOS_PRIORITARIOS, catalogo_areas, catalogo_carreras, catalogo_instituciones,
    escolaridad_canonica, grupo_canonico, opcion_canonica,
)
from ..core.constantes import PERSONAS_COLS, SIN_DATO, TIPOS_VINCULACION
from ..core.personas import obtener_personas_maestras, resumen_vinculaciones_por_persona
from ..core.texto import normalizar_texto, texto_vacio
from ..core.ubicacion import MUNICIPIOS_TLAXCALA, OPCIONES_UBICACION_FILTRO, normalizar_ubicacion_mexico, opciones_ubicacion
from ..services import datos, guardado
from . import ficha

SECCIONES = {
    "analisis": "📊 Análisis", "directorio": "👤 Directorio y ficha", "alta": "➕ Nueva vinculación",
    "carga": "📁 Carga Excel/CSV", "editar": "✏️ Editar / eliminar",
}
_SEXOS = ["", "Femenino", "Masculino", "Indefinido"]
MAX_FILAS_BUSQUEDA = 200


# ---------------------------------------------------------------- utilidades
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


def _txt(base: dict, campo: str) -> str:
    v = base.get(campo, "")
    return "" if texto_vacio(v) else str(v)


def _etiqueta_persona(m: pd.Series) -> str:
    return f"{m['nombre']} — {m['id_persona_maestro']} — {int(m['total_vinculaciones'])} vinculación(es)"


# ---------------------------------------------------------- formulario común
def _formulario(prefijo: str, base: dict, df: pd.DataFrame) -> dict:
    """Campos de un registro de persona. `base` trae los valores actuales (vacío en un alta)."""
    instituciones, carreras, areas = catalogo_instituciones(df), catalogo_carreras(df), catalogo_areas(df)
    edad_actual = pd.to_numeric(base.get("edad"), errors="coerce")
    c1, c2, c3 = st.columns(3)
    with c1:
        nombre = st.text_input("Nombre *", value=_txt(base, "nombre"), key=f"{prefijo}_nombre")
        sexo_a = _txt(base, "sexo")
        sexos = _SEXOS if sexo_a in _SEXOS else _SEXOS + [sexo_a]
        sexo = st.selectbox("Sexo", sexos, index=sexos.index(sexo_a), format_func=lambda x: SIN_DATO if x == "" else x, key=f"{prefijo}_sexo")
        edad = st.number_input("Edad (0 = sin dato)", 0, 120, int(edad_actual) if pd.notna(edad_actual) else 0, key=f"{prefijo}_edad")
        telefono = st.text_input("Teléfono", value=_txt(base, "telefono"), key=f"{prefijo}_tel")
        correo = st.text_input("Correo", value=_txt(base, "correo"), key=f"{prefijo}_correo")
    with c2:
        esc = escolaridad_canonica(_txt(base, "escolaridad"))
        escolaridad = st.selectbox("Escolaridad", ESCOLARIDADES, index=ESCOLARIDADES.index(esc), key=f"{prefijo}_esc")
        car = opcion_canonica(_txt(base, "carrera"), carreras, "Indefinido")
        carrera = st.selectbox("Carrera", carreras, index=carreras.index(car), key=f"{prefijo}_car",
                               help="Catálogo centralizado: las variantes equivalentes aparecen una sola vez.")
        ins = opcion_canonica(_txt(base, "Institución"), instituciones, "Indefinido")
        institucion = st.selectbox("Institución", instituciones, index=instituciones.index(ins), key=f"{prefijo}_ins")
        id_institucion = st.text_input("ID institución", value=_txt(base, "id_institucion"), key=f"{prefijo}_idins")
        ar = opcion_canonica(_txt(base, "area_carrera"), areas, "Indefinido")
        area = st.selectbox("Área de carrera", areas, index=areas.index(ar), key=f"{prefijo}_area")
    with c3:
        ub = normalizar_ubicacion_mexico(_txt(base, "municipio"))
        ub_ops = opciones_ubicacion(ub)
        municipio = st.selectbox("Municipio de Tlaxcala / estado", ub_ops, index=ub_ops.index(ub) if ub in ub_ops else 0,
                                 format_func=lambda x: SIN_DATO if x == "" else x, key=f"{prefijo}_mun",
                                 help="Para Tlaxcala elige uno de sus 60 municipios; para otra entidad, el estado.")
        id_municipio = st.text_input("ID municipio", value=_txt(base, "id_municipio"), key=f"{prefijo}_idmun")
        gr = grupo_canonico(_txt(base, "grupo_prioritario"), edad_actual if pd.notna(edad_actual) else None)
        grupo = st.selectbox("Grupo prioritario", GRUPOS_PRIORITARIOS, index=GRUPOS_PRIORITARIOS.index(gr), key=f"{prefijo}_grp")
        tipo_a = _txt(base, "vinculacion")
        tipos = TIPOS_VINCULACION if tipo_a in TIPOS_VINCULACION or not tipo_a else TIPOS_VINCULACION + [tipo_a]
        tipo = st.selectbox("Tipo de vinculación *", tipos, index=tipos.index(tipo_a) if tipo_a in tipos else 0, key=f"{prefijo}_tipo")
        f_a = pd.to_datetime(base.get("fecha_registro"), errors="coerce")
        fecha = st.date_input("Fecha de registro (opcional)", value=None if pd.isna(f_a) else f_a.date(), key=f"{prefijo}_fecha",
                              format="DD/MM/YYYY")
    return {"nombre": nombre, "sexo": sexo, "edad": None if edad == 0 else edad, "escolaridad": escolaridad,
            "carrera": carrera, "Institución": institucion, "id_institucion": id_institucion, "municipio": municipio,
            "id_municipio": id_municipio, "telefono": telefono, "correo": correo, "grupo_prioritario": grupo,
            "vinculacion": tipo, "fecha_registro": fecha, "area_carrera": area}


# ------------------------------------------------------------------- análisis
def _filtros_analisis(df: pd.DataFrame) -> pd.DataFrame:
    def vis(serie):
        s = serie.fillna("").astype(str).str.strip()
        return s.mask(s.eq(""), SIN_DATO)

    out = df
    with st.expander("🎛️ Filtros", expanded=False):
        cols = st.columns(4)
        for n, col in enumerate(["sexo", "escolaridad", "carrera", "Institución", "municipio", "grupo_prioritario", "vinculacion"]):
            if col == "municipio":
                ops = list(OPCIONES_UBICACION_FILTRO) + [m for m in vis(df[col]).unique() if m not in OPCIONES_UBICACION_FILTRO]
            else:
                ops = sorted(vis(df[col]).unique())
            sel = cols[n % 4].multiselect(col, ops, key=f"fp_{col}", placeholder="Todos")
            if sel:
                out = out[vis(out[col]).isin(sel)]
        anios = sorted(df["año"].dropna().astype(int).unique(), reverse=True)
        sel = cols[3].multiselect("Año", anios, key="fp_anio", placeholder="Todos")
        if sel:
            out = out[out["año"].isin(sel)]
    return out


def _seccion_analisis(s: Sesion) -> None:
    df = datos.personas_dashboard(s)
    if df.empty:
        ui.vacio("No hay registros de personas todavía.")
        return
    pf = _filtros_analisis(df)
    if pf.empty:
        ui.vacio()
        return
    por_persona = pf.groupby("id_persona_maestro").size()
    unicas, vinc = int(pf["id_persona_maestro"].nunique()), len(pf)
    c = st.columns(6)
    ui.kpi("Personas únicas", unicas, contenedor=c[0])
    ui.kpi("Vinculaciones", vinc, contenedor=c[1])
    ui.kpi("Recurrentes", int((por_persona > 1).sum()), "2 o más vinculaciones", contenedor=c[2])
    ui.kpi("Vinculaciones por persona", vinc / unicas if unicas else None, contenedor=c[3], decimales=2)
    ui.kpi("Máximo por persona", int(por_persona.max()), contenedor=c[4])
    ui.kpi("Sin año", int(pf["año"].isna().sum()), "No se asignan a un periodo", contenedor=c[5])
    ui.explicacion("Base de personas después de los filtros.",
                   "Personas únicas = ID persona maestra; vinculaciones = cada fila histórica.",
                   "Un promedio mayor a 1 indica recurrencia. «Sin año» no debe usarse para comparar periodos.")
    vista = st.segmented_control("Vista", ["Resumen", "Evolución anual", "Recurrencia", "Perfil"], default="Resumen",
                                 key="personas_vista", label_visibility="collapsed") or "Resumen"
    if vista == "Resumen":
        c1, c2 = st.columns(2)
        with c1:
            tipos = charts.conteo(pf["vinculacion"], "Tipo", "Vinculaciones")
            charts.mostrar(charts.barras_h(tipos, "Tipo", "Vinculaciones", "Vinculaciones por tipo"), "pa_tipos")
        with c2:
            dist = por_persona.value_counts().sort_index().reset_index()
            dist.columns = ["Vinculaciones por persona", "Personas"]
            dist["Grupo"] = dist["Vinculaciones por persona"].astype(str)
            charts.mostrar(charts.barras_v(dist, "Grupo", "Personas", "Frecuencia de vinculaciones por persona"), "pa_freq")
        top = resumen_vinculaciones_por_persona(pf).head(15)
        st.subheader("Personas con más vinculaciones")
        ui.tabla(top, ["id_persona_maestro", "nombre", "total_vinculaciones"],
                 {"id_persona_maestro": "ID", "nombre": "Nombre", "total_vinculaciones": "Vinculaciones"})
    elif vista == "Evolución anual":
        if paneles.evolucion_anual(pf, "pa_evo"):
            st.subheader("Indicadores anuales")
            ui.tabla(paneles.tabla_anual(pf))
            sin = int(pf["año"].isna().sum())
            ui.nota(f"Además hay {sin:,} vinculación(es) sin año; se conservan y no se asignan a ningún periodo.")
            if "anio_fuente" in pf.columns and (pf["anio_fuente"] == "imputado").any():
                ui.nota("Las barras rayadas son años estimados en una limpieza histórica; no fueron capturados originalmente.")
    elif vista == "Recurrencia":
        res = resumen_vinculaciones_por_persona(pf)
        rec = res[res["total_vinculaciones"] > 1]
        c = st.columns(3)
        ui.kpi("Con 1 vinculación", int((res["total_vinculaciones"] == 1).sum()), contenedor=c[0])
        ui.kpi("Con 2 o más", len(rec), contenedor=c[1])
        ui.kpi("% recurrentes", ui.fmt_pct(len(rec), len(res)), contenedor=c[2])
        ui.tabla(rec, ["id_persona_maestro", "nombre", "total_vinculaciones", "primera_fecha", "ultima_fecha"],
                 {"id_persona_maestro": "ID", "nombre": "Nombre", "total_vinculaciones": "Vinculaciones",
                  "primera_fecha": "Primera", "ultima_fecha": "Última"}, fechas=("primera_fecha", "ultima_fecha"), altura=420)
        ui.boton_exportar(s, "personas", rec, "personas_recurrentes", "personas_rec")
    else:
        m = obtener_personas_maestras(pf)
        c1, c2 = st.columns(2)
        with c1:
            charts.mostrar(charts.dona(charts.conteo(m["sexo"], "Sexo", "Personas"), "Sexo", "Personas", "Personas únicas por sexo"), "pa_sexo")
        with c2:
            esc = charts.conteo(m["escolaridad"], "Escolaridad", "Personas", top=10)
            charts.mostrar(charts.barras_h(esc, "Escolaridad", "Personas", "Escolaridad"), "pa_esc")
        conteo = m["municipio"].map(normalizar_ubicacion_mexico).value_counts()
        muni = pd.DataFrame({"Municipio": MUNICIPIOS_TLAXCALA})
        muni["Personas"] = muni["Municipio"].map(conteo).fillna(0).astype(int)
        con_datos = int((muni["Personas"] > 0).sum())
        st.subheader(f"Los 60 municipios de Tlaxcala ({con_datos} con personas)")
        with st.expander("Ver los 60 municipios (incluye los que tienen cero)"):
            charts.mostrar(charts.barras_h(muni.sort_values("Personas", ascending=False), "Municipio", "Personas",
                                           "Personas únicas por municipio de Tlaxcala", alto=1500), "pa_mun60")
        c3, c4 = st.columns(2)
        with c3:
            charts.mostrar(charts.barras_h(charts.conteo(m["Institución"], "Institución", "Personas", top=12),
                                           "Institución", "Personas", "Instituciones"), "pa_inst")
        with c4:
            charts.mostrar(charts.barras_h(charts.conteo(m["carrera"], "Carrera", "Personas", top=12),
                                           "Carrera", "Personas", "Carreras"), "pa_car")
        ui.explicacion("Una fila por persona maestra con su dato más reciente y completo.",
                       "Perfil de las personas únicas: sexo, escolaridad, territorio, institución y carrera.",
                       "Cero en un municipio significa que no hay personas registradas ahí con el filtro actual.")


# ------------------------------------------------------------------ directorio
def _seccion_directorio(s: Sesion, preseleccion: str | None) -> None:
    m = datos.maestras(s)
    if m.empty:
        ui.vacio("Todavía no hay personas registradas.")
        return
    q = st.text_input("Buscar por nombre, ID, correo o teléfono", placeholder="Ej. María López · PER-0042 · 246…", key="dir_q")
    vista = m
    if q.strip():
        terminos = normalizar_texto(q).split()
        pajar = m[["nombre", "id_persona_maestro", "correo", "telefono"]].astype(str).apply(lambda c: c.map(normalizar_texto)).agg(" ".join, axis=1)
        mask = pd.Series(True, index=m.index)
        for t in terminos:
            mask &= pajar.str.contains(t, regex=False)
        vista = m[mask]
    vista = vista.sort_values(["nombre", "id_persona_maestro"]).reset_index(drop=True)
    st.caption(f"{len(vista)} persona(s)" + (f" · mostrando las primeras {MAX_FILAS_BUSQUEDA}" if len(vista) > MAX_FILAS_BUSQUEDA else ""))
    tabla = vista.head(MAX_FILAS_BUSQUEDA)
    idx = ui.tabla(tabla, ["nombre", "id_persona_maestro", "municipio", "carrera", "Institución", "total_vinculaciones", "ultima_fecha"],
                   {"nombre": "Nombre", "id_persona_maestro": "ID", "municipio": "Municipio", "carrera": "Carrera",
                    "total_vinculaciones": "Vinculaciones", "ultima_fecha": "Última fecha"}, fechas=("ultima_fecha",),
                   altura=300, key="dir_tabla", seleccionable=True)
    ui.boton_exportar(s, "personas", vista, "personas_directorio", "personas_dir")
    elegido = None
    if idx is not None:
        elegido = str(tabla.iloc[idx]["id_persona_maestro"])
    elif preseleccion and preseleccion in set(m["id_persona_maestro"]):
        elegido = preseleccion
    if elegido:
        st.divider()
        ficha.contenido(s, elegido)
    else:
        ui.nota("Elige una fila para ver la ficha integral de la persona.")


# ------------------------------------------------------------------------ alta
def _seccion_alta(s: Sesion, preseleccion: str | None) -> None:
    df = datos.personas(s)
    maestras = datos.maestras(s) if not df.empty else pd.DataFrame()
    st.markdown("Cada captura agrega una **vinculación histórica**. Si la persona ya existe se conserva su ID de persona; "
                "si es nueva, el sistema le asigna uno **al guardar** (así nunca choca con capturas simultáneas de otras personas).")
    ref = None
    modo = st.radio("¿La persona ya existe?", ["Sí, asociar a una persona existente", "No, crear una persona nueva"],
                    horizontal=True, index=0 if preseleccion else 1, key="alta_modo")
    if modo.startswith("Sí"):
        if maestras.empty:
            st.info("Todavía no hay personas; registra una persona nueva.")
        else:
            m = maestras.sort_values(["nombre", "id_persona_maestro"]).reset_index(drop=True)
            ids = list(m["id_persona_maestro"])
            idx0 = ids.index(preseleccion) if preseleccion in ids else 0
            i = st.selectbox("Persona", list(m.index), index=idx0, format_func=lambda k: _etiqueta_persona(m.loc[k]), key="alta_persona")
            ref = m.loc[i]
            st.caption(f"La nueva vinculación quedará asociada a {ref['id_persona_maestro']}.")
    base = ref.to_dict() if ref is not None else {}
    if ref is not None:
        base["vinculacion"] = ""  # el tipo se elige en cada captura
        base["fecha_registro"] = None
    sufijo = ref["id_persona_maestro"] if ref is not None else "nueva"
    with st.form("form_alta_persona"):
        valores = _formulario(f"alta_{sufijo}", base, df)
        homonimo = False
        if ref is None:
            homonimo = st.checkbox("Si ya existe una persona con este mismo nombre, confirmo que es OTRA persona.", key="alta_homonimo")
        enviar = st.form_submit_button("💾 Guardar vinculación", width="stretch")
    if enviar:
        if ref is None and not maestras.empty and normalizar_texto(valores["nombre"]) in set(maestras["nombre"].map(normalizar_texto)):
            if not homonimo:
                st.error("Ya existe una persona con ese nombre. Si es la misma, elige «Sí, asociar a una persona existente»; "
                         "si es otra, marca la casilla de confirmación.")
                return
        fecha = valores["fecha_registro"]
        fila = {**valores, "id_persona": "", "id_persona_maestro": ref["id_persona_maestro"] if ref is not None else "",
                "Año": fecha.year if fecha else "", "estatus_vinculacion": "Vinculado"}
        try:
            res = guardado.importar_personas(s, pd.DataFrame([fila]), origen="Captura manual", archivo="Captura manual")
        except Exception as exc:  # noqa: BLE001
            ui.mostrar_error(exc)
            return
        if res.ok and res.guardados:
            ui.flash(res)
            st.rerun()
        ui.mostrar_resultado(res)


# ------------------------------------------------------------------------ carga
def _seccion_carga(s: Sesion) -> None:
    st.caption("Para conservar la relación entre registros, incluye siempre `id_persona_maestro` al importar históricos ya normalizados. "
               "**Importar nunca sobrescribe**: los registros cuyo ID ya existe se omiten y se te informa cuántos fueron.")
    c1, c2 = st.columns(2)
    c1.download_button("⬇️ Plantilla CSV", pd.DataFrame(columns=PERSONAS_COLS).to_csv(index=False).encode("utf-8-sig"),
                       "plantilla_personas.csv", "text/csv", width="stretch")
    c2.download_button("⬇️ Plantilla Excel", _plantilla_xlsx(PERSONAS_COLS), "plantilla_personas.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width="stretch")
    archivo = st.file_uploader("Sube un archivo (.csv, .xlsx, .xls)", type=["csv", "xlsx", "xls"], key="carga_personas")
    ui.bloque_deshacer(s, "personas")
    if not archivo:
        return
    try:
        bruto = _lectura_archivo(archivo)
    except Exception:  # noqa: BLE001
        st.error("No se pudo leer el archivo. Revisa que sea un CSV o Excel válido y que no esté protegido con contraseña.")
        return
    st.write("Vista previa (primeras 20 filas):")
    st.dataframe(bruto.head(20), width="stretch", hide_index=True)
    if not any(c.strip().lower() == "id_persona_maestro" for c in bruto.columns):
        st.warning("El archivo no trae `id_persona_maestro`: el sistema creará una persona nueva por cada fila; no puede inferir "
                   "con seguridad qué filas son de la misma persona.")
    try:
        prev = guardado.previsualizar_personas(s, bruto)
    except Exception as exc:  # noqa: BLE001
        ui.mostrar_error(exc)
        return
    if not prev.ok:
        st.error(prev.mensaje)
        if prev.errores:
            st.dataframe(pd.DataFrame(prev.errores), hide_index=True, width="stretch")
        return
    c = st.columns(3)
    ui.kpi("Filas recibidas", prev.recibidos, contenedor=c[0])
    ui.kpi("Se guardarán (nuevos)", prev.nuevos, contenedor=c[1])
    ui.kpi("Se omitirán (ya existen / repetidos)", prev.omitidos, contenedor=c[2])
    for aviso in prev.avisos:
        st.warning(aviso)
    if prev.nuevos == 0:
        st.info("No hay registros nuevos que guardar.")
        return
    if st.button(f"Guardar {prev.nuevos} registro(s) nuevos", type="primary", key="carga_personas_ok"):
        try:
            res = guardado.importar_personas(s, bruto, origen="Carga archivo", archivo=archivo.name)
        except Exception as exc:  # noqa: BLE001
            ui.mostrar_error(exc)
            return
        ui.flash(res)
        st.rerun()


# --------------------------------------------------------------- editar / baja
def _seccion_editar(s: Sesion, preseleccion: str | None) -> None:
    df = datos.personas(s)
    if df.empty:
        ui.vacio("No hay registros para editar.")
        return
    q = st.text_input("Buscar el registro (nombre, ID de registro o ID de persona)", key="edit_q",
                      value=preseleccion or "", placeholder="Ej. PER-0042 · A-00123-00456 · María")
    if not q.strip():
        ui.nota("Escribe algo para buscar. Se muestran hasta 200 registros.")
        ui.bloque_papelera(s, "personas")
        return
    terminos = normalizar_texto(q).split()
    pajar = df[["id_persona", "id_persona_maestro", "nombre"]].astype(str).apply(lambda c: c.map(normalizar_texto)).agg(" ".join, axis=1)
    mask = pd.Series(True, index=df.index)
    for t in terminos:
        mask &= pajar.str.contains(t, regex=False)
    res = df[mask].sort_values(["nombre", "fecha_registro"]).reset_index(drop=True).head(MAX_FILAS_BUSQUEDA)
    if res.empty:
        ui.vacio("Ningún registro coincide con la búsqueda.")
        return
    idx = ui.tabla(res, ["id_persona", "nombre", "id_persona_maestro", "vinculacion", "fecha_registro", "municipio"],
                   {"id_persona": "ID de registro", "nombre": "Nombre", "id_persona_maestro": "ID persona", "vinculacion": "Tipo",
                    "fecha_registro": "Fecha", "municipio": "Municipio"}, fechas=("fecha_registro",), altura=240,
                   key="edit_tabla", seleccionable=True)
    if idx is None:
        ui.nota("Elige un registro de la tabla para editarlo o eliminarlo.")
        ui.bloque_papelera(s, "personas")
        return
    fila = res.iloc[idx].to_dict()
    rid = str(fila["id_persona"])
    st.markdown(f"#### Registro {rid}")
    if s.puede("personas", "edit"):
        with st.form(f"form_editar_{rid}"):
            st.text_input("ID de registro (no editable)", value=rid, disabled=True)
            valores = _formulario(f"ed_{rid}", fila, df)
            guardar = st.form_submit_button("💾 Guardar cambios", width="stretch")
        if guardar:
            fecha = valores["fecha_registro"]
            nuevos = dict(valores)
            if fecha:  # Si se borra la fecha NO se borra el año (puede ser un dato histórico sin fecha).
                nuevos["Año"] = fecha.year
            try:
                r = guardado.editar(s, "personas", rid, nuevos)
            except Exception as exc:  # noqa: BLE001
                ui.mostrar_error(exc)
            else:
                if r.ok and r.guardados:
                    ui.flash(r)
                    st.rerun()
                ui.mostrar_resultado(r)
        with st.expander("Reasignar este registro a otra persona (corregir duplicados)"):
            ui.nota("Úsalo solo si este registro pertenece a otra persona ya existente (por ejemplo, la misma persona capturada dos veces).")
            m = datos.maestras(s).sort_values("nombre").reset_index(drop=True)
            m = m[m["id_persona_maestro"].ne(fila["id_persona_maestro"])].reset_index(drop=True)
            if m.empty:
                st.info("No hay otras personas.")
            else:
                j = st.selectbox("Nueva persona", list(m.index), format_func=lambda k: _etiqueta_persona(m.loc[k]), key=f"reasig_{rid}")
                if st.button("Reasignar", key=f"reasig_btn_{rid}"):
                    ui.pedir_confirmacion(f"reasig_{rid}", "Reasignar a otra persona", [
                        f"El registro {rid} dejará de pertenecer a {fila['id_persona_maestro']} y pasará a {m.loc[j, 'id_persona_maestro']} ({m.loc[j, 'nombre']}).",
                        "Cambia cuántas vinculaciones tiene cada persona y sus indicadores.",
                        "Puedes revertirlo reasignándolo de vuelta."], "Reasignar")
                if ui.confirmado(f"reasig_{rid}"):
                    r = guardado.editar(s, "personas", rid, {"id_persona_maestro": m.loc[j, "id_persona_maestro"]})
                    ui.flash(r)
                    st.rerun()
    else:
        ui.nota("Tu perfil puede ver este módulo pero no editar registros.")
    if s.puede("personas", "delete"):
        st.divider()
        if st.button("🗑️ Eliminar este registro", key=f"del_{rid}"):
            ui.pedir_confirmacion(f"del_{rid}", f"Eliminar el registro {rid}", guardado.impacto_eliminacion(s, "personas", rid),
                                  "Eliminar registro")
        if ui.confirmado(f"del_{rid}"):
            ui.flash(guardado.eliminar(s, "personas", rid))
            st.rerun()
    ui.bloque_papelera(s, "personas")


# ----------------------------------------------------------------------- página
@ui.protegido
def render() -> None:
    s = actual()
    ui.encabezado("Personas", "Análisis, directorio con ficha integral y registro de vinculaciones", "👥")
    ui.mostrar_flash()
    params = navegacion.tomar_parametros("personas")

    disponibles = {}
    if s.puede("personas", "view"):
        disponibles["analisis"] = SECCIONES["analisis"]
        disponibles["directorio"] = SECCIONES["directorio"]
    if s.puede("personas", "create"):
        disponibles["alta"] = SECCIONES["alta"]
        disponibles["carga"] = SECCIONES["carga"]
    if s.puede("personas", "edit") or s.puede("personas", "delete"):
        disponibles["editar"] = SECCIONES["editar"]
    if not disponibles:
        st.warning("Tu perfil no tiene acciones disponibles en este módulo.")
        return
    if params.get("apartado") in disponibles:
        st.session_state["personas_apartado"] = disponibles[params["apartado"]]
    etiquetas = list(disponibles.values())
    if st.session_state.get("personas_apartado") not in etiquetas:
        st.session_state["personas_apartado"] = etiquetas[0]
    elegido = st.segmented_control("Apartado", etiquetas, key="personas_apartado", label_visibility="collapsed") or etiquetas[0]
    clave = next(k for k, v in disponibles.items() if v == elegido)
    persona = params.get("persona") or params.get("editar")
    if clave == "analisis":
        _seccion_analisis(s)
    elif clave == "directorio":
        _seccion_directorio(s, persona)
    elif clave == "alta":
        _seccion_alta(s, persona)
    elif clave == "carga":
        _seccion_carga(s)
    else:
        _seccion_editar(s, persona)
