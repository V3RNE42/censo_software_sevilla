"""E6 — Organizaciones de GitHub con ubicacion en las provincias de Sevilla o Malaga.

Uso:  python3 scripts/collectors/e6_github.py [sevilla|malaga|all]

Escribe raw/e6_github_<provincia>_<fecha>.jsonl

Contrato: AGENTE_TEMPLATE.md. Sin URL de evidencia no hay ficha.

RATE LIMIT (medido 18/09/2026, sin token):
  /search  -> 10 req/min        (busquedas: 12 por provincia, espaciadas 7 s)
  /users/* -> 60 req/h en core  (el detalle de org es el cuello de botella)

Estrategia: /search solo da login+id, asi que hay que pedir /users/<login>
para obtener blog (web), description (senal de empresa) y public_repos.
Se piden primero las orgs que GitHub cree mas grandes (sort=repositories):
esas son las que tienen pinta de empresa, no de colectivo personal.

FILTRO: sin web corporativa NI description de empresa -> fuera. Un README de
proyecto de universidad no es una empresa (ver PLAN §1.3 EXC_*).
"""
import os, sys, json, time, re, datetime, urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import get, fichas, escribe                    # noqa: E402

FUENTE = "E6_GITHUB"
HOY = datetime.date.today().isoformat()
GH = "https://api.github.com"
HDR = {"Accept": "application/vnd.github+json"}
PAUSA_SEARCH = 7          # 10 req/min con margen

# Ubicaciones por provincia. La API de GitHub hace match por substring,
# asi que "Sevilla" ya cubre "Sevilla, Spain" y "Dos Hermanas, Sevilla, Spain".
QUERIES = {
    "SEVILLA": ["Sevilla", "Andalucia", "Dos Hermanas", "Utrera"],
    "MALAGA": ["Malaga", "Málaga", "Andalucia", "Marbella", "Mijas",
               "Torremolinos", "Benalmadena", "Estepona", "Fuengirola",
               "Velez-Malaga", "Ronda", "Antequera"],
    "HUELVA": ["Huelva", "Andalucia", "Lepe", "Almonte", "Ayamonte",
               "Moguer", "Aljaraque", "Valverde del Camino", "Isla Cristina"],
}

# Ubicacion de la org -> provincia. GitHub no obliga a poner la provincia.
PROV_RE = {
    "SEVILLA": re.compile(r"sevilla|dos hermanas|utrera|alcal[aá] de guada[ií]ra|"
                          r"mairena|coria del r[ií]o|tomares|bormujos|[ée]cija|"
                          r"carmona|mor[oó]n de la frontera|lebrija|alandalus", re.I),
    "MALAGA": re.compile(r"m[aá]laga|marbella|mijas|torremolinos|benalm[aá]dena|"
                         r"fuengirola|estepona|v[eé]lez|rinc[oó]n de la victoria|"
                         r"antequera|ronda|co[ií]n\b|torrox|nerja|archidona", re.I),
    # Huelva: 'punta umbria' y 'rocio' son del litoral; 'minas de riotinto' no
    # aparece como 'riotinto' suelto para no cazar el municipio de Sevilla.
    "HUELVA": re.compile(r"huelva|lepe|almonte|ayamonte|moguer|aljaraque|"
                         r"valverde del camino|isla cristina|punta umbr[ií]a|"
                         r"cartaya|gibrale[oó]n|rociana|la palma del condado", re.I),
}
# "Andalucia" a secas no dice provincia -> se pide detalle y si no aclara, fuera.

# Colectivos, comunidades y proyectos que NO son empresas.
NO_EMPRESA = re.compile(
    r"comunidad|community|asociaci[oó]n|colectivo|meetup|grupo de usuarios|"
    r"university|universidad|facultad|departamento|research group|"
    r"open source community|hackerspace|makerspace|scouts|estudiantes", re.I)


SENAL_EMPRESA = (r"s\.l\.|\bsl\b|gmbh|\binc\b|labs|software|digital|solutions|"
                 r"technolog|consultor|studio|systems|develop|engineer|"
                 r"startup|empresa|company|saas|\bapps?\b|web|hosting|cloud")


def _search(q, filtro_desc=False, paginas=3):
    """GET /search/users. Devuelve (logins, bloqueos).

    filtro_desc: si el resultado trae `description`, exige que hable de empresa.
    GitHub no indexa el campo blog, asi que sin esto se gastan peticiones de
    core (60 req/h) en colectivos y proyectos de universidad.
    """
    logins, bloqueos = [], []
    for p in range(1, paginas + 1):
        url = (f"{GH}/search/users?q={urllib.parse.quote(q)}&type=org"
               f"&sort=repositories&order=desc&per_page=100&page={p}")
        st, body = get(url, headers=HDR, timeout=45)
        if st != 200:
            bloqueos.append(f"search HTTP {st} q={q} p={p}")
            break
        try:
            d = json.loads(body)
        except ValueError:
            bloqueos.append(f"search JSON invalido q={q}")
            break
        items = d.get("items") or []
        for i in items:
            desc = i.get("description")        # solo presente en /search/users
            if filtro_desc and desc is not None:
                if NO_EMPRESA.search(desc) or not re.search(SENAL_EMPRESA, desc, re.I):
                    continue
            logins.append(i["login"])
        if len(items) < 100:
            break
        time.sleep(PAUSA_SEARCH)
    return logins, bloqueos


def _org(login):
    """GET /users/<login> -> (ficha_base_o_None, bloqueo_o_None, status)."""
    st, body = get(f"{GH}/users/{login}", headers=HDR, timeout=45)
    if st != 200:
        return None, f"users/{login} HTTP {st}", st
    try:
        d = json.loads(body)
    except ValueError:
        return None, f"users/{login} JSON invalido", st
    return d, None, st


