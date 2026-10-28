# Full TSA 23 route graph

This is the full TSA 23 DRA route graph, built from the public BCGW WFS and the
TSA 23 block layer. It is a route-length/access fixture, not a cost or
optimization model.

## Source

- TSA 23 bbox:
  `-122.25833858,50.95138545,-120.20000032,52.19999992` (EPSG:4326)
- Roads: BC Digital Road Atlas
  `WHSE_BASEMAPPING.DRA_DGTL_ROAD_ATLAS_MPAR_SP`
- WFS result: **90,198** road features
- Blocks: 102,128 TSA 23 blocks
- Destination: **West Fraser 100 Mile House**, `MILL_ID 95`, `LBR`, `Op`

The 57 MB DRA GPKG is not committed. The route fixture and report are small
enough to inspect.

## Fixture

- 90,198 route edges
- 80,733 vertices
- 102,128 block linkages
- one destination
- zero cost columns

`RouteNetwork.from_tables` loads the fixture.

## Route result

| Metric | Value |
|---|---:|
| Blocks | 102,128 |
| Routed to 100 Mile House | **99,335** |
| No route in DRA graph | **2,793** |
| WS4 block area | 988,816 ha |
| Routed area | 961,758 ha |
| Unrouted area | 27,058 ha |
| Route length median | 59,529 m |
| Route length p90 | 93,539 m |
| Route length max | 153,897 m |
| Connected components | 779 |
| Largest component | 77,819 vertices |

The 2,793 no-route blocks are explicitly `no_route_in_dra_graph` in
`ws4_route_report_full.csv`; they are not silently assigned a zero route.

## Important limitations

- The graph uses DRA features as edges; it does not split every line at every
  geometry vertex. The resulting 779 components reflect the DRA geometry and
  connectivity, not a cleaned road-network topology.
- Costs are zero. This is route length only.
- The 100 Mile House mill is a public destination, but no mill demand is
  allocated.
- No WS4 objective, constraint, growth, solver, or compiled dataset was
  changed.

## Files

- `route_fixture/segments.csv`, `vertices.csv`, `destinations.csv`,
  `linkages.csv`, `crosswalk.csv`
- `route_lengths_full.csv`
- `ws4_route_report_full.csv`
- `ws4_route_report_full_summary.json`
- `source_manifest.json`
