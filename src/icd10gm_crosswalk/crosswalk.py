"""The crosswalk engine: map ICD-10-GM codes across editions, with honest flags.

:class:`Crosswalk` wraps a :class:`~icd10gm_crosswalk.store.TransitionStore` and
offers two operations:

* :meth:`Crosswalk.map_step` — map one code across a single consecutive-year step,
  classifying the relationship as 1:1, 1:n (split), n:1 (merge), or none (deleted).
* :meth:`Crosswalk.map` — chain those steps across an arbitrary year range, taking
  the union of successors at each step and reporting where ambiguity or a
  manual-review step was introduced.

Design note on *kind* across a chain
------------------------------------
The net :attr:`~icd10gm_crosswalk.models.MapResult.kind` is decided purely by the
**forward cardinality** of the final target set (identity / one-to-one / split /
deleted). Merges are an inherently *inverse* relationship — "other codes also
landed here" — so they cannot be read off the forward set alone. They are
therefore surfaced *separately* from ``kind`` rather than overriding it:
:attr:`~icd10gm_crosswalk.models.StepResult.merged_from` is populated whenever a
code shares a target with other codes — including a code that *splits* into
children, one of which also absorbs siblings — and the chained result aggregates
this into :attr:`~icd10gm_crosswalk.models.MapResult.is_merge` /
:attr:`~icd10gm_crosswalk.models.MapResult.merged_from`. Keeping the forward
``kind`` undisturbed is also what makes the result reproduce the official one-off
crosswalks exactly.
"""

from __future__ import annotations

import os
from pathlib import Path

from .models import MappingKind, MapResult, StepResult
from .store import TransitionStore, YearStep

__all__ = ["Crosswalk"]


class Crosswalk:
    """Map ICD-10-GM codes forward across editions using a transition store."""

    def __init__(self, store: TransitionStore) -> None:
        self.store = store

    @classmethod
    def from_source(cls, source: str | Path) -> Crosswalk:
        """Convenience constructor: build the store from ``source`` and wrap it."""
        return cls(TransitionStore.from_source(source))

    # -- single step ------------------------------------------------------- #
    def map_step(self, code: str, from_year: int) -> StepResult:
        """Map ``code`` across the single step beginning at ``from_year``.

        A code absent from the step's table is carried forward unchanged
        (identity) — this mirrors BfArM's tables, which only list codes that
        change, and keeps long chains stable. Raises :class:`KeyError` if no step
        starts at ``from_year``.
        """
        step = self.store.step(from_year)
        rows = step.forward.get(code)

        if rows is None:
            return StepResult(
                code, step.from_year, step.to_year, (code,), MappingKind.IDENTITY, True
            )

        targets = tuple(sorted({r.code_cur for r in rows if r.code_cur}))
        # Automatic only if every row that yields a real successor is auto-forward.
        contributing = [r for r in rows if r.code_cur]
        automatic = all(r.auto_forward for r in contributing)

        if not targets:
            return StepResult(
                code, step.from_year, step.to_year, (), MappingKind.DELETED, automatic
            )
        if targets == (code,):
            return StepResult(
                code,
                step.from_year,
                step.to_year,
                targets,
                MappingKind.IDENTITY,
                automatic,
            )

        # Other source codes landing on *any* of this code's targets — i.e. codes it
        # co-merges with. Computed for splits too, so a code that splits into children
        # one of which also absorbs siblings still reports the merge (it is not lost).
        merged_from = tuple(
            sorted(
                {
                    tr.code_prev
                    for target in targets
                    for tr in step.inverse.get(target, [])
                    if tr.code_prev != code
                }
            )
        )
        if len(targets) > 1:
            kind = MappingKind.SPLIT
        else:
            kind = MappingKind.MERGE if merged_from else MappingKind.ONE_TO_ONE
        return StepResult(
            code, step.from_year, step.to_year, targets, kind, automatic, merged_from
        )

    # -- chained ----------------------------------------------------------- #
    def map(self, code: str, from_year: int, to_year: int) -> MapResult:
        """Map ``code`` from ``from_year`` to ``to_year`` through every yearly step.

        Raises :class:`ValueError` if the store is missing any step in the range
        (see :meth:`TransitionStore.require_chain`). ``from_year == to_year`` is a
        valid no-op that returns an identity result.
        """
        chain: list[YearStep] = self.store.require_chain(from_year, to_year)

        frontier: set[str] = {code}
        trace: list[StepResult] = []
        automatic = True
        merged_from: set[str] = set()

        for step in chain:
            nxt: set[str] = set()
            for current in sorted(frontier):
                sr = self.map_step(current, step.from_year)
                trace.append(sr)
                if not sr.automatic:
                    automatic = False
                if sr.merged_from:
                    merged_from.update(sr.merged_from)
                nxt.update(sr.targets)
            frontier = nxt
            if not frontier:
                break  # deleted with no successor; later steps are moot

        targets = tuple(sorted(frontier))
        kind = self._classify(code, targets)
        return MapResult(
            code=code,
            from_year=from_year,
            to_year=to_year,
            targets=targets,
            kind=kind,
            automatic=automatic,
            steps=tuple(trace),
            merged_from=tuple(sorted(merged_from)),
        )

    @staticmethod
    def _classify(source: str, targets: tuple[str, ...]) -> MappingKind:
        """Net forward classification of a (possibly chained) mapping."""
        if not targets:
            return MappingKind.DELETED
        if targets == (source,):
            return MappingKind.IDENTITY
        if len(targets) > 1:
            return MappingKind.SPLIT
        return MappingKind.ONE_TO_ONE

    # -- representative-code helper ---------------------------------------- #
    @staticmethod
    def recommend(result: MapResult) -> str | None:
        """Pick a single representative code for ``result``, or ``None``.

        Useful when a downstream consumer needs *one* code (e.g. for hierarchical
        scoring) even though the honest mapping is 1:n:

        * unique target → that code;
        * a split where the original code survived among the new siblings → the
          original code;
        * any other split → the longest shared code prefix, trimmed to a dot
          boundary (``len >= 3``), e.g. ``B18.11|B18.12|B18.19 → B18.1``;
        * a cross-chapter split with no common prefix, or a deletion → ``None``
          (genuinely ambiguous / no successor; inspect :attr:`MapResult.kind`).

        This is a lossy convenience, **not** a hierarchy lookup: the prefix is
        lexical, so the result can be a category header (e.g. ``K58``) that is not
        itself a billable/leaf code, and it is not validated against any edition's
        catalog. Use :attr:`MapResult.targets` when you need the exact mapping.
        """
        targets = result.targets
        if not targets:
            return None
        if len(targets) == 1:
            return targets[0]
        if result.code in targets:
            return result.code
        parent = os.path.commonprefix(targets).rstrip(".")
        return parent if len(parent) >= 3 else None
