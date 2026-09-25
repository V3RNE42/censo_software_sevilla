"""Cruza el censo con el BORME para detectar empresas EXTINGUIDAS o en concurso.

Fuente: API de datos abiertos del BOE (gratis, sin key, sin login).
  https://www.boe.es/diario_borme/xml.php?id=BORME-A-<anio>-<dia>-<prov>
Provincias: Sevilla=41  Huelva=21  Malaga=29

Por que: Google Maps no da fecha de resena sin sesion, asi que la pregunta
"¿esta viva?" queda sin responder. El BORME publica el acto de cierre
literal ('Extincion.', 'Disolucion. Voluntaria.', 'Cierre provisional hoja
registral', 'Situacion concursal') -- eso si es prueba.

Limite medido: el BORME NO publica CIF. El cruce es por nombre normalizado.
El nombre del censo es la razon social o el nombre comercial; el BORME solo
tiene razon social registral. Muchas fichas no casaran. Se informa, no se
inventa.

Uso:
  python3 scripts/borme_cruce.py --desde 2024-01-01            # dry-run
  python3 scripts/borme_cruce.py --desde 2024-01-01 --aplicar
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
import time
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EMPRESAS = os.path.join(RAIZ, "data", "empresas.json")
OVERLAY = os.path.join(RAIZ, "data", "actividad_maps.json")
CACHE = os.path.join(RAIZ, "data", "borme_cache")

PROV = {"sev": 41, "sin": 21, "mal": 29}
# actos que prueban cese de actividad, con su veredicto
CIERRE = [
    ("Extinción", "CERRADO"),
    ("Extincion", "CERRADO"),
    ("Disolución. Voluntaria", "CERRADO"),
    ("Disolucion. Voluntaria", "CERRADO"),
    ("Finalización fase Liquidación", "CERRADO"),
    ("Cierre provisional hoja registral", "CONCURSO"),
    ("Situación concursal", "CONCURSO"),
    ("Situacion concursal", "CONCURSO"),
]
SUFIJOS = re.compile(
    r"\b(sl|slu|sa|sau|sll|sc|cb|sociedad|limitada|anonima|unipersonal|"
    r"españa|spain|ltd|incorporated|inc)\b")


def norm(s):
    """Clave de cruce: sin acentos, sin sufijo societario, sin puntuacion."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = SUFIJOS.sub(" ", s)
    return re.sub(r"[^a-z0-9]", "", s) or None


def descarga(anio, dia, prov, pausa=0.4):
    """XML de un BORME provincial. Cache en disco: el BOE no cambia el pasado."""
    os.makedirs(CACHE, exist_ok=True)
    p = os.path.join(CACHE, f"{anio}-{dia}-{prov}.xml")
    if os.path.exists(p):
        return open(p, encoding="utf-8").read()
    url = f"https://www.boe.es/diario_borme/xml.php?id=BORME-A-{anio}-{dia}-{prov}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "censo-sevilla/1.0"})
        raw = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
    except Exception:
        return None                      # fin de semana, festivo o sin edicion
    if "<documento" not in raw:
        return None
    open(p, "w", encoding="utf-8").write(raw)
    time.sleep(pausa)
    return raw


def anuncios(raw):
    """[(nombre_razon_social, texto_actos)] de un XML del BORME."""
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return []
    ps = list(root.iter("p"))
    out = []
    for i, p in enumerate(ps):
        if p.get("class") == "articulo":
            sig = " ".join((q.text or "") for q in ps[i + 1:i + 3]
                           if q.get("class") == "parrafo")
            out.append(((p.text or "").strip(), sig))
    return out


def cierre_de(texto):
    for clave, ver in CIERRE:
        if clave in texto:
            return ver, clave
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--desde", default="2024-01-01")
    ap.add_argument("--aplicar", action="store_true")
    a = ap.parse_args()

    censo = json.load(open(EMPRESAS, encoding="utf-8"))
    overlay = {x["id"]: x for x in json.load(open(OVERLAY, encoding="utf-8"))}
    indice = {}
    for f in censo:
        k = norm(f.get("nombre") or "")
        if k:
            indice.setdefault(k, []).append(f)

    inicio = dt.date.fromisoformat(a.desde)
    hoy = dt.date.today()
    print(f"censo: {len(censo)} | desde {inicio} | provincias {list(PROV)}", flush=True)

    casos, dias_ok = {}, 0
    d = inicio
    while d <= hoy:
        for pre, prov in PROV.items():
            raw = descarga(d.year, d.timetuple().tm_yday, prov)
            if not raw:
                continue
            dias_ok += 1
            for nombre_borme, texto in anuncios(raw):
                c = cierre_de(texto)
                if not c:
                    continue
                k = norm(nombre_borme)
                for f in indice.get(k, []):
                    ver, clave = c
                    # CONCURSO no prueba cierre: puede seguir operando
                    prev = casos.get(f["id"])
                    if prev and prev[0] == "CERRADO":
                        continue
                    casos[f["id"]] = (ver, clave, nombre_borme, str(d))
        if d.day == 1:
            print(f"  {d} ... casos={len(casos)}", flush=True)
        d += dt.timedelta(days=1)

    print(f"\nediciones leidas: {dias_ok}")
    print(f"empresas del censo con acto de cierre/Concurso: {len(casos)}")
    for fid, (ver, clave, nb, fecha) in sorted(casos.items()):
        f = next(x for x in censo if x["id"] == fid)
        print(f"  {fid:>10} {ver:<8} {fecha}  {(f.get('nombre') or '')[:34]:<34} <- '{clave}' en BORME: {nb[:34]}")

    if a["aplicar"] and casos:
        for fid, (ver, clave, nb, fecha) in casos.items():
            o = overlay.get(fid)
            if not o:
                continue
            o["veredicto"] = ver
            o["razones"] = [f"BORME {fecha}: {clave}",
                            f"razon social registral: {nb}",
                            "fuente: BOE datos abiertos (sin key)"]
            o["borme_acto"] = clave
            o["borme_fecha"] = fecha
        json.dump(list(overlay.values()), open(OVERLAY, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        from collections import Counter
        print("\noverlay:", Counter(o["veredicto"] for o in overlay.values()))
    elif not a["aplicar"]:
        print("\n(dry-run: nada escrito. Repetir con --aplicar)")


if __name__ == "__main__":
    main()
