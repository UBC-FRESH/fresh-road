# TSA 23 route/access test

This is a TSA 23 route-topology/access test built from public DRA road vectors
and the existing TSA 23 block layer. It replaces the TFL 6 route-graph attempt
as the easier route fixture: interior BC, no coastal water masking, and roads
are directly available from the BCGW WFS.

## Source

- AOI: 5 km around TSA 23 block `33140`
- Bbox: `-121.2719135,51.5422347,-121.1919135,51.6022347` (EPSG:4326)
- Roads: BC Digital Road Atlas, `WHSE_BASEMAPPING.DRA_DGTL_ROAD_ATLAS_MPAR_SP`
- Query:
  `https://openmaps.gov.bc.ca/geo/pub/ows?service=WFS&version=2.0.0&request=GetFeature&typeName=WHSE_BASEMAPPING.DRA_DGTL_ROAD_ATLAS_MPAR_SP&outputFormat=application/json&count=10000&bbox=...`
- Blocks: TSA 23 `runtime/gis/tsa23_blocks.geojson`

The query returned 450 DRA lines clipped to the 5 km box. The road vectors are
small enough to keep in this example (`roads.gpkg`); no point cloud is needed
for this topology test.

## Fixture

`route_fixture/`:

- 6,881 vertices
- 6,921 route edges
- 356 TSA 23 blocks in the AOI
- one-to-many DRA-to-route-edge crosswalk
- block-to-nearest-vertex linkages
- empty `destinations.csv`
- zero cost columns

The fixture loads through `ws4.roads.network.RouteNetwork.from_tables`:

```text
segments=6921 vertices=6881 blocks=356 destinations=0
```

## Route/access findings

- Median block-to-road-vertex distance: **109.1 m**
- 90th percentile: **343.9 m**
- Maximum: **1,020.2 m**
- The graph has **10 connected components**; the largest contains 6,566
  vertices and 323 of the 356 blocks.
- 33 blocks are linked to smaller disconnected components.

These are topology/access diagnostics, not a route cost or harvest feasibility
result.

## What is not invented

- `destinations.csv` is empty; no mill assignment is invented.
- `linkages.csv` assigns each block to its nearest route vertex, recorded with
  the distance.
- Cost columns are zero; the fixture is not an optimization input.
- The graph is a 5 km test, not a complete TSA 23 road network.

## Next

1. Add real destinations and block-to-road assignment policy.
2. Add the documented haul/build/maintain cost model.
3. Then run route costs and PLAN-05 connectivity.
4. The TFL 6 ALS status pilot remains separate; it is not part of this TSA 23
   topology fixture.
