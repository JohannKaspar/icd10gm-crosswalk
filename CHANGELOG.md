# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-06-15

### Added

- `Crosswalk.map(code, from_year, to_year)` — chain official BfArM Umsteiger
  tables across an arbitrary year range, classifying each mapping as identity,
  one-to-one, split (1:n), merge (n:1), or deleted.
- `Crosswalk.map_step` — single consecutive-year mapping with merge detection.
- Per-step automatic-vs-manual transition flags, propagated to a chained
  `needs_manual_review` signal, plus an `ambiguous` flag for unresolved chains.
- `Crosswalk.recommend` — pick a single representative code (parent fallback) for
  a 1:n split.
- Combined-code & Kreuz-Stern support: `map` strips a trailing Kreuz (`†`/`+`),
  Stern (`*`), or `!` marker for the lookup and re-applies it to the result;
  `map_components` maps each component of a compound diagnosis; `map` raises on a
  compound. Helpers `strip_markers` / `split_marker` / `split_components`.
- Optional ClaML-backed marker validation: `Systematik.from_source` parses BfArM's
  ClaML into exact dagger/Stern/`!` roles (incl. modifier-expanded blocks such as
  diabetes); `Crosswalk(store, systematik=...)` then validates input markers and
  emits a `MarkerValidationWarning` on a contradiction — or when no systematik is
  loaded to check against. Stdlib XML parsing with an entity-declaration guard.
- `TransitionStore` / `parse_umsteiger_text` / `find_umsteiger` — read transition
  tables from a loose `.txt`, a year ZIP, or a directory (incl. BfArM's nested-ZIP
  layout from the 2022 edition onward), with recursion-depth and member-size guards
  against malformed or hostile archives.
- `download_instructions` / `transition_zip_urls` / `transition_zip_url` — tell you
  exactly which BfArM transition ZIPs a year range needs (the library never fetches
  or bundles data; BfArM's portal blocks scripted access and the files may not be
  redistributed).
- `icd10gm-crosswalk` CLI (`info`, `map`, `urls`).
- Golden regression test reproducing the BRONCO150 2017→2024 crosswalk exactly.

[Unreleased]: https://github.com/JohannKaspar/icd10gm-crosswalk/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/JohannKaspar/icd10gm-crosswalk/releases/tag/v0.1.0
