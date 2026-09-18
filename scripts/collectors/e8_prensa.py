"""E8 — Licitaciones publicas (PLACSP) + prensa local (Google News RSS).

Uso:  python3 scripts/collectors/e8_prensa.py [sevilla|malaga|all] [n_snapshots]

Escribe raw/e8_licitaciones_prensa_<provincia>_<fecha>.jsonl

Contrato: AGENTE_TEMPLATE.md. Sin URL de evidencia no hay ficha.

HALLAZGO (18/09/2026): la sindicacion de PLACSP es una VENTANA MOVIL (~280
entradas por defecto, 500 por snapshot). Los contratos de desarrollo adjudicados
con ejecucion en Sevilla/Malaga son RAROS: recorriendo 8 snapshots (~4.000
entradas) solo aparecen ~2 adjudicatarios privados con CPV 72. La mayoria de
CPV 72 del feed son de Madrid/nacionales o licitaciones aun sin adjudicar
(Estado PUB, sin cac:WinningParty). Por eso se recorre hacia atras via rel="next".
"""
import os, re, sys, html, datetime, urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import get, fichas, escribe  # noqa: E402

FUENTE = "E8_LICITACIONES_PRENSA"
HOY = datetime.date.today().isoformat()

PLACSP = ("https://contrataciondelestado.es/sindicacion/sindicacion_643/"
          "licitacionesPerfilesContratanteCompleto3.atom")
N_SNAPSHOTS = 8                     # ~500 entradas c/u; ver HALLAZGO arriba

PROV = {
    "SEVILLA": ("Sevilla", re.compile(r"^Sevilla$", re.I)),
    "MALAGA": ("Málaga", re.compile(r"^M[aá]laga$", re.I)),
}

NEWS_QS = {
    "SEVILLA": ["empresa software Sevilla", "startup Sevilla ronda financiacion",
                "tecnologica Sevilla nueva sede", "Sevilla empresa inteligencia artificial",
                "Sevilla software facturacion"],
    "MALAGA": ["empresa software Malaga", "startup Malaga ronda financiacion",
               "tecnologica Malaga nueva sede", "Malaga empresa inteligencia artificial",
               "Malaga TechPark empresa"],
}

# NIF de persona juridica privada: letra inicial A-H, J, N, U, V, W + 7 digitos + control.
# Excluye organismos publicos (P/S/Q/L) y personas fisicas (numeros/letraKLM).
NIF = re.compile(r"^[ABCDEFGHJNUVW]\d{7}[0-9A-J]$")

# Descriptores, recintos, organismos y publicaciones que NO son empresas censables.
NOT_A_COMPANY = re.compile(
    r"tech park|techpark|pol[oó] digital|agencia digital|polo tecnol|"
    r"^des$|digital enterprise|el digital|base tecnol|^m[aá]laga tech|"
    r"corporaci[oó]n tecnol[oó]gica|"
    r"^tech\b|^startup$|^empresa$|^compa[ñn][ií]a$|^firma$|^consultora$|"
    r"^el\b|^la\b|^los\b|^las\b|^un[a]?\b|^del\b|^qué\b|^cómo\b", re.I)

# El titular debe situar la empresa en la provincia; si no, es ruido nacional
# que Google News cuela al buscar "startup ... ronda". ponytail: filtro textual.
PROV_IN_TITLE = {"SEVILLA": re.compile(r"sevilla|andalu", re.I),
                 "MALAGA": re.compile(r"m[aá]laga|andalu|axarqu|costa del sol", re.I)}


def _txt(e, tag):
    m = re.search(rf"<[a-zA-Z0-9:._-]*{tag}[^>]*>(.*?)</[a-zA-Z0-9:._-]*{tag}>", e, re.S)
    return html.unescape(re.sub(r"\s+", " ", m.group(1)).strip()) if m else None


