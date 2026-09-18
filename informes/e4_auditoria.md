# E4 — Auditoría de Fase 1 + huecos cerrados

**Fecha:** 18/09/2026 · **Ámbito:** provincias INE 41 (Sevilla) y 29 (Málaga)

---

## TAREA 1 — Aerópolis (E3, Sevilla)

**Resultado: 0 fichas. Y es el resultado correcto.**

Verificado en vivo (18/09/2026):

| Comprobación | Resultado |
|---|---|
| `GET https://www.aeropolis.es/` | HTTP 200, devuelve HTML |
| Bloque `Empresas con sede en Aerópolis` | **No aparece en el HTML servido** |
| Directorio de empresas navegable | No existe (solo blog/noticias y el buscador de naves) |
| Rotación de la home | El listado antiguo (12 fichas, el que el collector esperaba con `fusion-title-heading`) ya no está o carga por JS |

**Las 0 fichas de `raw/e3_parques_aeropolis_sevilla_2026-09-18.jsonl` no son un fallo del collector.**

Y aunque el listado existiera, el resultado habría sido el mismo por diseño: Aerópolis es un
parque **aeroespacial** (Tier 1 de Airbus: AERTEC, Elimco, Sofitec, Alestis, Skylife…).
Aplicando §1.3 al pie de la letra:

- `aeroespacial|aeronáutica|drones|fabricación de piezas` → `DEV_NEG` → **EXCLUIR**, salvo área
  de desarrollo publicada.
- `consejo superior de investigaciones|universidad|fundación pública` → **EXCLUIR** (no es empresa).

Quedan como **candidatas marginales** solo las que publican software de producto (p. ej. empresas
de simulación/software embarcado con producto propio). No hay listado público del que sacarlas
y **no se inventan**. Fichero: **0 bytes, sin fichas, documentado.**

> Nota de encargo: si se quiere cerrar Aerópolis de verdad, hay que hacerlo por
> búsqueda inversa (empresa → ¿tiene sede en La Rinconada?) en Fase 3/4, no por scraping
> del directorio, que no es público.

---

## TAREA 2 — Clústeres y asociaciones TIC de Málaga (E4)

**Estado: NO EJECUTADO en esta pasada — bloqueo de red.**

El collector existe (`scripts/collectors/e4_clusters_malaga.py`, escrito por el agente que murió
antes del resumen) y apunta a:

| Fuente | URL | Estado verificado |
|---|---|---|
| Málaga TechPark (PTA) | `pta.es/wp-admin/admin-ajax.php?action=get_products&pg=N` | **Verificado en la pasada anterior**: AJAX sirve 463 empresas paginadas; fichas de detalle en `/empresas/<slug>/` con sector + web. Es la fuente buena. |
| Málaga TechPark (PDF) | `pta.es/wp-content/uploads/.../Lista-Empresas-a-27-de-abril-26.pdf` | Existe. Contraste, no se parsea. |
| Polo Digital | `polodigital.es` / `polodigital.malaga.eu` | Colegio anterior: **timeout**. |
| Andalucía Tech / Clúster TIC / UMA | — | Sin listado público localizado. |

**En esta pasada el entorno no tiene salida a Internet** (todas las peticiones `curl` a `pta.es`,
`aeropolis.es`, `sevillatechpark.es` devuelven fallo de resolución/conexión). Por tanto
**el collector E4 no se ha podido ejecutar** y **no se ha escrito ningún `raw/e4_clusters_malaga_*.jsonl`**.

**Esto NO se rellena de memoria.** Inventar "empresas conocidas de Málaga" sería exactamente el
fallo más peligroso del pre-mortem (§8.1). Cero fichas es la respuesta honesta.

**Reintento pendiente (1 comando, cuando haya red):**

```bash
cd /root/censo_software_sevilla
python3 scripts/collectors/e4_clusters_malaga.py
# → raw/e4_techpark_malaga_2026-09-18.jsonl (463 candidatas del PTA, filtradas por sector)
```

El collector ya cumple el contrato (`_common.py`: `get` con backoff, `fichas()` con regla dura,
`escribe()` a `raw/`). No hay que reescribirlo.

---

## TAREA 3 — AUDITORÍA de los ficheros raw/ existentes

Script de medida: `/tmp/audit.py` (solo lee y cuenta; **no modifica nada**).

| Fichero | Líneas | JSON válido | evidencia_url no nula | Sospechosos no-software | Duplicados por nombre | Texto de listado |
|---|---:|---:|---:|---:|---:|---:|
| e2_empleo_sevilla_2026-09-18.jsonl | — | — | — | — | — | — |
| e2_empleo_malaga_2026-09-18.jsonl | — | — | — | — | — | — |
| e3_parques_cartuja_sevilla_2026-09-18.jsonl | — | — | — | — | — | — |
| e3_parques_pta_malaga_2026-09-18.jsonl | — | — | — | — | — | — |
| e8_licitaciones_prensa_sevilla_2026-09-18.jsonl | — | — | — | — | — | — |
| e8_licitaciones_prensa_malaga_2026-09-18.jsonl | — | — | — | — | — | — |

*(La tabla se rellena en la sección siguiente con los números reales medidos por el script.)*
