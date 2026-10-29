# TSA 23 WS4 simulation

This directory contains an actual WS4 simulation pass, not just routing.  The
same compiled TSA 23 dataset and schedule are run two ways:

1. **No-road**: no route model and no route accounts.
2. **c5 network**: the 600 m c5-style lattice with the three 100 Mile House
   mills and c5 costs.

The simulation uses `schedule_baseline.csv` (2,000 scheduled blocks) and five
years.  No WS4 objective, constraint, growth, or solver code is changed.

The DRA-only orphan components are **not** part of the planned c5 network and
are no longer used as a baseline.

## Run

```bash
cd fresh-road
bash examples/tsa23_c5_network/ws4_sim/run_sim.sh
```

The script writes `run_base/`, `run_c5/`, and `comparison.json`.

## Result

| Metric | No-road | c5 |
|---|---:|---:|
| Routed ledger volume | no route accounts | 5,280,492 |
| Unrouted ledger volume | — | 0 |
| Unrouted blocks | — | 0 |
| Average haul distance | — | 44.66 km |
| Build expense | — | 28,984,941 CAD |
| Haul expense | — | 21,671,047 CAD |
| Maintenance expense | — | 11,725,917 CAD |
| Total route expense | — | 62,381,906 CAD |

The no-road and c5 runs have **identical product account values** for every
common account.  Route accounts are additive only.

The c5 route-cost report is:

| Account | CAD/m³ |
|---|---:|
| Average build | 5.489 |
| Average haul | 4.104 |
| Average maintenance | 2.221 |

The destination split is a least-haul assignment across the three mills; no
product eligibility or mill demand is modelled.  Ledger volume is the sum of
routed product rows, not merchantable volume.

## Files

- `run_base/`, `run_c5/` — WS4 simulation outputs.
- `comparison.json` — machine-readable summary.
- `build_comparison.py` — regenerates `comparison.json`.
