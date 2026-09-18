# ADDENDUM 01 — Incorporar la provincia de Huelva (INE 21)

> Añadido a `PLAN_CENSO_SOFTWARE.md`. No lo sustituye: el plan original sigue
> válido para Sevilla (41) y Málaga (29). Este documento describe **solo el
> diferencial**.

---

## 0. Resumen ejecutivo

| | Valor |
|---|---|
| Ámbito nuevo | Huelva, INE **21** |
| Universo (DIRCE CNAE 62, 2025) | **111 locales** |
| Fichas actuales de Huelva | **0** (ni en el censo ni en los 103 excluidos) |
| Descargas nuevas | **0** — el PBF `andalucia-latest.osm.pbf` ya contiene Huelva |
| Constantes a tocar | **4** |
| Agentes necesarios | **2** (no 12: ver §3) |
| Presupuesto Places | ~**3 €** |

**Huelva no es una tercera provincia del tamaño de las actuales: son 111 locales
frente a 1.298 (Sevilla) y 2.195 (Málaga). Es el 3,1% del ámbito nuevo.**
Eso no reduce el trabajo a la mitad — lo reduce a una tarde.

---

## 1. Por qué Huelva es cualitativamente distinto

Datos del DIRCE (tabla 301, CNAE 62, 2025), leídos del INE, no supuestos:

| Provincia | Locales | Sin asalariados | 6-9 | 10-19 | 20-49 | 50-99 | 100+ |
|---|---|---|---|---|---|---|---|
| Sevilla | 1.298 | 732 | 63 | 59 | 57 | 21 | 30 |
| Málaga | 2.195 | 1.527 | 58 | 71 | 44 | 20 | 13 |
| **Huelva** | **111** | **67** | **7** | **3** | **3** | **0** | **0** |

Consecuencias directas, todas derivadas de esa tabla:

1. **Cero empresas de más de 50 asalariados.** No hay sede corporativa tipo
   Cartuja ni PTA. La fuente `E3_PARQUES` (parques tecnológicos) **no aplica**:
   en Huelva no hay un parque tecnológico con directorio público de empresas.
2. **60% son autónomos** (67/111). Un autónomo sin local no tiene ficha de
   Google Maps → **el criterio «reseña en 12 meses» va a fallar por ausencia de
   ficha, no por inactividad**. Esto es la limitación principal y hay que
   declararla, no parchearla.
3. **La cola larga es el censo entero.** Con 111 objetivos, la estrategia de
   «triangular 6-9 fuentes y quedarse con el 4%» es un error de escala: aquí se
   puede aspirar a **cobertura mucho mayor** con el mismo esfuerzo.

---

## 2. Lo que NO hay que hacer (peldaños 1-2 de la escalera)

| Tentación | Por qué no |
|---|---|
| Refactorizar los collectors para soportar N provincias | Ya lo hacen: `_common.fichas(rows, fuente, provincia, fecha)` recibe la provincia por parámetro. Huelva es **un valor más**. |
| Descargar un PBF de Huelva | Geofabrik no lo sirve por provincia. Y `andalucia-latest.osm.pbf` (194 MB, ya usado) **ya contiene Huelva**. |
| Re-colectar Sevilla y Málaga | El censo actual no cambia. Solo se **re-filtra** `excluidos.json` (§4.1). |
| Montar un pipeline nuevo | Es el mismo, con otro `ambito`. |
| 12 agentes en paralelo | §3. |

---

## 3. Reparto de trabajo — 2 agentes, no 12

El reparto de la Fase 1 original (6 fuentes × 2 provincias = 12 agentes) se
justificaba por volumen: 1.108 fichas crudas. Huelva son 111 locales
**totales**. Lanzar 12 agentes para 111 objetivos es el 90% de los agentes
compitiendo por el mismo dato y solapándose en el dedupe.

