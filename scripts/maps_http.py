"""Extrae datos de ficha de Google Maps por HTTP, SIN navegador y SIN login.

Endpoint descubierto 2026-09-25: `google.com/search?...&tbm=map` devuelve un
payload JSON con los datos del negocio. ~0.5s por ficha frente a ~45s del
scraper con Chromium, y sin CAPTCHA ni muro de consentimiento.

Campos verificados contra Emergya (rating 4.6, 63 resenas, tel 954 51 75 77):
  d[0][1][0][14][11]        nombre
  d[0][1][0][14][4][7]      rating
  d[0][1][0][14][178][0][0] telefono
  d[0][1][0][14][7][0]      web
  d[0][1][0][14][78]        place_id
  d[0][1][0][14][13]        categorias
  d[0][1][0][14][10]        cid (0x...:0x...)
  d[0][1][0][14][9]         [_,_,lat,lng]

LIMITE CONOCIDO: la respuesta es NO determinista. Google devuelve una variante
corta (~14.4 KB, sin bloque de resenas) o larga (~16.6 KB, con el). No expone
fechas de resenas en ninguna de las dos sin sesion. Por eso se reintenta hasta
tener el bloque de resenas, que aporta el volumen (no la fecha).
"""
import json
import re
import time
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


def _fetch(consulta, hl="es", gl="es", timeout=25):
    url = "https://www.google.com/search?" + urllib.parse.urlencode(
        {"authuser": "0", "hl": hl, "gl": gl, "q": consulta, "tbm": "map"})
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept-Language": f"{hl};q=0.9",
    })
    return urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "replace")


def _json(raw):
    """El payload viene con el prefijo anti-XSSI `)]}'` + salto de linea."""
    if raw.lstrip().startswith(")]}'"):
        raw = raw.lstrip()[4:].lstrip()
    return json.loads(raw)


def _nodo(d):
    try:
        return d[0][1][0][14]
    except (IndexError, TypeError, KeyError):
        return None


def _telefono(nod):
    try:
        t = nod[178][0][0]
        return t if isinstance(t, str) else None
    except (IndexError, TypeError, KeyError):
        return None


def _categorias(nod):
    try:
        cats = nod[13]
        return [c for c in cats if isinstance(c, str)] if isinstance(cats, list) else []
    except (IndexError, TypeError):
        return []


def _rating(nod):
    try:
        r = nod[4][7]
        return float(r) if isinstance(r, (int, float)) else None
    except (IndexError, TypeError):
        return None


def _sin_ciudad(consulta):
    """'Aire Networks del Mediterráneo Málaga' -> 'Aire Networks del Mediterráneo'.

    Las consultas del censo llevan la provincia pegada al nombre y Google
    devuelve ficha vacia al no casar la cadena literal. Medido 2026-09-25:
    recupera ATLANTYQA, Onlinehuelva y Aire Networks.
    """
    if not consulta:
        return None
    p = consulta.split("|")[0]          # 'Onlinehuelva | Diseño Web ... Huelva'
    for ciudad in ("Huelva", "Sevilla", "Málaga", "Malaga", "Cádiz", "Cadiz",
                   "Córdoba", "Cordoba", "Granada", "Almería", "Almeria",
                   "Jaén", "Jaen", "Paterna del Campo", "Dos Hermanas"):
        if p.endswith(" " + ciudad):
            p = p[: -len(ciudad) - 1]
            break
    p = p.strip()
    return p if p and p != consulta else None


def _plausible(d, consulta):
    """Descarta fichas de OTRA empresa que Google devuelve al soltar la ciudad.

    Sin este filtro, 'ATLANTYQA SOVEREIGN SYSTEMS Huelva' sin ciudad devuelve
    Sovereign Systems de Indiana (+1 317-409-5064) -- medido 2026-09-25.
    Un dato de otra empresa es peor que ningun dato.

    Endurecido tras ver los resultados del primer pase: cuando Google devuelve
    el nodo sin `nombre_en_maps` solo trae ficha de homonimo ('Aiknow' ->
    Hotel Alfonso XIII de Marriott, 'RENTIKAR' -> alquiler de coches). Sin
    nombre que confirme la identidad, el fallback se RECHAZA: preferimos
    SIN_DATOS a una ficha de otra empresa.
    """
    tel = (d.get("telefono") or "").replace(" ", "")
    if tel.startswith("+") and not tel.startswith("+34"):
        return False
    nombre = (d.get("nombre_en_maps") or "").lower()
    if not nombre:
        return False                       # sin nombre no hay confirmacion
    palabras = [w for w in re.split(r"[^a-z0-9]+", consulta.lower())
                if len(w) > 3 and w not in
                ("huelva", "sevilla", "malaga", "málaga", "andalucia",
                 "andaluces", "software", "sociedad",
                 # genericas: 'RentalPlus' colaba por 'plus' -- medido 2026-09-25
                 "plus", "group", "grupo", "solutions", "soluciones",
                 "technology", "technologies", "tecnologia", "tecnologias",
                 "digital", "digitals", "systems", "sistemas", "global",
                 "consulting", "consultoria", "internet", "servicios",
                 "services", "informatica", "data", "tech", "labs", "net")]
    if not palabras:
        return False
    return any(w in nombre for w in palabras)


