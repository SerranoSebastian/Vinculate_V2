"""Errores de datos con mensajes entendibles para el usuario.

Los repositorios traducen las excepciones de PostgREST/httpx a estas clases para
que la interfaz nunca muestre un traceback ni texto técnico crudo.
"""
from __future__ import annotations


class ErrorDatos(Exception):
    """Error controlado: `str(exc)` es apto para mostrarse al usuario."""

    def __init__(self, mensaje: str, *, detalle: str = "", codigo: str = ""):
        super().__init__(mensaje)
        self.detalle = detalle
        self.codigo = codigo


class SinPermiso(ErrorDatos):
    pass


class SesionExpirada(ErrorDatos):
    pass


class Duplicado(ErrorDatos):
    pass


class NoEncontrado(ErrorDatos):
    pass


class SinConexion(ErrorDatos):
    pass


def traducir(exc: Exception, contexto: str = "la operación") -> ErrorDatos:
    """Convierte cualquier excepción de la capa de red/PostgREST en ErrorDatos."""
    if isinstance(exc, ErrorDatos):
        return exc
    codigo = str(getattr(exc, "code", "") or "")
    texto = str(getattr(exc, "message", "") or exc)
    bajo = texto.lower()
    detalle = f"{type(exc).__name__}: {texto}"

    if codigo in {"PGRST301", "PGRST303"} or "jwt expired" in bajo or "invalid jwt" in bajo:
        return SesionExpirada("Tu sesión expiró. Vuelve a iniciar sesión.", detalle=detalle, codigo=codigo)
    if codigo == "42501" or "row-level security" in bajo or "permission denied" in bajo:
        return SinPermiso(f"No tienes permiso para realizar {contexto}.", detalle=detalle, codigo=codigo)
    if codigo == "23505" or "duplicate key" in bajo:
        return Duplicado("Ya existe un registro con ese identificador.", detalle=detalle, codigo=codigo)
    if codigo in {"PGRST204", "PGRST205", "42703", "42P01"} or ("could not find the" in bajo and ("column" in bajo or "table" in bajo)):
        return ErrorDatos("La base todavía no tiene una columna o tabla que esta función necesita: falta aplicar una "
                          "migración en Supabase (revisa Administración → Estado del sistema).", detalle=detalle, codigo=codigo)
    if codigo in {"23514", "23502", "23503", "22P02", "22007", "22008"}:
        return ErrorDatos(f"Los datos no cumplen las reglas de la base ({texto}).", detalle=detalle, codigo=codigo)
    if codigo == "PGRST116":
        return NoEncontrado("El registro ya no existe.", detalle=detalle, codigo=codigo)
    nombre = type(exc).__name__
    if nombre in {"ConnectError", "ConnectTimeout", "ReadTimeout", "RemoteProtocolError", "ReadError",
                  "NetworkError", "TimeoutException", "ConnectionError"}:
        return SinConexion("No se pudo conectar con la base de datos. Revisa tu conexión e inténtalo de nuevo.",
                           detalle=detalle, codigo=codigo)
    return ErrorDatos(f"No se pudo completar {contexto}. Intenta de nuevo; si persiste, avisa a un administrador.",
                      detalle=detalle, codigo=codigo)
