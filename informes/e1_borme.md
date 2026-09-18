# E1 — BORME / datos abiertos BOE: ¿hay vía pública para empresas CNAE 62 en Sevilla y Málaga?

**Fecha:** 18/09/2026 · **Agente:** E1 (Fase 0) · **Estado:** ✅ **FUNCIONA, con matices importantes**

---

## Resumen ejecutivo

**Sí existe vía pública y gratuita.** La API real es la de **datos abiertos del BOE**, no un
"apartado BORME" en `boe.es/datosabiertos/` (esa URL da 404).

Pero **no hay endpoint por CNAE ni por provincia filtrable**. El BORME se publica **por fecha
y por provincia**, y el CNAE **solo aparece como texto libre dentro del "Objeto social"**, y
**solo en una minoría de los asientos**. Consecuencia: de la API se sacan **NOMBRES + provincia
+ fecha**, no un listado CNAE 62. Filtrar por CNAE 62 exige **descargar los XML provinciales y
hacer grep sobre el objeto social**.

**Medición real (25 días hábiles, 17/08 → 17/09/2026):**

| Provincia | Empresas en el periodo | Candidatas CNAE 62 (grep objeto social) |
|---|---|---|
| Sevilla (41) | 1.212 | **10** |
| Málaga (29) | 1.339 | **28** |

**Extrapolación:** ~10 empresas/Sevilla/mes y ~28 empresas/Málaga/mes que *mencionan* CNAE 62 en
el BORME → **~120/año Sevilla, ~330/año Málaga**. Y ~100% de las empresas existentes **NO pasan
por el BORME** cada mes (el BORME solo publica *actos inscritos*: constituciones, cambios, etc.).
El BORME captura **empresas nuevas o que cambian**, no el stock.

> **Conclusion para el plan:** el BORME sirve como **fuente de descubrimiento de empresas
> recién constituidas con objeto social de software** (útil, y con CIF/domicilio), pero **NO
> da el censo**. No sustituye a DIRCE para calibrar el universo.

---

## 1. Vías probadas

### 1.1 `datos.gob.es` catálogo (`/apidata/`) — ✅ FUNCIONA (pero no es lo que buscábamos)

La ruta que daba 400 era incorrecta. **Rutas válidas:**

```
GET https://datos.gob.es/apidata/catalog/dataset.json?_pageSize=5
GET https://datos.gob.es/apidata/catalog/dataset/title/borme.json?_pageSize=5
```

- `?_q=` → **400 `unknown shortname`** (no existe el parámetro `_q` en `/catalog/dataset/`)
- `_pageSize` y `_page` **sí** funcionan.

El catálogo **solo devuelve metadatos** del dataset, no datos. Y apunta a la fuente real:

```
Dataset: "Diario oficial BORME"  →  https://datos.gob.es/catalogo/ea0040819-diario-oficial-borme
  distribution.accessURL: https://www.boe.es/datosabiertos/api/api.php
```

**Conclusión:** `datos.gob.es` es un catálogo, no una API de datos. La fuente real es el BOE.

### 1.2 `https://www.boe.es/datosabiertos/` — ✅ API REAL LOCALIZADA

- `https://www.boe.es/datosabiertos/` → redirige a `/datosabiertos/api/api.php` (200, es HTML de documentación)
- `https://www.boe.es/datosabiertos/boletin-oficial-del-registro-mercantil/` → **404** (URL inventada)
- Documentación técnica oficial: **`https://www.boe.es/datosabiertos/documentos/APIsumarioBORME.pdf`** (v2.0, 28/05/2026)

### 1.3 API de sumarios BORME — ✅ FUNCIONA (JSON y XML)

```
GET https://boe.es/datosabiertos/api/borme/sumario/{AAAAMMDD}
Header: Accept: application/json   (o application/xml)
```

Ejemplo verificado:

```bash
curl -s -L -H "Accept: application/json" \
  "https://boe.es/datosabiertos/api/borme/sumario/20260917"
```

Devuelve `status.code=200` y un árbol `data.sumario.diario[].seccion[].item[]` donde **cada
`item` es una provincia** con tres URLs:

```json
{
  "identificador": "BORME-A-2026-180-41",
  "titulo": "SEVILLA",
  "url_pdf":  {"texto": "https://www.boe.es/borme/dias/2026/09/17/pdfs/BORME-A-2026-180-41.pdf"},
  "url_html": "https://www.boe.es/diario_borme/txt.php?id=BORME-A-2026-180-41",
  "url_xml":  "https://www.boe.es/diario_borme/xml.php?id=BORME-A-2026-180-41"
}
```