def extrae(consulta, intentos=2, pausa=0.4, con_volumen=False):
    """Datos de ficha por HTTP. ~0.5s por intento.

    `con_volumen=True` reintenta buscando la variante larga (trae '<N> reseñas').
    Medido 2026-09-25: sale ~1 de cada 6 peticiones (no 40%), asi que subir
    `intentos` encarece cada ficha sin garantia. Por defecto OFF: rating,
    telefono, web y place_id vienen en ambas variantes, y el volumen es un
    extra, no el dato que decide el veredicto.

    Si la consulta literal no trae ficha, reintenta una vez sin la ciudad
    (pitfall medido: 'Nombre Provincia' no casa con Google). Todo resultado
    pasa por `_plausible`, tambien el de la consulta literal: Google devuelve
    homonimos por busqueda difusa ('GOSISACA' -> goysa.com, 'BEINCERT' ->
    ecocert.com, 'RENTIKAR' -> rentalplus.es) -- medido 2026-09-25.
    """
    datos = _extrae_una(consulta, intentos, pausa, con_volumen)
    if not _vacio(datos) and not _plausible(datos, consulta):
        datos["descarte"] = "ficha de otra empresa (homonimo)"
        datos = {"consulta": consulta, "error": None}
    if _vacio(datos):
        alt = _sin_ciudad(consulta)
        if alt:
            d2 = _extrae_una(alt, 1, pausa, con_volumen)
            if not _vacio(d2) and _plausible(d2, consulta):
                d2["consulta"] = consulta
                d2["consulta_efectiva"] = alt
                return d2
    return datos


def _vacio(d):
    return not any(d.get(k) for k in
                   ("nombre_en_maps", "telefono", "web", "place_id", "rating"))


def _extrae_una(consulta, intentos=2, pausa=0.4, con_volumen=False):
    datos = {"consulta": consulta, "error": None}
    for i in range(max(1, intentos)):
        try:
            raw = _fetch(consulta)
        except Exception as e:                       # red, timeout, TLS
            datos["error"] = f"{type(e).__name__}: {e}"
            time.sleep(pausa * (i + 1))
            continue
        nod = None
        try:
            nod = _nodo(_json(raw))
        except (json.JSONDecodeError, ValueError):
            datos["error"] = "payload no parseable"
            time.sleep(pausa * (i + 1))
            continue
        if nod is None:
            datos["error"] = "estructura inesperada"
            time.sleep(pausa * (i + 1))
            continue

        datos["nombre_en_maps"] = nod[11] if len(nod) > 11 else None
        datos["rating"] = _rating(nod)
        datos["telefono"] = _telefono(nod)
        datos["categorias"] = _categorias(nod)
        datos["error"] = None
        try:
            datos["web"] = nod[7][0]
        except (IndexError, TypeError):
            datos["web"] = None
        try:
            datos["place_id"] = nod[78]
        except (IndexError, TypeError):
            datos["place_id"] = None
        try:
            datos["cid"] = nod[10]
        except (IndexError, TypeError):
            datos["cid"] = None
        try:
            datos["direccion"] = nod[39]
        except (IndexError, TypeError):
            datos["direccion"] = None
        try:
            datos["lat"], datos["lng"] = nod[9][2], nod[9][3]
        except (IndexError, TypeError):
            datos["lat"] = datos["lng"] = None

        # volumen: solo en la variante larga, y solo si se pide.
        m = re.search(r"(\d[\d.,]*)\s+(?:rese[ñn]as|reviews)", raw)
        datos["n_resenas"] = int(m.group(1).replace(".", "").replace(",", "")) if m else None
        datos["intentos_usados"] = i + 1
        if not con_volumen or datos["n_resenas"] is not None or i == intentos - 1:
            return datos
        time.sleep(pausa)
    return datos


def extrae_lote(consultas, pausa=0.8):
    for c in consultas:
        yield extrae(c)
        time.sleep(pausa)


# --- self-check ---------------------------------------------------------------
def demo():
    """Un solo assert runnable. Verifica el parser sin tocar la red: si alguien
    cambia los indices de la ruta d[0][1][0][14], esto falla."""
    nod = [None] * 180
    nod[11] = "Emergya"
    nod[4] = [None] * 7 + [4.6]
    nod[7] = ["https://www.emergya.com/", "emergya.com"]
    nod[13] = ["Empresa de software"]
    nod[10] = "0xd126ea2cf2d445d:0x7216b99a5d9f1aee"
    nod[78] = "ChIJXUQtz6JuEg0R7hqfXZq5FnI"
    nod[39] = "C. Luis de Morales, 32, Sevilla"
    nod[9] = [None, None, 37.383, -5.973]
    nod[178] = [["954 51 75 77"]]

    # la forma real: d[0][1][0][14] == nod
    d = [[None] * 15, None]
    d[0][1] = [None] * 15
    d[0][1][0] = [None] * 14 + [nod]

    assert _nodo(d) is nod, "la ruta d[0][1][0][14] ya no lleva al nodo"
    assert _rating(nod) == 4.6
    assert _telefono(nod) == "954 51 75 77"
    assert _categorias(nod) == ["Empresa de software"]

    # ausencias: None, nunca excepcion (Google omite campos a menudo)
    nod[178] = None
    assert _telefono(nod) is None
    nod[4] = [None] * 8
    assert _rating(nod) is None
    assert _nodo([None, None, None]) is None, "estructura corta debe dar None"
    assert _nodo({"a": 1}) is None

    # parser de volumen, las tres formas que sirve Google
    for txt, esp in [("63 reseñas", 63), ("1.234 reseñas", 1234), ("5 reviews", 5)]:
        m = re.search(r"(\d[\d.,]*)\s+(?:rese[ñn]as|reviews)", txt)
        assert m and int(m.group(1).replace(".", "").replace(",", "")) == esp, txt
    print("demo OK")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        demo()
    elif len(sys.argv) > 1:
        print(json.dumps(extrae(" ".join(sys.argv[1:])), ensure_ascii=False, indent=1))
    else:
        demo()
