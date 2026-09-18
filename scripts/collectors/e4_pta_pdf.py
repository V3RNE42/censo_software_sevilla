#!/usr/bin/env python3
"""Parser del PDF oficial 'Listado de Empresas' del PTA / Malaga TechPark.

Fuente: https://www.pta.es/wp-content/uploads/2026/04/Lista-Empresas-a-27-de-abril-26.pdf
(link 'Descarga el listado completo de empresas aqui' de https://www.pta.es/empresas/)

Estructura (pdftotext -layout):
  'Empresas e Instituciones instaladas en: <EDIFICIO>'  -> bloque
  'Empresa  Actividad  Dirección  Teléfono  FAX  E-Mail  Web'  -> cabecera
  filas: columnas separadas por 2+ espacios. Celdas multilinea continuan en
         lineas siguientes empezando por espacios (sin nombre).

Metodo: split por 2+ espacios (robusto al kerning de -layout), reconstruccion
por posicion de columna.
"""
import re
import sys

BLOQUE_RX = re.compile(r"Empresas e Instituciones instaladas en:\s*(.+?)\s*$", re.I)
HEADER_RX = re.compile(r"^Empresa\s{2,}Actividad\s{2,}", re.I)
WEB_RX = re.compile(r"(?:https?://)?(?:www\.)?[a-zA-Z0-9][a-zA-Z0-9.-]*\.(?:com|es|org|net|eu|io|co|info|tech|dev|ai|app|biz|online|cloud)(?:/[^\s]*)?")
MAIL_RX = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
TEL_RX = re.compile(r"(?:\+34[\s.-]?)?(?:9\d{2}|8\d{2})[\s.-]?\d{2}[\s.-]?\d{2}[\s.-]?\d{2}")

# Una direccion del PTA: 'C/ X', 'Avda. X', 'Johannes Kepler', 'Severo Ochoa', 'Caleta de Velez'...
DIR_RX = re.compile(
    r"^(?:c/|calle|avda|avenida|av\.|plaza|pl\.|camino|ctra|carretera|paseo|urb|pol[íi]gono|"
    r"sever[oa]\s|johannes\s|rosalind\s|marie\s|louis\s|ivan\s|iv[áa]n\s|albert\s|thomas\s|"
    r"charles\s|isaac\s|galileo|newton|darwin|m[áa]laga|johhanes|nave\b)",
    re.I,
)
# Ruido §1.3: reventa, hosteleria, banca pura, inmobiliaria, no-software
RX_EXCL = re.compile(
    r"^(?:restaurant|hosteler|inmobiliar|gestor[íi]a|asesor[íi]a\s+(?:fiscal|laboral|jur)|"
    r"reparaci[óo]n|venta\s+de\s+(?:ordenador|equipo)|cl[íi]nic|dental|abogad|seguros\b|"
    r"servicios\s+bancarios|cooperativa\s+distribuidora|distribuci[óo]n\s+y\s+comercial|"
    r"comercializad|florister|supermercado|gimnasio|guarder[íi]a|colegio|"
    r"fabricaci[óo]n|fabricar|industrial\s+de|suministros\s+industrial|"
    r"taller|arquitectura|laboratorio\s+de\s+investigaci[óo]n|"
    r"conjunto\s+empresarial|edificio|centro\s+de\s+formaci|formaci[óo]n\s+y|"
    r"publicidad|editorial|agencia\s+de\s+viajes|alquiler|"
    r"consultor[íi]a\s+(?:de\s+)?(?:negocio|estr[ée]gic|marketing|comunicaci)|",
    re.I,
)
# Señales de desarrollo de software (§1 D1-D4)
RX_DEV = re.compile(
    r"desarrollo\s+de\s+software|desarrollo\s+de\s+aplicacion|desarrollo\s+web|"
    r"desarrollo\s+de\s+app|desarrollo\s+de\s+plataforma|aplicaciones?\s+(?:web|m[óo]vil|inform)|"
    r"software\s+(?:a\s+medida|de\s+gesti|de\s+gestion|de\s+crm|de\s+erp|como\s+servicio)|"
    r"f[áa]brica\s+de\s+software|ingenier[íi]a\s+de\s+software|"
    r"\bsaas\b|software\s+de\s+|plataforma\s+digital|startup\s+de\s+software|"
    r"data\s+science|big\s*data|inteligencia\s+artificial|machine\s+learning|"
    r"inteligencia\s+de\s+mercado|videojuegos|realidad\s+virtual|metaverso|"
    r"consultor[íi]a\s+(?:tecnol[óo]gica|inform[áa]tica|\bit\b)|neashore|nearshore|"
    r"outsourcing\s+it|desarrollo\s+de\s+proyectos\s+inform|soluciones?\s+inform[áa]tic|"
    r"digitalizaci[óo]n|transformaci[óo]n\s+digital|app\s+de|marketplace|"
    r"ciberseguridad|cloud|computaci[óo]n|blockchain|iot\b|"
    r"desarrollo\s+de|programaci[óo]n|web\s+y\s+m[óo]vil|"
    r"\berp\b|\bcrm\b|odoo|sap\b|business\s+intelligence|"
    r"gesti[óo]n\s+de\s+proyectos?\s+inform|automatizaci[óo]n",
    re.I,
)


