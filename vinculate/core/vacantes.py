"""Reglas de negocio de vacantes (puras)."""
from __future__ import annotations

from datetime import date

import pandas as pd

from .constantes import (
    ALIASES_PUESTOS_VACANTES, ESTADOS_VACANTE, TIPOS_OPORTUNIDAD, VACANTES_COLS,
    VACANTES_COLS_OPCIONALES,
)
from .texto import normalizar_texto, parsear_fechas, texto_vacio


def normalizar_puesto_vacante(valor) -> str:
    """Homologa variantes claras sin inventar equivalencias entre puestos distintos."""
    if texto_vacio(valor):
        return ""
    limpio = " ".join(str(valor).strip().split())
    return ALIASES_PUESTOS_VACANTES.get(normalizar_texto(limpio), limpio)


_REGLAS_CATEGORIA = [
    (["ayudante", "operador", "produccion", "empacador", "hornero", "escaneador"], "Producción y Operaciones"),
    (["mantenimiento", "mecanico", "electromecanico", "electrico", "inyeccion"], "Mantenimiento y Electromecánica"),
    (["calidad", "sqa"], "Calidad"),
    (["ingeniero", "planeador"], "Ingeniería"),
    (["almacen", "almacenista", "materiales", "embarques", "comprador"], "Logística y Almacén"),
    (["contabilidad", "cuentas por cobrar", "costos", "financiero", "contador"], "Administración y Finanzas"),
    (["ventas"], "Ventas y Comercial"),
    (["capital humano", "reclutamiento"], "Recursos Humanos"),
    (["seguridad industrial", "medico industrial", "vigilante", "velador"], "Seguridad y Salud"),
    (["chofer", "tractocamion", "camion", "grua"], "Transporte"),
    (["soldador", "pailero", "carpintero", "tornero", "fresador", "montacarguista", "pintor"], "Oficios y Técnicos"),
    (["textil", "costura", "serigrafista", "tejedor", "cardero", "hilador", "atador"], "Textil"),
]


def categoria_puesto_vacante(puesto, tipo_oportunidad: str = "Empleo") -> str:
    if tipo_oportunidad in ("Prácticas Profesionales", "Servicio Social"):
        return "Formación y Vinculación"
    p = normalizar_texto(puesto)
    for palabras, categoria in _REGLAS_CATEGORIA:
        if any(x in p for x in palabras):
            return categoria
    return "Otros"


def asegurar_ids_vacantes(df: pd.DataFrame) -> pd.DataFrame:
    """Asigna IDs solo a filas nuevas y conserva los IDs históricos existentes."""
    df = df.copy()
    for c in ["ID Vacante", "ID Registro Origen"]:
        if c not in df.columns:
            df[c] = ""
        df[c] = df[c].fillna("").astype(str).str.strip()

    nums = pd.to_numeric(df["ID Vacante"].str.extract(r"VAC-(\d+)", expand=False), errors="coerce")
    siguiente = int(nums.max()) + 1 if nums.notna().any() else 1
    for idx in df.index[df["ID Vacante"].eq("")]:
        df.at[idx, "ID Vacante"] = f"VAC-{siguiente:04d}"
        siguiente += 1

    nums_o = pd.to_numeric(df["ID Registro Origen"].str.extract(r"ORI-(\d+)", expand=False), errors="coerce")
    siguiente_o = int(nums_o.max()) + 1 if nums_o.notna().any() else 1
    for idx in df.index[df["ID Registro Origen"].eq("")]:
        df.at[idx, "ID Registro Origen"] = f"ORI-{siguiente_o:04d}"
        siguiente_o += 1
    return df


