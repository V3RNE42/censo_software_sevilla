#!/usr/bin/env python3
"""E3 — Parques tecnológicos: directorios de empresas residentes.

Fuentes verificadas (18/09/2026):
  PTA / Málaga TechPark   https://www.pta.es/empresas/  -> PDF del listado completo
  PCT Cartuja / Sevilla TechPark  https://sevillatechpark.es/empresas/ -> tabla HTML
  Aerópolis (Sevilla)     https://www.aeropolis.es/  -> 12 fichas en home (#empresas)
  Polo Digital (Málaga)   https://polodigital.es  -> caído (timeout)

Escribe raw/e3_parques_<provincia>_<fecha>.jsonl con el contrato de AGENTE_TEMPLATE.md.
NO geocodifica (lat/lng = null). Filtra solo desarrollo de software (§1.1/§1.3 del PLAN).
"""
import html
import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import get, fichas, escribe  # noqa: E402

FECHA = "2026-09-18"

# ---------------------------------------------------------------------------
# Filtro de desarrollo de software (§1.1 criterios D1-D4, §1.3 fronteras)
# ---------------------------------------------------------------------------

# Exclusión dura: reventa, retail, formación, hardware, telco pura, medios (§1.3).
DEV_NEG = re.compile(
    r"^\s*(?:canon|huawei|siemens|schneider|vodafone|telef[oó]nica|masorange|orange)\b|"
    r"reparaci[oó]n|tienda|papeler[ií]a|reprograf|"
    r"escuela|formaci[oó]n|academia|docencia|colegio|educaci[oó]n|"
    r"telefon[ií]a|distribuidor|distribuci[oó]n|venta (?:online|de)|comercializaci[oó]n|representaci[oó]n de productos|"
    r"hosteler[ií]a|restaurante|hotel|abogad|asesor[ií]a jur[ií]dica|notar[ií]a|"
    r"\bbanco\b|banca|seguros|"
    r"alquiler|inmobiliaria|promoci[oó]n(?:es)? (?:inmobiliaria|empresarial)|"
    r"traducci[oó]n|"
    r"aeroespacial|aeron[aá]utic|drones?|fabricaci[oó]n de (?:piezas|sensores|materiales|impresoras)",
    re.I,
)

# Entidades públicas / centros de investigación: fuera del censo de EMPRESAS (§1.1.3).
EXC_PUBLICO = re.compile(
    r"consejo superior de investigaciones|csic|\bcsic\b|universidad|university|\buma\b|"
    r"instituto (?:de|universitario|andaluz)|centro nacional|centro andaluz|"
    r"fundaci[oó]n p[uú]blica|agencia estatal|comisi[oó]n europea|\bjrc\b|"
    r"aemet|meteorolog[ií]a|doñana|observatorio|"
    r"administraci[oó]n p[uú]blica|diputaci[oó]n|ayuntamiento|"
    r"parque tecnol[oó]gico|sociedad gestora|asociaci[oó]n|cl[uú]ster|asociaci",
    re.I,
)

# Sector explícito de informática/telecom (PCT). Dentro de él SÍ se filtra por nombre.
SECTOR_SW = re.compile(r"telecomunicaciones e inform[aá]tica|inform[aá]tica", re.I)

# Buckets no-informáticos de los que SÍ puede salir un software (p. ej. "Ingeniería").
SECTOR_OTROS_OK = re.compile(r"^$|ingenier|electr[oó]nica|servicios avanzados", re.I)

# Señales fuertes de actividad de desarrollo (no basta "desarrollo" a secas).
DEV_FUERTE = re.compile(
    r"desarrollo de software|desarrollo de aplicacion|desarrollo aplicacion|"
    r"programaci[oó]n|software a medida|programaci[oó]n a medida|"
    r"f[aá]brica de software|ingenier[ií]a de software|software de gesti[oó]n|"
    r"desarrollo web|dise[nñ]o web|aplicaciones web|"
    r"consultor[ií]a inform[aá]tica|consultor[ií]a tecnol[oó]gica|"
    r"sistemas de informaci[oó]n|soluciones (?:inform[aá]ticas|tecnol[oó]gicas|digitales)|"
    r"tecnolog[ií]as de la informaci[oó]n|"
    r"inteligencia artificial|machine learning|data science|"
    r"bases de datos|big data|anal[ií]tica|ciber?seguridad|seguridad inform[aá]tica|"
    r"videojuego|gamificaci[oó]n|computer vision|"
    r"\bsaas\b|\berp\b|\bcrm\b|software",
    re.I,
)


