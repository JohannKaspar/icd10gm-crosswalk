"""Tests for Umsteiger filename matching, row parsing, and ZIP discovery/safety."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from icd10gm_crosswalk import parse_umsteiger_text
from icd10gm_crosswalk import parsing as parsing_mod
from icd10gm_crosswalk.models import Transition
from icd10gm_crosswalk.parsing import find_umsteiger, umsteiger_year_pair

DATA_DIR = Path(__file__).parent / "data"

_ROWS = "A00.0;A00.0;A;A\nB18.1;B18.11;;A\n"


def _ueberl_zip_bytes(year: int, prev: int, rows: str = _ROWS) -> bytes:
    """An inner BfArM-style 'ueberl' ZIP holding the Umsteiger under a subdirectory."""
    buf = io.BytesIO()
    sub = "Klassifikationsdateien"
    member = f"{sub}/icd10gm{year}syst_umsteiger_{prev}_{year}_20221206.txt"
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(member, rows)
    return buf.getvalue()


def _write_year_zip(
    path: Path, year: int, prev: int, *, bad_member: bool = False
) -> None:
    """A year ZIP in BfArM's nested layout (year zip -> ueberl zip -> txt)."""
    with zipfile.ZipFile(path, "w") as outer:
        outer.writestr(f"icd10gm{year}syst-ueberl.zip", _ueberl_zip_bytes(year, prev))
        if bad_member:
            outer.writestr(f"icd10gm{year}syst-pdf.zip", b"not a zip at all")


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("icd10gm2018syst_umsteiger_2017_2018.txt", (2017, 2018)),
        ("icd10gm2023syst_umsteiger_2022_2023_20221206.txt", (2022, 2023)),
        ("icd10gm2024syst_umsteiger_2023_20221206_2024.txt", (2023, 2024)),
        ("not_a_transition_file.txt", None),
    ],
)
def test_year_pair_extraction(name: str, expected: tuple[int, int] | None) -> None:
    assert umsteiger_year_pair(name) == expected


def test_parse_rows_flags_and_deletion() -> None:
    text = "A00.0;A00.0;A;A\nB18.1;B18.11;;A\nZ04.0;;;\n\nmalformed\n"
    rows = parse_umsteiger_text(text)
    assert len(rows) == 3
    assert rows[0] == Transition("A00.0", "A00.0", True, True)
    # split row: forward not automatic, backward automatic
    assert rows[1].auto_forward is False
    assert rows[1].auto_backward is True
    # deletion: empty successor preserved
    assert rows[2].code_cur == ""


def test_find_umsteiger_discovers_all_steps() -> None:
    found = find_umsteiger(DATA_DIR)
    assert set(found) == {(2000, 2001), (2001, 2002), (2002, 2003)}
    assert len(found[(2000, 2001)]) == 10


def test_find_umsteiger_empty_source(tmp_path) -> None:
    assert find_umsteiger(tmp_path) == {}


def test_find_umsteiger_nested_zip(tmp_path: Path) -> None:
    """The real BfArM layout: year ZIP -> nested ueberl ZIP -> subdir/umsteiger.txt."""
    _write_year_zip(tmp_path / "icd10gm2023.zip", 2023, 2022)
    found = find_umsteiger(tmp_path)
    assert set(found) == {(2022, 2023)}
    assert len(found[(2022, 2023)]) == 2
    # Discovery also works when pointed straight at the year ZIP file.
    assert set(find_umsteiger(tmp_path / "icd10gm2023.zip")) == {(2022, 2023)}


def test_find_umsteiger_skips_bad_zip_member(tmp_path: Path) -> None:
    """A sibling member named *.zip that is not a valid ZIP is skipped, not fatal."""
    _write_year_zip(tmp_path / "icd10gm2023.zip", 2023, 2022, bad_member=True)
    assert set(find_umsteiger(tmp_path)) == {(2022, 2023)}


def test_scan_zip_depth_limit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Nested-ZIP recursion is bounded so a crafted archive cannot recurse forever."""
    _write_year_zip(tmp_path / "icd10gm2023.zip", 2023, 2022)  # nests 2 levels deep
    monkeypatch.setattr(parsing_mod, "MAX_ZIP_DEPTH", 1)
    assert find_umsteiger(tmp_path) == {}  # the inner ueberl ZIP is past the limit


def test_oversized_member_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A member whose declared size exceeds the cap is skipped (zip-bomb guard)."""
    zip_path = tmp_path / "icd10gm2024.zip"
    with zipfile.ZipFile(zip_path, "w") as z:
        z.writestr("icd10gm2024syst_umsteiger_2023_2024.txt", _ROWS)
    assert set(find_umsteiger(zip_path)) == {(2023, 2024)}  # fits by default
    monkeypatch.setattr(parsing_mod, "MAX_MEMBER_BYTES", 4)
    assert find_umsteiger(zip_path) == {}  # now too big -> skipped


def test_find_umsteiger_duplicate_pair_first_sorted_wins(tmp_path: Path) -> None:
    """When two files describe the same year pair, the sorted-first one wins."""
    (tmp_path / "a_icd10gm2021syst_umsteiger_2020_2021.txt").write_text(
        "X00.0;X00.0;A;A\n"
    )
    (tmp_path / "z_icd10gm2021syst_umsteiger_2020_2021.txt").write_text(
        "Y00.0;Y00.0;A;A\nY00.1;Y00.1;A;A\n"
    )
    found = find_umsteiger(tmp_path)
    assert len(found[(2020, 2021)]) == 1  # the 'a_' file (1 row) won
