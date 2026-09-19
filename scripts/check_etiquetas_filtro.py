#!/usr/bin/env python3
"""Check del filtrado de etiquetas: data-n debe cruzar con el numero de ficha.

Si alguien vuelve a generar las etiquetas sin data-n, el modal imprime las 379
siempre y este check lo caza. No necesita navegador: comprueba el HTML.
"""
import json, os, re, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts"))

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
E = os.path.join(RAIZ, "data", "empresas.json")


def main():
    html = open(os.path.join(RAIZ, "index.html"), encoding="utf-8").read()
    empresas = json.load(open(E, encoding="utf-8"))
    from etiquetas import generar, PROV_ES

    orden = sorted(empresas, key=lambda e: (e.get("nombre_normalizado") or e.get("nombre") or "").lower())
    for i, e in enumerate(orden, 1):
        e["numero"] = i
    celdas, _, _ = generar(orden)

    # 1) mismo numero de etiquetas en el HTML y en el generador
    n_html = html.count('<div class="etq" data-n=')
    assert n_html == len(celdas) == 379, (n_html, len(celdas))

    # 2) toda etiqueta lleva data-n y apunta a una ficha que existe
    nums_ficha = {e["numero"] for e in orden}
    ns = [int(x) for x in re.findall(r'<div class="etq" data-n="(\d+)"', html)]
    assert len(ns) == n_html, "hay etiquetas sin data-n"
    assert set(ns) <= nums_ficha, "data-n apunta a fichas inexistentes"

    # 3) el CP impreso corresponde a la provincia de ESA ficha (el cruce real).
    #    Es lo que rompe si data-n se desalinea: la etiqueta de Huelva se
    #    imprimiria con el filtro de Malaga.
    por_n = {e["numero"]: e for e in orden}
    malas = 0
    for celda in celdas:
        n = int(re.search(r'data-n="(\d+)"', celda).group(1))
        f = por_n[n]
        amb = f.get("ambito")
        if amb not in PROV_ES:
            continue
        loc = re.search(r'class="etq-loc">([^<]+)<', celda).group(1)
        cp = re.search(r"\b(\d{5})\b", loc)
        if cp and not cp.group(1).startswith({"SEVILLA": "41", "MALAGA": "29", "HUELVA": "21"}[amb]):
            malas += 1
    assert malas == 0, f"{malas} etiquetas con CP de provincia distinta a su ficha"

    # 4) el JS del modal filtra por data-n (no imprime siempre las 379)
    assert "aplicaEtq" in html and "ETQS" in html, "el modal no filtra: falta aplicaEtq"

    por_prov = {}
    for n in ns:
        amb = por_n[n].get("ambito")
        por_prov[amb] = por_prov.get(amb, 0) + 1
    print(f"OK etiquetas: {n_html} con data-n | por provincia {por_prov} | 0 CP cruzados")


if __name__ == "__main__":
    main()
