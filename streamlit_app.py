"""Vincúlate SEDECO v2 — archivo principal (en Streamlit Cloud: «Main file path» = streamlit_app.py)."""
from __future__ import annotations

import time

import streamlit as st

from vinculate import navegacion
from vinculate.auth import dispositivo, servicio
from vinculate.auth.sesion import Sesion, actual
from vinculate.components import avisos, ui
from vinculate.config.settings import LOGO_HORIZONTAL, LOGO_PORTADA, VERSION_APP, ConfiguracionInvalida, supabase_cfg
from vinculate.config.theme import aplicar_estilos
from vinculate.repositories.errores import SesionExpirada
from vinculate.services import datos
from vinculate.vistas import administracion, busqueda, explorador, inicio, mapa, personas, ridet, vacantes, vinculaciones

st.set_page_config(page_title="Vincúlate SEDECO", page_icon="🤝", layout="wide", initial_sidebar_state="expanded")
aplicar_estilos()

INTENTOS_MAX = 5
ESPERA_S = 60


# ------------------------------------------------------------------- pantallas
def _pantalla_configuracion(exc: Exception) -> None:
    st.markdown('<div class="vc-portada"><h1>VINCÚLATE</h1><p>SEDECO Tlaxcala</p></div>', unsafe_allow_html=True)
    st.error(str(exc), icon="⚙️")
    st.markdown("**Cómo configurarlo.** En Streamlit Cloud: *App settings → Secrets*. En tu computadora: `.streamlit/secrets.toml`.")
    st.code('[supabase]\nurl = "https://TU-PROYECTO.supabase.co"\nkey = "TU_LLAVE_PUBLICA_ANON_O_PUBLISHABLE"', language="toml")
    st.caption("Usa solamente la llave pública. La llave service_role / secret NO debe ponerse aquí: la aplicación se niega a arrancar con ella.")


def _login() -> None:
    dispositivo.asegurar_dispositivo()
    _, centro, _ = st.columns([1, 1.4, 1])
    with centro:
        if LOGO_PORTADA.exists():
            st.image(str(LOGO_PORTADA), width="stretch")
        st.markdown('<div class="vc-portada"><h1>VINCÚLATE</h1><p>Plataforma Integral de Vinculación Laboral · SEDECO Tlaxcala</p></div>',
                    unsafe_allow_html=True)
        espera = st.session_state.get("_bloqueo_hasta", 0) - time.monotonic()
        if espera > 0:
            st.warning(f"Demasiados intentos. Espera {int(espera) + 1} segundos antes de volver a intentar.")
            return
        with st.form("login"):
            correo = st.text_input("Correo", autocomplete="username")
            clave = st.text_input("Contraseña", type="password", autocomplete="current-password")
            entrar = st.form_submit_button("Entrar", type="primary", width="stretch")
        if entrar:
            try:
                servicio.iniciar_sesion(correo, clave)
                st.session_state.pop("_intentos", None)
                st.rerun()
            except (servicio.AccesoDenegado, ValueError) as exc:
                n = st.session_state.get("_intentos", 0) + 1
                st.session_state["_intentos"] = n
                if n >= INTENTOS_MAX:
                    st.session_state["_bloqueo_hasta"] = time.monotonic() + ESPERA_S
                    st.session_state["_intentos"] = 0
                    st.rerun()  # la siguiente ejecución muestra el aviso de espera en lugar del formulario
                st.error(str(exc))
            except Exception:  # noqa: BLE001
                st.error("No se pudo iniciar sesión. Revisa tu conexión e inténtalo de nuevo.")
        st.caption(f"Versión {VERSION_APP}")


