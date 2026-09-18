# Aviso legal, fuentes y metodología

## Finalidad

Este censo es un **directorio público de empresas de desarrollo de software** con sede
física en las provincias de Sevilla (INE 41) y Málaga (INE 29). Su finalidad es
informar a **personas que buscan empleo en el sector**, no evaluar ni puntuar a las
empresas listadas.

## Qué es y qué no es

**Es** un censo parcial. Cubre el **4,3 %** del universo estimado (DIRCE 2025, CNAE 62:
1.298 locales en Sevilla y 2.195 en Málaga). Está construido por triangulación de
fuentes públicas, no por consulta a un registro completo, porque **no existe un
registro público consultable de empresas de software**.

**No es** un directorio comercial, ni una base de prospección, ni una valoración.
Las valoraciones de Google se muestran como dato de actividad, no como
recomendación.

## Fuentes

| Fuente | Qué aporta | Fecha de captura |
|---|---|---|
| **Google Places API** (clásica) | Coordenadas, dirección, teléfono, web, valoración, **fecha de la reseña más reciente** | 2026-09-18 |
| **Portales de empleo** (Tecnoempleo y otros) | Nombre de la empresa ofertante, puesto | 2026-09-18 |
| **Parques tecnológicos** (PCT Cartuja, PTA Málaga) | Empresas residentes con web | 2026-09-18 |
| **BORME** (BOE datos abiertos) | Razón social y objeto social del registro mercantil | 2026-09-17 |
| **Licitaciones públicas** (PLACSP) | Empresas adjudicatarias | 2026-09-18 |
| **GitHub** | Organizaciones con ubicación declarada | 2026-09-18 |
| **Prensa local** | Rondas, premios, aperturas | 2026-09-18 |
| **INE DIRCE 2025** | Denominador: total de empresas CNAE 62 | 2025 |
| **OpenStreetMap (Geofabrik PBF)** | Límites provinciales | 2026-09-16 |

Toda ficha conserva su procedencia en el campo `fuentes[]` con la URL de
evidencia. Las fichas sin URL de evidencia se descartan en origen.

## Criterio de inclusión

Una entidad entra si cumple las tres condiciones:

1. **Actividad de desarrollo** — producto propio, servicios de desarrollo a
   terceros, CNAE 62, u ofertas de empleo para perfiles técnicos.
2. **Sede física** verificable en el ámbito. Un coworking o domiciliación no basta.
3. **Capacidad de contratación** — persona jurídica o autónomo con local.

El campo `tipologias[]` etiqueta el tipo (producto, factoría, consultora,
integrador, datos/IA, videojuegos, desarrollo, IT generalista, ETT tecnológica,
telco). Una empresa puede tener varias.

## Criterio de actividad

Se marca como activa la empresa con **al menos una reseña de Google publicada en
los últimos 12 meses**, o, si no la tiene, con **web operativa** verificada.

La fecha de reseña se obtiene de la API de Google Places ordenando por más
reciente (`reviews_sort=newest`). No se puede obtener por scraping: la interfaz
web solo muestra las reseñas "más relevantes", que en la práctica son las más
antiguas con más interacciones.

## Datos personales (RGPD)

Trata únicamente **datos de empresa**: razón social, dirección postal, teléfono y
web corporativos. Estos datos no identifican a personas físicas y su tratamiento
está amparado por el interés legítimo en informar sobre el mercado laboral
(art. 6.1.f RGPD).

No se recogen: nombres de empleados, contactos individuales, correos personales,
ni datos de las personas que firman reseñas. Las reseñas se usan **solo como
señal agregada de actividad** — se lee su fecha, no su contenido ni su autor.

## Retirada de una ficha

Cualquier empresa puede solicitar su exclusión. Escribe a **julio@cabanillas.dev**
indicando la razón social y, si es posible, la URL de su ficha. Se retira en un
plazo máximo de **7 días naturales**, sin necesidad de justificar la petición.

También se atienden correcciones de datos (dirección, web, teléfono) por la misma
vía.

## Limitaciones conocidas

- **Cobertura del 4,3 %** sobre el universo DIRCE. El censo es una cota inferior.
  Sevilla está sobrerrepresentada (9,2 %) frente a Málaga (1,5 %) por sesgo de las
  fuentes, no por realidad del tejido: el INE indica que Málaga tiene un 69 % más
  de empresas CNAE 62 que Sevilla.
- **DIRCE cuenta locales, no empresas.** El denominador se corrige con un factor
  1,17 (Sevilla) y 1,15 (Málaga) medido con los propios datos del INE.
- **El 42 % de los nombres no se pudo verificar en Google Places** con ese nombre
  exacto, normalmente por razones sociales distintas del nombre comercial.
- **Chao1 no aplicable**: las fuentes comparten pocas empresas entre sí, así que
  no hay historia de recaptura que permita estimar las que faltan.
- **Sin teléfono** en la mayoría de fichas: los portales de empleo y el BORME no
  lo publican.