def _es_empresa(d):
    """Devuelve (ok, motivo, tipologia_señal). REGLA: web corporativa o
    description de empresa; si no, no entra."""
    desc = (d.get("description") or "").strip()
    nombre = (d.get("name") or "").strip()
    blog = (d.get("blog") or "").strip()
    if NO_EMPRESA.search(desc) or NO_EMPRESA.search(nombre):
        return False, "colectivo/no empresa", None
    if not blog and len(desc) < 15:
        return False, "sin web y sin descripcion de empresa", None
    if not blog and re.search(r"s\.l\.|sl\b|gmbh|inc\.|labs|software|digital|"
                              r"solutions|technolog|consultor|studio|systems",
                              desc, re.I):
        return True, None, "descripcion de empresa (sin web)"
    if blog:
        return True, None, None
    return False, "sin web y sin descripcion de empresa", None


def _norm_web(blog):
    if not blog:
        return None
    b = blog.strip()
    if not b.startswith(("http://", "https://")):
        b = "https://" + b.lstrip("/")
    return b


def main():
    args = sys.argv[1:]
    arg = (args[0] if args else "all").upper()
    provincias = list(QUERIES) if arg == "ALL" else [arg]
    if any(p not in QUERIES for p in provincias):
        raise SystemExit(f"provincia invalida: {arg} (usa sevilla|malaga|all)")

    cache_org, bloqueos = {}, []
    for prov in provincias:
        logins, bl = _search_all(prov, cache_org)
        bloqueos += bl
        rows = _fichas_de(logins, prov, cache_org, bloqueos)
        esc = fichas(rows, FUENTE, prov, HOY)
        escribe(esc, FUENTE, prov, HOY)
        print(f"con_web: {sum(1 for f in esc if f['web'])}")
        print(f"bloqueos: {'; '.join(bloqueos) if bloqueos else 'ninguno'}")


def _search_all(prov, cache_org):
    """Busca todas las queries de la provincia. Devuelve (logins_unicos, bloqueos).
    Pide el detalle de cada org segun se encuentra (core: 60/h)."""
    logins, bloqueos, vistos = [], [], set()
    for i, q in enumerate(QUERIES[prov]):
        if i:
            time.sleep(PAUSA_SEARCH)
        # GitHub no indexa el campo blog en el buscador, pero SI la descripcion:
        # filtrar aqui ahorra peticiones de core (60 req/h, el cuello de botella).
        ls, bl = _search(q, filtro_desc=True, paginas=3)
        bloqueos += bl
        if not logins and not ls and i == 0:
            # 0 resultados en la pagina 1 de la query principal = hay precedentes
            # (la busqueda de usuarios se cae por tramos). Corte honesto, no 566
            # peticiones que devuelven 4 fichas.
            bloqueos.append(f"busqueda GitHub degradada: '{q}' devuelve 0 orgs; corte")
            break
        for l in ls:
            if l not in vistos:
                vistos.add(l)
                logins.append(l)
        print(f"# search '{q}' -> {len(ls)} logins (acumulado {len(logins)})",
              file=sys.stderr)
    return logins, bloqueos


def _fichas_de(logins, prov, cache_org, bloqueos):
    """Pide /users/<login> de cada org y aplica el filtro de empresa."""
    rows = []
    for i, login in enumerate(logins):
        if login in cache_org:                 # cache: 60 req/h de core
            d = cache_org[login]
        else:
            d, bl, st = _org(login)
            if bl:
                bloqueos.append(bl)
                if st == 403:                  # rate limit core agotado
                    bloqueos.append("core rate limit agotado, corte")
                    break
                continue
            cache_org[login] = d
        loc = d.get("location") or ""
        if not PROV_RE[prov].search(loc):
            continue                           # ubica en otra provincia (o ninguna)
        ok, _motivo, _ = _es_empresa(d)
        if not ok:
            continue
        nb = d.get("name") or login
        rows.append({
            "nombre": nb.strip(),
            "municipio": _municipio(loc, prov),
            "web": _norm_web(d.get("blog")),
            "tipologias": [],
            "evidencia_url": d.get("html_url") or f"https://github.com/{login}",
            "notas": (f"GITHUB ORG @{login} | ubicacion declarada: {loc or 'n/d'} | "
                      f"repos publicos: {d.get('public_repos')} | "
                      f"descripcion: {(d.get('description') or '')[:120]}"),
        })
        if i and i % 10 == 0:
            print(f"# {i}/{len(logins)} orgs consultadas", file=sys.stderr)
    return rows


def _municipio(loc, prov):
    """Municipio = primer segmento de la ubicacion declarada."""
    if not loc:
        return None
    return loc.split(",")[0].strip() or None


def demo():
    """Self-check: filtro de empresa y de provincia."""
    assert _es_empresa({"blog": "https://acme.com", "description": "",
                        "name": "Acme"})[0]
    assert _es_empresa({"blog": "", "description":
                        "Consultora de software a medida", "name": "X"})[0]
    assert not _es_empresa({"blog": "", "description": "proyectos", "name": "X"})[0]
    assert not _es_empresa({"blog": "https://u.es", "name": "Universidad de X",
                            "description": "University department"})[0]
    assert not _es_empresa({"blog": "https://meetup.com/x", "name": "X",
                            "description": "Comunidad de usuarios de Python"})[0]
    assert _norm_web("acme.com") == "https://acme.com"
    assert PROV_RE["SEVILLA"].search("Sevilla, Spain")
    assert not PROV_RE["SEVILLA"].search("Marbella, Spain")
    assert PROV_RE["MALAGA"].search("Málaga, Spain")
    assert _municipio("Marbella, Spain", "MALAGA") == "Marbella"
    print("demo OK")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        demo()
    else:
        main()