def asignar_ids_vacantes(df: pd.DataFrame, ids_existentes, origenes_existentes) -> pd.DataFrame:
    """Asigna 'ID Vacante' / 'ID Registro Origen' SOLO a filas que no los traen, a partir de los
    IDs reales de la base (no solo los del archivo), para no colisionar con registros ya guardados."""
    df = df.copy()
    for c in ("ID Vacante", "ID Registro Origen"):
        if c not in df.columns:
            df[c] = ""
        df[c] = df[c].fillna("").astype(str).str.strip()
    usados = pd.Series(sorted(set(map(str, ids_existentes)) | {x for x in df["ID Vacante"] if x}), dtype=str)
    nums = pd.to_numeric(usados.str.extract(r"VAC-(\d+)", expand=False), errors="coerce")
    siguiente = int(nums.max()) + 1 if nums.notna().any() else 1
    usados_o = pd.Series(sorted(set(map(str, origenes_existentes)) | {x for x in df["ID Registro Origen"] if x}), dtype=str)
    nums_o = pd.to_numeric(usados_o.str.extract(r"ORI-(\d+)", expand=False), errors="coerce")
    siguiente_o = int(nums_o.max()) + 1 if nums_o.notna().any() else 1
    for idx in df.index:
        if df.at[idx, "ID Vacante"] == "":
            df.at[idx, "ID Vacante"] = f"VAC-{siguiente:04d}"
            siguiente += 1
        if df.at[idx, "ID Registro Origen"] == "":
            df.at[idx, "ID Registro Origen"] = f"ORI-{siguiente_o:04d}"
            siguiente_o += 1
    return df


