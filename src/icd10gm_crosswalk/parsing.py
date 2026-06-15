"""Locate and parse BfArM *Umsteiger* (transition) tables.

The library never bundles BfArM data. These helpers read it from wherever the
user keeps it — a loose ``.txt`` file, a year ZIP, or a directory of year ZIPs —
including the nested-ZIP layout BfArM has used since the 2022 edition, where the
Umsteiger lives inside ``icd10gm<YYYY>syst-ueberl.zip`` *inside* the year ZIP.

Filename shapes seen in the wild (all matched by :data:`UMSTEIGER_RE`)::

    icd10gm2018syst_umsteiger_2017_2018.txt
    icd10gm2023syst_umsteiger_2022_2023_20221206.txt   # trailing date stamp
    icd10gm2024syst_umsteiger_2023_20221206_2024.txt   # date stamp in the middle
"""

from __future__ import annotations

import io
import re
import zipfile
import zlib
from collections.abc import Iterator
from pathlib import Path

from .models import Transition

__all__ = [
    "UMSTEIGER_RE",
    "find_umsteiger",
    "parse_umsteiger_text",
    "umsteiger_year_pair",
]

#: Guard rails for untrusted archives. The real BfArM layout nests 2 levels and its
#: Umsteiger members are well under a megabyte, so these caps never exclude valid
#: data; they only stop a maliciously crafted zip (a bomb or a deeply nested quine)
#: fed through the public ``from_source`` API from exhausting memory or the stack.
MAX_ZIP_DEPTH = 4
MAX_MEMBER_BYTES = 64 * 1024 * 1024  # 64 MiB uncompressed, per member

#: Matches any Umsteiger filename and captures the two 4-digit years it spans.
#: Tolerates optional 8-digit date stamps between/after the years.
UMSTEIGER_RE = re.compile(
    r"umsteiger_(?P<prev>\d{4})_(?:\d{8}_)?(?P<cur>\d{4})(?:_\d{8})?\.txt$",
    re.IGNORECASE,
)


def parse_umsteiger_text(text: str) -> list[Transition]:
    """Parse the raw text of one Umsteiger table into :class:`Transition` rows.

    Blank lines and malformed rows (fewer than two fields) are skipped. A row
    with an empty ``CodeCur`` is preserved as a deletion (``code_cur == ""``).
    """
    transitions: list[Transition] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        fields = line.split(";")
        if len(fields) < 2:
            continue
        code_prev = fields[0].strip()
        code_cur = fields[1].strip()
        if not code_prev:
            continue
        auto_forward = len(fields) > 2 and fields[2].strip().upper() == "A"
        auto_backward = len(fields) > 3 and fields[3].strip().upper() == "A"
        transitions.append(Transition(code_prev, code_cur, auto_forward, auto_backward))
    return transitions


def umsteiger_year_pair(name: str) -> tuple[int, int] | None:
    """Return the ``(prev, cur)`` years in an Umsteiger filename, or ``None``."""
    match = UMSTEIGER_RE.search(name)
    if not match:
        return None
    return int(match.group("prev")), int(match.group("cur"))


def _read_member(zf: zipfile.ZipFile, name: str) -> bytes | None:
    """Read a member, returning ``None`` if it is implausibly large or corrupt.

    The size check uses the declared uncompressed size first (cheap, defeats a
    classic zip bomb before any decompression) and bounds the actual read as a
    backstop against a lying header.
    """
    try:
        if zf.getinfo(name).file_size > MAX_MEMBER_BYTES:
            return None
        with zf.open(name) as member:
            data = member.read(MAX_MEMBER_BYTES + 1)
    except (zipfile.BadZipFile, OSError, zlib.error, KeyError):
        return None
    return None if len(data) > MAX_MEMBER_BYTES else data


def _scan_zip(
    zf: zipfile.ZipFile, label: str, depth: int = 0
) -> Iterator[tuple[str, str]]:
    """Yield ``(label, text)`` for Umsteiger members, recursing into nested ZIPs.

    ``depth`` bounds the nested-ZIP recursion (:data:`MAX_ZIP_DEPTH`) so a crafted
    or self-referential archive cannot drive unbounded recursion.
    """
    if depth >= MAX_ZIP_DEPTH:
        return
    for name in zf.namelist():
        if name.lower().endswith(".zip"):
            data = _read_member(zf, name)
            if data is None:
                continue
            try:
                with zipfile.ZipFile(io.BytesIO(data)) as nested:
                    yield from _scan_zip(nested, f"{label}!{name}", depth + 1)
            except (zipfile.BadZipFile, OSError, zlib.error):
                continue
        elif UMSTEIGER_RE.search(name):
            data = _read_member(zf, name)
            if data is not None:
                yield f"{label}!{name}", data.decode("utf-8", "replace")


def _iter_source(path: Path) -> Iterator[tuple[str, str]]:
    """Yield ``(member_label, text)`` for every Umsteiger table reachable from ``path``.

    ``path`` may be a single ``.txt`` file, a single ``.zip``, or a directory
    (searched recursively for ``*.zip`` and ``*umsteiger*.txt``).
    """
    if path.is_dir():
        for child in sorted(path.rglob("*")):
            if child.is_file() and (
                child.suffix.lower() == ".zip"
                or (child.suffix.lower() == ".txt" and UMSTEIGER_RE.search(child.name))
            ):
                yield from _iter_source(child)
        return

    suffix = path.suffix.lower()
    if suffix == ".zip":
        try:
            with zipfile.ZipFile(path) as zf:
                yield from _scan_zip(zf, str(path))
        except zipfile.BadZipFile:
            return
    elif suffix == ".txt" and UMSTEIGER_RE.search(path.name):
        yield str(path), path.read_text(encoding="utf-8", errors="replace")


def find_umsteiger(
    source: str | Path,
) -> dict[tuple[int, int], list[Transition]]:
    """Discover every Umsteiger table under ``source``, keyed by ``(prev, cur)`` year.

    ``source`` is a path to a file, ZIP, or directory. If two members describe
    the same year pair (e.g. a stray duplicate), the first one encountered by a
    sorted traversal wins, which keeps results deterministic.
    """
    found: dict[tuple[int, int], list[Transition]] = {}
    for label, text in _iter_source(Path(source).expanduser()):
        pair = umsteiger_year_pair(label)
        if pair is None or pair in found:
            continue
        found[pair] = parse_umsteiger_text(text)
    return found
