#!/usr/bin/env python3
"""
Fase 3 — ámbito + verificación Places + filtro de actividad 12 meses.

Dos pasos:
  1. ambito(): marca cada ficha con su provincia real resolviendo el conflicto
     CP vs coordenada (homónimos de Places), y aparta lo que cae fuera del ámbito.
  2. actividad(): Places textsearch (nombre LIMPIO, sin municipio) + details con
     reviews_sort=newest. publishTime ISO → filtro de 12 meses.

La verdad de "¿de qué provincia es esto?" NO vive aquí: vive en
build_provincias.ambito_de(), que es también lo que valida el escritor del
dataset (_common._escribe_dataset) y lo que lee el generador de etiquetas.

La key se lee del entorno. NUNCA inline (ver Anexo A del plan).
"""
import json, os, re, sys, time, urllib.parse, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "collectors"))
from build_provincias import (ambito_de, provincia_de, _ambito_key,
                              _ambito_a_provincia, CP_PROV)
from _common import _escribe_dataset  # noqa: E402  (vive en collectors/)

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EMPRESAS = os.path.join(RAIZ, "data", "empresas.json")
EXCLUIDOS = os.path.join(RAIZ, "data", "excluidos.json")
CACHE_PLACES = os.path.join(RAIZ, "data", "places_cache.json")
HOY = "2026-09-18"
CORTE_12M = "2025-09-18"          # publishTime >= esto ⇒ actividad reciente
LATENCIA = 0.25                    # ~4 req/s, dentro de cuota


def _key():
    k = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not k:
        raise SystemExit("Falta GOOGLE_MAPS_API_KEY. set -a; . /root/.hermes/.env; set +a")
    return k


def _places(url, params):
    """GET a Places. OJO: Google devuelve HTTP 200 en errores → mirar el campo status."""
    params = dict(params, key=_key())
    req = urllib.request.Request(url + "?" + urllib.parse.urlencode(params),
                                 headers={"User-Agent": "censo-software-sevilla/1.0"})
    for intento in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                d = json.load(r)
        except Exception:
            time.sleep(2 ** intento)
            continue
        if d.get("status") in ("OK", "ZERO_RESULTS"):
            return d
        if d.get("status") == "OVER_QUERY_LIMIT":
            time.sleep(5 * (intento + 1))
            continue
        return d                      # REQUEST_DENIED u otros: no reintentar
    return {"status": "FAIL", "results": []}


def _cp_a_ambito(cp):
    """'21006' -> 'HUELVA' | '41092' -> 'SEVILLA' | None si no es del ámbito."""
    p = _ambito_a_provincia(cp)
    return _ambito_key(p) if p else None


def tiene_domicilio(f):
    """¿Hay domicilio?: CALLE, o MUNICIPIO. El CP no hace falta.

    Medido: 136 fichas SIN_MUNICIPIO + sin direccion + sin web. Vienen de BORME
    (nombre + constitucion + CNAE software, nada mas) y de ofertas E2 sin
    ubicacion. No hay evidencia de domicilio, asi que no hay censo que hacer: no
    se pueden geocodificar, no se pueden visitar y no se puede imprimir un sobre.

    OJO con exigir CP: 'Mettis AI' y 'Metadev' (E8, municipio=Sevilla) y 'Kronte'
    (E2, municipio=Málaga) tienen municipio REAL y ningun CP, y pedir el par
    municipio+CP las borraba del censo. Un municipio es un domicilio: lo que no
    vale es un CP suelto sin calle ni municipio.

    Un CP SUELTO tampoco basta: 'Si Claro' tiene direccion = '41007 Sevilla,
    España', que es lo que Places devuelve cuando no encuentra la calle.
    """
    dire = (f.get("direccion") or "").strip()
    if (f.get("municipio") or "").strip():
        return True
    # Sin municipio: solo una calle de verdad cuenta. '41007 Sevilla, España' se
    # queda en 0 letras tras quitar CP/provincia/España.
    calle = re.sub(r"\b\d{5}\b|\b(sevilla|málaga|malaga|huelva|españa|spain)\b|[,\s]",
                   "", dire, flags=re.I)
    return len(calle) >= 3


