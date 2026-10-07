"""Búsqueda global: personas, vacantes y seguimientos que coinciden con un texto."""
from __future__ import annotations

import streamlit as st

from ..auth.sesion import actual
from ..components import ui
from ..services import busqueda
from . import ficha

TITULOS = {"personas": "👥 Personas", "vacantes": "💼 Vacantes", "vinculaciones": "🔗 Seguimientos"}
CLAVE_TEXTO = "busqueda_texto"


@ui.protegido
def render() -> None:
    sesion = actual()
    ui.encabezado("Búsqueda global", "Encuentra una persona, empresa, vacante o seguimiento desde un solo lugar.", "🔍")
    texto = st.text_input("Buscar", key=CLAVE_TEXTO, placeholder="Nombre, ID (PER-0001, VAC-0001…), correo, empresa, carrera…")
    if not texto.strip():
        ui.vacio("Escribe al menos dos letras. Se buscan todas las palabras que escribas, sin importar acentos ni mayúsculas.")
        return
    resultados = busqueda.buscar(sesion, texto)
    if not resultados:
        ui.vacio("Escribe al menos dos letras para buscar, o tu perfil no tiene acceso a ninguna base.")
        return
    total = sum(len(df) for df in resultados.values())
    if total == 0:
        ui.vacio(f"No se encontró nada para «{texto.strip()}».")
        return
    ui.nota(f"{total} resultado(s). Se muestran como máximo {busqueda.LIMITE_POR_TIPO} por categoría.")
    for tipo, df in resultados.items():
        if df.empty:
            continue
        with st.container(border=True):
            st.markdown(f"**{TITULOS[tipo]}** · {len(df)}")
            idx = ui.tabla(df, altura=min(300, 60 + 36 * len(df)), key=f"busq_{tipo}",
                           seleccionable=("id_persona_maestro" in df.columns), fechas=("Fecha", "fecha_vinculacion", "fecha_registro"))
            if idx is not None:
                fila = df.iloc[idx]
                etiqueta = fila.get("nombre") or fila.get("nombre_persona") or fila["id_persona_maestro"]
                if st.button(f"Abrir ficha de {etiqueta}", key=f"busq_ficha_{tipo}"):
                    ficha.dialogo(str(fila["id_persona_maestro"]))