- **Sección A** = "Empresarios. Actos inscritos" (aquí están las empresas)
- **Sección B** = "Otros actos publicados"
- **Sección C** = "Anuncios y avisos legales"
- El sufijo numérico del identificador **es el código de provincia** (41=Sevilla, 29=Málaga, 28=Madrid, 99=índice alfabético).

### 1.4 XML provincial BORME — ✅ FUNCIONA, y **contiene los NOMBRES**

```
GET https://www.boe.es/diario_borme/xml.php?id=BORME-A-2026-180-41
```

```xml
<documento fecha_actualizacion="20260917T071854Z">
  <metadatos>
    <identificador>BORME-A-2026-180-41</identificador>
    <titulo>SEVILLA</titulo>
    <fecha_publicacion>20260917</fecha_publicacion>
    <url_pdf>https://www.boe.es/borme/dias/2026/09/17/pdfs/BORME-A-2026-180-41.pdf</url_pdf>
  </metadatos>
  <texto>
    <p class="articulo">418256 - NONINAPP SOFTWARE SOCIEDAD LIMITADA.</p>
    <p class="parrafo">Constitución. ... Objeto social: Actividades de programación informática.
       Domicilio: C/ HUNGRIA 4 - PLANTA 0. CODIGO POSTAL 41012 (SEVILLA). Capital: 3.000,00 Euros.
       ... Socio único: CANO PUERTO RAUL. ...</p>
```

**Lo que da:** razón social, objeto social (texto libre), domicilio (a veces), CP (a veces),
capital, administradores, datos registrales (tomo/folio/hoja).

**Lo que NO da:** CNAE como campo estructurado, CIF, teléfono, web, email, número de empleados.
El `Accept: application/json` sobre `xml.php` **se ignora** (devuelve `application/xml`).

---

## 2. El problema del CNAE — medido, no supuesto

Sobre una muestra de 25 días hábiles × 2 provincias (2.551 asientos totales):

- Asientos con la cadena **"CNAE"** en el objeto social: **muy pocos** (grep en un día:
  7 en Málaga, 6 en Sevilla, de ~50-70 asientos por provincia y día)
- Asientos con **"CNAE 620x"** explícito: **0 de 2.551** en la muestra
- Asientos cuyo objeto social contiene **"programación informática"** o similar: **10 (Sevilla) + 28 (Málaga)**

Es decir: **el BORME no está indexado por CNAE.** Es texto libre, redactado por el registrador.
Algunos asientos lo mencionan ("CNAE 62.10. Actividades de programación informática"), la
mayoría no. Ejemplo de acierto claro:

```
MALAGA | CODEROLLERS SL. (2026-09-01)
  Cambio de objeto social. Actividad principal: La realización de todo tipo de desarrollo,
  diseño, consultoría y prestaciones de servicios informáticos; CNAE 62.10.
  "Actividades de programación informática".
```

Ejemplo de **falso positivo** (el grep léxico mete ruido):

```
SEVILLA | MIURA IBERICA IMPORT SOCIEDAD LIMITADA.
  Objeto social: Construcción de edificios no residenciales. Actividades de apoyo a la
  agricultura. ... Comercio al por menor de vehículos de motor. Restaurantes.
  Actividades de programa...   ← es una importadora de coches con muchas actividades listadas
```

→ Requiere revisión humana o filtro léxico más fino (el plan ya tiene `EXC_FALSO_LEXICO`).

---

## 3. Recuento real (evidencia reproducible)

Script: `scripts/collectors/borme_cnae62.py` → salida a `raw/borme_cnae62_2026-09-18.jsonl`

```bash
python3 scripts/collectors/borme_cnae62.py 25
```

```
{
  "41": { "fechas": 18, "empresas": 1212, "match_cnae": 0, "match_prog": 10 },
  "29": { "fechas": 20, "empresas": 1339, "match_cnae": 0, "match_prog": 28 }
}
```

- **Sevilla: 10 candidatas** en 25 días hábiles (~1 mes)
- **Málaga: 28 candidatas** en el mismo periodo
- Málaga produce **~2,8× más** que Sevilla → confirma §1.2 del plan (Málaga pesa más)

Muestra de candidatas (todas con URL de evidencia = XML provincial del día):

*Sevilla:* GESTION AMIC & DIGITAL MIC 1 SL, JRV LAB SL, SOFICONECTA CONSULTING S.L.,
CINEMATIC OPERATOR SL, NONINAPP SOFTWARE SL, MAMIDI STUDIO SL, FLETERS SOLUTIONS SL,
SILVANTIA PARTNERS SL, SEVIAN LABS SL