def _lic_snapshot(body, provincia):
    """Del feed ATOM -> adjudicatarios CPV 72 con ejecucion en la provincia."""
    _, prov_re = PROV[provincia]
    out = []
    for e in re.findall(r"<entry>.*?</entry>", body, re.S):
        cpvs = re.findall(r"ItemClassificationCode[^>]*>(\d+)", e)
        if not any(c.startswith("72") for c in cpvs):
            continue
        rl = re.search(r"<cac:RealizedLocation>.*?</cac:RealizedLocation>", e, re.S)
        if not rl:
            continue
        loc = _txt(rl.group(0), "CountrySubentity") or ""
        if not prov_re.match(loc):
            continue                  # provincia = UBICACION DE EJECUCION, no el comprador
        wp = re.search(r"<cac:WinningParty>(.*?)</cac:WinningParty>", e, re.S)
        if not wp:
            continue                  # licitacion sin adjudicar (Estado PUB)
        pn = re.search(r"<cac:PartyName>(.*?)</cac:PartyName>", wp.group(1), re.S)
        nombre = _txt(pn.group(1), "Name") if pn else None
        cif = _txt(wp.group(1), "ID")
        if not nombre or not cif or not NIF.match(cif):
            continue
        link = re.search(r'<link href="([^"]+)"', e)
        if not link:
            continue                  # sin URL de evidencia no hay ficha
        out.append({
            "nombre": nombre.strip(), "municipio": None, "cif": cif,
            "tipologias": ["FACTORIA"],   # dato bruto; clasificar.py decide
            "evidencia_url": html.unescape(link.group(1)),
            "notas": (f"LICITACION PLACSP CPV {','.join(cpvs[:3])} | "
                      f"adjudicacion: {_txt(e, 'AwardDate')} | "
                      f"importe: {_txt(e, 'TaxExclusiveAmount')} EUR | "
                      f"ejecucion: {loc} | titulo: {(_txt(e, 'title') or '')[:120]}"),
        })
    return out


def _placsp(provincia):
    """Recorre el feed y sus snapshots hacia atras. Devuelve (fichas, bloqueos)."""
    url, out, bloqueos = PLACSP, [], []
    for i in range(N_SNAPSHOTS):
        st, body = get(url, timeout=120)
        if st != 200 or "<entry" not in body:
            bloqueos.append(f"PLACSP HTTP {st} en snapshot {i}")
            break
        out += _lic_snapshot(body, provincia)
        nxt = re.search(r'<link href="([^"]+)" rel="next"/>', body)
        if not nxt:
            break
        url = html.unescape(nxt.group(1))
    return out, bloqueos


def _empresa_de_titular(title):
    """Nombre de empresa desde el titular. None si no hay señal clara."""
    t = re.sub(r"\s*[-–|]\s*[^-–|]*$", "", title).strip()   # quita " - Medio"
    m = re.search(r"\b([A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ&.]*(?:\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ&.]*){0,3}"
                  r"\s+(?:Software|Tech|Technologies|Labs|Digital|Solutions|Studio|"
                  r"Systems|Consulting|Data|AI|Cloud|Dev|Games|Apps|Innovación|Tecnológica))\b", t)
    m2 = re.search(r"\b(?:empresa|startup|tecnol[oó]gica|compa[ñn][ií]a|firma|consultora)\s+"
                   r"([A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ&.]*(?:\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ&.]*){0,3})", t)
    name = (m.group(0) if m else None) or (m2.group(1) if m2 else None)
    if not name or len(name) < 3:
        return None
    return name.strip()


