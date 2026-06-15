"""Optional ClaML-backed lookup of a code's Kreuz-Stern role, for marker validation.

The crosswalk maps bare codes; :mod:`icd10gm_crosswalk.codes` lets a caller carry a
Kreuz (``†``/``+``), Stern (``*``), or Ausrufezeichen (``!``) marker through the
mapping. This module lets :class:`~icd10gm_crosswalk.crosswalk.Crosswalk` *check*
that such a marker is consistent with the code's actual role, using BfArM's ClaML
systematik as the single source of truth.

Why ClaML and not the flat metadata: BfArM's ``kodes.txt`` (§295/§301) marks Stern
(``O``) and ``!`` (``Z``) exactly, but lumps **dagger** codes in with ordinary
primary codes under ``P`` — of ~13k ``P`` codes only ~131 are truly dagger. ClaML
carries the exact ``usage="dagger"``/``"aster"`` designation (plus the §295 Meta),
so a single ClaML file gives all three roles precisely.

The library never bundles ClaML; point :meth:`Systematik.from_source` at a ClaML
file/zip/dir you obtained from BfArM.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
import zipfile
from collections import defaultdict
from collections.abc import Iterator
from enum import StrEnum
from pathlib import Path

__all__ = ["MarkerValidationWarning", "Role", "Systematik"]


class MarkerValidationWarning(UserWarning):
    """A Kreuz/Stern/``!`` marker could not be validated, or contradicts the catalog."""


class Role(StrEnum):
    """A code's role in the ICD-10-GM multiple-coding system."""

    DAGGER = "dagger"
    """Kreuz (``†``): the underlying/aetiology code of a dagger-asterisk pair."""

    STAR = "star"
    """Stern (``*``): the manifestation code; usable only as a secondary code."""

    EXCLAMATION = "exclamation"
    """Ausrufezeichen (``!``): an additional/secondary code."""

    PRIMARY = "primary"
    """An ordinary primary code (not a dagger)."""

    NONCODABLE = "noncodable"
    """Not usable for coding (e.g. a 3-digit category header)."""


# Marker character -> the role it asserts.
_MARKER_ROLE = {
    "*": Role.STAR,
    "!": Role.EXCLAMATION,
    "†": Role.DAGGER,
    "+": Role.DAGGER,
}

_PARA_ROLE = {
    "O": Role.STAR,
    "Z": Role.EXCLAMATION,
    "P": Role.PRIMARY,
    "V": Role.NONCODABLE,
}


def expected_role(marker: str) -> Role | None:
    """The role a marker asserts, or ``None`` for an unrecognised/empty marker."""
    for ch in marker:
        if ch in _MARKER_ROLE:
            return _MARKER_ROLE[ch]
    return None


def _prefixes(code: str) -> Iterator[str]:
    """Yield ``code`` and its shorter dotted ancestors down to 3 chars.

    ``E10.30 -> E10.3 -> E10`` — so a modifier-expanded terminal inherits the role
    of its nearest annotated ancestor.
    """
    current = code
    yield current
    while len(current) > 3:
        current = current[:-1]
        if current.endswith("."):
            current = current[:-1]
        yield current


class Systematik:
    """A code → :class:`Role` table parsed from a BfArM ICD-10-GM ClaML file."""

    def __init__(self, roles: dict[str, Role]) -> None:
        self._roles = roles

    def role(self, code: str) -> Role | None:
        """Role of ``code`` (from the nearest annotated ancestor), or ``None``."""
        for prefix in _prefixes(code.strip()):
            role = self._roles.get(prefix)
            if role is not None:
                return role
        return None

    def __len__(self) -> int:
        return len(self._roles)

    def __repr__(self) -> str:
        return f"Systematik({len(self._roles)} coded entries)"

    # -- construction ------------------------------------------------------ #
    @classmethod
    def from_source(cls, source: str | Path) -> Systematik:
        """Build from a ClaML ``.xml``, a ``.zip`` containing one, or a directory."""
        text = _find_claml(Path(source).expanduser())
        if text is None:
            raise ValueError(
                f"no ICD-10-GM ClaML XML found under {source!r}. Point this at the "
                "BfArM ...syst-claml package (zip), its XML, or a directory."
            )
        return cls.from_claml(text)

    @classmethod
    def from_claml(cls, xml_text: str | bytes) -> Systematik:
        """Build from the raw ClaML XML content.

        Reads with the stdlib parser (no extra dependency). ElementTree does not
        resolve external entities, and we reject any custom ``<!ENTITY>``
        declaration outright, which closes the entity-expansion ("billion laughs")
        vector for the real BfArM ClaML, which declares none.
        """
        blob = (
            xml_text
            if isinstance(xml_text, str)
            else xml_text.decode("utf-8", "replace")
        )
        if "<!ENTITY" in blob:
            raise ValueError("ClaML with custom entity declarations is rejected.")
        root = ET.fromstring(blob)  # noqa: S314 - entities rejected above; no external DTD load
        roles: dict[str, Role] = {}

        # 1) explicit per-Class roles: usage attribute, else the §295 Meta.
        for cls_el in root.iter("Class"):
            code = cls_el.get("code")
            if not code:
                continue
            role = cls._class_role(cls_el)
            if role is not None:
                roles[code] = role

        # 2) modifier-expanded dagger/star (e.g. the diabetes E10-E14 .2/.3/.4 block):
        #    a ModifierClass digit carries the usage; apply it to every class that
        #    references that modifier. Dagger/Stern win over a plain ancestor role.
        modifier_usage: dict[str, dict[str, str]] = defaultdict(dict)
        for mc in root.iter("ModifierClass"):
            modifier = mc.get("modifier")
            digit = mc.get("code")
            usage = mc.get("usage")
            if modifier and digit and usage in ("dagger", "aster"):
                modifier_usage[modifier][digit] = usage
        if modifier_usage:
            for cls_el in root.iter("Class"):
                base = cls_el.get("code")
                if not base:
                    continue
                for mb in cls_el.findall("ModifiedBy"):
                    for digit, usage in modifier_usage.get(mb.get("code"), {}).items():
                        roles[base + digit] = (
                            Role.DAGGER if usage == "dagger" else Role.STAR
                        )

        return cls(roles)

    @staticmethod
    def _class_role(cls_el: ET.Element) -> Role | None:
        usage = cls_el.get("usage")
        if usage == "dagger":
            return Role.DAGGER
        if usage == "aster":
            return Role.STAR
        for meta in cls_el.findall("Meta"):
            if meta.get("name") == "Para295":
                return _PARA_ROLE.get(meta.get("value", ""))
        return None


def _find_claml(path: Path) -> str | None:
    """Return the text of the first ClaML XML reachable from ``path``, or ``None``."""

    def is_claml(name: str) -> bool:
        low = name.lower()
        return low.endswith(".xml") and "claml" in low

    if path.is_dir():
        for child in sorted(path.rglob("*")):
            if child.is_file() and (
                child.suffix.lower() == ".zip" or is_claml(child.name)
            ):
                found = _find_claml(child)
                if found is not None:
                    return found
        return None

    suffix = path.suffix.lower()
    if suffix == ".zip":
        try:
            with zipfile.ZipFile(path) as zf:
                for name in zf.namelist():
                    if is_claml(name):
                        return zf.read(name).decode("utf-8", "replace")
        except zipfile.BadZipFile:
            return None
        return None
    if is_claml(path.name):
        return path.read_text(encoding="utf-8", errors="replace")
    return None
