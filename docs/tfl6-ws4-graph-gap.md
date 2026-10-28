# TFL 6 WS4 route-graph gap

Status: **partial crosswalk fixture only**  
Date: 2026-10-28

## What exists

The TFL 6 instance has:

- public DRA road vectors:
  `data/source/tfl_6/roads/dra_roads_tfl6.gpkg`
- Patchworks block/track tables under
  `models/tfl6_patchworks_model/`
- a `fresh-road` pilot for four DRA segments

The `fresh-road` fixture at
`fresh-road/examples/tfl6_ledges/route_fixture/` contains:

- 18 vertices
- 16 node-split route edges
- a one-to-many DRA-to-route-edge crosswalk
- a road-status-by-edge report
- empty `destinations.csv` and `linkages.csv`
- zero costs

It loads through `ws4.roads.network.RouteNetwork.from_tables`, but it is not a
complete WS4 route model.

## What is missing

A real TFL 6 WS4 route graph needs the four established tables:

- `vertices.csv`: road junctions with coordinates
- `segments.csv`: edges, endpoint vertices, length, haul/build/maintenance cost
- `destinations.csv`: mill/facility vertices
- `linkages.csv`: block-to-vertex assignments

The TFL 6 instance has DRA linework but no materialized WS4/Patchworks route
tables. The Patchworks model has `tracks/` and `blocks/`, but no
`vertices/segments/destinations/linkages` route model. The sample route graph
under `tmp/sample_2025` is a different dataset and cannot be relabeled as TFL 6.

## Why we will not invent the missing pieces

The following are not derivable from DRA linework without new assumptions:

- mill destinations;
- block-to-road assignments;
- haul, build, and maintenance costs;
- road class/cost policy.

Writing zero costs and arbitrary destinations would create a route graph that
looks valid to WS4 but is not a model of TFL 6. That would violate the
no-fabrication rule and could silently change routing or optimization.

## What can be done next

1. Find an existing TFL 6 WS4/Patchworks route model with the four tables and
   map its edge ids to DRA ids.
2. If no route model exists, create one as a separate, explicit modeling task
   with documented cost and destination sources.
3. Until then, keep the crosswalk as a report-only fixture and do not use it
   in WS4 optimization.
4. PLAN-05 can proceed on a different WS4 dataset that already has a route
   graph; it should not use the TFL 6 fixture as if it were complete.

## Reproduce the fixture check

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
print(len(net.segments), len(net.vertex_coordinates), len(net.destinations))
```

Expected: `16 18 0`.
