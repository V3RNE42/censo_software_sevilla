#!/usr/bin/env python3
"""E2 — Empresas de desarrollo desde ofertas de empleo publicadas en portales IT.

Fuentes:
  tecnoempleo  GET https://www.tecnoempleo.com/busqueda-empleo.php?pr=<code>&pagina=N
               (pr: 274=Sevilla, 264=Málaga — código interno, NO el INE)
  manfred      GET https://www.getmanfred.com/api/v2/public/offers?onlyActive=false&lang=ES
               API pública JSON; filtro de ciudad local (locations[])

Bloqueadas (medido 18/09/2026, ver informes/e2_empleo.md):
  infojobs     Distil captcha -> canonical apunta a captcha.xhtml
  linkedin     sin sesión ignora geoId: resuelve "Sevilla" a Valle del Cauca (Colombia)

D4 del plan §1: publicar ofertas de desarrollo acredita actividad de desarrollo.
La fecha de la oferta es PROXY DE ACTIVIDAD (plan §4.2) -> va en notas.

Uso:  python3 scripts/collectors/e2_empleo.py [--fuentes tecnoempleo,manfred]
"""
import argparse
import json
import os
import re
import sys
import time
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402

HOY = date.today().isoformat()

# Tecnoempleo: código interno de provincia (leído del <select name="pr">)
TECNO_PROV = {"SEVILLA": 274, "MALAGA": 264}
TECNO_MAX_PAG = 30          # tope de seguridad; el portal pagina 30 ofertas/página
TECNO_POR_PAG = 30

# Ciudades del ámbito tal y como las escribe Manfred en locations[]
MANFRED_CIUDADES = ("sevilla", "málaga", "malaga", "marbella", "torremolinos",
                    "benalmádena", "benalmadena", "fuengirola", "mijas",
                    "estepona", "rincón de la victoria", "rincon de la victoria",
                    "alhaurín de la torre", "alhaurin de la torre", "antequera",
                    "vélez-málaga", "velez-malaga", "cártama", "cartama",
                    "ronda", "écija", "ecija", "utrera", "dos hermanas",
                    "mairena del aljarafe", "alcalá de guadaíra", "alcala de guadaira")

_MUNICIPIO = re.compile(r"<b>([^<]+)</b>")
_FECHA = re.compile(r"(\d{2}/\d{2}/\d{4})")
_EMPRESA = re.compile(
    r'<a title="Ofertas de Empleo ([^"]+)" href="(https://www\.tecnoempleo\.com/[^"]+)"')
_PUESTO = re.compile(r'<a href="(https://www\.tecnoempleo\.com/[^"]*?/rf-[0-9a-f]+)" '
                     r'class="font-weight-bold[^"]*"[^>]*>\s*([^<]+)')
_CIUDAD_SEP = re.compile(r'<b>([^<]+)</b>')


def _iso(fecha_ddmmaaaa):
    """18/09/2026 -> 2026-09-18."""
    d, m, y = fecha_ddmmaaaa.split("/")
    return f"{y}-{m}-{d}"


