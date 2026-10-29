#!/usr/bin/env python3
"""Fetch the public layers used by the TSA 23 c5-style road network.

The script downloads only public BCGW WFS layers, clips them to the TSA 23
stand extent (plus a small buffer), and writes local GeoPackages under
``runtime/source``.  The large source files are intentionally not committed.

Examples
--------
    python examples/tsa23_c5_network/fetch_public_data.py --force
    python examples/tsa23_c5_network/fetch_public_data.py --bbox 1259304,668240,1397278,812136
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable
from pathlib import Path

import geopandas as gpd
import requests

HERE = Path(__file__).resolve().parent
DEFAULT_BLOCKS = Path(
    "/srv/shared-data/gep/iversen-jamie-msc-thesis/"
    "femic-tsa23-instance/runtime/gis/tsa23_blocks.geojson"
)
WFS_URL = "https://openmaps.gov.bc.ca/geo/pub/ows"
PAGE_SIZE = 10_000

LAYERS = {
    "dra_roads": "pub:WHSE_BASEMAPPING.DRA_DGTL_ROAD_ATLAS_MPAR_SP",
    "ften_roads": "pub:WHSE_FOREST_TENURE.FTEN_ROAD_SECTION_LINES_SVW",
    "lakes": "pub:WHSE_BASEMAPPING.FWA_LAKES_POLY",
    "rivers": "pub:WHSE_BASEMAPPING.FWA_RIVERS_POLY",
    "protected_areas": "pub:WHSE_TANTALIS.TA_PARK_ECORES_PA_SVW",
    "mills": "pub:WHSE_IMAGERY_AND_BASE_MAPS.GSR_TMBR_PRCSSING_FAC_SV",
}


def _session() -> requests.Session:
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(max_retries=4)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def fetch_page(
    session: requests.Session,
    type_name: str,
    bbox: str,
    count: int = PAGE_SIZE,
) -> dict:
    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeNames": type_name,
        "bbox": f"{bbox},EPSG:3005",
        "srsName": "EPSG:3005",
        "outputFormat": "application/json",
        "count": count,
    }
    response = session.get(WFS_URL, params=params, timeout=600)
    response.raise_for_status()
    return response.json()


def _split_bbox(bbox: tuple[float, float, float, float]) -> list[tuple[float, float, float, float]]:
    """Split a bbox into four non-overlapping quadrants."""
    minx, miny, maxx, maxy = bbox
    midx = (minx + maxx) / 2.0
    midy = (miny + maxy) / 2.0
    return [
        (minx, miny, midx, midy),
        (midx, miny, maxx, midy),
        (minx, midy, midx, maxy),
        (midx, midy, maxx, maxy),
    ]


def fetch_tile(
    session: requests.Session,
    type_name: str,
    bbox: tuple[float, float, float, float],
    depth: int = 0,
) -> list[dict]:
    """Fetch one bbox tile, recursively splitting when the server cap is hit.

    The public WFS instance does not honour ``startIndex`` for every layer.  A
    deterministic bbox quadtree avoids paging state entirely: if a tile returns
    the server cap, it is split until every tile is below the cap.
    """
    text_bbox = ",".join(f"{value:.2f}" for value in bbox)
    payload = fetch_page(session, type_name, text_bbox)
    features = payload.get("features", [])
    if len(features) < PAGE_SIZE:
        return features
    if depth >= 12:
        raise RuntimeError(f"{type_name}: tile still capped at depth {depth}: {text_bbox}")
    print(f"{type_name}: split depth={depth} ({len(features):,} features in tile)")
    combined: list[dict] = []
    for child in _split_bbox(bbox):
        combined.extend(fetch_tile(session, type_name, child, depth + 1))
    return combined


def fetch_layer(
    session: requests.Session,
    name: str,
    type_name: str,
    bbox: str,
    out_path: Path,
    force: bool = False,
) -> int:
    if out_path.exists() and not force:
        existing = gpd.read_file(out_path)
        print(f"{name}: cached {len(existing):,} features -> {out_path}")
        return len(existing)

    bbox_tuple = tuple(float(value) for value in bbox.split(","))
    features = fetch_tile(session, type_name, bbox_tuple)

    if not features:
        raise RuntimeError(f"{name}: no features returned for {type_name}")

    frame = gpd.GeoDataFrame.from_features(features, crs="EPSG:3005")
    # Neighbouring bbox tiles can share a boundary feature; keep one copy.
    if "OBJECTID" in frame.columns:
        frame = frame.drop_duplicates(subset=["OBJECTID"], keep="first")
    frame = frame[frame.geometry.notna() & ~frame.geometry.is_empty].copy()
    print(f"{name}: collected {len(frame):,} unique features")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_file(out_path, driver="GPKG", layer=name)
    print(f"{name}: wrote {len(frame):,} features -> {out_path}")
    return len(frame)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blocks", type=Path, default=DEFAULT_BLOCKS)
    parser.add_argument(
        "--bbox",
        default=None,
        help="EPSG:3005 bbox minx,miny,maxx,maxy. Default: TSA 23 blocks + 2 km.",
    )
    parser.add_argument("--out-dir", type=Path, default=HERE / "runtime" / "source")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    blocks = gpd.read_file(args.blocks).to_crs(3005)
    if args.bbox:
        bbox_tuple = tuple(float(value) for value in args.bbox.split(","))
        if len(bbox_tuple) != 4:
            raise SystemExit("--bbox must have four comma-separated numbers")
    else:
        minx, miny, maxx, maxy = blocks.total_bounds
        bbox_tuple = (minx - 2000.0, miny - 2000.0, maxx + 2000.0, maxy + 2000.0)
    bbox = ",".join(f"{value:.2f}" for value in bbox_tuple)
    print(f"bbox EPSG:3005 = {bbox}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    session = _session()
    counts: dict[str, int] = {}
    for name, type_name in LAYERS.items():
        out_path = args.out_dir / f"{name}.gpkg"
        counts[name] = fetch_layer(session, name, type_name, bbox, out_path, args.force)

    # Keep a small, reviewable provenance record next to the large layers.
    manifest = {
        "schema": "fresh.road.network.source.v1",
        "wfs_url": WFS_URL,
        "bbox_epsg3005": [round(value, 2) for value in bbox_tuple],
        "blocks": str(args.blocks),
        "block_count": len(blocks),
        "layers": {
            name: {
                "type_name": LAYERS[name],
                "feature_count": counts[name],
                "local_path": str(args.out_dir / f"{name}.gpkg"),
            }
            for name in LAYERS
        },
    }
    (args.out_dir / "source_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(f"manifest -> {args.out_dir / 'source_manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
