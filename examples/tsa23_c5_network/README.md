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
- **Potential roads**: c5-style **600 m** square lattice with one 45-degree
  diagonal per cell.  The c5 `access.shp` potential roads are a 600 m lattice
  with one diagonal per occupied cell; the orientation is 50/50 in c5 with no
  recoverable spatial rule, so a fixed seed (`2025`) is used for the diagonal
  orientation.  Grid edges near existing roads, inside lakes/rivers/protected
  areas, or dangling are removed.  Each surviving grid edge is emitted four
  times with identical geometry and class-specific maintenance/haul costs.

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

The table lists coefficients per kilometre.  WS4 stores total segment costs, so
each segment's `build_cost`, `maintain_cost`, and `haul_cost` are the per-km
coefficient multiplied by `length_m / 1000`.

This is an explicit limitation, not a claim that c5 contains a four-way
construction ladder.  See [`../../docs/cost-sources.md`](../../docs/cost-sources.md).

## Result

| Metric | Value |
|---|---:|
| Existing paved | 583.6 km |
| Existing resource | 7,863.9 km |
| Potential grid, one class | 55,317.5 km |
| Potential class variants | 4 |
| Network segments | 465,263 |
| Vertices | 72,299 |
| Destinations | 3 |
| Connected components | 1 |
| Blocks linked to nearest vertex | 102,128 / 102,128 |
| Blocks routed to a mill | 102,128 |
| Blocks with no linkage | 0 |

The linkage is nearest-vertex, following the c5 rule; there is no distance cap.
The median block-to-vertex distance is 210 m, the 99th percentile is 1.28 km,
and the maximum is 8.11 km.  The maximum is retained in
`block_linkage_status.csv` as a visible outlier rather than hidden by a cap.

## WS4 report-only routing

`ws4_report/route.yaml` is a standard WS4 route configuration for the four
route tables.  `ws4_report/build_report.py` loads it through
`ws4.roads.accounts.load_route_config`, assigns every linked block to its
least-haul-cost mill, and writes:

- `ws4_report/block_routes.csv`
- `ws4_report/summary.json`

Result:

| Metric | Value |
|---|---:|
| Blocks routed | 102,128 / 102,128 |
| No-linkage blocks | 0 |
| Mills used | 3 |
| Destination split (733 / 694 / 95) | 61,534 / 24,315 / 16,279 |
| Median route length, nearest mill | 44.5 km |
| Median route length to `MILL_95_LBR` | 50.6 km |
| Median haul cost | 4.01 CAD/m³ |
| Unique used segments | 56,498 |
| Unique used length | 24,227 km |
| Unique used build exposure | 113.46 M CAD |

Against the DRA-only baseline, 99,335 routed blocks match.  The median
nearest-mill route is 13.37 km shorter than the DRA-only route because the
600 m lattice provides more direct candidate routes and three mills; forcing
every block to `MILL_95_LBR` is 6.73 km shorter at the median.

The destination split is a **least-haul assignment**, not a product-eligibility
or mill-demand allocation.  No product-specific eligibility table is invented.

This is report-only.  No WS4 objective, constraint, growth, solver, or compiled
dataset was changed.

## WS4 simulation pass

`ws4_sim/` runs the same compiled TSA 23 dataset and `schedule_baseline.csv`
(2,000 blocks, 5 years) with and without the c5 route model.  No objective,
constraint, growth, or solver code is changed.  The DRA-only orphan components
are not part of the planned network and are not used as a baseline.

| Metric | c5 |
|---|---:|
| Routed ledger volume | 5,280,492 |
| Unrouted ledger volume | 0 |
| Unrouted blocks | 0 |
| Average haul distance | 44.66 km |
| Build expense | 28.98 M CAD |
| Haul expense | 21.67 M CAD |
| Maintenance expense | 11.73 M CAD |
| Total route expense | 62.38 M CAD |

The no-road and c5 runs have identical product account values.  The c5 route
report averages are 5.489 CAD/m³ build, 4.104 CAD/m³ haul, and 2.221 CAD/m³
maintenance.

The destination split remains a least-haul assignment, not product eligibility
or mill demand.  Ledger volume is the sum of routed product rows, not
merchantable volume.

## Files

- `fetch_public_data.py` — reproducible BCGW WFS fetch (large files go to
  `runtime/source/`, which is ignored).
- `build_network.py` — network assembly and WS4 table writer.
- `route_fixture/` — the four WS4 tables:
  `segments.csv`, `vertices.csv`, `destinations.csv`, `linkages.csv`.
- `block_linkage_status.csv` — every block and its nearest-vertex distance;
  all 102,128 are linked in this build.
- `network.gpkg` — local inspection layer with one row per segment variant;
  generated by the build, not committed (it is over 100 MB at 600 m).
- `summary.json` — machine-readable build summary.
- `source_manifest.json` — WFS type names and feature counts.
- `ws4_report/route.yaml`, `build_report.py`, and the report outputs.
- `ws4_sim/` — actual simulation runs and comparison.

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
