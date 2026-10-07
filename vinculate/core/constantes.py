"""Constantes de dominio de Vincúlate SEDECO (sin dependencias de Streamlit)."""
from __future__ import annotations

# Texto único para todo dato faltante que se muestre al usuario. Nunca se
# muestra NaN, None, <NA> ni NaT.
SIN_DATO = "Información no disponible"

# Módulos y acciones del modelo de permisos (idéntico al de la base de datos).
MODULES = {
    "inicio": "Inicio",
    "personas": "Personas",
    "vacantes": "Vacantes",
    "vinculaciones": "Vinculaciones",
    "explorador": "Explorador general",
    "ridet": "Análisis territorial RIDET",
    "administracion": "Administración",
    "usuarios": "Usuarios y permisos",
    "dispositivos": "Computadoras autorizadas",
    "prioridades": "Prioridades y recordatorios",
    "auditoria": "Auditoría",
    "respaldos": "Respaldos",
}
ACTIONS = ("view", "create", "edit", "delete", "export")

# Una fila de PERSONAS representa una vinculación histórica.
#   id_persona          = ID del registro/vinculación histórica
#   id_persona_maestro  = ID permanente de la persona real
PERSONAS_COLS = [
    "id_persona", "id_persona_maestro", "nombre", "sexo", "edad", "escolaridad",
    "carrera", "Institución", "id_institucion", "municipio", "id_municipio",
    "telefono", "correo", "grupo_prioritario", "vinculacion", "fecha_registro",
    "Año", "area_carrera", "estatus_vinculacion",
]
# Columnas que existen solo después de aplicar migraciones posteriores (V005).
PERSONAS_COLS_OPCIONALES = ["anio_fuente", "institucion_fuente"]

VACANTES_COLS = [
    "ID Vacante", "ID Registro Origen", "Actividad", "Fecha", "Empresa", "Sector Empresa",
    "Puesto Original", "Tipo de Vacante", "Categoría de Puesto",
    "Tipo de Oportunidad", "Área de Oportunidad", "Descripción",
    "Requisitos", "Beneficios", "Link de la Publicación", "Estado",
]
# Opcionales: V007 (fecha_cierre) y V004 (municipio_excepcion).
VACANTES_COLS_OPCIONALES = ["fecha_cierre", "municipio_excepcion"]
ESTADOS_VACANTE = ["Activa", "Inactiva"]
TIPOS_OPORTUNIDAD = ["Empleo", "Prácticas Profesionales", "Servicio Social"]

# Variantes claras que deben resolverse siempre al mismo nombre.
ALIASES_PUESTOS_VACANTES = {
    "ayudante general": "Ayudante General",
    "ayudantes generales": "Ayudante General",
    "auxiliares generales": "Ayudante General",
    "soldador": "Soldador", "soldadores": "Soldador",
    "electromecanico": "Electromecánico", "electromecanicos": "Electromecánico",
    "operadores de costura": "Operador de Costura", "costureros": "Operador de Costura",
    "inspector de calidad": "Inspector de Calidad",
    "supervisor de mantenimiento": "Supervisor de Mantenimiento",
    "tecnico de mantenimiento": "Técnico de Mantenimiento",
    "tecnico en mantenimiento": "Técnico de Mantenimiento",
    "ayudante de produccion": "Ayudante de Producción",
    "mecanico textil": "Mecánico Textil",
    "ingeniero en mantenimiento": "Ingeniero de Mantenimiento",
    "practica profesionales": "Prácticas Profesionales",
    "practicas profesionales": "Prácticas Profesionales",
    "residencia practicas profesionales": "Prácticas Profesionales",
}

HISTORIAL_COLS = [
    "fecha_hora", "usuario", "base", "origen", "archivo_origen",
    "registros_recibidos", "registros_guardados", "duplicados_actualizados", "total_final",
]

# Seguimiento operativo: puede haber muchos seguimientos por persona maestra.
VINCULACIONES_COLS = [
    "id_vinculacion", "id_persona_maestro", "id_registro_origen", "nombre_persona",
    "empresa", "sector_empresa", "tipo_vacante", "area_oportunidad", "estatus",
    "fecha_vinculacion", "fecha_colocacion", "observaciones", "responsable", "fecha_actualizacion",
]
ESTATUS_VINCULACION = ["Vinculado", "Colocado", "No vinculado"]
ESTATUS_NUEVO = ["Vinculado", "No vinculado"]
TIPOS_VINCULACION = ["Inserción Laboral", "Atención", "Prácticas Profesionales", "Servicio Social"]
PREFIJOS_VINCULACION = {
    "Inserción Laboral": "I",
    "Atención": "A",
    "Prácticas Profesionales": "P",
    "Servicio Social": "S",
}

ALIASES_PERSONAS = {
    "id_institución": "id_institucion",
    "id_institucion": "id_institucion",
    "vinculación": "vinculacion",
    "vinculacion": "vinculacion",
    "año": "Año",
    "ano": "Año",
    "área_carrera": "area_carrera",
}

# Paleta institucional SEDECO Tlaxcala
PALETA_SEDECO = ["#AF2140", "#D0B786", "#922542", "#F2E6D3", "#62182F"]
ESCALA_SEDECO = ["#F2E6D3", "#D0B786", "#AF2140", "#922542", "#62182F"]
