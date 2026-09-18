#!/usr/bin/env python3
"""
Fase 4 — clasificación, casos frontera y proxy de actividad (N2).

Tres cosas:
  1. tipologias[] por tipología real (no la del plan a ciegas): se infiere de
     nombre + web + categoría de Google. Una empresa puede tener varias.
  2. Casos frontera de §1.3 → data/excluidos.json con motivo y evidencia.
  3. N2: las fichas sin reseña reciente pero con web viva pasan a "actividad por
     proxy". Sin proxy → excluida por SIN_ACTIVIDAD_12M.
"""
import json, os, re, sys, urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EMPRESAS = os.path.join(RAIZ, "data", "empresas.json")
EXCLUIDOS = os.path.join(RAIZ, "data", "excluidos.json")
HOY = "2026-09-18"

# Señales léxicas. Orden importa: el primero que casa gana para esa categoría.
SENALES = [
    ("VIDEOJUEGOS", r"videojuego|videogame|\bgame studio\b|gamificaci|unity|unreal"),
    ("DATA_IA", r"\bdata\b|analitic|analytics|\bIA\b|\bAI\b|machine learning|big data|inteligencia artificial"),
    ("FACTORIA", r"factory|factor[ií]a|nearshore|outsourc|staffing|team extension|equipo dedicado"),
    ("INTEGRADOR", r"\berp\b|\bcrm\b|odoo|sap\b|salesforce|dynamics|navision|integraci[oó]n de sistemas"),
    ("CONSULTORA", r"consultor|consulting|consultancy"),
    ("PRODUCTO", r"\bsaas\b|plataforma|app\b|software propio|producto propio"),
    ("IT_GENERALISTA", r"inform[aá]tic|sistemas|redes|hosting|soporte|telecomunicacion|cloud\b"),
    ("ETT_TECNOLOGICA", r"\bETT\b|trabajo temporal|selecci[oó]n de personal|recursos humanos|\bRRHH\b"),
    ("TELCO", r"telef[oó]nica|vodafone|orange|movistar|telecom"),
]

# §1.3 — excluir sin más. (patrón, motivo) — ojo: los que SÍ entran (ETT, TELCO) no van aquí.
EXCLUIR = [
    (r"^(PC ?BOX|APP ?INFORM|PCNET|PC3|inform[aá]tica [a-z]+|tienda)", "EXC_REVENTA"),
    (r"^centro guadalinfo|guadalinfo", "EXC_PUBLICO"),
    (r"^(ayuntamiento|diputaci[oó]n|junta de andaluc|universidad|consejer[ií]a|ministerio|hospital|biblioteca)",
     "EXC_PUBLICO"),
    (r"^u\.?s\.?c\.?|^universidad", "EXC_PUBLICO"),
    (r"^michael page|^hays|^adecco|^randstad|^manpower|^eurofirms|^spring professional", "EXC_ETT_NO_IT"),
]


def tipologias(nombre, web, tipos_google, notas):
    """Clasifica por señales reales. Orden de fiabilidad: notas de oferta > nombre > web.

    Places NO clasifica empresas de software (todas salen 'establishment' +
    'point_of_interest', medido con Emergya, CARTO, Freepik, Sopra, Indra). El
    único campo con texto de negocio de verdad son las notas de E2, que traen el
    puesto ofertado y a veces la actividad declarada.
    """
    out = []
    # 1. notas de oferta de empleo: la señal más rica
    puesto = ""
    if notas:
        m = re.search(r"puesto=([^;]+)", notas)
        puesto = m.group(1) if m else ""
    texto_oferta = " ".join(filter(None, [puesto, notas]))
    for etiqueta, patron in SENALES_PUESTO:
        if re.search(patron, texto_oferta, re.I):
            out.append(etiqueta)

    # 2. nombre + web
    txt = " ".join(list(filter(None, [nombre, web])) + list(tipos_google or []))
    for etiqueta, patron in SENALES:
        if re.search(patron, txt, re.I) and etiqueta not in out:
            out.append(etiqueta)
    return out                       # vacío es un resultado honesto: no sabemos


