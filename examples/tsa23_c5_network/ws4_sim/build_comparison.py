#!/usr/bin/env python3
"""Build the no-road / DRA / c5 WS4 simulation comparison.

Reads the run directories written by ``run_sim.sh`` and records the route
accounts, route-cost reports, and unrouted product rows.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
RUNS = {
    "no_road": HERE / "run_base",
    "dra": HERE / "run_dra",
    "c5": HERE / "run_c5",
}


def _read_run(path: Path) -> dict:
    result: dict = {"path": str(path)}
    accounts_path = path / "account_values.csv"
    if accounts_path.is_file():
        accounts = pd.read_csv(accounts_path)
        result["route_accounts"] = {
            str(row.account): float(row.value)
            for row in accounts.itertuples(index=False)
            if str(row.account).startswith("route.") or str(row.account).startswith("product.")
        }
    report_path = path / "route_cost_report.csv"
    if report_path.is_file():
        report = pd.read_csv(report_path).iloc[0]
        result["route_cost_report"] = {
            str(key): float(value)
            for key, value in report.items()
            if key not in {"PERIOD", "YEAR", "PERIODWIDTH"}
        }
    values_path = path / "route_values.csv"
    if values_path.is_file():
        values = pd.read_csv(values_path)
        unrouted = values[values["destination"].isna()]
        result["routing"] = {
            "product_rows": int(len(values)),
            "unrouted_product_rows": int(len(unrouted)),
            "unrouted_blocks": int(unrouted["block_id"].nunique()),
            "unrouted_ledger_volume": float(unrouted["volume"].sum()),
            "routed_ledger_volume": float(values.loc[values["destination"].notna(), "volume"].sum()),
            "total_ledger_volume": float(values["volume"].sum()),
            "median_route_length_m": float(values.loc[values["destination"].notna(), "length_m"].median()),
            "route_length_m": {
                "min": float(values.loc[values["destination"].notna(), "length_m"].min()),
                "median": float(values.loc[values["destination"].notna(), "length_m"].median()),
                "p90": float(values.loc[values["destination"].notna(), "length_m"].quantile(0.9)),
                "max": float(values.loc[values["destination"].notna(), "length_m"].max()),
            },
        }
    return result


def main() -> int:
    runs = {name: _read_run(path) for name, path in RUNS.items()}
    base_accounts = pd.read_csv(RUNS["no_road"] / "account_values.csv")
    product_checks = {}
    for name in ("dra", "c5"):
        other = pd.read_csv(RUNS[name] / "account_values.csv")
        merged = base_accounts.merge(
            other, on=["offset", "account"], suffixes=("_base", "_run"), how="outer"
        )
        common = merged[merged["_merge"].eq("both")] if "_merge" in merged else merged
        product_checks[name] = {
            "common_accounts": int(len(common)),
            "max_abs_product_account_delta": float(
                (common["value_base"] - common["value_run"]).abs().max()
            ),
        }

    comparison = {
        "schema": "fresh.ws4.c5-sim-comparison.v1",
        "scope": "WS4 simulation with and without route accounts; no objective, constraint, growth, or solver change",
        "dataset": "/srv/shared-data/gep/iversen-jamie-msc-thesis/femic-tsa23-instance/runtime/ws4/compiled",
        "schedule": "/srv/shared-data/gep/iversen-jamie-msc-thesis/femic-tsa23-instance/runtime/ws4/schedule_baseline.csv",
        "years": 5,
        "schedule_blocks": int(pd.read_csv(RUNS["no_road"] / "schedule.csv")["block_id"].nunique()),
        "product_account_check": product_checks,
        "runs": runs,
        "notes": [
            "The no-road baseline has no route model and no route accounts.",
            "The DRA fixture is route-length-only; its build, haul, and maintenance costs are zero.",
            "The c5 route model uses the 600 m c5-style lattice and c5 costs.",
            "The c5 destination split is least-haul assignment; no product eligibility or mill demand is modelled.",
            "Ledger volume is the sum of routed product rows, not merchantable volume.",
        ],
    }
    (HERE / "comparison.json").write_text(json.dumps(comparison, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {HERE / 'comparison.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
