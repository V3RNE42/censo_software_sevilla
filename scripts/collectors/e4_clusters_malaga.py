#!/usr/bin/env python3
"""E4b — Clústeres/parques TIC de la provincia de Málaga.

Fuentes verificadas (18/09/2026):
  - PTA / Málaga TechPark  : AJAX wp-admin/admin-ajax.php?action=get_products&pg=N
                             (463 empresas) + ficha de detalle /empresas/<slug>/
  - PDF oficial            : wp-content/uploads/2026/04/Lista-Empresas-a-27-de-abril-26.pdf
                             (contraste; no se parsea: las fichas web ya traen sector+web)
  - Polo Digital Málaga    : polodigital.malaga.eu / polodigital.eu (ver informe)

Regla dura: sin URL de evidencia no hay ficha. La evidencia es la ficha de detalle
del PTA (una por empresa), no el listado agregado.
"""
import html
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C

FECHA = "2026-09-18"
FUENTE = "E4_TECHPARK_MALAGA"
BASE = "https://www.pta.es"
AJAX = BASE + "/wp-admin/admin-ajax.php?action=get_products&pg={pg}"

# Sectores del PTA que son candidatos a desarrollo de software (§1.1).
# 'Información, Informática y Telecomunicaciones' es el núcleo; los demás entran
# solo si la descripción acredita D1/D2 (saaS, app, desarrollo, software, plataforma...).
SECTORES_SOFT = {"información, informática y telecomunicaciones"}

# Señales de desarrollo en la descripción de la ficha (D1/D2 del plan §1).
RX_DEV = re.compile(
    r"desarrollo\s+de\s+software|desarrollo\s+de\s+aplicacion|desarrollo\s+de\s+proyectos?\s+"
    r"inform|software\s+(?:a\s+medida|de\s+gestion|de\s+gesti\u00f3n)|f\u00e1brica\s+de\s+software|"
    r"saaS|cloud|plataforma\s+(?:digital|tecnol)|aplicaciones?\s+m\u00f3vil|app\s+m\u00f3vil|"
    r"desarrollo\s+web|desarrollo\s+de\s+app|microservicios|big\s*data|inteligencia\s+artificial|"
    r"machine\s+learning|data\s+science|blockchain|videojuegos|gamificaci\u00f3n|"
    r"ingenier\u00eda\s+de\s+software|desarrollo\s+de\s+producto\s+software|"
    r"soluciones?\s+inform\u00e1tic|transformaci\u00f3n\s+digital|full\s*stack|"
    r"consultor\u00eda\s+(?:tecnol|inform)|neashore|nearshore|outsourcing\s+it|"
    r"erp|crm|odoo|sap\s+business|implantaci\u00f3n\s+de\s+sistemas|business\s+intelligence",
    re.I,
)

# Ruido explícito (§1.3): reventa, restauración, formación sin desarrollo, inmobiliaria...
RX_RUIDO = re.compile(
    r"^restaurant|hosteler\u00eda|inmobiliaria|gestor\u00eda|asesor\u00eda\s+(fiscal|laboral|jur\u00eddica)|"
    r"reparaci\u00f3n|venta\s+de\s+ordenadores|suministros?\s+industriales|"
    r"taller|cl\u00ednic|dental|abogad|seguros|banco|colegio|guarder\u00eda|"
    r"academia\s+de\s+idiomas|gimnasio|florister\u00eda|supermercado",
    re.I,
)


def ajax_pagina(pg):
    st, body = C.get(AJAX.format(pg=pg))
    if st != 200:
        return None
    try:
        return json.loads(body)
    except Exception:
        return None


def listado():
    """Devuelve {nombre: url_ficha} paginando hasta que una página repita contenido."""
    out, vistos = {}, set()
    for pg in range(1, 60):
        d = ajax_pagina(pg)
        if not d:
            print(f"[aviso] pg {pg}: sin JSON, paro", file=sys.stderr)
            break
        v = d.get("view", "")
        nombres = re.findall(r'<div class="title">(.*?)</div>', v)
        links = re.findall(r'href="(https://www\.pta\.es/empresas/[^"]*)"', v)
        nuevos = 0
        for n, l in zip(nombres, links):
            n = html.unescape(n).strip()
            if n and n not in out:
                out[n] = l
                nuevos += 1
        vistos.add(hash(v))
        if not nombres or nuevos == 0:
            break
        time.sleep(0.4)          # 1 req/s por dominio (contrato)
    return out


