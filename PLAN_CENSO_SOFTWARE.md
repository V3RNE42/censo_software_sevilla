# PLAN — Censo de empresas de desarrollo de software en las provincias de Sevilla y Málaga

**Versión:** 1.0 — 18 septiembre 2026
**Proyecto:** `censo_software_sevilla`  ·  **Ámbito:** provincias INE 41 (Sevilla) y 29 (Málaga)
**Repositorio objetivo:** `V3RNE42/censo_software_sevilla` (privado)
**Destinatario:** orquestador + N agentes en paralelo
**Estado:** plan para ejecución. Los supuestos no verificados están marcados **`[EXP]`** y se resuelven en Fase 0 antes de gastar agentes.

---

## 0. Qué cambia respecto al proyecto anterior (`centros_compatibles`)

Este plan **NO es un clon**. Tres supuestos del proyecto anterior se han medido y **se caen**:

| Supuesto heredado | Medición real (18/09/2026) | Consecuencia |
|---|---|---|
| "OSM es fuente primaria de descubrimiento" | Radio 100 km: **18 entidades** de software con nombre, de las que 2 son centros Guadalinfo (públicos) y 1 es IBM. **~12 empresas reales** | OSM **degradado a fuente terciaria**. Si el barrido OSM fuera el eje, el censo tendría 12 fichas y se presentaría como completo |
| "Hay un equivalente a ACEIA" (buscador oficial de academias) | **No existe.** No hay registro público consultable de "empresas de software de Sevilla" | La búsqueda pasa a ser **multifuente + captura-recaptura**, no barrido de un buscador |
| "El filtro de reseñas se puede scrapear" | Emergya: scraping y navegador devuelven reseñas de hace **6, 9 y 12 años** (las "más relevantes"). La API con `reviews_sort=newest` devuelve **2025-02-14** | El filtro de 12 meses **solo** funciona vía Places API. Sin key, es infalsable |

**Lo que SÍ se hereda** (no reinventar — ver §10):
- Esquema de procedencia por ficha (`fuentes[]`, `n_fuentes_independientes`, `confianza`, `flags`)
- Generador único de HTML desde JSON (el desajuste ficha↔mapa se resuelve *por construcción*)
- `AVISO.md` con RGPD y procedimiento de retirada
- Captura-recaptura / Chao1 como criterio de parada
- Separación `excluidos.json` (exclusión ≠ borrado)

---

## 1. Definición operativa de "empresa de desarrollo de software"

Como me delegaste el criterio (§ decisión del 18/09), lo fijo aquí de forma **falsable**, no por intuición.

Una entidad entra en el censo si cumple **las tres**:

1. **Actividad de desarrollo**: produce software. Se acredita por **al menos una** de:
   - **D1** — Tiene producto propio (SaaS, app, licencia, SDK) publicado y comercializado.
   - **D2** — Factura servicios de desarrollo/fábrica a terceros (consultora, factoría, nearshore).
   - **D3** — CNAE de alta en **62** (programación, consultoría informática y otras actividades de servicios de información), subclases **6201 / 6202 / 6203 / 6209**.
   - **D4** — Publica ofertas de empleo para perfiles de desarrollo (dev, engineer, data, QA) en los últimos 24 meses.
2. **Sede física real**: local verificable en el ámbito. Un coworking/domiciliación **no basta por sí solo** (regla `EXC_DOMICILIACION`, heredada).
3. **Capacidad de contratación**: persona jurídica o autónomo con local que emplea o puede emplear a alguien distinto del titular. Esto separa "empresa" de "freelance suelto".

### 1.1 Tipologías (campo etiquetable, NO excluyente)

Se implementa como **campo**, no como poblaciones separadas: una empresa puede ser `PRODUCTO` y `DATA_IA` a la vez. El filtro lo aplica el consumidor al vuelo.

| Código | Tipología | Señal de detección |
|---|---|---|
| `PRODUCTO` | Producto propio / SaaS / app | Web con precios, app stores, changelog |
| `FACTORIA` | Factoría / nearshore / body shopping | Ofertas masivas, lenguaje de "equipo dedicado" |
| `CONSULTORA` | Consultoría tecnológica con desarrollo | CNAE 6202, proyectos públicos |
| `INTEGRADOR` | Integrador / implantador de ERP-CRM | Marcas (SAP, Odoo, Microsoft) en web |
| `DATA_IA` | Datos, analítica, IA/ML | Stack ML en web/ofertas |
| `VIDEOJUEGOS` | Videojuegos / gamificación | Registro/portfolio de títulos |
| `IT_GENERALISTA` | Soporte, sistemas, redes, hosting | **Caso frontera** — ver §1.3 |
| `ETT_TECNOLOGICA` | ETT que coloca perfiles IT | **Caso frontera** — ver §1.3 |
| `TELCO` | Telco con área de desarrollo | Caso frontera |

