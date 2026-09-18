#!/usr/bin/env python3
"""
build_html.py — ÚNICA vía de escritura de index.html.

Lee data/empresas.json (canónico) y genera fichas + mapLocations del mismo
registro, así la desincronización ficha↔mapa (defecto D1 del proyecto anterior)
es imposible por construcción.

Adaptado de centros_compatibles/scripts/build_html.py: misma arquitectura,
campos distintos y plantilla propia.
"""
import html as htmlmod
import json
import os
import re

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(RAIZ, "data", "empresas.json")
AVISO = os.path.join(RAIZ, "AVISO.md")
OUT = os.path.join(RAIZ, "index.html")


def esc(s):
    return htmlmod.escape(str(s)) if s else ""


def card(e):
    if e.get("web"):
        web = f'<a class="chip" href="{esc(e["web"])}" rel="noopener" target="_blank">{esc(e["web"][:42])}</a>'
    else:
        web = '<span class="chip off">sin web</span>'

    tel = f'<div class="tel">📞 {esc(e["telefono"])}</div>' if e.get("telefono") else ""
    dir_ = esc(e.get("direccion") or e.get("municipio") or "")

    return f'''<article class="ficha" data-n="{e.get('numero')}" data-prov="{esc(e.get("ambito"))}">
  <header>
    <span class="num">{e.get("numero")}</span>
    <h3>{esc(e["nombre"])}</h3>
  </header>
  <p class="dir">{dir_}</p>
  {tel}
  <div class="chips">{web}</div>
</article>'''


def main():
    empresas = json.load(open(DATA))
    orden = sorted(empresas, key=lambda e: (e.get("nombre_normalizado") or "").lower())
    for i, e in enumerate(orden, 1):
        e["numero"] = i

    con_coords = [e for e in orden if e.get("lat") and e.get("lng")]
    if len(con_coords) == 0:
        raise SystemExit("Ninguna ficha tiene coordenadas: revisa la Fase 3 antes de publicar")

    plantilla = open(os.path.join(RAIZ, "plantilla.html"), encoding="utf-8").read()
    aviso = ""
    if os.path.exists(AVISO):
        aviso = open(AVISO, encoding="utf-8").read()

    # fichas: van al marcador, no se inyectan en un HTML preexistente
    cuerpo = "\n".join(card(e) for e in orden)
    # etiquetas postales: misma fuente, otra vista. Se usa generar() (no
    # etiqueta() en bucle) para que el dedupe sea el mismo que el del script.
    from etiquetas import generar as _generar
    celdas_etq, _, _ = _generar(orden)
    hoja_etq = "\n".join(celdas_etq)
    puntos = ",\n".join(
        f'{{n:{e["numero"]},name:"{e["nombre"].replace(chr(34), chr(39))}",'
        f'lat:{e["lat"]},lng:{e["lng"]},prov:"{e.get("ambito","")}"}}'
        for e in con_coords
    )

    stats = {
        "total": len(orden),
        "con_coords": len(con_coords),
        "sevilla": sum(1 for e in orden if e.get("ambito") == "SEVILLA"),
        "malaga": sum(1 for e in orden if e.get("ambito") == "MALAGA"),
        "generado": "2026-09-18",
    }

    out = (plantilla
           .replace("<!--FICHAS-->", cuerpo)
           .replace("/*PUNTOS*/", puntos)
           .replace("<!--AVISO-->", aviso)
           .replace("<!--ETIQUETAS-->", hoja_etq)
           .replace("{{STATS}}", json.dumps(stats)))

    # comprobación de coherencia: fichas y puntos salen del mismo array
    n_fichas = out.count('<article class="ficha"')
    n_puntos = out.count("{n:")
    n_etq = out.count('<div class="etq">')
    assert n_fichas == len(orden), f"{n_fichas} fichas en HTML vs {len(orden)} en JSON"
    assert n_puntos == len(con_coords), f"{n_puntos} puntos vs {len(con_coords)} con coords"
    assert n_etq > 0, "sin etiquetas: revisa el marcador <!--ETIQUETAS-->"
    assert "<!--ETIQUETAS-->" not in out, "marcador de etiquetas sin reemplazar"

    open(OUT, "w", encoding="utf-8").write(out)
    print(f"index.html: {n_fichas} fichas, {n_puntos} puntos, {n_etq} etiquetas, "
          f"Sevilla {stats['sevilla']} / Málaga {stats['malaga']}")


if __name__ == "__main__":
    main()
