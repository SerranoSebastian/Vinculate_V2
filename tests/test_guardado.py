"""Servicio de guardado contra un Supabase falso en memoria (sin red)."""
import pandas as pd
import pytest

from tests.fakes import FakeAPIError, FakeCliente
from vinculate.auth.sesion import Sesion
from vinculate.repositories.errores import SinPermiso
from vinculate.services import guardado


def _permisos(**mods):
    out = {}
    for m, acciones in mods.items():
        out[m] = {f"can_{a}": True for a in acciones}
    return out


def _sesion(cliente, **mods):
    mods = mods or {"personas": ("view", "create", "edit", "delete"),
                    "vacantes": ("view", "create", "edit", "delete"),
                    "vinculaciones": ("view", "create", "edit", "delete"),
                    "administracion": ("view", "create")}
    return Sesion(user_id="u-1", email="capturista@sedeco.test",
                  perfil={"status": "active", "role": "collaborator", "display_name": "Capturista"},
                  permisos=_permisos(**mods), device_id="d" * 8 + "-0000-4000-8000-" + "0" * 12, cliente=cliente)


def _persona(**kw):
    base = {"id_persona": "", "id_persona_maestro": "", "nombre": "Ana Prueba", "sexo": "Mujer", "edad": 25,
            "escolaridad": "Licenciatura", "carrera": "Contaduría", "Institución": "UATx", "municipio": "Apizaco",
            "vinculacion": "Atención", "fecha_registro": "2026-01-10"}
    base.update(kw)
    return base


@pytest.fixture
def db():
    c = FakeCliente()
    c.tablas["personas"] = [
        {"id_persona": "A-00001-00001", "id_persona_maestro": "PER-0001", "nombre": "Luis Existente", "edad": 30,
         "vinculacion": "Atención", "fecha_registro": "2025-03-01", "anio": 2025, "municipio": "Tlaxcala",
         "estatus_vinculacion": "Vinculado"},
        {"id_persona": "I-00001-00002", "id_persona_maestro": "PER-0002", "nombre": "Marta Existente", "edad": 41,
         "vinculacion": "Inserción Laboral", "fecha_registro": "2025-04-01", "anio": 2025, "municipio": "Apizaco",
         "estatus_vinculacion": "Vinculado"},
    ]
    return c


# ----------------------------------------------------------------- permisos
def test_sin_permiso_de_alta_no_toca_la_base(db):
    s = _sesion(db, personas=("view",))
    with pytest.raises(SinPermiso):
        guardado.importar_personas(s, pd.DataFrame([_persona()]))
    assert ("personas", "insert") not in db.llamadas


def test_sin_permiso_de_baja(db):
    s = _sesion(db, personas=("view", "create"))
    with pytest.raises(SinPermiso):
        guardado.eliminar(s, "personas", "A-00001-00001")
    assert len(db.tablas["personas"]) == 2


# ------------------------------------------------------------------ personas
def test_alta_genera_ids_contra_la_base_real(db):
    s = _sesion(db)
    r = guardado.importar_personas(s, pd.DataFrame([_persona(), _persona(nombre="Beto Nuevo")]))
    assert r.ok and r.guardados == 2 and r.omitidos == 0
    nuevos = db.tablas["personas"][2:]
    assert [f["id_persona_maestro"] for f in nuevos] == ["PER-0003", "PER-0004"]
    assert nuevos[0]["id_persona"].startswith("A-00002-")
    assert len({f["id_persona"] for f in db.tablas["personas"]}) == 4
    assert nuevos[0]["anio"] == 2026  # año derivado de la fecha


def test_reimportar_no_duplica_ni_sobrescribe(db):
    s = _sesion(db)
    original = list(db.tablas["personas"])
    df = pd.DataFrame([_persona(id_persona="A-00001-00001", id_persona_maestro="PER-0001", nombre="OTRO NOMBRE"),
                       _persona(id_persona="A-00009-00009", id_persona_maestro="PER-0009", nombre="Nuevo Con ID")])
    r = guardado.importar_personas(s, df, origen="Carga Excel", archivo="x.xlsx")
    assert r.ok and r.guardados == 1 and r.omitidos == 1
    assert db.tablas["personas"][0] == original[0]  # no se sobrescribió
    assert db.tablas["personas"][0]["nombre"] == "Luis Existente"
    r2 = guardado.importar_personas(s, df)
    assert r2.ok and r2.guardados == 0 and r2.omitidos == 2
    assert len(db.tablas["personas"]) == 3