def tecnoempleo(provincia):
    """Una ficha por OFERTA (el dedupe a empresa lo hace merge_fuentes)."""
    pr = TECNO_PROV[provincia]
    filas, urls_vistas = [], set()
    for pag in range(1, TECNO_MAX_PAG + 1):
        url = f"https://www.tecnoempleo.com/busqueda-empleo.php?pr={pr}&pagina={pag}"
        status, html = C.get(url)
        if status != 200 or not html:
            print(f"  [tecnoempleo/{provincia}] pág {pag}: HTTP {status} — paro", file=sys.stderr)
            break
        # cada oferta empieza en un ancla <a name="rf-...">
        bloques = re.split(r'<a name="rf-', html)[1:]
        if not bloques:
            break
        nuevos = 0
        for b in bloques:
            emp = _EMPRESA.search(b)
            pue = _PUESTO.search(b)
            if not emp or not pue:
                continue
            job_url = pue.group(1)
            if job_url in urls_vistas:
                continue
            urls_vistas.add(job_url)
            nuevos += 1

            resto = b[emp.end():]
            mun = _MUNICIPIO.search(resto)
            fec = _FECHA.search(resto)
            municipio = mun.group(1).strip() if mun else None
            # '(Híbrido) y otras' -> el municipio real puede ser otro; se marca en notas
            otras = "y otras" in resto[:400]
            fecha = _iso(fec.group(1)) if fec else None

            filas.append({
                "nombre": emp.group(1).strip(),
                "municipio": municipio,
                "web": None,
                "tipologias": ["CONSULTORA"],   # se reclasifica en Fase 4
                "evidencia_url": job_url,
                "notas": (f"puesto={pue.group(2).strip()}; portal=tecnoempleo; "
                          f"empresa_url={emp.group(2)}; fecha_oferta={fecha}"
                          + ("; municipio_aproximado='y otras'" if otras else "")),
            })
        print(f"  [tecnoempleo/{provincia}] pág {pag}: {len(bloques)} ofertas, "
              f"{nuevos} nuevas (acum {len(filas)})", file=sys.stderr)
        if nuevos == 0:
            break
        time.sleep(1)                       # 1 req/s por dominio
    return filas


def manfred(provincia):
    """Ofertas de Manfred con ciudad en el ámbito. Proxy de actividad = updatedAt."""
    status, body = C.get("https://www.getmanfred.com/api/v2/public/offers"
                         "?onlyActive=false&lang=ES", timeout=60)
    if status != 200 or not body:
        print(f"  [manfred] API HTTP {status} — bloqueada", file=sys.stderr)
        return []
    try:
        ofertas = json.loads(body)
    except json.JSONDecodeError:
        print("  [manfred] respuesta no-JSON — bloqueada", file=sys.stderr)
        return []

    filas = []
    for o in ofertas:
        locs = o.get("locations") or []
        hit = next((l for l in locs
                    if any(c in l.lower() for c in MANFRED_CIUDADES)), None)
        if not hit:
            continue
        empresa = (o.get("company") or {}).get("name")
        if not empresa:
            continue
        fecha = (o.get("updatedAt") or "")[:10] or None
        filas.append({
            "nombre": empresa.strip(),
            "municipio": hit.split(",")[0].strip(),
            "web": (o.get("company") or {}).get("web"),
            "tipologias": ["CONSULTORA"],
            "evidencia_url": f"https://www.getmanfred.com/ofertas-empleo/{o['slug']}",
            "notas": (f"puesto={o.get('position')}; portal=manfred; "
                      f"fecha_oferta={fecha}"),
        })
    print(f"  [manfred/{provincia}] {len(ofertas)} ofertas totales, "
          f"{len(filas)} en el ámbito", file=sys.stderr)
    return filas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fuentes", default="tecnoempleo,manfred")
    a = ap.parse_args()
    fuentes = [f.strip() for f in a.fuentes.split(",") if f.strip()]

    for provincia in ("SEVILLA", "MALAGA"):
        print(f"== {provincia}", file=sys.stderr)
        filas = []
        if "tecnoempleo" in fuentes:
            filas += tecnoempleo(provincia)
        if "manfred" in fuentes:
            filas += manfred(provincia)
        if not filas:
            print(f"{provincia}: 0 fichas — todas las fuentes fallaron", file=sys.stderr)
            continue
        # nombre de fichero compuesto si hay >1 portal, para no pisar el otro agente
        fuente = "E2_EMPLEO" if len(fuentes) > 1 else f"E2_{fuentes[0].upper()}"
        salida = C.fichas(filas, fuente, provincia, HOY)
        C.escribe(salida, fuente, provincia, HOY)


if __name__ == "__main__":
    main()
