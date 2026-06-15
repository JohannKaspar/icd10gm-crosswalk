"""Helpers for ICD-10-GM multiple-coding notation (Kreuz †, Stern *, Ausrufezeichen !).

ICD-10-GM expresses combined diagnoses with role markers on otherwise ordinary
codes: a *Kreuz* (dagger, ``†`` or ``+``) tags the underlying/aetiology code, a
*Stern* (``*``) the manifestation, and an *Ausrufezeichen* (``!``) a secondary
code. Sources frequently join the components of one diagnosis into a single
string, e.g. ``A41.9,R65.1!`` or ``D48.9+,D63.0*``.

BfArM's transition tables, by contrast, key on **bare** codes — no markers, no
compounds. These helpers bridge the gap: separate a code from its marker and
split a compound string into components, so each component can be mapped on its
own and its marker re-applied to the result.
"""

from __future__ import annotations

__all__ = [
    "COMPONENT_SEPARATOR",
    "MARKERS",
    "split_components",
    "split_marker",
    "strip_markers",
]

#: Trailing role markers: Kreuz/dagger (``†``, ``+``), Stern (``*``),
#: Ausrufezeichen (``!``), and ``#`` (a BfArM variant), in any combination.
MARKERS = "†+*!#"

#: Default separator joining the components of a compound diagnosis.
COMPONENT_SEPARATOR = ","


def split_marker(code: str) -> tuple[str, str]:
    """Split a code into ``(bare_code, trailing_marker)``.

    The marker is whatever run of :data:`MARKERS` characters trails the code
    (usually one); the bare code is what remains. ``("A00.0", "")`` for an
    unmarked code.
    """
    stripped = code.strip()
    bare = stripped.rstrip(MARKERS)
    return bare, stripped[len(bare) :]


def strip_markers(code: str) -> str:
    """Return ``code`` without its trailing role marker(s)."""
    return split_marker(code)[0]


def split_components(text: str, sep: str = COMPONENT_SEPARATOR) -> list[str]:
    """Split a compound normalization into its component codes, markers preserved.

    Whitespace is trimmed and empty parts dropped; the markers stay on each
    component so a caller can keep the etiology/manifestation roles. Pass ``sep``
    to handle a different join convention (e.g. ``" "`` for space-joined pairs).

    ``split_components("A41.9,R65.1!") == ["A41.9", "R65.1!"]``
    """
    return [part.strip() for part in text.split(sep) if part.strip()]
