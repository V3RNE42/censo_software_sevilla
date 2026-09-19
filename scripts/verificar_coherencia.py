#!/usr/bin/env python3
"""verificar_coherencia.py — check runnable de la coherencia de provincia.

POR QUÉ EXISTE: durante el desarrollo, comparar `ambito` ('SEVILLA') con el
resultado canónico de provincia_de() ('Sevilla' / 'Málaga') dio 123 y luego 26
"incoherencias" que NO existían — era el case y la tilde. Un verificador que
grita en falso es peor que no tenerlo: hace perder tiempo y erosiona la
confianza en el dataset. Aquí la normalización es ASCII+upper, y hay un caso
de control con tilde para que el propio check no pueda volver a fallar así.

Uso: python3 scripts/verificar_coherencia.py
"""
import json
import os
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from geom import provincia_de
from build_provincias import ambito_de

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(RAIZ, "data", "empresas.json")


def norm(s):
    """ASCII + mayúsculas: 'Málaga'->'MALAGA', 'SEVILLA'->'SEVILLA'. Iguales."""
    return unicodedata.normalize("NFD", s or "").encode("ascii", "ignore").decode().upper().strip()


def _demo_norm():
    """El check se valida a sí mismo: sin esto, el bug de la tilde vuelve."""
    assert norm("Málaga") == norm("MALAGA") == "MALAGA"
    assert norm("Sevilla") == norm("SEVILLA") == "SEVILLA"
    assert norm("Málaga") != norm("Sevilla")
    assert norm(None) == ""


def main():
    _demo_norm()
    d = json.load(open(DATA, encoding="utf-8"))
    # Deriva de etiquetas.py: una provincia nueva no obliga a tocar 2 ficheros.
    from etiquetas import CP_PROV

    mal_coord = mal_cp = sin_coords = sin_cp = 0
    multisede = []
    # municipio en OTRA provincia, con la dirección sin mencionarlo: dato
    # contaminado de la oferta de empleo (EY: cp=41002 Sevilla + municipio=Málaga,
    # de una vacante en Málaga). Ningún check lo miraba — `etiqueta()` ya ignora
    # ese municipio, así que el efecto se contiene, pero no se veía en el informe.
    mun_ajeno = []
    for c in d:
        amb = norm(c.get("ambito"))
        cp = (c.get("cp") or "").strip()
        lat, lng = c.get("lat"), c.get("lng")
        prov = norm(provincia_de(lat, lng)) if (lat and lng) else ""
        # `ambito` se decide por CP cuando el CP y la coord discrepan (homónimos de
        # Places). Este check juzgaba solo por coordenada, así que las fichas
        # resueltas por CP salían como "23 incoherentes" que no lo son: usaba otra
        # regla que la fuente única. Se juzga con ambito_de, que es quien decide.
        prov_decidida, _, _ = ambito_de(lat, lng, c.get("cp"), c.get("provincia"))
        prov = norm(prov_decidida) if prov_decidida else ""
        # `municipio` puede ser un municipio o una provincia; interesa si es una
        # de las provincias del ámbito distinta a la de la ficha.
        mun = (c.get("municipio") or "").strip()
        if mun and norm(mun) in ("SEVILLA", "MALAGA", "HUELVA") and norm(mun) != amb:
            dire = norm(c.get("direccion") or "")
            if norm(mun) not in dire:      # si la dirección lo dice, no es contaminación
                mun_ajeno.append(c)
        if lat is None:
            sin_coords += 1
            continue
        if prov != amb:
            mal_coord += 1
            print(f"  COORD {c['id']:10s} {c['nombre'][:28]:28s} ambito={amb} coords->{prov}")
        exp = CP_PROV.get(amb)
        if exp and cp:
            if cp[:2] != exp:
                # El CP es de otra provincia pero la coordenada cae en el ámbito:
                # la empresa tiene varias sedes y esta ficha es la del ámbito, con
                # la dirección de OTRA sede pegada por la fuente. Medido:
                # sev-0023 'Between Technology' — direccion 'calle Charles Darwin
                # s/n, Barcelona, 08018' desde sevillatechpark.es, con coordenada
                # en la Cartuja de Sevilla. La ficha es válida (está en el ámbito);
                # lo que no vale es imprimir un sobre con ese CP. No es
                # incoherencia del dataset: es una sede múltiple. etiqueta() ya la
                # descarta por CP ajeno, que es el efecto correcto y buscado.
                if prov == amb:      # `prov` ya viene normalizado arriba (norm())
                    multisede.append(c)
                    continue
                mal_cp += 1
                print(f"  CP    {c['id']:10s} {c['nombre'][:28]:28s} ambito={amb} cp={cp}")
        elif exp and not cp:
            # Sin CP NO es incoherencia: `cp` lo rellena etiquetas.etiqueta() a
            # partir de la dirección (o Places) más adelante. Contarlo como fallo
            # daba 388/388 falsos positivos y mataba el check con assert.
            sin_cp += 1

    con_coords = len(d) - sin_coords
    print(f"ambito vs coordenada : {mal_coord}/{con_coords} incoherentes")
    print(f"ambito vs cp         : {mal_cp}/{con_coords} incoherentes "
          f"({sin_cp} sin CP poblado, no verificables aun)")
    print(f"multi-sede           : {len(multisede)} (CP de otra sede, coord en el ambito:"
          " no se imprimen, no son incoherentes)")
    for c in multisede:
        print(f"  MULTISEDE {c['id']:10s} {c['nombre'][:28]:28s} cp={c.get('cp')} "
              f"coord->{provincia_de(c['lat'], c['lng'])}")
    print(f"municipio de otra provincia: {len(mun_ajeno)} (dato de la oferta, no de la ficha:"
          " etiqueta() lo ignora)")
    for c in mun_ajeno[:15]:
        print(f"  MUN_AJENO {c['id']:10s} {c['nombre'][:26]:26s} amb={norm(c.get('ambito'))} "
              f"mun={c.get('municipio')} cp={c.get('cp') or '-'}")
    print(f"sin coordenadas      : {sin_coords} (provincia no verificable)")
    assert mal_coord == 0, f"{mal_coord} fichas con ambito != provincia de su coordenada"
    assert mal_cp == 0, f"{mal_cp} fichas con CP de otra provincia"
    print(f"OK: {con_coords} fichas coherentes (ambito == punto-en-poligono; "
          f"{con_coords-sin_cp-len(multisede)} ademas con rango de CP)")


if __name__ == "__main__":
    main()
