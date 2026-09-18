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
# Provincias EN ÁMBITO del censo. Se ensamblan TODAS las andaluzas en el cache
# (el parseo del PBF es lo caro: 194 MB); OBJETIVO filtra al LEER, no al escribir.
# Así añadir Cádiz o Córdoba es una línea aquí y cero re-descargas.
OBJETIVO = {"Sevilla": "Sevilla", "Málaga": "Málaga", "Huelva": "Huelva"}
# El PBF trae relaciones con nombre compuesto para enclaves/disputas de límite
# ('Córdoba - Sevilla', 163 pts). No son provincia: se guardan pero no se usan.
OTRAS_ANDALUZAS = ("Sevilla", "Málaga", "Huelva", "Cádiz", "Córdoba",
                   "Granada", "Jaén", "Almería")


def _extraer(pbf):
    """Ensambla TODAS las provincias andaluzas del PBF. Filtrar aquí tiraba datos
    que cuestan 194 MB de parseo: añadir una provincia obligaba a re-parsear."""
    import osmium

    class H(osmium.SimpleHandler):
        def __init__(self):
            super().__init__(); self.res = {}

        def area(self, a):
            t = a.tags
            if t.get("boundary") != "administrative" or t.get("admin_level") != "6":
                return
            nombre = t.get("name")
            if nombre not in OTRAS_ANDALUZAS:
                return
            anillos = [[(n.lon, n.lat) for n in ring] for ring in a.outer_rings()]
            anillos = [r for r in anillos if len(r) >= 4]
            if anillos and nombre not in self.res:  # 1ª relación gana; evita duplicados
                self.res[nombre] = anillos

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
    """'Sevilla' | 'Málaga' | 'Huelva' | None. Otras andaluzas y fuera de Andalucía -> None.

    Filtra por OBJETIVO al leer: el cache guarda las 8 andaluzas, pero solo las
    del ámbito del censo resuelven. Un punto en Cádiz da None a propósito.
    """
    from shapely.geometry import Point, Polygon
    p = Point(lng, lat)
    for nombre, anillos in _poligonos().items():
        if nombre not in OBJETIVO:  # fuera de ámbito: no resuelve
            continue
        for anillo in anillos:
            if Polygon(anillo).contains(p):
                return OBJETIVO[nombre]
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
        # Huelva: provincia entera, añadida en Addendum 01. Extremos: costa,
        # frontera PT, sierra norte y linde con Sevilla.
        ("Huelva capital", 37.2614, -6.9447, "Huelva"),
        ("Lepe", 37.2167, -7.4000, "Huelva"),
        ("Ayamonte", 37.2135, -7.4083, "Huelva"),
        ("Aracena", 37.8926, -6.5566, "Huelva"),
        ("Valverde del Camino", 37.5747, -6.7533, "Huelva"),
        ("Almonte (El Rocío)", 37.2630, -6.5166, "Huelva"),
        ("Cortegana", 37.9100, -6.8200, "Huelva"),
        # Fuera de ámbito: deben dar None a propósito.
        ("Córdoba capital", 37.8882, -4.7794, None),
        ("Cádiz capital", 36.5271, -6.2886, None),
        ("Badajoz (Extremadura)", 38.8794, -6.9707, None),
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
