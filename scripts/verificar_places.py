#!/usr/bin/env python3
"""
Fase 3 — ámbito + verificación Places + filtro de actividad 12 meses.

Dos pasos:
  1. ambito(): marca cada ficha con su provincia real por point-in-polygon del PBF,
     y descarta lo que cae fuera de Sevilla/Málaga (Córdoba, Huelva, Cádiz...).
  2. actividad(): Places textsearch (nombre LIMPIO, sin municipio) + details con
     reviews_sort=newest. publishTime ISO → filtro de 12 meses.

La key se lee del entorno. NUNCA inline (ver Anexo A del plan).
"""
import json, os, re, sys, time, urllib.parse, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_provincias import provincia_de

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
    from etiquetas import CP_PROV
    for amb, pref in CP_PROV.items():
        if (cp or "").startswith(pref):
            return amb
    return None


def ambito():
    """Marca provincia real y aparta lo que cae fuera del ámbito.

    `ambito` va SIEMPRE en mayúsculas (SEVILLA/MALAGA/HUELVA): es la clave que
    consumen build_html.py, etiquetas.py y el filtro del index (`dataset.prov`).
    provincia_de() devuelve la forma canónica ('Sevilla') y aquí se normaliza:
    tener las dos formas rompía el filtro del mapa (190 fichas invisibles).

    HOMÓNIMOS: Places busca por nombre limpio y una empresa como 'Diseño web HH'
    (Huelva) resuelve a un negocio homónimo de Sevilla. Medido: la ficha decía
    cp=21006 Huelva con coords de Sevilla y ambito=SEVILLA. Cuando el CP de la
    dirección es del ámbito y discrepa de la coordenada, MANDA EL CP: es dato
    postal verificado (el que va en el sobre), la coord es una búsqueda por nombre.
    """
    fichas = json.load(open(EMPRESAS))
    dentro, fuera = [], []
    for f in fichas:
        lat, lng = f.get("lat"), f.get("lng")
        prov = provincia_de(lat, lng) if (lat and lng) else None
        cp_amb = _cp_a_ambito((f.get("cp") or "").strip())

        if cp_amb and prov and _ambito_key(prov) != cp_amb:
            # discrepancia: el CP postal manda. La coord es de un homónimo.
            # NO se excluye: se queda en el censo con la provincia de su CP y sin
            # punto en el mapa (una coord de otra provincia no es su ubicación).
            f["flags"] = f.get("flags", []) + ["COORD_HOMONIMO"]
            f["coords_sospechosas"] = {"coord_ambito": _ambito_key(prov),
                                       "cp_ambito": cp_amb}
            f["lat"] = f["lng"] = None       # no son de esta empresa: fuera del mapa
            prov = cp_amb.capitalize().replace("Malaga", "Málaga")
        elif cp_amb and not prov:
            prov = cp_amb.capitalize().replace("Malaga", "Málaga")

        if prov:
            f["ambito"] = _ambito_key(prov)
            f["provincia"] = prov.capitalize().replace("Malaga", "Málaga")
            f["flags"] = [x for x in f.get("flags", []) if x != "MUNICIPIO_FUERA_PROVINCIA"]
            dentro.append(f)
        elif lat and lng:
            f["flags"] = f.get("flags", []) + ["FUERA_AMBITO"]
            f["ambito"] = None
            fuera.append(f)
        else:
            # Sin coords. El CP manda sobre `provincia`: el merge ya sobrescribió
            # `provincia` con lo que dijo Places, así que puede estar contaminado
            # ('Diseño web HH' de Huelva quedó como Sevilla). El CP viene de la
            # dirección postal, que es el dato del sobre.
            amb = cp_amb or _ambito_key(f.get("provincia"))
            f["ambito"] = amb
            if "COORD_HOMONIMO" not in (f.get("flags") or []):
                f["flags"] = f.get("flags", []) + ["SIN_COORDS"]
            dentro.append(f)
    return dentro, fuera


def _ambito_key(valor):
    """'Sevilla' | 'SÉVILLA' | 'Málaga' -> 'SEVILLA' | 'MALAGA'. Sin tildes."""
    import unicodedata
    s = unicodedata.normalize("NFD", str(valor or "").upper())
    return "".join(c for c in s if unicodedata.category(c) != "Mn").strip()