| Agente | Fuente | Qué busca | Salida |
|---|---|---|---|
| **H1** | BORME (API BOE) | Constituciones CNAE 62 en Huelva, 12-24 meses | `raw/borme_cnae62_huelva.jsonl` |
| **H2** | Empleo (Tecnoempleo/InfoJobs) + GitHub | Ofertas con municipio Huelva + devs con ubicación Huelva | `raw/e2_empleo_huelva.jsonl`, `raw/e6_github_huelva.jsonl` |

Ambos en **paralelo** (no hay dependencia entre ellos, a diferencia del `geo`
en serie de la Fase 1 — la geometría ya está resuelta y cacheada).

`E3_PARQUES` **descartado** por §1.1. `E4_CLUSTERS`, `E8_PRENSA` y
`E9_LICITACIONES`: **opcionales**, solo si H1+H2 devuelven <60 fichas. Decidir
con el dato, no antes.

---

## 4. Cambios de código — 4 constantes

Todos en `scripts/`. Ninguno es código nuevo: son entradas en mapas existentes.

### 4.1 `build_provincias.py` — añadir Huelva al PBF

```python
OBJETIVO = {"Sevilla": "Sevilla", "Málaga": "Málaga", "Huelva": "Huelva"}
```

Requiere **regenerar el cache** desde el PBF (que ya no está en `/tmp`, hay que
rebajarlo: 194 MB, ~36 s medidos). Alternativa sin descarga: el cache actual no
tiene Huelva, así que **es obligatorio rebajarlo**.

```bash
cd /tmp && curl -sLO https://download.geofabrik.de/europe/spain/andalucia-latest.osm.pbf
python3 scripts/build_provincias.py /tmp/andalucia-latest.osm.pbf
```

Añadir a los puntos de control del `__main__` (autocheck ya existente):

```python
("Huelva capital", 37.2614, -6.9447, "Huelva"),
("Lepe",           37.2547, -7.2039, "Huelva"),
("Ayamonte",       37.2133, -7.4076, "Huelva"),
("Sevilla capital", 37.3891, -5.9845, "Sevilla"),   # no debe cambiar
```

> **Riesgo medido:** `Huelva` como nombre de área administrativa nivel 6 puede
> colisionar con el municipio de Huelva (nivel 8) o con `Huelva` en otros
> `admin_level`. El filtro ya exige `admin_level == 6`, así que en principio
> está cubierto — **pero verificar que el cache resultante tiene 1 anillo
> grande (>2.000 puntos), no el municipio (~500)**. Si sale el municipio, el
> point-in-polygon rechazará Lepe y Ayamonte y el autocheck lo cazará.

### 4.2 `etiquetas.py` — las dos tablas

```python
PROV_ES = {"SEVILLA": "Sevilla", "MALAGA": "Málaga", "HUELVA": "Huelva"}
```
```python
OTRAS = (..., "Sevilla", "Málaga", "Malaga", "Huelva")   # añadir al final
```
**Ojo con el orden:** `OTRAS` es la lista de *provincias ajenas*. Huelva debe
entrar ahí para que una ficha de Sevilla con dirección de Huelva se detecte.
Y `PROV_ES` debe incluirla para que la etiqueta imprima «Huelva».

**El CP de Huelva es `21xxx`**, no 41/29 → toca la regex del CP:

```python
cps_dir = re.findall(r"\b(?:41|29|21)\d{3}\b", dire)
m = re.search(r"\b(21\d{3}|41\d{3}|29\d{3})\b", dire)   # y en el fallback
```

### 4.3 `verificar_coherencia.py`

```python
CP_PROV = {"SEVILLA": "41", "MALAGA": "29", "HUELVA": "21"}
```
El autocheck del módulo (`_demo_norm`) ya cubre tildes; **añadir un caso de
control con Huelva** no hace falta: Huelva no lleva tilde. Sí conviene añadir
`norm("Huelva") == "HUELVA"` para simetría.

### 4.4 `build_html.py` y `plantilla.html` — estadísticas y filtro

