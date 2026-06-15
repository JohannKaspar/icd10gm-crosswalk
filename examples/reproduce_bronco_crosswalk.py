#!/usr/bin/env python3
"""Example: crosswalk a set of ICD-10-GM 2017 codes to 2024 and print a report.

Run it against a directory of BfArM year ZIPs (2018-2024)::

    python examples/reproduce_bronco_crosswalk.py /path/to/bfarm/zips

This mirrors what a one-off research script would do — turn a list of codes from
an older edition into their current form — but using the reusable library, which
keeps the multi-year chaining and the honest "needs manual review" flag in one
place. Codes below are a public sample; swap in your own.
"""

from __future__ import annotations

import sys
from collections import Counter

from icd10gm_crosswalk import Crosswalk, MappingKind

# A public sample of ICD-10-GM 2017 codes (a mix of identity, split, and remap).
SAMPLE_CODES = ["A00.0", "J45.0", "B18.1", "K55.88", "R17", "T66", "C50.9"]


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2

    cw = Crosswalk.from_source(argv[1])
    counts: Counter[MappingKind] = Counter()

    print(f"{'code':10} {'kind':12} {'recommended':12} targets")
    print("-" * 64)
    for code in SAMPLE_CODES:
        res = cw.map(code, 2017, 2024)
        counts[res.kind] += 1
        flag = "  [manual]" if res.needs_manual_review else ""
        print(
            f"{code:10} {res.kind.value:12} {cw.recommend(res) or '<none>':12} "
            f"{'|'.join(res.targets) or '<deleted>'}{flag}"
        )

    print("\nsummary:", dict(counts))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
