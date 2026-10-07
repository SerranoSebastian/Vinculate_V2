"""Datos y cliente de demostración 100 % SINTÉTICOS para pruebas de interfaz (no hay personas reales)."""
from __future__ import annotations

import random
from types import SimpleNamespace

from tests.fakes import FakeCliente
from vinculate.auth.sesion import Sesion
from vinculate.core.constantes import MODULES

NOMBRES = ["Ana", "Luis", "Marta", "Pedro", "Sofía", "Diego", "Valeria", "Jorge", "Elena", "Raúl", "Camila", "Iván"]
APELLIDOS = ["Pérez", "Hernández", "López", "Martínez", "Sánchez", "Ramírez", "Flores", "Cruz", "Morales", "Ortega"]
MUNICIPIOS = ["Apizaco", "Tlaxcala", "Huamantla", "Chiautempan", "Zacatelco", "Calpulalpan", "Tlaxco", "San Pablo del Monte"]
CARRERAS = ["Ingeniería Industrial", "Contaduría", "Administración", "Ingeniería Mecatrónica", "Derecho"]
INSTITUCIONES = ["UATx", "UPTx", "UTT", "ITA", "UNAM"]
EMPRESAS = ["Greenbrier", "SIMEC", "La Luz", "Lear Corporation", "Empresa Sin Región SA", "Providencia"]
TIPOS = ["Inserción Laboral", "Atención", "Prácticas Profesionales", "Servicio Social"]


def pers(n=60, semilla=7):
    r = random.Random(semilla)
    filas = []
    for i in range(1, n + 1):
        maestro = f"PER-{(i % 40) + 1:04d}"
        tipo = r.choice(TIPOS)
        pref = {"Inserción Laboral": "I", "Atención": "A", "Prácticas Profesionales": "P", "Servicio Social": "S"}[tipo]
        filas.append({
            "id_persona": f"{pref}-{i:05d}-{(i % 40) + 1:05d}", "id_persona_maestro": maestro,
            "nombre": f"{r.choice(NOMBRES)} {r.choice(APELLIDOS)} {(i % 40) + 1}", "sexo": r.choice(["Mujer", "Hombre"]),
            "edad": r.randint(17, 55), "escolaridad": r.choice(["Superior", "Media Superior"]),
            "carrera": r.choice(CARRERAS), "institucion": r.choice(INSTITUCIONES), "municipio": r.choice(MUNICIPIOS + ["Puebla", ""]),
            "telefono": f"246{r.randint(1000000, 9999999)}", "correo": f"p{i}@example.test", "vinculacion": tipo,
            "fecha_registro": f"{r.choice([2023, 2024, 2025, 2026])}-{r.randint(1, 12):02d}-{r.randint(1, 28):02d}",
            "anio": r.choice([2023, 2024, 2025, 2026]), "estatus_vinculacion": "Vinculado", "grupo_prioritario": "Jóvenes",
            "area_carrera": "Ingenierías", "actualizado_en": "2026-10-01T10:00:00+00:00",
        })
    return filas


def vacs(n=14, semilla=11):
    r = random.Random(semilla)
    filas = []
    for i in range(1, n + 1):
        filas.append({
            "id_vacante": f"VAC-{i:04d}", "id_registro_origen": f"ORI-{i:04d}", "actividad": "Publicación", "fecha": f"2026-0{r.randint(1, 9)}-1{r.randint(0, 9)}",
            "empresa": r.choice(EMPRESAS), "sector_empresa": "Manufactura", "puesto_original": "Operador de Producción",
            "tipo_vacante": r.choice(["Operador de Producción", "Soldador", "Técnico de Calidad"]), "categoria_puesto": "Operativo",
            "tipo_oportunidad": r.choice(["Empleo", "Prácticas Profesionales"]), "area_oportunidad": "Manufactura y Producción",
            "estado": r.choice(["Activa", "Inactiva"]), "actualizado_en": "2026-10-01T10:00:00+00:00",
        })
    return filas


def vincs():
    return [{"id_vinculacion": f"VIN-{i:04d}", "id_persona_maestro": f"PER-{i:04d}", "nombre_persona": f"Persona {i}", "empresa": "Greenbrier",
             "sector_empresa": "Manufactura", "tipo_vacante": "Soldador", "area_oportunidad": "Manufactura y Producción",
             "estatus": r, "fecha_vinculacion": "2026-08-10", "observaciones": "", "responsable": "Capturista",
             "actualizado_en": "2026-10-01T10:00:00+00:00"} for i, r in enumerate(["Vinculado", "Colocado", "No vinculado"], start=1)]


def permisos(admin=False, **mods):
    out = {}
    for m in MODULES:
        acciones = mods.get(m, ())
        out[m] = {"module_key": m, **{f"can_{a}": (admin or a in acciones) for a in ("view", "create", "edit", "delete", "export")}}
    return out


def cliente_demo(**kw) -> FakeCliente:
    c = FakeCliente(pks={"app_profiles": "user_id", "app_permissions": "module_key", "app_priorities": "id",
                         "catalogo_empresas": "nombre", "app_devices": "device_id", "app_settings": "key",
                         "persona_disponibilidad": "id_persona_maestro"})
    c.tablas["personas"] = pers()
    c.tablas["vacantes"] = vacs()
    c.tablas["vinculaciones"] = vincs()
    c.tablas["catalogo_empresas"] = [{"nombre": "Greenbrier", "sector": "Manufactura", "activo": True}]
    c.tablas["app_profiles"] = [{"user_id": "u-admin", "email": "admin@sedeco.test", "display_name": "Admin", "role": "admin",
                                 "status": "active", "created_at": "2026-01-01T00:00:00+00:00"},
                                {"user_id": "u-col", "email": "col@sedeco.test", "display_name": "Colaboradora", "role": "collaborator",
                                 "status": "active", "created_at": "2026-02-01T00:00:00+00:00"}]
    c.tablas["app_audit_log"] = [{"id": 1, "created_at": "2026-10-01T10:00:00+00:00", "email": "admin@sedeco.test", "action": "login", "detail": "ok"}]
    c.tablas["app_devices"] = [{"user_id": "u-col", "device_id": "dev-1", "hostname": "Chrome en Windows", "os_name": "Windows",
                                "app_version": "2.0.0", "authorized": True, "last_seen": "2026-10-01T10:00:00+00:00"}]
    for k, v in kw.items():
        c.tablas[k] = v
    return c


def sesion_demo(cliente=None, admin=True, **mods) -> Sesion:
    cliente = cliente or cliente_demo()
    return Sesion(user_id="u-admin" if admin else "u-col", email="admin@sedeco.test",
                  perfil={"status": "active", "role": "admin" if admin else "collaborator", "display_name": "Admin Demo"},
                  permisos=permisos(admin=admin, **mods), device_id="11111111-1111-4111-8111-111111111111", cliente=cliente)