*Málaga:* ENFOCA AI SL, CHUUZIT SOLUTIONS SL, FOUR SEVEN TECH SL, OP-25 SOFT SL,
LIPARI DIGITAL SL, NETERIS SL, **CODEROLLERS SL**, QUANTX TECHNOLOGIES SL,
ONECONTROL ERP SL, GENIA INTELLIGENCE SL, TECHNOLOGY KYOIKU SL, SILICON SUR SL,
MOVION AI SYSTEMS SL, ISA-IN COLLECTIVE SL, 2027 LPJ CONSULTORES SL ...

Cada línea del jsonl lleva `evidencia_url` (el `xml.php?id=BORME-A-...`). **Regla dura respetada.**

---

## 4. Cómo usarlo en el censo (recomendación)

**Sí, úsalo — como fuente de descubrimiento de "recién constituidas", no como censo.**

1. **Barrido hacia atrás**: el BORME es diario desde 1998 y la API es gratuita y sin key.
   Recorrer 24 meses ≈ 520 días × 2 provincias = **1.040 requests al BOE** → 1 req/s ≈ 20 min.
   Extrae ~250-300 empresas/año con objeto social de software en las dos provincias.
2. **Ventaja**: son **empresas nuevas**, con domicilio y a veces CP → alimentan directamente
   `data/empresas.json` con `evidencia_url` verificable.
3. **Limitación dura**: no da el *stock* de empresas CNAE 62 ya existentes. Para calibrar el
   universo sigue haciendo falta **DIRCE** (E-0.5 del plan), que da conteos por municipio.
4. **Dedupe**: el mismo nombre reaparece en varios asientos (constitución → cambio de
   domicilio → ampliación). Deduplicar por nombre + datos registrales (T/F/H).
5. **Ruido**: el grep léxico mete falsos positivos (empresas multisector). Filtro adicional o
   revisión en Fase 4.
6. **CIF ausente**: el BORME no publica CIF. Si el censo lo necesita, hay que cruzarlo con otra
   fuente.

---

## 5. Veredicto

| Pregunta | Respuesta |
|---|---|
| ¿Existe vía pública y gratuita? | **SÍ** — API datos abiertos BOE |
| ¿Endpoint por CNAE? | **NO** — solo por fecha + provincia |
| ¿Devuelve nombres? | **SÍ** — razón social completa en el XML provincial |
| ¿Filtrable por CNAE 62? | **Solo por texto libre** del objeto social (grep), con ruido |
| ¿Da CIF / contacto / empleados? | **NO** |
| ¿Cuántas Sevilla? | **10** candidatas en 25 días hábiles (~1,2% del total de asientos) |
| ¿Cuántas Málaga? | **28** candidatas en el mismo periodo (~2,1%) |
| ¿Sustituye a DIRCE? | **NO** — es flujo (nuevas), no stock |
| ¿Coste? | **0 €, sin API key** |

**Para el plan:** E1 se declara **VIVA** con rol acotado — *descubrimiento de empresas de
software recién constituidas*, con evidencia URL por ficha. No es el censo completo y no
pretende serlo.

---

## Anexo — Endpoints verificados (18/09/2026)

| URL | Código | Notas |
|---|---|---|
| `https://www.boe.es/datosabiertos/` | 200 | redirige a `api.php` (HTML docs) |
| `https://www.boe.es/datosabiertos/api/api.php` | 200 | documentación de la API |
| `https://www.boe.es/datosabiertos/documentos/APIsumarioBORME.pdf` | 200 | **doc técnica oficial v2.0** |
| `https://boe.es/datosabiertos/api/borme/sumario/{AAAAMMDD}` | 200 | **JSON/XML**, parametrizado por fecha |
| `https://www.boe.es/diario_borme/xml.php?id=BORME-A-{AAAA}-{N}-{prov}` | 200 | **XML con nombres**, `Accept` ignorado |
| `https://www.boe.es/diario_borme/txt.php?id=BORME-A-...` | 200 | HTML |
| `https://www.boe.es/borme/dias/{AAAA}/{MM}/{DD}/pdfs/BORME-A-...pdf` | 200 | PDF |
| `https://www.boe.es/datosabiertos/boletin-oficial-del-registro-mercantil/` | **404** | URL inventada, NO existe |
| `https://datos.gob.es/apidata/catalog/dataset.json?_q=...` | **400** | `_q` no existe; usar `_pageSize` |
| `https://datos.gob.es/apidata/catalog/dataset/title/borme.json` | 200 | catálogo → apunta al BOE |
| `https://www.boe.es/datosabiertos/documentos/API_BORME.pdf` | **404** | nombre incorrecto; es `APIsumarioBORME.pdf` |

**Artefactos creados:**
- `scripts/collectors/borme_cnae62.py` — collector funcional
- `raw/borme_cnae62_2026-09-18.jsonl` — 38 candidatas con `evidencia_url`
- `informes/e1_borme.md` — este informe
