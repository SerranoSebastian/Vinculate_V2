"""Explorador general: cualquier tabla a la que el usuario tenga acceso, con búsqueda de texto y exportación."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from ..auth.sesion import actual
from ..components import ui
from ..core.texto import normalizar_texto
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


def _buscar(df: pd.DataFrame, texto: str) -> pd.DataFrame:
    terminos = [t for t in normalizar_texto(texto).split(" ") if t]
    if not terminos or df.empty:
        return df
    pajar = df.astype(str).apply(lambda s: s.map(normalizar_texto)).agg(" ".join, axis=1)
    mask = pd.Series(True, index=df.index)
    for t in terminos:
        mask &= pajar.str.contains(t, regex=False)
    return df[mask]


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
    texto = st.text_input("Buscar", key="explorador_texto", placeholder="Nombre, ID, empresa, municipio, carrera… (todas las palabras deben aparecer)")
    df = _base(sesion, clave)
    total = len(df)
    df = _buscar(df, texto).reset_index(drop=True)

    c1, c2 = st.columns(2)
    ui.kpi("Registros en la base", total, contenedor=c1)
    ui.kpi("Registros que coinciden", len(df), "con la búsqueda actual" if texto.strip() else "sin búsqueda activa", contenedor=c2)
    ui.explicacion(f"Base «{disponibles[clave][0]}» tal como la ve tu usuario (las reglas de seguridad de Supabase ya filtraron lo que no puedes ver).",
                   "Cuenta las filas que cumplen la búsqueda de texto.",
                   "En «Personas» cada fila es una persona única; en «Registros históricos» cada fila es una vinculación histórica, "
                   "por lo que una persona puede aparecer varias veces.")
    if df.empty:
        ui.vacio("No hay registros que coincidan con la búsqueda.")
        return
    cols = [c for c in COLS_VISTA[clave] if c in df.columns]
    vista = df.head(MAX_FILAS)
    if len(df) > MAX_FILAS:
        ui.nota(f"Se muestran las primeras {MAX_FILAS:,} filas de {len(df):,}. Afina la búsqueda o exporta para ver todas.")
    idx = ui.tabla(vista, cols, altura=520, key=f"explorador_tabla_{clave}", seleccionable=clave in ("personas", "historicos")
                   and sesion.puede("personas", "view"), fechas=("fecha_registro", "Fecha", "fecha_cierre", "fecha_vinculacion", "fecha_colocacion"))
    if idx is not None and "id_persona_maestro" in vista.columns:
        fila = vista.iloc[idx]
        if st.button(f"Abrir ficha de {fila.get('nombre', fila['id_persona_maestro'])}", key=f"explorador_ficha_{clave}"):
            ficha.dialogo(str(fila["id_persona_maestro"]))
    ui.boton_exportar(sesion, "explorador", df[cols], f"explorador_{clave}", f"explorador_{clave}")