def _clave_cache(nombre):
    """Clave de cache INSENSIBLE a mayúsculas/tildes/espacios.

    Indexar por `f['nombre']` crudo pagaba dos veces la misma empresa cuando el
    mismo negocio aparece como 'SYMONLINE' en un raw y 'Symonline' en otro
    (medido: 8 solapes entre las dos fuentes de Huelva). Misma normalización que
    usa el merge, para que coincida con lo que ya está cacheado.
    """
    import unicodedata
    s = unicodedata.normalize("NFD", str(nombre or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def resolver_coords(fichas):
    """Rellena lat/lng vía Places textsearch. Nombre LIMPIO: 'CARTO Sevilla' da ZERO_RESULTS."""
    cache = json.load(open(CACHE_PLACES)) if os.path.exists(CACHE_PLACES) else {}
    pendientes = {}
    for f in fichas:
        if f.get("lat"):
            continue
        k = _clave_cache(f["nombre"])
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
    con_pid = [f for f in json.load(open(EMPRESAS)) if cache.get(_clave_cache(f["nombre"]), {}).get("place_id")]
    print(f"  consultando reseñas de {len(con_pid)} fichas...")
    for i, f in enumerate(con_pid, 1):
        pid = cache[_clave_cache(f["nombre"])]["place_id"]
        d = _places("https://maps.googleapis.com/maps/api/place/details/json",
                    {"place_id": pid, "language": "es", "reviews_sort": "newest",
                     "fields": "name,rating,user_ratings_total,reviews,business_status"})
        r = d.get("result", {})
        fechas = sorted((x["time"] for x in r.get("reviews", [])), reverse=True)
        nueva = (time.strftime("%Y-%m-%d", time.gmtime(fechas[0])) if fechas else None)
        det[_clave_cache(f["nombre"])] = {
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
            if not f.get("telefono") and cache.get(_clave_cache(f["nombre"]), {}).get("place_id")]
    print(f"  enriqueciendo contacto de {len(pend)} fichas...")
    for i, f in enumerate(pend, 1):
        pid = cache[_clave_cache(f["nombre"])]["place_id"]
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
            json.dump(fichas, open(EMPRESAS, "w"), ensure_ascii=False, indent=1)
            print(f"    {i}/{len(pend)}")
        time.sleep(LATENCIA)
    json.dump(fichas, open(EMPRESAS, "w"), ensure_ascii=False, indent=1)
    print(f"  con teléfono: {sum(1 for f in fichas if f.get('telefono'))}")
    print(f"  con web:      {sum(1 for f in fichas if f.get('web'))}")


def main():
    print("Fase 3 — ámbito + Places + filtro de actividad")

    print("\n[1/4] resolviendo coordenadas")
    fichas = json.load(open(EMPRESAS))
    cache = resolver_coords(fichas)

    print("\n[2/4] aplicando ámbito provincial (point-in-polygon PBF)")
    for f in fichas:
        c = cache.get(_clave_cache(f["nombre"]), {})
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
    json.dump(fichas, open(EMPRESAS, "w"), ensure_ascii=False, indent=1)

    dentro, fuera = ambito()
    print(f"  dentro del ámbito: {len(dentro)} | fuera: {len(fuera)}")

    print("\n[3/4] consultando reseñas (filtro 12 meses)")
    det = actividad(cache)

    print("\n[4/4] escribiendo resultados")
    activas = inactivas = sin_datos = 0
    for f in dentro:
        d = det.get(_clave_cache(f["nombre"]))
        c = cache.get(_clave_cache(f["nombre"]), {})
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
    for f in fuera:
        excl.append({**f, "motivo_exclusion": "EXC_FUERA_AMBITO",
                     "evidencia_url": f"point-in-polygon PBF Geofabrik 2026-09-16",
                     "fecha": HOY})
    json.dump(dentro, open(EMPRESAS, "w"), ensure_ascii=False, indent=1)
    json.dump(excl, open(EXCLUIDOS, "w"), ensure_ascii=False, indent=1)

    print(f"\n  activas (reseña <12m):      {activas}")
    print(f"  sin reseña reciente:        {inactivas}")
    print(f"  sin datos en Places:        {sin_datos}")
    print(f"  fuera de ámbito → excluidos:{len(fuera)}")
    print(f"  total en data/empresas.json: {len(dentro)}")

    assert all(f.get("criterio_actividad") for f in dentro), "ficha sin criterio_actividad"
    print("\nOK: toda ficha tiene criterio_actividad")


if __name__ == "__main__":
    main()
