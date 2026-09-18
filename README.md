# censo_software_sevilla

Censo de empresas de desarrollo de software en las provincias de **Sevilla (INE 41)** y **Málaga (INE 29)**.

## Estado

**Fases 0-6 completadas.** 130 empresas en el censo. Cobertura del **4,3 %** del
universo DIRCE (CNAE 62, 2025). Publicado en `index.html`.

| Fase | Resultado |
|---|---|
| 0 — Prerequisitos | DIRCE 1.298 (Sevilla) / 2.195 (Málaga) locales CNAE 62. BORME vía API `boe.es/datosabiertos/api/borme/sumario/{AAAAMMDD}`. `provincia_de()` por polígonos del PBF Geofabrik (12/12 puntos OK) |
| 1 — Recolección | 1.108 fichas crudas de 7 fuentes (empleo, parques, BORME, licitaciones, GitHub, prensa) |
| 2 — Fusión | 1.108 → 313 fichas (72 % absorbidas en deduplicación) |
| 3 — Places + actividad | 103 fuera de ámbito. **82 con reseña <12 meses** |
| 4 — Clasificación | 66 clasificadas por tipología. N2 salvó 45 fichas vía web viva |
| 5 — Cierre | Cobertura 4,3 %. Chao1 no aplicable (`f2=0`) |
| 6 — Publicación | `index.html` generado desde `data/empresas.json` |

### Resultados

- **130 empresas**, 102 Sevilla / 28 Málaga
- **123 con actividad acreditada** (78 por reseña <12 m, 45 por web viva)
- **Su 108 fichas con teléfono** y 123 con web
- **No está completo**: cubre el 4,3 % del universo. Sevilla 9,2 %, Málaga 1,5 %

### Limitaciones conocidas

- El sesgo geográfico va **contra** Málaga: el DIRCE dice 63/37 y el censo da 79/21,
  porque la fuente de empleo cubre Sevilla mucho mejor.
- **42 % de los nombres no verificables en Places** con ese nombre exacto (razón
  social ≠ nombre comercial). `data/places_cache.json` conserva 97 geocodificaciones
  erróneas que el filtro de ámbito descartó correctamente.
- Places **no clasifica** empresas de software (todas salen `establishment`); la
  tipología sale de las notas de oferta de empleo.

## Documentos

| Fichero | Qué contiene |
|---|---|
| `PLAN_CENSO_SOFTWARE.md` | El plan completo: definición operativa, ámbito, fuentes, esquema de datos, pipeline, fases, riesgos y criterios de aceptación |
| `HANDOFFS.md` | Plantillas YAML para delegar a subagentes (Fase 0 y Fase 1) |
| `scripts/AGENTE_TEMPLATE.md` | Contrato de salida de todo agente de recolección |
| `scripts/geom.py` | Geometría: haversine e isócrona **verificados**; `provincia_de()` **bloqueada** (ver §5.1 del plan) |

## Estructura

```
scripts/     collectors y utilidades
data/        dataset canónico (empresas.json, excluidos.json)
raw/         salida cruda de cada collector (jsonl)
informes/    informes de fase
```

## Lo que ya está verificado

- **Google Places (API clásica)**: `details` + `reviews_sort=newest` devuelve `publishTime` en ISO exacto. Es la **única** vía de saber si un negocio tiene reseñas recientes — el scraping y el navegador solo muestran las "más relevantes" (típicamente de hace 6-12 años). Validado en 5/5 empresas con orden descendente correcto.
- **OSM NO sirve como fuente primaria**: en 100 km hay 18 entidades de software con nombre, de las que ~12 son empresas reales (2 son centros Guadalinfo públicos, 1 es IBM). Cobertura estimada del universo: **1,5-4%**.
- **No existe un registro público consultable** de empresas de software (no hay equivalente a ACEIA). El censo se construye por triangulación multifuente.

## Dependencias bloqueantes (Fase 0)

1. `provincia_de()` sin implementar — `out geom` devuelve fragmentos sueltos, no anillos. 4 salidas documentadas en `scripts/geom.py` y §5.1 del plan.
2. Conteo INE DIRCE (CNAE 62) por provincia — sin él no hay denominador ni reparto de agentes.
3. Localizar endpoint real de BORME — la ruta probada da 404.

Requiere `GOOGLE_MAPS_API_KEY` en el entorno. Nunca inline en comandos.
