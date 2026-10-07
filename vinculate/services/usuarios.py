"""Administración de cuentas y permisos (orquesta los RPC SECURITY DEFINER de V001).

La seguridad real vive en la base (V001 impide que un delegado se escale privilegios o toque
cuentas de administradores). Aquí solo se valida la entrada, se comprueba el permiso de interfaz,
se verifica que lo guardado coincida con lo pedido y se audita.
"""
from __future__ import annotations

from ..auth import servicio as auth_servicio
from ..auth.sesion import Sesion
from ..core.constantes import ACTIONS, MODULES
from ..repositories.admin import RepoAdmin
from ..repositories.cliente import nuevo_cliente
from ..repositories.errores import ErrorDatos, SinPermiso

ROLES = ("collaborator", "admin")
ESTADOS = ("pending", "active", "disabled")
ETIQUETA_ROL = {"collaborator": "Colaborador", "admin": "Administrador"}
ETIQUETA_ESTADO = {"pending": "Pendiente", "active": "Activo", "disabled": "Deshabilitado"}


def _exigir(sesion: Sesion, accion: str) -> None:
    if not sesion.puede("usuarios", accion):
        raise SinPermiso("Tu perfil no tiene permiso para esta acción en Usuarios y permisos.")


def _correo(email: str) -> str:
    valor = (email or "").strip().lower()
    if not auth_servicio.EMAIL_RE.match(valor):
        raise ValueError("Escribe un correo electrónico válido.")
    return valor


def _nombre(nombre: str, email: str) -> str:
    nombre = (nombre or "").strip() or email
    if len(nombre) > 120:
        raise ValueError("El nombre para mostrar es demasiado largo.")
    return nombre


def listar_perfiles(sesion: Sesion) -> list[dict]:
    _exigir(sesion, "view")
    return RepoAdmin(sesion.cliente).perfiles()


def permisos_de(sesion: Sesion, uid: str) -> dict[str, dict]:
    _exigir(sesion, "view")
    return {r["module_key"]: r for r in RepoAdmin(sesion.cliente).permisos_de(uid) if r.get("module_key")}


def _uid_de_respuesta(data) -> str:
    if isinstance(data, str):
        return data
    if isinstance(data, list) and data:
        primero = data[0]
        if isinstance(primero, dict):
            return str(primero.get("user_id") or primero.get("admin_finalize_collaborator") or "")
        return str(primero)
    if isinstance(data, dict):
        return str(data.get("user_id") or data.get("admin_finalize_collaborator") or "")
    return ""


def crear_colaborador(sesion: Sesion, email: str, password: str, nombre: str) -> str:
    """Alta en Auth con un cliente aparte (no reemplaza la sesión del administrador) y cierre
    transaccional del perfil con el RPC admin_finalize_collaborator."""
    _exigir(sesion, "create")
    email = _correo(email)
    auth_servicio.validar_contrasena(password)
    nombre = _nombre(nombre, email)
    repo = RepoAdmin(sesion.cliente)
    if repo.perfil_por_email(email):
        raise ValueError("Ese correo ya está registrado en Vincúlate. Puedes cambiar su contraseña o permisos.")
    error_alta = None
    try:
        nuevo_cliente().auth.sign_up({"email": email, "password": password,
                                      "options": {"data": {"display_name": nombre}}})
    except Exception as exc:  # noqa: BLE001 — un usuario huérfano puede ocultar detalle; el RPC lo repara
        error_alta = exc
    try:
        data = repo.rpc("admin_finalize_collaborator", {"p_email": email, "p_new_password": password,
                                                        "p_display_name": nombre})
    except ErrorDatos as exc:
        detalle = f" (alta en Authentication: {error_alta})" if error_alta else ""
        raise ErrorDatos(f"No se pudo finalizar el usuario: {exc}{detalle}") from exc
    uid = _uid_de_respuesta(data)
    if not uid:
        existente = repo.perfil_por_email(email)
        uid = str(existente["user_id"]) if existente else ""
    if not uid:
        raise ErrorDatos("Supabase no confirmó la persistencia del nuevo colaborador.")
    auth_servicio.auditar("user_created", f"Colaborador creado/reparado: {email}")
    return uid


def normalizar_permisos(permisos: list[dict]) -> list[dict]:
    """Solo módulos conocidos; cualquier acción exige 'ver' (no se puede crear lo que no se ve)."""
    out = []
    for fila in permisos:
        mk = str(fila.get("module_key", "")).strip()
        if mk not in MODULES:
            continue
        ver = bool(fila.get("can_view", False))
        out.append({"module_key": mk, "can_view": ver,
                    **{f"can_{a}": bool(fila.get(f"can_{a}", False)) and ver for a in ACTIONS if a != "view"}})
    return out


def guardar_permisos(sesion: Sesion, uid: str, permisos: list[dict]) -> list[dict]:
    """Reemplaza la matriz completa vía RPC y VERIFICA que lo persistido coincida."""
    _exigir(sesion, "edit")
    normal = normalizar_permisos(permisos)
    repo = RepoAdmin(sesion.cliente)
    repo.rpc("admin_replace_user_permissions", {"p_user_id": uid, "p_permissions": normal})
    campos = tuple(f"can_{a}" for a in ACTIONS)
    guardado = {r["module_key"]: tuple(bool(r.get(c)) for c in campos) for r in repo.permisos_de(uid)}
    esperado = {r["module_key"]: tuple(bool(r.get(c)) for c in campos) for r in normal}
    if any(guardado.get(k) != v for k, v in esperado.items()):
        raise ErrorDatos("Supabase respondió, pero lo guardado no coincide con lo solicitado. "
                         "Si eres delegado, no puedes otorgar permisos que tú no tienes.")
    auth_servicio.auditar("permissions_updated", f"user_id={uid}")
    return normal


def actualizar_cuenta(sesion: Sesion, uid: str, email: str, nombre: str, rol: str, estado: str) -> None:
    _exigir(sesion, "edit")
    email = _correo(email)
    nombre = _nombre(nombre, email)
    if rol not in ROLES:
        raise ValueError("Rol inválido.")
    if estado not in ESTADOS:
        raise ValueError("Estado inválido.")
    RepoAdmin(sesion.cliente).rpc("admin_update_user_account", {
        "p_user_id": uid, "p_email": email, "p_display_name": nombre, "p_role": rol, "p_status": estado})
    auth_servicio.auditar("account_updated", f"user_id={uid}; role={rol}; status={estado}")


def cambiar_contrasena_de(sesion: Sesion, uid: str, nueva: str) -> None:
    _exigir(sesion, "edit")
    auth_servicio.validar_contrasena(nueva)
    RepoAdmin(sesion.cliente).rpc("admin_set_user_password", {"p_user_id": uid, "p_new_password": nueva})
    auth_servicio.auditar("admin_password_changed", f"user_id={uid}")


def eliminar_cuenta(sesion: Sesion, uid: str) -> None:
    _exigir(sesion, "delete")
    if str(uid) == str(sesion.user_id):
        raise ValueError("No puedes dar de baja definitivamente tu propia cuenta desde una sesión activa.")
    RepoAdmin(sesion.cliente).rpc("admin_delete_user_account", {"p_user_id": uid})
    auth_servicio.auditar("account_deleted", f"user_id={uid}")
