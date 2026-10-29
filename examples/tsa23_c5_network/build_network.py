#!/usr/bin/env python3
"""Build the TSA 23 c5-style paved/resource/potential road network.

The design follows the Patchworks c5 sample:

* existing paved public roads and forest-tenure resource roads are kept;
* every existing segment has build cost 0;
* a regular grid of potential roads is clipped to the TSA 23 stand extent;
* near-parallel, impassable, and dangling potential edges are removed;
* each surviving potential grid edge is emitted once per potential road class
  with identical geometry and class-specific maintenance/haul coefficients;
* the result is written as the four WS4 route tables.

The cost table is documented in ``docs/cost-sources.md``.  The c5 sample has
one new-road construction coefficient (``N``), so the four potential classes
share the c5 ``N`` construction cost.  Their maintenance and haul coefficients
come from the c5 ``P/S/T/N`` rows; no four-way construction ladder is invented.

Usage
-----
    python examples/tsa23_c5_network/build_network.py
    python examples/tsa23_c5_network/build_network.py --grid-spacing 4000
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import random
import time
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from rasterio.features import rasterize
from rasterio.transform import from_origin
from scipy.ndimage import binary_dilation
from shapely import STRtree, coverage_union_all
from shapely.geometry import LineString, MultiLineString, Point
from shapely.ops import unary_union

HERE = Path(__file__).resolve().parent
DEFAULT_BLOCKS = Path(
    "/srv/shared-data/gep/iversen-jamie-msc-thesis/"
    "femic-tsa23-instance/runtime/gis/tsa23_blocks.geojson"
)
DEFAULT_SOURCE = HERE / "runtime" / "source"
DEFAULT_OUT = HERE

LOG = logging.getLogger("tsa23-c5")

# c5 `HaulCost.xlsx`, with the T haul value from the c5 `access.shp` fields.
# The workbook says 0.27; the delivered sample geometry uses 0.32.  The
# accession fields are the values WS4's c5 parity fixture uses.
EXISTING_COSTS = {
    "H": {"build": 0.0, "maintain": 0.0, "haul": 0.06},
    "P": {"build": 0.0, "maintain": 2000.0, "haul": 0.10},
    "S": {"build": 0.0, "maintain": 2000.0, "haul": 0.16},
    "T": {"build": 0.0, "maintain": 2000.0, "haul": 0.32},
}
POTENTIAL_COSTS = {
    "class_1": {"build": 5000.0, "maintain": 2000.0, "haul": 0.10},
    "class_2": {"build": 5000.0, "maintain": 2000.0, "haul": 0.16},
    "class_3": {"build": 5000.0, "maintain": 2000.0, "haul": 0.32},
    "class_4": {"build": 5000.0, "maintain": 500.0, "haul": 0.255078},
}
PUBLIC_PAVED_CLASSES = {"highway", "arterial", "collector", "local", "service", "yield"}
TRUE_STATUS = {"ACTIVE", "PENDING"}


def _line_parts(geometry) -> Iterable[LineString]:
    if geometry is None or geometry.is_empty:
        return
    if isinstance(geometry, LineString):
        if geometry.length > 0:
            yield geometry
    elif isinstance(geometry, MultiLineString):
        for part in geometry.geoms:
            if part.length > 0:
                yield part
    else:
        # A GeometryCollection or polygon can appear after clipping.  Keep only
        # its line components.
        for part in getattr(geometry, "geoms", []):
            yield from _line_parts(part)


def _round_point(x: float, y: float, digits: int = 2) -> tuple[float, float]:
    return (round(float(x), digits), round(float(y), digits))


def _vertex_key(point: Point, digits: int = 2) -> tuple[float, float]:
    return _round_point(point.x, point.y, digits)


class RasterMask:
    """A fast inside/outside mask for the TSA stand extent.

    The TSA block union has ~1.1 million boundary vertices and 10k holes.  Exact
    GEOS clipping of 85k source lines against that polygon is prohibitively
    slow.  A 50 m raster is a faithful, explicit clip for this strategic
    network and keeps the expensive topology work off the complex boundary.
    """

    def __init__(
        self,
        geometries: Iterable,
        bounds: tuple[float, float, float, float],
        resolution: float = 50.0,
        *,
        dilate: int = 1,
    ) -> None:
        self.bounds = bounds
        self.resolution = resolution
        minx, miny, maxx, maxy = bounds
        self.width = int(math.ceil((maxx - minx) / resolution))
        self.height = int(math.ceil((maxy - miny) / resolution))
        self.transform = from_origin(minx, maxy, resolution, resolution)
        shapes = ((geometry, 1) for geometry in geometries if geometry is not None and not geometry.is_empty)
        self.mask = rasterize(
            shapes,
            out_shape=(self.height, self.width),
            transform=self.transform,
            fill=0,
            all_touched=False,
            dtype="uint8",
        ).astype(bool)
        if dilate:
            self.mask = binary_dilation(self.mask, iterations=dilate)

    def contains(self, x: float, y: float) -> bool:
        minx, miny, maxx, maxy = self.bounds
        if not (minx <= x <= maxx and miny <= y <= maxy):
            return False
        col = int((x - minx) / self.resolution)
        row = int((maxy - y) / self.resolution)
        if row < 0 or row >= self.height or col < 0 or col >= self.width:
            return False
        return bool(self.mask[row, col])

    def line_any(self, line: LineString, samples: int = 5) -> bool:
        for fraction in np.linspace(0.0, 1.0, samples):
            point = line.interpolate(float(fraction), normalized=True)
            if self.contains(point.x, point.y):
                return True
        return False

    def line_midpoint(self, line: LineString) -> bool:
        point = line.interpolate(0.5, normalized=True)
        return self.contains(point.x, point.y)


def _load_source(
    path: Path,
    mask: RasterMask,
    *,
    extra_union=None,
    layer: str | None = None,
) -> gpd.GeoDataFrame:
    frame = gpd.read_file(path, layer=layer) if layer else gpd.read_file(path)
    frame = frame[frame.geometry.notna() & ~frame.geometry.is_empty].copy()
    frame = frame.cx[mask.bounds[0]:mask.bounds[2], mask.bounds[1]:mask.bounds[3]]

    def keep(geometry) -> bool:
        point = geometry.representative_point()
        if mask.contains(point.x, point.y):
            return True
        return extra_union is not None and extra_union.intersects(point)

    frame = frame[frame.geometry.map(keep)].copy()
    return frame


def _classify_existing(dra: gpd.GeoDataFrame, ften: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    dra = dra.copy()
    ften = ften.copy()

    dra_class = dra["ROAD_CLASS"].fillna("").str.lower()
    dra["road_type"] = np.select(
        [
            dra_class.eq("highway"),
            dra_class.isin(["arterial", "collector"]),
            dra_class.isin(["local", "service", "yield"]),
        ],
        ["H", "P", "S"],
        default="S",
    )
    dra["source_kind"] = "existing_paved"

    ften["road_type"] = np.where(
        ften["FILE_TYPE_DESCRIPTION"].eq("Forest Service Road"), "S", "T"
    )
    ften["source_kind"] = "existing_resource"

    keep = [
        "road_type",
        "source_kind",
        "geometry",
    ]
    combined = pd.concat([dra[keep], ften[keep]], ignore_index=True)
    combined = gpd.GeoDataFrame(combined, geometry="geometry", crs=dra.crs)
    # WFS can return MultiLineString even for a single road feature; explode so
    # endpoint snapping and noding operate on simple lines.
    combined = combined.explode(index_parts=False).reset_index(drop=True)
    return combined[combined.geometry.length > 0].reset_index(drop=True)


def _snap_existing_endpoints(
    frame: gpd.GeoDataFrame,
    *,
    cluster_m: float = 10.0,
    paved_tie_m: float = 25.0,
) -> gpd.GeoDataFrame:
    """Move existing road endpoints onto nearby endpoints/tie-ins.

    This is deliberately small: 10 m endpoint clustering for existing roads,
    plus a 25 m tie from resource-road endpoints to the nearest point on a
    paved line.  It is not a licence to bridge the large gaps found in the
    DRA-only graph.
    """
    if frame.empty:
        return frame

    # Collect every endpoint and cluster on a grid.  The centroid of each
    # cluster becomes the shared vertex coordinate.
    buckets: dict[tuple[int, int], list[tuple[float, float]]] = defaultdict(list)
    for line in frame.geometry:
        for endpoint in (line.coords[0], line.coords[-1]):
            key = (round(endpoint[0] / cluster_m), round(endpoint[1] / cluster_m))
            buckets[key].append((float(endpoint[0]), float(endpoint[1])))
    snapped = {
        key: (sum(x for x, _ in values) / len(values), sum(y for _, y in values) / len(values))
        for key, values in buckets.items()
    }

    paved = frame[frame["source_kind"].eq("existing_paved")]
    paved_geometries = list(paved.geometry)
    paved_tree = STRtree(paved_geometries) if paved_geometries else None

    def nearest_on_paved(point: Point) -> tuple[float, float] | None:
        if paved_tree is None:
            return None
        nearest_index = int(paved_tree.nearest(point))
        line = paved_geometries[nearest_index]
        distance = point.distance(line)
        if distance > paved_tie_m:
            return None
        snapped_point = line.interpolate(line.project(point))
        return (float(snapped_point.x), float(snapped_point.y))

    def snap_point(coords, source_kind: str) -> tuple[float, float]:
        x, y = float(coords[0]), float(coords[1])
        if source_kind == "existing_resource":
            tie = nearest_on_paved(Point(x, y))
            if tie is not None:
                return tie
        key = (round(x / cluster_m), round(y / cluster_m))
        return snapped.get(key, (x, y))

    geometries = []
    kept_rows = []
    for position, (line, source_kind) in enumerate(
        zip(frame.geometry, frame["source_kind"].astype(str), strict=False)
    ):
        coords = list(line.coords)
        if len(coords) < 2:
            continue
        start = snap_point(coords[0], source_kind)
        end = snap_point(coords[-1], source_kind)
        if start == end:
            continue
        geometry = LineString([start, *coords[1:-1], end])
        if geometry.length <= 0:
            continue
        geometries.append(geometry)
        kept_rows.append(position)
    out = frame.iloc[kept_rows].copy()
    out["geometry"] = geometries
    return out.reset_index(drop=True)


def _assign_source_classes(
    noded_lines: list[LineString],
    source_frame: gpd.GeoDataFrame,
) -> tuple[list[str], list[str], list[float]]:
    """Assign each noded piece to its best overlapping source line/class."""
    source_geometries = list(source_frame.geometry)
    source_tree = STRtree(source_geometries)
    source_type = source_frame["road_type"].astype(str).tolist()
    source_kind = source_frame["source_kind"].astype(str).tolist()

    types: list[str] = []
    kinds: list[str] = []
    overlaps: list[float] = []
    for piece in noded_lines:
        candidates = source_tree.query(piece)
        best_index = None
        best_overlap = 0.0
        for index in candidates:
            overlap = piece.intersection(source_geometries[int(index)]).length
            if overlap > best_overlap:
                best_overlap = overlap
                best_index = int(index)
        if best_index is None or best_overlap <= 0.0:
            # Union pieces can lose exact overlap at a shared endpoint.  Use
            # the nearest source line rather than silently filing a potential
            # grid edge as an existing resource road.
            nearest_index = int(source_tree.nearest(piece))
            types.append(source_type[nearest_index])
            kinds.append(source_kind[nearest_index])
            overlaps.append(0.0)
            continue
        types.append(source_type[best_index])
        kinds.append(source_kind[best_index])
        overlaps.append(float(best_overlap))
    return types, kinds, overlaps


def _grid_segments(
    bounds: tuple[float, float, float, float],
    spacing: float,
    *,
    diagonal_seed: int = 2025,
) -> list[LineString]:
    """Return the c5-style 600 m grid with one diagonal per cell.

    The c5 ``access.shp`` potential roads are a 600 m lattice (coordinates at
    the c5 lattice offset) with exactly one 45-degree diagonal per occupied
    cell.  The diagonal orientation in c5 is 50/50 and has no recoverable
    spatial rule, so a fixed-seed random choice is used here.  The orthogonal
    edges are generated once per cell boundary and the diagonals once per cell.
    """
    minx, miny, maxx, maxy = bounds
    start_x = math.floor(minx / spacing) * spacing
    start_y = math.floor(miny / spacing) * spacing
    xs = np.arange(start_x, maxx + spacing, spacing)
    ys = np.arange(start_y, maxy + spacing, spacing)
    segments: list[LineString] = []
    for x in xs:
        for y0, y1 in zip(ys[:-1], ys[1:], strict=False):
            segments.append(LineString([(float(x), float(y0)), (float(x), float(y1))]))
    for y in ys:
        for x0, x1 in zip(xs[:-1], xs[1:], strict=False):
            segments.append(LineString([(float(x0), float(y)), (float(x1), float(y))]))
    rng = random.Random(diagonal_seed)
    for x0, x1 in zip(xs[:-1], xs[1:], strict=False):
        for y0, y1 in zip(ys[:-1], ys[1:], strict=False):
            if rng.random() < 0.5:
                segments.append(LineString([(float(x0), float(y0)), (float(x1), float(y1))]))
            else:
                segments.append(LineString([(float(x0), float(y1)), (float(x1), float(y0))]))
    return segments


def _remove_grid_near_existing(
    grid: list[LineString],
    existing_union,
    impassable_union,
    *,
    existing_buffer_m: float = 30.0,
    impassable_buffer_m: float = 10.0,
    parallel_fraction: float = 0.5,
) -> tuple[list[LineString], Counter]:
    stats = Counter()
    existing_buffer = existing_union.buffer(existing_buffer_m) if existing_union else None
    kept: list[LineString] = []
    for line in grid:
        if impassable_union is not None and impassable_union.line_any(line, samples=7):
            stats["impassable"] += 1
            continue
        if existing_buffer is not None and line.intersects(existing_buffer):
            overlap = line.intersection(existing_buffer).length
            if line.within(existing_buffer) or overlap / line.length >= parallel_fraction:
                stats["near_parallel"] += 1
                continue
        kept.append(line)
    return kept, stats


def _remove_dangling(
    grid: list[LineString],
    *,
    iterations: int = 3,
    preserve_near_existing: bool = True,
    existing_union=None,
    preserve_m: float = 50.0,
) -> tuple[list[LineString], Counter]:
    stats = Counter()
    preserve = existing_union.buffer(preserve_m) if (preserve_near_existing and existing_union) else None
    current = list(grid)
    for _ in range(iterations):
        degree: dict[tuple[float, float], int] = defaultdict(int)
        for line in current:
            degree[_vertex_key(Point(line.coords[0]))] += 1
            degree[_vertex_key(Point(line.coords[-1]))] += 1
        next_lines: list[LineString] = []
        removed = 0
        for line in current:
            start = _vertex_key(Point(line.coords[0]))
            end = _vertex_key(Point(line.coords[-1]))
            dangling = degree[start] <= 1 or degree[end] <= 1
            if dangling:
                endpoint_geoms = [Point(line.coords[0]), Point(line.coords[-1])]
                near_existing = preserve is not None and any(
                    preserve.intersects(point) for point in endpoint_geoms
                )
                if not near_existing:
                    removed += 1
                    continue
            next_lines.append(line)
        stats["dangling_removed"] += removed
        if removed == 0:
            break
        current = next_lines
    return current, stats


def _keep_components(
    lines: list[LineString],
    *,
    min_length_m: float = 500.0,
) -> tuple[list[LineString], Counter]:
    """Drop tiny disconnected line components from the potential grid."""
    if not lines:
        return [], Counter()
    parent: dict[tuple[float, float], tuple[float, float]] = {}

    def find(item):
        parent.setdefault(item, item)
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    def union(a, b):
        root_a, root_b = find(a), find(b)
        if root_a != root_b:
            parent[root_b] = root_a

    for line in lines:
        a = _vertex_key(Point(line.coords[0]))
        b = _vertex_key(Point(line.coords[-1]))
        union(a, b)
    lengths: dict[tuple[float, float], float] = defaultdict(float)
    for line in lines:
        root = find(_vertex_key(Point(line.coords[0])))
        lengths[root] += line.length
    kept = [
        line
        for line in lines
        if lengths[find(_vertex_key(Point(line.coords[0])))] >= min_length_m
    ]
    return kept, Counter({"tiny_components": len(lines) - len(kept)})


def _union_parts(lines: list[LineString]) -> list[LineString]:
    if not lines:
        return []
    merged = unary_union(lines)
    return list(_line_parts(merged))


def _build_graph(
    lines: list[LineString],
    road_types: list[str],
    source_kinds: list[str],
    *,
    vertex_digits: int = 2,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    vertices: dict[tuple[float, float], int] = {}
    vertex_rows: list[dict] = []
    segment_rows: list[dict] = []

    def get_vertex(point: Point) -> int:
        key = _vertex_key(point, vertex_digits)
        if key not in vertices:
            vertex_id = len(vertices) + 1
            vertices[key] = vertex_id
            vertex_rows.append({"vertex_id": vertex_id, "x": key[0], "y": key[1]})
        return vertices[key]

    for line, road_type, source_kind in zip(lines, road_types, source_kinds, strict=True):
        from_id = get_vertex(Point(line.coords[0]))
        to_id = get_vertex(Point(line.coords[-1]))
        if from_id == to_id or line.length <= 0:
            continue
        segment_rows.append(
            {
                "from_vertex": from_id,
                "to_vertex": to_id,
                "length_m": float(line.length),
                "road_type": road_type,
                "source_kind": source_kind,
            }
        )
    return pd.DataFrame(segment_rows), pd.DataFrame(vertex_rows)


def _add_segment_costs(
    segments: pd.DataFrame,
    *,
    fixed_ids: bool = True,
) -> pd.DataFrame:
    rows: list[dict] = []
    next_id = 1
    for row in segments.itertuples(index=False):
        length_km = float(row.length_m) / 1000.0
        if row.source_kind == "potential":
            for class_name, costs in POTENTIAL_COSTS.items():
                rows.append(
                    {
                        "segment_id": next_id,
                        "from_vertex": row.from_vertex,
                        "to_vertex": row.to_vertex,
                        "length_m": row.length_m,
                        "build_cost": costs["build"] * length_km,
                        "maintain_cost": costs["maintain"] * length_km,
                        "haul_cost": costs["haul"] * length_km,
                        "road_type": class_name,
                        "source_kind": "potential",
                    }
                )
                next_id += 1
        else:
            costs = EXISTING_COSTS.get(row.road_type, EXISTING_COSTS["T"])
            rows.append(
                {
                    "segment_id": next_id,
                    "from_vertex": row.from_vertex,
                    "to_vertex": row.to_vertex,
                    "length_m": row.length_m,
                    "build_cost": costs["build"] * length_km,
                    "maintain_cost": costs["maintain"] * length_km,
                    "haul_cost": costs["haul"] * length_km,
                    "road_type": row.road_type,
                    "source_kind": row.source_kind,
                }
            )
            next_id += 1
    return pd.DataFrame(rows)


def _union_find_components(edges: pd.DataFrame, vertex_count: int) -> np.ndarray:
    parent = np.arange(vertex_count + 1, dtype=np.int64)

    def find(item: int) -> int:
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = int(parent[item])
        return item

    for row in edges.itertuples(index=False):
        a = find(int(row.from_vertex))
        b = find(int(row.to_vertex))
        if a != b:
            parent[b] = a
    roots = np.array([find(i) for i in range(vertex_count + 1)], dtype=np.int64)
    _, labels = np.unique(roots, return_inverse=True)
    return labels


def _nearest_vertices(vertices: pd.DataFrame, points: gpd.GeoSeries) -> pd.DataFrame:
    if vertices.empty or points.empty:
        return pd.DataFrame(columns=["point_index", "vertex_id", "distance_m"])
    tree = STRtree([Point(row.x, row.y) for row in vertices.itertuples(index=False)])
    rows = []
    for index, point in enumerate(points):
        nearest_index = int(tree.nearest(point))
        vertex = vertices.iloc[nearest_index]
        rows.append(
            {
                "point_index": index,
                "vertex_id": int(vertex.vertex_id),
                "distance_m": float(point.distance(Point(vertex.x, vertex.y))),
            }
        )
    return pd.DataFrame(rows)


def build(args: argparse.Namespace) -> dict:
    started = time.time()
    source = args.source_dir
    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)

    blocks = gpd.read_file(args.blocks).to_crs(3005)
    blocks = blocks[blocks.geometry.notna() & ~blocks.geometry.is_empty].copy()
    bounds = tuple(float(value) for value in blocks.total_bounds)
    # Raster mask rather than a 1.1M-vertex polygon union.  The mask is the
    # documented clip for this strategic network; block polygons remain the
    # area source.
    aoi_mask = RasterMask(blocks.geometry, bounds, resolution=args.aoi_resolution)
    aoi_area_ha = float(blocks["area_ha"].sum())
    LOG.info("AOI: %d blocks, %.1f ha, mask=%dx%d @ %.0f m", len(blocks), aoi_area_ha, aoi_mask.width, aoi_mask.height, args.aoi_resolution)

    mills = gpd.read_file(source / "mills.gpkg").to_crs(3005)
    aoi_polygon = coverage_union_all(blocks.geometry.values)
    mills["aoi_distance_m"] = mills.geometry.distance(aoi_polygon)
    near_mills = mills[
        mills["STATUS"].eq("Op") & (mills["aoi_distance_m"] <= args.max_mill_distance)
    ].copy()
    if near_mills.empty:
        raise RuntimeError("no operating mill within the configured TSA 23 access distance")
    mill_access_union = unary_union([
        geometry.buffer(args.mill_access_buffer) for geometry in near_mills.geometry
    ])
    LOG.info("mill access buffer: %d mills within %.0f m of AOI, %.0f m buffer", len(near_mills), args.max_mill_distance, args.mill_access_buffer)

    dra = _load_source(source / "dra_roads.gpkg", aoi_mask, extra_union=mill_access_union)
    ften = _load_source(source / "ften_roads.gpkg", aoi_mask)
    lakes = _load_source(source / "lakes.gpkg", aoi_mask)
    rivers = _load_source(source / "rivers.gpkg", aoi_mask)
    protected = _load_source(source / "protected_areas.gpkg", aoi_mask)

    LOG.info("clipped: DRA=%d FTEN=%d lakes=%d rivers=%d protected=%d", len(dra), len(ften), len(lakes), len(rivers), len(protected))

    paved = dra[
        dra["ROAD_SURFACE"].fillna("").str.lower().eq("paved")
        & dra["ROAD_CLASS"].fillna("").str.lower().isin(PUBLIC_PAVED_CLASSES)
        & dra["FEATURE_TYPE"].fillna("").str.lower().eq("road")
    ].copy()
    ften = ften[
        ften["LIFE_CYCLE_STATUS_CODE"].isin(TRUE_STATUS)
        & ften["FILE_TYPE_DESCRIPTION"].isin(["Forest Service Road", "Road Permit"])
    ].copy()
    LOG.info("existing: paved=%.1f km resource=%.1f km", paved.geometry.length.sum() / 1000, ften.geometry.length.sum() / 1000)

    existing = _classify_existing(paved, ften)
    existing = _snap_existing_endpoints(existing, cluster_m=args.endpoint_snap, paved_tie_m=args.paved_tie)
    existing_union = unary_union(list(existing.geometry))
    existing_lines = list(_line_parts(existing_union))
    LOG.info("existing noded: %d pieces, %.1f km", len(existing_lines), sum(line.length for line in existing_lines) / 1000)

    existing_types, existing_kinds, _ = _assign_source_classes(existing_lines, existing)
    existing_segments, existing_vertices = _build_graph(
        existing_lines, existing_types, existing_kinds
    )
    existing_segments = _add_segment_costs(existing_segments)

    # Build mill destinations on the existing network before adding potential
    # roads.  The nearest-vertex rule is the same rule the c5 sample uses.
    mill_points = gpd.GeoSeries(
        [Point(xy) for xy in zip(mills.geometry.x, mills.geometry.y)], crs=3005
    )
    mill_nearest = _nearest_vertices(existing_vertices, mill_points)
    mill_nearest["MILL_ID"] = mills.iloc[mill_nearest["point_index"].astype(int)]["MILL_ID"].astype(str).values
    mill_nearest["PRODUCT_CODE"] = mills.iloc[mill_nearest["point_index"].astype(int)]["PRODUCT_CODE"].astype(str).values
    mill_nearest["STATUS"] = mills.iloc[mill_nearest["point_index"].astype(int)]["STATUS"].astype(str).values
    mill_nearest["AOI_DISTANCE_M"] = mills.iloc[mill_nearest["point_index"].astype(int)]["aoi_distance_m"].astype(float).values

    # Keep only mills connected to the existing network by a documented
    # distance.  The 2 km ceiling prevents a mill from being attached across a
    # data gap.
    mills_op = mill_nearest[
        mill_nearest["STATUS"].eq("Op")
        & (mill_nearest["AOI_DISTANCE_M"] <= args.max_mill_distance)
        & (mill_nearest["distance_m"] <= args.max_mill_distance)
    ].copy()
    LOG.info("mills: %d operating, %d attached within %.0f m", (mills.STATUS == "Op").sum(), len(mills_op), args.max_mill_distance)
    if mills_op.empty:
        raise RuntimeError("no operating mill attached to the existing network")

    LOG.info("existing network retained for grid connection: %d segments, %.1f km", len(existing_segments), existing_segments.length_m.sum() / 1000)

    # Potential grid.  4 km is the default because it produces roughly the
    # same new-road length as the c5 sample (about 7,000 km) on TSA 23.
    grid = _grid_segments(bounds, args.grid_spacing, diagonal_seed=args.grid_diagonal_seed)
    grid = [line for line in grid if aoi_mask.line_midpoint(line)]
    LOG.info("grid raw: %d pieces, %.1f km", len(grid), sum(line.length for line in grid) / 1000)

    # Proximity filtering uses the complete existing network.  The grid can
    # then connect otherwise isolated resource-road sections; components are
    # filtered only after the union.
    connected_existing = existing_lines
    connected_existing_union = existing_union

    impassable_mask = RasterMask(
        [*lakes.geometry, *rivers.geometry, *protected.geometry],
        bounds,
        resolution=args.aoi_resolution,
        dilate=1,
    ) if len(lakes) or len(rivers) or len(protected) else None

    grid, filter_stats = _remove_grid_near_existing(
        grid,
        connected_existing_union,
        impassable_mask,
        existing_buffer_m=args.existing_buffer,
        impassable_buffer_m=args.impassable_buffer,
        parallel_fraction=args.parallel_fraction,
    )
    LOG.info("grid after proximity/impassable filter: %d pieces, %.1f km (%s)", len(grid), sum(line.length for line in grid) / 1000, dict(filter_stats))

    grid, dangling_stats = _remove_dangling(
        grid,
        iterations=args.dangling_iterations,
        existing_union=connected_existing_union,
        preserve_m=args.existing_buffer * 2,
    )
    grid, component_stats = _keep_components(grid, min_length_m=args.min_grid_component_length)
    LOG.info("grid after dangling/component filter: %d pieces, %.1f km (%s/%s)", len(grid), sum(line.length for line in grid) / 1000, dict(dangling_stats), dict(component_stats))

    # Combine and node existing + potential lines.  A grid edge that crosses an
    # existing road becomes a shared vertex here; no separate connector is
    # inserted.
    all_lines = [*existing_lines, *grid]
    noded = _union_parts(all_lines)
    LOG.info("combined noded: %d pieces", len(noded))

    combined_source = pd.concat(
        [
            existing[["road_type", "source_kind", "geometry"]],
            gpd.GeoDataFrame(
                {
                    "road_type": ["grid"] * len(grid),
                    "source_kind": ["potential"] * len(grid),
                    "geometry": grid,
                },
                geometry="geometry",
                crs=3005,
            ),
        ],
        ignore_index=True,
    )
    noded_types, noded_kinds, noded_overlaps = _assign_source_classes(noded, combined_source)
    # A piece whose overlap is less than half its length is probably a sliver
    # created by clipping; keep it but mark the source honestly.
    all_segments, all_vertices = _build_graph(noded, noded_types, noded_kinds)
    all_segments = _add_segment_costs(all_segments)
    LOG.info("all segments: %d, %.1f km", len(all_segments), all_segments.length_m.sum() / 1000)

    # Keep the network components that contain a mill.  This removes isolated
    # potential-grid islands and source fragments without inventing connectors.
    vertex_count = int(all_vertices.vertex_id.max())
    components = _union_find_components(all_segments, vertex_count)
    vertex_component = dict(
        zip(all_vertices["vertex_id"].astype(int), components[all_vertices["vertex_id"].astype(int)])
    )
    # Re-attach the selected mills to the combined vertex set; the old
    # existing-graph ids are not stable after noding with the grid.
    mill_points_final = gpd.GeoSeries(
        [mills.iloc[int(row.point_index)].geometry for row in mills_op.itertuples(index=False)],
        crs=3005,
    )
    mill_nearest_final = _nearest_vertices(all_vertices, mill_points_final)
    mill_vertices_all = set(mill_nearest_final["vertex_id"].astype(int))
    network_components = {
        vertex_component[vertex] for vertex in mill_vertices_all if vertex in vertex_component
    }
    keep_vertices = {
        vertex for vertex, component in vertex_component.items() if component in network_components
    }
    all_segments = all_segments[
        all_segments["from_vertex"].isin(keep_vertices)
        & all_segments["to_vertex"].isin(keep_vertices)
    ].copy()
    all_vertices = all_vertices[all_vertices["vertex_id"].isin(keep_vertices)].copy()
    LOG.info("mill-connected network: %d segments, %.1f km, %d vertices", len(all_segments), all_segments.length_m.sum() / 1000, len(all_vertices))

    # Re-number vertices and segments compactly.
    vertex_map = {int(old): new for new, old in enumerate(sorted(all_vertices.vertex_id.astype(int)), start=1)}
    all_vertices = all_vertices.copy()
    all_vertices["vertex_id"] = all_vertices["vertex_id"].astype(int).map(vertex_map)
    all_segments = all_segments.copy()
    all_segments["from_vertex"] = all_segments["from_vertex"].astype(int).map(vertex_map)
    all_segments["to_vertex"] = all_segments["to_vertex"].astype(int).map(vertex_map)
    all_segments = all_segments.reset_index(drop=True)
    all_segments["segment_id"] = np.arange(1, len(all_segments) + 1, dtype=np.int64)
    all_vertices = all_vertices.sort_values("vertex_id").reset_index(drop=True)

    # Recompute mill attachments on the final vertex ids.
    final_vertex_frame = all_vertices.rename(columns={"vertex_id": "vertex_id"})
    mill_tree = STRtree([Point(row.x, row.y) for row in final_vertex_frame.itertuples(index=False)])
    destinations = []
    for row in mills_op.itertuples(index=False):
        point_index = int(row.point_index)
        point = mills.iloc[point_index].geometry
        raw_index = int(mill_tree.nearest(point))
        vertex_id = int(final_vertex_frame.iloc[raw_index].vertex_id)
        account = f"destination.MILL_{row.MILL_ID}_{row.PRODUCT_CODE}"
        destinations.append(
            {
                "name": account,
                "vertex_id": vertex_id,
                "mill_id": row.MILL_ID,
                "product_code": row.PRODUCT_CODE,
                "company": mills.iloc[point_index]["COMPANY_NAME"],
                "locality": mills.iloc[point_index]["LOCALITY"],
            }
        )
    destinations_frame = pd.DataFrame(destinations).drop_duplicates(subset=["name"])

    # Block linkage: nearest final vertex, with a documented maximum distance.
    block_centroids = blocks.geometry.representative_point()
    block_nearest = _nearest_vertices(all_vertices, gpd.GeoSeries(block_centroids, crs=3005))
    linkages = pd.DataFrame(
        {
            "block_id": blocks["block_id"].astype(int).values,
            "vertex_id": block_nearest["vertex_id"].astype(int).values,
            "link_distance_m": block_nearest["distance_m"].astype(float).values,
        }
    )
    if args.max_block_link_distance > 0:
        linkages["routed"] = linkages["link_distance_m"] <= args.max_block_link_distance
    else:
        # The c5 sample links every block to its nearest node; no arbitrary
        # distance cap.  Keep the distance in the report so outliers are visible.
        linkages["routed"] = True
    linked = linkages[linkages["routed"]].copy()
    LOG.info(
        "blocks: %d linked, %d by the current distance rule (%s)",
        len(linked),
        len(linkages) - len(linked),
        "no cap" if args.max_block_link_distance <= 0 else f"{args.max_block_link_distance:.0f} m",
    )

    # Component reachability on the final network.
    final_components = _union_find_components(all_segments, int(all_vertices.vertex_id.max()))
    final_vertex_component = dict(
        zip(all_vertices["vertex_id"].astype(int), final_components[all_vertices["vertex_id"].astype(int)])
    )
    destination_components = {
        final_vertex_component[int(vertex)]
        for vertex in destinations_frame["vertex_id"].astype(int)
        if int(vertex) in final_vertex_component
    }
    linked["route_component"] = linked["vertex_id"].map(final_vertex_component)
    linked["routed"] = linked["route_component"].isin(destination_components)
    linkages = linkages.drop(columns=["routed"]).merge(
        linked[["block_id", "routed"]], on="block_id", how="left"
    )
    linkages["routed"] = linkages["routed"].fillna(False).astype(bool)
    routed_count = int(linkages["routed"].sum())
    LOG.info("WS4 reachability: %d routed / %d blocks", routed_count, len(linkages))

    # Write the four WS4 tables.
    segments_out = all_segments[
        [
            "segment_id",
            "from_vertex",
            "to_vertex",
            "length_m",
            "haul_cost",
            "build_cost",
            "maintain_cost",
            "road_type",
            "source_kind",
        ]
    ].copy()
    vertices_out = all_vertices[["vertex_id", "x", "y"]].copy()
    destinations_out = destinations_frame[["name", "vertex_id"]].copy()
    linkage_status = linkages[["block_id", "vertex_id", "link_distance_m", "routed"]].copy()
    linkage_status["status"] = np.where(linkage_status["routed"], "routed", "no_linkage")
    # WS4 must not receive a row for an unlinked block.  Keep the full status
    # table as a separate report so 2,587 blocks are not silently routed.
    linkages_out = linkage_status[linkage_status["routed"]][
        ["block_id", "vertex_id", "link_distance_m"]
    ].copy()

    fixture = out / "route_fixture"
    fixture.mkdir(parents=True, exist_ok=True)
    segments_out.to_csv(fixture / "segments.csv", index=False)
    vertices_out.to_csv(fixture / "vertices.csv", index=False)
    destinations_out.to_csv(fixture / "destinations.csv", index=False)
    linkages_out.to_csv(fixture / "linkages.csv", index=False)
    linkage_status.to_csv(out / "block_linkage_status.csv", index=False)

    # A compact spatial layer for inspection (not the WS4 input).
    road_table = segments_out.merge(
        vertices_out.rename(columns={"vertex_id": "from_vertex", "x": "x1", "y": "y1"}),
        on="from_vertex",
        how="left",
    ).merge(
        vertices_out.rename(columns={"vertex_id": "to_vertex", "x": "x2", "y": "y2"}),
        on="to_vertex",
        how="left",
    )
    road_layer = gpd.GeoDataFrame(
        road_table,
        geometry=[
            LineString([(row.x1, row.y1), (row.x2, row.y2)])
            for row in road_table.itertuples(index=False)
        ],
        crs=3005,
    )
    road_layer.to_file(out / "network.gpkg", driver="GPKG", layer="roads")

    # WS4 load check (does not modify WS4).
    from ws4.roads.network import RouteNetwork

    network = RouteNetwork.from_tables(
        segments_out,
        destinations_out,
        linkages_out.rename(columns={"block_id": "block_id", "vertex_id": "vertex_id"}),
        vertices=vertices_out,
    )
    LOG.info("WS4 RouteNetwork loaded: segments=%d vertices=%d destinations=%d blocks=%d", len(network.segments), len(network.vertex_coordinates), len(network.destinations), len(network.block_vertex))

    # Summaries by class and source.
    class_summary = (
        segments_out.groupby(["source_kind", "road_type"], dropna=False)
        .agg(segments=("segment_id", "count"), length_km=("length_m", lambda values: float(values.sum()) / 1000.0))
        .reset_index()
        .to_dict(orient="records")
    )
    components = _union_find_components(segments_out, int(vertices_out.vertex_id.max()))
    component_sizes = Counter(
        int(components[int(vertex)]) for vertex in vertices_out["vertex_id"].astype(int)
    )
    summary = {
        "schema": "fresh.road.network.summary.v1",
        "generated_utc": pd.Timestamp.now(tz="UTC").isoformat(),
        "aoi": {
            "blocks": len(blocks),
            "area_ha": float(aoi_area_ha),
            "bounds_epsg3005": [float(value) for value in bounds],
            "clip": f"raster mask at {args.aoi_resolution:.0f} m",
        },
        "source": {
            "dra_features": len(dra),
            "ften_features": len(ften),
            "lakes_features": len(lakes),
            "rivers_features": len(rivers),
            "protected_area_features": len(protected),
            "mill_features": len(mills),
        },
        "existing": {
            "paved_km": float(
                segments_out.loc[segments_out.source_kind == "existing_paved", "length_m"].sum() / 1000.0
            ),
            "resource_km": float(
                segments_out.loc[segments_out.source_kind == "existing_resource", "length_m"].sum() / 1000.0
            ),
            "source_paved_km": float(paved.geometry.length.sum() / 1000.0),
            "source_resource_km": float(ften.geometry.length.sum() / 1000.0),
            "segments": int((segments_out.source_kind != "potential").sum()),
            "length_km": float(segments_out.loc[segments_out.source_kind != "potential", "length_m"].sum() / 1000.0),
        },
        "potential": {
            "grid_spacing_m": float(args.grid_spacing),
            "raw_pieces": len(_grid_segments(bounds, args.grid_spacing)),
            "filtered_pieces": len(grid),
            "filtered_length_km": float(sum(line.length for line in grid) / 1000.0),
            "class_variants": len(POTENTIAL_COSTS),
            "segments": int((segments_out.source_kind == "potential").sum()),
            "length_km_by_variant": float(segments_out.loc[segments_out.source_kind == "potential", "length_m"].sum() / 1000.0 / len(POTENTIAL_COSTS)),
            "filters": {**dict(filter_stats), **dict(dangling_stats), **dict(component_stats)},
        },
        "network": {
            "segments": len(segments_out),
            "vertices": len(vertices_out),
            "destinations": len(destinations_out),
            "components": len(component_sizes),
            "largest_component_vertices": int(max(component_sizes.values())),
            "class_summary": class_summary,
        },
        "linkage": {
            "blocks": int(len(linkage_status)),
            "linked_within_m": (
                None if args.max_block_link_distance <= 0 else float(args.max_block_link_distance)
            ),
            "linked_blocks": (
                int(len(linkages_out))
                if args.max_block_link_distance <= 0
                else int(linkages_out["link_distance_m"].le(args.max_block_link_distance).sum())
            ),
            "routed_blocks": int(linkage_status["routed"].sum()),
            "no_route_or_no_linkage": int((~linkage_status["routed"]).sum()),
            "link_distance_m": {
                "min": float(linkage_status["link_distance_m"].min()),
                "median": float(linkage_status["link_distance_m"].median()),
                "p90": float(linkage_status["link_distance_m"].quantile(0.9)),
                "max": float(linkage_status["link_distance_m"].max()),
            },
            "status_file": "block_linkage_status.csv",
        },
        "costs": {
            "existing": EXISTING_COSTS,
            "potential": POTENTIAL_COSTS,
            "source": "docs/cost-sources.md",
            "caveat": "c5 has one new-road build coefficient (N); all four potential classes share it.",
        },
        "ws4_load": {
            "segments": int(len(network.segments)),
            "vertices_with_coordinates": int(len(network.vertex_coordinates)),
            "destinations": int(len(network.destinations)),
            "block_vertices": int(len(network.block_vertex)),
            "note": "loaded with ws4.roads.network.RouteNetwork.from_tables; no WS4 code changed",
        },
        "elapsed_seconds": float(time.time() - started),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    LOG.info("summary -> %s", out / "summary.json")
    LOG.info("done in %.1f s", time.time() - started)
    return summary


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blocks", type=Path, default=DEFAULT_BLOCKS)
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--grid-spacing", type=float, default=600.0)
    parser.add_argument("--grid-diagonal-seed", type=int, default=2025)
    parser.add_argument("--aoi-resolution", type=float, default=50.0)
    parser.add_argument("--existing-buffer", type=float, default=30.0)
    parser.add_argument("--impassable-buffer", type=float, default=10.0)
    parser.add_argument("--parallel-fraction", type=float, default=0.5)
    parser.add_argument("--dangling-iterations", type=int, default=3)
    parser.add_argument("--min-grid-component-length", type=float, default=1000.0)
    parser.add_argument("--endpoint-snap", type=float, default=10.0)
    parser.add_argument("--paved-tie", type=float, default=25.0)
    parser.add_argument("--max-mill-distance", type=float, default=5000.0)
    parser.add_argument("--mill-access-buffer", type=float, default=15000.0)
    parser.add_argument(
        "--max-block-link-distance",
        type=float,
        default=0.0,
        help="0 means nearest-vertex linkage with no distance cap (c5 behaviour).",
    )
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
    )
    build(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