def parse_detalle(h, url):
    """Extrae sector, edificio, descripcion, direccion, tel, email, web de la ficha."""
    b = re.sub(r"<script.*?</script>", " ", h, flags=re.S)
    b = re.sub(r"<style.*?</style>", " ", b, flags=re.S)
    txt = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", b)))

    d = {}
    m = re.search(r"Sector:\s*(.*?)\s*\|\s*Edificio:\s*(.*?)\s+(.*?)(?:Visitar web|Informaci\u00f3n de contacto)", txt)
    if m:
        d["sector"], d["edificio"], d["descripcion"] = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
    else:
        m2 = re.search(r"Sector:\s*(.*?)\s+(?:Edificio:|Visitar web|Informaci\u00f3n de contacto)", txt)
        d["sector"] = m2.group(1).strip() if m2 else None
        d["edificio"] = None
        m3 = re.search(r"Visitar web\s*(.*?)\s*Informaci\u00f3n de contacto", txt)
        d["descripcion"] = m3.group(1).strip() if m3 else None

    m = re.search(r"Direcci\u00f3n:\s*(.*?)\s*(?:Tel\u00e9fono:|Email:|Web:|Volver)", txt)
    d["direccion"] = m.group(1).strip() if m else None
    m = re.search(r"Tel\u00e9fono:\s*([\d\s+.-]{6,})", txt)
    d["telefono"] = re.sub(r"\s+", " ", m.group(1)).strip(" .-") if m else None
    m = re.search(r"Email:\s*([^\s|]+@[^\s|]+)", txt)
    d["email"] = m.group(1).strip(" .") if m else None
    m = re.search(r"Web:\s*(https?://[^\s|]+)", txt)
    d["web"] = m.group(1).strip(" .") if m else None
    if not d["web"]:                      # fallback: botón "Visitar web"
        m = re.search(r'href="(https?://(?!(?:www\.)?pta\.es)[^"]+)"[^>]*class="[^"]*btn[^"]*"', h)
        d["web"] = m.group(1) if m else None
    d["_evidencia"] = url
    return d


def municipio_de(direccion, edificio):
    """El PTA esta en Malaga capital (C/ Severo Ochoa, Campanillas). Sus empresas
    residentes tienen sede en el parque -> municipio Malaga. No lo inventamos: la
    direccion de la ficha pertenece al recinto del PTA (CP 29590)."""
    return "Malaga"


def main():
    comps = listado()
    print(f"[info] listado PTA: {len(comps)} empresas", file=sys.stderr)

    rows, excepciones = [], []
    for i, (nombre, url) in enumerate(sorted(comps.items()), 1):
        st, h = C.get(url, timeout=25)
        if st != 200 or len(h) < 500:
            excepciones.append({"nombre": nombre, "url": url, "motivo": f"HTTP {st}"})
            continue
        d = parse_detalle(h, url)
        sector = (d.get("sector") or "").strip()
        desc = (d.get("descripcion") or "").strip()
        notas = f"PTA sector={sector}"

        if sector.lower() in SECTORES_SOFT:
            rows.append({
                "nombre": nombre, "municipio": "Malaga",
                "direccion": d.get("direccion"), "web": d.get("web"),
                "telefono": d.get("telefono"), "email": d.get("email"),
                "tipologias": ["CONSULTORA", "FACTORIA", "PRODUCTO"][:1] + (["PRODUCTO"] if re.search(r"saaS|plataforma propia|app", desc, re.I) else []),
                "notas": notas + " | " + desc[:200],
                "evidencia_url": url,
            })
        elif RX_DEV.search(desc) and not RX_RUIDO.search(desc):
            rows.append({
                "nombre": nombre, "municipio": "Malaga",
                "direccion": d.get("direccion"), "web": d.get("web"),
                "telefono": d.get("telefono"), "email": d.get("email"),
                "tipologias": ["CONSULTORA"],
                "notas": notas + " | " + desc[:200],
                "evidencia_url": url,
            })
        if i % 50 == 0:
            print(f"[info] {i}/{len(comps)} procesadas, {len(rows)} fichas", file=sys.stderr)
        time.sleep(0.5)      # 1 req/s

    salida = C.fichas(rows, FUENTE, "MALAGA", FECHA)
    C.escribe(salida, FUENTE, "MALAGA", FECHA)
    print(f"bloqueos: {len(excepciones)} fichas no accesibles", file=sys.stderr)
    json.dump({"total_listado": len(comps), "fallidas": excepciones},
              open("/tmp/e4_pta_excepciones.json", "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
