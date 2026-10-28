# TFL 6 road-status route crosswalk fixture

This is the WS4-facing crosswalk for the four TFL 6 DRA segments in the
`fresh-road` pilot. It is a **report-only fixture**, not a complete TFL 6
WS4 route model.

## What it contains

- `vertices.csv`: 18 vertices from the DRA geometry nodes.
- `segments.csv`: 16 WS4-style route edges, split at DRA geometry vertices.
- `destinations.csv`: empty; no mill allocation is invented.
- `linkages.csv`: empty; no block-to-road assignment is invented.
- `crosswalk.csv`: one-to-many mapping from `dra_segment_id` to
  `ws4_segment_id`.
- `road_status_by_route_edge.csv`: the road-status classes and widths joined
  to the route-edge ids.

`fresh.road.status.v1` is keyed by DRA segment, while a WS4 route graph is
keyed by route edges. A single DRA segment can become several route edges after
splitting at geometry nodes. That is why the crosswalk is one-to-many.

## Cost columns are deliberately zero

`haul_cost`, `build_cost`, and `maintain_cost` are zero in this fixture. The
fixture is for checking the status join, not for running WS4 or costing roads.
Do not use these zero-cost edges in an optimization.

## Validate the fixture

```python
import pandas as pd
from pathlib import Path
from ws4.roads.network import RouteNetwork

root = Path("examples/tfl6_ledges/route_fixture")
net = RouteNetwork.from_tables(
    pd.read_csv(root / "segments.csv"),
    pd.read_csv(root / "destinations.csv"),
    pd.read_csv(root / "linkages.csv"),
    vertices=pd.read_csv(root / "vertices.csv"),
)
print(len(net.segments), len(net.vertex_coordinates))
```

The TFL 6 instance still needs a real WS4 route graph with destinations and
block linkages before this can become a model input. The current fixture only
proves the id mapping and report join.
