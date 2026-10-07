"""Repositorio genérico de las tablas de datos (personas, vacantes, vinculaciones, historial).

Solo habla con Supabase: no valida reglas de negocio ni conoce Streamlit.
Guarda de forma DIRIGIDA (insert / update por ID / delete por ID): nunca sube la
tabla completa, así RLS por acción (V002) funciona para quien solo puede crear.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..core.mapeo import TABLAS
from .errores import NoEncontrado, SinPermiso, traducir

PAGINA = 1000
BLOQUE_INSERT = 300


class RepoTabla:
    def __init__(self, cliente, clave: str):
        if clave not in TABLAS:
            raise KeyError(clave)
        self.cliente = cliente
        self.clave = clave
        self.cfg = TABLAS[clave]
        self.tabla = self.cfg["table"]
        self.pk = self.cfg["pk"]

    def _tabla(self):
        return self.cliente.table(self.tabla)

    # ---------------------------------------------------------------- lectura
    def listar(self, pagina: int = PAGINA) -> list[dict]:
        """Todas las filas (paginado de 1000 en 1000, ordenado por clave primaria)."""
        filas: list[dict] = []
        inicio = 0
        try:
            while True:
                resp = (self._tabla().select("*").order(self.pk).range(inicio, inicio + pagina - 1).execute())
                lote = resp.data or []
                filas.extend(lote)
                if len(lote) < pagina:
                    break
                inicio += pagina
        except Exception as exc:  # noqa: BLE001
            raise traducir(exc, f"la consulta de {self.tabla}") from exc
        return filas

    def version(self) -> str:
        """Huella barata del estado de la tabla: conteo|máx(actualizado_en).

        Sirve de llave de caché: si alguien guarda, cambia y nadie ve datos viejos.
        """
        try:
            resp = (self._tabla().select(f"{self.pk},actualizado_en", count="exact")
                    .order("actualizado_en", desc=True).limit(1).execute())
        except Exception as exc:  # noqa: BLE001
            raise traducir(exc, f"la consulta de {self.tabla}") from exc
        fila = (resp.data or [{}])[0] if resp.data else {}
        return f"{int(resp.count or 0)}|{fila.get('actualizado_en') or '-'}"

    def contar(self) -> int:
        try:
            resp = self._tabla().select(self.pk, count="exact").limit(1).execute()
        except Exception as exc:  # noqa: BLE001
            raise traducir(exc, f"la consulta de {self.tabla}") from exc
        return int(resp.count or 0)

    def ids(self) -> set[str]:
        """Todos los IDs actuales (para detectar colisiones al crear)."""
        out: set[str] = set()
        inicio = 0
        try:
            while True:
                resp = self._tabla().select(self.pk).order(self.pk).range(inicio, inicio + PAGINA - 1).execute()
                lote = resp.data or []
                out.update(str(r[self.pk]) for r in lote)
                if len(lote) < PAGINA:
                    break
                inicio += PAGINA
        except Exception as exc:  # noqa: BLE001
            raise traducir(exc, f"la consulta de {self.tabla}") from exc
        return out

    def columna(self, nombre: str) -> set[str]:
        """Valores distintos de UNA columna, leídos frescos de la base (para generar IDs sin colisión)."""
        out: set[str] = set()
        inicio = 0
        try:
            while True:
                resp = (self._tabla().select(nombre).order(self.pk).range(inicio, inicio + PAGINA - 1).execute())
                lote = resp.data or []
                out.update(str(r[nombre]) for r in lote if r.get(nombre) not in (None, ""))
                if len(lote) < PAGINA:
                    break
                inicio += PAGINA
        except Exception as exc:  # noqa: BLE001
            raise traducir(exc, f"la consulta de {self.tabla}") from exc
        return out

    def columnas_remotas(self) -> set[str]:
        """Nombres de columna que la base devuelve para esta tabla (según una fila de muestra).

        Sirve para saber si las columnas opcionales de V004/V005/V007 ya existen. Con la
        tabla vacía (o sin permiso de lectura) devuelve un conjunto vacío.
        """
        try:
            resp = self._tabla().select("*").limit(1).execute()
        except Exception:  # noqa: BLE001
            return set()
        return set((resp.data or [{}])[0].keys()) if resp.data else set()

    def obtener(self, id_valor: str) -> dict | None:
        try:
            resp = self._tabla().select("*").eq(self.pk, str(id_valor)).limit(1).execute()
        except Exception as exc:  # noqa: BLE001
            raise traducir(exc, f"la consulta de {self.tabla}") from exc
        return (resp.data or [None])[0]

    # -------------------------------------------------------------- escritura
    def insertar(self, filas: list[dict]) -> int:
        if not filas:
            return 0
        total = 0
        try:
            for i in range(0, len(filas), BLOQUE_INSERT):
                lote = filas[i:i + BLOQUE_INSERT]
                resp = self._tabla().insert(lote).execute()
                total += len(resp.data or lote)
        except Exception as exc:  # noqa: BLE001
            raise traducir(exc, f"el alta en {self.tabla}") from exc
        return total

    def actualizar(self, id_valor: str, cambios: dict[str, Any]) -> dict:
        """UPDATE de un solo registro. Falla si no se afectó exactamente una fila
        (sin permiso por RLS, o el registro ya no existe)."""
        if not cambios:
            raise ValueError("No hay cambios que guardar.")
        carga = dict(cambios)
        if self.clave in {"personas", "vacantes", "vinculaciones"}:
            carga["actualizado_en"] = datetime.now(timezone.utc).isoformat()
        try:
            resp = self._tabla().update(carga).eq(self.pk, str(id_valor)).execute()
        except Exception as exc:  # noqa: BLE001
            raise traducir(exc, f"la edición en {self.tabla}") from exc
        datos = resp.data or []
        if len(datos) != 1:
            raise SinPermiso("No se modificó ningún registro: no tienes permiso de edición o el registro ya no existe.")
        return datos[0]

    def actualizar_varios(self, ids: list[str], cambios: dict[str, Any], bloque: int = 100) -> int:
        """UPDATE de varios registros por ID con los MISMOS cambios. Devuelve cuántos se modificaron realmente."""
        if not cambios or not ids:
            return 0
        carga = dict(cambios)
        if self.clave in {"personas", "vacantes", "vinculaciones"}:
            carga["actualizado_en"] = datetime.now(timezone.utc).isoformat()
        total = 0
        try:
            for i in range(0, len(ids), bloque):
                resp = self._tabla().update(carga).in_(self.pk, [str(x) for x in ids[i:i + bloque]]).execute()
                total += len(resp.data or [])
        except Exception as exc:  # noqa: BLE001
            raise traducir(exc, f"la edición en {self.tabla}") from exc
        return total

    def eliminar_varios(self, ids: list[str], bloque: int = 100) -> list[dict]:
        """DELETE por lista de IDs (deshacer una carga). Devuelve las filas realmente eliminadas."""
        borradas: list[dict] = []
        try:
            for i in range(0, len(ids), bloque):
                resp = self._tabla().delete().in_(self.pk, [str(x) for x in ids[i:i + bloque]]).execute()
                borradas.extend(resp.data or [])
        except Exception as exc:  # noqa: BLE001
            raise traducir(exc, f"la baja en {self.tabla}") from exc
        return borradas

    def eliminar(self, id_valor: str) -> dict:
        """DELETE de un solo registro; devuelve la fila eliminada (para deshacer)."""
        try:
            resp = self._tabla().delete().eq(self.pk, str(id_valor)).execute()
        except Exception as exc:  # noqa: BLE001
            raise traducir(exc, f"la baja en {self.tabla}") from exc
        datos = resp.data or []
        if len(datos) != 1:
            raise NoEncontrado("No se eliminó ningún registro: no tienes permiso de baja o ya no existe.")
        return datos[0]