# Puesto ofertado → tipología. Es la señal fuerte.
SENALES_PUESTO = [
    ("DATA_IA", r"data|machine learning|\bML\b|\bAI\b|\bIA\b|analytics|big data|cient[ií]fico de datos"),
    ("VIDEOJUEGOS", r"videojuego|unity|unreal|gameplay|\bgame\b"),
    ("FACTORIA", r"nearshore|outsourc|equipo dedicado|staffing|team extension|augment"),
    ("INTEGRADOR", r"\berp\b|\bcrm\b|odoo|sap\b|salesforce|dynamics|navision"),
    ("CONSULTORA", r"consultor|analista funcional|business analyst"),
    ("PRODUCTO", r"product owner|producto|saas|plataforma"),
    ("IT_GENERALISTA", r"sysadmin|sistemas|redes|soporte|\bhelpdesk\b|devops|\bsre\b|cloud|infraestructura|seguridad"),
    ("DESARROLLO", r"desarrollador|developer|programador|desarrollo de software|frontend|backend|full ?stack"
                   r"|java\b|python|c#|\.net|javascript|react|angular|node|php|kotlin|swift|android|ios\b|qa\b|tester"),
]


def motivo_exclusion(nombre):
    for patron, motivo in EXCLUIR:
        if re.search(patron, nombre.strip(), re.I):
            return motivo
    return None


def web_viva(url, timeout=12):
    """HEAD con fallback a GET. True si responde <400. Evita bajar el cuerpo entero."""
    if not url:
        return None
    if not url.startswith("http"):
        url = "https://" + url
    for metodo in ("HEAD", "GET"):
        try:
            req = urllib.request.Request(
                url, method=metodo,
                headers={"User-Agent": "Mozilla/5.0 (compatible; censo-software/1.0)"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status < 400
        except Exception:
            continue
    return False


def main():
    fichas = json.load(open(EMPRESAS))
    excl = json.load(open(EXCLUIDOS)) if os.path.exists(EXCLUIDOS) else []

    dentro, expulsadas = [], []
    for f in fichas:
        motivo = motivo_exclusion(f["nombre"])
        if motivo:
            expulsadas.append({**f, "motivo_exclusion": motivo,
                               "evidencia_url": "regla §1.3 del plan",
                               "fecha": HOY})
            continue

        f["tipologias"] = tipologias(f["nombre"], f.get("web"), f.get("google_tipos"), f.get("notas"))
        # N3: sin reseña reciente y sin web que verificar → sin actividad acreditable
        if f.get("criterio_actividad") == "SIN_DATOS_PLACES" and not f.get("web"):
            expulsadas.append({**f, "motivo_exclusion": "SIN_ACTIVIDAD_12M",
                               "evidencia_url": "sin reseñas y sin web",
                               "fecha": HOY})
            continue
        dentro.append(f)

    # N2: web viva ⇒ proxy de actividad (solo para las que fallaron N1)
    pend = [f for f in dentro if f.get("criterio_actividad") == "PENDIENTE_PROXY" and f.get("web")]
    print(f"N2: verificando web viva de {len(pend)} fichas sin reseña reciente...")
    vivas = 0
    for i, f in enumerate(pend, 1):
        if web_viva(f["web"]):
            f["actividad_reciente"] = True
            f["criterio_actividad"] = "WEB_VIVA"
            f["proxies_actividad"] = [{"tipo": "ACTUALIZACION_WEB",
                                       "fecha": HOY, "url": f["web"]}]
            vivas += 1
        if i % 25 == 0:
            print(f"  {i}/{len(pend)}")

    # las que no acreditaron nada, fuera
    finales = []
    for f in dentro:
        if f.get("criterio_actividad") == "PENDIENTE_PROXY":
            expulsadas.append({**f, "motivo_exclusion": "SIN_ACTIVIDAD_12M",
                               "evidencia_url": f.get("web") or "sin web ni reseñas",
                               "fecha": HOY})
        elif f.get("criterio_actividad") == "SIN_DATOS_PLACES":
            f["actividad_reciente"] = None
            finales.append(f)
        else:
            finales.append(f)

    json.dump(finales, open(EMPRESAS, "w"), ensure_ascii=False, indent=1)
    json.dump(excl, open(EXCLUIDOS, "w"), ensure_ascii=False, indent=1)

    from collections import Counter
    print(f"\nfinales: {len(finales)} | excluidas nuevas: {len(expulsadas)} | total excluidos: {len(excl)}")
    print("criterio_actividad:", dict(Counter(f["criterio_actividad"] for f in finales)))
    print("actividad_reciente:", dict(Counter(str(f["actividad_reciente"]) for f in finales)))
    print("tipologias:", dict(Counter(t for f in finales for t in f["tipologias"]).most_common(12)))
    print("motivos exclusion:", dict(Counter(e["motivo_exclusion"] for e in excl)))

    assert all("tipologias" in f for f in finales), "ficha sin campo tipologias"
    assert all(f.get("criterio_actividad") for f in finales), "ficha sin criterio_actividad"
    print("\nOK: tipologias y criterio_actividad presentes en todas las fichas")


if __name__ == "__main__":
    main()
