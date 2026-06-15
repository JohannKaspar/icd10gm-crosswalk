"""Command-line interface: ``icd10gm-crosswalk {info,map,urls}``.

Stdlib ``argparse`` only — the library has no runtime dependencies.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from . import __version__
from .crosswalk import Crosswalk
from .sources import download_instructions
from .store import TransitionStore


def _add_data_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--data",
        required=True,
        metavar="PATH",
        help="BfArM year ZIP, a directory of them, or an umsteiger_*.txt file",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="icd10gm-crosswalk",
        description="Crosswalk ICD-10-GM codes across annual editions "
        "using official BfArM transition tables.",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_info = sub.add_parser("info", help="show the editions and steps a source covers")
    _add_data_arg(p_info)

    p_map = sub.add_parser("map", help="map one code across an edition range")
    p_map.add_argument("code", help="the ICD-10-GM code to map, e.g. J45.0")
    p_map.add_argument("--from", dest="from_year", type=int, required=True)
    p_map.add_argument("--to", dest="to_year", type=int, required=True)
    p_map.add_argument("--trace", action="store_true", help="print the per-year path")
    _add_data_arg(p_map)

    p_urls = sub.add_parser(
        "urls", help="print the BfArM download links needed for an edition range"
    )
    p_urls.add_argument("--from", dest="from_year", type=int, required=True)
    p_urls.add_argument("--to", dest="to_year", type=int, required=True)
    return parser


def _cmd_info(args: argparse.Namespace) -> int:
    store = TransitionStore.from_source(args.data)
    print(f"{store!r}")
    print(f"editions: {store.years}")
    for step in store.steps:
        print(
            f"  {step.from_year}→{step.to_year}: "
            f"{sum(len(v) for v in step.forward.values())} rows, "
            f"{len(step.codes_prev)} source codes"
        )
    return 0


def _cmd_map(args: argparse.Namespace) -> int:
    cw = Crosswalk.from_source(args.data)
    result = cw.map(args.code, args.from_year, args.to_year)
    rec = cw.recommend(result)
    print(f"{result.code}  {result.from_year}→{result.to_year}")
    print(f"  kind        : {result.kind.value}")
    print(f"  targets     : {', '.join(result.targets) or '<none>'}")
    print(f"  recommended : {rec or '<none>'}")
    print(f"  automatic   : {result.automatic}")
    print(f"  ambiguous   : {result.ambiguous}")
    if result.is_merge:
        print(f"  merged with : {', '.join(result.merged_from)}")
    if args.trace:
        print("  trace:")
        for sr in result.steps:
            arrow = ", ".join(sr.targets) or "<deleted>"
            flag = "" if sr.automatic else "  [manual]"
            path = f"{sr.from_year}→{sr.to_year} {sr.code} → {arrow}"
            print(f"    {path}  ({sr.kind.value}){flag}")
    return 0


def _cmd_urls(args: argparse.Namespace) -> int:
    print(download_instructions(args.from_year, args.to_year))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point. Returns a process exit code."""
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "info":
            return _cmd_info(args)
        if args.command == "map":
            return _cmd_map(args)
        if args.command == "urls":
            return _cmd_urls(args)
    except (ValueError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 2  # unreachable: subparser is required


if __name__ == "__main__":
    raise SystemExit(main())
