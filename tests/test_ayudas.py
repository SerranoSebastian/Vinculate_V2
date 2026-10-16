"""Las ayudas (❓) del Inicio: cada una tiene su texto, el texto respeta las reglas de redacción y se dibuja en la página."""
import re
from pathlib import Path

import pytest

from vinculate.components import ui
from vinculate.config import ayudas

RAIZ = Path(__file__).resolve().parents[1] / "vinculate"
PALABRAS_PROHIBIDAS = ["canaliz", "derivad", "revisar", "revisión", "pendiente", "falta", "migración", "supabase"]


def _claves_usadas(archivo: str) -> set[str]:
    codigo = (RAIZ / "vistas" / archivo).read_text(encoding="utf-8")
    return set(re.findall(r'(?:info=|ayuda_grafica\()"([\w.]+)"', codigo))


def test_cada_ayuda_usada_en_inicio_tiene_texto():
    usadas = _claves_usadas("inicio.py")
    assert len(usadas) >= 25
    assert [k for k in usadas if not ayudas.texto(k)] == []


def test_no_hay_textos_sin_usar_en_inicio():
    inicio = {k for k in ayudas.AYUDAS if k.startswith("inicio.")}
    assert inicio - _claves_usadas("inicio.py") == set()


@pytest.mark.parametrize("clave", sorted(ayudas.AYUDAS))
def test_redaccion_de_cada_ayuda(clave):
    t = ayudas.AYUDAS[clave].lower()
    assert t.strip(), "texto vacío"
    assert [w for w in PALABRAS_PROHIBIDAS if w in t] == []


def test_globo_html_escapa_y_separa_parrafos():
    html = ui._globo_ayuda("inicio.personas_unicas")
    assert html.count("<p>") == 3 and "vc-info-texto" in html
    assert ui._globo_ayuda("no.existe") == "" and ui._globo_ayuda(None) == ""
