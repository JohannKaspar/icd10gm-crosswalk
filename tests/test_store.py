"""Tests for the TransitionStore: indices, year range, chain validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from icd10gm_crosswalk import TransitionStore, YearStep
from icd10gm_crosswalk.models import Transition

DATA_DIR = Path(__file__).parent / "data"


def test_years_and_range(store: TransitionStore) -> None:
    assert store.years == [2000, 2001, 2002, 2003]
    assert store.min_year == 2000
    assert store.max_year == 2003


def test_forward_and_inverse_indices(store: TransitionStore) -> None:
    step = store.step(2000)
    assert sorted(t.code_cur for t in step.forward["Z02.0"]) == ["Z02.00", "Z02.01"]
    # Z03.9 has two predecessors -> the merge is visible in the inverse index
    assert sorted(t.code_prev for t in step.inverse["Z03.9"]) == ["Z03.0", "Z03.1"]


@pytest.mark.parametrize(
    ("frm", "to", "expected"),
    [(2000, 2003, True), (2000, 2010, False), (2003, 2000, False), (2000, 2000, True)],
)
def test_has_chain(store: TransitionStore, frm: int, to: int, expected: bool) -> None:
    assert store.has_chain(frm, to) is expected


def test_require_chain_ok(store: TransitionStore) -> None:
    chain = store.require_chain(2000, 2003)
    assert [s.from_year for s in chain] == [2000, 2001, 2002]


def test_require_chain_missing_step(store: TransitionStore) -> None:
    with pytest.raises(ValueError, match="missing transition step"):
        store.require_chain(2000, 2010)


def test_require_chain_reversed(store: TransitionStore) -> None:
    with pytest.raises(ValueError, match="must not be after"):
        store.require_chain(2003, 2000)


def test_empty_source_raises(tmp_path) -> None:
    with pytest.raises(ValueError, match="no Umsteiger"):
        TransitionStore.from_source(tmp_path)


def test_duplicate_from_year_rejected() -> None:
    rows = [Transition("A", "A", True, True)]
    steps = [
        YearStep.from_transitions(2000, 2001, rows),
        YearStep.from_transitions(2000, 2002, rows),
    ]
    with pytest.raises(ValueError, match="duplicate from_year"):
        TransitionStore(steps)


def test_from_source_accepts_single_file() -> None:
    path = DATA_DIR / "icd10gm2001syst_umsteiger_2000_2001.txt"
    store = TransitionStore.from_source(path)
    assert store.years == [2000, 2001]
