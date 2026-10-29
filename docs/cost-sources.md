# BC road cost sources

This file records the public sources used for the WS4 road-network build. It is
intentionally explicit about what comes from where; no class-1/2/3/4
coefficient is invented.

## BC Interior Appraisal Manual 2024

Source:
https://www2.gov.bc.ca/assets/gov/farming-natural-resources-and-industry/forestry/timber-pricing/interior-timber-pricing/interior-appraisal-manual/iam_2024_master_b.pdf

Relevant sections:

- **4.3.2.3 Subgrade Construction Cost Equations** — new-road subgrade cost in
  dollars per kilometre, by road group.
- **Table 4-2: Road Groups** — maps TSA/TFL/supply-block geography to a road
  group.
- **4.3.2.5 Snow and Ice Roads** — $7,678/km.
- **Table 4-5: Road Maintenance Cost Estimates** — road maintenance in dollars
  per cubic metre, by Road Management Group (RMG).

The subgrade equations are:

```text
Group 2: 8,385 + 7.462*SLOPE%^2 + 5,487*ICH_CWH + 9,665*LT
Group 3: 13,654 + 175*SLOPE%*LT + 2,075*ESSF
Group 4: 9,234 + 214*SLOPE% + 140*SLOPE%*LT
Group 5: 7,929 + 261*SLOPE%*LT + 2,076*SBS + 2,361*WET
Group 6: 11,507 + 5,829*LT
Group 7: 5,227 + 103*SLOPE% + 3,211*LT + 5,902*ESSF + 6,338*SBS
Group 8: 6,689 + 5.889*SLOPE%^2 + 7,136*LT + 4,228*ESSF
Group 9: 17,770 + 7.745*SLOPE%^2 + 9,316*LT - 151*ICH - 4,853*IDF
Group 10: 8,734 + 6.962*SLOPE%^2 + 2,987*ESSF + 6,132*LT
Group 11: 14,070 + 398*SLOPE% + 20,389*LT
Group 12: 12,862 + 5.897*SLOPE%^2 + 10,008*ESSF + 7,273*ICH + 10,712*LT
```

`LT=1` for a long-term road; `SLOPE%`, BEC flags, and `WET` are defined in
IAM §4.3.2.2.

TSA 23 is the **100 Mile House TSA**. IAM Table 4-2 puts it in road group 4 or
8 depending on supply block. IAM Table 4-5 puts it in RMG L or M. The exact
supply block and BEC/slope attributes must come from the TSA 23 inventory; do
not guess them.

## Patchworks c5 sample

Source:
`/srv/shared-data/gep/ws4/tmp/sample_2025/sample_2025/roads/`

- `HaulCost.xlsx`
- `access.shp` (`RDTYPE`, `BUILD_KM`, `MAINT_KM`, `HAUL_MKM`)
- `segments.csv`, `vertices.csv`, `destinations.csv`, `linkages.csv`

Cost table used by the build (c5 sample fields):

| Type | Construction CAD/km | Maintain CAD/km/period | Haul speed km/h | Haul CAD/m³/km |
|---|---:|---:|---:|---:|
| H | 0 | 0 | 90 | 0.06 |
| P | 0 | 2000 | 54 | 0.10 |
| S | 0 | 2000 | 33.75 | 0.16 |
| T | 0 | 2000 | 20 | 0.32 |
| N | 5000 | 500 | 21.17 | 0.255078 |

The c5 `HaulCost.xlsx` workbook gives T haul as 0.27, but the delivered c5
`access.shp`/`segments.csv` fields use **0.32**.  This build uses the delivered
field value, which is what the c5 route fixture carries.

The c5 sample has one new-road type (`N`) and four existing-road types
(`H/P/S/T`). It does **not** contain four independently sourced potential-road
classes.

## Implemented mapping

- Existing roads: build cost **0**.
- Existing paved DRA roads: `H/P/S` from `ROAD_CLASS`; FTEN resource roads:
  `S` for Forest Service Roads, `T` for Road Permits.
- Potential grid roads: every edge is emitted once per class.  All four classes
  use the c5 `N` construction coefficient; maintenance/haul come from the c5
  `P/S/T/N` rows:

| Potential class | Build CAD/km | Maintain CAD/km/period | Haul CAD/m³/km |
|---|---:|---:|---:|
| class_1 | 5000 | 2000 | 0.10 |
| class_2 | 5000 | 2000 | 0.16 |
| class_3 | 5000 | 2000 | 0.32 |
| class_4 | 5000 | 500 | 0.255078 |

The table lists per-kilometre coefficients.  WS4 stores total segment costs, so
each segment's `build_cost`, `maintain_cost`, and `haul_cost` are the per-km
coefficient multiplied by `length_m / 1000`.

The shared construction cost is an explicit source limitation.  The c5 sample
cannot justify four different new-road construction costs.  The four variants
are a service-class emulation, not four engineering cost standards.

## TSA 23 implementation status

The current c5-style network uses the c5 coefficients above and does **not**
apply the IAM subgrade equations.  The IAM source is recorded for a future
new-road costing layer; applying it needs segment slope, BEC flags, long-term
status, and the TSA 23 supply-block/RMG decision.  Those joins are not
invented in the current build.

Existing FTEN statuses used: `ACTIVE` and `PENDING`.  Retired road sections are
excluded.  The three 100 Mile House operating mills are within 5 km of the TSA
23 AOI; the seven Williams Lake operating mills are 25–36 km outside it and are
not TSA 23 destinations in this build.
