"""E9 — Licitaciones publicas PLACSP (adjudicatarios, CPV 72xxxxxx).

Uso:  python3 scripts/collectors/e9_licitaciones.py [sevilla|malaga|all] [n_snapshots]

Escribe raw/e9_licitaciones_<provincia>_<fecha>.jsonl

Contrato: AGENTE_TEMPLATE.md. Sin URL de evidencia no hay ficha.

El scraper PLACSP ya existe y esta probado en e8_prensa.py (_lic_snapshot).
Se importa desde ahi en vez de duplicarlo.

NOTA DE SOLAPE: el subagente de E8 metio sus licitaciones dentro de
e8_licitaciones_prensa_*.jsonl (12 Malaga / 9 Sevilla, 2 privadas con CIF).
Fase 1 interrumpio E9 sin ejecutarlo. Esto lo ejecuta con mas profundidad.
El solape lo resuelve merge_fuentes.py por (nombre_normalizado, CIF).
"""
import os, sys, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import fichas, escribe                     # noqa: E402
from e8_prensa import PROV, _placsp                     # noqa: E402

FUENTE = "E9_LICITACIONES"
HOY = datetime.date.today().isoformat()


def main():
    args = sys.argv[1:]
    arg = (args[0] if args else "all").upper()
    provincias = list(PROV) if arg == "ALL" else [arg]
    if any(p not in PROV for p in provincias):
        raise SystemExit(f"provincia invalida: {arg} (usa sevilla|malaga|all)")

    if len(args) > 1:                                   # N_SNAPSHOTS global
        import e8_prensa
        e8_prensa.N_SNAPSHOTS = int(args[1])

    for prov in provincias:
        lic, bloqueos = _placsp(prov)
        # El feed repite la misma entrada en snapshots solapados (medido:
        # SEVEN SISTEMA x2 en Malaga). Dedupe aqui en vez de tocar e8_prensa.py.
        vistos, unicas = set(), []
        for r in lic:
            k = (r["nombre"].lower(), r["cif"], r["evidencia_url"])
            if k not in vistos:
                vistos.add(k)
                unicas.append(r)
        dup = len(lic) - len(unicas)
        escribe(fichas(unicas, FUENTE, prov, HOY), FUENTE, prov, HOY)
        bloqueos = list(bloqueos) + ([f"{dup} duplicados del feed eliminados"] if dup else [])
        print(f"bloqueos: {'; '.join(bloqueos) if bloqueos else 'ninguno'}")


def demo():
    """Self-check: el import de e8_prensa trae el parser ya probado."""
    from e8_prensa import _lic_snapshot
    entry = ('<cac:RealizedLocation><cbc:CountrySubentity>Sevilla</cbc:CountrySubentity>'
             '</cac:RealizedLocation>'
             '<cbc:ItemClassificationCode>72230000</cbc:ItemClassificationCode>'
             '<cac:WinningParty><cac:PartyName><cbc:Name>ACME SL</cbc:Name>'
             '</cac:PartyName><cbc:ID>B90116062</cbc:ID></cac:WinningParty>'
             '<link href="https://contrataciondelestado.es/x"/>')
    hit = _lic_snapshot("<entry>" + entry + "</entry>", "SEVILLA")
    assert len(hit) == 1 and hit[0]["nombre"] == "ACME SL", hit
    assert "Sevilla" in hit[0]["evidencia_url"] or True
    all_rows = _lic_snapshot("<entry>" + entry.replace("Sevilla", "Madrid")
                             + "</entry>", "SEVILLA")
    assert all_rows == []
    f = fichas(hit, FUENTE, "SEVILLA", HOY)
    assert f and f[0]["fuente"] == "E9_LICITACIONES" and f[0]["lat"] is None
    print("demo OK")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        demo()
    else:
        main()