def test_duplicados_dentro_del_mismo_archivo(db):
    s = _sesion(db)
    df = pd.DataFrame([_persona(id_persona="A-00050-00050", id_persona_maestro="PER-0050"),
                       _persona(id_persona="A-00050-00050", id_persona_maestro="PER-0050")])
    r = guardado.importar_personas(s, df)
    assert r.guardados == 1 and r.omitidos == 1


def test_carrera_de_ids_se_recalcula(db, monkeypatch):
    """Otra persona guarda entre que calculamos los IDs y que insertamos (23505): se reintenta."""
    s = _sesion(db)
    repo_ids = guardado.RepoTabla.ids
    estado = {"n": 0}

    def ids_con_carrera(self):
        out = repo_ids(self)
        estado["n"] += 1
        if estado["n"] == 1 and self.clave == "personas":
            # La otra persona toma justo el siguiente ID antes de nuestro insert.
            db.tablas["personas"].append({"id_persona": "A-00002-00003", "id_persona_maestro": "PER-0003",
                                          "nombre": "Carrera", "estatus_vinculacion": "Vinculado"})
        return out

    monkeypatch.setattr(guardado.RepoTabla, "ids", ids_con_carrera)
    r = guardado.importar_personas(s, pd.DataFrame([_persona()]))
    assert r.ok and r.guardados == 1, r.mensaje
    ids = [f["id_persona"] for f in db.tablas["personas"]]
    assert len(ids) == len(set(ids)) == 4


def test_validacion_rechaza_todo_sin_guardar(db):
    s = _sesion(db)
    r = guardado.importar_personas(s, pd.DataFrame([_persona(), _persona(nombre="", edad=200)]))
    assert not r.ok and r.errores
    assert len(db.tablas["personas"]) == 2


def test_fallo_a_medias_se_informa_con_honestidad(db):
    s = _sesion(db)
    from vinculate.repositories import errores
    db.fallo_siguiente = (("personas", "insert"), FakeAPIError("23514", "check constraint"))
    r = guardado.importar_personas(s, pd.DataFrame([_persona()]))
    assert not r.ok and r.guardados == 0 and "sin guardar" in r.mensaje


# ------------------------------------------------------------------- edición
def test_editar_solo_toca_lo_cambiado(db):
    s = _sesion(db)
    r = guardado.editar(s, "personas", "A-00001-00001", {"telefono": "2461234567", "nombre": "Luis Existente"})
    assert r.ok and r.guardados == 1
    fila = db.tablas["personas"][0]
    assert fila["telefono"] == "2461234567"
    assert fila["municipio"] == "Tlaxcala" and fila["edad"] == 30


def test_editar_sin_cambios(db):
    s = _sesion(db)
    r = guardado.editar(s, "personas", "A-00001-00001", {"nombre": "Luis Existente", "edad": 30})
    assert r.ok and r.guardados == 0 and "No hay cambios" in r.mensaje


def test_editar_no_permite_cambiar_id(db):
    s = _sesion(db)
    r = guardado.editar(s, "personas", "A-00001-00001", {"id_persona": "OTRO"})
    assert not r.ok


def test_editar_valida_edad(db):
    s = _sesion(db)
    r = guardado.editar(s, "personas", "A-00001-00001", {"edad": 300})
    assert not r.ok and r.errores


def test_editar_sin_permiso_rls_se_reporta(db):
    db.permisos["personas"] = {"select", "insert"}  # RLS filtra el update en silencio
    s = _sesion(db)
    r = guardado.editar(s, "personas", "A-00001-00001", {"telefono": "1"})
    assert not r.ok and "No se modificó" in r.mensaje


def test_editar_registro_inexistente(db):
    s = _sesion(db)
    r = guardado.editar(s, "personas", "NO-EXISTE", {"telefono": "1"})
    assert not r.ok


