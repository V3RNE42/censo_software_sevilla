#!/usr/bin/env python3
"""Validación de la pasada de Places por dirección (CP que falta).

Places NO devuelve ZERO_RESULTS cuando no encuentra una calle: contesta con la que
más se le parece, y un CP así es un sobre que no llega. Los 8 casos de abajo están
medidos contra la API real; los 3 primeros son falsos positivos que se colaron en
una pasada anterior del censo.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cp_por_direccion import calle_coincide, coincide, municipio_en_direccion  # noqa: E402


# (dirección de la ficha, formatted_address que devuelve Places, ¿es válido?)
CASOS = [
    # Falsos positivos: Places contestó con OTRA calle del mismo término municipal.
    ("C/ BAHIA 2 4 1 (BENALMANA)", "C. Hamlet, 5, Teatinos-Universidad, 29006 Málaga", False),
    ("AVDA CONDE DE ORGAZ 49", "C. Cuarteles, 49, Distrito Centro, 29002 Málaga", False),
    # Mismo nombre de calle, municipio distinto: solo el municipio lo distingue.
    ("PLAZA GOYA 3 8 C (TORREMOLINOS)", "Calle Goya, 3, Carretera de Cádiz, 29002 Málaga", False),
    # Buenos: el municipio o la calle coinciden.
    ("C/ Nuestra Señora de Gracia 3 (MARBELLA)", "C. Ntra. Sra. de Gracia, 3, 29601 Marbella, Málaga", True),
    ("AVDA JUAN GOMEZ JUANITO 1", "Pl. Juan Gomez Juanito, 1, Carretera de Cádiz, 29004 Málaga", True),
    ("CALLE Jabea 36 Número36", "C. Jabea, 36, 29639 Benalmádena, Málaga", True),
    ("C/ GUATEMALA 8", "C. Guatemala, 8, 41840 Pilas, Sevilla", True),
    ("C/ TANZANIA 3 Ptl.3 (MALAGA)", "C. Tanzania, 3, Churriana, 29140 Málaga", True),
]


def valida(dire, devuelta):
    """Réplica del orden de comprobaciones de main(): el orden es lo que se prueba."""
    mun = municipio_en_direccion(dire)
    if mun:
        return coincide(mun, devuelta)
    return calle_coincide(dire, devuelta)


def main():
    for dire, dev, esp in CASOS:
        got = valida(dire, dev)
        assert got == esp, f"{dire!r} vs {dev!r}: {got} != {esp}"

    # El orden importa: con municipio en la dirección, comparar la calle rechazaría
    # 'Nuestra Señora' vs 'Ntra. Sra.' y tiraría un CP correcto.
    a, b = CASOS[3][0], CASOS[3][1]
    assert not calle_coincide(a, b), "el caso de Ntra. Sra. debe fallar por calle"
    assert valida(a, b), "y pasar por municipio: si no, el orden está invertido"

    assert municipio_en_direccion("C/ BAHIA 2 (BENALMANA)") == "BENALMANA"
    assert municipio_en_direccion("41013 Sevilla, España") == "Sevilla"
    assert municipio_en_direccion("C/ GUATEMALA 8") == ""

    print(f"OK places-por-direccion: {len(CASOS)} casos medidos, orden de capas correcto")


if __name__ == "__main__":
    main()
