# icd10gm-crosswalk

[![CI](https://github.com/JohannKaspar/icd10gm-crosswalk/actions/workflows/ci.yml/badge.svg)](https://github.com/JohannKaspar/icd10gm-crosswalk/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Checked with ty](https://img.shields.io/badge/types-ty-261230)](https://github.com/astral-sh/ty)

Map **ICD-10-GM** diagnosis codes across annual editions using the official
[BfArM *Umsteiger*](https://www.bfarm.de/DE/Kodiersysteme/Klassifikationen/ICD/ICD-10-GM/_node.html)
(transition) tables — chained over any year range, with the automatic-vs-manual
transition flag preserved and the ambiguity from chained splits and merges
reported honestly rather than swept under the rug.

ICD-10-GM (the German modification of ICD-10) is re-issued every year. A code
valid in 2017 may be **unchanged**, **renamed** 1:1, **split** into finer
children, **merged** into a broader code, or **deleted** by 2024. Getting this
right matters whenever you compare codings made under different editions — e.g.
scoring a 2017-annotated corpus against a 2024 prediction. The official source
of truth is BfArM's yearly Umsteiger tables; there is no direct multi-year table,
so 2017→2024 must be *chained* 2017→2018→…→2024, and a naive verbatim diff
silently misses splits whose parent survives as a category string. This library
does the chaining.

> **Python counterpart to the R [`ICD10gm`](https://github.com/edonnachie/ICD10gm)
> package.** The R package is excellent and more comprehensive; this one is
> focused on the multi-year *crosswalk* problem, ships zero runtime dependencies,
> and — importantly — **never redistributes BfArM data** (see [Data & licensing](#data--licensing)).

## Features

- **Multi-year chaining** — `map("J45.0", 2017, 2024)` walks every intermediate
  edition, not a single before/after diff.
- **Honest classification** — every mapping is `identity`, `one_to_one`, `split`
  (1:n), `merge` (n:1), or `deleted`.
- **Per-step provenance** — the automatic-vs-manual flag from each Umsteiger row
  is preserved and aggregated into a single `needs_manual_review` signal.
- **Ambiguity, surfaced** — chained splits that never re-merge are flagged
  (`ambiguous`), and a `recommend()` helper picks a single representative code
  (parent fallback) when you must collapse a 1:n mapping.
- **Reads BfArM's real layout** — loose `.txt`, a year ZIP, or a whole directory,
  including the nested-ZIP packaging used since the 2022 edition.
- **Combined codes & Kreuz-Stern notation** — maps the components of a compound
  diagnosis and carries the Kreuz (`†`/`+`), Stern (`*`), and `!` role markers
  through the mapping, optionally validating them against the ClaML systematik.
- **Zero runtime dependencies**, fully typed (`py.typed`), tested, with a CLI.

## Installation

This repo uses [uv](https://docs.astral.sh/uv/). Until it is published to PyPI,
install from source:

```bash
git clone https://github.com/JohannKaspar/icd10gm-crosswalk
cd icd10gm-crosswalk
uv sync
```

Once released, it will be installable directly:

```bash
pip install icd10gm-crosswalk        # or: uv add icd10gm-crosswalk  (after PyPI release)
```

## Quick start

```python
from icd10gm_crosswalk import Crosswalk

# Point at a directory of BfArM year ZIPs (see "Data & licensing" below).
cw = Crosswalk.from_source("~/icd10gm-zips")

res = cw.map("J45.0", 2017, 2024)
res.kind            # MappingKind.SPLIT
res.targets         # ('J45.00', 'J45.01', 'J45.02', 'J45.03', 'J45.04', 'J45.05', 'J45.09')
res.ambiguous       # True  -> needs the original mention to disambiguate
res.needs_manual_review  # True
cw.recommend(res)   # 'J45.0'  -> longest shared prefix (a lossy single-code pick)

cw.map("A00.0", 2017, 2024).kind   # MappingKind.IDENTITY
cw.map("K55.88", 2017, 2024)       # one_to_one -> ('K55.8',)

# Merges are detected via the inverse table — even when a code also splits.
# M79.67 splits, but one of its new targets (G90.71) also absorbs sibling codes,
# so the co-merge is surfaced rather than lost:
m = cw.map("M79.67", 2017, 2024)
m.kind          # MappingKind.SPLIT
m.is_merge      # True
m.merged_from   # ('M79.60', 'M79.65', 'M79.66')  -> the codes it co-merged with
```

### Inspecting the chain

```python
res = cw.map("J45.0", 2017, 2024)
for step in res.steps:
    print(step.from_year, "→", step.to_year, step.code, step.targets, step.kind.value)
```

### Combined codes & Kreuz-Stern notation

ICD-10-GM marks the roles in a combined diagnosis with a Kreuz/dagger (`†` or `+`,
the underlying disease), a Stern (`*`, the manifestation), and an `!`
(Ausrufezeichen, a secondary code), and sources often join the components into one
string. BfArM's transition tables key on *bare* codes, so `map()` strips a trailing
marker for the lookup and re-applies it to the result — and `map_components()`
handles a whole compound:

```python
cw.map("E10.30†", 2017, 2024).targets        # ('E10.30†',)  -> marker preserved
cw.map("B18.1†", 2017, 2024).targets         # ('B18.11†', 'B18.12†', 'B18.14†', 'B18.19†')

# A compound diagnosis: one result per component, each keeping its role marker.
for r in cw.map_components("A41.9,R65.1!", 2017, 2024):
    print(r.code, "→", r.targets)            # A41.9 → (...);  R65.1! → ('R65.1!',)

cw.map("A41.9,R65.1!", 2017, 2024)           # ValueError: use map_components()
```

Helpers `strip_markers`, `split_marker`, and `split_components` are exported if you
need them directly.

#### Validating markers against the systematik (optional)

By default the marker is re-applied *syntactically* — it preserves the source
annotation's role but isn't checked. Pass a `Systematik` (parsed from BfArM's
ClaML) and the crosswalk will verify each marker against the code's real role,
warning on a contradiction (and warning that it *can't* verify when no systematik
is loaded):

```python
from icd10gm_crosswalk import Crosswalk, Systematik

syst = Systematik.from_source("~/icd10gm2024syst-claml.zip")   # one ClaML file
cw = Crosswalk.from_source("~/icd10gm-zips", systematik=syst)

cw.map("H36.0*", 2017, 2024)   # fine — H36.0 really is a Stern code
cw.map("A09.9+", 2017, 2024)   # MarkerValidationWarning: A09.9 is not a dagger code
cw.map("H36.0+", 2017, 2024)   # MarkerValidationWarning: H36.0 is star, not dagger
```

ClaML is the single source of truth here: it carries the exact `dagger`/`aster`
designation (the flat metadata lumps dagger in with ordinary primary codes — of
~13k primary codes only ~131 are truly dagger), and the modifier-expanded blocks
(diabetes `E10–E14`, etc.) are resolved too, so `E10.30†` validates correctly.
Filter the notices with Python's `warnings` module (category
`MarkerValidationWarning`) if you don't want them.

## Command line

```bash
# What editions does a data source cover?
icd10gm-crosswalk info --data ~/icd10gm-zips

# Map a single code, with the per-year trace
icd10gm-crosswalk map J45.0 --from 2017 --to 2024 --trace --data ~/icd10gm-zips

# Which BfArM files do I need to download for a given range?
icd10gm-crosswalk urls --from 2017 --to 2024
```

## Data & licensing

This library deliberately **does not bundle or redistribute BfArM data.** BfArM's
[download conditions](https://www.bfarm.de/SharedDocs/Downloads/DE/Kodiersysteme/downloadbedingungen-2025.pdf?__blob=publicationFile)
make the files free but copyrighted: you accept a usage agreement on download, you
**may not pass the files on "in the acquired format"**, but you **may build and
distribute derived "value-added products"** (such as the crosswalk this library
produces). Bundling the tables would violate the first clause — so instead the
library reads data *you* obtain.

**Download once via your browser** (one click, accept the terms) and point the
library at the files. You need the *Überleitung* (transition) package for each
edition, e.g. `icd10gm2024syst-ueberl_zip.html` from the
[BfArM download page](https://www.bfarm.de/DE/Kodiersysteme/Services/Downloads/_node.html).
Drop the year ZIPs in a folder and pass that folder to `from_source`.

To save you hunting BfArM's site, the library tells you exactly which files a given
range needs — and only that. It does **not** fetch them: BfArM's portal sits behind
an anti-bot gate that rejects scripted requests, so an automated downloader would
be unreliable, and the files may not be redistributed anyway.

```bash
icd10gm-crosswalk urls --from 2017 --to 2024
```
```python
from icd10gm_crosswalk import download_instructions, transition_zip_urls
print(download_instructions(2017, 2024))      # copy-pasteable recipe + terms link
transition_zip_urls(2017, 2024)               # [(2018, url), ..., (2024, url)]
```

When you publish a crosswalk produced with this tool, attribute the source
("ICD-10-GM, © BfArM") as the terms require.

## How it works

1. **Parse** each yearly Umsteiger table — a UTF-8, semicolon-separated file of
   `CodePrev ; CodeCur ; A(uto-forward) ; A(uto-backward)` rows.
2. **Index** each step forward (`prev → rows`) and inverse (`cur → rows`); the
   inverse index is what makes n:1 merge detection possible.
3. **Chain** the steps: starting from your code, take the union of successors at
   each step (a code absent from a table is carried forward unchanged), tracking
   where a non-automatic row or a split was introduced.
4. **Classify** the net result by forward cardinality and surface merges and
   ambiguity separately, so the forward mapping stays faithful to the official
   tables. See the design note in
   [`crosswalk.py`](src/icd10gm_crosswalk/crosswalk.py).

## Correctness

The synthetic test suite (`tests/data/`) exercises every code path — identity,
1:1, split, merge, deletion, chained split-then-merge re-convergence, and
manual-flag propagation — offline, with no BfArM data.

A separate golden regression (`tests/test_bronco_regression.py`) reproduces a
real research crosswalk (BRONCO150, ICD-10-GM 2017→2024): 26 splits + 2 remaps,
0 deletions, each with its exact target set and manual flag. Every code in it is
a public ICD-10-GM code and every mapping a public BfArM transition. It runs when
`ICD10GM_DATA_DIR` points at a directory of BfArM year ZIPs, and is skipped
otherwise.

## Development

```bash
uv sync
uv run ruff check .          # lint
uv run ruff format --check . # format
uv run ty check              # type-check
uv run pytest                # test (synthetic fixtures; no BfArM data needed)

# To also run the real-data regression:
ICD10GM_DATA_DIR=~/icd10gm-zips uv run pytest
```

## License

[MIT](LICENSE). Note that the *BfArM ICD-10-GM data* this tool consumes is under
its own separate terms — see [Data & licensing](#data--licensing).
