#!/usr/bin/env python3
"""Report-only WS4 routing over the TSA 23 c5-style network.

This does not run an optimizer and does not change WS4 code.  It loads the
network through the WS4 route configuration API, assigns each linked block to
its least-haul-cost mill, and writes block-level route and cost exposure tables.

Usage
-----
    python examples/tsa23_c5_network/ws4_report/build_report.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from ws4.roads.accounts import load_route_config

HERE = Path(__file__).resolve().parent
DEFAULT_ROUTE_CONFIG = HERE / "route.yaml"
DEFAULT_DRA_REPORT = HERE.parents[1] / "tsa23_full_route" / "route_lengths_full.csv"


def _percentiles(series: pd.Series) -> dict[str, float]:
    return {
        "min": float(series.min()),
        "median": float(series.median()),
        "p90": float(series.quantile(0.9)),
        "max": float(series.max()),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--route-config", type=Path, default=DEFAULT_ROUTE_CONFIG)
    parser.add_argument("--dra-report", type=Path, default=DEFAULT_DRA_REPORT)
    parser.add_argument(
        "--linkage-status",
        type=Path,
        default=HERE.parent / "block_linkage_status.csv",
    )
    parser.add_argument("--out-dir", type=Path, default=HERE)
    args = parser.parse_args(argv)

    config = load_route_config(args.route_config)
    model = config.model
    network = model.network
    args.out_dir.mkdir(parents=True, exist_ok=True)

    linkage_status = pd.read_csv(args.linkage_status) if args.linkage_status.is_file() else None
    no_linkage_blocks = (
        int((linkage_status["status"] == "no_linkage").sum()) if linkage_status is not None else None
    )

    rows: list[dict[str, object]] = []
    used_segments: set[int] = set()
    block_ids = sorted(int(block_id) for block_id in network.block_vertex)

    for block_id in block_ids:
        destination, route = model.assign(block_id, "volume")
        if route is None:
            rows.append(
                {
                    "block_id": block_id,
                    "destination": destination,
                    "route_length_m": 0.0,
                    "haul_cost_per_m3": 0.0,
                    "build_cost_cad": 0.0,
                    "maintain_cost_cad": 0.0,
                    "segment_count": 0,
                    "route_95_length_m": None,
                    "routed": False,
                }
            )
            continue
        used_segments.update(route.segment_ids)
        route_95 = network.route(block_id, "destination.MILL_95_LBR")
        rows.append(
            {
                "block_id": block_id,
                "destination": destination,
                "route_length_m": route.length_m,
                "haul_cost_per_m3": route.haul_cost,
                "build_cost_cad": route.build_cost,
                "maintain_cost_cad": route.maintain_cost,
                "segment_count": len(route.segment_ids),
                "route_95_length_m": route_95.length_m if route_95 is not None else None,
                "routed": True,
            }
        )

    report = pd.DataFrame(rows).sort_values("block_id").reset_index(drop=True)
    report.to_csv(args.out_dir / "block_routes.csv", index=False)

    routed = report[report["routed"]].copy()
    segment_by_id = {segment.segment_id: segment for segment in network.segments}
    unique_build = sum(segment_by_id[int(segment_id)].build_cost for segment_id in used_segments)
    unique_length = sum(segment_by_id[int(segment_id)].length_m for segment_id in used_segments)

    destination_counts = {
        str(key): int(value) for key, value in routed["destination"].value_counts().items()
    }

    comparisons = {}
    if args.dra_report.is_file():
        dra = pd.read_csv(args.dra_report)
        dra = dra.rename(columns={"route_length_m": "dra_route_length_m"})
        merged = report.merge(
            dra[["block_id", "dra_route_length_m", "routed"]].rename(
                columns={"routed": "dra_routed"}
            ),
            on="block_id",
            how="left",
            validate="one_to_one",
        )
        both = merged[merged["routed"] & merged["dra_routed"].fillna(False)]
        comparisons = {
            "dra_report": str(args.dra_report),
            "dra_routed_blocks": int(dra["routed"].sum()) if "routed" in dra else None,
            "matched_routed_blocks": int(len(both)),
            "c5_routed_matched": int(both["routed"].sum()),
            "median_c5_minus_dra_m": float((both["route_length_m"] - both["dra_route_length_m"]).median()),
            "p90_c5_minus_dra_m": float((both["route_length_m"] - both["dra_route_length_m"]).quantile(0.9)),
            "median_c5_to_95_minus_dra_m": float((both["route_95_length_m"] - both["dra_route_length_m"]).median()),
        }

    summary = {
        "schema": "fresh.ws4.c5-route-report.v1",
        "scope": "report-only; no WS4 objective, constraint, solver, or growth change",
        "route_config": str(args.route_config),
        "network": {
            "segments": int(len(network.segments)),
            "vertices": int(len(network.vertex_coordinates)),
            "destinations": int(len(network.destinations)),
            "linked_blocks": int(len(network.block_vertex)),
        },
        "routing": {
            "total_blocks": int(len(linkage_status)) if linkage_status is not None else int(len(report)),
            "routed_blocks": int(len(routed)),
            "no_linkage_blocks": no_linkage_blocks,
            "unrouted_linked_blocks": int(len(report) - len(routed)),
            "destination_counts": destination_counts,
            "route_length_m": _percentiles(routed["route_length_m"]),
            "route_95_length_m": _percentiles(routed["route_95_length_m"].dropna()),
            "haul_cost_per_m3": _percentiles(routed["haul_cost_per_m3"]),
            "build_cost_cad_per_route": _percentiles(routed["build_cost_cad"]),
            "maintain_cost_cad_per_route": _percentiles(routed["maintain_cost_cad"]),
            "segment_count_per_route": _percentiles(routed["segment_count"]),
        },
        "unique_used_network": {
            "segments": int(len(used_segments)),
            "length_km": float(unique_length / 1000.0),
            "build_cost_cad": float(unique_build),
            "note": "build cost is the sum over distinct used segments; route-level build_cost repeats shared segments.",
        },
        "dra_comparison": comparisons,
        "files": {
            "block_routes": "block_routes.csv",
            "route_config": str(args.route_config),
        },
    }
    (args.out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(
        f"routed {len(routed):,}/{len(linkage_status) if linkage_status is not None else len(report):,} blocks; "
        f"no_linkage={no_linkage_blocks}; "
        f"destinations={destination_counts}; "
        f"route median={summary['routing']['route_length_m']['median']:.0f} m"
    )
    print(f"wrote {args.out_dir / 'block_routes.csv'}")
    print(f"wrote {args.out_dir / 'summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