def ambito(fichas=None):
    """Marca provincia real, separa SIN_DOMICILIO y aparta lo que cae fuera.

    `ambito` va SIEMPRE en mayúsculas (SEVILLA/MALAGA/HUELVA): es la clave que
    consumen build_html.py, etiquetas.py y el filtro del index (`dataset.prov`).

    La decisión (CP vs coordenada, homónimos) NO se toma aquí: se delega en
    build_provincias.ambito_de(). Tenerla duplicada es lo que dejó el dataset en
    un estado a medias — `lat` con coord ajena + `flags: COORD_HOMONIMO` puesto +
    `direccion` con el CP bueno, tres campos contradiciéndose entre sí. Con una
    sola implementación, lo que escribe este script y lo que valida el escritor
    del dataset no pueden discrepar.

    Recibe la lista en MEMORIA cuando la llama main(): leer EMPRESAS del disco se
    saltaba las coords y el CP que main() acababa de rellenar desde la cache, y las
    438 fichas salían sin lat ni cp tras el re-merge.

    Devuelve (dentro, fuera, sin_domicilio): los tres destinos son excluyentes.
    """
    if fichas is None:
        fichas = json.load(open(EMPRESAS))
    dentro, fuera, sin_dom = [], [], []
    for f in fichas:
        if not tiene_domicilio(f) and not (f.get("lat") and f.get("lng")):
            _flag(f, "SIN_DOMICILIO")
            f["ambito"] = None
            sin_dom.append(f)
            continue
        prov, coord, conflicto = ambito_de(f.get("lat"), f.get("lng"),
                                          f.get("cp"), f.get("provincia"))
        if conflicto:
            # El CP manda y la coord era de un homónimo: la ficha se queda, sin
            # punto en el mapa (una coord de otra provincia no es su ubicación).
            _flag(f, "COORD_HOMONIMO")
            f["coords_sospechosas"] = {"coord_ambito": _ambito_key(provincia_de(f.get("lat"), f.get("lng"))) if f.get("lat") else None,
                                       "cp_ambito": cp_ambito_de(f)}
            f["lat"] = f["lng"] = None
        if coord:
            f["lat"], f["lng"] = coord
        if prov:
            f["ambito"] = _ambito_key(prov)
            f["provincia"] = prov
            # `municipio` con el nombre de OTRA provincia del ambito: es de la
            # oferta, no del domicilio. Se limpia aqui (no solo se valida) para
            # que el campo no se contradiga con su propia ficha.
            mun_key = _ambito_key(f.get("municipio"))
            if mun_key in CP_PROV and mun_key != f["ambito"]:
                f["municipio"] = None
                _flag(f, "MUNICIPIO_FUERA_PROVINCIA")
            if not coord and "COORD_HOMONIMO" not in f["flags"]:
                _flag(f, "SIN_COORDS")
            dentro.append(f)
        elif f.get("lat") and f.get("lng"):
            _flag(f, "FUERA_AMBITO")
            f["ambito"] = None
            fuera.append(f)
        else:
            f["ambito"] = None
            fuera.append(f)
    return dentro, fuera, sin_dom


def _flag(f, nombre):
    """Añade un flag sin apilar. `ambito()` se re-ejecuta y `SIN_COORDS` salía x2
    en 20 fichas: `flags + [x]` no comprueba si ya está."""
    fl = f.setdefault("flags", [])
    if nombre not in fl:
        fl.append(nombre)


def cp_ambito_de(f):
    """Solo para la traza de `coords_sospechosas`."""
    return _cp_a_ambito((f.get("cp") or "").strip())


