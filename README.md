# censo_software_sevilla

Censo de empresas de desarrollo de software en las provincias de **Sevilla (INE 41)** y **Málaga (INE 29)**.

## Estado

**Fase 0 — pendiente.** El plan está escrito y verificado en sus partes críticas; la ejecución no ha empezado.

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
