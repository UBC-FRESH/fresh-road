#!/usr/bin/env python3
"""Build a report-only WS4 route/access table for the TSA 23 mill test."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--blocks-parquet",
        type=Path,
        default=Path(
            "/srv/shared-data/gep/iversen-jamie-msc-thesis/"
            "femic-tsa23-instance/runtime/ws4/compiled/blocks.parquet"
        ),
    )
    parser.add_argument("--route-dir", type=Path, default=Path("."))
    parser.add_argument("--out-csv", type=Path, default=Path("ws4_route_report.csv"))
    parser.add_argument(
        "--out-summary", type=Path, default=Path("ws4_route_report_summary.json")
    )
    args = parser.parse_args()

    blocks = pd.read_parquet(args.blocks_parquet)
    areas = (
        blocks.groupby("block_id", as_index=False)["area_ha"]
        .sum()
        .rename(columns={"area_ha": "ws4_area_ha"})
    )
    status = pd.read_csv(args.route_dir / "block_access_status.csv")
    build = pd.read_csv(args.route_dir / "route_build_costs_tr28.csv")
    report = status.merge(
        build.drop(columns=["routed"]), on="block_id", how="left", validate="one_to_one"
    )
    report = areas.merge(report, on="block_id", how="inner", validate="one_to_one")
    report = report.sort_values("block_id").reset_index(drop=True)
    report.to_csv(args.out_csv, index=False)

    routed = report[report["route_status"] == "routed"]
    summary = {
        "schema_version": "fresh.ws4.route-report.v1",
        "scope": "report-only; no WS4 objective, constraint, solver, or growth change",
        "block_count": int(len(report)),
        "routed_blocks": int(len(routed)),
        "unrouted_blocks": sorted(
            int(value) for value in report.loc[
                report["route_status"] != "routed", "block_id"
            ]
        ),
        "ws4_area_ha": float(report["ws4_area_ha"].sum()),
        "routed_area_ha": float(routed["ws4_area_ha"].sum()),
        "route_length_m": {
            "min": float(routed["route_length_m"].min()),
            "median": float(routed["route_length_m"].median()),
            "p90": float(routed["route_length_m"].quantile(0.9)),
            "max": float(routed["route_length_m"].max()),
        },
        "tr28_build_cost_cad": {
            "min": float(routed["build_cost_cad"].min()),
            "median": float(routed["build_cost_cad"].median()),
            "p90": float(routed["build_cost_cad"].quantile(0.9)),
            "max": float(routed["build_cost_cad"].max()),
        },
        "cost_scope": "TR-28 subgrade reconstruction only; excludes haul and maintenance",
    }
    args.out_summary.write_text(json.dumps(summary, indent=2) + "\n")
    print(f"wrote {args.out_csv} ({len(report)} blocks)")
    print(f"wrote {args.out_summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