# Persona física: nombre propio + 2 apellidos, SIN sufijo societario. Un autónomo
# con móvil personal es PII (dato personal identificable), no empresa censable.
# Medido en Huelva: 67 de 111 locales DIRCE son autónomos sin asalariados, así que
# esto NO es hipotético. OJO: 'Manuel Jesús Carbón Salas' tiene nombre COMPUESTO
# (4 palabras) — el patrón de 3 palabras no lo caza. Por eso se admiten 2-4.
PERSONA_FISICA = re.compile(
    r"^(?:[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+\s){2,4}[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+$")
MOVIL_ES = re.compile(r"(?:\+34[\s.]?)?[67]\d{2}[\s.]?\d{2,3}[\s.]?\d{2}[\s.]?\d{2}")
SUFIJO_SOCIETARIO = re.compile(
    r"\b(sl|s\.l|slu|s\.l\.u|sa|s\.a|sc|s\.c|cb|c\.b|slne|sociedad|limitada|"
    r"anonima|an[oó]nima|cooperativa|comunidad de bienes)\b", re.I)


def es_pii_autonomo(nombre, telefono, tiene_web=False):
    """True si es un particular con móvil: se descarta.

    Un autónomo CON web propia y marca comercial es un negocio (Abatic, Creadores
    Web Huelva) y se queda: la web es la seña de actividad empresarial. Uno sin web
    y con nombre de persona + móvil es un particular y no se censa.
    Medido: el criterio 'nombre de persona + móvil' a secas tiró 2 empresas reales.
    """
    if tiene_web or SUFIJO_SOCIETARIO.search(nombre or ""):
        return False
    return bool(PERSONA_FISICA.match((nombre or "").strip())
                and MOVIL_ES.search(telefono or ""))


def es_software(nombre, actividad, sector=""):
    """True si la entidad hace desarrollo de software. Fronteras §1.3."""
    if EXC_PUBLICO.search(nombre):
        return False
    if DEV_NEG.search(nombre) and not re.search(r"software|inform[aá]tica|tech|digital", nombre, re.I):
        return False
    if DEV_NEG.search(actividad):
        return False
    if sector and SECTOR_SW.search(sector):
        return True                     # bucket informático: no excluido arriba => software
    if sector and not SECTOR_OTROS_OK.search(sector):
        return False                    # sector ajeno (biotec, agro, hostelería...)
    if not actividad:
        # sin actividad descrita: solo aceptamos nombre inequívoco
        return bool(re.search(r"software|systems?|tech|digital|inform[aá]tica|\.io\b|\.ai\b|cloud", nombre, re.I))
    return bool(DEV_FUERTE.search(actividad))


def tipologias(nombre, actividad):
    t = []
    blob = f"{nombre} {actividad}".lower()
    if re.search(r"inteligencia artificial|machine learning|\bia\b|\bml\b|data |big data|anal[ií]tica", blob):
        t.append("DATA_IA")
    if re.search(r"videojuego|gamificaci", blob):
        t.append("VIDEOJUEGOS")
    if re.search(r"erp|crm|odoo|sap|integraci[oó]n|implantaci[oó]n", blob):
        t.append("INTEGRADOR")
    if re.search(r"software a medida|programaci[oó]n a medida|desarrollo a medida|f[aá]brica|factoria|nearshore|consultora|consultor[ií]a", blob):
        t.append("FACTORIA" if re.search(r"f[aá]brica|factoria|nearshore", blob) else "CONSULTORA")
    if re.search(r"consultor[ií]a inform[aá]tica|consultor[ií]a tecnol[oó]gica|proyectos|inform[aá]tica", blob):
        if "CONSULTORA" not in t:
            t.append("CONSULTORA")
    return t or ["PRODUCTO"]


# ---------------------------------------------------------------------------
# PTA / Málaga TechPark — PDF del listado de empresas
# ---------------------------------------------------------------------------

def pta_pdf_url():
    st, body = get("https://www.pta.es/empresas/")
    if st != 200:
        return None
    m = re.findall(r'href="(https://www\.pta\.es/wp-content/uploads/[^"]*[Ll]ista[^"]*\.pdf)"', body)
    return m[0] if m else None