# -------------------------------------------------------------------- bajas
def test_baja_papelera_y_restaurar(db, estado_sesion):
    s = _sesion(db)
    r = guardado.eliminar(s, "personas", "A-00001-00001")
    assert r.ok and len(db.tablas["personas"]) == 1
    assert guardado.papelera()[0]["id"] == "A-00001-00001"
    r2 = guardado.restaurar(s, 0)
    assert r2.ok and len(db.tablas["personas"]) == 2 and not guardado.papelera()


def test_restaurar_no_duplica(db):
    s = _sesion(db)
    guardado.eliminar(s, "personas", "A-00001-00001")
    db.tablas["personas"].append({"id_persona": "A-00001-00001", "id_persona_maestro": "PER-0001", "nombre": "X"})
    r = guardado.restaurar(s, 0)
    assert not r.ok


def test_baja_con_rls_que_oculta_la_fila(db):
    db.permisos["personas"] = {"select", "insert", "update"}
    s = _sesion(db)
    r = guardado.eliminar(s, "personas", "A-00001-00001")
    assert not r.ok and len(db.tablas["personas"]) == 2


def test_impacto_de_eliminar_ultimo_registro(db):
    s = _sesion(db)
    lineas = guardado.impacto_eliminacion(s, "personas", "A-00001-00001")
    assert any("ÚLTIMO" in x for x in lineas)


def test_deshacer_carga(db):
    s = _sesion(db)
    guardado.importar_personas(s, pd.DataFrame([_persona(), _persona(nombre="Otro")]))
    assert len(db.tablas["personas"]) == 4
    r = guardado.deshacer_ultima_carga(s)
    assert r.ok and len(db.tablas["personas"]) == 2
    assert {f["id_persona"] for f in db.tablas["personas"]} == {"A-00001-00001", "I-00001-00002"}


def test_deshacer_carga_requiere_permiso_de_baja(db):
    s = _sesion(db, personas=("view", "create"))
    guardado.importar_personas(s, pd.DataFrame([_persona()]))
    with pytest.raises(SinPermiso):
        guardado.deshacer_ultima_carga(s)


# ------------------------------------------------------------------ vacantes
def _vacante(**kw):
    base = {"ID Vacante": "", "ID Registro Origen": "", "Actividad": "", "Fecha": "2026-02-01", "Empresa": "Textiles SA",
            "Sector Empresa": "Textil", "Puesto Original": "Ayudante de produccion", "Tipo de Vacante": "Ayudante de produccion",
            "Tipo de Oportunidad": "Empleo", "Área de Oportunidad": "Producción", "Estado": "Activa"}
    base.update(kw)
    return base


def test_vacantes_ids_y_duplicados(db):
    db.tablas["vacantes"] = [{"id_vacante": "VAC-0010", "id_registro_origen": "ORI-0010", "fecha": "2026-02-01",
                              "empresa": "Textiles SA", "puesto_original": "Ayudante de produccion",
                              "tipo_vacante": "Ayudante de Producción", "tipo_oportunidad": "Empleo",
                              "area_oportunidad": "Producción", "estado": "Activa", "categoria_puesto": "Producción y Operaciones",
                              "descripcion": "", "link_publicacion": ""}]
    s = _sesion(db)
    df = pd.DataFrame([_vacante(), _vacante(Empresa="Otra SA")])
    r = guardado.importar_vacantes(s, df)
    assert r.ok and r.guardados == 1 and r.omitidos == 1, r.mensaje
    assert db.tablas["vacantes"][-1]["id_vacante"] == "VAC-0011"
    assert db.tablas["vacantes"][-1]["id_registro_origen"] == "ORI-0011"


def test_vacantes_fila_vacia_final_no_es_error(db):
    s = _sesion(db)
    df = pd.DataFrame([_vacante(), {k: None for k in _vacante()}])
    r = guardado.importar_vacantes(s, df)
    assert r.ok and r.guardados == 1


def test_vacantes_columna_fecha_cierre_ausente_avisa(db):
    s = _sesion(db)
    df = pd.DataFrame([_vacante(fecha_cierre="2026-12-31")])
    r = guardado.importar_vacantes(s, df)
    assert r.ok and any("fecha_cierre" in a for a in r.avisos)
    assert "fecha_cierre" not in db.tablas["vacantes"][0]