def _clave_cache(nombre, municipio=None):
    """Clave de cache INSENSIBLE a mayúsculas/tildes/espacios, + municipio.

    Indexar por `f['nombre']` crudo pagaba dos veces la misma empresa cuando el
    mismo negocio aparece como 'SYMONLINE' en un raw y 'Symonline' en otro
    (medido: 8 solapes entre las dos fuentes de Huelva).

    Y con SOLO el nombre, dos fichas de provincias distintas se repartían la misma
    entrada: 'Accenture' tiene ficha en Sevilla y en Málaga, y la de Málaga
    recibía la dirección del PT Cartuja de Sevilla (medido: 9 nombres con 2+
    municipios, 5 multi-sede real). El municipio separa esas; las variantes del
    MISMO pueblo ('Lepe' vs 'Lepe Huelva') siguen compartiendo cache porque el
    nombre de la provincia no distingue.
    """
    import unicodedata
    s = unicodedata.normalize("NFD", str(nombre or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    base = re.sub(r"[^a-z0-9]+", " ", s).strip()
    if not municipio:
        return base
    m = unicodedata.normalize("NFD", str(municipio).lower())
    m = "".join(c for c in m if unicodedata.category(c) != "Mn")
    m = re.sub(r"[^a-z0-9]+", " ", m).strip()
    # sufijo de provincia redundante: 'lepe huelva' -> 'lepe'
    for p in ("huelva", "sevilla", "malaga"):
        m = re.sub(rf"\b{p}\b", " ", m).strip()
    return f"{base}|{re.sub(r'[^a-z0-9]+',' ',m).strip()}" if m else base


def resolver_coords(fichas):
    """Rellena lat/lng vía Places textsearch. Nombre LIMPIO: 'CARTO Sevilla' da ZERO_RESULTS."""
    cache = json.load(open(CACHE_PLACES)) if os.path.exists(CACHE_PLACES) else {}
    pendientes = {}
    for f in fichas:
        if f.get("lat"):
            continue
        k = _clave_cache(f["nombre"], f.get("municipio"))
        if k in cache or k in pendientes:
            continue                       # cacheado, o ya en cola en esta pasada
        pendientes[k] = f
    print(f"  geocodificando {len(pendientes)} fichas únicas vía Places "
          f"({len(fichas)} fichas, {len(fichas)-len(pendientes)} ya resueltas o repetidas)...")
    for i, (k, f) in enumerate(pendientes.items(), 1):
        d = _places("https://maps.googleapis.com/maps/api/place/textsearch/json",
                    {"query": f["nombre"], "language": "es",
                     "location": "37.3891,-5.9845", "radius": "200000"})
        res = d.get("results", [])
        top = res[0] if res else None
        cache[k] = {
            "place_id": top.get("place_id") if top else None,
            "lat": top["geometry"]["location"]["lat"] if top else None,
            "lng": top["geometry"]["location"]["lng"] if top else None,
            "direccion": top.get("formatted_address") if top else None,
            "rating": top.get("rating") if top else None,
            "n_resenas": top.get("user_ratings_total") if top else None,
            "n_resultados": len(res),
            "status": d.get("status"),
        }
        if i % 50 == 0:
            json.dump(cache, open(CACHE_PLACES, "w"), ensure_ascii=False)
            print(f"    {i}/{len(pendientes)}")
        time.sleep(LATENCIA)
    json.dump(cache, open(CACHE_PLACES, "w"), ensure_ascii=False)
    return cache


def actividad(cache):
    """details con reviews_sort=newest → publishTime → filtro de 12 meses."""
    det = {}
    con_pid = [f for f in json.load(open(EMPRESAS)) if cache.get(_clave_cache(f["nombre"], f.get("municipio")), {}).get("place_id")]
    print(f"  consultando reseñas de {len(con_pid)} fichas...")
    for i, f in enumerate(con_pid, 1):
        pid = cache[_clave_cache(f["nombre"], f.get("municipio"))]["place_id"]
        d = _places("https://maps.googleapis.com/maps/api/place/details/json",
                    {"place_id": pid, "language": "es", "reviews_sort": "newest",
                     "fields": "name,rating,user_ratings_total,reviews,business_status"})
        r = d.get("result", {})
        fechas = sorted((x["time"] for x in r.get("reviews", [])), reverse=True)
        nueva = (time.strftime("%Y-%m-%d", time.gmtime(fechas[0])) if fechas else None)
        det[_clave_cache(f["nombre"], f.get("municipio"))] = {
            "business_status": r.get("business_status"),
            "rating": r.get("rating"),
            "n_resenas": r.get("user_ratings_total"),
            "resena_mas_reciente": nueva,
            "resenas_ultimos_12m": sum(1 for t in fechas
                                       if time.strftime("%Y-%m-%d", time.gmtime(t)) >= CORTE_12M),
        }
        if i % 50 == 0:
            print(f"    {i}/{len(con_pid)}")
        time.sleep(LATENCIA)
    return det


def enriquecer_contacto():
    """Teléfono y web desde Places details, solo para fichas sin teléfono."""
    cache = json.load(open(CACHE_PLACES)) if os.path.exists(CACHE_PLACES) else {}
    fichas = json.load(open(EMPRESAS))
    pend = [f for f in fichas
            if not f.get("telefono") and cache.get(_clave_cache(f["nombre"], f.get("municipio")), {}).get("place_id")]
    print(f"  enriqueciendo contacto de {len(pend)} fichas...")
    for i, f in enumerate(pend, 1):
        pid = cache[_clave_cache(f["nombre"], f.get("municipio"))]["place_id"]
        d = _places("https://maps.googleapis.com/maps/api/place/details/json",
                    {"place_id": pid, "language": "es",
                     "fields": "formatted_phone_number,website,address_components"})
        r = d.get("result", {})
        f["telefono"] = f.get("telefono") or r.get("formatted_phone_number")
        f["web"] = f.get("web") or r.get("website")
        for comp in r.get("address_components", []):
            if "locality" in comp.get("types", []):
                f["municipio"] = f.get("municipio") or comp["long_name"]
            if "postal_code" in comp.get("types", []):
                f["cp"] = f.get("cp") or comp["long_name"]
        if i % 50 == 0:
            _escribe_dataset(EMPRESAS, fichas)
            print(f"    {i}/{len(pend)}")
        time.sleep(LATENCIA)
    _escribe_dataset(EMPRESAS, fichas)
    print(f"  con teléfono: {sum(1 for f in fichas if f.get('telefono'))}")
    print(f"  con web:      {sum(1 for f in fichas if f.get('web'))}")


def main():
    print("Fase 3 — ámbito + Places + filtro de actividad")

    print("\n[1/4] resolviendo coordenadas")
    fichas = json.load(open(EMPRESAS))
    cache = resolver_coords(fichas)

    print("\n[2/4] aplicando ámbito provincial (point-in-polygon PBF + regla del CP)")
    for f in fichas:
        c = cache.get(_clave_cache(f["nombre"], f.get("municipio")), {})
        if not f.get("lat") and c.get("lat"):
            f["lat"], f["lng"] = c["lat"], c["lng"]
        # La dirección de Places trae el CP ('..., 29590 Málaga'); la de la fuente
        # muchas veces no ('Severo Ochoa, 12'). Sin CP, etiqueta() descarta la ficha
        # y no se imprime. Medido: 122 fichas de Málaga con CP en la cache tirado.
        fd = f.get("direccion") or ""
        cd = c.get("direccion") or ""
        if not f.get("cp"):
            m = re.search(r"\b(\d{5})\b", fd) or re.search(r"\b(\d{5})\b", cd)
            if m:
                f["cp"] = m.group(1)
        if cd and not re.search(r"\b\d{5}\b", fd):
            f["direccion"] = cd          # la nuestra no tiene CP: manda la de Places
        # `municipio` vacío con la localidad escrita en la dirección ('41013
        # Sevilla, España', '29640 Las Lagunas de Mijas, Málaga'). Sin municipio,
        # etiqueta() no imprime: 101 fichas con calle real se quedaban fuera del
        # sobre y solo salían 85. El municipio es el token delante del CP.
        if not f.get("municipio"):
            m = re.search(r"\b\d{5}\s+([^,]+)", f.get("direccion") or "")
            if m:
                f["municipio"] = m.group(1).strip()

    # ambito() ANTES de escribir, no despues: es quien clasifica y APARTA lo que
    # cae fuera. El merge no filtra ambito (produce las 592 con el pool remoto
    # dentro), asi que validar el fichero entero contra los invariantes del censo
    # aborta con las 305 de fuera — que es justo lo que hay que sacar.
    dentro, fuera, sin_dom = ambito(fichas)
    _escribe_dataset(EMPRESAS, dentro)
    print(f"  dentro del ámbito: {len(dentro)} | fuera: {len(fuera)} | "
          f"sin domicilio: {len(sin_dom)}")

    print("\n[3/4] consultando reseñas (filtro 12 meses)")
    det = actividad(cache)

    print("\n[4/4] escribiendo resultados")
    activas = inactivas = sin_datos = 0
    for f in dentro:
        d = det.get(_clave_cache(f["nombre"], f.get("municipio")))
        c = cache.get(_clave_cache(f["nombre"], f.get("municipio")), {})
        f["google_place_id"] = c.get("place_id")
        if d:
            f.update({
                "google_rating": d["rating"],
                "google_n_resenas": d["n_resenas"],
                "google_business_status": d["business_status"],
                "resena_mas_reciente": d["resena_mas_reciente"],
                "resenas_ultimos_12m": d["resenas_ultimos_12m"],
            })
            if d["resenas_ultimos_12m"] > 0:
                f["actividad_reciente"] = True
                f["criterio_actividad"] = "RESENA_12M"
                f["proxies_actividad"] = [{"tipo": "RESENA_GOOGLE",
                                           "fecha": d["resena_mas_reciente"],
                                           "url": f"google_place_id:{c['place_id']}"}]
                activas += 1
            else:
                f["actividad_reciente"] = False
                f["criterio_actividad"] = "PENDIENTE_PROXY"   # N2 lo resuelve en Fase 4
                inactivas += 1
        else:
            f["actividad_reciente"] = None
            f["criterio_actividad"] = "SIN_DATOS_PLACES"
            sin_datos += 1

    excl = json.load(open(EXCLUIDOS)) if os.path.exists(EXCLUIDOS) else []
    # Dedupe por NOMBRE, no por id: los ids se renumeran en cada merge (sev-0001,
    # sev-0002... por orden alfabetico), asi que un re-merge cambia el id de la
    # misma empresa y el guard por id dejaba pasar la entrada vieja. Medido: 219 de
    # 534 excluidos tenian su ficha viva en el censo.
    # Se reescribe el fichero desde cero cada pasada: la lista es un DERIVADO del
    # censo (las que no entran), no un historico acumulativo.
    def _k(x):
        """Clave de identidad de una ficha excluida.

        OJO: NO usar el id. Se renumera en cada merge (sev-0001, mal-0009, sin-0080
        segun la provincia calculada y el orden alfabetico), asi que la MISMA
        empresa cambia de id entre pasadas y el guard por id deja la entrada vieja.
        Medido: 212 entradas de mas, con 'alcorce telecomunicaciones' repetida como
        mal-0009 y sin-0096, y '2026 lpj consultores sl.' como mal-0001 y sin-0080.
        Nombre + calle, sin acentos, identifica lo mismo entre re-merges.
        """
        import unicodedata
        def nz(s):
            s = unicodedata.normalize("NFD", str(s or "").lower())
            return "".join(c for c in s if unicodedata.category(c) != "Mn").strip()
        return (nz(x.get("nombre")), nz(x.get("direccion")))

    excl = [x for x in excl if _k(x) in {_k(f) for f in fuera} | {_k(f) for f in sin_dom}]
    ya = {_k(x) for x in excl}
    for f, motivo in [(x, "EXC_FUERA_AMBITO") for x in fuera] + \
                     [(x, "EXC_SIN_DOMICILIO") for x in sin_dom]:
        if _k(f) in ya:
            continue
        ya.add(_k(f))
        excl.append({**f, "motivo_exclusion": motivo,
                     "evidencia_url": "point-in-polygon PBF Geofabrik 2026-09-16",
                     "fecha": HOY})
    _escribe_dataset(EXCLUIDOS, excl, backup=False, validar=False)

    print(f"\n  activas (reseña <12m):      {activas}")
    print(f"  sin reseña reciente:        {inactivas}")
    print(f"  sin datos en Places:        {sin_datos}")
    print(f"  fuera de ámbito → excluidos:{len(fuera)}")
    print(f"  total en data/empresas.json: {len(dentro)}")

    assert all(f.get("criterio_actividad") for f in dentro), "ficha sin criterio_actividad"
    print("\nOK: toda ficha tiene criterio_actividad")


if __name__ == "__main__":
    main()
