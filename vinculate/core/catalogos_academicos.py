import re
import unicodedata
import pandas as pd


def _clave(valor):
    s = '' if valor is None else str(valor).strip()
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(ch for ch in s if not unicodedata.combining(ch))
    s = s.upper()
    s = re.sub(r'[^A-Z0-9]+', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def _catalogo_sin_variantes(valores_existentes, valores_nuevos):
    """Conserva primero la forma ya usada en la base y evita variantes equivalentes."""
    salida, vistas = [], set()
    for v in list(valores_existentes) + list(valores_nuevos):
        if v is None or (isinstance(v, float) and pd.isna(v)):
            continue
        txt = str(v).strip()
        if not txt:
            continue
        k = _clave(txt)
        if k and k not in vistas:
            vistas.add(k)
            salida.append(txt)
    return salida


ESCOLARIDADES = [
    "Preescolar",
    "Primaria",
    "Secundaria",
    "Media Superior",
    "Superior",
    "Maestría",
    "Doctorado",
    "Indefinido",
]

GRUPOS_PRIORITARIOS = ["Jóvenes", "Adultos", "Adultos Mayores"]

# Las formas ya normalizadas de la base tienen prioridad. Esta lista amplía el
# catálogo para impedir la captura libre de variantes nuevas.
INSTITUCIONES_AMPLIADAS = [
    # Tlaxcala y entorno institucional directamente relacionado
    "UATx", "UPTx", "UTT", "UPIIT", "Instituto Tecnológico de Apizaco",
    "ITA", "Instituto Tecnológico Superior de Tlaxco", "UPTx Región Poniente",
    "UVT", "Universidad del Altiplano", "El Colegio de Tlaxcala",
    "Universidad Metropolitana de Tlaxcala", "CIBA-IPN", "CECUTLAX-IPN",
    "CECyTE Tlaxcala", "CONALEP Tlaxcala", "COBAT", "Escuela Normal Urbana Federal Emilio Sánchez Piedras",
    "Escuela Normal Preescolar Profesora Francisca Madera Martínez",
    "Escuela Normal Rural Lic. Benito Juárez", "Escuela Normal de Educación Física Revolución Mexicana",
    "Universidad Pedagógica Nacional Unidad 291 Tlaxcala", "Universidad Intercultural de Tlaxcala",
    "Instituto Tecnológico del Altiplano de Tlaxcala", "Instituto Tecnológico de Tlaxcala",
    "Universidad Politécnica de Tlaxcala Región Poniente",
    # Nacionales / regionales de alta recurrencia
    "UNAM", "IPN", "Tecnológico de Monterrey", "IBERO Puebla", "IBERO Ciudad de México",
    "UDLAP", "BUAP", "UPAEP", "Universidad Anáhuac Puebla", "Universidad Anáhuac México",
    "Universidad Autónoma de Guadalajara", "Universidad de Guadalajara", "Universidad Autónoma Metropolitana",
    "Universidad Autónoma de Puebla", "Universidad Autónoma del Estado de México",
    "Universidad Autónoma del Estado de Hidalgo", "Universidad Autónoma de Querétaro",
    "Universidad Veracruzana", "Universidad Autónoma de Nuevo León", "Universidad Autónoma de San Luis Potosí",
    "Universidad Autónoma de Aguascalientes", "Universidad Autónoma de Chapingo",
    "Universidad Autónoma de Yucatán", "Universidad Autónoma de Baja California",
    "Universidad Autónoma de Chihuahua", "Universidad Autónoma de Ciudad Juárez",
    "Universidad Autónoma de Zacatecas", "Universidad de Guanajuato", "Universidad de Colima",
    "Universidad de Sonora", "Universidad Juárez Autónoma de Tabasco", "Universidad Autónoma de Chiapas",
    "Universidad Autónoma Benito Juárez de Oaxaca", "Universidad Autónoma de Guerrero",
    "Universidad Autónoma del Estado de Morelos", "Universidad Autónoma de Nayarit",
    "Universidad Autónoma de Sinaloa", "Universidad Michoacana de San Nicolás de Hidalgo",
    "Universidad de las Américas Puebla", "Universidad del Valle de México", "Universidad Tecnológica de México",
    "Universidad Tecmilenio", "Universidad La Salle México", "Universidad Panamericana",
    "Universidad del Claustro de Sor Juana", "Universidad Abierta y a Distancia de México",
    "Tecnológico Nacional de México", "Escuela Bancaria y Comercial", "Instituto Tecnológico Autónomo de México",
    "Universidad Intercontinental", "Universidad Latina", "Universidad Insurgentes",
    "Universidad Tres Culturas", "Universidad ICEL", "Universidad del Valle de Puebla",
]

CARRERAS_AMPLIADAS = [
    # Administración, economía, negocios y finanzas
    "Administración", "Administración de Empresas", "Administración Pública", "Administración Turística",
    "Contaduría Pública", "Contaduría y Finanzas", "Economía", "Finanzas", "Ingeniería Financiera",
    "Negocios Internacionales", "Comercio Internacional", "Comercio Internacional y Aduanas",
    "Mercadotecnia", "Mercadotecnia y Publicidad", "Innovación de Negocios y Mercadotecnia",
    "Gestión Empresarial", "Ingeniería en Gestión Empresarial", "Ingeniería en Administración",
    "Gestión del Capital Humano", "Recursos Humanos", "Relaciones Industriales", "Relaciones Comerciales",
    "Logística", "Ingeniería Logística", "Logística y Transporte", "Ingeniería en Logística y Transporte",
    "Ingeniería en Transporte", "Ingeniería en Logística Comercial Global", "Actuaría", "Banca y Finanzas",
    "Dirección Financiera", "Creación y Desarrollo de Empresas", "Emprendimiento e Innovación Empresarial",
    "Negocios Digitales", "Inteligencia de Negocios", "Gestión y Dirección de Negocios",
    # Computación, datos y tecnologías
    "Ciencia de Datos", "Ciencias de la Computación", "Ingeniería en Ciencia de Datos y Matemáticas",
    "Ingeniería en Inteligencia Artificial", "Inteligencia Artificial", "Ingeniería en Sistemas Computacionales",
    "Ingeniería en Computación", "Ingeniería Informática", "Informática", "Ingeniería de Software",
    "Desarrollo de Software", "Tecnologías de la Información", "Ingeniería en Tecnologías de la Información",
    "Ingeniería en Tecnologías de la Información y Comunicación", "Tecnologías de la Información y Comunicación",
    "Ingeniería en Tecnologías Computacionales", "Ingeniería en Sistemas Digitales y Robótica",
    "Ingeniería en Ciberseguridad", "Ciberseguridad", "Seguridad Informática", "Telemática",
    "Ingeniería en Telecomunicaciones", "Ingeniería en Telecomunicaciones y Sistemas Electrónicos",
    "Ingeniería en Redes y Telecomunicaciones", "Robótica", "Ingeniería Robótica Industrial",
    "Ingeniería en Automatización", "Automatización y Diseño", "Ingeniería en Sistemas Electrónicos",
    # Ingenierías industriales y físicas
    "Ingeniería Industrial", "Ingeniería Mecánica", "Ingeniería Mecatrónica", "Ingeniería Electromecánica",
    "Ingeniería Eléctrica", "Ingeniería Electrónica", "Ingeniería Civil", "Ingeniería Química",
    "Ingeniería Ambiental", "Ingeniería en Energías Renovables", "Ingeniería en Energía",
    "Ingeniería en Materiales", "Ingeniería Metalúrgica", "Ingeniería en Metalurgia y Materiales",
    "Ingeniería Petrolera", "Ingeniería Geológica", "Ingeniería Geofísica", "Ingeniería Geomática",
    "Ingeniería Física", "Ingeniería Matemática", "Ingeniería en Nanotecnología", "Nanotecnología",
    "Ingeniería en Semiconductores", "Ingeniería en Manufactura", "Ingeniería en Manufactura de Autopartes",
    "Ingeniería en Procesos y Operaciones Industriales", "Ingeniería en Procesos y Gestión Industrial",
    "Ingeniería de Procesos", "Ingeniería en Mantenimiento Industrial", "Mantenimiento Industrial",
    "Ingeniería Automotriz", "Ingeniería en Sistemas Automotrices", "Sistemas Automotrices",
    "Ingeniería Aeronáutica", "Ingeniería Aeroespacial", "Ingeniería Naval", "Ingeniería Ferroviaria",
    "Ingeniería Textil", "Diseño Textil", "Ingeniería en Diseño Textil y Moda",
    # Ciencias exactas y naturales
    "Matemáticas", "Matemáticas Aplicadas", "Física", "Física Biomédica", "Química", "Química Industrial",
    "Química Farmacéutico Biológica", "Bioquímica", "Bioquímica Clínica", "Biología", "Biotecnología",
    "Ingeniería en Biotecnología", "Ciencias Ambientales", "Ciencias de la Tierra", "Ciencias Genómicas",
    "Ciencias de Materiales Sustentables", "Ecología", "Manejo Sustentable de Zonas Costeras",
    "Ciencias Agrogenómicas", "Ciencias Forestales", "Ciencias Agropecuarias", "Agronomía",
    "Ingeniería Agrícola", "Ingeniería Agronómica", "Ingeniería Forestal", "Ingeniería en Alimentos",
    "Ingeniería Bioquímica", "Ingeniería Biomédica", "Ingeniería Biónica",
    # Salud
    "Medicina", "Médico Cirujano", "Médico Cirujano y Partero", "Enfermería", "Nutrición", "Odontología",
    "Cirujano Dentista", "Psicología", "Psicoterapia", "Fisioterapia", "Terapia Física", "Terapia Ocupacional",
    "Optometría", "Farmacia", "Salud Pública", "Gerontología", "Gerontología Social", "Naturopatía",
    "Médico Veterinario Zootecnista", "Veterinaria", "Ciencias Forenses", "Neurociencias",
    # Derecho, política y sociedad
    "Derecho", "Ciencias Políticas y Administración Pública", "Ciencia Política", "Relaciones Internacionales",
    "Sociología", "Antropología", "Antropología Social", "Trabajo Social", "Criminología", "Criminalística",
    "Seguridad Pública", "Seguridad Nacional", "Estudios Latinoamericanos", "Desarrollo Territorial",
    "Desarrollo y Gestión Interculturales", "Geografía", "Geohistoria", "Demografía",
    # Educación, humanidades e idiomas
    "Pedagogía", "Ciencias de la Educación", "Educación", "Educación Inicial", "Educación Especial",
    "Educación Física", "Intervención Educativa", "Psicopedagogía", "Enseñanza de Lenguas",
    "Lenguas Modernas", "Lenguas Extranjeras", "Traducción", "Lingüística", "Lingüística Aplicada",
    "Filosofía", "Historia", "Letras Hispánicas", "Lengua y Literatura Hispanoamericana", "Literatura",
    "Bibliotecología y Estudios de la Información", "Gestión de la Información", "Desarrollo Humano",
    "Ciencias de la Familia", "Comunicación e Innovación Educativa",
    # Arquitectura, artes, diseño y comunicación
    "Arquitectura", "Arquitectura de Interiores", "Urbanismo", "Diseño Industrial", "Diseño Gráfico",
    "Diseño de Información Visual", "Diseño de Modas", "Diseño Multimedia", "Diseño y Comunicación Visual",
    "Artes Visuales", "Artes Plásticas", "Arte y Diseño", "Música", "Danza", "Teatro", "Cinematografía",
    "Comunicación", "Ciencias de la Comunicación", "Comunicación y Medios Digitales", "Periodismo",
    "Publicidad", "Producción Audiovisual", "Animación Digital", "Animación y Arte Digital",
    # Turismo, alimentos y servicios
    "Turismo", "Administración Turística", "Gastronomía", "Gastronomía y Hotelería", "Hospitalidad",
    "Administración de Hoteles y Restaurantes", "Gestión Turística", "Gestión y Desarrollo Turístico",
    # Carreras técnicas / TSU frecuentes en la base y UT
    "TSU en Administración", "TSU en Mecatrónica", "TSU en Procesos de Producción",
    "TSU en Mantenimiento, Área Industrial", "TSU en Automatización", "TSU en Robótica",
    "TSU en Procesos Productivos", "TSU en Moldeo de Plásticos", "TSU en Automotriz",
    "TSU en Gestión del Capital Humano", "TSU en Desarrollo de Negocios", "TSU en Tecnologías de la Información",
    "Técnico Eléctrico", "Técnico en Puericultura", "Técnico en Mantenimiento", "Técnico en Mecatrónica",
    "Técnico en Programación", "Técnico en Contabilidad", "Técnico en Administración",
    # Posgrados / registros genéricos conservables
    "Maestría en Impuestos", "Maestría en Ingeniería Administrativa", "Maestría en Ingeniería Mecatrónica",
    "Maestría en Sistemas Computacionales", "Maestría en Energías Renovables", "Doctorado en Ciencias de la Ingeniería",
    "Indefinido", "Sin Información",
]

AREAS_CARRERA_AMPLIADAS = [
    "Administración", "Recursos Humanos", "Contabilidad y Finanzas", "Economía y Finanzas",
    "Comercio Internacional", "Mercadotecnia", "Logística y Transporte", "TI y Sistemas",
    "Datos e Inteligencia Artificial", "Ciberseguridad y Redes", "Industrial y Calidad",
    "Producción y Manufactura", "Mantenimiento", "Mecánica y Mecatrónica", "Electricidad y Electrónica",
    "Sistemas Automotrices", "Química y Biotecnología", "Ciencias Exactas", "Ambiental",
    "Agropecuaria y Forestal", "Salud", "Veterinaria", "Psicología", "Educación",
    "Ciencias Sociales", "Derecho y Seguridad", "Arquitectura y Construcción", "Diseño y Artes",
    "Comunicación y Medios", "Textil y Confección", "Turismo y Gastronomía", "Seguridad Ocupacional",
    "Nivel educativo", "Sin área específica", "Sin Información", "Indefinido",
]


def catalogo_instituciones(df_personas=None):
    existentes = [] if df_personas is None or "Institución" not in df_personas.columns else df_personas["Institución"].dropna().tolist()
    return _catalogo_sin_variantes(existentes, INSTITUCIONES_AMPLIADAS)


def catalogo_carreras(df_personas=None):
    existentes = [] if df_personas is None or "carrera" not in df_personas.columns else df_personas["carrera"].dropna().tolist()
    return _catalogo_sin_variantes(existentes, CARRERAS_AMPLIADAS)


def catalogo_areas(df_personas=None):
    existentes = [] if df_personas is None or "area_carrera" not in df_personas.columns else df_personas["area_carrera"].dropna().tolist()
    return _catalogo_sin_variantes(existentes, AREAS_CARRERA_AMPLIADAS)


def opcion_canonica(actual, opciones, default=None):
    """Busca la forma canónica equivalente por acentos/caso/espacios."""
    if actual is None or (isinstance(actual, float) and pd.isna(actual)):
        return default if default in opciones else (opciones[0] if opciones else "")
    txt = str(actual).strip()
    k = _clave(txt)
    for op in opciones:
        if _clave(op) == k:
            return op
    return default if default in opciones else (opciones[0] if opciones else "")


def escolaridad_canonica(actual):
    k = _clave(actual)
    aliases = {
        "PREESCOLAR": "Preescolar", "PRIMARIA": "Primaria", "SECUNDARIA": "Secundaria",
        "BASICA": "Secundaria", "EDUCACION BASICA": "Secundaria",
        "BACHILLERATO": "Media Superior", "PREPARATORIA": "Media Superior", "MEDIA SUPERIOR": "Media Superior",
        "TSU": "Superior", "TECNICO SUPERIOR UNIVERSITARIO": "Superior", "LICENCIATURA": "Superior",
        "SUPERIOR": "Superior", "UNIVERSIDAD": "Superior", "MAESTRIA": "Maestría", "DOCTORADO": "Doctorado",
        "INDEFINIDO": "Indefinido", "SIN DATO": "Indefinido", "SIN INFORMACION": "Indefinido",
    }
    return aliases.get(k, "Indefinido")


def grupo_canonico(actual, edad=None):
    k = _clave(actual)
    if k in {"JOVEN", "JOVENES"}: return "Jóvenes"
    if k in {"ADULTO", "ADULTOS"}: return "Adultos"
    if k in {"ADULTO MAYOR", "ADULTOS MAYORES", "ADULTO MAYORES"}: return "Adultos Mayores"
    try:
        e = int(float(edad))
        if e >= 60: return "Adultos Mayores"
        if e >= 30: return "Adultos"
        if e > 0: return "Jóvenes"
    except Exception:
        pass
    return "Jóvenes"
