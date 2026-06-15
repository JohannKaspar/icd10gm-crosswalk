"""Tests for the download helper that need no network access."""

from __future__ import annotations

import io
import urllib.error
import zipfile
from pathlib import Path

import pytest

from icd10gm_crosswalk import BfArMDownloadError, download_year
from icd10gm_crosswalk.download import (
    TERMS_URL,
    default_cache_dir,
    transition_zip_url,
)


class _FakeResponse:
    """Minimal context-manager stand-in for an ``urlopen`` result."""

    def __init__(self, data: bytes) -> None:
        self._data = data

    def read(self, *args: object) -> bytes:
        return self._data

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *args: object) -> bool:
        return False


def _valid_zip_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("icd10gm2024syst_umsteiger_2023_2024.txt", "A00.0;A00.0;A;A\n")
    return buf.getvalue()


def test_accept_terms_gate() -> None:
    with pytest.raises(PermissionError, match="accept_terms=True"):
        download_year(2024, accept_terms=False)


def test_transition_url_shape() -> None:
    url = transition_zip_url(2024)
    assert "version2024" in url
    assert "icd10gm2024syst-ueberl_zip.html" in url
    assert url.startswith("https://")


def test_terms_url_is_https() -> None:
    assert TERMS_URL.startswith("https://")


def test_cache_dir_honours_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ICD10GM_CACHE_DIR", str(tmp_path / "cache"))
    assert default_cache_dir() == tmp_path / "cache"


def test_cache_dir_falls_back_to_xdg(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("ICD10GM_CACHE_DIR", raising=False)
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    assert default_cache_dir() == tmp_path / "icd10gm-crosswalk"


def test_returns_cached_zip_without_network(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cached = tmp_path / "icd10gm2024syst-ueberl.zip"
    with zipfile.ZipFile(cached, "w") as zf:
        zf.writestr("icd10gm2024syst_umsteiger_2023_2024.txt", "A00.0;A00.0;A;A\n")

    def _boom(*args: object, **kwargs: object) -> None:  # pragma: no cover
        raise AssertionError("network must not be touched when a valid cache exists")

    monkeypatch.setattr("urllib.request.urlopen", _boom)
    result = download_year(2024, accept_terms=True, cache_dir=tmp_path)
    assert result == cached


def test_success_path_writes_zip(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda *a, **k: _FakeResponse(_valid_zip_bytes())
    )
    path = download_year(2024, accept_terms=True, cache_dir=tmp_path)
    assert path.exists()
    assert zipfile.is_zipfile(path)
    assert not list(tmp_path.glob("*.part"))  # temp file cleaned up


def test_force_redownloads_over_valid_cache(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cached = tmp_path / "icd10gm2024syst-ueberl.zip"
    cached.write_bytes(_valid_zip_bytes())
    calls = {"n": 0}

    def _fake(*args: object, **kwargs: object) -> _FakeResponse:
        calls["n"] += 1
        return _FakeResponse(_valid_zip_bytes())

    monkeypatch.setattr("urllib.request.urlopen", _fake)
    download_year(2024, accept_terms=True, cache_dir=tmp_path, force=True)
    assert calls["n"] == 1  # force bypassed the cache short-circuit


def test_non_zip_response_raises_and_cleans_up(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *a, **k: _FakeResponse(b"<html>please accept the terms</html>"),
    )
    with pytest.raises(BfArMDownloadError, match="not a ZIP"):
        download_year(2024, accept_terms=True, cache_dir=tmp_path)
    assert not list(tmp_path.glob("*.part"))
    assert not list(tmp_path.glob("*.zip"))


def test_urlerror_raises_with_manual_instructions(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def _raise(*args: object, **kwargs: object) -> None:
        raise urllib.error.URLError("blocked")

    monkeypatch.setattr("urllib.request.urlopen", _raise)
    with pytest.raises(BfArMDownloadError) as exc:
        download_year(2025, accept_terms=True, cache_dir=tmp_path)
    message = str(exc.value)
    assert transition_zip_url(2025) in message
    assert TERMS_URL in message
    assert "icd10gm2025syst-ueberl.zip" in message
