#!/usr/bin/env python3
"""Rellena el CP que falta consultando la DIRECCIÓN a Places.

Por qué existe: BORME da la calle en el objeto social ('Domicilio: C/ GUATEMALA
8') pero NO el CP en muchos casos, y `etiqueta()` no imprime sin CP. Medido: 13
de las 24 fichas que reportó el usuario caían por esto, no por estar mal.

Usa el endpoint /maps/api/place/findplacefromtext con inputtype=textquery y
fields=address_components: es el barato (no devuelve reviews). El CP sale de
components[].postal_code, que es el dato del sobre — más fiable que rascar la
dirección formateada.

NO escribe si el CP que encuentra contradice la provincia de la ficha: eso
significa que la dirección estaba mal, no que faltara el CP.
"""
import json, os, re, sys, time, urllib.parse, urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EMPRESAS = os.path.join(RAIZ, "data", "empresas.json")
CACHE = os.path.join(RAIZ, "data", "cp_por_direccion.json")
ENV = os.path.expanduser("~/.hermes/.env")
LATENCIA = 0.25

sys.path.insert(0, os.path.join(RAIZ, "scripts"))
from etiquetas import etiqueta, CP_RE          # noqa: E402
from collectors._common import _escribe_dataset  # noqa: E402


def clave(f):
    """Estado frente a la API. Solo se paga por lo que aún no se sabe."""
    return (f["nombre"] + "|" + (f.get("direccion") or "")).lower()


def api_key():
    for ln in open(ENV, encoding="utf-8"):
        if ln.startswith("GOOGLE_MAPS_API_KEY"):
            return ln.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("GOOGLE_MAPS_API_KEY no está en ~/.hermes/.env")


def cp_de(consulta, key):
    """CP de una consulta de texto libre. None si no hay o si falla.

    `fields` en findplacefromtext solo admite una lista corta: pedir
    address_components da INVALID_REQUEST (medido, 22/22 llamadas quemadas).
    formatted_address es lo barato que si lo trae ('C. Guatemala, 8, 41840
    Pilas, Sevilla') y ademas devuelve la calle canonica de Places.
    """
    q = urllib.parse.urlencode({"input": consulta, "inputtype": "textquery",
                                "fields": "formatted_address",
                                "key": key, "language": "es"})
    url = f"https://maps.googleapis.com/maps/api/place/findplacefromtext/json?{q}"
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            d = json.load(r)
    except Exception as e:
        return None, None, f"HTTP {e}"
    if d.get("status") != "OK" or not d.get("candidates"):
        return None, None, d.get("status", "?")
    fa = d["candidates"][0].get("formatted_address") or ""
    m = re.search(r"\b(\d{5})\b", fa)
    return (m.group(1) if m else None), fa, "OK"


VACIO = {"calle", "c", "avda", "avenida", "av", "plaza", "pl", "paseo", "pº",
         "ctra", "carretera", "camino", "cmno", "poligono", "pol", "urbanizacion"}


def calle_coincide(preguntada, devuelta):
    """¿La calle que devuelve Places es la que se preguntó?

    Places responde con la calle más parecida en vez de ZERO_RESULTS, así que hay
    que confirmarlo. Se compara la primera palabra significativa (saltando el tipo
    de vía y las abreviaturas de Places: 'Ntra. Sra.' vs 'Nuestra Señora' no
    coincide literalmente, pero el número y el municipio sí validan el resto).
    """
    def via(s):
        import unicodedata
        s = unicodedata.normalize("NFD", str(s or "").lower())
        s = "".join(c for c in s if unicodedata.category(c) != "Mn")
        for w in re.findall(r"[a-zñ]+", s):
            if w not in VACIO and len(w) > 2:
                return w
        return ""
    a, b = via(preguntada), via(devuelta)
    return bool(a) and (a == b or a.startswith(b) or b.startswith(a))


def coincide(a, b):
    """Contención de cadenas sin tildes ni puntuación, con abreviaturas expandidas.

    'Almonte' ⊂ 'Polígono Industrial el Tomillar, nave 6, 21730 Almonte, Huelva'.
    El sentido es el que importa: un municipio es una cadena CORTA que debe
    aparecer en la larga. Al revés ('C/' ⊂ todo) compara basura.
    """
    import unicodedata
    def nz(s):
        s = unicodedata.normalize("NFD", str(s or "").lower())
        s = "".join(c for c in s if unicodedata.category(c) != "Mn")
        return re.sub(r"[^a-z0-9]+", " ", s).strip()
    a, b = nz(a), nz(b)
    return bool(a) and bool(b) and (a in b or b in a)


