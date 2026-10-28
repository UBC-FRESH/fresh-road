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

Cost table from `HaulCost.xlsx`:

| Type | Construction CAD/km | Maintain CAD/km/period | Haul speed km/h | Haul CAD/m3/km |
|---|---:|---:|---:|---:|
| H | 0 | 0 | 90 | 0.06 |
| P | 0 | 2000 | 54 | 0.10 |
| S | 0 | 2000 | 33.75 | 0.16 |
| T | 0 | 2000 | 20 | 0.27 |
| N | 5000 | 500 | 21.17 | 0.255078 |

The c5 sample has one new-road type (`N`) and four existing-road types
(`H/P/S/T`). It does **not** contain four independently sourced potential-road
classes.

## Mapping decision

- Existing roads: build cost **0**.
- Existing road maintenance/haul: c5 `H/P/S/T` values by source road class.
- Potential grid roads: use the c5 `N` construction/maintenance/haul
  coefficients, not invented values.
- If four class-1/2/3/4 potential variants are required, the class mapping
  must be supplied explicitly or derived from a published BC source. The c5
  sample alone cannot justify four different new-road cost sets.

## TSA 23 data still needed

- supply block for IAM road group (4 vs 8)
- slope percentage by segment
- BEC zone/subzone flags
- long-term vs short-term road flag
- RMG L vs M
- road permit / resource-road status for existing roads

These are data joins, not model invention. Do not replace them with guesses.
