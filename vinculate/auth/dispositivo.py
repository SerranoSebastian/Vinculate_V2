"""Identificador de equipo para servidor compartido (decisión D2).

En Streamlit Cloud el servidor es uno solo para todos, así que el ID de equipo
no puede vivir en un archivo del servidor (como en la v5). Ahora vive en el
NAVEGADOR (`vinculate_device`: UUID aleatorio en localStorage y cookie). Un
pequeño script lo entrega al servidor en la URL (?dv=<uuid>, se borra al
instante); el servidor lo guarda en la sesión, lo registra como equipo del
usuario y lo envía a Supabase en el encabezado `x-device-id` (V002, opcional,
lo valida en RLS).

Es un control SUAVE: identifica un navegador, no lo autentica. La defensa
principal siguen siendo el inicio de sesión y los permisos.
"""
from __future__ import annotations

import re
import uuid

COOKIE = "vinculate_device"
PARAM_RECARGA = "dv"          # el navegador entrega aquí su ID: ?dv=<uuid>
_CLAVE_SESION = "_device_id"  # ID ya aceptado, guardado en la sesión de Streamlit
_UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")

# Corre en el iframe del componente (mismo origen que la app). Busca el ID del equipo en localStorage o en la cookie
# del navegador (o lo crea), lo guarda en ambos y recarga la página padre con ?dv=<ID>. No depende de que el
# servidor reciba cookies: en Streamlit Cloud no siempre las recibe.
_JS_ENTREGAR_ID = """
<script>
(function () {
  try {
    var nombre = '%(cookie)s', param = '%(param)s', pw = window.parent, doc = pw.document;
    var uuidRe = /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/;
    var id = null;
    try { id = pw.localStorage.getItem(nombre); } catch (e) {}
    if (!id || !uuidRe.test(id)) {
      var m = doc.cookie.match('(?:^|; )' + nombre + '=([^;]*)');
      id = m ? decodeURIComponent(m[1]) : null;
    }
    if (!id || !uuidRe.test(id)) {
      id = (window.crypto && crypto.randomUUID) ? crypto.randomUUID() :
        'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
          var r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8); return v.toString(16); });
    }
    try { pw.localStorage.setItem(nombre, id); } catch (e) {}
    try {
      var seguro = pw.location.protocol === 'https:' ? '; Secure' : '';
      doc.cookie = nombre + '=' + encodeURIComponent(id) + '; Max-Age=157680000; Path=/; SameSite=Lax' + seguro;
    } catch (e) {}
    var u = new URL(pw.location.href);
    if (u.searchParams.get(param) !== id) {
      u.searchParams.set(param, id);
      // El iframe del componente está en un sandbox que NO puede navegar a su padre. Un <script> insertado
      // en el documento padre (mismo origen) corre con los permisos del padre y sí puede recargarlo.
      var s = doc.createElement('script');
      s.textContent = 'window.location.replace(' + JSON.stringify(u.toString()) + ');';
      doc.head.appendChild(s);
    }
  } catch (e) { /* sin acceso al documento padre: queda el botón de continuar sin identificar */ }
})();
</script>
"""


def es_id_valido(valor: str | None) -> bool:
    return isinstance(valor, str) and bool(_UUID_RE.match(valor))


def leer_cookie() -> str | None:
    """Cookie del navegador tal como la ve el servidor, o None. Nunca lanza excepciones."""
    try:
        import streamlit as st

        valor = st.context.cookies.get(COOKIE)
    except Exception:  # noqa: BLE001
        return None
    return valor if es_id_valido(valor) else None


def _leer_parametro() -> str | None:
    try:
        import streamlit as st

        valor = st.query_params.get(PARAM_RECARGA)
    except Exception:  # noqa: BLE001
        return None
    return valor if es_id_valido(valor) else None


def id_dispositivo() -> str | None:
    """ID del equipo (navegador) o None si aún no existe. Orden: sesión → pruebas → cookie → parámetro."""
    try:
        import streamlit as st

        for clave in (_CLAVE_SESION, "_device_id_forzado"):  # el segundo lo usan las pruebas automáticas
            valor = st.session_state.get(clave)
            if valor and es_id_valido(valor):
                return valor
    except Exception:  # noqa: BLE001
        pass
    return leer_cookie() or _leer_parametro()


def asegurar_dispositivo() -> str:
    """Devuelve el ID del equipo; si aún no se conoce, lo pide al navegador (que lo trae en la URL) y recarga una vez.

    Debe llamarse antes de mostrar el login. Nunca deja un callejón sin salida: si el navegador no puede
    entregar el ID, ofrece continuar con un identificador de esta sesión (el equipo queda como pendiente).
    """
    import streamlit as st
    import streamlit.components.v1 as componentes

    did = id_dispositivo()
    if did:
        st.session_state[_CLAVE_SESION] = did
        if PARAM_RECARGA in st.query_params:
            try:
                del st.query_params[PARAM_RECARGA]
            except Exception:  # noqa: BLE001
                pass
        return did

    if PARAM_RECARGA in st.query_params:  # llegó algo, pero no es un ID válido: se descarta y se vuelve a pedir
        try:
            del st.query_params[PARAM_RECARGA]
        except Exception:  # noqa: BLE001
            pass

    componentes.html(_JS_ENTREGAR_ID % {"cookie": COOKIE, "param": PARAM_RECARGA}, height=0)
    st.caption("Preparando este equipo… Si esta pantalla no avanza en unos segundos, usa el botón de abajo.")
    if st.button("Continuar sin identificar este equipo", key="_dv_continuar"):
        st.session_state[_CLAVE_SESION] = nuevo_id_aleatorio()
        st.rerun()
    st.caption(
        "Si continúas así, este equipo se registra como pendiente cada vez que entres desde un navegador distinto "
        "y un administrador tendrá que autorizarlo."
    )
    st.stop()


def nuevo_id_aleatorio() -> str:
    return str(uuid.uuid4())


def describir_navegador(user_agent: str | None) -> tuple[str, str]:
    """(navegador, sistema) legibles a partir del User-Agent. Sin dependencias externas."""
    ua = user_agent or ""
    if not ua:
        return "Navegador desconocido", "Sistema desconocido"
    so = "Sistema desconocido"
    for patron, nombre in [("Windows NT 10", "Windows 10/11"), ("Windows", "Windows"), ("Android", "Android"),
                           ("iPhone", "iOS"), ("iPad", "iPadOS"), ("Mac OS X", "macOS"), ("CrOS", "ChromeOS"),
                           ("Linux", "Linux")]:
        if patron in ua:
            so = nombre
            break
    nav = "Navegador desconocido"
    for patron, nombre in [("Edg/", "Edge"), ("OPR/", "Opera"), ("Firefox/", "Firefox"),
                           ("Chrome/", "Chrome"), ("Safari/", "Safari")]:
        if patron in ua:
            nav = nombre
            break
    return nav, so
