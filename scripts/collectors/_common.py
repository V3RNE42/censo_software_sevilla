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


def escribe(salida, fuente, provincia, fecha, aviso_pisar=False):
    """Escribe el raw. NO pisa en silencio un fichero del mismo día.

    Medido: ejecutar e2_empleo.py con otra lista de --fuentes sobreescribió el raw
    bueno de Sevilla/Málaga con uno de 329 ofertas remotas, y el merge duplicó E2
    (130 -> 592 fichas). Un collector puede correr dos veces; el fichero del día
    solo se pisa con intención explícita.
    """
    os.makedirs(RAW, exist_ok=True)
    ruta = os.path.join(RAW, f"{fuente.lower()}_{provincia.lower()}_{fecha}.jsonl")
    if os.path.exists(ruta) and not aviso_pisar:
        previas = sum(1 for _ in open(ruta, encoding="utf-8"))
        raise SystemExit(
            f"ABORTA: {ruta} ya existe ({previas} fichas) y no se pisa sin --pisar.\n"
            f"  Si es una re-ejecución legítima: añade --pisar al comando.\n"
            f"  Si es otro juego de fuentes: usa otro nombre de FUENTE."
        )
    with open(ruta, "w") as f:
        for s in salida:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    print(f"fuente: {fuente}\nprovincia: {provincia}\nfichas_escritas: {len(salida)}\n"
          f"con_web: {sum(1 for s in salida if s['web'])}\nruta: {ruta}")


# ---------------------------------------------------------------- dataset final
# ÚNICA vía de escritura de data/empresas.json. Antes cada fase hacía su propio
# json.dump y el resultado divergió: 571 entradas de cache pero solo 431 fichas,
# `lat` poblada con coordenadas de otra provincia, `cp` a medias... Un solo
# escritor con los invariantes en un assert hace imposible volver a ese estado.

def _coord_en_ambito(ficha, ambito_de, amb):
    """¿Su coordenada cae de verdad en la provincia de la ficha?

    Es la excepción de las multi-sede: CP de otra provincia + coord en el ámbito
    = sede múltiple, ficha válida.
    """
    prov, coord, _ = ambito_de(ficha.get("lat"), ficha.get("lng"),
                               ficha.get("cp"), ficha.get("provincia"))
    return bool(coord) and _ambito_key_upper(prov) == amb


def _ambito_key_upper(valor):
    import unicodedata
    s = unicodedata.normalize("NFD", str(valor or "").upper())
    return "".join(c for c in s if unicodedata.category(c) != "Mn").strip()


def _escribe_dataset(ruta, fichas, backup=True, validar=True):
    """Escribe el dataset validando los invariantes. Aborta (no escribe) si falla.

    `validar=False` para data/excluidos.json: sus invariantes son DISTINTOS por
    diseño — es la lista de fichas fuera de ámbito, así que exigirle "dentro del
    ámbito" abortaba con 497 errores. Los invariantes de ámbito solo valen para el
    censo.

    Import perezoso de build_provincias: vive en scripts/, no en collectors/.
    """
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from build_provincias import ambito_de, _ambito_key, CP_PROV

    if not validar:
        with open(ruta, "w", encoding="utf-8") as fh:
            json.dump(fichas, fh, ensure_ascii=False, indent=1)
        return len(fichas)

    malas = []
    for f in fichas:
        prov, coord, conflicto = ambito_de(f.get("lat"), f.get("lng"),
                                           f.get("cp"), f.get("provincia"))
        amb = _ambito_key(f.get("ambito"))
        if not prov:
            malas.append((f.get("nombre"), "fuera de ámbito pero está en el dataset"))
            continue
        if amb != _ambito_key(prov):
            malas.append((f.get("nombre"), f"ambito={amb} pero su CP/coord dice {prov}"))
        if f.get("lat") and not coord:
            malas.append((f.get("nombre"), "coord de otra provincia (homónimo)"))
        cp = (f.get("cp") or "").strip()
        # CP de otra provincia: NO es incoherencia si la coordenada cae en el
        # ámbito — la empresa tiene varias sedes y la fuente pegó la dirección de
        # la otra (Between Technology, dir. Barcelona 08018 desde
        # sevillatechpark.es, coord en la Cartuja). La ficha es válida; no se
        # imprimirá el sobre con ese CP. Misma excepción que verificar_coherencia.
        if (cp and CP_PROV.get(amb) and not cp.startswith(CP_PROV[amb])
                and not _coord_en_ambito(f, ambito_de, amb)):
            malas.append((f.get("nombre"), f"cp={cp} no es de {amb}"))
    if malas:
        raise SystemExit(
            "ABORTA: el dataset no es coherente (no se escribe nada):\n  "
            + "\n  ".join(f"{n}: {m}" for n, m in malas[:20])
            + (f"\n  ... y {len(malas)-20} más" if len(malas) > 20 else "")
        )
    if backup and os.path.exists(ruta):
        import shutil
        shutil.copy2(ruta, ruta + ".bak")     # una generación: volver atrás es un cp
    with open(ruta, "w", encoding="utf-8") as fh:
        json.dump(fichas, fh, ensure_ascii=False, indent=1)
    return len(fichas)
