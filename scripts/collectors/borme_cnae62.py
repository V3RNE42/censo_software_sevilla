#!/usr/bin/env python3
"""E1 — BORME por CNAE 62 (Sevilla 41 / Malaga 29).

Via: API datos abiertos BOE.
  sumario:  https://boe.es/datosabiertos/api/borme/sumario/{AAAAMMDD}   (Accept: application/json)
  provincia: https://www.boe.es/diario_borme/xml.php?id=BORME-A-{AAAA}-{N}-{prov}

NO existe endpoint por CNAE. BORME se publica por FECHA + PROVINCIA y el CNAE
solo aparece como texto libre dentro de "Objeto social" (y no siempre).
Por tanto: descargar N dias habiles de las provincias 41 y 29 y hacer grep
sobre el objeto social. Esto es un muestreo, NO un censo.

Uso: python3 borme_cnae62.py [n_dias]
"""
import json
import re
import sys
import time
import urllib.request
import urllib.error
import datetime

UA = {"User-Agent": "censo-software-sevilla/1.0 (julio@cabanillas.dev)"}
SUMARIO = "https://boe.es/datosabiertos/api/borme/sumario/{}"
PROV_XML = "https://www.boe.es/diario_borme/xml.php?id={}"

# CNAE 62 = programacion, consultoria informatica y otras actividades de servicios
# de informacion. Subclases 6201/6202/6203/6209.
CNAE_RE = re.compile(r"\b620[1239]\b")
PROG_RE = re.compile(
    r"programaci[oó]n\s+inform[aá]tica|consultor[ií]a\s+inform[aá]tica|"
    r"actividades\s+de\s+programaci[oó]n|servicios\s+de\s+informaci[oó]n",
    re.I,
)
ART_RE = re.compile(r'<p class="articulo">(.*?)</p>', re.S)
PAR_RE = re.compile(r'<p class="parrafo">(.*?)</p>', re.S)


def get(url, accept=None):
    h = dict(UA)
    if accept:
        h["Accept"] = accept
    req = urllib.request.Request(url, headers=h)
    for intento in range(3):
        try:
            with urllib.request.urlopen(req, timeout=45) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code in (404, 400):
                return None            # dia sin BORME / no existe -> valido
            time.sleep(2 * (intento + 1))
        except Exception:
            time.sleep(2 * (intento + 1))
    return None


def dias_habiles(n, hasta=None):
    d = hasta or datetime.date(2026, 9, 17)
    out = []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d -= datetime.timedelta(days=1)
    return out


def parse_provincia(xml):
    """Devuelve [(nombre, objeto_social_texto)] del XML provincial."""
    if not xml:
        return []
    trozos = re.split(r'<p class="articulo">', xml)[1:]
    out = []
    for t in trozos:
        m = re.search(r"^(.*?)</p>", t, re.S)
        if not m:
            continue
        nombre = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        nombre = re.sub(r"^\d+\s*-\s*", "", nombre)      # quita "242864 - "
        resto = t[m.end():]
        parr = re.findall(r'<p class="parrafo">(.*?)</p>', resto, re.S)
        texto = " ".join(re.sub(r"<[^>]+>", " ", p) for p in parr)
        texto = re.sub(r"\s+", " ", texto)
        out.append((nombre, texto))
    return out


def main():
    n_dias = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    provincias = {"41": "SEVILLA", "29": "MALAGA"}
    encontrados = {k: [] for k in provincias}
    stats = {k: {"fechas": 0, "empresas": 0, "match_cnae": 0, "match_prog": 0}
             for k in provincias}

    for fecha in dias_habiles(n_dias):
        ymd = fecha.strftime("%Y%m%d")
        raw = get(SUMARIO.format(ymd), accept="application/json")
        if not raw:
            print(f"  {ymd}: sin sumario (404/no publicado)")
            continue
        try:
            doc = json.loads(raw)
        except Exception:
            continue
        items = []
        for dd in doc.get("data", {}).get("sumario", {}).get("diario", []):
            for s in dd.get("seccion", []):
                its = s.get("item", [])
                if isinstance(its, dict):      # seccion con un solo item
                    its = [its]
                items.extend(i for i in its if isinstance(i, dict))
        for prov, nom in provincias.items():
            ids = [it["identificador"] for it in items
                   if it.get("identificador", "").endswith("-" + prov)
                   and it.get("identificador", "").startswith("BORME-A")]
            if not ids:
                continue
            stats[prov]["fechas"] += 1
            xml = get(PROV_XML.format(ids[0]))
            for nombre, texto in parse_provincia(xml):
                stats[prov]["empresas"] += 1
                m_cnae = bool(CNAE_RE.search(texto))
                m_prog = bool(PROG_RE.search(texto))
                if m_cnae or m_prog:
                    encontrados[prov].append({
                        "nombre": nombre,
                        "fecha_borme": ymd,
                        "match": "CNAE_620x" if m_cnae else "OBJETO_SOCIAL",
                        "objeto_social": texto[:400],
                        "evidencia_url": PROV_XML.format(ids[0]),
                        "fuente": "BORME_BOE",
                    })
                if m_cnae:
                    stats[prov]["match_cnae"] += 1
                if m_prog:
                    stats[prov]["match_prog"] += 1
            time.sleep(0.4)   # 1 req/s por dominio (BOE)
        time.sleep(0.4)

    print(json.dumps(stats, indent=2, ensure_ascii=False))
    for prov, nom in provincias.items():
        print(f"\n### {nom}: {len(encontrados[prov])} candidatos CNAE62/objeto social")
        for e in encontrados[prov]:
            print(f"  {e['fecha_borme']} | {e['nombre']} | {e['match']}")

    with open("/root/censo_software_sevilla/raw/borme_cnae62_2026-09-18.jsonl", "w") as f:
        for prov in provincias:
            for e in encontrados[prov]:
                e["provincia"] = provincias[prov]
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
    print("\n-> raw/borme_cnae62_2026-09-18.jsonl")


if __name__ == "__main__":
    main()
