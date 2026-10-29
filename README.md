# fresh-road

`fresh-road` is a small, optional bridge between the published
[ALSroads](https://github.com/r-lidar-lab/ALSroads) implementation and the
FRESH ecosystem.

It does one job: turn an ALSroads result over an existing BC Digital Road Atlas
(DRA) centerline into a source-preserving **road-status record**. It does not
invent a new road detector, a new passability model, or a new optimizer input.

Status: `0.1.0a1` alpha / pilot.

**Important:** the TSA 23 `tsa23_route`, `tsa23_mill_route`, and
`tsa23_full_route` examples are exploratory DRA-only tests. They are not the
planned WS4 paved/resource/grid road network. The planned c5-style network is
in [`examples/tsa23_c5_network/`](examples/tsa23_c5_network/).

## Why it exists

WS4 can build, route, and cost a supplied road network. FHOPS assumes access.
Neither ingests remotely sensed road condition. The INV-09 candidate is the
missing data contract between:

- public ALS point clouds and DRA roads;
- ALSroads measurements (`CLASS`, `SCORE`, width, cover, shoulders);
- a road-status layer that WS4/FHOPS can consume later.

This package starts with the contract and one real TFL 6 pilot. It does not
change WS4 routing, costs, objectives, or constraints.

## Record contract

The proposed record schema is `fresh.road.status.v1`:

| Field | Meaning |
|---|---|
| `segment_id` | Stable source segment id, e.g. `dra:1781964` |
| `status` | Source-preserving ALSroads class: `class_1`–`class_4` or `unknown` |
| `passability` | `unknown` in the pilot; not inferred from the class |
| `surface` | DRA `ROAD_SURFACE` |
| `road_class` | DRA `ROAD_CLASS` |
| `source_feature_id` | DRA `DIGITAL_ROAD_ATLAS_LINE_ID` |
| `alsroads_class` | Numeric source `CLASS` |
| `state_score` | ALSroads `SCORE` (0–100) |
| `road_width_m` | ALSroads `ROADWIDTH` |
| `drivable_width_m` | ALSroads `DRIVABLEWIDTH` |
| `percent_above_road` | ALSroads `PERCABOVEROAD` |
| `shoulders` | ALSroads `SHOULDERS` |
| `sinuosity` | ALSroads `SINUOSITY` |
| `conductivity` | ALSroads `CONDUCTIVITY` |
| `geometry` | Corrected or source centerline, depending on ALSroads class |
| `source`, `source_date`, `retrieved_utc`, `crs`, `notes` | Provenance |

`class_1`…`class_4` are **not** silently translated to open/closed. ALSroads
already defines the state classes from its score; any operational label is a
separate management decision.

## Install

```bash
python -m pip install -e ".[dev]"

# R side (experimental, GPL-3)
Rscript -e 'remotes::install_github("r-lidar-lab/ALSroads")'
```

The R bridge also needs `lidR`, `sf`, `raster`, and the ALSroads dependencies.
The package creates a LAS spatial index (`.lax`) if one is missing.

## Run

```bash
fresh-road run \
  --las runtime/road_status/bc_092l055_3_4_3_xyes_8_utm9_20231031_20231031.laz \
  --dtm runtime/road_status/bc_092l055_3_4_3_xli1m_utm9_20231031_20231031.tif \
  --roads examples/tfl6_ledges/centerlines.gpkg \
  --out-gpkg examples/tfl6_ledges/alsroads_result.gpkg

fresh-road ingest \
  --gpkg examples/tfl6_ledges/alsroads_result.gpkg \
  --out-json examples/tfl6_ledges/road_status.json \
  --out-csv examples/tfl6_ledges/road_status.csv \
  --source-date 2023-10-31
```

The pilot data are in `examples/tfl6_ledges/`.

## TFL 6 pilot

Source:

- LidarBC OP24BMRS001 2023, 8 points/m², UTM 9N, CGVD2013.
- Tile `bc_092l055_3_4_3`.
- DRA roads, `WHSE_BASEMAPPING.DRA_DGTL_ROAD_ATLAS_MPAR_SP`, clipped to TFL 6.
- Five DRA segments in the tile; ALSroads processed four (one duplicate DRA
  feature id was collapsed before measurement).

Result:

| DRA segment | DRA surface | ALSroads class | score | width | drivable width | cover |
|---|---|---:|---:|---:|---:|---:|
| `1820758` | loose | 1 | 75.0 | 7.0 m | 7.0 m | 0.2% |
| `1781964` | loose | 4 | 0.0 | 0.0 m | 0.0 m | 100% |
| `387113` | loose | 1 | 83.2 | 7.8 m | 6.9 m | 7.6% |
| `460555` | loose | 1 | 100.0 | 11.5 m | 11.2 m | 1.0% |

The `1781964` result is a real **class 4 / no traversable path** outcome, not a
missing row. It reports `ROADWIDTH = 0`, `CONDUCTIVITY = 0`, and 100% cover.

## Integration

The full TSA 23 route topology cleanup is documented in
[`docs/topology-cleanup.md`](docs/topology-cleanup.md). Noding/merging the DRA
linework and adding the public FSR road-section layer did not improve block
access; the remaining disconnected blocks are DRA/source topology gaps.

The current TFL 6 WS4 graph gap and the report-only crosswalk fixture are
documented in [`docs/tfl6-ws4-graph-gap.md`](docs/tfl6-ws4-graph-gap.md).

### WS4

The intended consumer is a WS4 road-status reader/report layer. It would join
`segment_id` to the existing road graph and report state/width next to cost and
volume. This package does not modify WS4.

The TFL 6 instance has DRA road vectors but no WS4 route-edge graph with
matching ids. TSA 23 has a stronger route test:
`examples/tsa23_mill_route/` uses 729 blocks, 18,314 edges, and the public
West Fraser 100 Mile House mill (`MILL_ID 95`) as a destination. 727/729 blocks
route to the mill; median route length is 6,550 m. Cost columns remain zero, so
this is route-length only, not an optimization input. A larger no-destination
topology fixture is also under `examples/tsa23_route/`.

### TSA 23 c5-style network

The planned WS4 road network is
[`examples/tsa23_c5_network/`](examples/tsa23_c5_network/). It includes:

- paved public DRA roads and active/pending FTEN resource roads;
- three operating 100 Mile House mill destinations;
- a 4 km potential grid clipped to the TSA 23 stand extent;
- four identical-geometry potential class variants per grid edge;
- build cost 0 on existing roads and c5 maintenance/haul coefficients.

Result: 465,263 segments, 72,299 vertices, one connected component, and all
102,128 blocks linked and routed. The potential grid is the c5-style 600 m
lattice with one diagonal per cell, not a 4 km lattice. The report-only WS4
route test in `examples/tsa23_c5_network/ws4_report/` gives a median 44.5 km
route to the nearest mill; the actual simulation pass in
`examples/tsa23_c5_network/ws4_sim/` routes all scheduled volume; the c5 network
is a single mill-connected component with 0 unrouted blocks. No WS4 objective or
solver code is changed.

See the example README and [`docs/cost-sources.md`](docs/cost-sources.md) for
the exact source and cost caveats.

### FHOPS

FHOPS could later use the same records as an access/status layer. That is
outside this pilot; the contract can be shared without making FHOPS depend on
R or ALSroads.

### FEMIC and DEC-04

The contract is currently package-local (`fresh.road.status.v1`). Promotion to
`femic.road.status.v1` would be a separate contract decision with a model card
and validation. No FEMIC growth or objective logic is changed here.

## Caveats

- One TFL 6 tile and four segments is a pilot, not a validation.
- ALSroads is experimental; its classes are source-defined and not a legal
  access determination.
- DRA attribution and centerline errors remain.
- No passability or open/closed mapping is applied.
- The point-cloud tile is public but large; LAZ bytes stay under `runtime/` and
  are not committed.
- `class_4` may mean “no traversable path” or a failed relocation; investigate
  per segment before using it operationally.

## References

- Roussel, J.-R., Bourdon, J.-F., Morley, I. D., Coops, N. C., & Achim, A.
  (2022). Correction, update, and enhancement of vectorial forestry road maps
  using ALS data, a pathfinder, and seven metrics. *International Journal of
  Applied Earth Observation and Geoinformation*, 114, 103020.
  https://doi.org/10.1016/j.jag.2022.103020
- ALSroads: https://github.com/r-lidar-lab/ALSroads
- LidarBC Open LiDAR Data Portal:
  https://lidar.gov.bc.ca/pages/download-discovery
- BC Digital Road Atlas:
  https://catalogue.data.gov.bc.ca/dataset/digital-road-atlas-dra-master-partially-attributed-roads

## Licence

Apache-2.0 for this package. ALSroads is a separate GPL-3 dependency and is not
redistributed here.
