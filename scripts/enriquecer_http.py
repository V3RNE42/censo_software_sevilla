"""Enriquece las fichas SIN_DATOS del fact-check usando maps_http.

Las SIN_DATOS son las que el scraper de navegador no pudo leer (vista limitada
de Google: 'Sign in' + 'limited view'). El endpoint HTTP no sufre ese muro y
recupera telefono, web, rating y volumen para una parte de ellas.

Lee  data/actividad_maps.json   (overlay del fact-check con navegador)
Escribe data/actividad_maps.json  (in situ: veredicto recalculado)
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fact_check_maps as fc          # noqa: E402  (el veredicto es el suyo)
import maps_http                       # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EMPRESAS = os.path.join(RAIZ, "data", "empresas.json")
SALIDA = os.path.join(RAIZ, "data", "actividad_maps.json")


def a_datos_veredicto(h, fila):
    """Traduce la salida de maps_http al dict que espera fc.veredicto()."""
    return {
        "nombre_en_maps": h.get("nombre_en_maps"),
        "pid": h.get("place_id"),
        "total": h.get("n_resenas"),
        "tel": h.get("telefono"),
        "web": h.get("web"),
        "cat": (h.get("categorias") or [None])[0],
        "reviews": [],                # el HTTP no da fechas: sin reseñas datables
        "error": h.get("error"),
        "cerrado_permanente": False,
        "no_encontrado": not h.get("nombre_en_maps"),
    }


def main():
    solo = "--only" in sys.argv
    fichas = {f["id"]: f for f in json.load(open(EMPRESAS, encoding="utf-8"))}
    filas = json.load(open(SALIDA, encoding="utf-8"))
    objetivo = [x for x in filas if x["veredicto"] == "SIN_DATOS"]
    print(f"SIN_DATOS a enriquecer: {len(objetivo)}", flush=True)

    mejoras = {}
    for i, fila in enumerate(objetivo, 1):
        f = fichas.get(fila["id"])
        if not f:
            continue
        t0 = time.time()
        h = maps_http.extrae(fila["consulta_maps"], intentos=2)
        ver, razones = fc.veredicto(f, a_datos_veredicto(h, fila))
        if ver != "SIN_DATOS":
            mejoras[fila["id"]] = (ver, razones, h)
            fila["veredicto"] = ver
            fila["razones"] = razones + ["recuperado por maps_http (sin navegador)"]
            for k, v in (("telefono_maps", h.get("telefono")),
                         ("web_maps", h.get("web")),
                         ("rating", h.get("rating")),
                         ("maps_total", h.get("n_resenas")),
                         ("place_id", h.get("place_id"))):
                if v is not None:
                    fila[k] = v
        print(f"[{i}/{len(objetivo)}] {fila['id']:>10} {fila['veredicto']:<13} "
              f"{(f.get('nombre') or '')[:32]:<32} {time.time()-t0:5.2f}s", flush=True)
        if i % 10 == 0:
            json.dump(filas, open(SALIDA, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1)
    json.dump(filas, open(SALIDA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    from collections import Counter
    print("\nrecuperadas:", len(mejoras))
    print(Counter(v for v, _, _ in mejoras.values()))
    print("total overlay:", Counter(x["veredicto"] for x in filas))


if __name__ == "__main__":
    main()
