"""Estado del sistema: conexión, conteos y migraciones detectadas (solo lectura, sin modificar nada)."""
from __future__ import annotations

from dataclasses import dataclass

from ..auth.sesion import Sesion
from ..repositories.admin import RepoAdmin
from ..repositories.catalogos import RepoEmpresas
from ..repositories.disponibilidad import RepoDisponibilidad
from ..repositories.errores import ErrorDatos
from ..repositories.tablas import RepoTabla

AJUSTE_EQUIPO = "enforce_device_rls"


@dataclass(frozen=True)
class Migracion:
    clave: str
    nombre: str
    aplicada: bool | None  # None = no se puede verificar desde la app
    detalle: str


def conexion(sesion: Sesion) -> tuple[bool, str]:
    try:
        RepoAdmin(sesion.cliente).perfil(sesion.user_id)
        return True, "Conectado a Supabase."
    except ErrorDatos as exc:
        return False, str(exc)
    except Exception:  # noqa: BLE001
        return False, "No se pudo consultar Supabase."


def conteos(sesion: Sesion) -> dict[str, int | None]:
    """Filas por tabla (None si el perfil no puede consultarla o falló la consulta)."""
    salida: dict[str, int | None] = {}
    for tipo in ("personas", "vacantes", "vinculaciones"):
        if not sesion.puede(tipo, "view"):
            salida[tipo] = None
            continue
        try:
            salida[tipo] = RepoTabla(sesion.cliente, tipo).contar()
        except ErrorDatos:
            salida[tipo] = None
    return salida


def migraciones(sesion: Sesion) -> list[Migracion]:
    """Detecta qué migraciones opcionales ya están en la base, mirando columnas y tablas (sin escribir)."""
    out: list[Migracion] = []
    admin = RepoAdmin(sesion.cliente)

    out.append(Migracion("V001", "Cierre de brechas de seguridad (RPC y permisos)", None,
                         "No es verificable desde la app; se comprueba con las pruebas SQL de tests/sql."))
    out.append(Migracion("V002", "RLS por permiso y control opcional de equipo",
                         admin.ajuste(AJUSTE_EQUIPO) is not None, "Busca la tabla app_settings."))
    out.append(Migracion("V003", "Auditoría en el servidor (disparadores)", None,
                         "No es verificable desde la app; se revisa con la consulta de verificación al final del archivo."))

    col_emp = set()
    try:
        filas = RepoEmpresas(sesion.cliente).listar()
        col_emp = set(filas[0].keys()) if filas else set()
    except ErrorDatos:
        pass
    col_vac = RepoTabla(sesion.cliente, "vacantes").columnas_remotas() if sesion.puede("vacantes", "view") else set()
    col_per = RepoTabla(sesion.cliente, "personas").columnas_remotas() if sesion.puede("personas", "view") else set()

    def _estado(cols: set[str], esperadas: tuple[str, ...], puede: bool) -> bool | None:
        if not puede or not cols:  # tabla vacía o sin permiso de lectura: no hay muestra para comparar
            return None
        return all(c in cols for c in esperadas)

    v004 = None
    if col_emp and col_vac:
        v004 = "municipio" in col_emp and "municipio_excepcion" in col_vac
    out.append(Migracion("V004", "Ubicación de empresas y excepción de municipio por vacante", v004,
                         "Columnas municipio (empresas) y municipio_excepcion (vacantes)."))
    out.append(Migracion("V005", "Origen del dato: año/institución registrados vs. estimados",
                         _estado(col_per, ("anio_fuente", "institucion_fuente"), sesion.puede("personas", "view")),
                         "Columnas anio_fuente e institucion_fuente en personas."))
    out.append(Migracion("V007", "Vigencia de vacantes (fecha de cierre)",
                         _estado(col_vac, ("fecha_cierre",), sesion.puede("vacantes", "view")),
                         "Columna fecha_cierre en vacantes."))
    try:
        disp = RepoDisponibilidad(sesion.cliente).listar()
        out.append(Migracion("V008", "Disponibilidad de personas para vincular", disp is not None, "Tabla persona_disponibilidad."))
    except ErrorDatos:
        out.append(Migracion("V008", "Disponibilidad de personas para vincular", None, "Tabla persona_disponibilidad."))
    return out


def equipo_obligatorio(sesion: Sesion) -> bool | None:
    """True/False según app_settings; None si V002 no está aplicada."""
    valor = RepoAdmin(sesion.cliente).ajuste(AJUSTE_EQUIPO)
    return None if valor is None else str(valor).strip().lower() == "true"


def fijar_equipo_obligatorio(sesion: Sesion, activo: bool) -> None:
    from ..auth import servicio as auth_servicio
    from ..repositories.errores import SinPermiso
    if not sesion.es_admin:
        raise SinPermiso("Solo un administrador puede cambiar este control.")
    RepoAdmin(sesion.cliente).guardar_ajuste(AJUSTE_EQUIPO, "true" if activo else "false")
    auth_servicio.auditar("device_gate_changed", f"enforce_device_rls={'true' if activo else 'false'}")
