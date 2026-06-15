"""Tests for the argparse CLI."""

from __future__ import annotations

from pathlib import Path

import pytest

from icd10gm_crosswalk.cli import main
from icd10gm_crosswalk.sources import TERMS_URL

DATA = str(Path(__file__).parent / "data")


def test_info(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["info", "--data", DATA]) == 0
    out = capsys.readouterr().out
    assert "2000→2003" in out
    assert "source codes" in out


def test_map_split_with_trace(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(
        ["map", "Z02.0", "--from", "2000", "--to", "2002", "--trace", "--data", DATA]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "kind        : split" in out
    assert "recommended : Z02.0" in out
    assert "ambiguous   : True" in out
    assert "[manual]" in out


def test_map_merge_reports_merge(capsys: pytest.CaptureFixture[str]) -> None:
    main(["map", "Z03.0", "--from", "2000", "--to", "2001", "--data", DATA])
    out = capsys.readouterr().out
    assert "merged with : Z03.1" in out


def test_map_unknown_year_errors(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["map", "Z00.0", "--from", "2000", "--to", "2050", "--data", DATA])
    assert rc == 2
    assert "error:" in capsys.readouterr().err


def test_urls_lists_download_links(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["urls", "--from", "2017", "--to", "2024"])
    assert rc == 0
    out = capsys.readouterr().out
    assert TERMS_URL in out
    assert "2023→2024" in out
    assert "version2024" in out


def test_urls_reversed_years_errors(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["urls", "--from", "2024", "--to", "2017"])
    assert rc == 2
    assert "error:" in capsys.readouterr().err