`build_html.py` calcula `sevilla` y `malaga` a mano:
```python
"sevilla": sum(1 for e in orden if e.get("ambito") == "SEVILLA"),
"malaga":  sum(1 for e in orden if e.get("ambito") == "MALAGA"),
```
→ sustituir por un contador genérico (3 líneas → 1, y no vuelve a pasar al
añadir Cádiz o Córdoba):
```python
"por_provincia": dict(Counter(e.get("ambito") for e in orden)),
```

La leyenda del mapa (`COLORES` en `plantilla.html`) tiene 2 entradas. Añadir la
tercera. **Paleta:** `#5b8cff` (Sevilla, azul) y `#2fbf71` (Málaga, verde) →
Huelva `#e8a33d` (ámbar, ya en los tokens CSS como `--warn`).

> **Accesibilidad:** ámbar vs verde en daltonismo deuteranopía son
> distinguibles; azul vs verde también. Los tres juntos siguen siendo
> separables. No hace falta cambiar la paleta existente.

El `<select id="prov">` de la plantilla: añadir `<option value="HUELVA">Huelva</option>`.

### 4.5 `cierre.py` — denominador y factor

```python
FACTOR_LOCALES = {"Sevilla": 1.17, "Málaga": 1.15, "Huelva": 1.15}
```
**El 1.15 de Huelva es un placeholder, no un dato.** El factor locales/empresas
no lo publica el INE por provincia; se estimó comparando dos tablas para
Sevilla y Málaga. Para Huelva **no hay ese cálculo hecho**: usar 1.15 (la
media) y **marcarlo `ponytail:` como aproximación**, o aceptar el sesgo y
declararlo. No inventar un tercer valor.

Añadir la fila de Huelva a `data/dirce_cnae62.csv` (datos reales, ya extraídos):

```csv
Huelva,62,Total,111
Huelva,62,Sin asalariados,67
Huelva,62,De 1 a 2 asalariados,23
Huelva,62,De 3 a 5 asalariados,8
Huelva,62,De 6 a 9 asalariados,7
Huelva,62,De 10 a 19 asalariados,3
Huelva,62,De 20 a 49 asalariados,3
Huelva,62,De 50 a 99 asalariados,0
Huelva,62,De 100 o más asalariados,0
```

### 4.6 Reaprovechar los 103 excluidos (regla de la escalera)

Con Huelva en el ámbito, **re-ejecutar el filtro de ámbito sobre
`data/excluidos.json`**. Hoy tienen `motivo_exclusion: EXC_FUERA_AMBITO` y
`provincia` **null** (se asignó tras el filtro y quedó vacía). Recorrerlos con
`provincia_de(lat, lng)` puede devolver `Huelva` en algunos casos.

**Medido: 0 de los 103 son de Huelva.** Pero 31 aparecían con municipio Málaga y
29 con Sevilla — el filtro actual los descartó por coordenada. Al ampliar el
ámbito **no cambian**, así que esta re-ejecución es barata y probablemente no
devuelva nada. **Hacerla igual** (una pasada, segundos) para no afirmar sin
comprobar. Si devuelve 0, se documenta y se cierra.

---

## 5. Fases

| Fase | Qué | Bloqueo | Estado |
|---|---|---|---|
| **A0** | Cambios de código §4 (4 constantes + cache PBF + DIRCE Huelva) | Ninguno | **HECHA** |
| **A1** | Colecta con 2 agentes (§3) | A0 | en curso |
| **A2** | Merge al censo existente | A1 | pendiente |
| **A3** | Places + filtro 12 meses sobre las fichas de Huelva | A2 | pendiente |
| **A4** | Etiquetas + PDF + re-publicación | A3 | pendiente |

**A0 bloquea A1 por una razón concreta:** los agentes validan sus fichas con
`provincia_de()`. Si el cache no tiene Huelva, toda ficha onubense sale
`None` y se descarta en silencio — exactamente el fallo que ya ocurrió con
Málaga. **No lanzar A1 antes de que el autocheck de `build_provincias.py`
pase con los 3 puntos de Huelva.**

