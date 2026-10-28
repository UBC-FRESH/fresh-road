# TFL 6 Ledge Point road-status pilot

This is the first real-data INV-09 pilot: one LidarBC point-cloud tile, one
LidarBC 1 m DEM tile, and four unique DRA road segments in TFL 6.

It exercises the published `ALSroads` implementation and the
`fresh.road.status.v1` contract. It does **not** validate the classes against
field observations, and it does not change the WS4 road network or optimizer.

A second acquisition of the same tile (2019) is included as a
**repeat-acquisition consistency check**, not as independent ground truth.

## Source data

- Point cloud: `bc_092l055_3_4_3_xyes_8_utm9_20231031_20231031.laz`
  - LidarBC OP24BMRS001, 2023, 8 points/m², UTM 9N, CGVD2013
  - https://nrs.objectstore.gov.bc.ca/gdwuts/092/092l/2023/pointcloud/bc_092l055_3_4_3_xyes_8_utm9_20231031_20231031.laz
- DEM: `bc_092l055_3_4_3_xli1m_utm9_20231031_20231031.tif`
  - LidarBC 1 m DEM
  - https://nrs.objectstore.gov.bc.ca/gdwuts/092/092l/2023/dem/bc_092l055_3_4_3_xli1m_utm9_20231031_20231031.tif
- Roads: BC Digital Road Atlas, TFL 6 extract
  - `femic/external/femic-tfl6-instance/data/source/tfl_6/roads/dra_roads_tfl6.gpkg`
- ALSroads: 0.2.0
  - https://github.com/r-lidar-lab/ALSroads

The LAZ and DEM bytes are large and remain under `runtime/`; they are not
committed. `centerlines.gpkg` contains the four unique DRA segments used.

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

# 2019 repeat acquisition
fresh-road run \
  --las runtime/road_status_2019/bc_092l055_3_4_3_xyes_8_utm10_2019.laz \
  --dtm runtime/road_status_2019/bc_092l055_xl1m_utm10_2019.tif \
  --roads examples/tfl6_ledges/centerlines.gpkg \
  --out-gpkg examples/tfl6_ledges/alsroads_result_2019.gpkg

fresh-road ingest \
  --gpkg examples/tfl6_ledges/alsroads_result_2019.gpkg \
  --out-json examples/tfl6_ledges/road_status_2019.json \
  --out-csv examples/tfl6_ledges/road_status_2019.csv \
  --source-date 2019
```

## Results

| Segment | DRA surface | ALSroads class | Score | Width | Drivable width | Cover |
|---|---|---:|---:|---:|---:|---:|
| `dra:1820758` | loose | 1 | 75.0 | 7.0 m | 7.0 m | 0.2% |
| `dra:1781964` | loose | 4 | 0.0 | 0.0 m | 0.0 m | 100% |
| `dra:387113` | loose | 1 | 83.2 | 7.8 m | 6.9 m | 7.6% |
| `dra:460555` | loose | 1 | 100.0 | 11.5 m | 11.2 m | 1.0% |

`dra:1781964` is the interesting negative result: ALSroads returned class 4,
zero conductivity, zero width, and 100% cover, with the message that it could
not travel to the end of the road. That means “no traversable path under the
reference centerline” for this run; it is not a missing feature.

## Repeat-acquisition consistency

| Segment | 2019 class / score / width | 2023 class / score / width |
|---|---|---|
| `1820758` | 1 / 78.4 / 14.3 m | 1 / 75.0 / 7.0 m |
| `1781964` | 4 / 0.0 / 0.0 m | 4 / 0.0 / 0.0 m |
| `387113` | 1 / 84.0 / 7.8 m | 1 / 83.2 / 7.8 m |
| `460555` | 1 / 75.0 / 8.2 m | 1 / 100.0 / 11.5 m |

Class is stable for 4/4 segments across the two acquisitions. Width and score
are not stable for `1820758` and `460555`; these numbers should not be treated as
fixed asset attributes without an independent measurement.

## What is not claimed

- No field validation of class or width.
- No conversion from `class_4` to an operational “closed” label.
- No import into the WS4 road graph yet.
- No effect on WS4/FHOPS routing, cost, objective, or constraints.
- One tile and four segments are not a road-network accuracy estimate.

The next steps are a second tile with an independent status observation,
then a WS4 report-only join from `segment_id` to the existing road graph.