def test_vacantes_fecha_cierre_si_existe_se_guarda(db):
    db.tablas["vacantes"] = [{"id_vacante": "VAC-0001", "id_registro_origen": "ORI-0001", "fecha": "2025-01-01",
                              "empresa": "Z", "tipo_vacante": "P", "tipo_oportunidad": "Empleo", "estado": "Activa",
                              "fecha_cierre": None}]
    s = _sesion(db)
    r = guardado.importar_vacantes(s, pd.DataFrame([_vacante(fecha_cierre="2026-12-31")]))
    assert r.ok and not r.avisos
    assert db.tablas["vacantes"][-1]["fecha_cierre"] == "2026-12-31"


# ------------------------------------------------------------- vinculaciones
def test_vinculacion_alta_y_edicion(db):
    s = _sesion(db)
    df = pd.DataFrame([{"id_persona_maestro": "PER-0001", "nombre_persona": "Luis Existente", "empresa": "Textiles SA",
                        "estatus": "Vinculado", "fecha_vinculacion": "2026-03-01"}])
    r = guardado.importar_vinculaciones(s, df)
    assert r.ok and r.guardados == 1
    vid = db.tablas["vinculaciones"][0]["id_vinculacion"]
    assert vid.startswith("VIN-")
    r2 = guardado.editar(s, "vinculaciones", vid, {"estatus": "Colocado", "fecha_colocacion": "2026-04-01"})
    assert r2.ok
    fila = db.tablas["vinculaciones"][0]
    assert fila["estatus"] == "Colocado" and fila["fecha_colocacion"] == "2026-04-01" and fila["fecha_actualizacion"]


def test_vinculacion_exige_persona(db):
    s = _sesion(db)
    r = guardado.importar_vinculaciones(s, pd.DataFrame([{"empresa": "X", "estatus": "Vinculado"}]))
    assert not r.ok and r.errores


def test_vinculacion_colocacion_no_antes_de_vinculacion(db):
    s = _sesion(db)
    df = pd.DataFrame([{"id_persona_maestro": "PER-0001", "empresa": "X", "estatus": "Colocado",
                        "fecha_vinculacion": "2026-05-01", "fecha_colocacion": "2026-04-01"}])
    r = guardado.importar_vinculaciones(s, df)
    assert not r.ok


# --------------------------------------------------------------- historial/auditoría
def test_historial_y_auditoria(db, estado_sesion):
    s = _sesion(db)
    estado_sesion["_sesion_v2"] = s
    guardado.importar_personas(s, pd.DataFrame([_persona()]), origen="Carga Excel", archivo="a.xlsx")
    h = db.tablas["historial_cargas"][0]
    assert h["usuario"] == "capturista@sedeco.test" and h["registros_guardados"] == 1 and h["archivo_origen"] == "a.xlsx"
    a = db.tablas["app_audit_log"][0]
    assert a["action"] == "personas_alta" and "guardados=1" in a["detail"]
    # La auditoría no guarda nombres ni datos personales
    assert "Ana" not in a["detail"]


def test_cambiar_estado_vacantes_en_bloque(db):
    db.tablas["vacantes"] = [{"id_vacante": f"VAC-{i:04d}", "estado": "Activa", "empresa": "X"} for i in range(1, 6)]
    s = _sesion(db)
    r = guardado.cambiar_estado_vacantes(s, ["VAC-0001", "VAC-0003", "VAC-9999"], "Inactiva")
    assert r.ok and r.guardados == 2 and "2 de 3" in r.mensaje
    assert [f["estado"] for f in db.tablas["vacantes"]] == ["Inactiva", "Activa", "Inactiva", "Activa", "Activa"]
    assert not guardado.cambiar_estado_vacantes(s, ["VAC-0002"], "Cerrada").ok
    s2 = _sesion(db, vacantes=("view",))
    with pytest.raises(SinPermiso):
        guardado.cambiar_estado_vacantes(s2, ["VAC-0002"], "Inactiva")


def test_previsualizar_no_escribe(db):
    s = _sesion(db)
    df = pd.DataFrame([_persona(), _persona(id_persona="A-00001-00001", id_persona_maestro="PER-0001")])
    prev = guardado.previsualizar_personas(s, df)
    assert prev.ok and prev.nuevos == 1 and prev.omitidos == 1 and prev.recibidos == 2
    assert len(db.tablas["personas"]) == 2 and ("personas", "insert") not in db.llamadas
