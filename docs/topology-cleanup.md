# TSA 23 route topology cleanup

Status: completed, **did not materially improve connectivity**

## What was cleaned

- read the 90,198 DRA road features used by the full TSA 23 route test
- applied `shapely.unary_union` to node coincident linework at intersections
- applied `linemerge` to merge continuous pieces
- preserved isolated components rather than inventing connectors
- rebuilt the route graph from the resulting 83,187 line parts
- re-linked all 102,128 TSA 23 blocks to the nearest route vertex
- reran the 100 Mile House route test

## Before / after

| Metric | Raw DRA features | Noded/merged |
|---|---:|---:|
| Route edges | 90,198 | 83,187 |
| Vertices | 80,733 | 73,719 |
| Connected components | 779 | 778 |
| Blocks routed | 99,335 | 99,289 |
| Blocks no-route | 2,793 | 2,839 |
| Median route length | 59,529 m | 59,536 m |
| P90 route length | 93,539 m | 93,655 m |
| Max route length | 153,897 m | 153,837 m |

Noding reduced edge count but did not reduce the disconnected components or
improve block access. The remaining gaps are in the DRA source connectivity,
not simple duplicate vertices. A snap tolerance could force more connections,
but that would be a new topology assumption and was not applied.

## Conclusion

- Do not add full-graph costs or start PLAN-05 until access gaps are resolved or
  explicitly classified as no route in the DRA graph.
- The 2,793/2,839 disconnected blocks must remain visible.
- A future cleanup should use an authoritative road-topology source or a
  documented snapping rule with validation, not arbitrary connectors.

No WS4 objective, constraint, solver, or growth code was changed.

## Additional FSR layer check

The public Forest Tenure road-section layer
`WHSE_FOREST_TENURE.FTEN_ROAD_SECTION_LINES_SVW` was also tested:

- 16,112 unique sections in the TSA 23 bbox
- 11,089 `ACTIVE` sections retained
- combined with the 90,198 DRA features and re-noded

Result: 509,374 merged parts, 302,314 vertices, **1,787 components**, and
95,831 blocks routed (6,297 no-route). The FSR layer made connectivity worse,
so it was not adopted.

The DRA-only graph remains the better base. The remaining disconnected blocks
are a source/topology limitation, not a missing endpoint-snap or a missing FSR
layer.
