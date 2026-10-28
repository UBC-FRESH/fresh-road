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

The two unrouted blocks are in small disconnected components, not missing from
the block layer. Both share the same nearest road vertex and are **777.9 m**
from the nearest DRA line. They are classified `unrouted_disconnected` in
`block_access_status.csv`; no connector or zero-length access link was
invented.

## What is not claimed

- Cost columns are **zero**; this is a route-length test, not a haul/build cost
  model.
- The mill is a public facility, but no mill demand allocation is created.
- Blocks are linked to the nearest road vertex; that is a documented linkage
  rule, not a field-verified access point.
- No WS4 objective, constraint, solver, or growth code was changed.

`route_lengths.csv` contains the block-level route lengths and access distances.
`block_access_status.csv` classifies every block as `routed` or
`unrouted_disconnected`. `source_manifest.json` records the exact sources and
counts.

## Next

1. Resolve the two disconnected blocks (link, drop, or mark as no-access).
2. Add documented haul/build/maintenance cost parameters.
3. Run route costs against a WS4/TSA23 schedule.
4. Then use the graph for PLAN-05 connectivity.
