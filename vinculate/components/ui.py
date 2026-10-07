"""Componentes de interfaz reutilizables (sin lógica de negocio)."""
from __future__ import annotations

import functools
import logging
from html import escape

import pandas as pd
import streamlit as st

from ..auth.sesion import Sesion
from ..core.constantes import SIN_DATO
from ..core.texto import texto_vacio
from ..repositories.errores import ErrorDatos, SesionExpirada
from ..services import respaldos
from ..services import guardado
from ..services.guardado import Resultado


# ------------------------------------------------------------------ formato
def fmt_num(valor, decimales: int = 0) -> str:
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return "No disponible"
    try:
        return f"{float(valor):,.{decimales}f}"
    except (TypeError, ValueError):
        return str(valor)


def fmt_pct(parte, total, decimales: int = 1) -> str:
    return "No disponible" if not total else f"{parte / total * 100:.{decimales}f}%"


# --------------------------------------------------------------- estructura
def encabezado(titulo: str, subtitulo: str = "", icono: str = "") -> None:
    sub = f"<p>{escape(subtitulo)}</p>" if subtitulo else ""
    st.markdown(f'<div class="vc-encabezado"><h1>{escape((icono + " " if icono else "") + titulo)}</h1>{sub}</div>',
                unsafe_allow_html=True)


def kpi(etiqueta: str, valor, ayuda: str = "", *, contenedor=None, decimales: int = 0, no_disponible: bool = False) -> None:
    """Tarjeta de indicador. `valor=None` o `no_disponible=True` muestra 'No disponible' (nunca un 0 inventado)."""
    cont = contenedor if contenedor is not None else st
    with cont.container(border=True):
        nd = no_disponible or valor is None
        texto = "No disponible" if nd else (valor if isinstance(valor, str) else fmt_num(valor, decimales))
        clase = "vc-kpi-valor vc-nd" if nd else "vc-kpi-valor"
        ayuda_html = f'<div class="vc-kpi-ayuda">{escape(ayuda)}</div>' if ayuda else ""
        st.markdown(f'<div class="vc-kpi-etiqueta">{escape(etiqueta)}</div><div class="{clase}">{escape(str(texto))}</div>{ayuda_html}',
                    unsafe_allow_html=True)


def chip(texto: str, tipo: str = "") -> str:
    return f'<span class="vc-chip {tipo}">{escape(texto)}</span>'


def nota(texto: str) -> None:
    st.markdown(f'<div class="vc-nota">{escape(texto)}</div>', unsafe_allow_html=True)


def explicacion(fuente: str, significado: str, interpretacion: str) -> None:
    """Trazabilidad de cada indicador: de dónde sale, qué mide y cómo leerlo."""
    with st.expander("ℹ️ Fuente, significado e interpretación"):
        st.markdown(f"**Fuente:** {fuente}  \n**Qué significa:** {significado}  \n**Cómo se interpreta:** {interpretacion}")


def vacio(mensaje: str = "No hay información para mostrar con los filtros actuales.") -> None:
    st.info(mensaje, icon="📭")


def mostrar_resultado(res: Resultado) -> None:
    """Muestra el resultado de un guardado con toda la verdad: guardados, omitidos, errores y avisos."""
    if res.ok:
        st.success(res.mensaje, icon="✅")
    else:
        st.error(res.mensaje, icon="⚠️")
    for aviso in res.avisos:
        st.warning(aviso)
    if res.errores:
        st.dataframe(pd.DataFrame(res.errores).rename(columns={"fila": "Fila", "campo": "Campo", "error": "Problema"}),
                     hide_index=True, width="stretch")


def mostrar_error(exc: Exception) -> None:
    """Error de datos entendible; nunca un traceback."""
    if isinstance(exc, ErrorDatos):
        st.error(str(exc), icon="⚠️")
    else:
        st.error("Ocurrió un problema inesperado. Intenta de nuevo; si persiste, avisa a un administrador.", icon="⚠️")