def parse(path):
    lineas = open(path, encoding="utf-8", errors="ignore").read().split("\n")
    filas, edificio = [], None
    en_tabla = False

    def nueva():
        return {"nombre": None, "actividad": "", "direccion": "", "telefono": "",
                "email": "", "web": "", "edificio": edificio}

    for ln in lineas:
        limpio = ln.replace("\f", "").rstrip()
        if not limpio.strip():
            continue
        m = BLOQUE_RX.search(limpio)
        if m:
            edificio = m.group(1).strip()
            en_tabla = False
            continue
        if HEADER_RX.match(limpio.strip()):
            en_tabla = True
            continue
        if not en_tabla:
            continue

        partes = re.split(r"\s{2,}", limpio.strip())
        if limpio[0] != " ":                      # fila nueva: empieza en columna 0
            f = nueva()
            f["nombre"] = partes[0].strip()
            resto = partes[1:]
            filas.append(f)
            celdas = resto
        else:                                      # continuacion de la fila anterior
            if not filas:
                continue
            f = filas[-1]
            celdas = partes

        # asignar celdas: la primera que parezca direccion tel/email/web va a su campo,
        # el resto acumula en 'actividad' (respetando el orden textual).
        for c in celdas:
            c = c.strip()
            if not c or c == "---":
                continue
            if MAIL_RX.search(c):
                m2 = MAIL_RX.search(c)
                f["email"] = (f["email"] + " " + m2.group(0)).strip()
            elif TEL_RX.search(c) and not re.search(r"[A-Za-z]{4}", c):
                m2 = TEL_RX.search(c)
                f["telefono"] = (f["telefono"] + " " + m2.group(0)).strip()
            elif WEB_RX.search(c):
                m2 = WEB_RX.search(c)
                f["web"] = (f["web"] + " " + m2.group(0)).strip()
            elif DIR_RX.match(c):
                f["direccion"] = (f["direccion"] + " " + c).strip()
            else:
                f["actividad"] = (f["actividad"] + " " + c).strip()

    out = []
    for f in filas:
        if not f["nombre"] or not re.search(r"[A-Za-z]{3}", f["nombre"]):
            continue
        for k in ("actividad", "direccion", "telefono", "email", "web"):
            f[k] = re.sub(r"\s+", " ", f[k]).strip() or None
        if f["web"] and not f["web"].startswith("http"):
            f["web"] = "http://" + f["web"]
        out.append(f)
    return out


def es_software(f):
    txt = f"{f['nombre']} {f['actividad'] or ''}"
    if RX_EXCL.search(txt):
        return False
    return bool(RX_DEV.search(txt))


if __name__ == "__main__":
    r = parse(sys.argv[1] if len(sys.argv) > 1 else "pta.txt")
    dev = [x for x in r if es_software(x)]
    print(f"filas: {len(r)}", file=sys.stderr)
    print(f"con actividad: {sum(1 for x in r if x['actividad'])}", file=sys.stderr)
    print(f"con web: {sum(1 for x in r if x['web'])}", file=sys.stderr)
    print(f"software: {len(dev)}", file=sys.stderr)
    for x in r[:15]:
        print(x)
    print("--- SOFTWARE ---")
    for x in dev[:40]:
        print(x["nombre"], "|", (x["actividad"] or "")[:70], "|", x["web"])
