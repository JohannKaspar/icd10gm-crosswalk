"""Reproduce the BRONCO150 2017→2024 crosswalk (T-020 / T-026) exactly.

These 28 non-identity mappings are the substantive output of the original one-off
script. Every code and target here is a *public* ICD-10-GM code and every mapping
is a *public* BfArM transition — there is nothing patient-derived in this table,
so it is safe to commit as a golden fixture.

The test needs the official BfArM transition tables to run, which the library
never bundles. Point ``ICD10GM_DATA_DIR`` at a directory of BfArM year ZIPs
(2018-2024) and it will execute; otherwise it skips.
"""

from __future__ import annotations

import os

import pytest

from icd10gm_crosswalk import Crosswalk, MappingKind

DATA_DIR = os.environ.get("ICD10GM_DATA_DIR")

pytestmark = pytest.mark.skipif(
    not DATA_DIR,
    reason="set ICD10GM_DATA_DIR to a directory of BfArM year ZIPs (2018-2024)",
)

# (code_2017, net status, recommended_2024, sorted targets, needs_manual_review)
GOLDEN: list[tuple[str, str, str, tuple[str, ...], bool]] = [
    ("B18.1", "split", "B18.1", ("B18.11", "B18.12", "B18.14", "B18.19"), True),
    ("E66.82", "split", "E66.8", ("E66.86", "E66.87", "E66.88"), True),
    ("E66.92", "split", "E66.9", ("E66.96", "E66.97", "E66.98"), True),
    ("H35.3", "split", "H35.3", ("H35.30", "H35.31", "H35.38", "H35.39"), True),
    ("I21.4", "split", "I21.4", ("I21.40", "I21.41", "I21.48"), True),
    ("I27.28", "split", "I27.28", ("I27.21", "I27.22", "I27.28"), True),
    ("I31.9", "split", "I31.9", ("I31.80", "I31.9"), True),
    ("I77.8", "split", "I77.8", ("I77.80", "I77.88"), True),
    ("I82.88", "split", "I82.88", ("I82.81", "I82.88"), True),
    ("I86.8", "split", "I86.8", ("I86.80", "I86.81", "I86.82", "I86.88"), True),
    (
        "J45.0",
        "split",
        "J45.0",
        ("J45.00", "J45.01", "J45.02", "J45.03", "J45.04", "J45.05", "J45.09"),
        True,
    ),
    (
        "J45.9",
        "split",
        "J45.9",
        ("J45.90", "J45.91", "J45.92", "J45.93", "J45.94", "J45.95", "J45.99"),
        True,
    ),
    ("J98.1", "split", "J98.1", ("J98.10", "J98.11", "J98.12", "J98.18"), True),
    ("K31.1", "split", "K31.1", ("K31.10", "K31.11", "K31.12", "K31.18"), True),
    ("K55.88", "remapped", "K55.8", ("K55.8",), False),
    ("K59.0", "split", "K59.0", ("K59.00", "K59.01", "K59.02", "K59.09"), True),
    ("K65.0", "split", "K65.0", ("K65.00", "K65.09"), True),
    ("K72.0", "split", "K72.0", ("K72.0", "K72.10"), True),
    ("K72.1", "split", "K72.1", ("K72.10", "K72.18"), True),
    ("K83.0", "split", "K83.0", ("K83.00", "K83.01", "K83.08", "K83.09"), True),
    (
        "M14.6",
        "split",
        "M14.6",
        (
            "M14.60",
            "M14.61",
            "M14.62",
            "M14.63",
            "M14.64",
            "M14.65",
            "M14.66",
            "M14.67",
            "M14.68",
            "M14.69",
        ),
        True,
    ),
    ("M79.67", "split", "M79.67", ("G90.71", "M79.67"), True),
    ("M79.69", "split", "M79.69", ("G90.79", "M79.69"), True),
    (
        "R02",
        "split",
        "R02",
        (
            "R02.00",
            "R02.01",
            "R02.02",
            "R02.03",
            "R02.04",
            "R02.05",
            "R02.06",
            "R02.07",
            "R02.09",
            "R02.8",
        ),
        True,
    ),
    ("R17", "remapped", "R17.0", ("R17.0",), False),
    ("R35", "split", "R35", ("R35.0", "R35.1", "R35.2"), True),
    ("T66", "split", "T66", ("K20.1", "T66"), True),
    ("T88.7", "split", "T88.7", ("D76.4", "T88.7"), True),
]

_STATUS = {"split": MappingKind.SPLIT, "remapped": MappingKind.ONE_TO_ONE}


@pytest.fixture(scope="module")
def crosswalk() -> Crosswalk:
    assert DATA_DIR is not None
    return Crosswalk.from_source(DATA_DIR)


@pytest.mark.parametrize("code,status,recommended,targets,manual", GOLDEN)
def test_bronco_nonidentity_mapping(
    crosswalk: Crosswalk,
    code: str,
    status: str,
    recommended: str,
    targets: tuple[str, ...],
    manual: bool,
) -> None:
    res = crosswalk.map(code, 2017, 2024)
    assert res.targets == targets
    assert res.kind is _STATUS[status]
    assert crosswalk.recommend(res) == recommended
    assert res.needs_manual_review is manual


def test_bronco_headline_counts(crosswalk: Crosswalk) -> None:
    """The non-identity set is exactly 26 splits + 2 remaps, 0 retired (T-020)."""
    kinds = [crosswalk.map(c, 2017, 2024).kind for c, *_ in GOLDEN]
    assert kinds.count(MappingKind.SPLIT) == 26
    assert kinds.count(MappingKind.ONE_TO_ONE) == 2
    assert kinds.count(MappingKind.DELETED) == 0


def test_identity_codes_unchanged(crosswalk: Crosswalk) -> None:
    """A handful of common codes are stable across 2017→2024."""
    for code in ("A00.0", "C50.9", "E11.9", "I10.90"):
        res = crosswalk.map(code, 2017, 2024)
        assert res.kind is MappingKind.IDENTITY
        assert res.targets == (code,)
