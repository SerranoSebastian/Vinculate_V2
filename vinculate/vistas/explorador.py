"""Explorador general: cualquier tabla a la que el usuario tenga acceso, con filtros por columna, búsqueda por nombre/ID y exportación."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from ..auth.sesion import actual
from ..components import ui
from ..core import explorador as filtros_exp
from ..services import datos
from . import ficha

MAX_FILAS = 1000
BASES = {
    "personas": ("Personas (una fila por persona)", "personas"),
    "historicos": ("Registros históricos de personas", "personas"),
    "vacantes": ("Vacantes", "vacantes"),
    "vinculaciones": ("Seguimientos con empresas", "vinculaciones"),
}
COLS_VISTA = {
    "personas": ["id_persona_maestro", "nombre", "sexo", "edad", "municipio", "escolaridad", "carrera", "Institución",
                 "grupo_prioritario", "telefono", "correo", "total_vinculaciones", "tipos_vinculacion", "años_con_registro"],
    "historicos": ["id_persona", "id_persona_maestro", "nombre", "municipio", "carrera", "Institución", "vinculacion",
                   "estatus_vinculacion", "fecha_registro", "Año"],
    "vacantes": ["ID Vacante", "Empresa", "Sector Empresa", "Puesto Original", "Tipo de Vacante", "Tipo de Oportunidad",
                 "Área de Oportunidad", "Estado", "Fecha", "fecha_cierre", "Link de la Publicación"],
    "vinculaciones": ["id_vinculacion", "id_persona_maestro", "nombre_persona", "empresa", "sector_empresa", "tipo_vacante",
                      "estatus", "fecha_vinculacion", "fecha_colocacion", "responsable"],
}


def _base(sesion, clave: str) -> pd.DataFrame:
    if clave == "personas":
        return datos.maestras(sesion)
    if clave == "historicos":
        return datos.personas(sesion)
    if clave == "vacantes":
        return datos.vacantes(sesion)
    return datos.vinculaciones(sesion)


def _limpiar(clave: str) -> None:
    for col, _, _ in filtros_exp.FILTROS[clave]:
        st.session_state.pop(f"exp_f_{clave}_{col}", None)
    st.session_state.pop(f"exp_texto_{clave}", None)


def _filtros(clave: str, df: pd.DataFrame) -> tuple[dict[str, list[str]], str]:
    """Dibuja el buscador de nombre/ID y los filtros por columna de la base elegida."""
    texto = st.text_input("Buscar", key=f"exp_texto_{clave}", placeholder=filtros_exp.AYUDA_TEXTO[clave] + " (todas las palabras deben aparecer)")
    elegidos: dict[str, list[str]] = {}
    with st.expander("🎛️ Filtros", expanded=True):
        defs = [d for d in filtros_exp.FILTROS[clave] if d[0] in df.columns]
        for i in range(0, len(defs), 3):
            cols = st.columns(3)
            for caja, (col, etiqueta, multi) in zip(cols, defs[i:i + 3]):
                elegidos[col] = caja.multiselect(etiqueta, filtros_exp.opciones(df, col, multi), key=f"exp_f_{clave}_{col}", placeholder="Todos")
        st.button("Limpiar filtros", on_click=_limpiar, args=(clave,), key=f"exp_limpiar_{clave}")
    activos = [f"{etq}: {', '.join(elegidos[c])}" for c, etq, _ in filtros_exp.FILTROS[clave] if elegidos.get(c)]
    if activos:
        st.caption("Filtros activos → " + " · ".join(activos))
    if clave == "personas" and activos:
        st.caption("Una persona aparece si alguno de sus registros cumple los filtros (igual que en el Inicio ejecutivo). "
                   "La columna «municipio» muestra su dato más reciente.")
    return elegidos, texto


@ui.protegido
def render() -> None:
    sesion = actual()
    ui.encabezado("Explorador general", "Consulta, busca y exporta las bases a las que tu perfil tiene acceso.", "🔎")
    disponibles = {k: v for k, v in BASES.items() if sesion.puede(v[1], "view")}
    if not disponibles:
        ui.vacio("Tu perfil no tiene acceso a ninguna base de datos. Pide a un administrador que habilite Personas, Vacantes o Vinculaciones.")
        return
    clave = st.segmented_control("Base", list(disponibles), format_func=lambda k: disponibles[k][0],
                                 default=next(iter(disponibles)), key="explorador_base", label_visibility="collapsed")
    if clave is None:
        clave = next(iter(disponibles))
    df = _base(sesion, clave)
    total = len(df)
    if clave == "personas":
        # Misma regla que el Inicio ejecutivo: los filtros se evalúan sobre los registros históricos de cada persona.
        hist = datos.personas_dashboard(sesion)
        elegidos, texto = _filtros(clave, hist)
        df = filtros_exp.aplicar_a_personas(hist, df, elegidos, texto).reset_index(drop=True)
    else:
        elegidos, texto = _filtros(clave, df)
        df = filtros_exp.aplicar(df, clave, elegidos, texto).reset_index(drop=True)
    hay_filtro = bool(texto.strip()) or any(elegidos.values())

    c1, c2 = st.columns(2)
    ui.kpi("Registros en la base", total, contenedor=c1)
    ui.kpi("Registros que coinciden", len(df), "con la búsqueda y los filtros actuales" if hay_filtro else "sin filtros activos", contenedor=c2)
    ui.explicacion(f"Base «{disponibles[clave][0]}» tal como la ve tu usuario (las reglas de seguridad de Supabase ya filtraron lo que no puedes ver).",
                   "Cuenta las filas que cumplen los filtros elegidos (cada filtro revisa solo su propia columna) y la búsqueda por nombre o ID.",
                   "En «Personas» cada fila es una persona única; en «Registros históricos» cada fila es una vinculación histórica, "
                   "por lo que una persona puede aparecer varias veces.")
    if df.empty:
        ui.vacio("No hay registros con esos filtros. Quita alguno o pulsa «Limpiar filtros».")
        return
    cols = [c for c in COLS_VISTA[clave] if c in df.columns]
    vista = df.head(MAX_FILAS)
    if len(df) > MAX_FILAS:
        ui.nota(f"Se muestran las primeras {MAX_FILAS:,} filas de {len(df):,}. Afina los filtros o exporta para ver todas.")
    idx = ui.tabla(vista, cols, altura=520, key=f"explorador_tabla_{clave}", seleccionable=clave in ("personas", "historicos")
                   and sesion.puede("personas", "view"), fechas=("fecha_registro", "Fecha", "fecha_cierre", "fecha_vinculacion", "fecha_colocacion"))
    if idx is not None and "id_persona_maestro" in vista.columns:
        fila = vista.iloc[idx]
        if st.button(f"Abrir ficha de {fila.get('nombre', fila['id_persona_maestro'])}", key=f"explorador_ficha_{clave}"):
            ficha.dialogo(str(fila["id_persona_maestro"]))
    ui.boton_exportar(sesion, "explorador", df[cols], f"explorador_{clave}", f"explorador_{clave}")
