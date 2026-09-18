#!/usr/bin/env python3
"""Fase 2 — fusion y deduplicacion de raw/*.jsonl en data/empresas.json.

Reejecutable: borra y reescribe la salida. No toca raw/.

Reglas de dedupe (PLAN §6 Fase 2):
  - igual nombre_normalizado + igual municipio_resuelto -> misma empresa, fusión
  - nombre_normalizado casi igual (fuzzy) -> NO se fusiona, flag DUPLICADO_POSIBLE
  - igual coords ±50 m -> no aplica todavía (lat/lng son null en Fase 1,
    los rellena verificar_places.py). `fusionar_coords()` queda listo y se
    invocará cuando ese paso exista.

Uso:  python3 scripts/merge_fuentes.py
"""
import html
import json
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from difflib import SequenceMatcher

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(RAIZ, "raw")
DATA = os.path.join(RAIZ, "data")
INFORMES = os.path.join(RAIZ, "informes")
SALIDA = os.path.join(DATA, "empresas.json")

# DIRCE 2025 (INE, operación DIR): locales CNAE 62 por provincia
DIRCE = {"SEVILLA": 1298, "MALAGA": 2195}

# Municipio centinela para ofertas de empleo sin ubicación: NO es un municipio
# real y no debe anclar la deduplicación (ver informe de fusión §"cambios de criterio").
SIN_MUNICIPIO = None

SUFIJOS = [
    "sociedad limitada nueva empresa", "sociedad limitada unipersonal",
    "sociedad anonima unipersonal", "sociedad limitada", "sociedad anonima",
    "sociedad cooperativa", "comunidad de bienes",
    "s l u", "s l n e", "s a u", "s l", "s a", "s c", "s coop", "sl", "sa",
]
# ponytail: lista plana, no parser societario. Añadir aquí cuando aparezca un sufijo nuevo.
FORMA_JURIDICA = re.compile(
    r"\b(?:sociedad limitada|sociedad anonima|sociedad unipersonal|sociedad cooperativa|"
    r"s l u|s l n e|s l|s a u|s a|slu|sln|sl|sa)\b")
VACIO = re.compile(r"\b(?:desconocid\w*|sin municipio|varios|y otras|espana|nacional|remoto)\b")
# etiqueta humana canonica (el valor normalizado ya es la clave)
ETIQUETA = {"malaga": "Málaga", "sevilla": "Sevilla", "marbella": "Marbella"}


def sin_acentos(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s)
                   if not unicodedata.combining(c))


def norm_municipio(mun):
    """Devuelve (clave_normalizada_o_None, etiqueta_humana_o_None)."""
    if not mun:
        return SIN_MUNICIPIO, None
    m = sin_acentos(html.unescape(str(mun))).lower()
    m = re.sub(r"[^\w\s%]", " ", m)          # fuera puntuación (“LEOSOFT”)
    m = re.sub(r"\s+", " ", m).strip()
    if not m or VACIO.search(m):
        return SIN_MUNICIPIO, None
    # PTA: la fuente da el barrio (Campanillas) -> es Málaga
    if m.startswith("campanillas"):
        return "malaga", "Málaga"
    clave = m.replace(" ", "-")
    return clave, ETIQUETA.get(clave, m.title())


def norm_nombre(nombre):
    """Minusculas + sin acentos + sin sufijos societarios + sin puntuacion."""
    n = html.unescape(str(nombre or ""))
    n = sin_acentos(n).lower()
    n = re.sub(r"[^\w\s]", " ", n)
    n = re.sub(r"\s+", " ", n).strip()
    for suf in SUFIJOS:                       # repetido: "X S.L." -> "x"
        n = re.sub(r"\b" + suf.replace(" ", r"\s+") + r"\b", " ", n)
        n = re.sub(r"\s+", " ", n).strip()
    return n


# --------------------------------------------------------------------------- fusión

def lee_raw():
    """[(ficha_raw, fichero)] de todos los raw/*.jsonl (ignora ficheros vacíos)."""
    fichas = []
    for nombre in sorted(os.listdir(RAW)):
        if not nombre.endswith(".jsonl"):
            continue
        ruta = os.path.join(RAW, nombre)
        for i, linea in enumerate(open(ruta, encoding="utf-8"), 1):
            linea = linea.strip()
            if not linea:
                continue
            try:
                d = json.loads(linea)
            except json.JSONDecodeError as e:
                raise SystemExit(f"{nombre}:{i}: JSON inválido — {e}")
            if not d.get("nombre"):           # regla dura de AGENTE_TEMPLATE.md
                continue
            fichas.append((d, nombre))
    return fichas