### 1.2 Ámbito geográfico: provincias de Sevilla (INE 41) y Málaga (INE 29)

**Decisión:** entran **todas las fichas de ambas provincias**. El radio de 100 km **no** delimita el corpus — se conserva como campo informativo (`distancia_km`, `isocrona_min`) para que el consumidor filtre por lo que le sirva.

**Por qué la provincia y no el radio:** Málaga capital está a **~160 km** de Sevilla. Un radio de 100 km corta la provincia por la mitad (Antequera a ~130 km, Málaga capital fuera; Ronda al borde). La movilidad real (remoto, híbrido) justifica incluirla; el tiempo de viaje se **declara**, no se decide.

**Por qué esto cambia la escala del proyecto:** Málaga capital tiene un tejido tecnológico mayor que Sevilla (PTA / Málaga TechPark, Polo Nacional de Contenidos Digitales, Polo Digital). El universo a censar y el reparto de agentes **deben recalcularse en Fase 0** con el conteo DIRCE de ambas provincias. **No repartir 50/50 a ciegas.**

| Campo | Valores | Fuente |
|---|---|---|
| `distancia_km` | float | haversine desde 37.3891,-5.9845 |
| `isocrona_min` | 30 / 45 / 60 / 90 / >90 | **etiqueta, no filtro** (ver §5.1) |
| `ambito` | `SEVILLA` / `MALAGA` | point-in-polygon provincial — **Dependencia de Fase 0, ver §5.1** |
| `municipio`, `provincia` | texto | del propio registro o geocodificación inversa |

**Coronas operativas** (para repartir trabajo entre agentes):

**Provincia de Sevilla (INE 41)**
- **C0** — Sevilla capital (11 distritos). Prioridad máxima.
- **C1** — 0-20 km: Dos Hermanas, Alcalá de Guadaíra, Mairena del Aljarafe, Camas, Tomares, Bormujos, San Juan, Coria, Castilleja de la Cuesta, Gelves, Palomares, La Rinconada, Utrera, Carmona, Espartinas, Gines, Salteras, Santiponce, Valencina, La Algaba, Sanlúcar la Mayor, Almensilla, Bollullos, Villanueva del Ariscal, Umbrete, Pilas, Benacazón, Aznalcázar, La Puebla del Río, Guillena, Brenes, Alcalá del Río, Mairena del Alcor, El Viso del Alcor, Castilleja de Guzmán, Olivares, Gerena, Isla Mayor, Villamanrique, Aznalcóllar, Albaida, Huévar, Carrión, Castilleja del Campo.
- **C2** — resto de la provincia: Écija, Osuna, Morón, Marchena, Estepa, Arahal, Lebrija, Las Cabezas, Cazalla, Constantina, Cantillana, Lora del Río, Peñaflor, Fuentes de Andalucía, La Luisiana, Paradas, El Coronil, Montellano, Puerto Serrano, Prado del Rey, Alcalá del Valle…

**Provincia de Málaga (INE 29)** — provincia entera, no solo el borde de los 100 km
- **M1** — Málaga capital + área metropolitana: Torremolinos, Benalmádena, Fuengirola, Mijas, Marbella, Rincón de la Victoria, Alhaurín de la Torre, Cártama.
- **M2** — resto de la provincia: Antequera, Ronda, Estepona, Vélez-Málaga, Coín, Álora, Archidona, Campillos, Nerja, Torrox, Algarrobo, …

> Dos provincias suman **208 municipios** (105 + 103). Las fuentes de nombres (clústeres, directorios, parques) son **capitalinas por naturaleza**: sin un barrido municipal explícito, las coronas quedarán vacías. Es el modo de fallo nº1 de este plan (§8.1).

### 1.3 Casos frontera — regla explícita

