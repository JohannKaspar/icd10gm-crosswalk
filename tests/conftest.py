"""Shared fixtures: a store and crosswalk built from the synthetic 2000→2003 data."""

from __future__ import annotations

from pathlib import Path

import pytest

from icd10gm_crosswalk import Crosswalk, TransitionStore

DATA_DIR = Path(__file__).parent / "data"


@pytest.fixture
def store() -> TransitionStore:
    return TransitionStore.from_source(DATA_DIR)


@pytest.fixture
def crosswalk(store: TransitionStore) -> Crosswalk:
    return Crosswalk(store)
