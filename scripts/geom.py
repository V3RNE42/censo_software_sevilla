#!/usr/bin/env python3
"""
geom.py — geometría para el censo.

DEPENDENCIA DE FASE 0: provincia_de() NO funciona todavía. Está bloqueada por cómo
Overpass sirve los límites provinciales (ver nota abajo). haversine e isocrona SÍ
están verificados y se pueden usar ya.

Requisito: shapely (disponible). NO disponibles: pyproj, geopandas.
"""
import json, math, os, urllib.parse, urllib.request

SEVILLA = (37.3891, -5.9845)          # Puerta de Jerez
R_TIERRA = 6371.0088

# IDs de relación OSM, obtenidos vía Nominatim (consulta barata de 2 llamadas).
# OJO: NO usar area["ref:ine"="41"] en Overpass — medido el 18/09/2026 devuelve 0
# elementos para Andalucía. Los IDs de relación sí son correctos.
PROVINCIAS = {"SEVILLA": 349008, "MALAGA": 5275848}
CACHE = os.path.expanduser("~/.cache/censo_software/provincias.json")

MIRRORS = [
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass-api.de/api/interpreter",
]


def haversine_km(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * R_TIERRA * math.asin(math.sqrt(h))


def isocrona_bucket(km):
    """Etiqueta, no filtro. El radio no recorta: Málaga capital está a ~160 km y entra igual."""
    for tope, etiqueta in ((30, "30"), (45, "45"), (60, "60"), (90, "90")):
        if km <= tope:
            return etiqueta
    return ">90"


# ─────────────────────────────────────────────────────────────────────────────
# provincia_de() — BLOQUEADO
#
# Estado: 'out geom' devuelve los límites como ~100-134 way-fragments sueltos por
# provincia (no anillos cerrados). Un punto en una costura entre fragmentos no cae
# dentro de ninguno y provincia_de() devuelve None. Verificado: Sevilla capital
# devuelve None con 106 fragmentos cargados.
#
# Solución a implementar en Fase 0 (una de estas, de más barata a más cara):
#   1. Descargar el límite por MUNICIPIO (admin_level=8) en vez de por provincia.
#      Municipios hay ~105+103, pero 'out geom' de cada uno es pequeño y la
#      asignación municipio->provincia es una tabla fija que no necesita polígonos.
#      Coste: ~208 consultas cacheadas una vez. Es la vía recomendada.
#   2. Usar 'out geom' con los fragmentos y ensamblarlos en anillos por
#      coincidencia de extremos. Más código y frágil.
#   3. Convertir el PBF de Geofabrik (192 MB) y usar sus límites ya ensamblados.
#      Lo más robusto, más trabajo de setup.
#   4. Geocodificación inversa por ficha con Nominatim (1 req/s). Evita polígonos
#      del todo, pero son cientos de llamadas y depende de un servicio externo.
#
# Mientras no esté resuelto, el pipeline NO puede descartar fichas de Córdoba o
# Huelva que entren por fuentes amplias. Es un agujero conocido, no un olvido.
# ─────────────────────────────────────────────────────────────────────────────
def provincia_de(lat, lng):
    raise NotImplementedError(
        "provincia_de() sin implementar: Overpass sirve los límites provinciales como "
        "way-fragments sueltos, no como anillos. Ver opciones 1-4 en el docstring. "
        "Bloqueante para Fase 0."
    )


def _descargar_fragmentos():
    """Baja los límites provinciales crudos (fragmentos). Cachea en disco."""
    ids = ",".join(str(i) for i in PROVINCIAS.values())
    q = f"[out:json][timeout:280];rel(id:{ids});out geom;"
    cuerpo = urllib.parse.urlencode({"data": q}).encode()
    ultimo_error = None
    for _ in range(3):
        for mirror in MIRRORS:
            req = urllib.request.Request(
                mirror, data=cuerpo,
                headers={"User-Agent": "censo-software-sevilla/1.0 (julio@cabanillas.dev)"},
            )
            try:
                datos = json.load(urllib.request.urlopen(req, timeout=300))
            except Exception as exc:                       # 504, timeout, JSON roto
                ultimo_error = f"{mirror}: {exc}"
                continue
            por_id = {v: k for k, v in PROVINCIAS.items()}
            salida = {}
            for rel in datos.get("elements", []):
                frags = [
                    [(p["lat"], p["lon"]) for p in m["geometry"]]
                    for m in rel.get("members", [])
                    if m.get("role") == "outer" and m.get("geometry")
                ]
                if frags:
                    salida[por_id.get(rel["id"])] = frags
            if salida:
                return salida
            ultimo_error = f"{mirror}: respuesta sin miembros outer"
    raise RuntimeError(f"No se pudieron descargar los límites. Ultimo error: {ultimo_error}")


def _fragmentos():
    if os.path.exists(CACHE):
        return json.load(open(CACHE))
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    frags = _descargar_fragmentos()
    json.dump(frags, open(CACHE, "w"))
    return frags


def _demo():
    """Check runnable: python3 geom.py"""
    d_self = haversine_km(SEVILLA, SEVILLA)
    assert d_self < 1e-9, f"mismo punto debe dar 0, dio {d_self}"

    d_carmona = haversine_km(SEVILLA, (37.4712, -5.6466))
    assert 25 < d_carmona < 35, f"Carmona deberia estar a ~30 km, dio {d_carmona:.1f}"

    assert isocrona_bucket(0) == "30"
    assert isocrona_bucket(44) == "45"
    assert isocrona_bucket(200) == ">90"

    print(f"OK haversine (Carmona {d_carmona:.1f} km) + isocrona")

    try:
        provincia_de(*SEVILLA)
    except NotImplementedError:
        print("PENDIENTE provincia_de(): ver opciones en el docstring (bloqueante Fase 0)")
    else:
        raise AssertionError("provincia_de() deberia seguir sin implementar; actualiza este check")


if __name__ == "__main__":
    _demo()
