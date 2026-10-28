"""Command-line entry point for fresh-road."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .alsroads import (
    DEFAULT_SOURCE,
    DEFAULT_SOURCE_DATE,
    records_from_alsroads,
    run_alsroads,
    write_road_status_csv,
    write_road_status_json,
)


def _run(args: argparse.Namespace) -> int:
    """Run ALSroads against one LAS tile and one road set."""
    result = run_alsroads(
        args.las,
        args.dtm,
        args.roads,
        args.out_gpkg,
        r_libs_user=args.r_libs_user,
    )
    print(
        f"wrote {result['output']} using ALSroads {result['alsroads_version']}"
    )
    return 0


def _ingest(args: argparse.Namespace) -> int:
    """Convert ALSroads GPKG output to the road.status contract."""
    records = records_from_alsroads(
        args.gpkg,
        source=args.source,
        source_date=args.source_date,
        retrieved_utc=args.retrieved_utc,
    )
    write_road_status_json(args.out_json, records)
    write_road_status_csv(args.out_csv, records)
    print(f"wrote {len(records)} road records to {args.out_json} and {args.out_csv}")
    return 0


def _version(_: argparse.Namespace) -> int:
    print(__version__)
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(
        prog="fresh-road",
        description="ALSroads bridge and road.status contract",
    )
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="run the reference ALSroads bridge")
    run.add_argument("--las", type=Path, required=True)
    run.add_argument("--dtm", type=Path, required=True)
    run.add_argument("--roads", type=Path, required=True)
    run.add_argument("--out-gpkg", type=Path, required=True)
    run.add_argument("--r-libs-user", type=Path, default=None)
    run.set_defaults(func=_run)

    ingest = subparsers.add_parser("ingest", help="emit road.status JSON/CSV")
    ingest.add_argument("--gpkg", type=Path, required=True)
    ingest.add_argument("--out-json", type=Path, required=True)
    ingest.add_argument("--out-csv", type=Path, required=True)
    ingest.add_argument("--source", default=DEFAULT_SOURCE)
    ingest.add_argument("--source-date", default=DEFAULT_SOURCE_DATE)
    ingest.add_argument("--retrieved-utc", default=None)
    ingest.set_defaults(func=_ingest)

    version = subparsers.add_parser("version", help="print the version")
    version.set_defaults(func=_version)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the CLI."""
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except Exception as exc:
        print(f"fresh-road: {exc}", file=sys.stderr)
        return 1
