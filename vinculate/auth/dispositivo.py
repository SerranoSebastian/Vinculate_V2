"""Identificador de equipo para servidor compartido (decisión D2).

En Streamlit Cloud el servidor es uno solo para todos, así que el ID de equipo
no puede vivir en un archivo del servidor (como en la v5). Ahora vive en una
cookie del NAVEGADOR (`vinculate_device`, UUID aleatorio, ~5 años). El servidor
la lee con st.context.cookies, la guarda como equipo del usuario y la envía a
Supabase en el encabezado `x-device-id`, donde (V002, opcional) RLS la valida.

Es un control SUAVE: identifica un navegador, no lo autentica. La defensa
principal siguen siendo el inicio de sesión y los permisos.
"""
from __future__ import annotations

import re
import uuid

COOKIE = "vinculate_device"
PARAM_RECARGA = "dv"
_UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")

_JS_CREAR_COOKIE = """
<script>
(function () {
  try {
    var nombre = '%(cookie)s', doc = window.parent.document;
    var m = doc.cookie.match('(?:^|; )' + nombre + '=([^;]*)');
    var id = m ? decodeURIComponent(m[1]) : null;
    if (!id) {
      id = (window.crypto && crypto.randomUUID) ? crypto.randomUUID() :
        'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
          var r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8); return v.toString(16); });
      var seguro = window.parent.location.protocol === 'https:' ? '; Secure' : '';
      doc.cookie = nombre + '=' + encodeURIComponent(id) + '; Max-Age=157680000; Path=/; SameSite=Lax' + seguro;
    }
    var u = new URL(window.parent.location.href);
    if (u.searchParams.get('%(param)s') !== '1') {
      u.searchParams.set('%(param)s', '1');
      // El iframe del componente está en un sandbox que NO puede navegar a su padre (Chrome lo bloquea). Un <script>
      // insertado en el documento padre (mismo origen) corre con los permisos del padre y sí puede recargarlo.
      var s = doc.createElement('script');
      s.textContent = 'window.location.replace(' + JSON.stringify(u.toString()) + ');';
      doc.head.appendChild(s);
    }
  } catch (e) { /* sin acceso al documento padre: el servidor mostrará el aviso */ }
})();
</script>
"""


def es_id_valido(valor: str | None) -> bool:
    return bool(valor and _UUID_RE.match(valor))


def leer_cookie() -> str | None:
    """Cookie del navegador, o None. Nunca lanza excepciones."""
    try:
        import streamlit as st

        valor = st.context.cookies.get(COOKIE)
    except Exception:  # noqa: BLE001
        return None
    return valor if es_id_valido(valor) else None


def id_dispositivo() -> str | None:
    """ID del equipo (navegador) o None si aún no existe."""
    try:
        import streamlit as st

        forzado = st.session_state.get("_device_id_forzado")  # pruebas automáticas
    except Exception:  # noqa: BLE001
        forzado = None
    if forzado and es_id_valido(forzado):
        return forzado
    return leer_cookie()


def asegurar_dispositivo() -> str:
    """Devuelve el ID del equipo; si el navegador aún no tiene cookie, la crea y recarga una vez.

    Debe llamarse antes de mostrar el login. Si el navegador bloquea cookies,
    muestra un aviso en lugar de entrar en un ciclo de recargas.
    """
    import streamlit as st
    import streamlit.components.v1 as componentes

    did = id_dispositivo()
    if did:
        if st.query_params.get(PARAM_RECARGA):
            try:
                del st.query_params[PARAM_RECARGA]
            except Exception:  # noqa: BLE001
                pass
        return did

    if st.query_params.get(PARAM_RECARGA) == "1":
        st.error(
            "Tu navegador no permite guardar cookies, y Vincúlate las necesita para identificar este equipo. "
            "Habilita las cookies para este sitio (o sal del modo incógnito) y recarga la página."
        )
        st.stop()

    componentes.html(_JS_CREAR_COOKIE % {"cookie": COOKIE, "param": PARAM_RECARGA}, height=0)
    st.caption("Preparando este equipo… Si esta pantalla no avanza en unos segundos, recarga la página (F5).")
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
