# Synthetic transition fixtures

These `umsteiger_*.txt` files are **hand-authored** test data, not BfArM files.
They use invented `Z##.#` codes (no real ICD-10-GM code starts with `Z00.0` in
this shape) so the suite can exercise every code path offline, with no BfArM data
and no licensing concerns.

The scenario spans editions 2000 → 2003 and covers:

| code   | 2000 → 2001 behaviour                        | exercises                          |
| ------ | -------------------------------------------- | ---------------------------------- |
| Z00.0  | `Z00.0` (unchanged)                          | identity, multi-step carry-forward |
| Z01.0  | `Z01.1` (auto)                               | clean 1:1 remap                    |
| Z02.0  | `Z02.00`, `Z02.01` (manual)                  | 1:n split; chained split at step 2 |
| Z03.0  | `Z03.9` (auto) — shared with Z03.1           | n:1 merge                          |
| Z04.0  | *(none)*                                      | deletion                           |
| Z05.0  | `Z05.5` (manual)                             | 1:1 remap that needs manual review |
| Z06.0  | `Z06.1`, `Z06.2` (manual) → both → `Z06.9`   | split then merge re-converging     |

The real-data correctness check (reproducing the BRONCO 2017→2024 crosswalk) lives
in `tests/test_bronco_regression.py` and is skipped unless `ICD10GM_DATA_DIR`
points at a local directory of BfArM year ZIPs.
