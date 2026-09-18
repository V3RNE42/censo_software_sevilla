#!/usr/bin/env python3
"""
provincia_de() desde el PBF de Geofabrik: polígonos ya ensamblados.

Por qué PBF y no Overpass: 'out geom' devuelve ~106 way-fragments sueltos por
provincia, y un punto en la costura no cae dentro de ninguno (fallo silencioso
→ None). El PBF trae las áreas cerradas: Sevilla viene como 1 anillo de 7.816
puntos. Medido el 18/09/2026.

Refrescar datos (el PBF cambia a diario, los límites no):
  cd /tmp && curl -sLO https://download.geofabrik.de/europe/spain/andalucia-latest.osm.pbf
  python3 scripts/build_provincias.py /tmp/andalucia-latest.osm.pbf
Luego se puede borrar el PBF: el cache JSON son ~2 MB.
"""
import json, os, sys

CACHE = os.path.expanduser("~/.cache/censo_software/provincias_and.json")
# Forma canónica = la que usa `municipio`/`provincia` en todo el proyecto.
# NO cambiar a mayúsculas: 'Malaga' != 'Málaga' y el filtro de provincia
# del index comparaba por startswith -> Málaga salía 0 fichas (Fase 5).
OBJETIVO = {"Sevilla": "Sevilla", "Málaga": "Málaga"}


def _extraer(pbf):
    import osmium

    class H(osmium.SimpleHandler):
        def __init__(self):
            super().__init__(); self.res = {}

        def area(self, a):
            t = a.tags
            if t.get("boundary") != "administrative" or t.get("admin_level") != "6":
                return
            destino = OBJETIVO.get(t.get("name"))
            if not destino:
                return
            anillos = [[(n.lon, n.lat) for n in ring] for ring in a.outer_rings()]
            anillos = [r for r in anillos if len(r) >= 4]
            if anillos:
                self.res[destino] = anillos

    h = H()
    h.apply_file(pbf, locations=True)
    return h.res


def _poligonos():
    if not os.path.exists(CACHE):
        raise SystemExit(
            f"Falta {CACHE}. Generarlo con:\n"
            "  cd /tmp && curl -sLO https://download.geofabrik.de/europe/spain/andalucia-latest.osm.pbf\n"
            "  python3 scripts/build_provincias.py /tmp/andalucia-latest.osm.pbf"
        )
    return json.load(open(CACHE))


def provincia_de(lat, lng):
    """'Sevilla' | 'Málaga' | None. Las demás provincias andaluzas dan None (fuera de ámbito)."""
    from shapely.geometry import Point, Polygon
    p = Point(lng, lat)
    for nombre, anillos in _poligonos().items():
        for anillo in anillos:
            if Polygon(anillo).contains(p):
                return nombre
    return None


def dentro_de_provincias(lat, lng):
    return provincia_de(lat, lng) is not None


if __name__ == "__main__":
    if len(sys.argv) > 1:
        datos = _extraer(sys.argv[1])
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        json.dump(datos, open(CACHE, "w"))
        print(f"cache escrito: {CACHE} ({os.path.getsize(CACHE)//1024} KB)")
        for k, v in datos.items():
            print(f"  {k}: {len(v)} anillos, {sum(len(a) for a in v)} puntos")

    from geom import haversine_km, isocrona_bucket, SEVILLA

    puntos = [
        ("Sevilla capital", 37.3891, -5.9845, "Sevilla"),
        ("Málaga capital", 36.7213, -4.4214, "Málaga"),
        ("Dos Hermanas", 37.2829, -5.9209, "Sevilla"),
        ("Utrera", 37.1851, -5.7807, "Sevilla"),
        ("Carmona", 37.4712, -5.6466, "Sevilla"),
        ("Écija", 37.5424, -5.0825, "Sevilla"),
        ("Antequera", 37.0194, -4.5622, "Málaga"),
        ("Ronda", 36.7423, -5.1665, "Málaga"),
        ("Marbella", 36.5110, -4.8870, "Málaga"),
        ("Córdoba capital", 37.8882, -4.7794, None),
        ("Huelva capital", 37.2614, -6.9447, None),
        ("Cádiz capital", 36.5271, -6.2886, None),
    ]
    fallos = 0
    for nombre, lat, lng, esperado in puntos:
        got = provincia_de(lat, lng)
        ok = got == esperado
        fallos += not ok
        print(f"  {'OK ' if ok else 'FALLO'} {nombre:18} {str(got):8} (esperado {esperado})")
    assert fallos == 0, f"{fallos} puntos mal clasificados"
    print(f"OK provincia_de(): {len(puntos)}/{len(puntos)} puntos correctos")
    print(f"OK haversine (Carmona {haversine_km(SEVILLA, (37.4712, -5.6466)):.1f} km) + isocrona {isocrona_bucket(50)}")
