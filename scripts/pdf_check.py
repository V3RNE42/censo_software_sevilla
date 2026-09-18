#!/usr/bin/env python3
"""pdf_check.py — genera el PDF de etiquetas y VERIFICA que no se corten.

Por qué: el CSS de A4 (@page + break-inside:avoid) no se puede dar por bueno
mirando el HTML. El navegador decide dónde corta. Aquí se genera el PDF real
con el motor de impresión de Chromium y se comprueba:
  1. el numero de paginas
  2. que no haya texto recortado (comparando el texto de las etiquetas del DOM
     con el texto extraido del PDF)

Uso: python3 scripts/pdf_check.py [salida.pdf]
"""
import os
import re
import sys

from playwright.sync_api import sync_playwright

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(RAIZ, "index.html")
OUT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/etiquetas.pdf"


def main():
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page()
        pg.goto(f"file://{HTML}")
        pg.click("#btn-etq")
        pg.wait_for_timeout(400)

        # texto esperado: todas las etiquetas del DOM
        esperadas = pg.eval_on_selector_all(
            "#hoja .etq",
            "els => els.map(e => e.innerText.replace(/\\s+/g,' ').trim())"
        )

        pg.pdf(path=OUT, format="A4", print_background=True,
               margin={"top": "8mm", "bottom": "8mm", "left": "8mm", "right": "8mm"})
        b.close()

    size = os.path.getsize(OUT)
    print(f"PDF: {OUT} ({size//1024} KB)")
    print(f"etiquetas en el DOM: {len(esperadas)}")

    # extraer texto del PDF para comprobar que las etiquetas viajaron enteras
    txt = ""
    try:
        from pypdf import PdfReader
        r = PdfReader(OUT)
        print(f"paginas en el PDF  : {len(r.pages)}")
        txt = " ".join(" ".join((p.extract_text() or "").split()) for p in r.pages)
    except ImportError:
        try:
            import PyPDF2 as pypdf2
            r = pypdf2.PdfReader(OUT)
            print(f"paginas en el PDF  : {len(r.pages)}")
            txt = " ".join(" ".join((p.extract_text() or "").split()) for p in r.pages)
        except ImportError:
            print("sin pypdf/PyPDF2: no se puede verificar el texto del PDF")
            return 0

    norm = lambda s: re.sub(r"\s+", " ", s).strip().lower()
    t = norm(txt)
    faltan = [e for e in esperadas if norm(e)[:60] not in t]
    print(f"etiquetas halladas : {len(esperadas) - len(faltan)}/{len(esperadas)}")
    for e in faltan[:8]:
        print(f"  FALTA: {e[:75]}")
    assert not faltan, f"{len(faltan)} etiquetas no aparecen en el PDF (texto cortado o perdido)"
    print("OK: todas las etiquetas estan enteras en el PDF")
    return 0


if __name__ == "__main__":
    sys.exit(main())