| Caso | Regla | Código |
|---|---|---|
| Tienda de informática / reparación (lo que OSM sí tiene) | **EXCLUIR** salvo que tenga área de desarrollo propia publicada | `EXC_REVENTA` |
| ETT tecnológica | **INCLUIR** con `tipologia: ETT_TECNOLOGICA` — puede contratarte, que es el fin | — |
| Telco / banca con departamento interno | **INCLUIR** solo si publica ofertas de desarrollo dirigidas al mercado | `TELCO` |
| Consultora de negocio sin desarrollo | **EXCLUIR** | `EXC_SIN_DESARROLLO` |
| Autónomo/freelance sin local | **EXCLUIR** | `EXC_AUTONOMO` |
| Dirección = coworking con >5 empresas | **EXCLUIR** salvo sede propia verificada | `EXC_DOMICILIACION` |
| Empresa extranjera con sede comercial en Sevilla | **INCLUIR** con `tipologia: INTEGRADOR` o `PRODUCTO` según caso | — |
| Plaza de toros, cementerio, etc. con "software" en la web | **EXCLUIR** (falso positivo léxico, ya pasó en el proyecto anterior) | `EXC_FALSO_LEXICO` |

**Exclusión ≠ borrado.** Todo excluido va a `data/excluidos.json` con `motivo_exclusion`, `evidencia_url`, `fecha`. Sin esto, el captura-recaptura se corrompe recontando excluidos como "nuevos" en cada pasada.

## 2. Fuentes — verificadas y por verificar

### 2.1 Estado real medido el 18/09/2026

| Fuente | Estado | Rol en el censo |
|---|---|---|
| **Google Places API (clásica)** | ✅ key funcionando. `textsearch` OK; `details` + `reviews_sort=newest` OK → `publishTime` ISO | **Verificador + filtro de actividad**. NO fuente de descubrimiento (20 resultados/consulta) |
| **OSM / Overpass** | ✅ responde — ❌ 18 entidades en 100 km | Terciaria. Aporte marginal |
| **INE DIRCE** (CNAE 62) | ✅ responde | **Calibración del universo**: da conteos por municipio, no nombres. Define cuándo parar |
| **BORME** | ❌ 404 en la ruta probada | `[EXP]` — localizar API real en Fase 0 |
| **OpenCorporates** | ❌ requiere token de pago | Descartada |
| **Wikidata** | ❌ 40 resultados, ruido (Abengoa, Cruzcampo, US) | Descartada |
| **Axesor / Informa / Empresia** | Sin probar | `[EXP]` — alternativas comerciales a BORME |

### 2.2 Fuentes a explorar en Fase 0 (cada una es un experimento con criterio de éxito)

| ID | Fuente | Qué se espera | Criterio de éxito |
|---|---|---|---|
| E1 | **BORME** (datos abiertos BOE) por CNAE 62 | Nombres + CIF + domicilio por provincia | Encontrar endpoint real que devuelva >0 registros de Sevilla |
| E2 | **Ofertas de empleo** (InfoJobs, LinkedIn, Tecnoempleo, Manfred) | Empresas que contratan desarrollo | Extraer ≥50 empresas distintas del ámbito |
| E3 | **Parques tecnológicos** — Sevilla: PCT Cartuja, Aerópolis, Parque Tecnológico de la Salud (Granada→n/a). Málaga: **PTA (Parque Tecnológico de Andalucía)**, **PCT Málaga / Málaga TechPark**, **Polo Nacional de Contenidos Digitales**, **La Térmica/Polo Digital** | Directorios de empresas alojadas | ≥40 empresas/provincia con dirección verificable |
| E4 | **Clústeres y asociaciones** (ETICOM/ANDALUCIA.ES, Clúster TIC Andalucía, AETIC) | Listado de socios | Listado público descargable |
| E5 | **Directorios sectoriales** (Software Sevilla, Guía de empresas, Páginas Amarillas) | Nombres + contacto | ≥100 empresas |
| E6 | **GitHub orgs** con ubicación Sevilla | Empresas con repo público | ≥30 orgs con web corporativa |
| E7 | **Webs corporativas** de semilla → `clientes`/`partners` | Descubrimiento por grafo | ≥50 empresas nuevas |
| E8 | **Google News / prensa local** (rondas de financiación, premios) | Nombres con fecha | ≥20 empresas |
| E9 | **Registro de licitaciones** (PLACSP) por CPV 72xxxxx | Empresas que contratan con lo público | ≥30 empresas |
| E9b | **Clústeres de Málaga** (Málaga TechPark, Polo Digital, Andalucía Tech, Sando/Unicaja ecosistema) | Socios y empresas residentes | Listado público descargable |
| E10 | **CNAE 62 vía API de empresas** (si E1 falla) | Nombres por municipio | Evaluar coste |

