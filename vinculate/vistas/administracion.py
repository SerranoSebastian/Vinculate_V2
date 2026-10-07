"""Administración: estado del sistema, usuarios, permisos, equipos, prioridades, auditoría y respaldos.

Cada apartado se muestra solo si el perfil tiene el permiso del módulo correspondiente; además, cada
servicio vuelve a exigirlo y la base (RLS + RPC de V001/V002) es quien decide en última instancia.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st

from ..auth import servicio as auth_servicio
from ..auth.sesion import Sesion, actual
from ..components import ui
from ..core.constantes import ACTIONS, MODULES, SIN_DATO
from ..repositories.admin import RepoAdmin
from ..repositories.errores import ErrorDatos
from ..services import datos, estado, prioridades, respaldos, usuarios
from ..services.guardado import ZONA, ahora_mx

APARTADOS = {
    "estado": ("🩺 Estado del sistema", "administracion", "view"),
    "usuarios": ("👤 Usuarios", "usuarios", "view"),
    "permisos": ("🔐 Permisos", "usuarios", "edit"),
    "equipos": ("💻 Computadoras", "dispositivos", "view"),
    "prioridades": ("⏰ Prioridades", "prioridades", "view"),
    "auditoria": ("🧾 Auditoría", "auditoria", "view"),
    "respaldos": ("💾 Respaldos e historial", "respaldos", "export"),
}


def hay_algo_que_administrar(sesion: Sesion) -> bool:
    return any(sesion.puede(m, a) for _, m, a in APARTADOS.values()) or sesion.puede("administracion", "view")


def _hora_mx(valor) -> str:
    """UTC de la base → hora de la Ciudad de México legible."""
    if not valor:
        return SIN_DATO
    try:
        dt = datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
    except ValueError:
        return str(valor)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(ZONA).strftime("%d/%m/%Y %H:%M")


def _etiqueta_cuenta(p: dict) -> str:
    return f"{p.get('display_name') or p.get('email')} — {p.get('email')}"


# --------------------------------------------------------------------- estado
def _estado(sesion: Sesion) -> None:
    ok, mensaje = estado.conexion(sesion)
    (st.success if ok else st.error)(("🟢 " if ok else "🔴 ") + mensaje)
    cont = estado.conteos(sesion)
    c = st.columns(3)
    ui.kpi("Vinculaciones históricas", cont["personas"], contenedor=c[0])
    ui.kpi("Vacantes", cont["vacantes"], contenedor=c[1])
    ui.kpi("Seguimientos con empresas", cont["vinculaciones"], contenedor=c[2])
    ui.nota("«No disponible» significa que tu perfil no puede consultar esa tabla o que la consulta falló; no es un cero.")

    st.markdown("##### Migraciones de la base de datos")
    migs = estado.migraciones(sesion)
    tabla = pd.DataFrame([{"Migración": m.clave, "Qué agrega": m.nombre,
                           "Estado": "✅ Aplicada" if m.aplicada else ("⏳ Pendiente" if m.aplicada is False else "➖ No verificable"),
                           "Cómo se detecta": m.detalle} for m in migs])
    st.dataframe(tabla, hide_index=True, width="stretch")
    ui.nota("Las migraciones están en supabase/migrations/. Se ejecutan a mano en el SQL Editor de Supabase (primero en un proyecto de prueba). "
            "Esta pantalla solo LEE el estado; nunca modifica el esquema.")

    st.markdown("##### Control de equipo en la base de datos")
    obligatorio = estado.equipo_obligatorio(sesion)
    if obligatorio is None:
        st.info("Este control requiere la migración V002. Mientras no esté aplicada, el equipo se registra y se autoriza desde la aplicación, "
                "pero la base no lo exige.")
    else:
        st.write("**Estado actual:** " + ("🔒 la base EXIGE un equipo autorizado" if obligatorio else "🔓 la base no exige equipo autorizado (solo lo valida la aplicación)"))
        ui.nota("Es un control suave: el identificador de equipo vive en el navegador y sirve para ordenar y revocar accesos, no para impedir "
                "que alguien con usuario, contraseña y conocimientos técnicos intente acceder desde otro navegador.")
        if sesion.es_admin:
            etiqueta = "Dejar de exigir equipo autorizado" if obligatorio else "Exigir equipo autorizado en la base"
            if st.button(etiqueta, key="adm_toggle_gate"):
                if obligatorio:
                    ui.pedir_confirmacion("gate", "Dejar de exigir equipo autorizado", [
                        "La base volverá a permitir leer y escribir datos sin comprobar el equipo.",
                        "La aplicación seguirá registrando equipos."], "Aplicar")
                else:
                    ui.pedir_confirmacion("gate", "Exigir equipo autorizado en la base", [
                        "Desde este momento la base rechazará lecturas y escrituras de cualquier equipo que no esté autorizado en Computadoras.",
                        "Antes de activarlo, autoriza TU equipo y los de tus colaboradores; si no, nadie verá datos.",
                        "Se puede revertir desde aquí o con una línea de SQL (está documentada en V002)."], "Exigir")
            if ui.confirmado("gate"):
                try:
                    estado.fijar_equipo_obligatorio(sesion, not obligatorio)
                    st.success("Control actualizado.")
                    st.rerun()
                except Exception as exc:  # noqa: BLE001
                    ui.mostrar_error(exc)


# ------------------------------------------------------------------- usuarios
def _alta_usuario(sesion: Sesion) -> None:
    with st.expander("➕ Dar de alta una cuenta"):
        ui.nota("El correo se guarda en minúsculas. La contraseña temporal debe tener entre 8 y 72 caracteres.")
        with st.form("adm_alta_usuario", clear_on_submit=False):
            nombre = st.text_input("Nombre para mostrar")
            correo = st.text_input("Correo del colaborador")
            c1, c2 = st.columns(2)
            p1 = c1.text_input("Contraseña temporal", type="password")
            p2 = c2.text_input("Repetir contraseña", type="password")
            enviar = st.form_submit_button("Crear cuenta", type="primary")
        if not enviar:
            return
        if not nombre.strip():
            st.error("Escribe el nombre del colaborador.")
        elif p1 != p2:
            st.error("Las contraseñas no coinciden.")
        else:
            try:
                usuarios.crear_colaborador(sesion, correo, p1, nombre)
                st.success("Cuenta creada. Ahora asígnale permisos en el apartado Permisos.")
            except Exception as exc:  # noqa: BLE001
                ui.mostrar_error(exc)


def _usuarios(sesion: Sesion) -> None:
    perfiles = usuarios.listar_perfiles(sesion)
    if perfiles:
        df = pd.DataFrame(perfiles)
        df["rol"] = df.get("role", "").map(usuarios.ETIQUETA_ROL).fillna(SIN_DATO)
        df["estado"] = df.get("status", "").map(usuarios.ETIQUETA_ESTADO).fillna(SIN_DATO)
        df["alta"] = df.get("created_at", "").map(_hora_mx)
        ui.tabla(df, ["display_name", "email", "rol", "estado", "alta"],
                 {"display_name": "Nombre", "email": "Correo", "rol": "Rol", "estado": "Estado", "alta": "Alta"}, altura=260)
    if sesion.puede("usuarios", "create"):
        _alta_usuario(sesion)
    if not perfiles or not sesion.puede("usuarios", "edit"):
        return
    etiquetas = {_etiqueta_cuenta(p): p for p in perfiles}
    elegido = st.selectbox("Administrar cuenta", list(etiquetas), key="adm_cuenta")
    fila = etiquetas[elegido]
    uid = str(fila["user_id"])
    st.markdown("###### Datos, rol y acceso")
    with st.form(f"adm_cuenta_{uid}"):
        c1, c2 = st.columns(2)
        nombre = c1.text_input("Nombre", value=fila.get("display_name") or "")
        correo = c2.text_input("Correo", value=fila.get("email") or "")
        rol = c1.selectbox("Rol", list(usuarios.ROLES), format_func=usuarios.ETIQUETA_ROL.get,
                           index=usuarios.ROLES.index(fila.get("role")) if fila.get("role") in usuarios.ROLES else 0)
        est = c2.selectbox("Estado", list(usuarios.ESTADOS), format_func=usuarios.ETIQUETA_ESTADO.get,
                           index=usuarios.ESTADOS.index(fila.get("status")) if fila.get("status") in usuarios.ESTADOS else 0)
        guardar = st.form_submit_button("Guardar cuenta", type="primary")
    if guardar:
        try:
            usuarios.actualizar_cuenta(sesion, uid, correo, nombre, rol, est)
            st.success("Cuenta actualizada.")
        except Exception as exc:  # noqa: BLE001
            ui.mostrar_error(exc)

    st.markdown("###### Contraseña de esta cuenta")
    with st.form(f"adm_pw_{uid}", clear_on_submit=True):
        c1, c2 = st.columns(2)
        n1 = c1.text_input("Nueva contraseña", type="password")
        n2 = c2.text_input("Repetir nueva contraseña", type="password")
        cambiar = st.form_submit_button("Cambiar contraseña")
    if cambiar:
        if n1 != n2:
            st.error("Las contraseñas no coinciden.")
        else:
            try:
                usuarios.cambiar_contrasena_de(sesion, uid, n1)
                st.success("Contraseña actualizada.")
            except Exception as exc:  # noqa: BLE001
                ui.mostrar_error(exc)

    if sesion.puede("usuarios", "delete") and uid != str(sesion.user_id):
        st.markdown("###### Baja definitiva")
        st.warning("Elimina la cuenta de acceso, su perfil, permisos y equipos. NO elimina personas, vacantes ni seguimientos. "
                   "Si solo quieres impedir el acceso, cambia el estado a «Deshabilitado»: es reversible.")
        if st.button("Dar de baja definitivamente", key=f"adm_baja_{uid}"):
            ui.pedir_confirmacion(f"baja_{uid}", f"Baja definitiva de {fila.get('email')}", [
                "Se eliminará la cuenta de acceso y su perfil, permisos y equipos.",
                "No se puede deshacer; para volver a darle acceso habría que crear la cuenta de nuevo.",
                "Los registros que esa persona capturó se conservan."], "Dar de baja")
        if ui.confirmado(f"baja_{uid}"):
            try:
                usuarios.eliminar_cuenta(sesion, uid)
                st.success("Cuenta dada de baja.")
                st.rerun()
            except Exception as exc:  # noqa: BLE001
                ui.mostrar_error(exc)


# -------------------------------------------------------------------- permisos
def _permisos(sesion: Sesion) -> None:
    perfiles = [p for p in usuarios.listar_perfiles(sesion) if p.get("role") != "admin"]
    if not perfiles:
        ui.vacio("No hay colaboradores. Los administradores tienen acceso a todo y no necesitan matriz de permisos.")
        return
    etiquetas = {_etiqueta_cuenta(p): p for p in perfiles}
    elegido = st.selectbox("Colaborador", list(etiquetas), key="adm_perm_usuario")
    uid = str(etiquetas[elegido]["user_id"])
    actuales = usuarios.permisos_de(sesion, uid)
    filas = []
    for clave, nombre in MODULES.items():
        viejo = actuales.get(clave, {})
        filas.append({"clave": clave, "Módulo": nombre, **{a.title(): bool(viejo.get(f"can_{a}")) for a in ACTIONS}})
    etiq = {a.title(): t for a, t in zip(ACTIONS, ("Ver", "Crear", "Editar", "Eliminar", "Exportar"))}
    df = pd.DataFrame(filas)
    editado = st.data_editor(
        df, hide_index=True, width="stretch", key=f"adm_perm_{uid}", disabled=["clave", "Módulo"],
        column_config={"clave": None, **{k: st.column_config.CheckboxColumn(v) for k, v in etiq.items()}})
    ui.nota("Crear, editar, eliminar y exportar requieren «Ver»: al guardar se activa «Ver» automáticamente. "
            "Para dar de alta personas o vacantes también se necesita «Ver», porque el sistema debe leer los IDs existentes para no repetirlos.")
    if st.button("💾 Guardar permisos", type="primary", key=f"adm_perm_guardar_{uid}"):
        carga = [{"module_key": r["clave"], **{f"can_{a}": bool(r[a.title()]) for a in ACTIONS}} for _, r in editado.iterrows()]
        try:
            guardados = usuarios.guardar_permisos(sesion, uid, carga)
            st.success("Permisos guardados y verificados en Supabase.")
            ajustados = [MODULES[g["module_key"]] for g, c in zip(guardados, carga)
                         if any(c.get(f"can_{a}") and not g.get(f"can_{a}") for a in ACTIONS)]
            if ajustados:
                st.info("Se quitaron acciones que no tenían «Ver» en: " + ", ".join(ajustados) + ".")
        except Exception as exc:  # noqa: BLE001
            ui.mostrar_error(exc)


# --------------------------------------------------------------------- equipos
def _equipos(sesion: Sesion) -> None:
    repo = RepoAdmin(sesion.cliente)
    equipos = repo.equipos()
    if not equipos:
        ui.vacio("Todavía no hay equipos registrados.")
        return
    nombres = {p["user_id"]: (p.get("display_name") or p.get("email")) for p in repo.perfiles()} if sesion.puede("usuarios", "view") else {}
    ahora = datetime.now(timezone.utc)
    filas = []
    for e in equipos:
        try:
            visto = datetime.fromisoformat(str(e.get("last_seen")).replace("Z", "+00:00"))
            reciente = ahora - visto <= timedelta(minutes=15)
        except (ValueError, TypeError):
            reciente = False
        filas.append({"Usuario": nombres.get(e.get("user_id"), SIN_DATO), "Equipo": e.get("hostname") or SIN_DATO,
                      "Sistema": e.get("os_name") or SIN_DATO, "Versión": e.get("app_version") or SIN_DATO,
                      "Autorizado": "Sí" if e.get("authorized") else "No", "Activo (15 min)": "Sí" if reciente else "No",
                      "Último acceso": _hora_mx(e.get("last_seen")), "_uid": e.get("user_id"), "_did": e.get("device_id")})
    df = pd.DataFrame(filas)
    c = st.columns(3)
    ui.kpi("Equipos registrados", len(df), contenedor=c[0])
    ui.kpi("Autorizados", int((df["Autorizado"] == "Sí").sum()), contenedor=c[1])
    ui.kpi("Con actividad reciente", int((df["Activo (15 min)"] == "Sí").sum()), contenedor=c[2])
    ui.tabla(df, [c for c in df.columns if not c.startswith("_")], altura=300)
    ui.nota("Un equipo es un NAVEGADOR (se identifica con una cookie). Si alguien cambia de navegador, borra las cookies o usa otro dispositivo, "
            "aparecerá como un equipo nuevo pendiente de autorización.")
    if not sesion.puede("dispositivos", "edit"):
        return
    opciones = {f"{r['Usuario']} · {r['Equipo']} · {str(r['_did'])[:8]}": r for r in filas}
    elegido = st.selectbox("Administrar equipo", list(opciones), key="adm_equipo")
    r = opciones[elegido]
    deseado = st.toggle("Equipo autorizado", value=r["Autorizado"] == "Sí", key=f"adm_eq_auth_{r['_did']}")
    if st.button("Guardar autorización", key="adm_eq_guardar"):
        if r["Autorizado"] == "Sí" and not deseado:
            ui.pedir_confirmacion("revocar_equipo", "Revocar el acceso de este equipo", [
                f"{r['Usuario']} ya no podrá entrar desde «{r['Equipo']}» hasta que lo vuelvas a autorizar.",
                "Si la base exige equipo autorizado (Estado del sistema), también dejará de ver datos de inmediato."], "Revocar")
            st.session_state["_equipo_pendiente"] = (r["_uid"], r["_did"], r["Equipo"])
        else:
            _aplicar_equipo(sesion, r["_uid"], r["_did"], r["Equipo"], deseado)
    if ui.confirmado("revocar_equipo"):
        uid, did, nombre = st.session_state.pop("_equipo_pendiente", (None, None, ""))
        if uid:
            _aplicar_equipo(sesion, uid, did, nombre, False)


def _aplicar_equipo(sesion: Sesion, uid: str, did: str, nombre: str, autorizado: bool) -> None:
    try:
        RepoAdmin(sesion.cliente).autorizar_equipo(uid, did, autorizado)
        auth_servicio.auditar("device_authorization_changed", f"{nombre} -> {autorizado}")
        st.success("Autorización actualizada.")
        st.rerun()
    except Exception as exc:  # noqa: BLE001
        ui.mostrar_error(exc)


# ----------------------------------------------------------------- prioridades
def _prioridades(sesion: Sesion) -> None:
    filas = prioridades.listar(sesion)
    if filas:
        df = pd.DataFrame(filas)
        df["aviso"] = df.get("reminder_at", "").map(_hora_mx)
        df["estatus"] = df["active"].map({True: "Activa", False: "Atendida"}) if "active" in df.columns else SIN_DATO
        ui.tabla(df, ["title", "entity_type", "entity_id", "priority_level", "aviso", "estatus"],
                 {"title": "Título", "entity_type": "Tipo", "entity_id": "Referencia", "priority_level": "Nivel", "aviso": "Aviso (hora CDMX)",
                  "estatus": "Estatus"}, altura=260)
    else:
        ui.vacio("No hay prioridades registradas.")
    if sesion.puede("prioridades", "create"):
        with st.expander("➕ Programar una prioridad"):
            ahora = ahora_mx()
            with st.form("adm_prioridad"):
                c1, c2 = st.columns(2)
                tipo = c1.selectbox("Tipo", list(prioridades.TIPOS))
                ref = c2.text_input("ID o referencia (opcional)", placeholder="PER-0001, VAC-0001…")
                titulo = st.text_input("Título")
                desc = st.text_area("Descripción", height=80)
                c3, c4, c5, c6 = st.columns(4)
                nivel = c3.selectbox("Nivel", list(prioridades.NIVELES))
                dia = c4.date_input("Fecha del primer aviso", value=ahora.date())
                hora = c5.time_input("Hora (Ciudad de México)", value=(ahora + timedelta(minutes=5)).time().replace(second=0, microsecond=0))
                cada = c6.number_input("Repetir cada (min)", min_value=1, value=60)
                enviar = st.form_submit_button("Programar", type="primary")
            if enviar:
                try:
                    prioridades.crear(sesion, tipo, ref, titulo, desc, nivel, dia, hora, int(cada))
                    st.success("Prioridad programada.")
                    st.rerun()
                except Exception as exc:  # noqa: BLE001
                    ui.mostrar_error(exc)
    activas = [f for f in filas if f.get("active")]
    if activas and sesion.puede("prioridades", "edit"):
        opciones = {f"#{f['id']} · {f.get('title')}": f for f in activas}
        elegido = st.selectbox("Marcar como atendida", list(opciones), key="adm_prio_cerrar")
        if st.button("✓ Marcar como atendida", key="adm_prio_btn"):
            f = opciones[elegido]
            try:
                prioridades.cerrar(sesion, f["id"], f.get("title") or "")
                st.success("Prioridad cerrada.")
                st.rerun()
            except Exception as exc:  # noqa: BLE001
                ui.mostrar_error(exc)


# ------------------------------------------------------------------- auditoría
def _auditoria(sesion: Sesion) -> None:
    filas = RepoAdmin(sesion.cliente).auditoria(limite=1000)
    if not filas:
        ui.vacio("Aún no hay movimientos de auditoría.")
        return
    df = pd.DataFrame(filas)
    df["fecha"] = df.get("created_at", "").map(_hora_mx)
    c1, c2 = st.columns([2, 1])
    texto = c1.text_input("Filtrar por usuario, acción o detalle", key="adm_aud_texto")
    acciones = ["Todas", *sorted(df["action"].dropna().astype(str).unique())] if "action" in df.columns else ["Todas"]
    accion = c2.selectbox("Acción", acciones, key="adm_aud_accion")
    if texto.strip():
        t = texto.strip().lower()
        pajar = df[[c for c in ("email", "action", "detail") if c in df.columns]].astype(str).agg(" ".join, axis=1).str.lower()
        df = df[pajar.str.contains(t, regex=False)]
    if accion != "Todas":
        df = df[df["action"] == accion]
    ui.nota(f"{len(df):,} movimiento(s) (últimos 1,000). Las horas son de la Ciudad de México.")
    ui.tabla(df, ["fecha", "email", "action", "detail", "device_id"],
             {"fecha": "Fecha", "email": "Usuario", "action": "Acción", "detail": "Detalle", "device_id": "Equipo"}, altura=420)
    ui.boton_exportar(sesion, "auditoria", df[[c for c in ("fecha", "email", "action", "detail") if c in df.columns]], "auditoria", "auditoria")


# -------------------------------------------------------------------- respaldos
def _respaldos(sesion: Sesion) -> None:
    st.markdown("##### Respaldo bajo demanda")
    st.write("Genera un ZIP con una copia de cada tabla (con los nombres reales de las columnas de Supabase). "
             "Streamlit Cloud no guarda archivos de forma permanente, por eso el respaldo se descarga en tu equipo y **tú** lo guardas.")
    st.warning("El respaldo contiene datos personales. Guárdalo en un lugar seguro y nunca lo subas a un repositorio.", icon="🔒")
    tablas = respaldos.tablas_respaldables(sesion)
    if not tablas:
        ui.vacio("Tu perfil no puede consultar ninguna tabla respaldable.")
    elif st.button("Generar respaldo", key="adm_resp_gen"):
        with st.spinner("Preparando el respaldo…"):
            try:
                datos_zip, archivo, conteos = respaldos.respaldo_zip(sesion)
                st.session_state["_respaldo"] = (datos_zip, archivo, conteos)
            except Exception as exc:  # noqa: BLE001
                ui.mostrar_error(exc)
    listo = st.session_state.get("_respaldo")
    if listo:
        datos_zip, archivo, conteos = listo
        st.success(" · ".join(f"{t}: {n:,} registros" for t, n in conteos.items()))
        st.download_button(f"⬇️ Descargar {archivo}", datos_zip, archivo, respaldos.MIME["zip"], key="adm_resp_dl")
    if sesion.puede("administracion", "view"):
        st.markdown("##### Historial de cargas")
        filas = RepoAdmin(sesion.cliente).historial(limite=300)
        if not filas:
            ui.vacio("Todavía no hay cargas registradas.")
        else:
            df = pd.DataFrame(filas)
            ui.tabla(df, ["fecha_hora", "usuario", "base", "origen", "archivo_origen", "registros_recibidos", "registros_guardados",
                          "duplicados_actualizados", "total_final"],
                     {"fecha_hora": "Fecha y hora (CDMX)", "usuario": "Usuario", "base": "Base", "origen": "Origen", "archivo_origen": "Archivo",
                      "registros_recibidos": "Recibidos", "registros_guardados": "Guardados", "duplicados_actualizados": "Omitidos (duplicados)",
                      "total_final": "Total final"}, altura=320)
            ui.nota("«Omitidos» son registros que ya existían (mismo ID o misma vacante): la carga no los modifica ni los duplica.")


# ---------------------------------------------------------------------- página
@ui.protegido
def render() -> None:
    sesion = actual()
    ui.encabezado("Administración", "Estado del sistema, cuentas, permisos, equipos y respaldos.", "⚙️")
    visibles = {k: v[0] for k, v in APARTADOS.items() if sesion.puede(v[1], v[2])}
    if not visibles:
        st.warning("Tu perfil no tiene apartados de administración habilitados.")
        return
    llaves = list(visibles.values())
    if st.session_state.get("adm_apartado") not in llaves:
        st.session_state["adm_apartado"] = llaves[0]
    elegido = st.segmented_control("Apartado", llaves, key="adm_apartado", label_visibility="collapsed") or llaves[0]
    clave = next(k for k, v in visibles.items() if v == elegido)
    {"estado": _estado, "usuarios": _usuarios, "permisos": _permisos, "equipos": _equipos, "prioridades": _prioridades,
     "auditoria": _auditoria, "respaldos": _respaldos}[clave](sesion)


@ui.protegido
def render_cuenta() -> None:
    """«Mi cuenta»: disponible para cualquier usuario con sesión (contraseña propia y equipo actual)."""
    sesion = actual()
    ui.encabezado("Mi cuenta", "Tus datos de acceso.", "👤")
    c = st.columns(3)
    ui.kpi("Correo", sesion.email, contenedor=c[0])
    ui.kpi("Rol", usuarios.ETIQUETA_ROL.get(sesion.perfil.get("role"), SIN_DATO), contenedor=c[1])
    ui.kpi("Estado", usuarios.ETIQUETA_ESTADO.get(sesion.perfil.get("status"), SIN_DATO), contenedor=c[2])
    st.markdown("##### Cambiar mi contraseña")
    with st.form("cuenta_pw", clear_on_submit=True):
        p1 = st.text_input("Nueva contraseña", type="password")
        p2 = st.text_input("Repetir nueva contraseña", type="password")
        enviar = st.form_submit_button("Cambiar mi contraseña", type="primary")
    if enviar:
        if p1 != p2:
            st.error("Las contraseñas no coinciden.")
        else:
            try:
                auth_servicio.cambiar_contrasena_propia(p1)
                st.success("Contraseña actualizada.")
            except Exception as exc:  # noqa: BLE001
                if isinstance(exc, (ValueError, ErrorDatos)):
                    st.error(str(exc))
                else:
                    st.error("No se pudo cambiar la contraseña. Inténtalo de nuevo.")
    st.markdown("##### Permisos de mi perfil")
    filas = [{"Módulo": nombre, **{a: ("Sí" if sesion.puede(clave, a) else "No") for a in ACTIONS}} for clave, nombre in MODULES.items()]
    st.dataframe(pd.DataFrame(filas).rename(columns={"view": "Ver", "create": "Crear", "edit": "Editar", "delete": "Eliminar", "export": "Exportar"}),
                 hide_index=True, width="stretch")
