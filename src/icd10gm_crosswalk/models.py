"""Core data model for ICD-10-GM transitions and crosswalk results.

Everything here is a plain, immutable value object. The semantics mirror the
official BfArM *Umsteiger* (transition) tables, whose rows are::

    CodePrev ; CodeCur ; A(uto-forward) ; A(uto-backward)

* ``CodePrev`` / ``CodeCur`` — the code in the earlier / later annual edition.
* the third field is ``A`` when the **forward** conversion (prev → cur) can be
  applied automatically, and empty when it needs manual review.
* the fourth field is ``A`` when the **backward** conversion (cur → prev) is
  automatic, and empty otherwise.

A 1:n *split* shows up as several rows sharing one ``CodePrev`` (forward usually
non-automatic — you cannot tell which finer child applies); an n:1 *merge* shows
up as several rows sharing one ``CodeCur`` (backward non-automatic).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

__all__ = [
    "MapResult",
    "MappingKind",
    "StepResult",
    "Transition",
]


class MappingKind(StrEnum):
    """How one source code relates to its target(s) across a transition.

    The four kinds named in the BfArM model, plus :attr:`IDENTITY` as the common
    special case of a 1:1 mapping where the code is unchanged. A :class:`~enum.StrEnum`
    so the value serialises cleanly (e.g. to CSV/JSON) as ``"split"`` etc.
    """

    IDENTITY = "identity"
    """1:1, and the code itself is unchanged (``A00.0 → A00.0``)."""

    ONE_TO_ONE = "one_to_one"
    """1:1 to a *different* code (the report calls this ``remapped``)."""

    SPLIT = "split"
    """1:n — the source was subdivided into several finer codes."""

    MERGE = "merge"
    """n:1 — the source was absorbed into a code that other codes also map to."""

    DELETED = "deleted"
    """The code has no successor in the target edition (retired without one)."""

    @property
    def is_ambiguous(self) -> bool:
        """True when the forward direction does not yield a single clear code.

        A split has several candidate targets; a deletion has none. Identity,
        1:1 and merge each resolve to exactly one forward target.
        """
        return self in (MappingKind.SPLIT, MappingKind.DELETED)


@dataclass(frozen=True, slots=True)
class Transition:
    """One row of a yearly Umsteiger table."""

    code_prev: str
    code_cur: str
    auto_forward: bool
    auto_backward: bool


@dataclass(frozen=True, slots=True)
class StepResult:
    """Mapping a single code across **one** consecutive-year step.

    ``targets`` is the de-duplicated, sorted set of successor codes. ``automatic``
    is ``True`` only when every contributing row had the automatic-forward flag.
    ``merged_from`` lists the *other* source codes that map to any of this code's
    targets in the same step — non-empty for an n:1 merge, and also for a split
    one of whose children absorbs sibling codes (so the merge signal is not lost).
    """

    code: str
    from_year: int
    to_year: int
    targets: tuple[str, ...]
    kind: MappingKind
    automatic: bool
    merged_from: tuple[str, ...] = field(default_factory=tuple)

    @property
    def changed(self) -> bool:
        """True unless this step left the code exactly as it was."""
        return self.kind is not MappingKind.IDENTITY


@dataclass(frozen=True, slots=True)
class MapResult:
    """Mapping a single code across a (possibly multi-year) range.

    The net forward relationship is summarised by :attr:`kind` and :attr:`targets`;
    :attr:`steps` keeps the full per-year trace so callers can see *where* an
    ambiguity or manual step was introduced. Merge information — which other
    source codes share this result's target(s) — is surfaced separately in
    :attr:`merged_from`, because a forward classification alone cannot express it.
    """

    code: str
    from_year: int
    to_year: int
    targets: tuple[str, ...]
    kind: MappingKind
    automatic: bool
    steps: tuple[StepResult, ...] = field(default_factory=tuple)
    merged_from: tuple[str, ...] = field(default_factory=tuple)

    @property
    def needs_manual_review(self) -> bool:
        """True when any step in the chain was non-automatic going forward."""
        return not self.automatic

    @property
    def ambiguous(self) -> bool:
        """True when the chain does not resolve to a single forward target.

        This is the honest "you must look at this" signal: either the net result
        has more than one candidate code (a split, or a split somewhere along the
        chain that never re-merged), or the code was deleted with no successor.
        """
        return len(self.targets) != 1

    @property
    def is_merge(self) -> bool:
        """True when this code shared a target with other codes somewhere in the chain.

        That is, it was absorbed alongside :attr:`merged_from` into a common code at
        some step — whether as a clean n:1 merge or as a split whose child also took
        in siblings.
        """
        return bool(self.merged_from)

    @property
    def single_target(self) -> str | None:
        """The lone target code when unambiguous, else ``None``."""
        return self.targets[0] if len(self.targets) == 1 else None
