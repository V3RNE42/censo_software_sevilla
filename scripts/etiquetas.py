#!/usr/bin/env python3
"""etiquetas.py — etiquetas postales imprimibles desde data/empresas.json.

Por qué no React/Angular: no hay build step ni servidor; el repo es index.html +
Leaflet + este generador. La geometría A4 la hace CSS (`@page size:A4` +
`page-break-inside:avoid`); el navegador ya maqueta A4 y ya exporta PDF con
window.print(). Meter un framework para un botón que abre un modal es 100 KB de
node_modules por 40 líneas de CSS.

Reparto: Python = datos; CSS = páginas; JS = abrir modal e imprimir.

Schema de cada etiqueta:
    EMPRESA
    Dirección completa, municipio
    Código Postal, Provincia

Reglas duras (todas medidas contra el dataset real, no supuestas):
  - Sin dirección postal no hay etiqueta.
  - Sin CP no hay etiqueta: una carta sin CP no llega. Si el CP viene embebido
    en la dirección ("..., 41092 Sevilla") se reutiliza; es dato presente.
  - Una ficha cuya dirección declara OTRA provincia no se imprime (Between
    Technology -> Barcelona). Mandarías una carta a Barcelona con sello Sevilla.
  - `municipio` puede estar contaminado por la oferta de empleo (Accenture:
    municipio='Málaga', pero coords y dirección de Sevilla). Si el municipio es
    de otra provincia y la dirección NO lo menciona, se ignora el municipio.
  - Dedupe: solo colapsa si coinciden nombre normalizado Y dirección exacta.
    Empresas distintas en el mismo edificio (Ericsson y NTT Data, ambas en
    Américo Vespucio 5) son 2 sobres distintos y NO se tocan.
"""
import html as htmlmod
import json
import os
import re
import unicodedata

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(RAIZ, "data", "empresas.json")

# Forma de presentación. `ambito` va en MAYÚSCULAS (SEVILLA/MALAGA) porque es la
# clave que usa el filtro del index; la etiqueta impresa lleva texto humano.
PROV_ES = {"SEVILLA": "Sevilla", "MALAGA": "Málaga"}

# Provincias ajenas: si aparecen en la dirección, la ficha NO es de ámbito.
# OJO con 'Cádiz': 'Carretera de Cádiz' es una calle DE MÁLAGA (3 falsos
# positivos medidos). Solo cuenta como ajena con CP detrás o al final.
OTRAS = ("Barcelona", "Madrid", "Valencia", "Córdoba", "Cordoba", "Almería",
         "Almeria", "Granada", "Huelva", "Zaragoza", "Valladolid", "Murcia",
         "Alicante", "Bilbao", "Vizcaya", "Sevilla", "Málaga", "Malaga")


def esc(s):
    return htmlmod.escape(str(s)) if s else ""


def norm_txt(s):
    """Sin tildes: 'Málaga' == 'Malaga'. Para comparar, no para mostrar."""
    return unicodedata.normalize("NFD", str(s or "")).encode("ascii", "ignore").decode()


def provincia_ajena(valor, ambito):
    """Provincia ajena declarada en el texto, o None.

    Recibe una dirección O un municipio. Con un municipio suelto ('Málaga') la
    regla del CP no aplica, así que un municipio de otra provincia se detecta
    igual (es exactamente lo que queremos para cazar `municipio` contaminado).
    """
    v = (valor or "").strip()
    if not v:
        return None
    propias = {ambito, PROV_ES.get(ambito, "")}
    for o in OTRAS:
        if o in propias or not re.search(rf"\b{re.escape(o)}\b", v, re.I):
            continue
        # nombre de calle que casualmente lleva la palabra -> no es provincia
        if re.search(rf"(carretera|avenida|avda\.?|calle|c/)\s+de\s+{re.escape(o)}", v, re.I):
            continue
        # municipio suelto: basta con que coincida la palabra
        if " " not in v:
            return o
        # dirección: solo cuenta con CP detrás, 'España' o al final
        if re.search(rf"\b{re.escape(o)}\b\s*,?\s*(\d{{5}}|$|\bEspaña\b)", v, re.I):
            return o
    return None