# ------------------------------------------------------------------- tablas
def _texto_fecha(v) -> str:
    if texto_vacio(v):
        return SIN_DATO
    f = pd.to_datetime(v, errors="coerce")
    return SIN_DATO if pd.isna(f) else f.strftime("%d/%m/%Y")


def preparar_tabla(df: pd.DataFrame, columnas: list[str] | None = None, nombres: dict[str, str] | None = None,
                   fechas: tuple[str, ...] = ()) -> pd.DataFrame:
    """Copia lista para mostrar: sin NaN/None/NaT (se escribe «Información no disponible»)."""
    d = df[[c for c in (columnas or list(df.columns)) if c in df.columns]].copy()
    for c in d.columns:
        if c in fechas or pd.api.types.is_datetime64_any_dtype(d[c]):
            d[c] = d[c].map(_texto_fecha)
        elif pd.api.types.is_numeric_dtype(d[c]) and not d[c].isna().any():
            continue
        else:
            d[c] = d[c].map(lambda v: SIN_DATO if texto_vacio(v) else (str(int(v)) if isinstance(v, float) and v.is_integer() else str(v)))
    return d.rename(columns=nombres or {})


def tabla(df: pd.DataFrame, columnas: list[str] | None = None, nombres: dict[str, str] | None = None,
          fechas: tuple[str, ...] = (), altura: int | None = None, key: str | None = None,
          seleccionable: bool = False):
    """st.dataframe seguro. Con `seleccionable=True` devuelve el índice (posición) de la fila elegida o None."""
    if df is None or df.empty:
        vacio()
        return None
    d = preparar_tabla(df, columnas, nombres, fechas)
    extra = {"height": altura} if altura else {}  # height=None no es válido en Streamlit ≥1.5x
    if seleccionable:
        ev = st.dataframe(d, hide_index=True, width="stretch", key=key, on_select="rerun", selection_mode="single-row", **extra)
        filas = ev.selection.rows if ev and ev.selection else []
        return filas[0] if filas else None
    st.dataframe(d, hide_index=True, width="stretch", **extra)
    return None


# ----------------------------------------------------------- confirmaciones
@st.dialog("Confirmar acción")
def _dialogo_confirmar(clave: str, titulo: str, lineas: list[str], boton: str) -> None:
    st.markdown(f"**{titulo}**")
    for linea in lineas:
        st.markdown(f"- {linea}")
    entiendo = st.checkbox("Entiendo lo que va a pasar y quiero continuar.", key=f"_chk_{clave}")
    c1, c2 = st.columns(2)
    if c1.button("Cancelar", key=f"_cancel_{clave}", width="stretch"):
        st.rerun()
    if c2.button(boton, key=f"_ok_{clave}", type="primary", disabled=not entiendo, width="stretch"):
        st.session_state[f"_confirmado_{clave}"] = True
        st.rerun()


def pedir_confirmacion(clave: str, titulo: str, lineas: list[str], boton: str = "Confirmar") -> None:
    """Abre el cuadro de confirmación explícito para una acción destructiva."""
    _dialogo_confirmar(clave, titulo, lineas, boton)


def confirmado(clave: str) -> bool:
    """True UNA vez después de que la persona confirmó en el cuadro."""
    return bool(st.session_state.pop(f"_confirmado_{clave}", False))


# --------------------------------------------------------------- exportación
def boton_exportar(sesion: Sesion, modulo: str, df: pd.DataFrame, nombre: str, clave: str) -> None:
    """Exportación en dos pasos (preparar → descargar) para auditar UNA vez y respetar `<módulo>.export`."""
    if not sesion.puede(modulo, "export"):
        nota("Tu perfil no tiene permiso para exportar este módulo.")
        return
    if df is None or df.empty:
        return
    c1, c2 = st.columns([1, 2])
    formato = c1.segmented_control("Formato", ["csv", "xlsx"], default="csv", key=f"fmt_{clave}",
                                   label_visibility="collapsed") or "csv"
    llave = f"_exp_{clave}"
    listo = st.session_state.get(llave)
    if listo and listo.get("firma") != (len(df), formato, tuple(df.columns)):
        listo = None
    if c2.button("Preparar exportación", key=f"prep_{clave}"):
        try:
            datos, archivo, mime = respaldos.exportar_df(sesion, modulo, df, nombre, formato)
            st.session_state[llave] = {"datos": datos, "archivo": archivo, "mime": mime,
                                       "firma": (len(df), formato, tuple(df.columns))}
            listo = st.session_state[llave]
        except Exception as exc:  # noqa: BLE001
            mostrar_error(exc)
    if listo:
        st.download_button(f"⬇️ Descargar {listo['archivo']}", listo["datos"], listo["archivo"], listo["mime"],
                           key=f"dl_{clave}", width="stretch")


