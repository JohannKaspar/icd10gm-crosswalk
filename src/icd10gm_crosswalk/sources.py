"""Where to get BfArM ICD-10-GM transition tables — the library never bundles them.

BfArM's files are free but copyrighted: downloading forms a usage agreement, you
may not redistribute the files "in the acquired format", and you *may* distribute
derived products (such as the crosswalk this library produces). So the library
neither ships nor fetches the data — it tells you the exact files to download
yourself, once, after which it reads them locally.

(BfArM's download portal sits behind an anti-bot gate that rejects scripted
requests, so an automated downloader would be unreliable. These helpers give you
the precise URLs instead, which never go stale silently.)
"""

from __future__ import annotations

__all__ = [
    "DOWNLOADS_PAGE",
    "TERMS_URL",
    "download_instructions",
    "transition_zip_url",
    "transition_zip_urls",
]

#: BfArM download conditions (Downloadbedingungen) — read and accept before downloading.
TERMS_URL = (
    "https://www.bfarm.de/SharedDocs/Downloads/DE/Kodiersysteme/"
    "downloadbedingungen-2025.pdf?__blob=publicationFile"
)

#: Human-facing landing page listing every classification download.
DOWNLOADS_PAGE = "https://www.bfarm.de/DE/Kodiersysteme/Services/Downloads/_node.html"

_UEBERL_URL = (
    "https://www.bfarm.de/SharedDocs/Downloads/DE/Kodiersysteme/klassifikationen/"
    "icd-10-gm/version{year}/icd10gm{year}syst-ueberl_zip.html?__blob=publicationFile"
)


def transition_zip_url(year: int) -> str:
    """The BfArM URL for the transition (Überleitung) ZIP of edition ``year``.

    That ZIP holds ``icd10gm<year>syst_umsteiger_<prev>_<year>.txt`` — the table
    for the single ``(year - 1) → year`` step.
    """
    return _UEBERL_URL.format(year=year)


def transition_zip_urls(from_year: int, to_year: int) -> list[tuple[int, str]]:
    """The ``(year, url)`` pairs needed to crosswalk ``from_year`` → ``to_year``.

    Crosswalking spans the steps ``from_year→from_year+1`` … ``to_year-1→to_year``,
    and each step lives in that *later* year's transition ZIP, so you need the
    Überleitung ZIP for every year in ``from_year + 1 … to_year``. Returns an empty
    list when the years are equal; raises :class:`ValueError` if reversed.
    """
    if from_year > to_year:
        raise ValueError(
            f"from_year ({from_year}) must not be after to_year ({to_year})"
        )
    return [
        (year, transition_zip_url(year)) for year in range(from_year + 1, to_year + 1)
    ]


def download_instructions(from_year: int, to_year: int) -> str:
    """A copy-pasteable list of the BfArM ZIPs a year range needs, and the terms.

    The library never fetches these for you (BfArM's portal blocks scripted access
    and the files may not be redistributed); download them once in your browser,
    then point :meth:`Crosswalk.from_source` at the folder you saved them in.
    """
    urls = transition_zip_urls(from_year, to_year)
    if not urls:
        return f"{from_year} and {to_year} are the same edition — no transition needed."
    lines = [
        f"Crosswalk {from_year}→{to_year} needs {len(urls)} BfArM transition ZIP(s):",
        f"Accept the BfArM download terms first: {TERMS_URL}",
        "",
    ]
    lines += [f"  {year - 1}→{year}: {url}" for year, url in urls]
    lines += [
        "",
        "Save them into one folder, then pass that folder to Crosswalk.from_source().",
    ]
    return "\n".join(lines)