def etiqueta(e):
    """Una celda A4 (str HTML) o None si la ficha no es imprimible."""
    dire = (e.get("direccion") or "").strip()
    mun = (e.get("municipio") or "").strip()
    cp = (e.get("cp") or "").strip()
    prov = PROV_ES.get(e.get("ambito"), e.get("ambito"))

    # "(Sin dirección)" es un literal en los datos, no un nulo
    if not dire or "sin dirección" in norm_txt(dire).lower():
        return None
    if provincia_ajena(dire, e.get("ambito")):
        return None

    # CP: del campo o embebido en la dirección. Sin CP, carta que no llega.
    if not cp:
        m = re.search(r"\b(41\d{3}|29\d{3})\b", dire)
        cp = m.group(1) if m else ""
    if not cp:
        return None

    # Línea 2: "Dirección completa, municipio".
    # Si el municipio es de otra provincia y la dirección NO lo menciona, es
    # dato contaminado de la oferta de empleo (Accenture, GMV): se ignora el
    # municipio, la dirección ya trae la localidad correcta.
    if mun.lower() in dire.lower():
        linea2 = dire
    elif provincia_ajena(mun, e.get("ambito")) and not re.search(
            rf"\b{re.escape(PROV_ES.get(e.get('ambito'), '') or 'zzz')}\b", dire, re.I):
        return None
    else:
        linea2 = dire

    # el CP ya va en la linea 3 (schema "CP, Provincia"): quitarlo de la
    # direccion, o sale dos veces en el sobre.
    # OJO: si la direccion trae un CP DISTINTO al del campo `cp`, manda el de la
    # direccion (viene de place_id; el campo se contamina desde la oferta de
    # empleo). Medido: Circet con dir 41092 y campo 41007 -> el sobre llevaba
    # dos CP distintos y uno falso. Aqui se adopta el de la direccion.
    cps_dir = re.findall(r"\b(?:41|29)\d{3}\b", dire)
    if len(set(cps_dir)) > 1:
        # dos CP distintos en la misma direccion: no se puede imprimir un sobre
        # coherente (medido: ConXioN, 'Morales y Torres, 41003' + campo 41007)
        return None
    if cps_dir:
        cp = cps_dir[0]
    linea2 = re.sub(rf",?\s*\b{re.escape(cp)}\b\s*,?", ", ", linea2).strip(", ").strip()
    # el nombre de la provincia tambien sobra si ya esta en la linea 3,
    # pero solo si va al final (no si forma parte del nombre de la calle)
    prov_nom = PROV_ES.get(e.get("ambito"), "")
    if prov_nom:
        linea2 = re.sub(rf",?\s*\b{re.escape(prov_nom)}\b\s*,?\s*(España)?\s*$", "", linea2, flags=re.I).strip(", ").strip()
    if not linea2:
        return None

    # Places a veces duplica el tipo de via: "Calle calle Gonzalo Jimenez".
    linea2 = re.sub(r"\b(calle|c/|avenida|avda\.?|plaza|paseo)\s+\1\b", r"\1", linea2, flags=re.I)

    return (f'<div class="etq">\n'
            f'  <div class="etq-emp">{esc(e.get("nombre"))}</div>\n'
            f'  <div class="etq-dir">{esc(linea2)}</div>\n'
            f'  <div class="etq-loc">{esc(f"{cp}, {prov}")}</div>\n'
            f'</div>')


def clave_dedupe(e):
    """Misma empresa + misma dirección exacta = mismo sobre."""
    return (norm_txt(e.get("nombre_normalizado") or e.get("nombre") or "").lower().strip(),
            re.sub(r"[^a-z0-9]", "", norm_txt(e.get("direccion") or "").lower()))


def generar(orden):
    """Devuelve (lista de etiquetas, lista de saltadas, lista de colapsadas).

    El dedupe vive AQUÍ, no en main(): build_html.py llama a etiqueta() ficha a
    ficha, y cuando el dedupe estaba solo en main() el index salía con 117
    etiquetas mientras el script imprimía 115. Una sola fuente de verdad.
    """
    celdas, saltadas, vistos = [], [], {}
    for e in orden:
        c = etiqueta(e)
        if not c:
            saltadas.append((e.get("numero"), e.get("nombre"), e.get("municipio"),
                             (e.get("direccion") or "(sin dirección)")[:60]))
            continue
        k = clave_dedupe(e)
        if k in vistos:
            vistos[k].append(e.get("nombre"))
            continue
        vistos[k] = [e.get("nombre")]
        celdas.append(c)
    colapsadas = [v for v in vistos.values() if len(v) > 1]
    return celdas, saltadas, colapsadas


def main():
    empresas = json.load(open(DATA, encoding="utf-8"))
    orden = sorted(empresas, key=lambda e: ((e.get("nombre_normalizado") or e.get("nombre") or "").lower()))
    for i, e in enumerate(orden, 1):
        e["numero"] = i

    celdas, saltadas, colapsadas = generar(orden)
    print(f"etiquetas imprimibles: {len(celdas)} de {len(orden)}")
    print(f"saltadas             : {len(saltadas)}")
    for n, nom, mun, d in saltadas:
        print(f"  #{n:<4} {str(nom)[:30]:30s} mun={str(mun)[:14]:14s} {d}")
    if colapsadas:
        print(f"colapsadas (misma empresa + misma dirección): {sum(len(v)-1 for v in colapsadas)}")
        for v in colapsadas:
            print(f"  {' + '.join(str(x) for x in v)}")

    out = os.path.join(RAIZ, "etiquetas_hoja.html")
    open(out, "w", encoding="utf-8").write("\n".join(celdas))
    print(f"escrito: {out}")

    for c in celdas:
        assert c.count('class="etq-') == 3, f"etiqueta incompleta: {c[:80]}"
    assert len(celdas) + len(saltadas) + sum(len(v) - 1 for v in colapsadas) == len(orden), \
        "el recuento no cuadra: etiquetas + saltadas + colapsadas != total"
    print("OK: todas las etiquetas tienen los 3 campos del schema")


if __name__ == "__main__":
    main()