# ------------------------------------------------------- mensajes entre reruns
_FLASH = "_flash_resultado"


def flash(res: Resultado) -> None:
    """Guarda un resultado para mostrarlo tras el siguiente rerun (p. ej. después de guardar y refrescar listas)."""
    st.session_state[_FLASH] = res


def mostrar_flash() -> None:
    res = st.session_state.pop(_FLASH, None)
    if res is not None:
        mostrar_resultado(res)


# ----------------------------------------------------- deshacer / papelera
def bloque_deshacer(sesion: Sesion, tipo: str) -> None:
    """Permite deshacer la última carga de esta sesión (borra EXACTAMENTE lo que se acaba de insertar)."""
    carga = guardado.ultima_carga()
    if not carga or carga["tipo"] != tipo or not sesion.puede(tipo, "delete"):
        return
    clave = f"deshacer_{tipo}"
    with st.container(border=True):
        st.markdown(f"**Última carga de esta sesión:** {len(carga['ids'])} registro(s) nuevos.")
        if st.button("↩️ Deshacer esta carga", key=f"btn_{clave}"):
            pedir_confirmacion(clave, "Deshacer la última carga", [
                f"Se eliminarán los {len(carga['ids'])} registros que se guardaron en esa carga (y solo esos).",
                "Los registros que ya existían antes no se tocan.",
                "Si alguien editó esos registros después, también se eliminarán."], "Deshacer carga")
    if confirmado(clave):
        flash(guardado.deshacer_ultima_carga(sesion))
        st.rerun()


def bloque_papelera(sesion: Sesion, tipo: str) -> None:
    """Registros eliminados en esta sesión, con opción de restaurarlos (requiere permiso de alta)."""
    items = [(i, x) for i, x in enumerate(guardado.papelera()) if x["tipo"] == tipo]
    if not items:
        return
    with st.expander(f"🗑️ Papelera de esta sesión ({len(items)})"):
        nota("Solo vive mientras esta sesión siga abierta. Restaurar vuelve a crear el registro con su mismo ID.")
        for i, x in items:
            c1, c2 = st.columns([4, 1])
            c1.write(f"{x['id']} · eliminado a las {x['ts']}")
            if c2.button("Restaurar", key=f"rest_{tipo}_{i}_{x['id']}", disabled=not sesion.puede(tipo, "create")):
                flash(guardado.restaurar(sesion, i))
                st.rerun()


# ---------------------------------------------------------------- página segura
def protegido(funcion):
    """Evita que un error de datos muestre un traceback: lo traduce a un mensaje entendible.

    La sesión expirada sube al archivo principal, que cierra la sesión y pide iniciar de nuevo.
    """
    @functools.wraps(funcion)
    def envoltura(*args, **kwargs):
        try:
            return funcion(*args, **kwargs)
        except SesionExpirada:
            raise
        except ErrorDatos as exc:
            st.error(str(exc), icon="⚠️")
        except Exception:  # noqa: BLE001 — los saltos de Streamlit (rerun/stop) no son Exception
            logging.getLogger("vinculate").exception("Error inesperado en %s", funcion.__name__)
            st.error("Ocurrió un problema inesperado. Intenta de nuevo; si persiste, avisa a un administrador.", icon="⚠️")
    return envoltura
