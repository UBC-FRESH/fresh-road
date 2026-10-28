# TSA 23 / 100 Mile House route test

This is a real route-length test on TSA 23 with an actual public mill
destination. It uses DRA road vectors and the TSA 23 block layer; it does not
require coastal water masking and it does not use the TFL 6 route-graph gap.

## Source data

- AOI: 10 km box around the West Fraser 100 Mile House mill
- Mill: `MILL_ID 95`, West Fraser Mills Ltd., 100 Mile House, LBR, status `Op`
- Roads: BC Digital Road Atlas
  `WHSE_BASEMAPPING.DRA_DGTL_ROAD_ATLAS_MPAR_SP`
- Blocks: TSA 23 `runtime/gis/tsa23_blocks.geojson`

Inputs fetched from the public BCGW WFS:

- 1,414 DRA lines / 1,315 merged line parts
- 1 public mill destination
- 729 TSA 23 blocks whose centroids fall inside the road bbox

## Route fixture

- 18,314 route edges
- 17,972 vertices
- 729 blocks linked to the nearest route vertex
- one destination: `destination.WEST_FRASER_100MILE_95`
- `destinations.csv` and `linkages.csv` populated
- zero cost columns

`RouteNetwork.from_tables` loads:

```text
segments=18314 vertices=17972 blocks=729 destinations=1
```

## Route-length result

Using route length (not cost) with every edge open:

| Metric | Value |
|---|---:|
| Blocks routed to the mill | **727 / 729** |
| Minimum route length | 495 m |
| Median route length | 6,550 m |
| 90th percentile | 9,542 m |
| Maximum route length | 11,265 m |
| Not routed | blocks `20222`, `67577` |
| Connected components | 3 |
| Largest component | 17,949 vertices |

The two no-route blocks are in small disconnected components, not missing from
the block layer. Both share the same nearest road vertex and are **777.9 m**
from the nearest DRA line. They are classified `no_route_in_dra_graph` in
`block_access_status.csv`; no connector or zero-length access link was
invented.

## TR-28 subgrade reconstruction scenario

A documented partial cost scenario is included:

- FERIC TR-28, `Caterpillar 235 hydraulic backhoe`
- 2024 CAD unit cost: **28.7654 CAD/m**
- source: `fhops.reference.tr28_subgrade`
- `segments_tr28.csv`: every route edge assigned that unit cost
- `route_build_costs_tr28.csv`: build cost along the shortest-length path

| Route construction cost | CAD |
|---|---:|
| Minimum | 14,235 |
| Median | 188,422 |
| 90th percentile | 274,477 |
| Maximum | 324,034 |

This is a **subgrade reconstruction scenario**, not the present-day cost of the
existing DRA roads. It excludes haul and maintenance. It is not a total
delivered cost and is not used by WS4 optimization.

## Partial haul scenario

A separate haul-variable scenario uses the public FHOPS `examples/hauling`
highway truck:

- capacity 45 m3
- variable cost **1.20 CAD/min**
- scenario speed **37 km/h**, derived from the example's three
  `travel_minutes`/`distance_km` pairs
- round-trip travel only

| Haul variable cost | CAD/m3 |
|---|---:|
| Minimum | 0.043 |
| Median | 0.567 |
| 90th percentile | 0.825 |
| Maximum | 0.974 |

This excludes the fixed truck day, loading/unloading, overtime, maintenance,
and profit. It is not a delivered-cost model.

## WS4 report-only join

`build_ws4_report.py` joins the route/status table to the TSA 23 compiled WS4
block ids and writes:

- `ws4_route_report.csv`
- `ws4_route_report_summary.json`
- `haul_cost_parameters.json`

The join is report-only and uses the existing WS4 compiled block table:

- 729 route blocks matched to 729 WS4 blocks
- 6,807.75 ha of WS4 block area
- 727 routed blocks / 6,801.06 ha
- two no-route blocks (`20222`, `67577`)

No WS4 objective, constraint, solver, or growth table was changed.

## What is not claimed

- The base route test has zero costs; the TR-28 file is a separate partial
  build-cost scenario, not a full haul/build/maintenance model.
- TR-28 assumes subgrade reconstruction of every segment; it is not a claim
  that the existing roads need rebuilding.
- The mill is a public facility, but no mill demand allocation is created.
- Blocks are linked to the nearest road vertex; that is a documented linkage
  rule, not a field-verified access point.
- No WS4 objective, constraint, solver, or growth code was changed.

`route_lengths.csv` contains the block-level route lengths and access distances.
`block_access_status.csv` classifies every block as `routed` or
`no_route_in_dra_graph`. `source_manifest.json` records the exact sources and
counts.

## Next

1. Resolve the two disconnected blocks (link, drop, or mark as `no_route_in_dra_graph`).
2. Add documented haul/build/maintenance cost parameters.
3. Run route costs against a WS4/TSA23 schedule.
4. Then use the graph for PLAN-05 connectivity.