# ------------------------------------------------------------------ navegación
def _paginas(s: Sesion) -> dict[str, st.Page]:
    def pagina(clave, funcion, titulo, icono):
        return clave, st.Page(funcion, title=titulo, icon=icono, url_path=clave)

    def alguna(modulo):
        return s.puede_alguna(modulo, ("view", "create", "edit", "delete"))

    catalogo: list[tuple[str, str, tuple]] = []  # (sección, clave, (clave, página))
    if s.puede("inicio", "view"):
        catalogo.append(("Panorama", "inicio", pagina("inicio", inicio.render, "Inicio", "📊")))
    if s.puede("ridet", "view"):
        catalogo.append(("Panorama", "mapa", pagina("mapa", mapa.render, "Mapa territorial", "🗺️")))
        catalogo.append(("Panorama", "ridet", pagina("ridet", ridet.render, "RIDET", "🧭")))
    for modulo, funcion, titulo, icono in (("personas", personas.render, "Personas", "👥"), ("vacantes", vacantes.render, "Vacantes y empresas", "💼"),
                                          ("vinculaciones", vinculaciones.render, "Vinculaciones", "🔗")):
        if alguna(modulo):
            catalogo.append(("Operación", modulo, pagina(modulo, funcion, titulo, icono)))
    if s.puede("explorador", "view"):
        catalogo.append(("Consulta", "explorador", pagina("explorador", explorador.render, "Explorador", "🔎")))
    if any(s.puede(m, "view") for m in ("personas", "vacantes", "vinculaciones")):
        catalogo.append(("Consulta", "busqueda", pagina("busqueda", busqueda.render, "Búsqueda", "🔍")))
    if administracion.hay_algo_que_administrar(s):
        catalogo.append(("Sistema", "administracion", pagina("administracion", administracion.render, "Administración", "⚙️")))
    catalogo.append(("Sistema", "cuenta", pagina("cuenta", administracion.render_cuenta, "Mi cuenta", "👤")))

    secciones: dict[str, list] = {}
    for seccion, _, (_, pag) in catalogo:
        secciones.setdefault(seccion, []).append(pag)
    navegacion.registrar({clave: pag for _, clave, (_, pag) in catalogo})
    return secciones


def _barra_lateral(s: Sesion) -> None:
    with st.sidebar:
        if LOGO_HORIZONTAL.exists():
            st.image(str(LOGO_HORIZONTAL), width="stretch")
        st.markdown(f"**{s.nombre}**")
        st.caption("Administrador" if s.es_admin else "Colaborador")
    with st.sidebar.form("busqueda_global", border=False, clear_on_submit=True):
        c1, c2 = st.columns([4, 1])
        texto = c1.text_input("Buscar", placeholder="Buscar persona, empresa o ID", label_visibility="collapsed")
        ir = c2.form_submit_button("🔍")
    if ir and texto.strip() and navegacion.existe("busqueda"):
        st.session_state["busqueda_texto"] = texto.strip()
        navegacion.ir_a("busqueda")
    with st.sidebar:
        avisos.campana()
        if st.button("🔄 Actualizar datos y permisos", width="stretch", key="btn_actualizar"):
            datos.invalidar()
            st.cache_data.clear()
            servicio.revalidar(forzar=True)
            st.rerun()
        if st.button("Cerrar sesión", width="stretch", key="btn_salir"):
            servicio.cerrar_sesion()
            st.rerun()
        st.caption(f"Versión {VERSION_APP} · datos en Supabase")


# ------------------------------------------------------------------- principal
def main() -> None:
    try:
        supabase_cfg()
    except ConfiguracionInvalida as exc:
        _pantalla_configuracion(exc)
        return
    if actual() is None:
        _login()
        return
    try:
        sesion = servicio.revalidar()
    except servicio.AccesoDenegado as exc:
        servicio.cerrar_sesion()
        st.warning(str(exc))
        _login()
        return
    except SesionExpirada:
        servicio.cerrar_sesion()
        st.warning("Tu sesión expiró. Vuelve a iniciar sesión.")
        _login()
        return
    try:
        pagina = st.navigation(_paginas(sesion), position="sidebar")
        _barra_lateral(sesion)
        pagina.run()
    except SesionExpirada:
        servicio.cerrar_sesion()
        st.warning("Tu sesión expiró. Vuelve a iniciar sesión.")
        st.rerun()


main()