def campo_foraneo(d):
    """Municipio declarado por la oferta pero fuera de la provincia del fichero."""
    mun = norm_municipio(d.get("municipio"))[1]
    prov = (d.get("provincia") or "").upper()
    if mun and prov in DIRCE and norm_municipio(mun)[0] != prov.islower():
        return mun
    return None


def funde(grupo, ficheros_ok):
    """Ficha canónica a partir de N filas raw ya deduplicadas por empresa+municipio."""
    fuentes = []
    vistos = set()
    for d, fichero in grupo:
        s = (d.get("fuente"), d.get("fecha_captura"), d.get("evidencia_url"), fichero)
        if s in vistos:
            continue
        vistos.add(s)
        aporta = sorted({k for k in ("nombre", "municipio", "direccion", "web", "telefono",
                                     "email", "cif", "tipologias", "lat", "lng")
                         if d.get(k)})
        # BORME no trae fecha_captura: usa fecha_borme, o la fecha del nombre de fichero
        fecha = (d.get("fecha_captura") or d.get("fecha_borme")
                 or (re.search(r"(\d{4}-\d{2}-\d{2})", fichero) or [None, None])[1])
        fuentes.append({"source": d.get("fuente"), "fecha_captura": fecha,
                        "fichero": fichero, "evidencia_url": d.get("evidencia_url"),
                        "campos": aporta})

    def primero(campo):
        for d, _ in grupo:
            d = dict(d)
            v = d.get(campo)
            if v and campo == "municipio":
                v = norm_municipio(v)[1]
            if v:
                return v
        return None

    mun_clave, mun = norm_municipio(primero("municipio"))
    # provincia: la del fichero que declara el municipio elegido; si el municipio
    # resuelto es Sevilla/Malaga, manda el municipio (E2 cross-lista entre ficheros).
    prov = None
    for d, _ in grupo:
        if norm_municipio(d.get("municipio"))[1] == mun and (d.get("provincia") or "").upper() in DIRCE:
            prov = (d.get("provincia") or "").upper()
            break
    if (mun or "").lower() in ("sevilla", "málaga"):
        prov = mun.upper().replace("Á", "A")
    if not prov:
        prov = next(((d.get("provincia") or "").upper() for d, _ in grupo
                     if (d.get("provincia") or "").upper() in DIRCE), "")
    tipologias = sorted({t for d, _ in grupo for t in (d.get("tipologias") or [])})
    notas = [d.get("notas") for d, _ in grupo if d.get("notas")]
    n_src = len({f["source"] for f in fuentes})
    flags = []
    if any(campo_foraneo(d) for d, _ in grupo):
        flags.append("MUNICIPIO_FUERA_PROVINCIA")
    if mun is None:
        flags.append("SIN_MUNICIPIO")

    return {
        "id": None,                            # se rellena al final (orden estable)
        "nombre": primero("nombre"),
        "nombre_normalizado": norm_nombre(primero("nombre")),
        "municipio_normalizado": mun_clave,
        "cif": primero("cif"),
        "municipio": mun,
        "provincia": {"MALAGA": "Málaga"}.get(prov, prov.title() if prov else None),
        "cp": None,
        "direccion": primero("direccion"),
        "direccion_completa": None,
        "lat": None, "lng": None,              # los rellena Fase 3
        "distancia_km": None, "isocrona_min": None,
        "telefono": primero("telefono"),
        "web": primero("web"),
        "email": primero("email"),
        "tipologias": tipologias,
        "cnae": None,
        "empleados_rango": primero("empleados_rango"),
        "google_place_id": None, "google_rating": None, "google_n_resenas": None,
        "google_business_status": None, "google_tipos": [],
        "resena_mas_reciente": None, "resenas_ultimos_12m": None,
        "actividad_reciente": None, "criterio_actividad": None,
        "proxies_actividad": [],
        "estado": "ACTIVO",
        "confianza": "ALTA" if n_src >= 3 else ("MEDIA" if n_src == 2 else "BAJA"),
        "fuentes": fuentes,
        "n_fuentes_independientes": n_src,
        "n_ofertas": sum(1 for d, _ in grupo if d.get("fuente") == "E2_EMPLEO"),
        "flags": flags,
        "notas": " | ".join(dict.fromkeys(notas))[:600] or None,
    }


