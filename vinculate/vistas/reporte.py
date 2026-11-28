"""Reporte: documento informativo (PDF y Excel) con las cifras y gráficas que muestran el avance y el aporte del programa."""
from __future__ import annotations

import streamlit as st

from ..auth.sesion import actual
from ..components import ui
from ..core import reportes as nucleo
from ..repositories.errores import SinPermiso
from ..services import datos, reporte_pdf, reportes

_ESTADO = "_reporte_generado"
_ARCHIVOS = "_reporte_archivos"


def _opciones(s, tipo: str) -> list[str]:
    """Municipios o instituciones elegibles; se recalculan solo si cambió la base."""
    pf_n = len(datos.personas_dashboard(s))
    guardado = st.session_state.get("_rep_opciones")
    if not guardado or guardado[0] != pf_n:
        guardado = (pf_n, reportes.opciones(s))
        st.session_state["_rep_opciones"] = guardado
    return guardado[1][tipo]


def _generar(s, tipo: str, valor: str | None, anios: list[int]) -> None:
    try:
        r = reportes.construir(s, tipo, valor, anios)
    except (SinPermiso, ValueError) as exc:
        ui.mostrar_error(exc)
        return
    st.session_state[_ESTADO] = {"reporte": r, "graficas": reporte_pdf.graficas(r), "firma": (tipo, valor, tuple(anios))}
    st.session_state.pop(_ARCHIVOS, None)


def _vista_previa(r: nucleo.Reporte, graficas: dict) -> None:
    i = r.indicadores
    st.markdown(f"### {r.subtitulo}")
    st.caption(f"Periodo: {r.periodo}")
    c = st.columns(4)
    ui.kpi("Personas atendidas", i["personas"], contenedor=c[0], info="reporte.indicadores")
    ui.kpi("Con al menos una vinculación", i["vinculadas"], contenedor=c[1])
    ui.kpi("Vinculaciones", i["vinculaciones"], contenedor=c[2])
    ui.kpi("Empresas con vinculación", i["empresas"], contenedor=c[3])
    if r.colocaciones_disponibles:
        c = st.columns(4)
        ui.kpi("Personas colocadas", i["colocadas"], contenedor=c[0])
        ui.kpi("Colocaciones", i["colocaciones"], contenedor=c[1])
        ui.kpi("Tasa de colocación", None if i["tasa_colocacion"] is None else f"{i['tasa_colocacion']}%", contenedor=c[2], info="reporte.tasa_colocacion")
        ui.kpi("Personas recurrentes", i["recurrentes"], contenedor=c[3])
    else:
        ui.nota("Tu perfil no puede consultar los seguimientos con empresas, así que el reporte no incluye colocaciones.")
    st.markdown("**Lectura rápida**")
    for t in r.lecturas:
        st.markdown(f"- {t}")
    ui.ayuda_grafica("reporte.embudo")
    st.image(graficas["embudo"], width="stretch")
    if "avance" in graficas:
        st.image(graficas["avance"], width="stretch")
        c1, c2 = st.columns(2)
        for col, clave in ((c1, "acumulado"), (c2, "tipos")):
            if clave in graficas:
                col.image(graficas[clave], width="stretch")
    for clave in ("municipios", "instituciones"):
        if clave in graficas:
            st.image(graficas[clave], width="stretch")
    perfil = [graficas[k] for k in ("sexo", "escolaridad", "edad", "prioritario") if k in graficas]
    for a in range(0, len(perfil), 2):
        cols = st.columns(2)
        for col, png in zip(cols, perfil[a:a + 2]):
            col.image(png, width="stretch")
    if not r.empresas.empty:
        st.markdown("**Empresas con más personas vinculadas y colocadas**")
        st.dataframe(r.empresas, hide_index=True, width="stretch")


def _descargas(s, r: nucleo.Reporte) -> None:
    st.markdown("#### Descargar")
    if not s.puede("inicio", "export"):
        ui.nota("Tu perfil no tiene permiso para exportar este módulo.")
        return
    ui.ayuda_grafica("reporte.nota", fila_propia=True)
    nota = st.text_area("Nota para el reporte (opcional)", key="rep_nota", max_chars=900, height=90,
                        placeholder="Por ejemplo: contexto del periodo, quién lo solicita o una aclaración que quieras que aparezca impresa.")
    archivos = st.session_state.get(_ARCHIVOS, {})
    c1, c2 = st.columns(2)
    for col, formato, texto in ((c1, "pdf", "📄 Preparar PDF"), (c2, "xlsx", "📊 Preparar Excel con las tablas")):
        if col.button(texto, key=f"rep_prep_{formato}", width="stretch"):
            try:
                datos_b, archivo, mime = reportes.exportar(s, r, formato, nota)
                archivos[formato] = {"datos": datos_b, "archivo": archivo, "mime": mime}
                st.session_state[_ARCHIVOS] = archivos
            except Exception as exc:  # noqa: BLE001
                ui.mostrar_error(exc)
        if formato in archivos:
            a = archivos[formato]
            col.download_button(f"⬇️ Descargar {a['archivo']}", a["datos"], a["archivo"], a["mime"], key=f"rep_dl_{formato}", width="stretch")
    if "pdf" in archivos:
        st.caption("Si cambias la nota, vuelve a pulsar «Preparar PDF» para que aparezca en el archivo.")


@ui.protegido
def render() -> None:
    s = actual()
    ui.encabezado("Reporte", "Un documento con las cifras y gráficas que muestran el avance y el aporte del programa", "📄")
    if not (s.puede("inicio", "view") and s.puede("personas", "view")):
        st.info("Tu cuenta no puede consultar la información necesaria para el reporte.")
        return

    ui.ayuda_grafica("reporte.tipo", fila_propia=True)
    etiquetas = {k: v for k, v in nucleo.TIPOS.items()}
    tipo = st.radio("Tipo de reporte", list(etiquetas), format_func=etiquetas.get, horizontal=True, key="rep_tipo")
    c1, c2 = st.columns(2)
    valor = None
    if tipo != "general":
        lista = _opciones(s, tipo)
        if not lista:
            c1.warning("Todavía no hay datos para elegir.")
        else:
            valor = c1.selectbox("Municipio" if tipo == "municipio" else "Institución", lista, key=f"rep_valor_{tipo}",
                                 format_func=nucleo.nombre_legible if tipo == "municipio" else str)
    anios_disp = _opciones(s, "anios")
    anios = c2.multiselect("Años (vacío = todos)", anios_disp, key="rep_anios")

    if st.button("Generar reporte", type="primary", key="rep_generar", disabled=(tipo != "general" and not valor)):
        _generar(s, tipo, valor, sorted(anios))

    est = st.session_state.get(_ESTADO)
    if not est:
        ui.nota("Elige el tipo y el periodo, y pulsa «Generar reporte» para ver la vista previa y descargarlo.")
        return
    if est["firma"] != (tipo, valor, tuple(sorted(anios))):
        ui.nota("Cambiaste las opciones: pulsa «Generar reporte» para actualizar la vista previa.")
    r = est["reporte"]
    st.divider()
    if r.vacio:
        ui.vacio("No hay información para el periodo y la selección elegidos.")
        return
    _vista_previa(r, est["graficas"])
    st.divider()
    _descargas(s, r)