---

## 5bis. A0 ejecutada — lo que se midió (no lo que se supuso)

Se ejecutó A0 y el resultado **corrigió el addendum en 4 puntos**. Se anota aquí
porque el plan original se escribió sin estos datos.

### 5bis.1 El cache de producción no tenía Huelva, y no se podía regenerar

`_extraer()` filtraba durante el parseo (`OBJETIVO.get(name)` → `return`), así que
el cache `~/.cache/censo_software/provincias_and.json` solo tenía Sevilla y Málaga.
Añadir una provincia obligaba a **re-parsear los 194 MB** del PBF. Arreglado: se
ensamblan las 8 andaluzas y **`OBJETIVO` filtra al leer**. Coste pagado una vez
(42 s), y Cádiz/Córdoba ya no lo repiten.

### 5bis.2 `Huelva` resuelve a provincia, no a municipio — riesgo #1 descartado

`provincia_de()` **19/19** puntos: 7 de Huelva (capital, Lepe, Ayamonte, Aracena,
Valverde, Almonte, Cortegana) resuelven a `Huelva`; Córdoba, Cádiz y Badajoz dan
`None`. Un punto en Cádiz da `None` **a propósito**.

### 5bis.3 El PBF trae un `Córdoba - Sevilla` de 163 puntos

Relación con nombre compuesto (enclave de límite), sin `ref_ine`. Es la
explicación de los `None` históricos en la costura. Se guarda pero no se usa.

### 5bis.4 `TECNO_PROV[HUELVA] = 277` era **TERUEL** — el error más caro evitado

El código de Tecnoempleo **no es el INE**. Medido del `<select name="pr">`:
`Huelva=255` (277 es Teruel, 235 Almería, 244 Cádiz). Haberlo dejado habría
metido ofertas de Teruel etiquetadas como Huelva.

### 5bis.5 🔴 **E2/Tecnoempleo NO sirve para Huelva** — corrige §3

Medición de las 3 provincias con el mismo collector:

| Provincia | Fichas | `100% remoto` | Con municipio real |
|---|---|---|---|
| Sevilla | 424 | 329 (77,6 %) | **95** |
| Málaga | 388 | 329 (84,8 %) | **59** |
| Huelva | 332 | 329 (99,1 %) | **3** |

Las **329 remotas son idénticas en las 3** — es el mismo pool nacional servido a
cada consulta de provincia. Para Huelva la fuente aporta **3 fichas de 332**
(0,9 %). El raw se borró: no se mergea ruido.

**Consecuencia para §3:** el addendum asignaba a Huelva el mismo E2 que a las
otras dos. **Ya no.** La fuente principal de Huelva pasa a ser BORME + búsquedas
locales. El agente de empleo se reduce a la papelera.

### 5bis.6 BORME sí funciona, y da la primera empresa onubense real

Con `21` añadido al dict de provincias (antes `{"41","29"}`), 10 días de BORME dan
**Huelva 1 / Sevilla 5 / Málaga 8** — proporción coherente con 111 vs 1.298 vs 2.195.

```
ATLANTYQA SOVEREIGN SYSTEMS SL. | C/ BARCO, 4 Ptl.6 1º b | BORME-A-2026-172-21
```

Domicilio en Huelva capital, objeto social de programación y SaaS, evidencia BOE.
**Imprimible** (CP 21xxx, dirección postal). Es exactamente el perfil que E2 no
encontró.

### 5bis.7 Un excluido resucita: `sev-0117 Seabery`

`provincia_de()` pasa ahora su coordenada a `Huelva` (2,5 km de Huelva capital,
84 km de Sevilla). Reverse geocoding externo (Nominatim) confirma
`Calle Doctor Emilio Haya Prats, Huelva, 21005`.

