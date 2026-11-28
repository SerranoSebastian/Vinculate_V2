"""Reporte informativo: cifras, series y rankings que se dibujan en el PDF (lógica pura, sin Streamlit ni gráficas).

Usa exactamente las mismas reglas que Inicio (personas únicas, vinculaciones, colocaciones) para que ninguna cifra del
reporte contradiga a la plataforma. Todo es agregado: el reporte nunca lleva nombres ni datos de contacto.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .colocaciones import colocaciones
from .constantes import SIN_DATO
from .normalizacion import agrupar_tipo_vinculacion, homologar_nulos, unificar_variantes
from .personas import obtener_personas_maestras, preparar_personas_dashboard, solo_vinculaciones

TIPOS = {"general": "General", "municipio": "Por municipio", "institucion": "Por institución"}
_CAMPO = {"municipio": "municipio", "institucion": "Institución"}
_CON_VINCULACION = ("Vinculado", "Colocado")
SIN_EMPRESA = "Sin asignar"
ETAPAS = ("Personas atendidas", "Con al menos una vinculación", "Colocadas en una empresa")
GRUPOS_EDAD = ["Menos de 18", "18 a 24", "25 a 34", "35 a 44", "45 o más", SIN_DATO]


@dataclass
class Reporte:
    tipo: str
    valor: str | None
    anios: list[int]
    periodo: str
    titulo: str
    subtitulo: str
    colocaciones_disponibles: bool
    indicadores: dict = field(default_factory=dict)
    embudo: pd.DataFrame = field(default_factory=pd.DataFrame)
    anual: pd.DataFrame = field(default_factory=pd.DataFrame)
    tipos_vinculacion: pd.DataFrame = field(default_factory=pd.DataFrame)
    municipios: pd.DataFrame = field(default_factory=pd.DataFrame)
    instituciones: pd.DataFrame = field(default_factory=pd.DataFrame)
    empresas: pd.DataFrame = field(default_factory=pd.DataFrame)
    perfil: dict = field(default_factory=dict)
    participacion: float | None = None
    lecturas: list = field(default_factory=list)

    @property
    def vacio(self) -> bool:
        return not self.indicadores or self.indicadores.get("personas", 0) == 0


# ---------------------------------------------------------------- utilidades
def _limpio(serie: pd.Series) -> pd.Series:
    """Misma unificación que las gráficas de Inicio: variantes de redacción juntas y todo faltante como «Indefinido»."""
    return homologar_nulos(unificar_variantes(serie), SIN_DATO)


def _conteo(serie: pd.Series, columna: str, top: int | None = None, etiqueta: str = "Categoría") -> pd.DataFrame:
    c = _limpio(serie).value_counts()
    if top:
        c = c.head(top)
    return c.rename_axis(etiqueta).reset_index(name=columna)


def _ids(df: pd.DataFrame | None) -> set:
    if df is None or df.empty or "id_persona_maestro" not in df.columns:
        return set()
    return set(df["id_persona_maestro"].dropna().astype(str))


def _pct(parte: float, total: float) -> float | None:
    return round(100 * parte / total, 1) if total else None


_MINUSCULAS = {"de", "del", "la", "las", "los", "el", "y"}


def nombre_legible(texto) -> str:
    """«SAN PABLO DEL MONTE» → «San Pablo del Monte». Solo toca lo que viene todo en mayúsculas (siglas y mixtos se respetan)."""
    t = str(texto).strip()
    if not t.isupper() or len(t) <= 5 and " " not in t:
        return t
    return " ".join(p.lower() if i and p.lower() in _MINUSCULAS else p.capitalize() for i, p in enumerate(t.split()))


def _personas(n) -> str:
    return f"{_n(n)} " + ("persona" if int(n) == 1 else "personas")


def _grupo_edad(edad) -> str:
    n = pd.to_numeric(pd.Series([edad]), errors="coerce").iloc[0]
    if pd.isna(n) or n <= 0:
        return SIN_DATO
    return "Menos de 18" if n < 18 else "18 a 24" if n < 25 else "25 a 34" if n < 35 else "35 a 44" if n < 45 else "45 o más"


def texto_periodo(anios) -> str:
    anios = sorted({int(a) for a in anios})
    if not anios:
        return "Todos los años"
    if len(anios) == 1:
        return str(anios[0])
    if anios == list(range(anios[0], anios[-1] + 1)):
        return f"{anios[0]} a {anios[-1]}"
    return ", ".join(map(str, anios))


def opciones(pf: pd.DataFrame) -> dict[str, list]:
    """Valores que se pueden elegir para el periodo y para los reportes por municipio / institución."""
    if pf is None or pf.empty:
        return {"anios": [], "municipio": [], "institucion": []}
    pf = preparar_personas_dashboard(pf)
    m = obtener_personas_maestras(pf)
    anios = sorted(int(a) for a in pd.to_numeric(pf["año"], errors="coerce").dropna().unique())

    def valores(col):
        s = _limpio(m[col]) if col in m.columns else pd.Series(dtype=object)
        return sorted(v for v in s.unique() if v != SIN_DATO)
    return {"anios": anios, "municipio": valores("municipio"), "institucion": valores("Institución")}


# ---------------------------------------------------------------- construcción
def construir(pf: pd.DataFrame, seg: pd.DataFrame | None, *, tipo: str = "general", valor: str | None = None,
              anios=()) -> Reporte:
    """Arma todas las cifras del reporte. `seg` es None cuando el perfil no puede consultar los seguimientos."""
    if tipo not in TIPOS:
        raise ValueError("Tipo de reporte no válido.")
    if tipo != "general" and not valor:
        raise ValueError("Elige el municipio o la institución del reporte.")
    anios = sorted({int(a) for a in anios})
    periodo = texto_periodo(anios)
    pf = preparar_personas_dashboard(pf if pf is not None else pd.DataFrame()).copy()
    hay_seg = seg is not None
    seg = seg.copy() if hay_seg else pd.DataFrame()

    nombre_valor = valor if tipo != "general" else None
    titulo = "Reporte"
    subtitulo = {"general": "Resultados de la vinculación laboral en Tlaxcala",
                 "municipio": f"Municipio de {nombre_legible(valor)}", "institucion": f"Institución: {valor}"}[tipo]
    r = Reporte(tipo=tipo, valor=nombre_valor, anios=anios, periodo=periodo, titulo=titulo, subtitulo=subtitulo,
                colocaciones_disponibles=hay_seg)
    if pf.empty:
        return r

    # Periodo: mismas reglas que Inicio (personas por año de registro; seguimientos por fecha de vinculación).
    if anios:
        pf = pf[pf["año"].isin(anios)]
        if hay_seg and not seg.empty:
            seg = seg[seg["fecha_vinculacion"].dt.year.isin(anios)]
    n_estado = len(_ids(pf) | (_ids(seg) if hay_seg else set()))

    # Alcance: municipio o institución de la persona (dato más completo, igual que el detalle de Inicio).
    if tipo != "general":
        base = obtener_personas_maestras(pf)
        campo = _CAMPO[tipo]
        en_alcance = set(base.loc[_limpio(base[campo]).eq(valor), "id_persona_maestro"].astype(str))
        pf = pf[pf["id_persona_maestro"].astype(str).isin(en_alcance)]
        if hay_seg and not seg.empty:
            seg = seg[seg["id_persona_maestro"].astype(str).isin(en_alcance)]
    if pf.empty:
        return r

    pv = solo_vinculaciones(pf)
    seg_vinc = seg[seg["estatus"].isin(_CON_VINCULACION)] if hay_seg and not seg.empty else pd.DataFrame()
    col = colocaciones(seg) if hay_seg else pd.DataFrame()

    ids_vinc = _ids(pv) | _ids(seg_vinc)
    ids_col = _ids(col)
    ids_atendidas = _ids(pf) | ids_vinc | ids_col
    por_persona = pv.groupby("id_persona_maestro").size() if not pv.empty else pd.Series(dtype=int)
    empresas_vinc = set(seg_vinc.loc[seg_vinc["empresa"].ne(SIN_EMPRESA), "empresa"]) if not seg_vinc.empty else set()

    n_pers, n_vinc_pers, n_col_pers = len(ids_atendidas), len(ids_vinc), len(ids_col)
    r.indicadores = {
        "personas": n_pers, "vinculadas": n_vinc_pers, "vinculaciones": int(len(pv)),
        "recurrentes": int((por_persona > 1).sum()), "empresas": len(empresas_vinc),
        "colocadas": n_col_pers, "colocaciones": int(len(col)),
        "tasa_vinculacion": _pct(n_vinc_pers, n_pers),
        "tasa_colocacion": _pct(n_col_pers, n_vinc_pers) if hay_seg else None,
    }
    r.participacion = _pct(n_pers, n_estado) if tipo != "general" else None

    r.embudo = pd.DataFrame({"Etapa": list(ETAPAS), "Personas": [n_pers, n_vinc_pers, n_col_pers],
                             "Porcentaje de las atendidas": [100.0 if n_pers else None, _pct(n_vinc_pers, n_pers), _pct(n_col_pers, n_pers)]})
    if not hay_seg:
        r.embudo = r.embudo.iloc[:2].reset_index(drop=True)

    # --- avance por año
    a_per = pf[pf["año"].notna()].groupby("año")["id_persona_maestro"].nunique()
    a_vin = pv[pv["año"].notna()].groupby("año").size() if not pv.empty else pd.Series(dtype=int)
    a_col = pd.Series(dtype=int)
    if not col.empty:
        a_col = col[col["fecha_colocacion"].notna()].groupby(col["fecha_colocacion"].dt.year).size()
    años = sorted({int(x) for x in (*a_per.index, *a_vin.index, *a_col.index)})
    anual = pd.DataFrame({"Año": años})
    anual["Personas atendidas"] = [int(a_per.get(a, 0)) for a in años]
    anual["Vinculaciones"] = [int(a_vin.get(a, 0)) for a in años]
    anual["Colocaciones"] = [int(a_col.get(a, 0)) for a in años]
    anual["Vinculaciones acumuladas"] = anual["Vinculaciones"].cumsum()
    anual["Colocaciones acumuladas"] = anual["Colocaciones"].cumsum()
    r.anual = anual

    # --- cortes (una fila por persona; vinculadas y colocadas se cuentan sobre la misma persona)
    maestras = obtener_personas_maestras(pf)
    maestras["_id"] = maestras["id_persona_maestro"].astype(str)
    maestras["_vinc"] = maestras["_id"].isin(ids_vinc)
    maestras["_col"] = maestras["_id"].isin(ids_col)

    def corte(campo: str, etiqueta: str, top: int) -> pd.DataFrame:
        etiquetas = _limpio(maestras[campo])
        if campo == "municipio":
            etiquetas = etiquetas.map(nombre_legible)
        d = pd.DataFrame({etiqueta: etiquetas, "_vinc": maestras["_vinc"], "_col": maestras["_col"]})
        g = d.groupby(etiqueta).agg(Personas=(etiqueta, "size"), Vinculadas=("_vinc", "sum"), Colocadas=("_col", "sum")).reset_index()
        g = g.sort_values(["Personas", etiqueta], ascending=[False, True])
        sin = g[g[etiqueta].eq(SIN_DATO)]
        g = pd.concat([g[~g[etiqueta].eq(SIN_DATO)].head(top), sin]).reset_index(drop=True)
        g[["Personas", "Vinculadas", "Colocadas"]] = g[["Personas", "Vinculadas", "Colocadas"]].astype(int)
        return g
    if tipo != "municipio":
        r.municipios = corte("municipio", "Municipio", 12)
    if tipo != "institucion":
        r.instituciones = corte("Institución", "Institución", 10)

    r.tipos_vinculacion = _conteo(agrupar_tipo_vinculacion(pv["vinculacion"]), "Vinculaciones", etiqueta="Tipo") if not pv.empty else pd.DataFrame(columns=["Tipo", "Vinculaciones"])

    edad = maestras["edad"].map(_grupo_edad).value_counts().reindex(GRUPOS_EDAD, fill_value=0)
    edad = edad[edad > 0]
    r.perfil = {
        "Sexo": _conteo(maestras["sexo"], "Personas", etiqueta="Sexo"),
        "Escolaridad": _conteo(maestras["escolaridad"], "Personas", etiqueta="Escolaridad"),
        "Edad": edad.rename_axis("Edad").reset_index(name="Personas"),
        "Grupo prioritario": _conteo(maestras["grupo_prioritario"], "Personas", 8, etiqueta="Grupo prioritario"),
    }

    # --- empresas receptoras
    if not seg_vinc.empty:
        e = seg_vinc[seg_vinc["empresa"].ne(SIN_EMPRESA)]
        if not e.empty:
            g = e.groupby("empresa").agg(Vinculaciones=("id_vinculacion", "size"), Personas=("id_persona_maestro", "nunique"),
                                         Colocaciones=("estatus", lambda s: int((s == "Colocado").sum()))).reset_index()
            r.empresas = (g.rename(columns={"empresa": "Empresa"})
                          .sort_values(["Colocaciones", "Vinculaciones", "Empresa"], ascending=[False, False, True])
                          .head(10).reset_index(drop=True))
    r.lecturas = lecturas(r)
    return r


# ---------------------------------------------------------------- lectura en palabras
def _n(v) -> str:
    return f"{int(v):,}"


def lecturas(r: Reporte) -> list[str]:
    """Frases de lectura automática: dicen lo que muestran las cifras, sin interpretar de más."""
    i = r.indicadores
    if not i:
        return []
    donde = "" if r.tipo == "general" else (f" del municipio de {nombre_legible(r.valor)}" if r.tipo == "municipio" else f" de la institución {r.valor}")
    cuando = "desde que existe el registro" if not r.anios else f"en {r.periodo}"
    out = [f"{cuando.capitalize()} se atendió a {_personas(i['personas'])}{donde}; {_n(i['vinculadas'])} "
           f"({i['tasa_vinculacion']}%) ya tienen al menos una vinculación con una empresa o programa."]
    if r.colocaciones_disponibles:
        if i["colocadas"]:
            out.append(f"{_personas(i['colocadas'])} " + ("fue colocada" if i["colocadas"] == 1 else "fueron colocadas")
                       + f" en una empresa, es decir, {i['tasa_colocacion']}% de las vinculadas.")
        else:
            out.append("Todavía no hay colocaciones registradas en este periodo.")
    if r.participacion is not None:
        out.append(f"Esto representa {r.participacion}% de las personas atendidas en todo el estado en el mismo periodo.")
    if not r.anual.empty and r.anual["Vinculaciones"].max() > 0:
        top = r.anual.loc[r.anual["Vinculaciones"].idxmax()]
        out.append(f"El año con más vinculaciones fue {int(top['Año'])} ({_n(top['Vinculaciones'])}).")
    for tabla, campo, texto in ((r.municipios, "Municipio", "El municipio con más personas atendidas fue"),
                                (r.instituciones, "Institución", "La institución de origen con más personas fue")):
        t = tabla[tabla[campo].ne(SIN_DATO)] if not tabla.empty else tabla
        if not t.empty:
            out.append(f"{texto} {t.iloc[0][campo]} ({_personas(t.iloc[0]['Personas'])}).")
    if not r.empresas.empty and r.empresas.iloc[0]["Colocaciones"] > 0:
        e = r.empresas.iloc[0]
        out.append(f"La empresa con más colocaciones fue {e['Empresa']} ({_n(e['Colocaciones'])} " + ("colocación" if e["Colocaciones"] == 1 else "colocaciones") + ").")
    return out


# ---------------------------------------------------------------- tablas de respaldo (Excel)
def tablas_excel(r: Reporte) -> dict[str, pd.DataFrame]:
    i = r.indicadores
    nombres = {"personas": "Personas atendidas", "vinculadas": "Personas con al menos una vinculación",
               "vinculaciones": "Vinculaciones", "recurrentes": "Personas con 2 o más vinculaciones",
               "empresas": "Empresas con vinculación", "colocadas": "Personas colocadas", "colocaciones": "Colocaciones",
               "tasa_vinculacion": "% de atendidas con vinculación", "tasa_colocacion": "% de vinculadas colocadas"}
    ind = pd.DataFrame([{"Indicador": nombres[k], "Valor": i.get(k)} for k in nombres if k in i])
    ctx = pd.DataFrame([{"Indicador": "Tipo de reporte", "Valor": TIPOS[r.tipo] + (f": {r.valor}" if r.valor else "")},
                        {"Indicador": "Periodo", "Valor": r.periodo}])
    hojas = {"Indicadores": pd.concat([ctx, ind], ignore_index=True), "Embudo": r.embudo, "Por año": r.anual,
             "Tipos de vinculación": r.tipos_vinculacion, "Municipios": r.municipios, "Instituciones": r.instituciones,
             "Empresas": r.empresas}
    for nombre, t in r.perfil.items():
        hojas[f"Perfil - {nombre}"[:31]] = t
    return {k: v for k, v in hojas.items() if v is not None and not v.empty}