**Regla:** cada fuente es un script independiente en `scripts/collectors/` que escribe a `raw/<fuente>_<fecha>.jsonl`. Ningún collector escribe a `data/`. Esto permite reejecutar y auditar.

---

## 3. Modelo de datos (esquema canónico)

`data/empresas.json` — array de fichas:

```json
{
  "id": "sev-0001",
  "nombre": "Emergya",
  "nombre_normalizado": "emergya",
  "cif": null,
  "municipio": "Sevilla",
  "provincia": "Sevilla",
  "cp": "41018",
  "direccion": "C. Luis de Morales, 32, 5º, Puerta 5",
  "direccion_completa": "C. Luis de Morales, 32, 5º, Puerta 5, 41018 Sevilla",
  "lat": 37.383353,
  "lng": -5.973442,
  "distancia_km": 0.4,
  "isocrona_min": 30,
  "telefono": null,
  "web": "https://www.emergya.com/",
  "email": null,
  "tipologias": ["CONSULTORA", "IT_GENERALISTA"],
  "cnae": null,
  "empleados_rango": null,

  "google_place_id": "ChIJXUQtz6JuEg0R7hqfXZq5FnI",
  "google_rating": 4.6,
  "google_n_resenas": 63,
  "google_business_status": "OPERATIONAL",
  "google_tipos": ["establishment", "point_of_interest"],

  "resena_mas_reciente": "2025-02-14",
  "resenas_ultimos_12m": 1,
  "actividad_reciente": true,
  "criterio_actividad": "RESENA_12M",

  "proxies_actividad": [
    {"tipo": "RESENA_GOOGLE", "fecha": "2025-02-14", "url": "google_place_id:ChIJXUQtz6JuEg0R7hqfXZq5FnI"}
  ],

  "estado": "ACTIVO",
  "confianza": "ALTA",
  "fuentes": [
    {"source": "SEED_ETICOM", "fecha_captura": "2026-09-18", "campos": ["nombre", "web"]},
    {"source": "GOOGLE_PLACES", "fecha_captura": "2026-09-18", "campos": ["lat", "lng", "direccion", "google_rating"]}
  ],
  "n_fuentes_independientes": 2,
  "flags": []
}
```

### 3.1 Campos de procedencia (obligatorios, heredados del proyecto anterior)

- `fuentes[]` — nunca una sola; `campos` indica qué aportó cada una
- `n_fuentes_independientes` — conteo para captura-recaptura
- `confianza` — `ALTA` (≥2 fuentes + Places verificado) / `MEDIA` (2 fuentes) / `BAJA` (1 fuente)
- `flags[]` — `SIN_COORDS`, `CERRADO_PROBABLE`, `DOMICILIACION_SOSPECHOSA`, `DUPLICADO_POSIBLE`, `FUERA_100KM`

---

## 4. El filtro de actividad — corazón del encargo

El requisito: **"al menos una reseña en los últimos 12 meses"**.

### 4.1 Lo que se midió

```
Emergya — 63 reseñas, 4.6★
  reviews_sort=newest (API)     → 2025-02-14 | 2024-10-31 | 2024-04-11 | ...
  scraping / navegador          → "Hace 6 años" | "Hace 9 años" | "Hace 12 años"
```

Las reseñas recientes **son invisibles** por scraping: Google ordena por "más relevantes" y sirve solo las primeras ~5 de 63 sin sesión. **La API es la única vía.**

### 4.2 Implementación en tres niveles

| Nivel | Criterio | Campo | Coste |
|---|---|---|---|
| **N1** | Reseña con `publishTime` ≤ 12 meses | `resena_mas_reciente`, `resenas_ultimos_12m` | ~$0.017/empresa (Places details) |
| **N2** | Sin reseña reciente, pero `business_status=OPERATIONAL` **y** algún proxy de actividad ≤12 m | `proxies_actividad[]` | 0 (crawl web) |
| **N3** | Ni N1 ni N2 | `actividad_reciente: false` → **excluido** con `motivo_exclusion: SIN_ACTIVIDAD_12M` | 0 |

