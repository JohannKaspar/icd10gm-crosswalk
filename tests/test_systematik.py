"""Tests for ClaML-backed role lookup and marker validation."""

from __future__ import annotations

import os
import warnings
from pathlib import Path

import pytest

from icd10gm_crosswalk import (
    Crosswalk,
    MarkerValidationWarning,
    Role,
    Systematik,
    TransitionStore,
    YearStep,
)
from icd10gm_crosswalk.models import Transition

MINI_CLAML = Path(__file__).parent / "data" / "mini_claml.xml"


@pytest.fixture
def systematik() -> Systematik:
    return Systematik.from_source(MINI_CLAML)


@pytest.mark.parametrize(
    ("code", "role"),
    [
        ("A00.0", Role.PRIMARY),
        ("A18.0", Role.DAGGER),  # usage="dagger"
        ("H36.0", Role.STAR),  # usage="aster"
        ("B95.6", Role.EXCLAMATION),  # §295 = Z
        ("J44", Role.NONCODABLE),  # §295 = V
        ("E10.30", Role.DAGGER),  # modifier .3 dagger, inherited by prefix
        ("E10.20", Role.DAGGER),  # modifier .2 dagger
        ("Z99.9", None),  # unknown
    ],
)
def test_role_lookup(systematik: Systematik, code: str, role: Role | None) -> None:
    assert systematik.role(code) == role


# -- validation integration through Crosswalk.map -------------------------- #
def _crosswalk(systematik: Systematik | None) -> Crosswalk:
    rows = [
        Transition("A00.0", "A00.0", True, True),
        Transition("A18.0", "A18.0", True, True),
        Transition("H36.0", "H36.0", True, True),
    ]
    store = TransitionStore([YearStep.from_transitions(2000, 2001, rows)])
    return Crosswalk(store, systematik=systematik)


def test_consistent_marker_does_not_warn(systematik: Systematik) -> None:
    cw = _crosswalk(systematik)
    with warnings.catch_warnings():
        warnings.simplefilter("error", MarkerValidationWarning)
        cw.map("A18.0†", 2000, 2001)  # A18.0 really is a dagger code
        cw.map("H36.0*", 2000, 2001)  # H36.0 really is a star code


def test_dagger_on_plain_primary_warns(systematik: Systematik) -> None:
    cw = _crosswalk(systematik)
    with pytest.warns(MarkerValidationWarning, match="primary"):
        cw.map("A00.0†", 2000, 2001)  # A00.0 is primary, not dagger


def test_star_marker_on_dagger_code_warns(systematik: Systematik) -> None:
    cw = _crosswalk(systematik)
    with pytest.warns(MarkerValidationWarning, match="dagger"):
        cw.map("A18.0*", 2000, 2001)  # A18.0 is dagger, marked star


def test_no_systematik_warns_unverified() -> None:
    cw = _crosswalk(None)
    with pytest.warns(MarkerValidationWarning, match="no systematik"):
        cw.map("A18.0†", 2000, 2001)


def test_bare_code_never_warns() -> None:
    cw = _crosswalk(None)
    with warnings.catch_warnings():
        warnings.simplefilter("error", MarkerValidationWarning)
        cw.map("A18.0", 2000, 2001)  # no marker -> no validation, no warning


def test_empty_source_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no ICD-10-GM ClaML"):
        Systematik.from_source(tmp_path)


# -- optional real-data check --------------------------------------------- #
_CLAML = os.environ.get("ICD10GM_CLAML")


@pytest.mark.skipif(not _CLAML, reason="set ICD10GM_CLAML to a BfArM ClaML zip/xml")
def test_real_claml_roles() -> None:
    assert _CLAML is not None
    syst = Systematik.from_source(_CLAML)
    assert syst.role("H36.0") is Role.STAR
    assert syst.role("B95.6") is Role.EXCLAMATION
    assert syst.role("E10.30") is Role.DAGGER  # modifier-expanded dagger
    assert syst.role("A00.0") is Role.PRIMARY
