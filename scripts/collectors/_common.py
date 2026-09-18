"""Helper compartido por collectors. Stdlib solo."""
import json, os, time, urllib.request, urllib.error

UA = "censo-software-sevilla/1.0 (julio@cabanillas.dev)"
RAW = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "raw")


def get(url, headers=None, timeout=30, intentos=3):
    """GET con backoff. Devuelve (status, body_text). No lanza: reporta."""
    h = {"User-Agent": UA}
    if headers:
        h.update(headers)
    for i in range(intentos):
        try:
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, r.read().decode("utf-8", "ignore")
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and i < intentos - 1:
                time.sleep(2 ** i)
                continue
            return e.code, ""
        except Exception:
            if i < intentos - 1:
                time.sleep(2 ** i)
                continue
            return 0, ""
    return 0, ""


def key():
    k = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not k:
        raise SystemExit("Falta GOOGLE_MAPS_API_KEY. Cargar con: set -a; . /root/.hermes/.env; set +a")
    return k


def fichas(rows, fuente, provincia, fecha):
    """Normaliza y valida el contrato de AGENTE_TEMPLATE.md."""
    salida = []
    for r in rows:
        if not r.get("nombre") or not r.get("evidencia_url"):
            continue                      # REGLA DURA: sin evidencia no hay ficha
        salida.append({
            "nombre": r["nombre"].strip(),
            "municipio": r.get("municipio"),
            "provincia": provincia,
            "direccion": r.get("direccion"),
            "web": r.get("web"),
            "telefono": r.get("telefono"),
            "email": r.get("email"),
            "cif": r.get("cif"),
            "tipologias": r.get("tipologias", []),
            "empleados_rango": r.get("empleados_rango"),
            "lat": None, "lng": None,     # los rellena verificar_places.py
            "evidencia_url": r["evidencia_url"],
            "fuente": fuente,
            "fecha_captura": fecha,
            "notas": r.get("notas"),
        })
    return salida


def escribe(salida, fuente, provincia, fecha):
    os.makedirs(RAW, exist_ok=True)
    ruta = os.path.join(RAW, f"{fuente.lower()}_{provincia.lower()}_{fecha}.jsonl")
    with open(ruta, "w") as f:
        for s in salida:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    print(f"fuente: {fuente}\nprovincia: {provincia}\nfichas_escritas: {len(salida)}\n"
          f"con_web: {sum(1 for s in salida if s['web'])}\nruta: {ruta}")