**`proxies_actividad[]`** admite: `POST_RRSS`, `OFERTA_EMPLEO`, `NOTA_PRENSA`, `ACTUALIZACION_WEB` (changelog/blog), `LICITACION_ADJUDICADA`. Cada uno con `fecha` y `url` — **sin URL y fecha no cuenta**.

### 4.3 Nota crítica sobre falsos negativos

`details.reviews` devuelve **solo las 5 más recientes**. Si una empresa tiene 200 reseñas y las 5 más nuevas son de hace 3 años, el criterio N1 dice "sin actividad" correctamente. Pero si tiene **una sola reseña de hace 2 meses**, aparece primera con `reviews_sort=newest` y se captura. **El orden `newest` hace el muestreo de 5 suficiente para este filtro concreto** — no se necesita paginación.

`[EXP]` E11: verificar con 20 empresas que `reviews_sort=newest` respeta el orden en todos los casos (alguna reseña sin texto puede alterar el orden).

---

## 5. Pipeline técnico

```
raw/*.jsonl  (collectors, uno por fuente)
      │
      ▼
scripts/merge_fuentes.py     → dedupe por (nombre_normalizado, municipio) + fuzzy + coords
      │                         genera candidatos con n_fuentes_independientes
      ▼
scripts/verificar_places.py  → Places textsearch (nombre limpio, SIN municipio*) + details
      │                         → enriquece: coords, dirección, rating, tipologías Google
      │                         → aplica filtro N1 (publishTime)
      ▼
scripts/clasificar.py        → tipologías + CNAE + casos frontera + exclusiones
      │
      ▼
scripts/actividad.py         → N2: crawl web/RRSS para proxies (solo los que fallaron N1)
      │
      ▼
data/empresas.json           → dataset canónico
data/excluidos.json          → con motivo + evidencia + fecha
      │
      ▼
scripts/build_html.py        → index.html (ÚNICA vía de escritura, heredado)
```

\* **Medido:** `"CARTO Sevilla"` → `ZERO_RESULTS`; `"CARTO"` → 2 resultados. Concatenar el municipio **pierde** fichas. Consultar por nombre limpio y filtrar por coordenadas después.

### 5.1 Deuda técnica bloqueante descubierta el 18/09/2026

`geom.py::provincia_de()` **no está implementada**. Medición real:

- Los IDs de relación OSM son correctos (`349008` Sevilla, `5275848` Málaga — vía Nominatim)
- **`area["ref:ine"="41"]` en Overpass devuelve 0 elementos** para Andalucía → no usar
- `out geom` de una provincia entera devuelve **~106 fragmentos sueltos** (Sevilla) y **134** (Málaga), **no anillos cerrados**. Un punto en la costura entre fragmentos no cae dentro de ninguno → `provincia_de()` devuelve `None`

**Consecuencia mientras no se resuelva:** el pipeline no puede descartar fichas de Córdoba, Huelva o Cádiz que entren por fuentes amplias. Es un agujero **conocido**, no un olvido.

**Salidas, de más barata a más cara** (decidir en Fase 0):
1. **Bajar el límite por municipio (admin_level=8)** y usar una tabla fija municipio→provincia. ~208 consultas cacheadas una sola vez. **Recomendada.**
2. Ensamblar fragmentos en anillos por coincidencia de extremos. Más código, frágil.
3. Usar los límites ya ensamblados del PBF de Geofabrik (192 MB). Robusto, más setup.
4. Geocodificación inversa por ficha vía Nominatim. Evita polígonos, pero son cientos de llamadas a un servicio externo.

`haversine_km()` e `isocrona_bucket()` **sí están verificados** (`python3 scripts/geom.py`) y se pueden usar ya.

### 5.2 Rate limiting y coste

- **Places:** ~50 req/s de cuota; usar 5 req/s con backoff exponencial. Presupuesto: 500 empresas × 2 llamadas (textsearch + details) = 1.000 llamadas ≈ **$17** total. Cabe en el tramo gratuito si hay facturación.
- **Overpass:** mirror `overpass-api.de` con `User-Agent` identificativo. Si da 504, fallback a `overpass.private.coffee` (verificado OK en esta sesión).
- **Crawls web:** 1 req/s por dominio, respetar `robots.txt`.
- **Nunca** teclear la key inline en comandos → `os.environ["GOOGLE_MAPS_API_KEY"]` (la key vive en el `.env` de Hermes). Esto causó 6 intentos fallidos en esta sesión.

