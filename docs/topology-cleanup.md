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
| Blocks unrouted | 2,793 | 2,839 |
| Median route length | 59,529 m | 59,536 m |
| P90 route length | 93,539 m | 93,655 m |
| Max route length | 153,897 m | 153,837 m |

Noding reduced edge count but did not reduce the disconnected components or
improve block access. The remaining gaps are in the DRA source connectivity,
not simple duplicate vertices. A snap tolerance could force more connections,
but that would be a new topology assumption and was not applied.

## Conclusion

- Do not add full-graph costs or start PLAN-05 until access gaps are resolved or
  explicitly classified as no-access.
- The 2,793/2,839 disconnected blocks must remain visible.
- A future cleanup should use an authoritative road-topology source or a
  documented snapping rule with validation, not arbitrary connectors.

No WS4 objective, constraint, solver, or growth code was changed.
