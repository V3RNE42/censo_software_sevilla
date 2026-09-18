#!/usr/bin/env python3
"""F1 — Directorios publicos y listados de empresas de software en HUELVA.

Fuente unica del agente F1. Estrategia (una sola pasada, sin scraping agresivo):
  A) BORME 60 dias habiles  -> prov 21, ya recolectado en borme_cnae62.py.
     Se re-lee raw/borme_cnae62_2026-09-18.jsonl (provincia HUELVA) y se
     re-extrae el domicilio COMPLETO del XML del BOE (el raw lo corta a 400
     chars y perdia el CP). El CP del BORME es INE: 21xxx = Huelva.
  B) Directorios publicos onubenses con direccion postal verificable:
     - digitalpulse.media/listados/agencias-de-desarrollo-de-software/huelva
       (15 fichas con calle + CP 21xxx)
     - proveedores.com/desarrollo-de-software/huelva-ciudad (5 empresas)
     - diphuelva.es (HuelvaEmpresa / HuelvaLab / Ignite): sin directorio de
       empresas -> NO aporta fichas (se documenta, no se inventa).
     - camarahuelva.com (403), paginasamarillas (403), cylex (403),
       empresite (captcha, 410), ejesor/infocif (WAF): bloqueados.

REGLA DURA: sin evidencia_url no hay ficha. Sin CP 21xxx o municipio onubense
verificable, no entra.

Uso: python3 f1_directorios_huelva.py
"""
import json
import os
import re
import sys
import urllib.request
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import fichas, escribe  # noqa: E402

FECHA = "2026-09-18"
BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
UA = {"User-Agent": "censo-software-sevilla/1.0 (julio@cabanillas.dev)"}

MUNIS_HUELVA = {
    "huelva", "lepe", "almonte", "ayamonte", "moguer", "aljaraque", "gibraleon",
    "gibraleón", "isla cristina", "aracena", "valverde del camino", "bollullos par del condado",
    "san juan del puerto", "valdelarco", "palos de la frontera", "punta umbría",
    "punta umbria", "cartaya", "trigueros", "beas", "nerva", "rociana del condado",
}
CP_RE = re.compile(r"\b(21\d{3})\b")


def get(url):
    req = urllib.request.Request(url, headers=UA)
    for i in range(3):
        try:
            with urllib.request.urlopen(req, timeout=45) as r:
                return r.read().decode("utf-8", "replace")
        except Exception:
            time.sleep(2 * (i + 1))
    return None


def municipio_de(direccion, cp):
    """Municipio onubense desde el texto de la direccion. None si no consta."""
    d = (direccion or "").lower()
    for m in sorted(MUNIS_HUELVA, key=len, reverse=True):
        if re.search(r"\b" + re.escape(m) + r"\b", d):
            return m.title()
    if cp and cp.startswith("21"):
        return "Huelva"          # CP 21xxx sin municipio explicito -> provincia, no inventamos
    return None


# ---------------------------------------------------------------- A) BORME 21
def desde_borme():
    """Re-lee el raw del BORME y recupera el domicilio COMPLETO del XML del BOE."""
    ruta = os.path.join(BASE, "raw", "borme_cnae62_2026-09-18.jsonl")
    if not os.path.exists(ruta):
        return []
    pend = [json.loads(l) for l in open(ruta) if l.strip()]
    pend = [r for r in pend if r.get("provincia") == "HUELVA"]

    por_url = {}
    for r in pend:
        por_url.setdefault(r["evidencia_url"], []).append(r["nombre"])

    out = []
    for url, nombres in por_url.items():
        xml = get(url)
        if not xml:
            continue
        for t in re.split(r'<p class="articulo">', xml)[1:]:
            m = re.search(r"^(.*?)</p>", t, re.S)
            if not m:
                continue
            nom = re.sub(r"<[^>]+>", "", m.group(1)).strip()
            nom = re.sub(r"^\d+\s*-\s*", "", nom)
            if not any(nom.startswith(n.split(" SL")[0][:18]) for n in nombres):
                continue
            parr = re.findall(r'<p class="parrafo">(.*?)</p>', t[m.end():], re.S)
            txt = re.sub(r"\s+", " ", " ".join(re.sub(r"<[^>]+>", " ", p) for p in parr))
            dom = re.search(r"Domicilio:\s*(.*?)(?:\.\s*(?:Capital|Nombramientos|Datos)|\Z)", txt)
            dire = re.sub(r"\s+", " ", dom.group(1)).strip() if dom else None
            cp = CP_RE.search(dire or "")
            cp = cp.group(1) if cp else None
            if not cp or not cp.startswith("21"):
                continue                      # sin CP onubense -> fuera (evita ruido)
            art = re.search(r"BORME-A-\d+-\d+-21", url).group(0)
            out.append({
                "nombre": nom,
                "municipio": municipio_de(dire, cp),
                "direccion": f"{dire}, {cp}" if dire else None,
                "cp": cp,
                "tipologias": ["DESARROLLO"],
                "evidencia_url": url,
                "notas": f"CNAE 62 constitucion BORME {art}",
            })
        time.sleep(0.4)
    return out


