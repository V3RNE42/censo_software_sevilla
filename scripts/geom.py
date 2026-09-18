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


# provincia_de() e isocrona viven en build_provincias.py (polígonos del PBF,
# ensamblados). Aquí solo se reexporta para que los collectors tengan un import único.
from build_provincias import provincia_de, dentro_de_provincias  # noqa: E402,F401


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

    assert provincia_de(*SEVILLA) == "Sevilla"
    assert provincia_de(36.7213, -4.4214) == "Málaga"
    assert provincia_de(37.8882, -4.7794) is None, "Cordoba queda fuera de ambito"
    print("OK provincia_de(): Sevilla=Sevilla | Malaga=Málaga | Cordoba=None")


if __name__ == "__main__":
    _demo()
