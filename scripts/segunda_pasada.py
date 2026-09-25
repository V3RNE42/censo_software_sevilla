"""Segunda pasada HTTP sobre las fichas SIN_DATOS sin ninguna senal.

Las 40-52 que quedan sin senal tienen nombres que Google no resuelve en la
consulta del censo ('GMV' -> sede central, 'Oracle' -> matriz). Este pase
prueba variantes: nombre corto, nombre + provincia, nombre con la razon social
recortada, y acepta solo resultados que pasan `maps_http._plausible`.

No usa navegador: si alguna requiere Chromium, se queda SIN_DATOS y se lista
aparte para decidir. 1-3 s por ficha.

Uso:  python3 scripts/segunda_pasada.py [--aplicar]
Sin --aplicar solo informa (dry-run).
"""
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fact_check_maps as fc      # noqa: E402
import maps_http                  # noqa: E402
from enriquecer_http import a_datos_veredicto   # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EMPRESAS = os.path.join(RAIZ, "data", "empresas.json")
OVERLAY = os.path.join(RAIZ, "data", "actividad_maps.json")

SUFIJOS = ("sl", "slu", "sa", "sau", "sll", "sc", "cb", "ltd", "sociedad",
           "limitada", "anonima", "unipersonal", "españa", "spain", "iberia")


def variantes(nombre, ciudad):
    """Candidatos de busqueda, del mas literal al mas laxo. Sin duplicados."""
    vistos, out = set(), []
    base = re.split(r"[|/]", nombre or "")[0].strip()

    def add(s):
        s = (s or "").strip(" .,-")
        if s and len(s) > 2 and s.lower() not in vistos:
            vistos.add(s.lower())
            out.append(s)

    add(f"{base} {ciudad}" if ciudad else base)
    add(base)
    # recortar sufijos societarios del final
    p = base.split()
    while p and p[-1].lower().strip(".,") in SUFIJOS:
        p.pop()
        add(" ".join(p))
    # primeras palabras (nombres compuestos largos)
    if len(p) > 3:
        add(" ".join(p[:3]))
        add(" ".join(p[:2]))
    return out


def ciudad_de(fila):
    for f in ("sevilla", "málaga", "malaga", "huelva", "cádiz", "cádiz"):
        if f in (fila.get("consulta_maps") or "").lower():
            return f.capitalize()
    return None


def main():
    aplicar = "--aplicar" in sys.argv
    fichas = {f["id"]: f for f in json.load(open(EMPRESAS, encoding="utf-8"))}
    filas = json.load(open(OVERLAY, encoding="utf-8"))

    sin = [x for x in filas if x["veredicto"] == "SIN_DATOS"
           and not any(x.get(k) for k in
                       ("nombre_en_maps", "place_id", "web_maps",
                        "telefono_maps", "rating", "dias_ultima_resena"))]
    print(f"sin senal: {len(sin)}", flush=True)

    recuperadas, siguen = [], []
    for i, fila in enumerate(sin, 1):
        f = fichas.get(fila["id"], {})
        ciudad = ciudad_de(fila)
        hit = None
        for cand in variantes(f.get("nombre") or fila["consulta_maps"], ciudad):
            t0 = time.time()
            h = maps_http.extrae(cand, intentos=1)
            if not maps_http._vacio(h) and maps_http._plausible(h, cand):
                hit = (h, cand)
                break
            time.sleep(0.3)
        if hit:
            h, cand = hit
            ver, razones = fc.veredicto(f, a_datos_veredicto(h, fila))
            recuperadas.append((fila, h, cand, ver, razones))
            if aplicar:
                fila["veredicto"] = ver
                fila["razones"] = razones + [f"2a pasada HTTP via '{cand}'"]
                for k, v in (("telefono_maps", h.get("telefono")),
                             ("web_maps", h.get("web")),
                             ("rating", h.get("rating")),
                             ("maps_total", h.get("n_resenas")),
                             ("place_id", h.get("place_id"))):
                    if v is not None:
                        fila[k] = v
            print(f"[{i}/{len(sin)}] HIT  {fila['id']:>10} {(f.get('nombre') or '')[:30]:<30} "
                  f"via '{cand}' tel={h.get('telefono')}", flush=True)
        else:
            siguen.append(fila)
            print(f"[{i}/{len(sin)}] ---- {fila['id']:>10} {(f.get('nombre') or '')[:30]:<30}",
                  flush=True)
        if aplicar and i % 10 == 0:
            json.dump(filas, open(OVERLAY, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1)

    if aplicar:
        json.dump(filas, open(OVERLAY, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)

    from collections import Counter
    print(f"\nrecuperadas: {len(recuperadas)}  siguen sin senal: {len(siguen)}")
    print("veredictos nuevos:", Counter(v for *_, v, _ in recuperadas))
    print("quedan sin senal:", [x["id"] for x in siguen])
    if not aplicar:
        print("\n(dry-run: nada escrito. Repetir con --aplicar)")


if __name__ == "__main__":
    main()
