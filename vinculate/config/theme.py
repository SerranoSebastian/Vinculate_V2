"""Sistema visual de Vincúlate v2: paleta institucional SEDECO Tlaxcala, CSS y tema de gráficas.

El CSS se mantiene corto y se apoya en el tema nativo de Streamlit (.streamlit/config.toml)
en lugar de forzar estilos internos de BaseWeb, para no romperse con cada versión de Streamlit.
"""
from __future__ import annotations

import streamlit as st

from ..core.constantes import ESCALA_SEDECO, PALETA_SEDECO

GUINDA, GUINDA_2, GUINDA_OSCURO = "#AF2140", "#922542", "#62182F"
DORADO, BEIGE = "#D0B786", "#F2E6D3"
TINTA, TINTA_SUAVE = "#1A1A1A", "#5B5148"
COLOR_OK, COLOR_AVISO, COLOR_ERROR = "#2E7D32", "#B26A00", "#B3261E"

_CSS = f"""
<style>
:root {{
  --guinda: {GUINDA}; --guinda-2: {GUINDA_2}; --guinda-osc: {GUINDA_OSCURO};
  --dorado: {DORADO}; --beige: {BEIGE}; --tinta: {TINTA}; --tinta-suave: {TINTA_SUAVE};
}}
.stApp {{ background: linear-gradient(135deg, #FFFFFF 0%, #FBF7F1 60%, #F6EEE1 100%); }}
[data-testid="stSidebar"] {{ background: linear-gradient(180deg, {GUINDA_OSCURO} 0%, #7B1D39 55%, {GUINDA_2} 100%);
  border-right: 1px solid rgba(208,183,134,.6); }}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3,
[data-testid="stSidebar"] p, [data-testid="stSidebar"] label, [data-testid="stSidebar"] span,
[data-testid="stSidebar"] small, [data-testid="stSidebar"] a {{ color: #FFFFFF !important; }}
[data-testid="stSidebar"] hr {{ border-color: rgba(242,230,211,.35) !important; }}
[data-testid="stSidebar"] input {{ color: {TINTA} !important; }}
[data-testid="stSidebar"] .stButton > button, [data-testid="stSidebar"] button[data-testid="stPopoverButton"],
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] {{
  background: rgba(255,255,255,.12) !important; border: 1px solid rgba(242,230,211,.55) !important; color: #FFFFFF !important; }}
[data-testid="stSidebar"] .stButton > button:hover, [data-testid="stSidebar"] button[data-testid="stPopoverButton"]:hover {{
  background: rgba(255,255,255,.24) !important; border-color: {DORADO} !important; }}
[data-testid="stSidebar"] [data-testid="stFormSubmitButton"] > button {{ background: #FFFFFF !important; color: {GUINDA_OSCURO} !important; }}
h1, h2, h3 {{ color: {GUINDA_OSCURO}; font-weight: 800; letter-spacing: -.01em; }}
.vc-encabezado {{ border-left: 6px solid {GUINDA}; padding: .15rem 0 .15rem 1rem; margin: .2rem 0 1.1rem; }}
.vc-encabezado h1 {{ margin: 0; font-size: 1.85rem; }}
.vc-encabezado p {{ margin: .25rem 0 0; color: var(--tinta-suave); font-size: 1rem; }}
.vc-kpi-etiqueta {{ font-size: .86rem; color: var(--tinta-suave); font-weight: 600; margin-bottom: .1rem; }}
.vc-kpi-valor {{ font-size: 2rem; font-weight: 800; color: {GUINDA}; line-height: 1.1; }}
.vc-kpi-valor.vc-nd {{ font-size: 1.05rem; color: var(--tinta-suave); font-weight: 600; padding: .55rem 0; }}
.vc-kpi-ayuda {{ font-size: .78rem; color: var(--tinta-suave); margin-top: .15rem; }}
[data-testid="stVerticalBlockBorderWrapper"] {{ border-color: rgba(208,183,134,.75) !important; background: rgba(255,255,255,.88); }}
.vc-chip {{ display: inline-block; padding: .1rem .55rem; border-radius: 999px; font-size: .75rem; font-weight: 700;
  border: 1px solid {DORADO}; background: {BEIGE}; color: {GUINDA_OSCURO}; margin-right: .3rem; }}
.vc-chip.est {{ background: #FFF4DB; border-color: #E0B040; color: #7A5200; }}
.vc-chip.ok {{ background: #E7F4E8; border-color: #8CC28F; color: #1F5E24; }}
.vc-chip.no {{ background: #FBE9E7; border-color: #E0A39C; color: #8C1D18; }}
.vc-nota {{ font-size: .86rem; color: var(--tinta-suave); }}
.vc-portada {{ text-align:center; padding: 1.6rem 1rem .4rem; }}
.vc-portada h1 {{ font-size: 2.6rem; letter-spacing: .08em; color: {GUINDA}; margin: .6rem 0 0; }}
.vc-portada p {{ color: var(--tinta-suave); margin: .2rem 0 0; }}
@media (prefers-reduced-motion: reduce) {{ * {{ animation: none !important; transition: none !important; }} }}
</style>
"""


def aplicar_estilos() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def tema_grafica(fig, alto: int | None = None):
    """Aplica la identidad visual a una figura de Plotly."""
    fig.update_layout(
        template="plotly_white", colorway=PALETA_SEDECO, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font={"color": TINTA, "size": 13}, title_font={"color": GUINDA_OSCURO, "size": 16},
        margin={"l": 10, "r": 10, "t": 50, "b": 10},
        hoverlabel={"bgcolor": "#FFFFFF", "bordercolor": DORADO, "font_color": TINTA},
        legend={"font": {"color": TINTA}},
    )
    if alto:
        fig.update_layout(height=alto)
    fig.update_xaxes(gridcolor="rgba(208,183,134,.38)", linecolor="#8A6F58", zerolinecolor=DORADO)
    fig.update_yaxes(gridcolor="rgba(208,183,134,.38)", linecolor="#8A6F58", zerolinecolor=DORADO)
    fig.update_coloraxes(colorbar={"tickfont": {"color": TINTA}})
    return fig


__all__ = ["aplicar_estilos", "tema_grafica", "PALETA_SEDECO", "ESCALA_SEDECO", "GUINDA", "DORADO", "BEIGE"]
