# TSA 23 c5-style road network

This is the planned WS4 road network for TSA 23, built as a Patchworks c5-style
paved/resource/potential graph.  It is **not** the earlier DRA-only route test.

## What was built

- **AOI**: TSA 23 stand extent, 102,128 blocks / 988,816 ha.  The network is
  clipped by a 50 m raster mask over those blocks.
- **Existing paved public roads**: DRA
  `WHSE_BASEMAPPING.DRA_DGTL_ROAD_ATLAS_MPAR_SP`, surface `paved`, public
  classes (`highway`, `arterial`, `collector`, `local`, `service`, `yield`).
  Roads within 15 km of the selected mills are included so the mills connect
  to the forest entry points.
- **Existing resource roads**: FTEN
  `WHSE_FOREST_TENURE.FTEN_ROAD_SECTION_LINES_SVW`, active/pending Forest
  Service Roads and Road Permits, clipped to the TSA 23 AOI.
- **Mills**: operating public timber-processing facilities within 5 km of the
  TSA 23 AOI.  Three 100 Mile House mills qualify:
  `MILL_95_LBR`, `MILL_694_LGH`, `MILL_733_LGH`.  The seven Williams Lake
  operating mills are 25–36 km outside TSA 23 and are not treated as TSA 23
  destinations in this build.
- **Potential roads**: 4 km regular grid over the AOI.  Grid edges near
  existing roads, inside lakes/rivers/protected areas, or dangling are removed.
  Each surviving grid edge is emitted four times with identical geometry and
  class-specific maintenance/haul costs.

## Cost table

Existing roads have **build cost 0**.  The c5 sample is the source; the T
haul value is taken from the c5 `access.shp` fields (0.32, not the 0.27 in the
workbook).

| Existing type | Build CAD/km | Maintain CAD/km/period | Haul CAD/m³/km |
|---|---:|---:|---:|
| H | 0 | 0 | 0.06 |
| P | 0 | 2000 | 0.10 |
| S | 0 | 2000 | 0.16 |
| T | 0 | 2000 | 0.32 |

Potential classes all use the c5 **N** construction coefficient because the c5
sample has only one new-road construction row.  Their maintenance/haul values
come from c5 P/S/T/N:

| Potential class | Build CAD/km | Maintain CAD/km/period | Haul CAD/m³/km |
|---|---:|---:|---:|
| class_1 | 5000 | 2000 | 0.10 |
| class_2 | 5000 | 2000 | 0.16 |
| class_3 | 5000 | 2000 | 0.32 |
| class_4 | 5000 | 500 | 0.255078 |

This is an explicit limitation, not a claim that c5 contains a four-way
construction ladder.  See [`../../docs/cost-sources.md`](../../docs/cost-sources.md).

## Result

| Metric | Value |
|---|---:|
| Existing paved | 475.0 km |
| Existing resource | 5,918.8 km |
| Potential grid, one class | 4,336.0 km |
| Potential class variants | 4 |
| Network segments | 25,159 |
| Vertices | 13,321 |
| Destinations | 3 |
| Connected components | 1 |
| Blocks linked within 3 km | 99,541 / 102,128 |
| Blocks routed to a mill | 99,541 |
| Blocks with no linkage | 2,587 |

The 2,587 unlinked blocks are farther than 3 km from the nearest network vertex;
they are not called “no access.”  They are reported as `no_linkage` in the
linkage table.

## Files

- `fetch_public_data.py` — reproducible BCGW WFS fetch (large files go to
  `runtime/source/`, which is ignored).
- `build_network.py` — network assembly and WS4 table writer.
- `route_fixture/` — the four WS4 tables:
  `segments.csv`, `vertices.csv`, `destinations.csv`, `linkages.csv`.
- `network.gpkg` — inspection layer with one row per segment variant.
- `summary.json` — machine-readable build summary.
- `source_manifest.json` — WFS type names and feature counts.

## Run

```bash
python examples/tsa23_c5_network/fetch_public_data.py --force
python examples/tsa23_c5_network/build_network.py
```

The build is deterministic except for the timestamp in `summary.json`.

## Limitations

- The grid is strategic (4 km).  It is not a cutblock-level road layout.
- The potential classes share one construction cost because that is the only
  new-road coefficient in c5.  Do not read the four variants as four
  independently costed engineering standards.
- The AOI clip is a 50 m raster mask, not an exact polygon intersection.  This
  avoids the 1.1M-vertex TSA block boundary but can include a boundary cell.
- Lakes, FWA rivers, and protected areas are masked.  No public cliff polygon
  was identified in the BCGW WFS catalogue; cliff/rock terrain is not applied
  as an impassable layer in this build.
- Block and mill attachment is nearest-vertex; it is a linkage rule, not a
  field-verified access point.
- No WS4 objective, constraint, growth, solver, or compiled dataset was
  changed.
