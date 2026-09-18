# AGENTE — contrato de salida

Todo agente de recolección lee esto antes de empezar. No hay excepciones.

## Regla dura

**Sin URL de evidencia no hay campo.** Un campo sin `evidencia_url` se descarta. No se rellena "porque es plausible". El proyecto anterior tuvo 36 emails propagados y 11 coordenadas descuadradas por exactamente eso.

## Qué escribes y qué NO

- **SÍ** — `raw/<fuente>_<provincia>_<fecha>.jsonl`
- **NO** — `data/`, `index.html`, `empresas.json`, `excluidos.json`. Esos los toca el pipeline, nunca un agente.

## Formato de línea (JSONL, una ficha por línea)

```json
{"nombre": "Emergya", "municipio": "Sevilla", "provincia": "SEVILLA", "direccion": "C. Luis de Morales, 32", "web": "https://www.emergya.com/", "telefono": null, "email": null, "cif": null, "tipologias": ["CONSULTORA"], "empleados_rango": null, "lat": null, "lng": null, "evidencia_url": "https://eticom.es/socios", "fuente": "SEED_ETICOM", "fecha_captura": "2026-09-18", "notas": null}
```

`lat`/`lng` van a `null`: los rellena `verificar_places.py`. No geocodifiques tú.

## Cómo entregas

Escribe el fichero, luego devuelve **solo** este resumen (no vuelques datos en la respuesta):

```
fuente: SEED_ETICOM
provincia: SEVILLA
fichas_escritas: 47
con_web: 31
bloqueos: ninguno
ruta: raw/seed_eticom_sevilla_2026-09-18.jsonl
```

## Límites

- 1 req/s por dominio, `robots.txt` respetado
- Backoff exponencial en 429/5xx; 3 reintentos y sigues
- Si una fuente tiene >2000 fichas, paras y reportas `bloqueos: volumen excesivo, necesita revisión` — no vuelques 20 MB en un jsonl

## Fallo esperado

Si no encuentras la fuente o da 404: **repórtalo**. `bloqueos: fuente caida, 404 en <url>` es una respuesta válida y útil. Inventar fichas para no volver con las manos vacías es el peor resultado posible.
