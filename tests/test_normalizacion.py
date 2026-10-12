"""Unificación de variantes y agrupación visual del tipo de vinculación."""
import pandas as pd

from vinculate.components import charts
from vinculate.core.normalizacion import GRUPO_ATENCION, GRUPO_FORMACION, agrupar_tipo_vinculacion, unificar_variantes
from vinculate.core.personas import limpiar_personas


def test_masculino_y_MASCULINO_se_cuentan_juntos():
    s = pd.Series(["Masculino", "MASCULINO", "masculino", " Masculino ", "Femenino", "FEMENINO", "hombre", None, ""])
    c = charts.conteo(s, "Sexo", "Personas").set_index("Sexo")["Personas"].to_dict()
    assert c == {"Masculino": 5, "Femenino": 2, "Indefinido": 2}


def test_otras_columnas_eligen_la_redaccion_natural_y_respetan_siglas():
    s = pd.Series(["Superior", "superior", "SUPERIOR", "Media superior", "MEDIA SUPERIOR", "IPN", "IPN", "Ipn", "Tlaxcala", "Tlaxcala", "TLAXCALA", "Tláxcala"])
    u = unificar_variantes(s)
    assert set(u[:3]) == {"Superior"} and set(u[3:5]) == {"Media superior"}
    assert set(u[5:8]) == {"IPN"} and set(u[8:]) == {"Tlaxcala"}  # gana la más frecuente entre las naturales


def test_solo_mayusculas_sin_alternativa_no_se_inventa_redaccion():
    assert unificar_variantes(pd.Series(["UNIVERSIDAD X", "UNIVERSIDAD X"])).tolist() == ["UNIVERSIDAD X"] * 2


def test_agrupacion_visual_de_tipos():
    s = pd.Series(["Prácticas Profesionales", "Servicio Social", "practicas profesionales", "Atención", "Inserción Laboral", "INSERCION LABORAL", "", None, "Otro"])
    g = agrupar_tipo_vinculacion(s).tolist()
    assert g == [GRUPO_FORMACION] * 3 + [GRUPO_ATENCION] * 3 + ["Indefinido"] * 2 + ["Otro"]
    # Los datos originales no se tocan
    assert s.iloc[1] == "Servicio Social"


def test_la_carga_normaliza_sexo_y_escolaridad():
    df = pd.DataFrame({"nombre": ["a", "b", "c"], "sexo": ["MASCULINO", "mujer", "Otro"], "escolaridad": ["superior", "Media superior", ""]})
    out = limpiar_personas(df, generar_ids=False)
    assert out["sexo"].tolist() == ["Masculino", "Femenino", "Otro"]
    assert out["escolaridad"].tolist() == ["Superior", "Media superior", ""]


def test_todas_las_formas_de_sin_dato_son_una_sola_etiqueta():
    from vinculate.core.constantes import SIN_DATO
    from vinculate.core.normalizacion import es_nulo, homologar_nulos
    s = pd.Series(["Indefinido", "indefinido", "Sin Información", "sin informacion", "Sin dato", "Información no disponible", "", None, float("nan"), "Superior"])
    h = homologar_nulos(s).tolist()
    assert h == [SIN_DATO] * 9 + ["Superior"]
    assert not es_nulo("Masculino") and not es_nulo("Naucalpan")
    c = charts.conteo(s, "Escolaridad", "Personas").set_index("Escolaridad")["Personas"].to_dict()
    assert c == {SIN_DATO: 9, "Superior": 1}


def test_tablas_muestran_la_misma_etiqueta():
    from vinculate.components import ui
    from vinculate.core.constantes import SIN_DATO
    df = pd.DataFrame({"carrera": ["Sin Información", "indefinido", None, "Derecho"]})
    assert ui.preparar_tabla(df)["carrera"].tolist() == [SIN_DATO] * 3 + ["Derecho"]
