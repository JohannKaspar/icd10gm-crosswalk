"""Tests for the mapping engine: every kind, chaining, flags, ambiguity."""

from __future__ import annotations

from icd10gm_crosswalk import Crosswalk, MappingKind, TransitionStore, YearStep
from icd10gm_crosswalk.models import Transition


# -- single step ----------------------------------------------------------- #
def test_step_identity(crosswalk: Crosswalk) -> None:
    sr = crosswalk.map_step("Z00.0", 2000)
    assert sr.kind is MappingKind.IDENTITY
    assert sr.targets == ("Z00.0",)
    assert sr.automatic is True
    assert sr.changed is False


def test_step_one_to_one(crosswalk: Crosswalk) -> None:
    sr = crosswalk.map_step("Z01.0", 2000)
    assert sr.kind is MappingKind.ONE_TO_ONE
    assert sr.targets == ("Z01.1",)
    assert sr.automatic is True


def test_step_split_is_manual(crosswalk: Crosswalk) -> None:
    sr = crosswalk.map_step("Z02.0", 2000)
    assert sr.kind is MappingKind.SPLIT
    assert sr.targets == ("Z02.00", "Z02.01")
    assert sr.automatic is False  # forward flag empty on split rows


def test_step_merge(crosswalk: Crosswalk) -> None:
    sr = crosswalk.map_step("Z03.0", 2000)
    assert sr.kind is MappingKind.MERGE
    assert sr.targets == ("Z03.9",)
    assert sr.merged_from == ("Z03.1",)
    assert sr.automatic is True


def test_step_deleted(crosswalk: Crosswalk) -> None:
    sr = crosswalk.map_step("Z04.0", 2000)
    assert sr.kind is MappingKind.DELETED
    assert sr.targets == ()


def test_step_one_to_one_manual(crosswalk: Crosswalk) -> None:
    sr = crosswalk.map_step("Z05.0", 2000)
    assert sr.kind is MappingKind.ONE_TO_ONE
    assert sr.automatic is False


def test_step_unlisted_code_is_identity(crosswalk: Crosswalk) -> None:
    sr = crosswalk.map_step("Z99.9", 2000)
    assert sr.kind is MappingKind.IDENTITY
    assert sr.targets == ("Z99.9",)


# -- chained --------------------------------------------------------------- #
def test_chain_identity_carries_forward(crosswalk: Crosswalk) -> None:
    res = crosswalk.map("Z00.0", 2000, 2003)
    assert res.kind is MappingKind.IDENTITY
    assert res.targets == ("Z00.0",)
    assert res.ambiguous is False
    assert res.needs_manual_review is False


def test_chain_one_to_one_then_carry(crosswalk: Crosswalk) -> None:
    res = crosswalk.map("Z01.0", 2000, 2003)
    assert res.kind is MappingKind.ONE_TO_ONE
    assert res.targets == ("Z01.1",)


def test_chain_split_accumulates(crosswalk: Crosswalk) -> None:
    res = crosswalk.map("Z02.0", 2000, 2002)
    # Z02.0 -> {Z02.00, Z02.01} -> {Z02.00, Z02.010, Z02.011}
    assert res.kind is MappingKind.SPLIT
    assert res.targets == ("Z02.00", "Z02.010", "Z02.011")
    assert res.ambiguous is True
    assert res.needs_manual_review is True
    assert res.single_target is None


def test_chain_merge_flagged(crosswalk: Crosswalk) -> None:
    res = crosswalk.map("Z03.0", 2000, 2001)
    assert res.kind is MappingKind.ONE_TO_ONE  # net forward cardinality is 1
    assert res.is_merge is True
    assert res.merged_from == ("Z03.1",)


def test_chain_deleted(crosswalk: Crosswalk) -> None:
    res = crosswalk.map("Z04.0", 2000, 2003)
    assert res.kind is MappingKind.DELETED
    assert res.targets == ()
    assert res.ambiguous is True
    # the chain stops at the deleting step rather than tracing dead years
    assert all(s.from_year == 2000 for s in res.steps)


def test_chain_split_then_merge_reconverges(crosswalk: Crosswalk) -> None:
    res = crosswalk.map("Z06.0", 2000, 2002)
    # splits to Z06.1/Z06.2 then both merge back to Z06.9
    assert res.targets == ("Z06.9",)
    assert res.kind is MappingKind.ONE_TO_ONE
    assert res.ambiguous is False  # net single code...
    assert res.needs_manual_review is True  # ...but the split step was manual
    assert res.is_merge is True
    kinds = [s.kind for s in res.steps]
    assert MappingKind.SPLIT in kinds
    assert MappingKind.MERGE in kinds


def test_same_year_is_identity(crosswalk: Crosswalk) -> None:
    res = crosswalk.map("Z02.0", 2000, 2000)
    assert res.kind is MappingKind.IDENTITY
    assert res.targets == ("Z02.0",)
    assert res.steps == ()


def test_kind_is_ambiguous_property() -> None:
    assert MappingKind.SPLIT.is_ambiguous
    assert MappingKind.DELETED.is_ambiguous
    assert not MappingKind.IDENTITY.is_ambiguous
    assert not MappingKind.MERGE.is_ambiguous


# -- recommend ------------------------------------------------------------- #
def test_recommend_unique(crosswalk: Crosswalk) -> None:
    res = crosswalk.map("Z01.0", 2000, 2003)
    assert crosswalk.recommend(res) == "Z01.1"


def test_recommend_common_parent(crosswalk: Crosswalk) -> None:
    res = crosswalk.map("Z02.0", 2000, 2002)
    # Z02.00 | Z02.010 | Z02.011 -> deepest common parent "Z02.0"
    assert crosswalk.recommend(res) == "Z02.0"


def test_recommend_deleted_is_none(crosswalk: Crosswalk) -> None:
    res = crosswalk.map("Z04.0", 2000, 2003)
    assert crosswalk.recommend(res) is None


# -- split that also co-merges (merge signal must not be lost on a split) --- #
def _co_merge_crosswalk() -> Crosswalk:
    # A splits to X and Y; B also lands on Y -> A co-merges into Y while splitting.
    rows = [
        Transition("A", "X", False, True),
        Transition("A", "Y", False, True),
        Transition("B", "Y", True, False),
    ]
    return Crosswalk(TransitionStore([YearStep.from_transitions(2000, 2001, rows)]))


def test_step_split_still_reports_co_merge() -> None:
    sr = _co_merge_crosswalk().map_step("A", 2000)
    assert sr.kind is MappingKind.SPLIT  # forward classification unchanged
    assert sr.merged_from == ("B",)  # but the merge is still surfaced


def test_chain_split_with_co_merge_is_merge() -> None:
    res = _co_merge_crosswalk().map("A", 2000, 2001)
    assert res.kind is MappingKind.SPLIT
    assert res.is_merge is True
    assert res.merged_from == ("B",)
