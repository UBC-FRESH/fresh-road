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
    # Optional documented FHOPS highway-truck scenario. Keep the raw route
    # length separate from this partial variable-cost column.
    speed_kmh = 37.0
    variable_cost_per_minute = 1.20
    capacity_m3 = 45.0
    report["haul_one_way_minutes"] = report["route_length_m"] / 1000.0 / speed_kmh * 60.0
    report["haul_round_trip_minutes"] = report["haul_one_way_minutes"] * 2.0
    report["haul_variable_cost_cad_m3"] = (
        report["haul_round_trip_minutes"] * variable_cost_per_minute / capacity_m3
    )
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
        "haul_scenario": {
            "source": "FHOPS examples/hauling/scenario.yaml highway truck",
            "speed_kmh": 37.0,
            "variable_cost_per_minute_cad": 1.20,
            "capacity_m3": 45.0,
            "scope": "variable travel only; excludes fixed truck day, loading/unloading, overtime, maintenance, profit",
            "cost_cad_m3": {
                "min": float(routed["haul_variable_cost_cad_m3"].min()),
                "median": float(routed["haul_variable_cost_cad_m3"].median()),
                "p90": float(routed["haul_variable_cost_cad_m3"].quantile(0.9)),
                "max": float(routed["haul_variable_cost_cad_m3"].max()),
            },
        },
    }
    args.out_summary.write_text(json.dumps(summary, indent=2) + "\n")
    print(f"wrote {args.out_csv} ({len(report)} blocks)")
    print(f"wrote {args.out_summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
