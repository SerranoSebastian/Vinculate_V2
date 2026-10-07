"""Ficha integral de una persona: perfil, historial, seguimientos con empresas y calidad de datos."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from .. import navegacion
from ..auth.sesion import Sesion, actual
from ..components import ui
from ..core.constantes import SIN_DATO
from ..core.texto import fecha_visible, texto_vacio, visible
from ..repositories.errores import ErrorDatos
from ..services import datos, disponibilidad

CAMPOS_PERFIL = [("sexo", "Sexo"), ("edad", "Edad"), ("municipio", "Municipio / estado"), ("escolaridad", "Escolaridad"),
                 ("carrera", "Carrera"), ("area_carrera", "Área de carrera"), ("Institución", "Institución"),
                 ("grupo_prioritario", "Grupo prioritario"), ("telefono", "Teléfono"), ("correo", "Correo")]
CAMPOS_CALIDAD = ["telefono", "correo", "municipio", "carrera", "Institución", "escolaridad", "sexo", "edad"]
_NO_DEFINIDO = {"", "indefinido", "nan", "none"}


def _faltantes(fila) -> list[str]:
    nombres = dict(CAMPOS_PERFIL)
    out = []
    for c in CAMPOS_CALIDAD:
        v = fila.get(c)
        if texto_vacio(v) or str(v).strip().lower() in _NO_DEFINIDO:
            out.append(nombres[c])
    return out


def _anio_txt(r) -> str:
    anio = visible(r.get("Año"))
    return anio + " (estimado)" if r.get("anio_fuente") == "imputado" and anio != SIN_DATO else anio


def _inst_txt(r) -> str:
    inst = visible(r.get("Institución"))
    return inst + " (asignada por balanceo)" if r.get("institucion_fuente") == "balanceado" and inst != SIN_DATO else inst


def contenido(sesion: Sesion, id_maestro: str) -> None:
    if not sesion.puede("personas", "view"):
        st.error("Tu perfil no tiene permiso para consultar personas.")
        return
    personas = datos.personas(sesion)
    hist = personas[personas["id_persona_maestro"].eq(id_maestro)].copy()
    if hist.empty:
        ui.vacio("Esa persona ya no existe o fue eliminada.")
        return
    maestras = datos.maestras(sesion)
    fila = maestras[maestras["id_persona_maestro"].eq(id_maestro)].iloc[0]
    hist = hist.sort_values(["fecha_registro", "id_persona"], na_position="last")

    seg = pd.DataFrame()
    estatus = "Vinculado"
    if sesion.puede("vinculaciones", "view"):
        todos = datos.vinculaciones(sesion)
        seg = todos[todos["id_persona_maestro"].eq(id_maestro)].copy()
        estado = datos.estado_personas(sesion)
        e = estado[estado["id_persona_maestro"].eq(id_maestro)]
        if not e.empty:
            estatus = e.iloc[0]["estatus_general"]

    faltan = _faltantes(fila)
    st.subheader(visible(fila.get("nombre")))
    chips = ui.chip(f"ID {id_maestro}") + ui.chip(estatus, "ok" if estatus in ("Vinculado", "Colocado") else "no")
    if len(hist) > 1:
        chips += ui.chip(f"Recurrente · {len(hist)} vinculaciones")
    if faltan:
        chips += ui.chip(f"{len(faltan)} dato(s) incompleto(s)", "est")
    if (hist.get("anio_fuente", pd.Series(dtype=str)) == "imputado").any():
        chips += ui.chip("Incluye año estimado", "est")
    st.markdown(chips, unsafe_allow_html=True)

    fechas = hist["fecha_registro"].dropna()
    c = st.columns(4)
    ui.kpi("Vinculaciones", len(hist), contenedor=c[0])
    ui.kpi("Tipos distintos", int(hist["vinculacion"].replace("", pd.NA).nunique()), contenedor=c[1])
    ui.kpi("Primera fecha", fecha_visible(fechas.min()) if len(fechas) else SIN_DATO, contenedor=c[2], no_disponible=not len(fechas))
    ui.kpi("Última fecha", fecha_visible(fechas.max()) if len(fechas) else SIN_DATO, contenedor=c[3], no_disponible=not len(fechas))

    t1, t2, t3, t4 = st.tabs(["Perfil", "Historial", "Seguimientos con empresas", "Calidad de datos"])
    with t1:
        cols = st.columns(3)
        for n, (campo, etiqueta) in enumerate(CAMPOS_PERFIL):
            cols[n % 3].markdown(f"**{etiqueta}:** {visible(fila.get(campo))}")
        nota_inst = hist.get("institucion_fuente", pd.Series(dtype=str)).eq("balanceado").any()
        if nota_inst:
            ui.nota("La institución de al menos un registro fue asignada por una corrección de balanceo, no capturada por la persona.")
        _bloque_disponibilidad(sesion, id_maestro)
    with t2:
        tabla = pd.DataFrame({
            "ID de registro": hist["id_persona"], "Tipo": hist["vinculacion"], "Fecha": hist["fecha_registro"],
            "Año": hist.apply(_anio_txt, axis=1), "Institución": hist.apply(_inst_txt, axis=1),
            "Carrera": hist["carrera"], "Municipio": hist["municipio"],
        })
        ui.tabla(tabla, fechas=("Fecha",))
    with t3:
        if not sesion.puede("vinculaciones", "view"):
            ui.nota("Tu perfil no puede consultar seguimientos.")
        elif seg.empty:
            st.info("Todavía no tiene seguimientos con empresas. Su registro histórico ya cuenta como vinculación.")
        else:
            seg = seg.sort_values(["fecha_vinculacion", "fecha_actualizacion"], na_position="first")
            ui.tabla(seg, ["id_vinculacion", "empresa", "tipo_vacante", "area_oportunidad", "estatus", "fecha_vinculacion",
                           "fecha_colocacion", "observaciones", "responsable"],
                     {"id_vinculacion": "ID", "empresa": "Empresa", "tipo_vacante": "Puesto", "area_oportunidad": "Área",
                      "estatus": "Estatus", "fecha_vinculacion": "Vinculación", "fecha_colocacion": "Colocación",
                      "observaciones": "Observaciones", "responsable": "Responsable"},
                     fechas=("fecha_vinculacion", "fecha_colocacion"))
    with t4:
        if faltan:
            st.warning("Información no disponible en: " + ", ".join(faltan))
        else:
            st.success("Todos los campos clave de contacto y perfil están capturados.")
        ui.nota("«Indefinido» se cuenta como dato incompleto. Nada se rellena automáticamente.")

    st.divider()
    a, b, c3 = st.columns(3)
    if sesion.puede("vinculaciones", "create") and navegacion.existe("vinculaciones"):
        if a.button("➕ Registrar seguimiento", key=f"fch_seg_{id_maestro}", width="stretch"):
            navegacion.ir_a("vinculaciones", persona=id_maestro, apartado="nuevo")
    if sesion.puede("personas", "create") and navegacion.existe("personas"):
        if b.button("➕ Agregar vinculación histórica", key=f"fch_alta_{id_maestro}", width="stretch"):
            navegacion.ir_a("personas", persona=id_maestro, apartado="alta")
    if sesion.puede("personas", "edit") and navegacion.existe("personas"):
        if c3.button("✏️ Editar un registro", key=f"fch_edit_{id_maestro}", width="stretch"):
            navegacion.ir_a("personas", persona=id_maestro, apartado="editar")


def _bloque_disponibilidad(sesion: Sesion, id_maestro: str) -> None:
    try:
        df = disponibilidad.estado(sesion)
    except ErrorDatos:
        return
    if df is None:
        ui.nota("Disponibilidad para vincular: no habilitada todavía (requiere la migración V008).")
        return
    fila = df[df["id_persona_maestro"].eq(id_maestro)]
    actual_v = bool(fila.iloc[0]["disponible"]) if not fila.empty else False
    nota_v = "" if fila.empty or texto_vacio(fila.iloc[0]["nota"]) else str(fila.iloc[0]["nota"])
    st.markdown("**Disponibilidad para ser vinculada** (marca manual)")
    if fila.empty:
        ui.nota("Sin marcar: Información no disponible.")
    if sesion.puede("personas", "edit"):
        nuevo = st.toggle("Disponible para vinculación", value=actual_v, key=f"disp_{id_maestro}")
        texto = st.text_input("Nota (opcional)", value=nota_v, key=f"dispn_{id_maestro}", max_chars=200)
        if st.button("Guardar disponibilidad", key=f"dispg_{id_maestro}"):
            try:
                disponibilidad.guardar(sesion, id_maestro, nuevo, texto)
                st.success("Disponibilidad actualizada.")
            except Exception as exc:  # noqa: BLE001
                ui.mostrar_error(exc)
    else:
        st.write("Disponible" if actual_v and not fila.empty else ("No disponible" if not fila.empty else SIN_DATO))


@st.dialog("Ficha integral de la persona", width="large")
def dialogo(id_maestro: str) -> None:
    sesion = actual()
    if sesion is None:
        st.error("Tu sesión expiró.")
        return
    contenido(sesion, id_maestro)