---

## 6. Fases y reparto entre agentes

### Fase 0 — Prerequisitos (1 agente, secuencial, BLOQUEANTE)

Resuelve los `[EXP]`. **No lanzar agentes de recolección hasta cerrar esto.**

| Tarea | Entregable | Criterio de éxito |
|---|---|---|
| 0.1 | `scripts/collectors/` esqueleto + helper común (`http_get` con backoff, `write_raw`) | Un collector de prueba escribe jsonl válido |
| 0.2 | `scripts/geom.py`: haversine + isócrona + point-in-polygon | Test con Puerta de Jerez → 0 km; Carmona → ~30 km |
| 0.3 | **E1 BORME** | Endpoint real que devuelva >0 registros de Sevilla |
| 0.4 | **E11 orden de reviews** | 20 empresas: `newest` siempre ordenado descendente |
| 0.5 | **INE DIRCE** scrapeado a CSV | Conteo de empresas CNAE 62 por municipio y tramo de asalariados |
| 0.6 | Semilla inicial: empresas conocidas con `place_id` (Emergya, CARTO, …) | ≥20 fichas de prueba end-to-end |

**Salida de Fase 0:** `informes/fase0.md` con el universo estimado (DIRCE) y qué fuentes quedan vivas. **Si DIRCE dice 400 empresas y las fuentes vivas dan 50, el plan se revisa antes de lanzar 12 agentes.**

### Fase 1 — Recolección masiva (N agentes en paralelo)

Un agente por **combinación fuente × provincia** (7 fuentes vivas × 2 provincias ≈ **14 agentes**), todos escribiendo a `raw/<fuente>_<provincia>_<fecha>.jsonl`. **Independientes entre sí** → paralelizable sin conflictos.

> El tejido de Málaga capital es considerablemente mayor que el de Sevilla (PTA + Málaga TechPark + Polo Digital). **No repartir agentes 50/50 a ciegas**: dimensionar con el conteo DIRCE de §0.5, que da el peso relativo de cada provincia.

Cada agente:
1. Lee `scripts/AGENTE_TEMPLATE.md` (esquema de salida, rate limits, política de errores)
2. Escribe `raw/<fuente>_<fecha>.jsonl`
3. Devuelve **solo** un resumen: nº fichas, fuentes de evidencia, bloqueos
4. **No** toca `data/` ni `index.html`

### Fase 2 — Fusión y deduplicación (1 agente, secuencial)

`merge_fuentes.py`. Reglas de dedupe:
- Igual `nombre_normalizado` + igual municipio → mismo
- Igual coords ±50 m → mismo
- Fuzzy `rapidfuzz.ratio > 90` → revisar, no fusionar automáticamente
- Distinto municipio + misma dirección → **bandera**, no fusión (fue el defecto D3 del proyecto anterior)

### Fase 3 — Verificación y filtro de actividad (paralelizable por lotes)

`verificar_places.py` sobre el dataset fusionado. Aquí cae el corte de los 12 meses. **Requiere la key.**

### Fase 4 — Clasificación y fronteras (1-2 agentes)

Tipologías, CNAE, casos frontera de §1.3. Los casos frontera **deben ir a `excluidos.json` con evidencia**, nunca borrarse.

### Fase 5 — Cierre y captura-recaptura (1 agente)

Chao1 con las fuentes que aportaron ≥1 ficha. Criterio de parada: si las últimas 3 fuentes aportan <5% de fichas nuevas, se declara cubierto. **Documentar el % alcanzado respecto a DIRCE.**

### Fase 6 — Publicación (1 agente)

`build_html.py` (heredado), `AVISO.md`, README, push a GitHub privado.

---

## 7. Definición de "hecho" (criterios de aceptación)

1. `data/empresas.json` con **procedencia completa** en cada ficha (ninguna sin `fuentes[]`)
2. Cada ficha tiene `lat`/`lng` verificados o `flag: SIN_COORDS` con motivo
3. `criterio_actividad` presente en **todas** las fichas — ninguna sin decisión registrada
4. `data/excluidos.json` con motivo + URL de evidencia + fecha en **todos** los casos
5. Cobertura declarada como **% del universo DIRCE desglosado por provincia** (Sevilla / Málaga), no como número absoluto agregado
6. `index.html` generado por script desde JSON (cero edición manual)
7. `AVISO.md` con finalidad, fuentes, RGPD y procedimiento de retirada
8. **Cero fichas fuera de las provincias 41/29** — depende de resolver §5.1
8. Repo privado, sincronizado, con la estructura de §5

