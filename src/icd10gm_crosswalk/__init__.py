"""icd10gm-crosswalk — map ICD-10-GM codes across annual editions.

A small, dependency-free Python library that turns BfArM's official *Umsteiger*
(transition) tables into a multi-year crosswalk, preserving the automatic-vs-manual
transition flag and honestly reporting the ambiguity that chained splits and merges
introduce.

Quick start
-----------
>>> from icd10gm_crosswalk import Crosswalk
>>> cw = Crosswalk.from_source("~/icd10gm-zips")  # doctest: +SKIP
>>> result = cw.map("J45.0", 2017, 2024)            # doctest: +SKIP
>>> result.kind, result.targets                     # doctest: +SKIP
(<MappingKind.SPLIT: 'split'>, ('J45.00', 'J45.01', ...))

The library never bundles or redistributes BfArM data; see
:mod:`icd10gm_crosswalk.sources` for helpers that point you at the exact files to
download yourself.
"""

from __future__ import annotations

from .crosswalk import Crosswalk
from .models import MappingKind, MapResult, StepResult, Transition
from .parsing import find_umsteiger, parse_umsteiger_text
from .sources import download_instructions, transition_zip_url, transition_zip_urls
from .store import TransitionStore, YearStep

__version__ = "0.1.0"

__all__ = [
    "Crosswalk",
    "MapResult",
    "MappingKind",
    "StepResult",
    "Transition",
    "TransitionStore",
    "YearStep",
    "__version__",
    "download_instructions",
    "find_umsteiger",
    "parse_umsteiger_text",
    "transition_zip_url",
    "transition_zip_urls",
]
