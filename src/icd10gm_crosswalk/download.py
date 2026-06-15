"""Best-effort downloader for BfArM ICD-10-GM transition (Überleitung) ZIPs.

The library **never** redistributes BfArM data. This module instead helps *you*
fetch it to your own machine, which is what BfArM's terms permit: the files are
free but copyrighted, you accept a usage agreement on download, you may not pass
the files on "in the acquired format", and you *may* build and share derived
"value-added products" (such as the crosswalk this library produces).

Two consequences shape the API:

* :func:`download_year` refuses to do anything unless you pass ``accept_terms=True``,
  which is your acknowledgement of the BfArM Downloadbedingungen (:data:`TERMS_URL`).
* BfArM's portal sits behind a consent gate and a bot-protection layer that often
  rejects scripted requests. When that happens we do not paper over it: we raise
  :class:`BfArMDownloadError` with the exact URL to open in a browser and the
  directory to drop the ZIP into. Local parsing then works identically.
"""

from __future__ import annotations

import os
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

__all__ = [
    "DOWNLOADS_PAGE",
    "TERMS_URL",
    "BfArMDownloadError",
    "default_cache_dir",
    "download_year",
    "transition_zip_url",
]

#: BfArM download conditions (Downloadbedingungen) — read before using this module.
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

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/17.0 Safari/605.1.15"
    ),
    "Accept": "application/zip,application/octet-stream,*/*",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    "Referer": "https://www.bfarm.de/DE/Kodiersysteme/Services/Downloads/_node.html",
}


class BfArMDownloadError(RuntimeError):
    """Raised when the BfArM portal could not be fetched programmatically."""


def transition_zip_url(year: int) -> str:
    """The BfArM URL for the transition (Überleitung) package of edition ``year``.

    This ZIP holds ``icd10gm<year>syst_umsteiger_<prev>_<year>.txt`` — the table
    mapping the *previous* edition's codes onto ``year``'s codes.
    """
    return _UEBERL_URL.format(year=year)


def default_cache_dir() -> Path:
    """Where downloaded ZIPs are cached.

    Honours ``ICD10GM_CACHE_DIR``, then ``XDG_CACHE_HOME``, else ``~/.cache``.
    """
    if env := os.environ.get("ICD10GM_CACHE_DIR"):
        return Path(env).expanduser()
    base = os.environ.get("XDG_CACHE_HOME")
    root = Path(base).expanduser() if base else Path.home() / ".cache"
    return root / "icd10gm-crosswalk"


def _manual_instructions(year: int, target: Path) -> str:
    return (
        f"\nDownload it manually instead:\n"
        f"  1. Open {transition_zip_url(year)}\n"
        f"     (accept the BfArM download terms: {TERMS_URL})\n"
        f"  2. Save the ZIP to {target}\n"
        f"Then point the library at {target.parent} (or the ZIP directly)."
    )


def download_year(
    year: int,
    *,
    accept_terms: bool,
    cache_dir: str | Path | None = None,
    timeout: float = 60.0,
    force: bool = False,
) -> Path:
    """Download edition ``year``'s transition ZIP into the cache, returning its path.

    Parameters
    ----------
    year:
        The *later* edition year (e.g. ``2024`` for the 2023→2024 transition).
    accept_terms:
        Must be ``True``. By passing it you acknowledge the BfArM Downloadbedingungen
        (:data:`TERMS_URL`). The download establishes a usage agreement between you
        and BfArM; this library is merely the transport.
    cache_dir:
        Target directory. Defaults to :func:`default_cache_dir`.
    force:
        Re-download even if a valid cached ZIP already exists.

    Raises
    ------
    PermissionError
        If ``accept_terms`` is not ``True``.
    BfArMDownloadError
        If the portal rejects the request (its bot-protection commonly does) — the
        message includes the exact URL and target path for a manual download.
    """
    if accept_terms is not True:
        raise PermissionError(
            "BfArM ICD-10-GM files are free but copyrighted, and downloading them "
            "forms a usage agreement with BfArM. Read the terms at "
            f"{TERMS_URL} and pass accept_terms=True to proceed."
        )

    cache = Path(cache_dir).expanduser() if cache_dir else default_cache_dir()
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / f"icd10gm{year}syst-ueberl.zip"

    if target.exists() and not force and zipfile.is_zipfile(target):
        return target

    url = transition_zip_url(year)
    request = urllib.request.Request(url, headers=_BROWSER_HEADERS)  # noqa: S310 (https only)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            data = response.read()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
        raise BfArMDownloadError(
            f"could not fetch {url}: {exc}." + _manual_instructions(year, target)
        ) from exc

    tmp = target.with_suffix(".zip.part")
    tmp.write_bytes(data)
    if not zipfile.is_zipfile(tmp):
        tmp.unlink(missing_ok=True)
        raise BfArMDownloadError(
            f"the response from {url} was not a ZIP (the portal likely served its "
            f"consent page or blocked the request)."
            + _manual_instructions(year, target)
        )
    tmp.replace(target)
    return target
