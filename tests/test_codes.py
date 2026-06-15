"""Tests for the Kreuz-Stern / compound-code notation helpers."""

from __future__ import annotations

import pytest

from icd10gm_crosswalk import split_components, split_marker, strip_markers


@pytest.mark.parametrize(
    ("code", "bare", "marker"),
    [
        ("A00.0", "A00.0", ""),
        ("R65.1!", "R65.1", "!"),
        ("E10.30†", "E10.30", "†"),
        ("D48.9+", "D48.9", "+"),
        ("H36.0*", "H36.0", "*"),
        (" B95.6# ", "B95.6", "#"),
    ],
)
def test_split_marker(code: str, bare: str, marker: str) -> None:
    assert split_marker(code) == (bare, marker)


def test_strip_markers() -> None:
    assert strip_markers("R65.1!") == "R65.1"
    assert strip_markers("A00.0") == "A00.0"


def test_split_components_preserves_markers() -> None:
    assert split_components("A41.9,R65.1!") == ["A41.9", "R65.1!"]
    assert split_components("D48.9+,D63.0*") == ["D48.9+", "D63.0*"]


def test_split_components_trims_and_drops_empties() -> None:
    assert split_components(" A41.9 , , R65.1! ") == ["A41.9", "R65.1!"]
    assert split_components("") == []


def test_split_components_custom_separator() -> None:
    assert split_components("E10.30+ H36.0*", sep=" ") == ["E10.30+", "H36.0*"]
