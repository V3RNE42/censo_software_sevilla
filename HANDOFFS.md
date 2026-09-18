# HANDOFFS — Fase 1 (recolección en paralelo)

Formato: YAML (handoff = instrucciones + datos → YAML gana ~15% de tokens vs JSON).
Cada bloque es autocontenido: el subagente no conoce esta conversación.

## Plantilla base (rellenar por fuente × provincia)

```yaml
goal: >
  Recolectar empresas de desarrollo de software de la provincia de <PROVINCIA>
  desde la fuente <FUENTE_ID>, escribiendo cada ficha con su URL de evidencia.

rol: "Recolector de datos OSINT — fuente <FUENTE_ID>, provincia <PROVINCIA>"
toolsets: [web, terminal, file]

context:
  jerarquia:
    overview: >
      Censo de empresas de desarrollo de software de las provincias de Sevilla
      (INE 41) y Málaga (INE 29). Este agente cubre UNA fuente en UNA provincia.
      Otros agentes cubren las demás fuentes en paralelo.
    overview_detalle: >
      El censo NO puede construirse desde OSM: se midió que en 100 km hay solo
      ~12 empresas reales de software en OpenStreetMap, porque a diferencia de
      colegios o comercios, las empresas de software casi no se mapean. Por eso
      cada fuente de nombres vale por sí misma y su aporte es no solapable.
    fuentes:
      - contrato_de_salida: "scripts/AGENTE_TEMPLATE.md (LEERLO ANTES DE EMPEZAR)"
      - esquema_ficha: "PLAN_CENSO_SOFTWARE.md §3"
      - criterio_de_inclusion: "PLAN_CENSO_SOFTWARE.md §1 (regla D1-D4: las tres condiciones deben cumplirse)"

  relaciones_explicitas:
    - "Tú produces raw/<fuente>_<provincia>_<fecha>.jsonl → merge_fuentes.py lo fusiona con los demás raw/*.jsonl"
    - "NUNCA escribes en data/ ni index.html: eso lo hace el pipeline, no un agente"
    - "El peso de tu provincia se calibra con el conteo DIRCE de la Fase 0 — no infles ni recortes para igualar a la otra provincia"
    - "lat/lng van a null: los rellena verificar_places.py. No geocodifiques."

  reglas:
    - "SIN URL DE EVIDENCIA NO HAY CAMPO. Un campo sin evidencia_url se descarta. No rellenes 'lo plausible'."
    - "1 req/s por dominio; respeta robots.txt; backoff exponencial en 429/5xx, 3 reintentos y sigues"
    - "Si la fuente supera 2000 fichas, PARA y reporta bloqueo — no vuelques 20 MB"
    - "Si la fuente da 404 o no existe, repórtalo. Es una respuesta válida. Inventar fichas es el peor resultado."

  output:
    archivo: "raw/<fuente>_<provincia>_<fecha>.jsonl"
    resumen_de_vuelta: >
      fuente / provincia / fichas_escritas / con_web / bloqueos / ruta.
      NO vuelques los datos en la respuesta.
    metrica_exito:
      - "Existe el fichero y cada línea es JSON válido"
      - "Toda línea tiene evidencia_url no nula"
      - "fichas_escritas coincide con el número real de líneas"

  feedback_loop: >
    Antes de terminar, verifica y responde:
    1. ¿Cuántas líneas NO tienen evidencia_url? (debe ser 0)
    2. ¿Las empresas son de la provincia asignada, no de la vecina?
    3. ¿Alguna ficha es una tienda de informática o un centro Guadalinfo?
       (esos van a excluidos, no a raw — ver §1.3)
    Si la respuesta a 1 es >0 o a 3 es SÍ, corrige antes de volver.
```

## Fuentes y su estado (Fase 0 decide cuáles se lanzan)

| ID | Fuente | Provincia | Estado |
|---|---|---|---|
| E1 | BORME / registro mercantil | ambas | `[EXP]` localizar endpoint real |
| E2 | Ofertas de empleo (InfoJobs, Tecnoempleo, Manfred, LinkedIn) | ambas | por verificar |
| E3 | Parques tecnológicos (PCT Cartuja, Aerópolis / PTA, Málaga TechPark, Polo Digital) | ambas | por verificar |
| E4 | Clústeres TIC (ETICOM Andalucía) | Sevilla | por verificar |
| E9b | Clústeres Málaga (Málaga TechPark, Andalucía Tech) | Málaga | por verificar |
| E5 | Directorios sectoriales | ambas | por verificar |
| E6 | GitHub orgs con ubicación | ambas | por verificar |
| E8 | Prensa local (rondas, premios) | ambas | por verificar |
| E9 | Licitaciones PLACSP (CPV 72xxxxx) | ambas | por verificar |

