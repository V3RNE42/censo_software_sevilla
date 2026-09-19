#!/usr/bin/env python3
"""Check del municipio contaminado por la oferta de empleo.

El bug: `norm_municipio` da clave en minusculas y DIRCE esta en mayusculas, asi
que la comparacion no era cierta nunca y ni `campo_foraneo` ni `municipio_util`
filtraban. 38 fichas quedaron con cp de Sevilla y municipio=Málaga.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from merge_fuentes import municipio_util, campo_foraneo, _ambito_de_valor

CASOS_UTIL = [
    ({"municipio": "Málaga", "provincia": "SEVILLA"}, None, "EY: provincia contraria"),
    ({"municipio": "MALAGA", "provincia": "SEVILLA"}, None, "mayusculas"),
    ({"municipio": "sevilla", "provincia": "MALAGA"}, None, "minusculas, inverso"),
    ({"municipio": "Huelva", "provincia": "SEVILLA"}, None, "Huelva vs Sevilla"),
    ({"municipio": "Dos Hermanas", "provincia": "SEVILLA"}, "Dos Hermanas", "municipio real"),
    ({"municipio": "Málaga", "provincia": "MALAGA"}, "Málaga", "municipio = provincia"),
    ({"municipio": "Cádiz", "provincia": "SEVILLA"}, None, "Cádiz es provincia, no municipio"),
    ({"municipio": "Marbella", "provincia": "MALAGA"}, "Marbella", "Marbella es municipio"),
    ({"municipio": "Málaga", "provincia": "MALAGA"}, "Málaga", "Málaga capital = provincia"),
    ({"municipio": "Madrid", "provincia": "MALAGA"}, None, "Madrid colado en fila andaluza"),
    ({"municipio": None, "provincia": "SEVILLA"}, None, "sin municipio"),
    ({"municipio": "Málaga"}, "Málaga", "sin provincia: no se juzga"),
    ({"municipio": "100% remoto", "provincia": "SEVILLA"}, None, "centinela"),
]

CASOS_FORANEO = [
    ({"municipio": "Málaga", "provincia": "SEVILLA"}, "MALAGA", "cruza"),
    ({"municipio": "Málaga", "provincia": "MALAGA"}, None, "misma provincia"),
    ({"municipio": "Dos Hermanas", "provincia": "SEVILLA"}, None, "municipio real"),
    ({"municipio": "Cádiz", "provincia": "SEVILLA"}, None, "fuera de ambito no cuenta"),
]


def main():
    assert _ambito_de_valor("Málaga") == "MALAGA"
    assert _ambito_de_valor("malaga") == "MALAGA"
    assert _ambito_de_valor("Dos Hermanas") is None

    for d, esp, desc in CASOS_UTIL:
        got = municipio_util(d)
        assert got == esp, f"municipio_util {desc}: {got!r} != {esp!r}"
    for d, esp, desc in CASOS_FORANEO:
        got = campo_foraneo(d)
        assert got == esp, f"campo_foraneo {desc}: {got!r} != {esp!r}"

    # y sobre el dataset real: ninguna ficha con municipio = otra provincia del ambito
    import json
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    fichas = json.load(open(os.path.join(raiz, "data", "empresas.json"), encoding="utf-8"))
    malas = [f["nombre"] for f in fichas
             if _ambito_de_valor(f.get("municipio"))
             and _ambito_de_valor(f.get("ambito"))
             and _ambito_de_valor(f.get("municipio")) != _ambito_de_valor(f.get("ambito"))]
    assert not malas, f"{len(malas)} fichas con municipio de otra provincia: {malas[:5]}"
    print(f"OK municipio: {len(CASOS_UTIL)}+{len(CASOS_FORANEO)} casos, 0 fichas cruzadas en el dataset")


if __name__ == "__main__":
    main()