# ------------------------------------------------------------- B) DIRECTORIOS
def desde_digitalpulse():
    """15 agencias onubenses con calle + CP del listado publico."""
    url = "https://digitalpulse.media/listados/agencias-de-desarrollo-de-software/huelva/"
    h = get(url)
    if not h:
        return []
    import html as _h
    h = re.sub(r"<script.*?</script>", "", h, flags=re.S | re.I)
    h = re.sub(r"<style.*?</style>", "", h, flags=re.S | re.I)
    t = _h.unescape(re.sub(r"<[^>]+>", "\n", h))
    lines = [l.strip() for l in t.split("\n") if l.strip()]
    out, i = [], 0
    while i < len(lines) - 1:
        nom, nxt = lines[i], lines[i + 1]
        mm = re.search(r"^(.*?),\s*(21\d{3}),\s*(.+)$", nxt)
        if mm and not re.match(r"^\d", nom) and len(nom) > 2:
            dire, cp, muni = mm.group(1).strip(), mm.group(2), mm.group(3).strip()
            # descarta filas que no son empresa (menu, FAQ, etc.)
            if not re.search(r"Preguntas|¿|^Ver |^Servicios", nom):
                out.append({
                    "nombre": nom,
                    "municipio": muni,
                    "direccion": f"{dire}, {cp} {muni}",
                    "cp": cp,
                    "tipologias": ["DESARROLLO"],
                    "evidencia_url": url,
                    "notas": "Directorio Digital Pulse Media (agencias desarrollo software Huelva)",
                })
            i += 2
            continue
        i += 1
    return out


def desde_proveedores():
    """5 proveedores de desarrollo de software en Huelva ciudad."""
    url = "https://www.proveedores.com/desarrollo-de-software/huelva-ciudad"
    h = get(url)
    if not h:
        return []
    out = []
    for m in re.finditer(r'href="(/proveedores/[^"]+)"[^>]*>\s*(?:<[^>]+>\s*)*([^<]{2,60})', h):
        nom = m.group(2).strip()
        if not nom or nom.lower().startswith(("ver ", "todo")):
            continue
        out.append({
            "nombre": nom,
            "municipio": "Huelva",
            "direccion": None,
            "cp": None,
            "tipologias": ["DESARROLLO"],
            "evidencia_url": url,
            "notas": "Proveedores.com — Desarrollo de Software, Huelva (Ciudad)",
        })
    return out


# ------------------------------------------------------------------ ensamblado
def norm(n):
    return re.sub(r"\s+", " ", n or "").strip().lower()


def main():
    todos = []
    for fn in (desde_borme, desde_digitalpulse, desde_proveedores):
        try:
            r = fn()
        except Exception as e:
            print(f"  ! {fn.__name__}: {e}")
            r = []
        print(f"  {fn.__name__}: {len(r)}")
        todos += r

    # dedupe por nombre normalizado (mismo criterio que el merge del orquestador)
    vistos, uniq = set(), []
    for r in todos:
        k = norm(r["nombre"])
        if not k or k in vistos:
            continue
        vistos.add(k)
        uniq.append(r)

    # REGLA DURA: descartar lo que no se pueda atar a Huelva
    validos = [r for r in uniq
               if r.get("evidencia_url")
               and (r.get("cp", "") or "").startswith("21")
               and (r.get("municipio") or r.get("direccion"))]
    fuera = [r["nombre"] for r in uniq if r not in validos]
    if fuera:
        print(f"  descartados (sin CP 21xxx / sin municipio): {len(fuera)}")
        for f in fuera:
            print(f"    - {f}")

    salida = fichas(validos, "F1_DIRECTORIOS_HUELVA", "HUELVA", FECHA)
    escribe(salida, "f1_directorios_huelva", "huelva", FECHA)
    return salida


def _demo():
    """Self-check: el filtro de CP y el dedupe son la logica que rompe en silencio."""
    assert municipio_de("C/ RABIDA, 10 21001", "21001") == "Huelva"
    assert municipio_de("ANIBAL GONZALEZ, 27 21200 (ARACENA)", "21200") == "Aracena"
    assert municipio_de("Calle Falsa 123, 41092 Sevilla", "41092") is None
    assert CP_RE.search("21410 (ISLA CRISTINA)").group(1) == "21410"
    assert norm("  Onubensys.com ") == "onubensys.com"


if __name__ == "__main__":
    _demo()
    main()
