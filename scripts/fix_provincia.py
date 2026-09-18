#!/usr/bin/env python3
"""fix_provincia.py — deriva `provincia` de la COORDENADA (PBF), no del id.

Causa raíz: el prefijo del `id` (sev-/mal-) es el de la FUENTE que descubrió la
ficha, no el de la provincia donde está. E2_EMPLEO buscó en Málaga y encontró
ofertas de Accenture en Cartuja (Sevilla) -> id mal-0002 con provincia Sevilla.

Regla: provincia = point-in-polygon(lat,lng) sobre los polígonos del PBF.
Si no hay coords -> provincia = null (no se inventa).
"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from geom import provincia_de

ROOT = Path("/root/censo_software_sevilla")
DATA = ROOT / "data" / "empresas.json"


def main():
    d = json.loads(DATA.read_text(encoding="utf-8"))
    cambios, sin_coords, nulos = [], 0, 0
    for c in d:
        lat, lng = c.get("lat"), c.get("lng")
        vieja = c.get("provincia")
        if lat is None or lng is None:
            sin_coords += 1
            nueva = None
        else:
            nueva = provincia_de(lat, lng)
            if nueva is None:
                nulos += 1
                nueva = None
        if nueva is not None:
            nueva = nueva.capitalize()  # geom devuelve SEVILLA/MALAGA
        if nueva != vieja:
            cambios.append((c["id"], c.get("nombre"), c.get("municipio"), vieja, nueva))
        c["provincia"] = nueva

    DATA.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"provincia corregida desde coordenada: {len(cambios)} cambios")
    for cid, nom, mun, v, n in cambios:
        print(f"  {cid:12s} {str(nom)[:34]:34s} mun={str(mun)[:20]:20s} {str(v):8s} -> {n}")
    print(f"\nsin coordenadas (provincia=null): {sin_coords}")
    print(f"coords fuera de SE/MA        : {nulos}")
    from collections import Counter
    print("\nreparto final:", dict(Counter(c["provincia"] for c in d)))


if __name__ == "__main__":
    main()
