"""Tests for the argparse CLI."""

from __future__ import annotations

from pathlib import Path

import pytest

from icd10gm_crosswalk import BfArMDownloadError
from icd10gm_crosswalk import cli as cli_mod
from icd10gm_crosswalk.cli import main

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


def test_download_without_accept_terms_refuses(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = main(["download", "2024"])
    assert rc == 2
    assert "--accept-terms" in capsys.readouterr().err


def test_download_success(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = tmp_path / "icd10gm2024syst-ueberl.zip"
    monkeypatch.setattr(cli_mod, "download_year", lambda *a, **k: fake)
    rc = main(["download", "2024", "--accept-terms", "--cache", str(tmp_path)])
    assert rc == 0
    assert f"2024: {fake}" in capsys.readouterr().out


def test_download_partial_failure_aggregates_exit_code(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def _fake(year: int, **kwargs: object) -> Path:
        if year == 2024:
            raise BfArMDownloadError("blocked by portal")
        return tmp_path / f"icd10gm{year}syst-ueberl.zip"

    monkeypatch.setattr(cli_mod, "download_year", _fake)
    rc = main(["download", "2023", "2024", "--accept-terms", "--cache", str(tmp_path)])
    assert rc == 1  # any failure -> non-zero
    captured = capsys.readouterr()
    assert "2023:" in captured.out  # the success printed to stdout
    assert "2024:" in captured.err  # the failure printed to stderr