**Pero la ficha está contaminada:** su dirección es `calle Inca Garcilaso, 3,
Sevilla, 41092` (PT Cartuja, 84 km) y su web `seaberyat.com` es de la Seabery
sevillana. Es una **colisión de dos empresas homónimas**. No se puede imprimir
(`etiqueta()` devuelve `None` porque la dirección declara provincia ajena) —
y eso es **correcto**: enviar esa carta a Cartuja sería un error.

**Regla nueva para el handoff (§3):** si el nombre existe en Sevilla/Málaga con
otra dirección, comprobar que la coordenada y la dirección **concuerdan** antes de
escribir la ficha. Homónimos entre provincias son un modo de fallo real, no
hipotético.

---

## 6. Métrica de éxito (falsable)

| # | Criterio | Cómo se comprueba |
|---|---|---|
| 1 | `build_provincias.py` autocheck: 15/15 puntos (los 12 actuales + 3 de Huelva) | salida del script |
| 2 | Huelva tiene ≥1 anillo en el cache, >2.000 puntos (provincia, no municipio) | `python3 -c` sobre el cache |
| 3 | `verificar_coherencia.py` pasa con `HUELVA` incluido | salida del script |
| 4 | Fichas con `ambito == "HUELVA"` ≥ 40 (36% de 111) | `empresas.json` |
| 5 | Cobertura Huelva declarada explícitamente, sea cual sea | `cierre.py` |
| 6 | Etiquetas con CP `21xxx` presentes en el PDF; 0 etiquetas con CP de otra provincia | `pdf_check.py` + grep |
| 7 | 0 fichas de Huelva sin `evidencia_url` | `empresas.json` |
| 8 | Las 2 provincias actuales no regresan (Sevilla 102, Málaga 28) | `index.html` |

**Criterio 4 es el techo realista, no una aspiración:** Huelva tiene 111 locales
y 67 son autónomos sin local físico. Sacar 40 (36%) ya es **4× la cobertura de
Málaga** (1,5%). Si sale menos, el criterio **falla** y hay que decirlo, no
rebajarlo.

---

## 7. Riesgos

| Riesgo | Probabilidad | Mitigación |
|---|---|---|
| ~~`Huelva` en el PBF resuelve al **municipio**~~ | ~~Media~~ | **DESCARTADO — 19/19 puntos. §5bis.2** |
| Los 67 autónomos **sin local** no aparecen en Places → criterio 12 meses inservible | **Alta** | Declararlo. El criterio pasa a ser «≤50% sin ficha», no «0 sin ficha» |
| 🔴 **E2 no aporta nada para Huelva** (3 de 332) | **Cierto, medido** | Sustituir por BORME + búsquedas locales. §5bis.5 |
| Huelva da menos fichas que el criterio 4 | Media | Reportar el número real. **No** relajar el criterio ni rellenar con datos plausibles |
| Homónimos entre provincias (Seabery) contaminan fichas | Media | Regla de concordancia coords/dirección en §3. §5bis.7 |
| El factor locales/empresas 1.15 de Huelva es un placeholder | Alta | Marcarlo `ponytail:` en `cierre.py` |
| Solape con las 103 excluidas | Baja (medido 1: Seabery) | Re-ejecutado. §5bis.7 |

---

## 8. Lo que este addendum NO hace

- No amplía a Cádiz, Córdoba, Granada, Almería o Jaén. El plan queda abierto a
  ellas **solo si esta ejecución valida el patrón** (4 constantes + 2 agentes).
  Si añadir Huelva sale tan barato como parece, añadir las 5 andaluzas
  restantes es el mismo trabajo repetido — pero **se decide después de ver el
  resultado de Huelva**, no antes.
- No cambia el modelo de datos. `ambito` ya es un campo de texto libre; Huelva
  es un valor nuevo, no un esquema nuevo.
- No toca la arquitectura del frontend. Es HTML + CSS + un generador.
- No promete cobertura. Promete un número honesto y su cota inferior.