def parse_pta_pdf(pdf_bytes, url):
    """Reensambla el PDF de columnas fijas en fichas. Solo devuelve las de software.

    Los offsets de columna CAMBIAN por sección (>30 variantes de cabecera), así que
    se derivan de la línea de cabecera activa, no de constantes.
    """
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(pdf_bytes)
        ruta_pdf = f.name
    try:
        txt = subprocess.run(["pdftotext", "-layout", ruta_pdf, "-"],
                             capture_output=True, text=True).stdout
    finally:
        os.unlink(ruta_pdf)

    entidades = []
    edificio = None
    cols = None  # no usado: el PDF no respeta offsets fijos (ver split)

    for raw in txt.split("\n"):
        linea = raw.rstrip()
        if not linea.strip() or linea.lstrip().startswith("Listado de Empresas"):
            continue
        m = re.search(r"Empresas e Instituciones instaladas en:\s*(.+?)\s*$", linea)
        if m:
            edificio = m.group(1).strip()
            continue
        if linea.strip().startswith("Empresa") and "Actividad" in linea:
            continue                          # fila de cabecera

        # El PDF NO respeta offsets fijos: el corte de columnas es la 1ª racha de 2+
        # espacios (los nombres/actividades nunca llevan dobles espacios internos).
        celdas = [c.strip() for c in re.split(r"\s{2,}", linea) if c.strip()]
        if not celdas:
            continue

        # Fila con nombre: arranca en columna 0. Si no, es continuación de la anterior.
        sangria = len(linea) - len(linea.lstrip())
        if sangria > 2 and entidades:
            # línea de continuación: reparte el texto extra en actividad/dirección
            extra = " ".join(celdas)
            entidades[-1]["_cont"].append(extra)
            continue

        nombre = celdas[0]
        entidades.append({"_nom": nombre, "_celdas": celdas[1:], "_cont": [],
                          "_edif": edificio})

    out = []
    for e in entidades:
        nombre = re.sub(r"\s+", " ", e["_nom"]).strip()
        # Descarta fragmentos de nombre partido por el PDF (empiezan en minúscula
        # o son solo sufijo societario) — sin esto se cuelan como "empresas" falsas.
        if not nombre or nombre[0].islower() or re.match(r"^(?:s\.?l\.?|s\.?a\.?|s\.?l\.?u)\.?,?$", nombre, re.I):
            continue
        # fragmento de nombre partido que empieza por sufijo societario suelto
        if re.match(r"^(?:technologies|sistemas|solutions|consulting|soluciones|servicios)\b[,\s]*s\.?l", nombre, re.I):
            continue
        # actividad = primera celda con texto; dirección = celda que parece dirección
        resto = list(e["_celdas"]) + e["_cont"]
        act = e["_celdas"][0] if e["_celdas"] else ""
        direc = ""
        for celda in e["_celdas"][1:]:
            if re.search(r"\b(?:c/|calle|avda|avenida|plaza|mar[ií]a curie|severo ochoa|kepler|einstein|"
                         r"l[oó]pez pe[nñ]alver|graham bell|iv[aá]n pavlov|boulevard|sever[oa]|"
                         r"thomas alva|josephine|charles darwin|max planck|rosalind)\b", celda, re.I):
                direc = celda
                break
        if not direc and len(e["_celdas"]) > 1:
            direc = e["_celdas"][1]
        act = re.sub(r"\s+", " ", act).strip()
        if e["_cont"] and act:
            act = (act + " " + " ".join(e["_cont"])).strip()

        if not es_software(nombre, act):
            continue
        web = next((c for c in e["_celdas"] if re.search(r"\.(?:es|com|net|org|io|ai|eu)\b", c, re.I) and " " not in c), "")
        web = f"https://{web}" if web.startswith("www.") else (web if web.startswith("http") else None)
        mail = next((c for c in e["_celdas"] if re.match(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", c, re.I)), None)
        out.append({
            "nombre": nombre,
            "municipio": "Campanillas" if re.search(r"campanillas|kepler|curie|ochoa|l[oó]pez pe[nñ]alver|einstein|thomas alva|graham bell|pavlov", direc, re.I) else "Málaga",
            "direccion": re.sub(r"\s+", " ", f"{direc} ({e['_edif']})").strip() if e["_edif"] else (direc or None),
            "web": web,
            "email": mail,
            "tipologias": tipologias(nombre, act),
            "notas": f"Actividad: {act}" if act else None,
            "evidencia_url": url,
        })
    return out, len(entidades)


# ---------------------------------------------------------------------------
# PCT Cartuja / Sevilla TechPark — tabla HTML
# ---------------------------------------------------------------------------

def parse_cartuja(html_body, url):
    m = re.search(r'<table id="tablepress-6".*?</table>', html_body, re.S)
    if not m:
        return [], 0
    rows = re.findall(r'<tr class="row-\d+">(.*?)</tr>', m.group(0), re.S)

    def cell(r, n):
        mm = re.search(r'<td class="column-%d">(.*?)</td>' % n, r, re.S)
        if not mm:
            return ""
        v = mm.group(1)
        a = re.search(r'href="([^"]+)"', v)
        return html.unescape(a.group(1)).strip() if a else html.unescape(re.sub(r"<[^>]+>", "", v)).strip()

    out = []
    for r in rows:
        sector, nombre, direc, web = cell(r, 1), cell(r, 2), cell(r, 3), cell(r, 4)
        if not nombre:
            continue
        if not es_software(nombre, f"{sector} {nombre}", sector):
            continue
        if not web or web.lower().startswith("(sin web"):
            web = None
        ciudad = "Sevilla"
        mc = re.search(r",\s*([A-Za-zÁÉÍÓÚÑáéíóúñ ]+),\s*\d{5}", direc)
        if mc:
            ciudad = mc.group(1).strip()
        out.append({
            "nombre": nombre,
            "municipio": ciudad,
            "direccion": direc or None,
            "web": web,
            "tipologias": tipologias(nombre, sector),
            "notas": f"Sector PCT: {sector}",
            "evidencia_url": url,
        })
    return out, len(rows)


# ---------------------------------------------------------------------------
# Aerópolis — bloque #empresas del home (12 fichas visibles)
# ---------------------------------------------------------------------------

def parse_aeropolis(html_body, url):
    m = re.search(r"Empresas con\s*sede en Aerópolis(.*)$", html_body, re.S)
    if not m:
        return [], 0
    blk = m.group(1)
    cards = re.findall(r'fusion-title-heading[^>]*>(.*?)</h3>.*?Categories:\s*(.*?)</div>', blk, re.S)
    out = []
    for crudo, cats in cards:
        nombre = html.unescape(re.sub(r"<[^>]+>", "", crudo)).strip()
        nombre = re.sub(r"^Empresas con sede en Aerópolis\s*", "", nombre).strip()
        cats = html.unescape(re.sub(r"<[^>]+>", " ", cats))
        cats = re.sub(r"Tags:.*", "", cats).strip(" ,")
        if not nombre or not es_software(nombre, cats):
            continue
        out.append({
            "nombre": nombre,
            "municipio": "La Rinconada",
            "direccion": "Aerópolis, La Rinconada (Sevilla)",
            "web": None,
            "tipologias": tipologias(nombre, cats),
            "notas": f"Aerópolis categorías: {cats}" if cats else None,
            "evidencia_url": url,
        })
    return out, len(cards)


# ---------------------------------------------------------------------------
def main():
    resumen = {}

    # --- PTA (Málaga) ---
    u = pta_pdf_url()
    if not u:
        resumen["pta"] = (0, 0, "fallo: no se encontró el PDF en /empresas/")
    else:
        import urllib.request
        body = None
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "censo-software-sevilla/1.0 (julio@cabanillas.dev)"})
            with urllib.request.urlopen(req, timeout=120) as r:
                body = r.read()
        except Exception as ex:
            resumen["pta"] = (0, 0, f"fallo: {ex}")
        if body and body.startswith(b"%PDF"):
            filas, total = parse_pta_pdf(body, u)
            escribe(fichas(filas, "E3_PARQUES_PTA", "MALAGA", FECHA), "e3_parques_pta", "MALAGA", FECHA)
            resumen["pta"] = (len(filas), total, u)
        elif body is not None:
            resumen["pta"] = (0, 0, "fallo: respuesta no es PDF")

    # --- PCT Cartuja / Sevilla TechPark ---
    st, body = get("https://sevillatechpark.es/empresas/")
    if st != 200:
        resumen["cartuja"] = (0, 0, f"fallo: HTTP {st}")
    else:
        filas, total = parse_cartuja(body, "https://sevillatechpark.es/empresas/")
        escribe(fichas(filas, "E3_PARQUES_CARTUJA", "SEVILLA", FECHA), "e3_parques_cartuja", "SEVILLA", FECHA)
        resumen["cartuja"] = (len(filas), total, "https://sevillatechpark.es/empresas/")

    # --- Aerópolis ---
    st, body = get("https://www.aeropolis.es/")
    if st != 200:
        resumen["aeropolis"] = (0, 0, f"fallo: HTTP {st}")
    else:
        filas, total = parse_aeropolis(body, "https://www.aeropolis.es/")
        escribe(fichas(filas, "E3_PARQUES_AEROPOLIS", "SEVILLA", FECHA), "e3_parques_aeropolis", "SEVILLA", FECHA)
        resumen["aeropolis"] = (len(filas), total, "https://www.aeropolis.es/")

    print("\n== E3 RESUMEN ==")
    for k, (n, tot, info) in resumen.items():
        print(f"{k:10} software={n:3} / total_parque={tot:4}  {info}")


if __name__ == "__main__":
    main()
