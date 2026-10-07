"""Centro de avisos: campana con las prioridades vencidas y avisos emergentes (toasts) periódicos."""
from __future__ import annotations

import streamlit as st

from ..auth.sesion import actual
from ..repositories.errores import ErrorDatos
from ..services import prioridades

ICONO = {"urgente": "🔴", "alta": "🟠", "normal": "🔵"}
REFRESCO = "60s"


@st.fragment(run_every=REFRESCO)
def campana() -> None:
    """Se actualiza sola cada minuto (solo este fragmento, no toda la página)."""
    sesion = actual()
    if sesion is None or not sesion.puede("prioridades", "view"):
        return
    try:
        pendientes = prioridades.pendientes(sesion)
        for fila in prioridades.para_toast(sesion, pendientes_ya=pendientes):
            st.toast(f"**{fila.get('title') or 'Aviso'}**" + (f"\n\n{fila['description']}" if fila.get("description") else ""),
                     icon=ICONO.get(fila.get("priority_level"), "🔔"))
    except ErrorDatos:
        return  # un fallo de red o una sesión vencida lo resuelve el flujo principal; la campana no interrumpe
    etiqueta = f"🔔 {len(pendientes)}" if pendientes else "🔔"
    with st.popover(etiqueta, help="Avisos y prioridades pendientes", width="stretch"):
        if not pendientes:
            st.caption("No tienes avisos pendientes.")
        for fila in pendientes[:8]:
            st.markdown(f"{ICONO.get(fila.get('priority_level'), '🔔')} **{fila.get('title') or 'Aviso'}**")
            detalle = " · ".join(x for x in (fila.get("entity_type"), fila.get("entity_id")) if x)
            if detalle:
                st.caption(detalle)
            if fila.get("description"):
                st.write(fila["description"])
            if sesion.puede("prioridades", "edit"):
                if st.button("Marcar como atendida", key=f"av_cerrar_{fila['id']}"):
                    try:
                        prioridades.cerrar(sesion, fila["id"], fila.get("title") or "")
                        st.rerun(scope="app")
                    except ErrorDatos as exc:
                        st.error(str(exc))
            st.divider()
        if len(pendientes) > 8:
            st.caption(f"Y {len(pendientes) - 8} más en Administración → Prioridades.")