def fusionar_coords(fichas, tol_m=50):
    """Pendiente Fase 3: fusiona fichas con coords ±tol_m. No-op sin lat/lng."""
    res = []
    for f in fichas:
        if f["lat"] is None:
            res.append(f)
            continue
        choque = next((o for o in res if o["lat"] is not None
                       and abs(o["lat"] - f["lat"]) < tol_m / 111_320
                       and abs(o["lng"] - f["lng"]) < tol_m / 111_320), None)
        if choque:                             # ponytail: reino-aprox, sobra a 50 m
            choque["fuentes"] += f["fuentes"]
            choque["flags"].append("FUSIONADA_POR_COORDS")
        else:
            res.append(f)
    return res


def marca_posibles_duplicados(fichas, umbral=90.0):
    """Similitud alta (>= umbral) -> flag DUPLICADO_POSIBLE en ambas. Sin fusionar."""
    por_prov = defaultdict(list)
    for f in fichas:
        por_prov[f["provincia"]].append(f)
    pares = []
    for grupo in por_prov.values():
        for i, a in enumerate(grupo):
            for b in grupo[i + 1:]:
                if a["nombre_normalizado"] == b["nombre_normalizado"]:
                    continue                   # eso ya se fusionó aguas arriba
                r = SequenceMatcher(None, a["nombre_normalizado"],
                                    b["nombre_normalizado"]).ratio() * 100
                if r >= umbral:
                    pares.append((round(r, 1), a["id"], b["id"],
                                  a["nombre"], b["nombre"]))
                    for f in (a, b):
                        if "DUPLICADO_POSIBLE" not in f["flags"]:
                            f["flags"].append("DUPLICADO_POSIBLE")
    return sorted(pares, reverse=True)


# --------------------------------------------------------------------------- main

OBLIGATORIOS = ("id", "nombre", "nombre_normalizado", "municipio", "provincia",
                "estado", "confianza", "fuentes", "n_fuentes_independientes", "flags")


def valida(fichas):
    ids = set()
    for f in fichas:
        # municipio/provincia pueden ser null legitimamente (ofertas sin ubicacion,
        # BORME sin municipio); su ausencia va marcada en flags, no es un fallo.
        faltan = [c for c in OBLIGATORIOS
                  if f.get(c) in (None, "", []) and c not in ("municipio", "provincia")]
        assert not faltan, f"{f.get('id')}: campos obligatorios vacíos {faltan}"
        assert f["id"] not in ids, f"id repetido {f['id']}"
        ids.add(f["id"])
        assert f["confianza"] in ("ALTA", "MEDIA", "BAJA"), f["confianza"]
        assert f["n_fuentes_independientes"] == len(
            {x["source"] for x in f["fuentes"]}), f"{f['id']}: n_fuentes incoherente"
        for x in f["fuentes"]:
            assert x["source"] and x["fecha_captura"], f"{f['id']}: fuente sin source/fecha"
    return True


