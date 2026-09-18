# Fase 2 — Fusión y deduplicación

**Fecha:** 2026-09-18 · **Script:** `scripts/merge_fuentes.py` (reejecutable)
**Salida:** `data/empresas.json` — 313 fichas

## Entrada / salida

- Fichas de entrada (raw/*.jsonl): **1108**
- Fichas de salida: **313**
- Filas absorbidas en fusión: **795** (71.8 % de la entrada)
- Fusiones (grupos con >1 fila): **78**

### Desglose por fuente (fichas que aportan)

- `E2_EMPLEO`: aporta a **892** fichas (97 en exclusiva)
- `E3_PARQUES_CARTUJA`: aporta a **90** fichas (88 en exclusiva)
- `E3_PARQUES_PTA`: aporta a **53** fichas (53 en exclusiva)
- `BORME_BOE`: aporta a **38** fichas (38 en exclusiva)
- `E8_LICITACIONES_PRENSA`: aporta a **21** fichas (21 en exclusiva)
- `E9_LICITACIONES`: aporta a **10** fichas (10 en exclusiva)
- `E6_GITHUB`: aporta a **4** fichas (4 en exclusiva)

### Ficheros leídos

- `raw/borme_cnae62_2026-09-18.jsonl`: 38 líneas
- `raw/e2_empleo_malaga_2026-09-18.jsonl`: 428 líneas
- `raw/e2_empleo_sevilla_2026-09-18.jsonl`: 464 líneas
- `raw/e3_parques_cartuja_sevilla_2026-09-18.jsonl`: 90 líneas
- `raw/e3_parques_pta_malaga_2026-09-18.jsonl`: 53 líneas
- `raw/e6_github_sevilla_2026-09-18.jsonl`: 4 líneas
- `raw/e8_licitaciones_prensa_malaga_2026-09-18.jsonl`: 12 líneas
- `raw/e8_licitaciones_prensa_sevilla_2026-09-18.jsonl`: 9 líneas
- `raw/e9_licitaciones_sevilla_2026-09-18.jsonl`: 10 líneas

## Confianza

- ALTA (≥3 fuentes): **0**
- MEDIA (2 fuentes): **2**
- BAJA (1 fuente): **311**

## Flags

- `MUNICIPIO_FUERA_PROVINCIA`: 232
- `SIN_MUNICIPIO`: 81
- `DUPLICADO_POSIBLE`: 2

### DUPLICADO_POSIBLE — 1 pares (similitud ≥ 90, **no fusionados**, requieren revisión humana)

- 93.3 % · `sev-0115` S&H Consultores ↔ `sev-0123` SHS Consultores S.L

## Cobertura frente a DIRCE 2025

- DIRCE 2025, locales CNAE 62: Sevilla 1298, Málaga 2195, total **3493**
- Censo fusionado: **313** fichas → **8.96 %** del universo DIRCE

Por provincia:

- Sevilla: 155 / 1298 = **11.94 %**
- Málaga: 158 / 2195 = **7.20 %**

## Cambios de criterio aplicados (documentados, no silenciosos)

- `municipio = "100% remoto"` **no se trata como municipio** para deduplicar: no es una ubicación y produce falsas fusiones entre provincias. Se normaliza a `municipio = null`, clave `None`, y se marca `SIN_MUNICIPIO`. Si una empresa tiene filas con municipio conocido y filas en remoto, se fusionan en una sola ficha que conserva el municipio conocido (dato real: CAS TRAINING aparecía repartida entre `Málaga`, `100% remoto` y los dos ficheros E2 — ahora es una única ficha `mal-0028` con 24 ofertas).
- Desambiguación por municipio: mismo nombre normalizado en 2+ municipios **reales** distintos son fichas separadas (agencias de empleo tipo Michael Page, UST, T-Systems, presentes a la vez en Sevilla y Málaga). Con municipio desconocido de por medio NO se desambigua: es la misma empresa. 12 nombres quedan con ≥2 fichas por este motivo, todas legítimas.
- Municipio del fichero y `provincia` del fichero discrepan a menudo en E2 (ofertas de una provincia listadas desde otra). La ficha se asigna a la provincia del fichero; si el municipio declarado es de la otra provincia se marca `MUNICIPIO_FUERA_PROVINCIA` (232 fichas). **No se descarta nada**: la decisión de ámbito es de Fase 4.
- `e3_parques_pta` da el barrio (Campanillas) en lugar del municipio → normalizado a Málaga.
- BORME: entidades HTML (`&amp;`) desescapadas y sufijos societarios eliminados del nombre normalizado.

## Pendiente (fuera de esta fase)

- Fusión por coords ±50 m: `fusionar_coords()` está implementada y es no-op hasta que Fase 3 (`verificar_places.py`) rellene `lat`/`lng`.
- El % sobre DIRCE es una **cota inferior**: E2 sólo captura quien publica ofertas y sólo de dos portales; faltan fuentes (Google Places, clusters, colegios profesionales). No es la cifra final del censo.
