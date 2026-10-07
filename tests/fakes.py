"""Cliente Supabase falso en memoria (solo para pruebas): imita lo mínimo de PostgREST que usa la app."""
from __future__ import annotations

import copy
from types import SimpleNamespace


class FakeAPIError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code, self.message = code, message


class _Consulta:
    def __init__(self, db, nombre):
        self.db, self.nombre = db, nombre
        self.op, self.carga, self.filtros, self.orden = "select", None, [], None
        self.rango, self.limite, self.contar = None, None, False

    # --- construcción
    def select(self, columnas="*", count=None):
        self.op, self.columnas, self.contar = "select", columnas, bool(count)
        return self

    def insert(self, carga):
        self.op, self.carga = "insert", carga
        return self

    def update(self, carga):
        self.op, self.carga = "update", carga
        return self

    def delete(self):
        self.op = "delete"
        return self

    def upsert(self, carga, on_conflict=""):
        self.op, self.carga, self.conflicto = "upsert", carga, [c.strip() for c in on_conflict.split(",") if c.strip()]
        return self

    def eq(self, col, val):
        self.filtros.append(lambda f, c=col, v=val: str(f.get(c)) == str(v))
        return self

    def in_(self, col, vals):
        vals = {str(v) for v in vals}
        self.filtros.append(lambda f, c=col: str(f.get(c)) in vals)
        return self

    def order(self, col, desc=False):
        self.orden = (col, desc)
        return self

    def range(self, a, b):
        self.rango = (a, b)
        return self

    def limit(self, n):
        self.limite = n
        return self

    # --- ejecución
    def execute(self):
        if self.nombre in self.db.tablas_faltantes:
            raise FakeAPIError("PGRST205", f"Could not find the table 'public.{self.nombre}' in the schema cache")
        t = self.db.tablas.setdefault(self.nombre, [])
        permisos = self.db.permisos.get(self.nombre, {"select", "insert", "update", "delete"})
        self.db.llamadas.append((self.nombre, self.op))
        if self.db.fallo_siguiente and self.db.fallo_siguiente[0] == (self.nombre, self.op):
            _, exc = self.db.fallo_siguiente
            self.db.fallo_siguiente = None
            raise exc
        if self.op not in permisos and not (self.op == "upsert" and {"insert", "update"} <= permisos):
            # RLS: select/update/delete se filtran en silencio; insert falla con 42501
            if self.op == "insert":
                raise FakeAPIError("42501", "new row violates row-level security policy")
            return SimpleNamespace(data=[], count=0)
        pk = self.db.pks.get(self.nombre, "id")
        if self.op == "upsert":
            for fila in (self.carga if isinstance(self.carga, list) else [self.carga]):
                previa = next((f for f in t if all(str(f.get(c)) == str(fila.get(c)) for c in self.conflicto)), None)
                if previa is None:
                    t.append(copy.deepcopy(fila))
                else:
                    previa.update(copy.deepcopy(fila))
            return SimpleNamespace(data=copy.deepcopy(self.carga if isinstance(self.carga, list) else [self.carga]), count=None)
        if self.op == "insert":
            filas = self.carga if isinstance(self.carga, list) else [self.carga]
            existentes = {str(f.get(pk)) for f in t}
            nuevos = {}
            for f in filas:
                if pk not in f and pk == "id":
                    f = {**f, "id": len(t) + len(nuevos) + 1}
                k = str(f.get(pk))
                if k in existentes or k in nuevos:
                    raise FakeAPIError("23505", f'duplicate key value violates unique constraint "{self.nombre}_pkey"')
                nuevos[k] = copy.deepcopy(f)
            t.extend(nuevos.values())
            return SimpleNamespace(data=copy.deepcopy(list(nuevos.values())), count=None)
        sel = [f for f in t if all(fn(f) for fn in self.filtros)]
        if self.op == "update":
            for f in sel:
                f.update(copy.deepcopy(self.carga))
            return SimpleNamespace(data=copy.deepcopy(sel), count=None)
        if self.op == "delete":
            for f in sel:
                t.remove(f)
            return SimpleNamespace(data=copy.deepcopy(sel), count=None)
        if self.orden:
            col, desc = self.orden
            sel = sorted(sel, key=lambda f: (f.get(col) is None, str(f.get(col))), reverse=desc)
        total = len(sel)
        if self.rango:
            sel = sel[self.rango[0]:self.rango[1] + 1]
        if self.limite is not None:
            sel = sel[:self.limite]
        cols = None if self.columnas.strip() == "*" else [c.strip() for c in self.columnas.split(",")]
        data = [({c: f.get(c) for c in cols} if cols else copy.deepcopy(f)) for f in sel]
        return SimpleNamespace(data=data, count=total if self.contar else None)


class FakeCliente:
    def __init__(self, pks=None, permisos=None):
        self.tablas: dict[str, list[dict]] = {}
        self.pks = {"personas": "id_persona", "vacantes": "id_vacante", "vinculaciones": "id_vinculacion",
                    "historial_cargas": "id", "app_audit_log": "id", **(pks or {})}
        self.permisos = permisos or {}
        self.llamadas: list[tuple] = []
        self.fallo_siguiente = None
        self.auth = SimpleNamespace(sign_out=lambda: None)

    def table(self, nombre):
        return _Consulta(self, nombre)


class _Rpc:
    def __init__(self, db, nombre, params):
        self.db, self.nombre, self.params = db, nombre, params

    def execute(self):
        self.db.rpcs.append((self.nombre, self.params))
        resp = self.db.rpc_respuestas.get(self.nombre)
        if isinstance(resp, Exception):
            raise resp
        if callable(resp):
            resp = resp(self.params)
        return SimpleNamespace(data=resp)


def _rpc(self, nombre, params):
    return _Rpc(self, nombre, params)


FakeCliente.rpc = _rpc
_init_original = FakeCliente.__init__


def _init(self, *a, **k):
    _init_original(self, *a, **k)
    self.rpcs, self.rpc_respuestas = [], {}
    self.tablas_faltantes: set[str] = set()  # tablas "sin migrar": toda consulta falla con PGRST205


FakeCliente.__init__ = _init
