"""Guardado DIRIGIDO de personas, vacantes y vinculaciones.

Principios (corrigen defectos de la v5 documentados en el informe de la Fase 0):
  * Nunca se sube la tabla completa: solo INSERT de filas nuevas, UPDATE por ID de las
    columnas tocadas y DELETE por ID. Así RLS por acción (V002) funciona de verdad.
  * Importar NO sobrescribe ni duplica: lo que ya existe (mismo ID, o misma vacante) se omite
    y se informa cuántos fueron.
  * Los IDs nuevos se calculan contra los IDs REALES de la base (no solo contra el archivo) y,
    si otra persona guarda al mismo tiempo (error 23505), se recalculan hasta 3 veces.
  * Cada baja va a una papelera de la sesión con opción de restaurar; cada carga se puede deshacer.
  * El resultado siempre dice la verdad: lo guardado, lo omitido y, si algo falló a medias, hasta
    dónde llegó.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from ..auth import servicio as auth_servicio
from ..auth.sesion import Sesion
from ..core import mapeo
from ..core.constantes import ESTADOS_VACANTE
from ..core.personas import asignar_ids_personas, limpiar_personas, validar_personas
from ..core.vacantes import (
    asignar_ids_vacantes, clave_duplicado_vacante, limpiar_vacantes, validar_vacantes,
)
from ..core.vinculaciones import (
    asignar_ids_vinculaciones, limpiar_vinculaciones, validar_vinculaciones,
)
from ..repositories.admin import RepoAdmin
from ..repositories.errores import Duplicado, ErrorDatos, NoEncontrado, SinPermiso
from ..repositories.tablas import BLOQUE_INSERT, RepoTabla
from . import datos

ZONA = ZoneInfo("America/Mexico_City")
NOMBRES = {"personas": "Personas", "vacantes": "Vacantes", "vinculaciones": "Vinculaciones"}
VERBOS = {"create": "registrar", "edit": "editar", "delete": "eliminar"}
MAX_PAPELERA = 25
MAX_INTENTOS_ID = 4  # 1 intento + 3 reintentos ante colisión de IDs (error 23505)


def ahora_mx() -> datetime:
    return datetime.now(ZONA)


@dataclass
class Resultado:
    ok: bool
    mensaje: str
    guardados: int = 0
    omitidos: int = 0
    errores: list[dict] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    ids: list[str] = field(default_factory=list)


# ------------------------------------------------------------------ utilidades
def _exigir(sesion: Sesion, tipo: str, accion: str) -> None:
    if not sesion.puede(tipo, accion):
        raise SinPermiso(f"Tu perfil no tiene permiso para {VERBOS.get(accion, accion)} en {NOMBRES.get(tipo, tipo)}.")


def _extras(sesion: Sesion, tipo: str) -> set[str]:
    """Columnas opcionales (V004/V005/V007) que SÍ existen en la base. Se sondea poco y se recuerda."""
    cache = st.session_state.setdefault("_extras", {})
    previo = cache.get(tipo)
    if previo and previo[1] and time.monotonic() - previo[0] < 600:
        return previo[1]
    remotas = RepoTabla(sesion.cliente, tipo).columnas_remotas()
    presentes = {r for r in mapeo.TABLAS[tipo]["opcionales"].values() if r in remotas}
    cache[tipo] = (time.monotonic() if remotas else 0.0, presentes if remotas else set())
    return presentes


def columnas_opcionales(sesion: Sesion, tipo: str) -> set[str]:
    """Columnas opcionales (migraciones V004/V005/V007) que ya existen en la base para esa tabla."""
    return _extras(sesion, tipo)


def _igual(a, b) -> bool:
    """Comparación tolerante (None == '' ; 22 == '22' == 22.0; fechas ISO)."""
    def norm(v):
        if v is None:
            return ""
        try:
            if pd.isna(v):
                return ""
        except (TypeError, ValueError):
            pass
        if isinstance(v, (pd.Timestamp, datetime)):
            return v.strftime("%Y-%m-%d")
        t = str(v).strip()
        if t.lower() in {"nan", "none", "nat", "<na>"}:
            return ""
        if len(t) >= 10 and t[4:5] == "-" and t[7:8] == "-":
            return t[:10]
        try:
            f = float(t)
            return str(int(f)) if f.is_integer() else str(f)
        except ValueError:
            return t
    return norm(a) == norm(b)


def _historial(sesion: Sesion, tipo: str, origen: str, archivo: str | None, recibidos: int,
               guardados: int, omitidos: int) -> None:
    try:
        total = RepoTabla(sesion.cliente, tipo).contar() if sesion.puede(tipo, "view") else None
        RepoAdmin(sesion.cliente).registrar_historial({
            "fecha_hora": ahora_mx().strftime("%Y-%m-%d %H:%M:%S"),
            "usuario": sesion.email, "base": tipo, "origen": origen,
            "archivo_origen": archivo or "", "registros_recibidos": int(recibidos),
            "registros_guardados": int(guardados), "duplicados_actualizados": int(omitidos),
            "total_final": total,
        })
    except Exception:  # noqa: BLE001 — el historial nunca debe tumbar un guardado ya hecho
        pass


def _recordar_carga(tipo: str, ids: list[str]) -> None:
    if ids:
        st.session_state["_ultima_carga"] = {"tipo": tipo, "ids": list(ids), "ts": time.time()}


def ultima_carga() -> dict | None:
    return st.session_state.get("_ultima_carga")


@dataclass
class _Insercion:
    guardados: int
    ids: list[str]
    omitidos: int
    pendientes: int
    error: ErrorDatos | None


def _insertar_con_reintentos(repo: RepoTabla, tipo: str, df: pd.DataFrame, extras: set[str], pk: str,
                             cols_auto: list[str], asignar, ocupados_fn) -> _Insercion:
    """Inserta por bloques. Las filas sin ID reciben uno nuevo calculado contra lo que hay en la
    base; si otra persona gana la carrera (23505) se vuelve a calcular. Las filas con ID propio que
    ya existe se omiten, no se sobrescriben."""
    pk_sql = mapeo.TABLAS[tipo]["map"][pk]
    pend = df.copy()
    for c in cols_auto:
        pend[f"_auto_{c}"] = pend[c].eq("")
    ocupados = ocupados_fn()
    guardados, ids_ok, omitidos = 0, [], 0
    ultimo_error: ErrorDatos | None = None
    for _ in range(MAX_INTENTOS_ID):
        if pend.empty:
            ultimo_error = None
            break
        for c in cols_auto:
            pend.loc[pend[f"_auto_{c}"], c] = ""
        pend = asignar(pend, *ocupados)
        filas = mapeo.a_filas_sql(tipo, pend, extras)
        i, fallo = 0, None
        while i < len(filas):
            lote = filas[i:i + BLOQUE_INSERT]
            try:
                repo.insertar(lote)
            except Duplicado as exc:
                fallo = exc
                break
            except ErrorDatos as exc:
                return _Insercion(guardados, ids_ok, omitidos, len(filas) - i, exc)
            guardados += len(lote)
            ids_ok += [str(f[pk_sql]) for f in lote]
            i += len(lote)
        if fallo is None:
            pend = pend.iloc[0:0]
            ultimo_error = None
            break
        pend = pend.iloc[i:].copy()
        ocupados = ocupados_fn()
        ya = pend[pk].isin(ocupados[0]) & ~pend[f"_auto_{pk}"]
        omitidos += int(ya.sum())
        pend = pend[~ya]
        ultimo_error = fallo
    if pend.empty:
        ultimo_error = None
    return _Insercion(guardados, ids_ok, omitidos, len(pend), ultimo_error)


def _cerrar_carga(sesion: Sesion, tipo: str, ins: _Insercion, omitidos_previos: int, recibidos: int,
                  origen: str, archivo: str | None, avisos: list[str]) -> Resultado:
    omitidos = omitidos_previos + ins.omitidos
    if ins.guardados or omitidos_previos:
        datos.invalidar(tipo)
    if ins.guardados:
        _historial(sesion, tipo, origen, archivo, recibidos, ins.guardados, omitidos)
        _recordar_carga(tipo, ins.ids)
        auth_servicio.auditar(f"{tipo}_alta", f"origen={origen}; guardados={ins.guardados}; omitidos={omitidos}")
    nombre = NOMBRES[tipo].lower()
    if ins.error is not None:
        return Resultado(False, (
            f"Se guardaron {ins.guardados} de {recibidos} registros de {nombre} y quedaron {ins.pendientes} sin guardar: "
            f"{ins.error}"), guardados=ins.guardados, omitidos=omitidos, avisos=avisos, ids=ins.ids)
    if ins.guardados == 0:
        return Resultado(True, f"No había registros nuevos de {nombre}: los {omitidos} ya existían, no se cambió nada.",
                         omitidos=omitidos, avisos=avisos)
    msg = f"Se guardaron {ins.guardados} registro(s) nuevos de {nombre}."
    if omitidos:
        msg += f" {omitidos} ya existían y se omitieron (no se sobrescriben)."
    return Resultado(True, msg, guardados=ins.guardados, omitidos=omitidos, avisos=avisos, ids=ins.ids)


def _convertir_error(exc: Exception) -> Resultado:
    return Resultado(False, f"No se pudo preparar la información: {exc}")


# ------------------------------------------------------------------- personas
@dataclass
class Previa:
    """Qué pasaría al importar (sin escribir nada): sirve para confirmar antes de guardar."""
    ok: bool
    mensaje: str = ""
    recibidos: int = 0
    nuevos: int = 0
    omitidos: int = 0
    errores: list[dict] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    _df: pd.DataFrame | None = field(default=None, repr=False)


def _preparar_personas(sesion: Sesion, df: pd.DataFrame) -> Previa:
    recibidos = len(df)
    limpio = limpiar_personas(df, generar_ids=False)
    if limpio.empty:
        return Previa(False, "No se encontraron registros con datos para guardar.", recibidos)
    errores = validar_personas(limpio)
    if errores:
        return Previa(False, "Corrige estos datos antes de guardar; no se guardó nada.", recibidos, errores=errores)
    repo = RepoTabla(sesion.cliente, "personas")
    omitidos = 0
    dup_archivo = limpio["id_persona"].ne("") & limpio.duplicated("id_persona", keep="last")
    omitidos += int(dup_archivo.sum())
    limpio = limpio[~dup_archivo]
    existentes = repo.ids()
    ya = limpio["id_persona"].ne("") & limpio["id_persona"].isin(existentes)
    omitidos += int(ya.sum())
    limpio = limpio[~ya].copy()
    extras = _extras(sesion, "personas")
    if "anio_fuente" in extras:
        limpio["anio_fuente"] = "registrado"
        limpio["institucion_fuente"] = "registrado"
    return Previa(True, "", recibidos, len(limpio), omitidos, avisos=[], _df=limpio)


def previsualizar_personas(sesion: Sesion, df: pd.DataFrame) -> Previa:
    _exigir(sesion, "personas", "create")
    return _preparar_personas(sesion, df)


def importar_personas(sesion: Sesion, df: pd.DataFrame, origen: str = "Carga manual",
                      archivo: str | None = None) -> Resultado:
    """Alta de uno o muchos registros de personas (captura manual o carga Excel/CSV)."""
    _exigir(sesion, "personas", "create")
    prev = _preparar_personas(sesion, df)
    if not prev.ok:
        return Resultado(False, prev.mensaje, errores=prev.errores)
    if prev._df is None or prev._df.empty:
        return _cerrar_carga(sesion, "personas", _Insercion(0, [], 0, 0, None), prev.omitidos, prev.recibidos, origen, archivo, [])
    repo = RepoTabla(sesion.cliente, "personas")

    def ocupados():
        return repo.ids(), repo.columna("id_persona_maestro")

    try:
        ins = _insertar_con_reintentos(repo, "personas", prev._df, _extras(sesion, "personas"), "id_persona",
                                       ["id_persona", "id_persona_maestro"], asignar_ids_personas, ocupados)
    except ValueError as exc:
        return _convertir_error(exc)
    return _cerrar_carga(sesion, "personas", ins, prev.omitidos, prev.recibidos, origen, archivo, [])


# ------------------------------------------------------------------- vacantes
def _preparar_vacantes(sesion: Sesion, df: pd.DataFrame) -> Previa:
    recibidos = len(df)
    if not df.empty:  # filas completamente vacías (típico al final de un Excel) no cuentan
        df = df[df.apply(lambda r: any(pd.notna(v) and str(v).strip() != "" for v in r), axis=1)]
    limpio = limpiar_vacantes(df)
    if limpio.empty:
        return Previa(False, "No se encontraron vacantes con datos para guardar.", recibidos)
    errores = validar_vacantes(limpio)
    if errores:
        return Previa(False, "Corrige estos datos antes de guardar; no se guardó nada.", recibidos, errores=errores)
    repo = RepoTabla(sesion.cliente, "vacantes")
    omitidos = 0
    limpio = limpio.copy()
    limpio["_clave"] = clave_duplicado_vacante(limpio)
    dup_archivo = limpio.duplicated("_clave", keep="last")
    omitidos += int(dup_archivo.sum())
    limpio = limpio[~dup_archivo]
    avisos: list[str] = []
    if sesion.puede("vacantes", "view"):
        previas = limpiar_vacantes(datos.crudo(sesion, "vacantes"))
        if not previas.empty:
            ya = limpio["_clave"].isin(set(clave_duplicado_vacante(previas)))
            omitidos += int(ya.sum())
            limpio = limpio[~ya]
    else:
        avisos.append("Tu perfil no puede consultar vacantes: no se pudo comprobar si alguna ya existía.")
    existentes = repo.ids()
    ya_id = limpio["ID Vacante"].ne("") & limpio["ID Vacante"].isin(existentes)
    omitidos += int(ya_id.sum())
    limpio = limpio[~ya_id].drop(columns=["_clave"]).copy()
    extras = _extras(sesion, "vacantes")
    for col in ("fecha_cierre", "municipio_excepcion"):
        if col in df.columns and col not in extras:
            avisos.append(f"La base todavía no tiene la columna «{col}» (migración pendiente): ese dato no se guardará.")
    return Previa(True, "", recibidos, len(limpio), omitidos, avisos=avisos, _df=limpio)


def previsualizar_vacantes(sesion: Sesion, df: pd.DataFrame) -> Previa:
    _exigir(sesion, "vacantes", "create")
    return _preparar_vacantes(sesion, df)


def importar_vacantes(sesion: Sesion, df: pd.DataFrame, origen: str = "Carga manual",
                      archivo: str | None = None) -> Resultado:
    _exigir(sesion, "vacantes", "create")
    prev = _preparar_vacantes(sesion, df)
    if not prev.ok:
        return Resultado(False, prev.mensaje, errores=prev.errores)
    if prev._df is None or prev._df.empty:
        return _cerrar_carga(sesion, "vacantes", _Insercion(0, [], 0, 0, None), prev.omitidos, prev.recibidos, origen, archivo, prev.avisos)
    repo = RepoTabla(sesion.cliente, "vacantes")

    def ocupados():
        return repo.ids(), repo.columna("id_registro_origen")

    try:
        ins = _insertar_con_reintentos(repo, "vacantes", prev._df, _extras(sesion, "vacantes"), "ID Vacante",
                                       ["ID Vacante", "ID Registro Origen"], asignar_ids_vacantes, ocupados)
    except ValueError as exc:
        return _convertir_error(exc)
    return _cerrar_carga(sesion, "vacantes", ins, prev.omitidos, prev.recibidos, origen, archivo, prev.avisos)


# -------------------------------------------------------------- vinculaciones
def importar_vinculaciones(sesion: Sesion, df: pd.DataFrame, origen: str = "Captura manual",
                           archivo: str | None = None) -> Resultado:
    _exigir(sesion, "vinculaciones", "create")
    recibidos = len(df)
    personas = datos.crudo(sesion, "personas") if sesion.puede("personas", "view") else None
    limpio = limpiar_vinculaciones(df, personas, generar_ids=False)
    if limpio.empty:
        return Resultado(False, "No se encontraron seguimientos para guardar.")
    ahora = ahora_mx().strftime("%Y-%m-%d %H:%M:%S")
    limpio["fecha_actualizacion"] = ahora
    errores = validar_vinculaciones(limpio)
    if errores:
        return Resultado(False, "Corrige estos datos antes de guardar; no se guardó nada.", errores=errores)

    repo = RepoTabla(sesion.cliente, "vinculaciones")
    omitidos = 0
    dup_archivo = limpio["id_vinculacion"].ne("") & limpio.duplicated("id_vinculacion", keep="last")
    omitidos += int(dup_archivo.sum())
    limpio = limpio[~dup_archivo]
    existentes = repo.ids()
    ya = limpio["id_vinculacion"].ne("") & limpio["id_vinculacion"].isin(existentes)
    omitidos += int(ya.sum())
    limpio = limpio[~ya].copy()
    if limpio.empty:
        return _cerrar_carga(sesion, "vinculaciones", _Insercion(0, [], 0, 0, None), omitidos, recibidos, origen, archivo, [])

    def ocupados():
        ids = repo.ids()
        return ids, ids

    def asignar(d, ids, _sec):
        return asignar_ids_vinculaciones(d, ids)

    try:
        ins = _insertar_con_reintentos(repo, "vinculaciones", limpio, set(), "id_vinculacion",
                                       ["id_vinculacion"], asignar, ocupados)
    except ValueError as exc:
        return _convertir_error(exc)
    return _cerrar_carga(sesion, "vinculaciones", ins, omitidos, recibidos, origen, archivo, [])


# --------------------------------------------------------------------- edición
def _limpiar_y_validar(tipo: str, df: pd.DataFrame):
    if tipo == "personas":
        limpio = limpiar_personas(df, generar_ids=False)
        return limpio, validar_personas(limpio)
    if tipo == "vacantes":
        limpio = limpiar_vacantes(df)
        return limpio, validar_vacantes(limpio)
    limpio = limpiar_vinculaciones(df, None, generar_ids=False)
    return limpio, validar_vinculaciones(limpio)


def editar(sesion: Sesion, tipo: str, id_valor: str, nuevos: dict) -> Resultado:
    """UPDATE por ID de SOLO las columnas que la persona cambió realmente."""
    _exigir(sesion, tipo, "edit")
    cfg = mapeo.TABLAS[tipo]
    pk_local = next(k for k, v in cfg["map"].items() if v == cfg["pk"])
    repo = RepoTabla(sesion.cliente, tipo)
    actual_sql = repo.obtener(id_valor)
    if actual_sql is None:
        return Resultado(False, "El registro ya no existe (alguien más pudo haberlo eliminado). Actualiza la lista.")
    actual = mapeo.a_dataframe(tipo, [actual_sql]).iloc[0].to_dict()
    permitidas = set(mapeo.columnas_locales(tipo, True))
    tocados = [c for c, v in nuevos.items() if c in permitidas and not _igual(v, actual.get(c))]
    if pk_local in tocados:
        return Resultado(False, "El identificador del registro no se puede cambiar.")
    if not tocados:
        return Resultado(True, "No hay cambios que guardar.")

    fila = {**actual, **{c: nuevos[c] for c in tocados}}
    limpio, errores = _limpiar_y_validar(tipo, pd.DataFrame([fila]))
    if errores:
        return Resultado(False, "Corrige estos datos antes de guardar; no se guardó nada.", errores=errores)

    extras = _extras(sesion, tipo)
    avisos = []
    try:
        fila_sql = mapeo.a_filas_sql(tipo, limpio, extras)[0]
    except ValueError as exc:
        return _convertir_error(exc)
    cambios = {}
    for c in tocados:
        remoto = cfg["map"].get(c) or cfg["opcionales"].get(c)
        if remoto in fila_sql:
            cambios[remoto] = fila_sql[remoto]
        elif c in cfg["opcionales"]:
            avisos.append(f"La base todavía no tiene la columna «{c}» (migración pendiente): ese cambio no se guardó.")
    if tipo == "personas" and "anio_fuente" in extras:
        if "Año" in tocados:
            cambios["anio_fuente"] = "registrado"
        if "Institución" in tocados:
            cambios["institucion_fuente"] = "registrado"
    if tipo == "vinculaciones":
        cambios["fecha_actualizacion"] = ahora_mx().strftime("%Y-%m-%d %H:%M:%S")
    if not cambios:
        return Resultado(False, "Ninguno de los cambios se pudo guardar.", avisos=avisos)
    try:
        repo.actualizar(id_valor, cambios)
    except ErrorDatos as exc:
        return Resultado(False, str(exc), avisos=avisos)
    datos.invalidar(tipo)
    auth_servicio.auditar(f"{tipo}_edicion", f"id={id_valor}; campos={','.join(sorted(cambios))}")
    return Resultado(True, "Registro actualizado.", guardados=1, ids=[str(id_valor)], avisos=avisos)


# ----------------------------------------------------------------------- bajas
def impacto_eliminacion(sesion: Sesion, tipo: str, id_valor: str) -> list[str]:
    """Frases que explican qué se va a eliminar y qué NO (para el cuadro de confirmación)."""
    fila = RepoTabla(sesion.cliente, tipo).obtener(id_valor)
    if fila is None:
        return ["El registro ya no existe."]
    if tipo == "personas":
        maestro = fila.get("id_persona_maestro")
        lineas = [f"Se eliminará el registro histórico {id_valor} de {fila.get('nombre') or 'la persona'}."]
        try:
            otros = [r for r in RepoTabla(sesion.cliente, "personas").listar() if r.get("id_persona_maestro") == maestro]
            if len(otros) <= 1:
                lineas.append("Es el ÚLTIMO registro de esta persona: dejará de aparecer en la plataforma.")
            else:
                lineas.append(f"La persona conserva sus otros {len(otros) - 1} registro(s).")
            if sesion.puede("vinculaciones", "view"):
                n = sum(1 for r in RepoTabla(sesion.cliente, "vinculaciones").listar() if r.get("id_persona_maestro") == maestro)
                if n:
                    lineas.append(f"Sus {n} seguimiento(s) de vinculación NO se eliminan; quedarán sin registro histórico asociado.")
        except ErrorDatos:
            pass
        return lineas
    if tipo == "vacantes":
        return [f"Se eliminará la vacante {id_valor} ({fila.get('puesto_original') or fila.get('tipo_vacante') or 'sin puesto'}) de {fila.get('empresa') or 'empresa no registrada'}."]
    return [f"Se eliminará el seguimiento {id_valor} de {fila.get('nombre_persona') or 'la persona'} con {fila.get('empresa') or 'empresa no registrada'}."]


def papelera() -> list[dict]:
    return st.session_state.setdefault("_papelera", [])


def eliminar(sesion: Sesion, tipo: str, id_valor: str) -> Resultado:
    _exigir(sesion, tipo, "delete")
    try:
        fila = RepoTabla(sesion.cliente, tipo).eliminar(id_valor)
    except ErrorDatos as exc:
        return Resultado(False, str(exc))
    p = papelera()
    p.insert(0, {"tipo": tipo, "id": str(id_valor), "fila": fila, "ts": ahora_mx().strftime("%H:%M:%S")})
    del p[MAX_PAPELERA:]
    datos.invalidar(tipo)
    auth_servicio.auditar(f"{tipo}_baja", f"id={id_valor}")
    return Resultado(True, "Registro eliminado. Puedes restaurarlo desde la papelera mientras no cierres la sesión.",
                     guardados=1, ids=[str(id_valor)])


def restaurar(sesion: Sesion, indice: int) -> Resultado:
    p = papelera()
    if not (0 <= indice < len(p)):
        return Resultado(False, "Ese registro ya no está en la papelera.")
    item = p[indice]
    _exigir(sesion, item["tipo"], "create")
    try:
        RepoTabla(sesion.cliente, item["tipo"]).insertar([item["fila"]])
    except Duplicado:
        return Resultado(False, "Ya existe un registro con ese identificador; no se restauró para no duplicarlo.")
    except ErrorDatos as exc:
        return Resultado(False, str(exc))
    del p[indice]
    datos.invalidar(item["tipo"])
    auth_servicio.auditar(f"{item['tipo']}_restauracion", f"id={item['id']}")
    return Resultado(True, "Registro restaurado.", guardados=1, ids=[item["id"]])


def deshacer_ultima_carga(sesion: Sesion) -> Resultado:
    """Elimina EXACTAMENTE los registros que insertó la última carga de esta sesión."""
    carga = ultima_carga()
    if not carga:
        return Resultado(False, "No hay una carga reciente que deshacer en esta sesión.")
    tipo = carga["tipo"]
    _exigir(sesion, tipo, "delete")
    try:
        borradas = RepoTabla(sesion.cliente, tipo).eliminar_varios(carga["ids"])
    except ErrorDatos as exc:
        return Resultado(False, str(exc))
    st.session_state.pop("_ultima_carga", None)
    datos.invalidar(tipo)
    auth_servicio.auditar(f"{tipo}_deshacer_carga", f"eliminados={len(borradas)} de {len(carga['ids'])}")
    if len(borradas) != len(carga["ids"]):
        return Resultado(True, f"Se deshizo parcialmente: {len(borradas)} de {len(carga['ids'])} registros "
                               "(el resto ya no existía o no tienes permiso sobre ellos).", guardados=len(borradas))
    return Resultado(True, f"Carga deshecha: se eliminaron los {len(borradas)} registros que se acababan de guardar.",
                     guardados=len(borradas))


# ------------------------------------------------------- cambios en bloque
def cambiar_estado_vacantes(sesion: Sesion, ids: list[str], estado: str) -> Resultado:
    """Cambia el Estado (Activa/Inactiva) de varias vacantes de una vez (revisión de vigencia)."""
    _exigir(sesion, "vacantes", "edit")
    if estado not in ESTADOS_VACANTE:
        return Resultado(False, "El estado debe ser Activa o Inactiva.")
    ids = [str(i) for i in dict.fromkeys(ids)]
    if not ids:
        return Resultado(False, "No hay vacantes seleccionadas.")
    try:
        n = RepoTabla(sesion.cliente, "vacantes").actualizar_varios(ids, {"estado": estado})
    except ErrorDatos as exc:
        return Resultado(False, str(exc))
    datos.invalidar("vacantes")
    auth_servicio.auditar("vacantes_estado_en_bloque", f"estado={estado}; solicitadas={len(ids)}; modificadas={n}")
    if n != len(ids):
        return Resultado(True, f"Se actualizaron {n} de {len(ids)} vacantes (el resto ya no existía o no tienes permiso).", guardados=n)
    return Resultado(True, f"Se marcaron {n} vacante(s) como {estado}.", guardados=n, ids=ids)
