#!/usr/bin/env python3
"""
Fase 5 — cierre: cobertura sobre DIRCE y captura-recaptura (Chao1).

Pregunta que responde: ¿cuántas empresas de software del ámbito se nos han
escapado? Sin esto el censo no tiene denominador y no se puede declarar nada.
"""
import csv, json, os
from collections import Counter

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIRCE = os.path.join(RAIZ, "data", "dirce_cnae62.csv")

# DIRCE cuenta LOCALES, no empresas (advertido por el agente de Fase 0).
# Factor locales/empresas medido con datos del propio INE: 1,17 Sevilla / 1,15 Málaga.
FACTOR_LOCALES = {"Sevilla": 1.17, "Málaga": 1.15}


def universo():
    """(total locales, total empresas estimadas) por provincia desde el DIRCE."""
    if not os.path.exists(DIRCE):
        raise SystemExit(f"Falta {DIRCE}")
    out = {}
    for r in csv.DictReader(open(DIRCE)):
        if r["tramo_asalariados"].strip().lower() == "total":
            out[r["provincia"]] = int(r["n_empresas"])
    return out


def chao1(fichas):
    """Estimador Chao1 sobre las fuentes que aportaron fichas.

    f1 = fuentes que aparecen en UNA sola ficha (raras)
    f2 = fuentes que aparecen en DOS fichas
    N  = fichas observadas
    S  = N + f1²/(2·f2)   → estimación del total existente
    """
    cuenta = Counter()
    for f in fichas:
        for fuente in {x["source"] for x in f.get("fuentes", [])}:
            cuenta[fuente] += 1
    f1 = sum(1 for n in cuenta.values() if n == 1)
    f2 = sum(1 for n in cuenta.values() if n == 2)
    n = len(fichas)
    if f2 == 0:
        return n, f1, f2, None
    return n, f1, f2, round(n + (f1 ** 2) / (2 * f2))


def main():
    fichas = json.load(open(os.path.join(RAIZ, "data", "empresas.json")))
    excl = json.load(open(os.path.join(RAIZ, "data", "excluidos.json")))
    uni = universo()

    print("=" * 64)
    print("FASE 5 — CIERRE")
    print("=" * 64)

    def norm(s):
        """Compara sin acentos ni mayúsculas: el dataset escribe 'Málaga', el DIRCE 'Málaga'."""
        return (s or "").lower().replace("á", "a").replace("é", "e").replace("í", "i")

    print("\n## Cobertura sobre DIRCE (CNAE 62, locales 2025)")
    print(f"{'provincia':10} {'censo':>6} {'locales':>8} {'empresas≈':>10} {'cobertura':>10}")
    tot_c = tot_l = 0
    for prov, locales in sorted(uni.items()):
        col = norm("malaga") if norm(prov).startswith("mal") else norm("sevilla")
        census = sum(1 for f in fichas if norm(f.get("ambito") or "").startswith(col[:4]))
        emp = round(locales / FACTOR_LOCALES.get(prov, 1.0))
        tot_c += census
        tot_l += locales
        print(f"{prov:10} {census:>6} {locales:>8} {emp:>10} {100*census/emp:>9.1f}%")
    tot_emp = round(sum(l / FACTOR_LOCALES.get(p, 1.0) for p, l in uni.items()))
    print(f"{'TOTAL':10} {tot_c:>6} {tot_l:>8} {tot_emp:>10} {100*tot_c/tot_emp:>9.1f}%")
    print("\n  ⚠ El censo NO está completo. La cobertura es la cota inferior real.")

    print("\n## Captura-recaptura (Chao1) sobre las fuentes de descubrimiento")
    n, f1, f2, est = chao1(fichas)
    print(f"  fichas observadas:            {n}")
    print(f"  fuentes raras (f1):           {f1}")
    print(f"  fuentes dobles (f2):          {f2}")
    if est:
        print(f"  estimación Chao1 de total:    {est}")
        print(f"  ⇒ quedan por descubrir:       ~{max(0, est - n)} ({100*max(0, est-n)/est:.0f}%)")
    else:
        print("  Chao1 no aplicable: ninguna fuente con f2 (todas raras o todas trucadas)")

    print("\n## Composición")
    print("  por provincia:", dict(Counter((f.get("ambito") or "?") for f in fichas)))
    print("  por actividad:", dict(Counter(f.get("criterio_actividad") for f in fichas)))
    print("  con web:      ", sum(1 for f in fichas if f.get("web")))
    print("  con teléfono: ", sum(1 for f in fichas if f.get("telefono")))
    print("  con coords:   ", sum(1 for f in fichas if f.get("lat")))
    print("  n fuentes>=2: ", sum(1 for f in fichas if f.get("n_fuentes_independientes", 0) >= 2))
    print(f"  excluidas:     {len(excl)}")
    print("  motivos:      ", dict(Counter(e["motivo_exclusion"] for e in excl)))

    print("\n## Fuentes que aportaron")
    for fuente, k in Counter(x["source"] for f in fichas for x in f.get("fuentes", [])).most_common():
        print(f"  {fuente:28} {k:>4}")

    # Informe persistente
    with open(os.path.join(RAIZ, "informes", "fase5_cierre.md"), "w") as fh:
        fh.write(f"# Fase 5 — Cierre\n\n")
        fh.write(f"- Fichas en el censo: **{n}**\n")
        fh.write(f"- Cobertura DIRCE: **{100*tot_c/tot_emp:.1f}%** ({tot_c} de ~{tot_emp} empresas estimadas)\n")
        fh.write(f"- Estimación Chao1: {est if est else 'no aplicable'}\n")
        fh.write(f"- Excluidas: {len(excl)}\n")
    print(f"\n  informe: informes/fase5_cierre.md")


if __name__ == "__main__":
    main()
