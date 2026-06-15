"""Tests for the BfArM download-URL helpers (no network access)."""

from __future__ import annotations

import pytest

from icd10gm_crosswalk import (
    download_instructions,
    transition_zip_url,
    transition_zip_urls,
)
from icd10gm_crosswalk.sources import TERMS_URL


def test_transition_url_shape() -> None:
    url = transition_zip_url(2024)
    assert url.startswith("https://")
    assert "version2024" in url
    assert "icd10gm2024syst-ueberl_zip.html" in url


def test_terms_url_is_https() -> None:
    assert TERMS_URL.startswith("https://")


def test_transition_zip_urls_spans_later_years() -> None:
    pairs = transition_zip_urls(2017, 2024)
    assert [year for year, _ in pairs] == [2018, 2019, 2020, 2021, 2022, 2023, 2024]
    assert all(f"version{year}" in url for year, url in pairs)


def test_transition_zip_urls_same_year_is_empty() -> None:
    assert transition_zip_urls(2024, 2024) == []


def test_transition_zip_urls_reversed_raises() -> None:
    with pytest.raises(ValueError, match="must not be after"):
        transition_zip_urls(2024, 2017)


def test_download_instructions_lists_urls_and_terms() -> None:
    text = download_instructions(2017, 2024)
    assert TERMS_URL in text
    assert "7 BfArM transition ZIP(s)" in text
    assert "2023→2024" in text
    assert transition_zip_url(2024) in text


def test_download_instructions_same_year() -> None:
    assert "no transition needed" in download_instructions(2024, 2024)
