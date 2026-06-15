"""In-memory store of yearly transition steps with forward and inverse indices.

A :class:`TransitionStore` holds one :class:`YearStep` per consecutive-year pair
it was given. Each step exposes a forward index (``prev_code -> rows``) for
mapping old → new, and an inverse index (``cur_code -> rows``) used to detect
n:1 merges and to map new → old.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from .models import Transition
from .parsing import find_umsteiger

__all__ = ["TransitionStore", "YearStep"]


@dataclass(frozen=True, slots=True)
class YearStep:
    """One consecutive-year transition (``from_year -> to_year``)."""

    from_year: int
    to_year: int
    forward: dict[str, list[Transition]]
    inverse: dict[str, list[Transition]]

    @classmethod
    def from_transitions(
        cls, from_year: int, to_year: int, transitions: list[Transition]
    ) -> YearStep:
        forward: dict[str, list[Transition]] = defaultdict(list)
        inverse: dict[str, list[Transition]] = defaultdict(list)
        for tr in transitions:
            forward[tr.code_prev].append(tr)
            if tr.code_cur:
                inverse[tr.code_cur].append(tr)
        return cls(from_year, to_year, dict(forward), dict(inverse))

    @property
    def codes_prev(self) -> set[str]:
        """All source codes listed in this step (the earlier edition's catalog)."""
        return set(self.forward)

    @property
    def codes_cur(self) -> set[str]:
        """All target codes listed in this step (the later edition's catalog)."""
        return set(self.inverse)


class TransitionStore:
    """A collection of :class:`YearStep` objects spanning a range of editions."""

    def __init__(self, steps: list[YearStep]) -> None:
        self._steps: dict[int, YearStep] = {s.from_year: s for s in steps}
        if len(self._steps) != len(steps):
            raise ValueError("duplicate from_year among steps")

    @classmethod
    def from_source(cls, source: str | Path) -> TransitionStore:
        """Build a store from a file, ZIP, or directory of BfArM year ZIPs.

        See :func:`icd10gm_crosswalk.parsing.find_umsteiger` for accepted layouts.
        Raises :class:`ValueError` if no Umsteiger table is found.
        """
        tables = find_umsteiger(source)
        if not tables:
            raise ValueError(
                f"no Umsteiger transition tables found under {source!r}. "
                "Point this at a BfArM year ZIP, a directory of them, or an "
                "umsteiger_*.txt file."
            )
        steps = [
            YearStep.from_transitions(prev, cur, rows)
            for (prev, cur), rows in sorted(tables.items())
        ]
        return cls(steps)

    @property
    def steps(self) -> list[YearStep]:
        """The steps held, ordered by ``from_year``."""
        return [self._steps[y] for y in sorted(self._steps)]

    @property
    def years(self) -> list[int]:
        """All reachable edition years, ascending."""
        if not self._steps:
            return []
        froms = sorted(self._steps)
        return [*froms, self._steps[froms[-1]].to_year]

    @property
    def min_year(self) -> int:
        return min(self._steps)

    @property
    def max_year(self) -> int:
        return self._steps[max(self._steps)].to_year

    def step(self, from_year: int) -> YearStep:
        """The step starting at ``from_year``; raises :class:`KeyError` if absent."""
        return self._steps[from_year]

    def has_chain(self, from_year: int, to_year: int) -> bool:
        """True when every step from ``from_year`` to ``to_year`` is present."""
        if from_year > to_year:
            return False
        return all(y in self._steps for y in range(from_year, to_year))

    def require_chain(self, from_year: int, to_year: int) -> list[YearStep]:
        """Ordered steps for the range; raises ``ValueError`` if incomplete."""
        if from_year > to_year:
            raise ValueError(
                f"from_year ({from_year}) must not be after to_year ({to_year})"
            )
        missing = [y for y in range(from_year, to_year) if y not in self._steps]
        if missing:
            raise ValueError(
                f"missing transition step(s) for year(s) {missing}; "
                f"loaded steps cover {sorted(self._steps)}"
            )
        return [self._steps[y] for y in range(from_year, to_year)]

    def __repr__(self) -> str:
        if not self._steps:
            return "TransitionStore(empty)"
        return (
            f"TransitionStore({self.min_year}→{self.max_year}, "
            f"{len(self._steps)} steps)"
        )
