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
    return set(re.findall(r'(?:\binfo=|ayuda_grafica\(|ayudas\.texto\()"([\w.]+)"', codigo))


@pytest.mark.parametrize("archivo,prefijo,minimo", [("inicio.py", "inicio.", 25), ("mapa.py", "mapa.", 14)])
def test_cada_ayuda_usada_tiene_texto_y_cada_texto_se_usa(archivo, prefijo, minimo):
    usadas = _claves_usadas(archivo)
    assert len(usadas) >= minimo
    assert [k for k in usadas if not ayudas.texto(k)] == []
    definidas = {k for k in ayudas.AYUDAS if k.startswith(prefijo)}
    assert definidas - usadas == set()


@pytest.mark.parametrize("clave", sorted(ayudas.AYUDAS))
def test_redaccion_de_cada_ayuda(clave):
    t = ayudas.AYUDAS[clave].lower()
    assert t.strip(), "texto vacío"
    assert [w for w in PALABRAS_PROHIBIDAS if w in t] == []


def test_globo_html_escapa_y_separa_parrafos():
    html = ui._globo_ayuda("inicio.personas_unicas")
    assert html.count("<p>") == 3 and "vc-info-texto" in html
    assert ui._globo_ayuda("no.existe") == "" and ui._globo_ayuda(None) == ""
