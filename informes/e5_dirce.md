# E5 — DIRCE / INE: denominador de empresas CNAE 62 en Sevilla (41) y Málaga (29)

**Fecha de consulta:** 2026-09-18
**Fuente:** INE — Explotación Estadística del Directorio Central de Empresas (operación `DIR`, id 43), Tempus3 API.
**Año de los datos:** 2025 (última referencia publicada; `Ultima_Modificacion` = 2025-12-11).

---

## ⚠️ AVISO METODOLÓGICO — leer antes de usar estos números

La única tabla del DIRCE que cruza **provincia × división CNAE × tramo de asalariados** es la
**tabla 301**, y mide **LOCALES (establecimientos), NO EMPRESAS**:

> *"Locales por provincia, actividad principal (divisiones CNAE 2009) y estrato de asalariados."*
> (título verificado en `https://www.ine.es/jaxiT3/Tabla.htm?t=301`)

**Consecuencia:** una empresa con varias sedes en la misma provincia cuenta **varias veces** en la 301.
El sesgo es material y está medido con los propios datos del INE:

- Totales provinciales (todos los CNAE), año 2025:
  - **Málaga:** Empresas = 142.401 (tabla 39374) · Locales = 164.412 (tabla 306) → locales ×1,15
  - **Sevilla:** Empresas = 121.706 (tabla 39374) · Locales = 141.889 (tabla 306) → locales ×1,17

Por tanto **el total de locales CNAE 62 SOBRESTIMA el número de empresas CNAE 62 en ~15 %**.

**No existe** en el DIRCE público una tabla "**Empresas** por provincia × división CNAE × tramo de asalariados"
(se revisaron las 30 tablas de la operación `DIR`). Lo más cercano:
- Tabla **39371** — Empresas × actividad (grupos CNAE) × tramo, pero **solo nacional**.
- Tabla **39374 / 73022** — Empresas × provincia × tramo, **sin CNAE**.
- Tabla **302 / 73021** — Empresas × provincia × condición jurídica, **sin CNAE ni tramo**.

**Recomendación de uso del denominador:** usar el total de locales CNAE 62 y **declararlo como
cota superior** del universo empresarial, o aplicar el factor de corrección locales→empresas por
provincia (÷1,15 Málaga, ÷1,17 Sevilla) y marcar el resultado como estimación. NO presentar los
locales como "empresas" sin esta nota.

---

## Totales CNAE 62 (división 62: programación, consultoría y otras actividades informáticas)

| Provincia | Locales CNAE 62 (tramo Total) | Estimación empresas (÷factor locales/empresas) |
|---|---|---|
| **Sevilla (41)** | **1.298** | ≈ 1.109 (÷1,17) |
| **Málaga (29)** | **2.195** | ≈ 1.909 (÷1,15) |

Málaga tiene **~69 % más** actividad CNAE 62 que Sevilla (2.195 vs 1.298 locales).
**No repartir agentes 50/50** — el peso relativo es ~ 63 % Málaga / 37 % Sevilla.

---

## Desglose por tramo de asalariados (locales, año 2025)

| Tramo | Sevilla (41) | % Sevilla | Málaga (29) | % Málaga |
|---|---|---|---|---|
| Total | **1.298** | 100 % | **2.195** | 100 % |
| Sin asalariados | 732 | 56,4 % | 1.527 | 69,6 % |
| De 1 a 2 | 223 | 17,2 % | 380 | 17,3 % |
| De 3 a 5 | 113 | 8,7 % | 82 | 3,7 % |
| De 6 a 9 | 63 | 4,9 % | 58 | 2,6 % |
| De 10 a 19 | 59 | 4,5 % | 71 | 3,2 % |
| De 20 a 49 | 57 | 4,4 % | 44 | 2,0 % |
| De 50 a 99 | 21 | 1,6 % | 20 | 0,9 % |
| De 100 o más | 30 | 2,3 % | 13 | 0,6 % |

Suma de tramos = Total en ambas provincias (1.298 y 2.195). Sin valores suprimidos por secreto
estadístico (`Secreto: false` en todas las celdas extraídas).

### Lectura para el censo (§1.3 del plan)

- **Tramo con capacidad de contratación real** (excluye "sin asalariados", que el plan ya excluye
  con `EXC_AUTONOMO`): **Sevilla 566** · **Málaga 668** locales.
- **Empresas medianas/grandes (20+ asalariados)** — las "caras" del censo (§4 del plan):
  - Sevilla: 57 + 21 + 30 = **108** locales (≈78 empresas por factor)
  - Málaga: 44 + 20 + 13 = **77** locales (≈67 empresas)
  - **Sevilla tiene MÁS empresas grandes de software que Málaga**, pese a que Málaga tiene más
    volumen total (dominado por microempresas y "sin asalariados", 69,6 %).
- Las ~732+1.527 = **2.259 unidades "sin asalariados"** son en su mayoría autónomos sin empleados:
  fuera del censo por §1.3 (`EXC_AUTONOMO`), salvo evidencia contraria.

---

## Desglose por grupos CNAE 62xx (6201 / 6202 / 6203 / 6209)

**NO DISPONIBLE a nivel provincial.** El DIRCE solo publica la **división** 62 a 2 dígitos
desagregada por provincia (tabla 301 y su gemela de CNAE-93, tabla 304). Los grupos de 3-4 dígitos
(6201, 6202, 6203, 6209) solo existen agregados a **nivel nacional** (tablas 39371 / 73019).
La tabla 4721 (municipio × CNAE) también usa solo secciones, no grupos.

Si se necesita el desglose 6201/6202 provincial, hay que acudir a una fuente comercial
(SABI, Axesor, Informa) — el INE no lo da.

---

## Tabla INE correcta

- **Tabla 301** — "Locales por provincia, actividad principal (divisiones CNAE 2009) y estrato de asalariados".
  `https://www.ine.es/jaxiT3/Tabla.htm?t=301`
- API: `https://servicios.ine.es/wstempus/js/ES/DATOS_TABLA/301?nult=1`
- Valores usados: grupo **1620 = Provincias** (id 41 Sevilla, 30 Málaga),
  grupo **1621 = Estrato de asalariados** (9 tramos),
  grupo **1623 = Actividad principal** (id **17591** = "62 Programación, consultoría y otras actividades relacionadas con la informática").
- La **tabla 3954** propuesta en el encargo NO sirve: es "Empresas por actividad principal (divisiones CNAE 2009) **y edad**" — a nivel nacional, sin provincia ni tramo de asalariados.

## Reproducción

```bash
curl -s "https://servicios.ine.es/wstempus/js/ES/DATOS_TABLA/301?nult=1" -o t301.json
# filtrar series con '62 Programación, consultoría...' y prefijo 'Sevilla.'/'Málaga.'
```
CSV generado: `data/dirce_cnae62.csv` (columna `n_empresas` contiene LOCALES — ver aviso).

## Qué NO se pudo obtener (para no inventar)

1. Empresas (no locales) CNAE 62 por provincia y tramo → no publicado por el INE.
2. Desglose 6201/6202/6203/6209 por provincia → no publicado por el INE.