def municipio_en_direccion(dire):
    """Municipio escrito en la dirección: el paréntesis de BORME o lo que sigue al CP.

    'C/ BAHIA 2 4 1 (BENALMANA)' y '41013 Sevilla, España'. Es el mismo caso que el
    domicilio del objeto_social: el dato está, sin parsear. Sin esto, la validación
    de la pasada de Places solo ve la provincia, y 'C/ BAHIA 2' colaba con el CP de
    otra calle de Málaga capital.
    """
    m = re.search(r"\(([^)]+)\)", dire or "")
    if m:
        return m.group(1).strip()
    m = re.search(r"\b\d{5}\s+([^,]+)", dire or "")
    return m.group(1).strip() if m else ""


def main():
    fichas = json.load(open(EMPRESAS, encoding="utf-8"))
    cache = json.load(open(CACHE, encoding="utf-8")) if os.path.exists(CACHE) else {}
    key = api_key()

    # Ladder rung 1: solo las que fallan por CP. El resto ya imprime.
    objetivo = [f for f in fichas
                if not etiqueta(f) and (f.get("direccion") or "").strip()
                and not f.get("cp")]
    print(f"fichas sin CP candidatas: {len(objetivo)}")

    nuevas = consultas = 0
    descartes = []
    for f in objetivo:
        k = clave(f)
        if k not in cache:
            mun = f.get("municipio") or (f.get("provincia") or "")
            consulta = f"{f['direccion']}, {mun}".strip(", ")
            cp, fa, estado = cp_de(consulta, key)
            cache[k] = {"cp": cp, "estado": estado, "consulta": consulta,
                        "formatted_address": fa}
            consultas += 1
            time.sleep(LATENCIA)
        got = cache[k].get("cp")
        if not got:
            descartes.append((f["nombre"], cache[k].get("estado")))
            continue
        # Validación final. Dos capas, en este orden (el orden importa):
        #  1. prefijo de CP en la provincia de la ficha -> pilla Madrid/Barcelona.
        #  2. MUNICIPIO: si la dirección dice en qué pueblo está ('(MARBELLA)', el
        #     paréntesis de BORME), Places tiene que haber devuelto ese municipio.
        #     Esta capa sola pilla los tres falsos positivos medidos: 'C/ BAHIA 2
        #     (BENALMANA)' contestado con 'C. Hamlet, 5, Málaga', 'PLAZA GOYA 3
        #     (TORREMOLINOS)' con 'Calle Goya, 3, Málaga' (mismo nombre de calle) y
        #     'AVDA CONDE DE ORGAZ 49' (Madrid) con 'C. Cuarteles, 49, Málaga'.
        #  3. Solo si NO hay municipio en la dirección, se compara la calle.
        #     Comparar la calle cuando ya tienes el municipio RECHAZA DATOS BUENOS:
        #     'Nuestra Señora' vs 'Ntra. Sra.' (la abreviatura de Places) daba falso
        #     negativo y tiraba el CP correcto de Dorai Labs.
        # Lo que no pase las capas no se escribe: un CP inventado imprime un sobre
        # que no llega, y eso es peor que no imprimirlo.
        prefijo = {"SEVILLA": "41", "MALAGA": "29", "HUELVA": "21"}.get(f.get("ambito"))
        if prefijo and not got.startswith(prefijo):
            descartes.append((f["nombre"], f"CP {got} fuera de {f.get('ambito')}"))
            continue
        dev = cache[k].get("formatted_address") or ""
        mun_dir = municipio_en_direccion(f.get("direccion") or "")
        if mun_dir:
            if not coincide(mun_dir, dev):
                descartes.append((f["nombre"], f"{mun_dir} != {dev}"))
                continue
        elif not calle_coincide(f.get("direccion") or "", dev):
            descartes.append((f["nombre"], f"calle distinta: {dev}"))
            continue
        f["cp"] = got
        f.setdefault("flags", []).append("CP_DESDE_DIRECCION")
        nuevas += 1

    json.dump(cache, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    _escribe_dataset(EMPRESAS, fichas)
    print(f"llamadas a la API: {consultas} | CP rellenados: {nuevas}")
    for n, m in descartes:
        print(f"  sin CP: {n[:38]:38} {m}")
    print(f"etiquetas ahora: {sum(1 for f in fichas if etiqueta(f))}")


if __name__ == "__main__":
    main()
