# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A census (`censo_software_sevilla`) of software-development companies in three Andalusian
provinces — Sevilla (INE 41), Málaga (INE 29), Huelva (INE 21) — built by triangulating
public sources (BORME, job boards, tech parks, GitHub, press, public tenders) because no
single public registry of these companies exists. Currently 445 records in `data/empresas.json`,
published as a static `index.html` (map + printable cards + mailing labels).

Read `PLAN_CENSO_SOFTWARE.md` before any pipeline change — it has the operative definition of
"software company", the border-case rules (§1.3), the data schema (§3), and a running log of
mistakes already made (Anexo A). `AVISO.md` is the GDPR/legal notice shipped inside `index.html`;
update it if inclusion criteria or data sources change. `README.md`'s numbers are stale (says
130 companies; the dataset has 445) — trust `data/empresas.json` and `git log`, not the README.

## Commands

No package manager, no build step, no test framework — everything is a directly-runnable
stdlib-only Python script (Python 3, `shapely` is the one third-party dependency, needed only
for `geom.py`/`build_provincias.py` point-in-polygon).

```bash
# Run the full publish pipeline after editing data/empresas.json by hand or via a script
python scripts/build_html.py          # regenerates index.html from data/empresas.json — the ONLY way to write it

# Checks (plain scripts with assert + print, not pytest — run individually)
python scripts/verificar_coherencia.py      # ambito vs provincia_de(): must be zero mismatches
python scripts/test_escritor.py             # invariants of _common._escribe_dataset (the dataset writer)
python scripts/test_municipio_provincia.py  # municipio must match its own province, not a neighbor's
python scripts/test_cp_por_direccion.py     # Places findplacefromtext postal-code matching logic
python scripts/check_etiquetas_filtro.py    # index.html <-> empresas.json label numbering stays in sync

# Regenerate cierre/coverage report
python scripts/cierre.py

# Regenerate the province-boundary cache (only needed if boundaries look wrong; ~194MB PBF download)
cd /tmp && curl -sLO https://download.geofabrik.de/europe/spain/andalucia-latest.osm.pbf
python scripts/build_provincias.py /tmp/andalucia-latest.osm.pbf
```

`scripts/collectors/*.py` are one-shot data-gathering scripts per source (BORME, job boards,
tech parks, GitHub, press/tenders); each writes to `raw/<fuente>_<fecha>.jsonl` and is normally
run once per source refresh, not part of a repeatable build.

## Architecture

**Pipeline is strictly one-directional and file-based**, no database:

```
raw/*.jsonl (collectors, one per source)
    -> scripts/merge_fuentes.py     dedupe -> data/empresas.json (canonical dataset)
    -> scripts/verificar_places.py  Google Places verification + 12-month activity filter
    -> scripts/clasificar.py        typology, border cases -> data/excluidos.json
    -> scripts/cierre.py            DIRCE coverage % + Chao1 capture-recapture, closes the census
    -> scripts/build_html.py        renders index.html from data/empresas.json (only writer of index.html)
```

Collector scripts never touch `data/` or `index.html` directly — they only ever write to `raw/`.
Records excluded by border-case rules go to `data/excluidos.json` with `motivo_exclusion` +
evidence URL, never deleted outright (this is what makes capture-recapture accounting valid
across re-runs).

**Single source of truth for "which province is this record in"**: `scripts/build_provincias.py`
— `ambito_de()` resolves CP-vs-coordinate conflicts (Places sometimes returns a homonym in the
wrong province) and is also what `scripts/collectors/_common.py::_escribe_dataset` (the dataset
writer) validates against and what the label generator (`scripts/etiquetas.py`) reads. Do not
derive province from `id` prefixes (`sev-`/`mal-`/`sin-`) — those describe which collector
*found* the record, not where it is; that mismatch was a real bug (see `fix_provincia.py`'s
docstring). `scripts/geom.py::provincia_de()` does the actual point-in-polygon lookup against a
cached PBF-derived polygon set (`~/.cache/censo_software/provincias_and.json`); `ambito_de()` in
`build_provincias.py` wraps it with the CP-conflict resolution and is the one to call from new
code. Province name normalization is ASCII+uppercase everywhere (`verificar_coherencia.py`'s
docstring explains why: accent/case mismatches produced false-positive "incoherencias" before).

**`data/empresas.json` schema** (see PLAN §3 for the full annotated example): every record
carries `fuentes[]` (provenance, never a single source), `n_fuentes_independientes` (drives
capture-recapture), `confianza` (ALTA/MEDIA/BAJA based on source count + Places verification),
and `flags[]` for known issues (`SIN_COORDS`, `DUPLICADO_POSIBLE`, etc.). **No field is ever
filled with a plausible-but-unsourced guess** — `scripts/AGENTE_TEMPLATE.md`'s hard rule ("sin
URL de evidencia no hay campo") applies to every script and agent touching this dataset; the
prior project this one supersedes had 36 propagated emails and 11 mismatched coordinates from
violating exactly this.

**Activity filter** (whether a company counts as currently active): Google Places review dates
sorted `reviews_sort=newest` via the API — scraping/browser only surfaces "most relevant"
reviews, which in practice are years old and useless for a 12-month cutoff (PLAN §4 has the
measured example). N1 = recent review; N2 = no recent review but a dated activity proxy
(`proxies_actividad[]`: job posting, press mention, adjudicated tender, etc., each requiring its
own URL+date); N3 = neither, excluded as `SIN_ACTIVIDAD_12M`.

**`index.html` generation**: `scripts/build_html.py` reads `data/empresas.json` and
`plantilla.html`, then renders both the map markers and the card list from the *same* sorted
array in one pass — this is deliberate so cards and map pins can never drift out of sync (a bug
class the predecessor project had). It also calls `scripts/etiquetas.py::generar()` for the
printable-labels sheet embedded in the same page, and asserts fiche/point/label counts match the
source array before writing the file. Never hand-edit `index.html` — regenerate it.

**Windows note**: `scripts/fix_provincia.py` and `scripts/crear_repo.py` have a hardcoded
`/root/censo_software_sevilla` root from the original (Linux) development environment — fix the
path before running them here, or run everything else (which uses
`os.path.dirname(os.path.abspath(__file__))`-relative paths, which are portable) instead.

**Google Maps API key**: read from the environment (`GOOGLE_MAPS_API_KEY`), never inline in a
command — Anexo A of the plan documents this causing real debugging pain (Google returns HTTP
200 on API errors too; only the response body's `status` field tells you if a call failed).
