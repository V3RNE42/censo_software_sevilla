#!/usr/bin/env python3
"""Check runnable del escritor del dataset: una sola verdad de provincia.

Si esto falla, alguien ha vuelto a duplicar la logica de ambito y el dataset
puede divergir otra vez (que es el desastre que arregla este fichero).
"""
import json, os, sys
sys.path.insert(0, "scripts"); sys.path.insert(0, "scripts/collectors")
from build_provincias import ambito_de, _ambito_key
from _common import _escribe_dataset

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
E = os.path.join(RAIZ, "data", "empresas.json")


def main():
    fichas = json.load(open(E))

    # 1) ambito_de resuelve el homonimo a favor del CP (el bug de los 21)
    prov, coord, conflicto = ambito_de(37.3864291, -5.9793255, "21006", "Sevilla")
    assert (prov, coord, conflicto) == ("Huelva", None, True), (prov, coord, conflicto)

    # 2) coord y CP de acuerdo: no hay conflicto y la coord se conserva
    prov, coord, conflicto = ambito_de(37.4022592, -6.005636, "41092", None)
    assert prov == "Sevilla" and coord and not conflicto

    # 3) fuera de ambito
    assert ambito_de(40.41, -3.70, "28013", None)[0] is None
    assert ambito_de(40.41, -3.70, None, "Madrid")[0] is None

    # 4) sin cp y sin coord: se acepta `provincia` solo si esta en el ambito
    assert ambito_de(None, None, None, "Huelva")[0] == "Huelva"
    assert ambito_de(None, None, None, "Teruel")[0] is None

    # 5) el escritor acepta el dataset real
    with open("/tmp/_t_ok.json", "w") as f:
        pass
    assert _escribe_dataset("/tmp/_t_ok.json", fichas) == len(fichas)

    # 6) y aborta un homonimo inyectado
    malo = [dict(fichas[0], nombre="H", ambito="HUELVA", cp="21006",
                 lat=37.4022, lng=-6.0056)]
    try:
        _escribe_dataset("/tmp/_t_bad.json", malo)
        raise AssertionError("el escritor acepto un homonimo")
    except SystemExit:
        pass

    # 7) excluidos se escribe sin los invariantes del censo
    _escribe_dataset("/tmp/_t_exc.json", [dict(fichas[0], ambito=None)],
                     backup=False, validar=False)

    print("OK escritor: 7/7 checks (homonimo->CP, fuera de ambito, guard, excluidos)")


if __name__ == "__main__":
    main()