def main():
    os.makedirs(DATA, exist_ok=True)
    os.makedirs(INFORMES, exist_ok=True)

    raw = lee_raw()
    por_fichero = Counter(f for _, f in raw)

    claves = defaultdict(list)                 # norm_nombre -> filas
    for d, fichero in raw:
        claves[norm_nombre(d["nombre"])].append((d, fichero))

    # Desambiguacion por municipio: mismo nombre en 2+ municipios REALES distintos
    # son empresas distintas (cadena "Grupo Digital" en Sevilla y Malaga). Si uno
    # de los grupos tiene municipio desconocido (ofertas en remoto), NO desambigua:
    # es la misma empresa, y se fusiona con el municipio conocido.
    grupos = []
    for filas in claves.values():
        por_mun = defaultdict(list)
        for d, f in filas:
            por_mun[norm_municipio(d.get("municipio"))[0]].append((d, f))
        conocidos = [k for k in por_mun if k is not None]
        if len(conocidos) <= 1:
            grupos.append(filas)               # un solo municipio real: todo junto
        else:
            primero = []                       # siempre queda asignado (>=2 conocidos)
            for k, v in por_mun.items():       # 2+ municipios reales: separa
                if k is None:
                    continue
                grupos.append(v)
                if not primero:
                    primero = grupos[-1]
            if por_mun.get(None):              # remoto sin ubicacion -> al primero
                primero += por_mun[None]

    fichas = [funde(g, None) for g in grupos]
    fichas = fusionar_coords(fichas)

    # orden estable -> ids reproducibles
    fichas.sort(key=lambda f: (f["provincia"] or "~", f["nombre_normalizado"]))
    contador = Counter()
    for f in fichas:
        pref = "sev" if f["provincia"] == "Sevilla" else ("mal" if f["provincia"] == "Málaga" else "sin")
        contador[pref] += 1
        f["id"] = f"{pref}-{contador[pref]:04d}"

    pares = marca_posibles_duplicados(fichas)
    valida(fichas)

    with open(SALIDA, "w", encoding="utf-8") as fh:
        json.dump(fichas, fh, ensure_ascii=False, indent=1)
        fh.write("\n")

    # ------------------------------------------------------------- informe
    fusionadas = len(raw) - len(fichas)
    por_fuente = Counter(x["source"] for f in fichas for x in f["fuentes"])
    solo_fuente = Counter()
    for f in fichas:
        if f["n_fuentes_independientes"] == 1:
            solo_fuente[f["fuentes"][0]["source"]] += 1
    conf = Counter(f["confianza"] for f in fichas)
    con_flag = Counter(fl for f in fichas for fl in f["flags"])
    excl_empleo_fuera = sum(1 for f in fichas
                            if "MUNICIPIO_FUERA_PROVINCIA" in f["flags"])
    total_dirce = sum(DIRCE.values())

    L = ["# Fase 2 — Fusión y deduplicación",
         "",
         f"**Fecha:** 2026-09-18 · **Script:** `scripts/merge_fuentes.py` (reejecutable)",
         f"**Salida:** `data/empresas.json` — {len(fichas)} fichas",
         "",
         "## Entrada / salida",
         "",
         f"- Fichas de entrada (raw/*.jsonl): **{len(raw)}**",
         f"- Fichas de salida: **{len(fichas)}**",
         f"- Filas absorbidas en fusión: **{fusionadas}** "
         f"({100*fusionadas/len(raw):.1f} % de la entrada)",
         f"- Fusiones (grupos con >1 fila): **{sum(1 for g in claves.values() if len(g)>1)}**",
         "",
         "### Desglose por fuente (fichas que aportan)",
         ""]
    for s, n in por_fuente.most_common():
        L.append(f"- `{s}`: aporta a **{n}** fichas ({solo_fuente[s]} en exclusiva)")
    L += ["",
          "### Ficheros leídos",
          ""]
    for s, n in sorted(por_fichero.items()):
        L.append(f"- `raw/{s}`: {n} líneas")
    L += ["",
          "## Confianza",
          "",
          f"- ALTA (≥3 fuentes): **{conf['ALTA']}**",
          f"- MEDIA (2 fuentes): **{conf['MEDIA']}**",
          f"- BAJA (1 fuente): **{conf['BAJA']}**",
          "",
          "## Flags",
          ""]
    for fl, n in con_flag.most_common():
        L.append(f"- `{fl}`: {n}")
    L += ["",
          f"### DUPLICADO_POSIBLE — {len(pares)} pares (similitud ≥ 90, "
          "**no fusionados**, requieren revisión humana)",
          ""]
    for r, ia, ib, na, nb in pares[:40]:
        L.append(f"- {r} % · `{ia}` {na} ↔ `{ib}` {nb}")
    if len(pares) > 40:
        L.append(f"- … y {len(pares)-40} pares más (ver flags en `data/empresas.json`)")
    L += ["",
          "## Cobertura frente a DIRCE 2025",
          "",
          f"- DIRCE 2025, locales CNAE 62: Sevilla {DIRCE['SEVILLA']}, "
          f"Málaga {DIRCE['MALAGA']}, total **{total_dirce}**",
          f"- Censo fusionado: **{len(fichas)}** fichas → "
          f"**{100*len(fichas)/total_dirce:.2f} %** del universo DIRCE",
          "",
          "Por provincia:",
          ""]
    for prov, den in (("Sevilla", DIRCE["SEVILLA"]), ("Málaga", DIRCE["MALAGA"])):
        n = sum(1 for f in fichas if f["provincia"] == prov)
        L.append(f"- {prov}: {n} / {den} = **{100*n/den:.2f} %**")
    sin_prov = sum(1 for f in fichas if not f["provincia"])
    if sin_prov:
        L.append(f"- sin provincia asignada (BORME sin municipio): {sin_prov}")
    L += ["",
          "## Cambios de criterio aplicados (documentados, no silenciosos)",
          "",
          "- `municipio = \"100% remoto\"` **no se trata como municipio** para deduplicar: "
          "no es una ubicación y produce falsas fusiones entre provincias. Se normaliza a "
          "`municipio = null`, clave `None`, y se marca `SIN_MUNICIPIO`. Si una empresa tiene "
          "filas con municipio conocido y filas en remoto, se fusionan en una sola ficha que "
          "conserva el municipio conocido (dato real: CAS TRAINING aparecía repartida entre "
          "`Málaga`, `100% remoto` y los dos ficheros E2 — ahora es una única ficha `mal-0028` "
          "con 24 ofertas).",
          "- Desambiguación por municipio: mismo nombre normalizado en 2+ municipios **reales** "
          "distintos son fichas separadas (agencias de empleo tipo Michael Page, UST, T-Systems, "
          "presentes a la vez en Sevilla y Málaga). Con municipio desconocido de por medio NO se "
          "desambigua: es la misma empresa. "
          f"{sum(1 for n, c in Counter(f['nombre_normalizado'] for f in fichas).items() if c > 1)} "
          "nombres quedan con ≥2 fichas por este motivo, todas legítimas.",
          "- Municipio del fichero y `provincia` del fichero discrepan a menudo en E2 "
          "(ofertas de una provincia listadas desde otra). La ficha se asigna a la provincia "
          "del fichero; si el municipio declarado es de la otra provincia se marca "
          f"`MUNICIPIO_FUERA_PROVINCIA` ({excl_empleo_fuera} fichas). **No se descarta nada**: "
          "la decisión de ámbito es de Fase 4.",
          "- `e3_parques_pta` da el barrio (Campanillas) en lugar del municipio → normalizado "
          "a Málaga.",
          "- BORME: entidades HTML (`&amp;`) desescapadas y sufijos societarios eliminados del "
          "nombre normalizado.",
          "",
          "## Pendiente (fuera de esta fase)",
          "",
          "- Fusión por coords ±50 m: `fusionar_coords()` está implementada y es no-op hasta que "
          "Fase 3 (`verificar_places.py`) rellene `lat`/`lng`.",
          "- El % sobre DIRCE es una **cota inferior**: E2 sólo captura quien publica ofertas y "
          "sólo de dos portales; faltan fuentes (Google Places, clusters, colegios "
          "profesionales). No es la cifra final del censo.",
          ""]
    with open(os.path.join(INFORMES, "fase2_fusion.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))

    print(f"entrada={len(raw)} salida={len(fichas)} fusionadas={fusionadas} "
          f"duplicado_posible={len(pares)} cobertura={100*len(fichas)/total_dirce:.2f}%")
    return fichas


if __name__ == "__main__":
    # --- check: el JSON en disco valida contra los campos obligatorios del esquema §3
    esperado = main()
    with open(SALIDA, encoding="utf-8") as fh:
        leido = json.load(fh)
    valida(leido)
    assert len(leido) == len(esperado)

    # check de regresión: los duplicados reales conocidos quedan fusionados en 1 ficha
    por_nombre = defaultdict(list)
    for f in leido:
        por_nombre[f["nombre_normalizado"]].append(f)
    cas = por_nombre["cas training"]
    assert len(cas) == 1, f"CAS TRAINING deberia ser 1 ficha, hay {len(cas)}"
    assert cas[0]["municipio"] == "Málaga", cas[0]["municipio"]
    panel = por_nombre["panel sistemas informaticos"]
    assert len(panel) == 1, f"PANEL deberia ser 1 ficha, hay {len(panel)}"
    assert panel[0]["n_ofertas"] >= 25, panel[0]["n_ofertas"]

    if len(sys.argv) > 1 and sys.argv[1] == "--show":
        print(json.dumps(leido[:3], ensure_ascii=False, indent=1))
    print(f"OK — data/empresas.json valida ({len(leido)} fichas)")
