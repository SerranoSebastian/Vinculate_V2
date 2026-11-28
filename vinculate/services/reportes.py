"""Reporte informativo: arma las cifras con los datos que el perfil puede ver y genera el PDF / Excel (todo en memoria).

Ver el reporte exige poder ver Inicio; descargarlo exige `inicio.export` y queda en la auditoría. Es solo lectura:
no escribe nada en la base de datos.
"""
from __future__ import annotations

import io

import pandas as pd

from ..auth import servicio as auth_servicio
from ..auth.sesion import Sesion
from ..core import reportes as nucleo
from ..repositories.errores import SinPermiso
from . import datos, reporte_pdf
from .guardado import ahora_mx
from .respaldos import MIME, neutralizar_df

MODULO = "inicio"


def opciones(sesion: Sesion) -> dict[str, list]:
    if not sesion.puede("personas", "view"):
        return {"anios": [], "municipio": [], "institucion": []}
    return nucleo.opciones(datos.personas_dashboard(sesion))


def construir(sesion: Sesion, tipo: str, valor: str | None, anios) -> nucleo.Reporte:
    """Cifras del reporte con lo que el perfil puede consultar (sin seguimientos, el reporte omite las colocaciones)."""
    if not sesion.puede(MODULO, "view") or not sesion.puede("personas", "view"):
        raise SinPermiso("Tu perfil no puede consultar la información necesaria para el reporte.")
    pf = datos.personas_dashboard(sesion)
    seg = datos.vinculaciones(sesion) if sesion.puede("vinculaciones", "view") else None
    return nucleo.construir(pf, seg, tipo=tipo, valor=valor, anios=anios)


def _nombre(r: nucleo.Reporte) -> str:
    base = "reporte" if r.tipo == "general" else f"reporte_{r.tipo}"
    pieza = "".join(c if c.isalnum() else "_" for c in (r.valor or "")).strip("_").lower()
    periodo = "todos" if not r.anios else "_".join(map(str, r.anios)) if len(r.anios) <= 3 else f"{r.anios[0]}_{r.anios[-1]}"
    return "_".join(x for x in (base, pieza[:30], periodo) if x)


def _excel(r: nucleo.Reporte) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        for hoja, tabla in nucleo.tablas_excel(r).items():
            neutralizar_df(tabla).to_excel(w, index=False, sheet_name=hoja[:31])
    return buf.getvalue()


def exportar(sesion: Sesion, r: nucleo.Reporte, formato: str, nota: str = "") -> tuple[bytes, str, str]:
    """PDF o Excel del reporte. Exige `inicio.export` y audita la descarga."""
    if not sesion.puede(MODULO, "export"):
        raise SinPermiso("Tu perfil no tiene permiso para exportar este módulo.")
    if r.vacio:
        raise ValueError("No hay información para el periodo y la selección elegidos.")
    ahora = ahora_mx()
    if formato == "pdf":
        datos_b = reporte_pdf.generar_pdf(r, generado_por=sesion.nombre or sesion.email, ahora=ahora, nota=nota)
        mime = "application/pdf"
    elif formato == "xlsx":
        datos_b, mime = _excel(r), MIME["xlsx"]
    else:
        raise ValueError("Formato no soportado.")
    archivo = f"{_nombre(r)}_{ahora.strftime('%Y%m%d_%H%M')}.{formato}"
    auth_servicio.auditar("inicio_reporte", f"archivo={archivo}; tipo={r.tipo}; valor={r.valor or '-'}; periodo={r.periodo}; formato={formato}")
    return datos_b, archivo, mime