def _prensa(provincia):
    """Google News RSS -> nombre + fecha del titular. Devuelve (fichas, bloqueos)."""
    prov, _ = PROV[provincia]
    out, bloqueos, vistos = [], [], set()
    for q in NEWS_QS[provincia]:
        url = ("https://news.google.com/rss/search?q=" + urllib.parse.quote(q)
               + "&hl=es&gl=ES&ceid=ES:es")
        st, body = get(url, timeout=40)
        if st != 200 or "<item>" not in body:
            bloqueos.append(f"Google News HTTP {st} q={q}")
            continue
        for item in re.findall(r"<item>(.*?)</item>", body, re.S):
            title = _txt(item, "title") or ""
            link = _txt(item, "link") or ""
            if not PROV_IN_TITLE[provincia].search(title):
                continue              # titular sin la provincia = ruido nacional
            nombre = _empresa_de_titular(title)
            if (not nombre or not link or nombre.lower() in vistos
                    or NOT_A_COMPANY.search(nombre)):
                continue
            vistos.add(nombre.lower())
            fecha = None
            pub = _txt(item, "pubDate") or ""
            if pub:
                try:
                    fecha = datetime.datetime.strptime(pub[:16], "%a, %d %b %Y").date().isoformat()
                except ValueError:
                    pass
            out.append({
                "nombre": nombre, "municipio": prov, "tipologias": [],
                "evidencia_url": link,
                "notas": (f"PRENSA | titular: {title[:160]}"
                          + (f" | fecha_fuente: {fecha}" if fecha else "")),
            })
    return out, bloqueos


def main():
    args = sys.argv[1:]
    arg = (args[0] if args else "all").upper()
    global N_SNAPSHOTS
    if len(args) > 1:
        N_SNAPSHOTS = int(args[1])
    provincias = list(PROV) if arg == "ALL" else [arg]
    if any(p not in PROV for p in provincias):
        raise SystemExit(f"provincia invalida: {arg} (usa sevilla|malaga|all)")

    for prov in provincias:
        lic, bl1 = _placsp(prov)
        pr, bl2 = _prensa(prov)
        escribe(fichas(lic + pr, FUENTE, prov, HOY), FUENTE, prov, HOY)
        bloqueos = bl1 + bl2
        if bloqueos:
            print("bloqueos:", "; ".join(bloqueos))


def demo():
    """Self-check: parser PLACSP, filtro de provincia y filtro de ruido de prensa."""
    entry = (
        '<cac:RealizedLocation><cbc:CountrySubentity>Málaga</cbc:CountrySubentity>'
        '</cac:RealizedLocation>'
        '<cbc:ItemClassificationCode>72310000</cbc:ItemClassificationCode>'
        '<cac:WinningParty><cac:PartyName><cbc:Name>ACME SOFTWARE SL</cbc:Name>'
        '</cac:PartyName><cbc:ID>B90116062</cbc:ID></cac:WinningParty>'
        '<cbc:AwardDate>2026-09-14</cbc:AwardDate>'
        '<link href="https://contrataciondelestado.es/x"/>'
    )
    hit = _lic_snapshot("<entry>" + entry + "</entry>", "MALAGA")
    assert len(hit) == 1 and hit[0]["nombre"] == "ACME SOFTWARE SL", hit
    assert hit[0]["cif"] == "B90116062" and hit[0]["evidencia_url"].endswith("/x")
    # provincia equivocada -> nada
    assert _lic_snapshot("<entry>" + entry.replace("Málaga", "Madrid") + "</entry>",
                         "MALAGA") == []
    # sin adjudicatario (licitacion abierta) -> nada
    assert _lic_snapshot("<entry>" + entry.replace("<cac:WinningParty><cac:PartyName>"
                         "<cbc:Name>ACME SOFTWARE SL</cbc:Name></cac:PartyName>"
                         "<cbc:ID>B90116062</cbc:ID></cac:WinningParty>", "") + "</entry>",
                         "MALAGA") == []
    # NIF publico (P...) -> nada
    assert _lic_snapshot("<entry>" + entry.replace("B90116062", "P2900000A") + "</entry>",
                         "MALAGA") == []
    # titular de prensa: extrae nombre y descarta descriptores
    assert _empresa_de_titular("La empresa Metadev capta un congreso - ABC") == "Metadev"
    assert NOT_A_COMPANY.search("Polo Digital")
    assert NOT_A_COMPANY.search("Corporación Tecnológica de Andalucía")
    print("demo OK")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        demo()
    else:
        main()