---

## 8. Riesgos

| Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| OSM-céntrico → censo de 12 fichas | **Alta si no se lee §0** | Crítico | OSM es terciaria por diseño; DIRCE calibra |
| Cuota Places agotada a mitad | Media | Alto | Presupuesto por lotes; checkpoint en `data/`; reanudable |
| Fuentes de nombres insuficientes | **Media-alta** | Crítico | Fase 0 es bloqueante: si las fuentes vivas no cubren ≥30% de DIRCE, replantear antes de gastar agentes |
| Duplicados por nombre comercial vs razón social | Alta | Medio | Dedupe por coords + CIF, no solo por nombre |
| Agente inventa datos para "completar" | Media | Crítico | Regla: **sin URL de evidencia no hay campo**. Revisión adversarial en Fase 5 |
| Falsos positivos léxicos ("software" en web de otro sector) | Alta | Bajo | `EXC_FALSO_LEXICO` documentado |
| Radio 100 km mete Córdoba/Huelva/Málaga | Segura | Medio | La isócrona lo resuelve; no recortar, etiquetar |

### 8.1 Pre-mortem (resumen)

**Fallo más probable:** el censo acaba como "Málaga capital + Sevilla capital" con las provincias vacías por detrás, presentado como censo provincial. Las fuentes de nombres (clústeres, directorios, parques) son **capitalinas por naturaleza**; la provincia de Málaga tiene 103 municipios y la de Sevilla 105, y las coronas no aparecen en ninguna parte — igual que pasó en el proyecto anterior (21/46 municipios).

**Riesgo añadido de Málaga:** el tejido de Málaga capital es mayor y más "tech-branded" (PTA, Polo Digital) que el de Sevilla. Sin calibrar por DIRCE, los agentes malagueños producirán más fichas que los sevillanos y el censo quedará **desbalanceado sin que nadie lo note**. Solo el conteo de §0.5 permite afirmar "cubrimos X% en cada provincia".

**Fallo más peligroso:** que un agente rellene huecos con datos plausibles. El proyecto anterior ya tuvo 36 emails propagados y 11 coordenadas descuadradas que exigieron una auditoría completa. **Con 500 fichas y 12 agentes en paralelo, una Fabricación silenciosa es indistinguible de un dato bueno** hasta la auditoría final.

**Asunción oculta más grande:** que exista un registro consultable de empresas de software de Sevilla. **No existe** (verificado: ACEIA no tiene equivalente, OpenCorporates es de pago, Wikidata es ruido). Todo el censo depende de **reconstruir** ese registro desde fuentes dispersas — eso es más caro y más incompleto de lo que sugiere "replicar centros_compatibles".

**Revisión concreta:** Fase 0 bloqueante + criterio de aceptación medido contra DIRCE, no contra sí mismo.

---

## 9. Presupuesto

| Concepto | Coste |
|---|---|
| Google Places (~1.300-2.000 llamadas, 2 provincias) | ~22-34 $ (dentro del tramo gratuito de 10.000/mes con facturación) |
| Todo lo demás | 0 $ |
| Agentes | Fase 1: **~14 en paralelo** (7 fuentes × 2 provincias). Fases 3-4: por lotes. Total ~25-30 ejecuciones |

> El tramo gratuito de Places (10.000 llamadas/mes) **cubre de sobra** el censo aunque Málaga duplique el volumen. El límite real es el dimensionado de agentes, no el dinero.

---

## 10. Reutilización explícita (NO reinventar)

Antes de escribir cualquier script, comprobar si ya existe:

| Necesidad | Qué usar | Dónde |
|---|---|---|
| Captura web con retry/backoff | `web-content-acquisition` (skill) | `skill_view` |
| Geocodificación / direcciones | MCP `gmaps` | herramientas disponibles |
| Plantilla de collector + rate limit | `centros_compatibles/scripts/baseline_extract.py`, `collectors/*` | repo existente |
| Point-in-polygon provincia | `centros_compatibles/scripts/point_in_provincia.py` | repo existente |
| Generador HTML desde JSON | `centros_compatibles/scripts/build_html.py` | repo existente |
| Auditoría de coordenadas | `centros_compatibles/scripts/auditoria_coords_v2.py` | repo existente |
| Chao1 / captura-recaptura | `centros_compatibles/PLAN_OSINT_ACADEMIAS.md` §7.5 | repo existente |
| Esquema de procedencia | `centros_compatibles/data/centros.json` | repo existente |

