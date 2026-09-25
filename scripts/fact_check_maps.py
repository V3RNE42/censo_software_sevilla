#!/usr/bin/env python3
"""Fact-checking de empresas del censo contra Google Maps via playwright-cli. SIN API key.

Sustituye la parte de `verificar_places.py` que llamaba a maps.googleapis.com.
NO toca data/empresas.json: escribe un overlay en data/actividad_maps.json que
un merge aparte aplica (mismo patrón que centros_compatibles/fact_check_maps.py).

Lo que SÍ puede dar sin key, y lo que NO:
  SÍ  -> business_status (cerrada permanentemente: única exclusión dura),
         rating, nº de reseñas, teléfono, web, categoría, 5 reseñas con fecha.
  NO  -> `reviews_sort=newest`: Google solo ordena reseñas por recientes con
         sesión iniciada. Sin login solo hay 5 "más relevantes", que en negocios
         con historial son de hace años. Por eso NO se emite
         `resenas_ultimos_12m` ni se declara inactividad: sería un falso negativo.

Uso:
    python3 scripts/fact_check_maps.py --limit 5 --verbose
    python3 scripts/fact_check_maps.py --only sev-0001
    python3 scripts/fact_check_maps.py --workers 8          # 8 subagentes en paralelo
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import unicodedata

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EMPRESAS = os.path.join(RAIZ, "data", "empresas.json")
CONSULTADAS = os.path.join(RAIZ, "data", "_consultadas.txt")
SALIDA = os.path.join(RAIZ, "data", "actividad_maps.json")
SCRIPTS_SKILL = os.path.expanduser(
    "~/.hermes/skills/research/google-maps-scraper/scripts/maps-extract.mjs"
)

# --- parseo de fechas relativas de Google Maps ---------------------------------

_UNIDAD_DIAS = [          # (raíz de 3 letras, días) — ES + EN
    (("dia", "day"), 1),
    (("sem", "wee"), 7),
    (("mes", "mon"), 30),
    (("ano", "yea"), 365),
    (("hor", "hou"), 1 / 24),   # Google usa 'hours ago' en reseñas del mismo día
]
_NUMERO = {
    # ES
    "un": 1, "una": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
    "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10, "once": 11, "doce": 12,
    # EN — 'a year ago' es 1; 'an hour ago' también.
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
}


def dias_desde(when):
    """'Hace 6 años' / 'hace 2 semanas' -> días aproximados. None si no parsea."""
    if not when:
        return None
    s = unicodedata.normalize("NFKD", when.lower())
    s = "".join(c for c in s if not unicodedata.combining(c)).replace("ñ", "n")
    # Google sirve las reseñas en el idioma del navegador: 'hace 2 años' (es)
    # o '2 years ago' (en-US, locale por defecto de Playwright). Sin el 'ago'
    # opcional, el parser devolvía None en TODAS las fichas y el veredicto
    # caía siempre en REVISAR (verificado 2026-09-25: 69/69).
    m = re.search(r"(?:hace\s+)?(\d+|[a-zñ]+)\s+([a-zñ]+)(?:\s+ago)?", s) or \
        re.search(r"hace\s+(\d+|[a-zñ]+)\s+([a-zñ]+)", s)
    if not m:
        return None
    n_txt, unidad = m.group(1), m.group(2)
    n = int(n_txt) if n_txt.isdigit() else _NUMERO.get(n_txt)
    if not n:
        return None
    for variantes, dias in _UNIDAD_DIAS:
        # 'meses' y 'mes' comparten raíz 'mes'; 'semanas'/'semana' la suya.
        # No vale rstrip('s'): de 'meses' quita una sola 's' -> 'mese' != 'mes'.
        # Se corta a 3 letras, que es la raíz real de las unidades (ES y EN).
        if unidad[:3] in variantes:
            return n * dias
    return None


def normaliza(s):
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _tel_num(s):
    """Solo dígitos, sin prefijo de país. '+34 902 25 94 54' == '902259454'.

    Sin esto, el dataset (que guarda '+34 ...') nunca coincide con Maps (que
    da el número pelado) y `telefono_coincide` sale False en todas las fichas
    con prefijo — que son la mayoría. Un False sistemático no es un dato.
    """
    d = re.sub(r"\D", "", s or "")
    return d[2:] if d.startswith("34") and len(d) > 9 else d


def _web_dom(s):
    """Dominio sin esquema, sin www y sin barra final: 'https://www.x.es/' -> 'x.es'."""
    d = re.sub(r"^https?://", "", (s or "").strip().lower())
    d = re.sub(r"^www\.", "", d)
    return d.split("/")[0]


def nombre_coincide(nombre, extraido):
    """Comparación por tokens: 'Academia Afoban' ⊂ 'Academia Afoban Sevilla'."""
    a, b = normaliza(nombre), normaliza(extraido)
    if not a or not b:
        return False
    if a == b or a in b or b in a:
        return True
    ta, tb = set(a.split()), set(b.split())
    return len(ta & tb) / max(len(ta), 1) >= 0.75


def nombre_consulta(f):
    """Nombre LIMPIO para Maps.

    El municipio va SIEMPRE: hay 23 nombres repetidos entre provincias
    (medido: 'Accenture' Sevilla + Málaga, 'Symonline' en dos fuentes de
    Huelva). Sin municipio, la segunda ficha recibe la dirección de la primera.

    Se quita el sufijo societario ('SL', 'SLU', 'SA') porque el h1 de Maps
    nunca lo lleva y rompe `nombre_coincide`.
    """
    n = (f.get("nombre") or "").strip()
    n = re.sub(r"[,.]?\s+(S\.?L\.?U?\.?|S\.?A\.?U?\.?|S\.?C\.?|C\.?B\.?)$", "", n, flags=re.I)
    mun = (f.get("municipio") or "").strip()
    return f"{n} {mun}".strip() if mun else n


# --- playwright ----------------------------------------------------------------

def cli(*args, timeout=90, session=None):
    """playwright-cli. Con `--workers>1` cada worker usa SU sesión nombrada, o
    los navegadores se pisan y todos devuelven 'browser is not open'."""
    cmd = ["playwright-cli", *(["-s", session] if session else []), *args]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return r.stdout


def cli_raw(expr, timeout=60, session=None):
    """--raw eval devuelve JSON serializado; a veces con comillas envolventes."""
    out = cli("--raw", "eval", expr, timeout=timeout, session=session).strip()
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return out


def acepta_consentimiento(session=None):
    """Rechaza el muro de cookies. Un click basta; reintentar no ayuda porque el
    navegador se relanza en cada intento y vuelve al mismo muro.

    El botón llega en el idioma del navegador, y playwright-cli NO permite fijar
    el locale (verificado 2026-09-25: no hay flag --locale ni clave en
    cli.config.json; el paquete no contiene la cadena 'locale'). Por eso el
    patrón es bilingüe y por submatch, no por nombre exacto.
    """
    for _ in range(3):
        if "consent.google.com" not in str(cli_raw("document.location.href",
                                                   session=session) or ""):
            return True
        snap = cli("--raw", "snapshot", session=session)
        # 'Rechazar todo' (es) | 'Reject all' (en) | variantes de Aceptar.
        m = re.search(r'button "(?:Rechazar todo|Reject all|Aceptar todo|'
                      r'Accept all)"[^\n]*?\[ref=(\w+)\]', snap)
        if not m:
            m = re.search(r'button "([^"]*(?:Rechazar|Reject|Aceptar|Accept)[^"]*)"'
                          r'[^\n]*?\[ref=(\w+)\]', snap)
            if m:
                cli("click", m.group(2), session=session)
            else:
                time.sleep(3)      # el muro tarda en renderizar el botón
                continue
        else:
            cli("click", m.group(1), session=session)
        time.sleep(4)              # el redirect a Maps no es instantáneo
    return "consent.google.com" not in str(cli_raw("document.location.href",
                                                   session=session) or "")


def _abre(consulta, timeout=90, session=None):
    """(Re)abre el navegador en la búsqueda. El proceso muere entre fichas:
    sin esto la siguiente devuelve 'browser is not open'."""
    cli("kill-all", timeout=30, session=session)
    time.sleep(0.5)
    cli("open", "--browser=chromium",
        "https://www.google.com/maps/search/" + consulta.replace(" ", "+"),
        timeout=timeout, session=session)
    time.sleep(2)


def extrae(consulta, timeout=90, reintentos=2, session=None):
    """Campos del negocio, o {'error': ...}."""
    datos = {"error": "sin intentos"}
    for intento in range(reintentos + 1):
        datos = _extrae_una_vez(consulta, timeout, session)
        if not datos.get("error"):
            return datos
        if intento < reintentos:
            time.sleep(2)
    return datos


def _extrae_una_vez(consulta, timeout=90, session=None):
    _abre(consulta, timeout, session)

    snap = cli("--raw", "snapshot", session=session)
    if not snap:
        return {"error": "sin respuesta del navegador"}
    if "is not open" in snap or "please run open first" in snap:
        return {"error": "navegador no abierto"}

    if "consent.google.com" in str(cli_raw("document.location.href", session=session) or ""):
        if not acepta_consentimiento(session):
            return {"error": "muro de consentimiento no superado"}

    url = str(cli_raw("document.location.href", session=session) or "")
    if "/maps/place/" in url:
        # recargar con la URL completa (feature id) hace renderizar el panel
        # de reseñas, rating y categoría; sin él solo sale el raíl izquierdo
        cli("goto", url, timeout=timeout, session=session)
        time.sleep(3)

    texto_pagina = str(cli_raw("document.body.innerText || ''", session=session) or "")

    # "Google Maps no encuentra X" — negocio ausente de Maps. La vista de búsqueda
    # sin resultado único NO tiene h1, así que hay que comprobar esto ANTES.
    if "no encuentra" in texto_pagina:
        return {"error": None, "no_encontrado": True, "nombre_en_maps": None,
                "reviews": [], "pid": None,
                "mensaje_maps": texto_pagina.split("|")[0][:120]}

    nombre_maps = str(cli_raw("document.querySelector('h1')?.textContent || ''",
                              session=session) or "")
    # el muro de cookies también renderiza un h1; no es un negocio
    if not nombre_maps or "Antes de ir a Google" in nombre_maps:
        return {"error": "consentimiento no resuelto", "nombre_en_maps": nombre_maps}

    raw = cli("--raw", "run-code", f"--filename={SCRIPTS_SKILL}", session=session)
    try:
        datos = json.loads(json.loads(raw.strip()))
    except (json.JSONDecodeError, TypeError):
        return {"error": "extracción ilegible", "nombre_en_maps": nombre_maps}

    datos["nombre_en_maps"] = nombre_maps
    texto = str(cli_raw("document.body.innerText || ''", session=session) or "")
    datos["cerrado_permanente"] = bool(
        re.search(r"cerrado permanentemente|permanentemente cerrado", texto, re.I)
    )
    datos["cerrado_temporalmente"] = bool(
        re.search(r"cerrado temporalmente|temporalmente cerrado", texto, re.I)
    )
    return datos


# --- veredicto ------------------------------------------------------------------

MESES_RECIENTE = 18      # reseña <= 18 meses = señal fuerte de vida
MESES_INTERMEDIO = 48    # 18-48 meses = señal débil; > 48 = inconcluso


def veredicto(ficha, datos, umbral_meses=MESES_RECIENTE):
    """OK | CERRADO | NO_ENCONTRADO | REVISAR | SIN_DATOS, con lista de razones."""
    if datos.get("error"):
        return "SIN_DATOS", [datos["error"], "no equivale a cerrado: reintentar"]

    if datos.get("no_encontrado"):
        return "NO_ENCONTRADO", [
            f"Google Maps no devuelve ficha para '{nombre_consulta(ficha)}'",
            "revisar nombre en el dataset o dar de baja: NO es prueba de cierre",
        ]

    if datos.get("cerrado_permanente"):
        return "CERRADO", ["Google Maps marca cerrado permanentemente"]

    señales = []
    if datos.get("tel"):
        señales.append("telefono")
    if datos.get("web"):
        señales.append("web")
    if datos.get("hist") or datos.get("total"):
        señales.append("resenas")
    if datos.get("cat"):
        señales.append("categoria")

    dias_nuevos = [d for d in (dias_desde(r.get("when")) for r in datos.get("reviews", []))
                   if d is not None]
    dias = min(dias_nuevos) if dias_nuevos else None

    razones = []
    if datos.get("cerrado_temporalmente"):
        razones.append("cerrado temporalmente")

    if not datos.get("nombre_en_maps"):
        return "SIN_DATOS", ["ficha vacía en Maps", "el negocio puede no existir o estar sin listar"]

    if not nombre_coincide(ficha.get("nombre", ""), datos["nombre_en_maps"]):
        razones.append(
            f"nombre en Maps '{datos['nombre_en_maps']}' != dataset '{ficha.get('nombre')}'"
        )
        return "REVISAR", razones

    if dias is None:
        if not señales:
            return "SIN_DATOS", ["sin teléfono, web, categoría ni reseñas"]
        razones.append("sin reseñas con fecha (¿negocio sin volumen de reseñas?)")
        return "REVISAR", razones + [f"señales: {', '.join(señales)}"]

    meses = dias / 30.0
    if meses <= umbral_meses:
        return "OK", [f"reseña hace ~{meses:.0f} meses"] + [f"señales: {', '.join(señales)}"]
    if meses <= MESES_INTERMEDIO:
        razones.append(f"reseña más reciente hace ~{meses:.0f} meses (débil)")
        return "REVISAR", razones + [f"señales: {', '.join(señales)}"]
    razones.append(f"reseña más reciente hace ~{meses:.0f} meses (> {MESES_INTERMEDIO//12} años)")
    return "REVISAR", razones + ["antigüedad de reseñas NO prueba cierre: falso negativo probable"]


# --- reparto de trabajo (subagentes paralelos) ---------------------------------

def reparte(n_total, workers, solo_worker=None):
    """Asigna fichas por índice módulo. Con 8 workers y 445 fichas, cada uno
    coge ~56. El filtro por `_consultadas.txt` hace el reparto reanudable."""
    rango = range(n_total)
    if solo_worker is not None:
        rango = [i for i in rango if i % workers == solo_worker - 1]
    return list(rango)


# --- main -----------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--only", help="id de una ficha concreta")
    ap.add_argument("--umbral-meses", type=int, default=MESES_RECIENTE)
    ap.add_argument("--workers", type=int, default=1,
                    help="nº total de workers; particiona por índice")
    ap.add_argument("--worker", type=int, default=None,
                    help="este worker (1..workers), para subagentes en paralelo")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    fichas = json.load(open(EMPRESAS, encoding="utf-8"))
    if args.only:
        fichas = [f for f in fichas if f.get("id") == args.only]
        if not fichas:
            sys.exit(f"id no encontrado: {args.only}")

    # el reparto por índice se hace sobre el fichero COMPLETO, no sobre --limit,
    # para que 8 subagentes cada uno con --limit 56 no cojan los mismos 56.
    if args.limit:
        fichas = fichas[:args.limit] if args.workers == 1 else fichas

    session = f"fc{w}" if (w := args.worker) else None
    if args.workers > 1:
        quedan = [f for i, f in enumerate(fichas)
                  if i % args.workers == (args.worker or 1) - 1
                  and f.get("id") not in _ya_consultadas()]
    else:
        quedan = [f for f in fichas if f.get("id") not in _ya_consultadas()]
    if args.limit and args.workers == 1:
        quedan = quedan[:args.limit]

    previo = {}
    if os.path.exists(SALIDA):
        previo = {v["id"]: v for v in json.load(open(SALIDA, encoding="utf-8"))}

    print(f"worker {args.worker or 1}/{args.workers}: {len(quedan)} fichas")
    for i, f in enumerate(quedan, 1):
        if f["id"] in previo:
            continue
        consulta = nombre_consulta(f)
        t0 = time.time()
        try:
            datos = extrae(consulta, session=session)
        except subprocess.TimeoutExpired:
            datos = {"error": "timeout de playwright"}
        ver, razones = veredicto(f, datos, args.umbral_meses)
        previo[f["id"]] = _fila(f, consulta, ver, razones, datos, t0)
        v = previo[f["id"]]
        if args.verbose:
            print(json.dumps(v, ensure_ascii=False, indent=1))
        else:
            print(f"[{i}/{len(quedan)}] {f['id']:>10}  {ver:<13}  "
                  f"{(f.get('nombre') or '')[:34]:<34} "
                  f"{v['dias_ultima_resena'] if v['dias_ultima_resena'] is not None else '-':>6}d  "
                  f"{v['segundos']}s", flush=True)
        # persistencia incremental: un fallo no tira el trabajo pagado en tiempo.
        # Escritura atómica: 8 workers escribiendo el mismo fichero a la vez
        # dejarian JSON truncado y se perderia la corrida entera.
        _escribe_atomico(list(previo.values()))
        _marca_consultada(f["id"])
        time.sleep(1.5)

    cli("kill-all", session=session)

    conteo = {}
    for v in previo.values():
        conteo[v["veredicto"]] = conteo.get(v["veredicto"], 0) + 1
    print("\n" + json.dumps(conteo, indent=1, ensure_ascii=False))
    print(f"-> {os.path.relpath(SALIDA, RAIZ)}  ({len(previo)} fichas)")


def _fila(f, consulta, ver, razones, datos, t0):
    """Una fila del overlay. Incluye lo que la API daba y sí es obtenible."""
    return {
        "id": f["id"],
        "nombre": f.get("nombre"),
        "consulta_maps": consulta,
        "estado_dataset": f.get("estado"),
        "veredicto": ver,
        "razones": razones,
        "nombre_en_maps": datos.get("nombre_en_maps"),
        "place_id": datos.get("pid"),
        "maps_total": datos.get("total"),
        "rating": datos.get("rating"),
        "categoria_maps": datos.get("cat"),
        "telefono_maps": datos.get("tel"),
        "web_maps": datos.get("web"),
        "cerrado_permanente": datos.get("cerrado_permanente"),
        "mensaje_maps": datos.get("mensaje_maps"),
        "telefono_coincide": (_tel_num(datos["tel"]) == _tel_num(f.get("telefono"))
                              if datos.get("tel") and f.get("telefono") else None),
        "web_coincide": (_web_dom(datos["web"]) == _web_dom(f.get("web"))
                         if datos.get("web") and f.get("web") else None),
        "dias_ultima_resena": next(iter(sorted(
            d for d in (dias_desde(r.get("when")) for r in datos.get("reviews", []))
            if d is not None)), None),
        "reviews": datos.get("reviews", [])[:3],
        "error": datos.get("error"),
        "segundos": round(time.time() - t0, 1),
        "fecha_verificacion": time.strftime("%Y-%m-%d"),
    }


def _escribe_atomico(filas):
    """Escritura atómica: con --workers>1 varios procesos comparten SALIDA."""
    tmp = SALIDA + f".tmp{os.getpid()}"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(filas, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, SALIDA)


# --- consultadas (reparto reanudable) ------------------------------------------

def _ya_consultadas():
    if not os.path.exists(CONSULTADAS):
        return set()
    return {ln.strip() for ln in open(CONSULTADAS, encoding="utf-8") if ln.strip()}


def _marca_consultada(id_):
    """Fichero append-only de ids ya mirados: un worker caído se reanuda sin
    volver a pagar el tiempo de los que ya terminaron."""
    with open(CONSULTADAS, "a", encoding="utf-8") as fh:
        fh.write(id_ + "\n")


# --- demo -----------------------------------------------------------------------

def demo():
    """Autochequeo del parser de fechas, del matching y del veredicto."""
    assert dias_desde("Hace 6 años") == 6 * 365
    assert dias_desde("Hace 2 meses") == 60
    assert dias_desde("hace 3 semanas") == 21
    assert dias_desde("Hace un año") == 365
    assert dias_desde("Hace 12 años") == 4380
    assert dias_desde("Hace 1 mes") == 30          # regresión: plural/singular
    assert dias_desde("") is None and dias_desde("el mes pasado") is None

    assert nombre_coincide("Academia Afoban", "Academia Afoban")
    assert nombre_coincide("Symonline SL", "Symonline")
    assert not nombre_coincide("Kids&Us Sevilla", "Kids&Us Mairena")

    # regresión: el sufijo societario no debe ir a Maps (el h1 nunca lo lleva)
    assert nombre_consulta({"nombre": "Enrique Puentes, S.L.", "municipio": "Sevilla"}) \
        == "Enrique Puentes Sevilla"
    assert nombre_consulta({"nombre": "Abatic", "municipio": None}) == "Abatic"
    # el municipio separa homónimos: Accenture tiene ficha en 2 provincias
    assert nombre_consulta({"nombre": "Accenture", "municipio": "Málaga"}) != \
        nombre_consulta({"nombre": "Accenture", "municipio": "Sevilla"})

    # regresión: '+34' del dataset contra el número pelado de Maps
    assert _tel_num("+34 902 25 94 54") == _tel_num("902 25 94 54") == "902259454"
    assert _tel_num("954 123 456") == "954123456"
    assert _tel_num("") == "" and _tel_num(None) == ""
    # regresión: esquema, www y barra final no cambian el dominio
    assert _web_dom("https://www.actiobp.com/") == _web_dom("actiobp.com") == "actiobp.com"
    assert _web_dom("http://x.es/a/b") == "x.es"
    # regresión: 'meses'/'semanas' en plural (el bug de raíz/rstrip)
    assert dias_desde("Hace 2 meses") == 60
    assert dias_desde("hace 3 semanas") == 21

    # regresión 2026-09-25: Google sirve las reseñas en INGLÉS con el locale por
    # defecto de Playwright. El parser solo entendía 'hace N unidad' -> devolvía
    # None en todas las fichas -> veredicto REVISAR en el 100% (69/69). Estas
    # aserciones fallan si alguien vuelve a romper el soporte EN.
    assert dias_desde("2 years ago") == 730
    assert dias_desde("5 years ago") == 1825
    assert dias_desde("6 months ago") == 180
    assert dias_desde("3 weeks ago") == 21
    assert dias_desde("5 days ago") == 5
    assert dias_desde("a year ago") == 365
    assert dias_desde("2 years ago ") == 730        # espacio sobrante
    d_hora = dias_desde("an hour ago")
    assert d_hora is not None and d_hora < 1      # 'hours ago' = mismo día
    assert dias_desde("edited 3 months ago") == 90  # Google antepone 'edited'
    # el caso mixto debe seguir funcionando o la corrección EN rompió el ES
    assert dias_desde("hace 2 años") == 730
    assert dias_desde("just now") is None

    f = {"nombre": "Emergya"}
    d = {"nombre_en_maps": "Emergya", "pid": "ChIJ", "total": 63, "tel": "954",
         "web": "x.es", "cat": "Software", "reviews": [{"when": "Hace 19 meses"}]}
    assert veredicto(f, d)[0] == "REVISAR"          # 19 meses -> ni OK ni CERRADO
    d["reviews"] = [{"when": "Hace 6 meses"}]
    assert veredicto(f, d)[0] == "OK"
    d["cerrado_permanente"] = True
    assert veredicto(f, d)[0] == "CERRADO"
    assert veredicto(f, {"error": "timeout"})[0] == "SIN_DATOS"
    assert veredicto(f, {"nombre_en_maps": "Otro Negocio SL", "pid": "x"})[0] == "REVISAR"
    assert veredicto(f, {"nombre_en_maps": "Emergya"})[0] == "SIN_DATOS"  # sin señales
    # regresión: el muro de cookies renderiza un h1 y NO es un negocio
    assert veredicto(f, {"error": "consentimiento no resuelto",
                         "nombre_en_maps": "Antes de ir a Google"})[0] == "SIN_DATOS"
    # regresión 2026-09-25: el botón del muro se buscaba SOLO en español
    # ('Rechazar todo'). playwright-cli no permite fijar locale (no existe
    # --locale ni clave en cli.config.json), así que el navegador negocia el
    # idioma y el botón puede llegar como 'Reject all' -> nunca se encontraba
    # -> 2 sleeps de 3s y SIN_DATOS. El patrón debe aceptar ambas lenguas.
    for txt in ["Rechazar todo", "Reject all", "Aceptar todo", "Accept all"]:
        snap = f'- button "{txt}" [ref=abc123] [cursor=pointer]'
        mm = re.search(r'button "(?:Rechazar todo|Reject all|Aceptar todo|'
                       r'Accept all)"[^\n]*?\[ref=(\w+)\]', snap)
        assert mm and mm.group(1) == "abc123", f"no casa el boton {txt!r}"
    # la vista degradada de Maps no trae datos: nombre correcto pero cero
    # señales -> SIN_DATOS (no REVISAR, que es lo que da un nombre que no casa).
    assert veredicto({"nombre": "AFP Informáticos"},
                     {"nombre_en_maps": "AFP Informáticos"})[0] == "SIN_DATOS"
    # regresión: el navegador muerto no debe confundirse con un cierre
    assert veredicto(f, {"error": "navegador no abierto"})[0] == "SIN_DATOS"
    # regresión: 'no encuentra' es concluyente, no un fallo técnico
    assert veredicto(f, {"no_encontrado": True})[0] == "NO_ENCONTRADO"
    print("demo OK")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--demo":
        demo()
    else:
        main()