**Nota:** E3, E4 y E9b están separadas por provincia pero comparten método. Si Fase 0 revela que una es infructuosa, se cae para las dos provincias y libera 2 agentes.

---

# HANDOFF — Fase 0 (bloqueante, 1 agente)

```yaml
goal: >
  Resolver los 7 experimentos de Fase 0 y emitir informes/fase0.md con el
  universo estimado por provincia. De esta fase depende si el plan sigue en pie.

rol: "Ingeniero de datos — validación de fuentes y calibración de universo"
toolsets: [web, terminal, file]

context:
  jerarquia:
    overview: >
      Antes de gastar ~14 agentes recolectando, hay que saber si las fuentes
      existen y cuántas empresas hay en total. El plan anterior se lanzó sin
      esto y acabó con 21/46 municipios cubiertos sin saber el porcentaje real.
    tareas:
      - id: 0.1
        que: "scripts/collectors/ esqueleto + helper http_get con backoff y write_raw"
        exito: "un collector de prueba escribe jsonl válido"
      - id: 0.2
        que: "scripts/geom.py: haversine + point-in-polygon provincia"
        exito: "Puerta de Jerez -> 0 km; Carmona -> ~30 km; assert en __main__"
      - id: 0.3
        que: "E1 localizar API real de BORME (la ruta probada da 404)"
        exito: "endpoint que devuelva >0 registros de Sevilla con CNAE 62"
      - id: 0.4
        que: "E11 validar orden de reviews_sort=newest"
        exito: "20 empresas, orden descendente siempre"
        nota: "YA VALIDADO en 5/5 empresas (Emergya, CARTO, Freepik, Sopra, Indra). Solo ampliar a 20."
      - id: 0.5
        que: "INE DIRCE: conteo de empresas CNAE 62 por municipio y tramo de asalariados, Sevilla Y Málaga"
        exito: "CSV con el universo total por provincia"
      - id: 0.6
        que: "Semilla inicial: empresas conocidas con place_id"
        exito: ">=20 fichas end-to-end por el pipeline completo"

  relaciones_explicitas:
    - "0.5 (DIRCE) define el DENOMINADOR: sin él no se puede decir 'cubrimos X%'"
    - "0.5 también fija el reparto de agentes entre provincias — no 50/50 a ciegas"
    - "0.4 y 0.6 ya están parcialmente hechos (ver nota); no repetir trabajo"
    - "Si 0.5 da un universo >> lo que las fuentes vivas pueden cubrir, el plan SE REVISA antes de Fase 1"

  reglas:
    - "No lanzar Fase 1 hasta que esta fase cierre. Es bloqueante por diseño."
    - "Las claves API se leen del entorno: os.environ['GOOGLE_MAPS_API_KEY']. NUNCA inline en el comando."
    - "Places devuelve HTTP 200 en errores: leer el campo `status` del body, no el código HTTP."
    - "Consultar Places por nombre LIMPIO, sin municipio: 'CARTO Sevilla' da ZERO_RESULTS donde 'CARTO' encuentra."

  output:
    archivo: "informes/fase0.md"
    debe_contener:
      - "Universo DIRCE por provincia (Sevilla / Málaga), CNAE 62"
      - "Qué fuentes quedan vivas y cuáles caídas"
      - "Reparto recomendado de agentes entre provincias, justificado con DIRCE"
      - "Estimación de llamadas a Places y coste"

  feedback_loop: >
    Responde antes de terminar:
    1. ¿El universo de las fuentes vivas cubre >=30% del DIRCE? Si NO, dilo — no lo tapes.
    2. ¿Sabes cuántas empresas de Málaga vs Sevilla? Si no, 0.5 está incompleto.
    3. ¿Algún dato del informe es una estimación tuya sin fuente? Márcalo como [ESTIMACION].
```
