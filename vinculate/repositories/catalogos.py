"""Catálogo de empresas (nombre, sector y —tras V004— ubicación)."""
from __future__ import annotations

from datetime import datetime, timezone

from .errores import ErrorDatos, traducir

TABLA = "catalogo_empresas"


class RepoEmpresas:
    def __init__(self, cliente):
        self.c = cliente

    def listar(self) -> list[dict]:
        filas, inicio = [], 0
        try:
            while True:
                lote = self.c.table(TABLA).select("*").order("nombre").range(inicio, inicio + 999).execute().data or []
                filas.extend(lote)
                if len(lote) < 1000:
                    break
                inicio += 1000
        except Exception as exc:  # noqa: BLE001
            raise traducir(exc, "la consulta del catálogo de empresas") from exc
        return filas

    def obtener(self, nombre: str) -> dict | None:
        try:
            r = self.c.table(TABLA).select("*").eq("nombre", nombre).limit(1).execute()
        except Exception as exc:  # noqa: BLE001
            raise traducir(exc, "la consulta del catálogo de empresas") from exc
        return (r.data or [None])[0]

    def guardar_ubicacion(self, nombre: str, sector: str | None, ubicacion: dict) -> None:
        """UPDATE de la empresa si existe; si no, INSERT. Nunca borra ni renombra empresas."""
        existente = self.obtener(nombre)
        carga = {**ubicacion, "ubicacion_actualizada": datetime.now(timezone.utc).isoformat()}
        try:
            if existente is None:
                self.c.table(TABLA).insert({"nombre": nombre, "sector": sector or None, "activo": True, **carga}).execute()
            else:
                r = self.c.table(TABLA).update(carga).eq("nombre", nombre).execute()
                if len(r.data or []) != 1:
                    raise ErrorDatos("No se modificó la empresa: no tienes permiso o ya no existe.")
        except ErrorDatos:
            raise
        except Exception as exc:  # noqa: BLE001
            raise traducir(exc, "el guardado de la ubicación de la empresa") from exc