**Regla Ponytail:** si el 90% de un script ya existe en `centros_compatibles`, se copia y se adapta. No se escribe de cero.

---

## 11. Orden de ejecución

```
Fase 0 (BLOQUEANTE, 1 agente)
   │  ← aquí se decide si el plan sigue en pie
   ▼
Fase 1 (9 agentes en paralelo, uno por fuente)
   ▼
Fase 2 (fusión — 1 agente)
   ▼
Fase 3 (verificación + filtro 12m — por lotes)
   ▼
Fase 4 (clasificación — 1-2 agentes)
   ▼
Fase 5 (Chao1 + auditoría adversarial — 1 agente)
   ▼
Fase 6 (publicación — 1 agente)
```

---

## Anexo A — Errores ya cometidos en esta sesión (para no repetirlos)

| Error | Lección |
|---|---|
| Leer `HTTP 200` como éxito | Google devuelve **200 en errores**. Leer el campo `status` del body |
| Concluir "key inválida" tras un fallo | `REQUEST_DENIED/invalid` sale **también con la key mal pegada**. Pasarla por fichero, no inline |
| Afirmar "CPU verificada" sin comprobar el cuerpo | Reportar solo lo que el cuerpo de la respuesta dice |
| `"Nombre Municipio"` en Places | Da `ZERO_RESULTS`. Consultar **nombre limpio** |
| Asumir que OSM sirve porque funcionó con colegios | Sectores distintos → cobertura OSM distinta. **Medir siempre** |
| Confundir "se descargó" con "funciona" | Los polígonos se bajaron (106 fragmentos) y di por bueno `provincia_de()` sin probar un punto. **Probar el caso feliz antes de dar algo por hecho** |
| Usar `area["ref:ine"]` en Overpass | Devuelve 0 elementos en Andalucía. Los IDs de relación sí funcionan |
| Tratar fragmentos como anillos | `out geom` no devuelve polígonos cerrados. Un punto en la costura falla silenciosamente devolviendo `None`, no un error |

## Anexo B — Comandos de referencia

```bash
# La key se lee del entorno, NUNCA inline
set -a; . /root/.hermes/.env; set +a

# Places textsearch (nombre LIMPIO, sin municipio)
curl -sG "https://maps.googleapis.com/maps/api/place/textsearch/json" \
  --data-urlencode "query=$NOMBRE" \
  --data-urlencode "key=$GOOGLE_MAPS_API_KEY" | jq -r '.status, (.results[] | "\(.name) | \(.place_id)")'

# Places details con reseñas ordenadas por fecha (EL filtro de 12 meses)
curl -sG "https://maps.googleapis.com/maps/api/place/details/json" \
  --data-urlencode "place_id=$PLACE_ID" \
  --data-urlencode "fields=name,rating,user_ratings_total,reviews,business_status" \
  --data-urlencode "reviews_sort=newest" \
  --data-urlencode "key=$GOOGLE_MAPS_API_KEY" | jq -r '.result.reviews[].time'

# Overpass con User-Agent identificativo (sin él: 406 o 504)
curl -s -X POST "https://overpass-api.de/api/interpreter" \
  -H "User-Agent: censo-software-sevilla/1.0 (julio@cabanillas.dev)" \
  --data 'data=[out:json][timeout:60];nwr["office"="it"](around:100000,37.3891,-5.9845);out center tags;'

# Por provincia (mejor que radio: no corta Málaga)
curl -s -X POST "https://overpass-api.de/api/interpreter" \
  -H "User-Agent: censo-software-sevilla/1.0 (julio@cabanillas.dev)" \
  --data-urlencode 'data=[out:json][timeout:90];
area["ref:ine"="41"]->.sev; area["ref:ine"="29"]->.mal;
(nwr["office"="it"](area.sev); nwr["office"="it"](area.mal);
 nwr["craft"="software_development"](area.sev); nwr["craft"="software_development"](area.mal);
 nwr["office"="company"]["company"="software"](area.sev); nwr["office"="company"]["company"="software"](area.mal);
); out center tags;'
```