def limpiar_vacantes(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = df.columns.astype(str).str.strip()

    # Compatibilidad con archivos antiguos: conservar el texto original antes de homologar.
    if "Puesto Original" not in df.columns:
        df["Puesto Original"] = df["Tipo de Vacante"] if "Tipo de Vacante" in df.columns else ""
    for c in VACANTES_COLS:
        if c not in df.columns:
            df[c] = ""
    opcionales = [c for c in VACANTES_COLS_OPCIONALES if c in df.columns]
    df = df[VACANTES_COLS + opcionales]
    df["Fecha"] = parsear_fechas(df["Fecha"])
    if "fecha_cierre" in opcionales:
        df["fecha_cierre"] = parsear_fechas(df["fecha_cierre"])

    texto_cols = [c for c in VACANTES_COLS if c != "Fecha"] + [c for c in opcionales if c != "fecha_cierre"]
    for col in texto_cols:
        df[col] = df[col].fillna("").astype(str).str.strip().str.replace(r"\s+", " ", regex=True)

    df["Puesto Original"] = df["Puesto Original"].where(df["Puesto Original"].ne(""), df["Tipo de Vacante"])
    df["Tipo de Vacante"] = df["Tipo de Vacante"].apply(normalizar_puesto_vacante)

    # Deducir tipo de oportunidad en archivos antiguos y mantenerlo consistente.
    vacio_tipo = df["Tipo de Oportunidad"].eq("")
    puesto_key = df["Tipo de Vacante"].map(normalizar_texto)
    df.loc[vacio_tipo & puesto_key.str.contains("practicas profesionales", na=False), "Tipo de Oportunidad"] = "Prácticas Profesionales"
    df.loc[vacio_tipo & puesto_key.str.contains("servicio social", na=False), "Tipo de Oportunidad"] = "Servicio Social"
    df.loc[df["Tipo de Oportunidad"].eq(""), "Tipo de Oportunidad"] = "Empleo"

    vacia_cat = df["Categoría de Puesto"].eq("")
    if vacia_cat.any():
        df.loc[vacia_cat, "Categoría de Puesto"] = df.loc[vacia_cat].apply(
            lambda r: categoria_puesto_vacante(r["Tipo de Vacante"], r["Tipo de Oportunidad"]), axis=1
        )

    estado = df["Estado"].str.lower()
    df["Estado"] = estado.map({"activa": "Activa", "inactiva": "Inactiva", "finalizada": "Inactiva"}).fillna("Activa")
    return df


def preparar_vacantes_dashboard(df: pd.DataFrame) -> pd.DataFrame:
    df = limpiar_vacantes(df)
    df["Mes"] = df["Fecha"].dt.to_period("M").astype(str)
    df["Año"] = df["Fecha"].dt.year
    df["MesNombre"] = df["Fecha"].dt.strftime("%b %Y")
    return df


def tiene_vigencia(df: pd.DataFrame) -> bool:
    """True si la base ya cuenta con la columna `fecha_cierre` (migración V007)."""
    return "fecha_cierre" in df.columns


def vigentes_mask(df: pd.DataFrame, hoy: date | None = None) -> pd.Series:
    """Vacante vigente = Estado 'Activa' y sin fecha de cierre vencida.

    Sin la columna `fecha_cierre` (V007 no aplicada) la vigencia NO puede
    afirmarse: se devuelve solo 'Activa', y la interfaz lo declara así.
    """
    activa = df["Estado"].eq("Activa")
    if "fecha_cierre" not in df.columns:
        return activa
    hoy_ts = pd.Timestamp(hoy or date.today())
    cierre = df["fecha_cierre"]
    return activa & (cierre.isna() | (cierre >= hoy_ts))


def clasificar_vigencia(df: pd.DataFrame, hoy: date | None = None) -> pd.Series:
    """Etiqueta de cada vacante: 'Vigente', 'Activa con cierre vencido' o 'Inactiva'.

    Sin la columna `fecha_cierre` solo se puede distinguir 'Activa (sin fecha de cierre registrada)'
    de 'Inactiva': la vigencia real no es verificable y la etiqueta lo dice.
    """
    activa = df["Estado"].eq("Activa")
    if "fecha_cierre" not in df.columns:
        return activa.map({True: "Activa (vigencia no verificable)", False: "Inactiva"})
    hoy_ts = pd.Timestamp(hoy or date.today())
    vencida = activa & df["fecha_cierre"].notna() & (df["fecha_cierre"] < hoy_ts)
    out = pd.Series("Inactiva", index=df.index)
    out[activa] = "Vigente"
    out[vencida] = "Activa con cierre vencido"
    return out


def validar_vacantes(df: pd.DataFrame) -> list[dict]:
    df = limpiar_vacantes(df).reset_index(drop=True)
    errores = []
    for i, fila in df.iterrows():
        if pd.isna(fila.get("Fecha")):
            errores.append({"fila": i + 1, "campo": "Fecha", "error": "La fecha es obligatoria y debe ser válida."})
        if texto_vacio(fila.get("Empresa")):
            errores.append({"fila": i + 1, "campo": "Empresa", "error": "La empresa es obligatoria."})
        if texto_vacio(fila.get("Tipo de Vacante")):
            errores.append({"fila": i + 1, "campo": "Tipo de Vacante", "error": "El puesto es obligatorio."})
        if fila.get("Tipo de Oportunidad") not in TIPOS_OPORTUNIDAD:
            errores.append({"fila": i + 1, "campo": "Tipo de Oportunidad", "error": "Usa Empleo, Prácticas Profesionales o Servicio Social."})
        if fila.get("Estado") not in ESTADOS_VACANTE:
            errores.append({"fila": i + 1, "campo": "Estado", "error": "El estado debe ser Activa o Inactiva."})
        if "fecha_cierre" in df.columns and pd.notna(fila.get("fecha_cierre")) and pd.notna(fila.get("Fecha")):
            if fila["fecha_cierre"] < fila["Fecha"]:
                errores.append({"fila": i + 1, "campo": "fecha_cierre", "error": "La fecha de cierre no puede ser anterior a la publicación."})
    return errores


def clave_duplicado_vacante(df: pd.DataFrame) -> pd.Series:
    """Clave de duplicado: fecha + empresa + puesto + oportunidad + área + link + descripción.

    Una misma publicación puede contener muchos puestos; el link por sí solo
    nunca es duplicado.
    """
    f = df["Fecha"].dt.strftime("%Y-%m-%d").fillna("")
    partes = [
        f,
        df["Empresa"].map(normalizar_texto),
        df["Tipo de Vacante"].map(normalizar_texto),
        df["Tipo de Oportunidad"].map(normalizar_texto),
        df["Área de Oportunidad"].map(normalizar_texto),
        df["Link de la Publicación"].map(normalizar_texto),
        df["Descripción"].map(normalizar_texto),
    ]
    clave = partes[0].astype(str)
    for p in partes[1:]:
        clave = clave + "|" + p.astype(str)
    return clave


def aplicar_duplicados_vacantes(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    df = limpiar_vacantes(df).copy()
    antes = len(df)
    df["_dup"] = clave_duplicado_vacante(df)
    df = df.drop_duplicates("_dup", keep="last").drop(columns=["_dup"])
    df = asegurar_ids_vacantes(df)
    return df, antes - len(df)
