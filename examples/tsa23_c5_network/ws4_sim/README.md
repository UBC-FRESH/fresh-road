# TSA 23 WS4 simulation comparison

This directory contains an actual WS4 simulation pass, not just routing.  The
same compiled TSA 23 dataset and schedule are run three ways:

1. **No-road**: no route model and no route accounts.
2. **DRA route fixture**: the existing DRA-only graph.
3. **c5 network**: the 600 m c5-style lattice with the three 100 Mile House
   mills and c5 costs.

The simulation uses `schedule_baseline.csv` (2,000 scheduled blocks) and five
years.  No WS4 objective, constraint, growth, or solver code is changed.

## Run

```bash
cd fresh-road
bash examples/tsa23_c5_network/ws4_sim/run_sim.sh
```

The script writes `run_base/`, `run_dra/`, `run_c5/`, and `comparison.json`.

## Result

| Metric | No-road | DRA | c5 |
|---|---:|---:|---:|
| Routed ledger volume | no route accounts | 5,090,935 | 5,280,492 |
| Unrouted ledger volume | — | 189,557 | 0 |
| Unrouted blocks | — | 36 | 0 |
| Average haul distance | — | 129.63 km | 44.66 km |
| Build expense | — | 0 | 28,984,941 CAD |
| Haul expense | — | 0 | 21,671,047 CAD |
| Maintenance expense | — | 0 | 11,725,917 CAD |
| Total route expense | — | 0 | 62,381,906 CAD |

The no-road and routed runs have **identical product account values** for every
common account.  Route accounts are additive only.

The DRA fixture is route-length-only, so its zero build/haul/maintenance costs
are not a cost baseline.  It also leaves 36 scheduled blocks / 189,557 ledger
volume unrouted.  This is **not** true isolation: every one of the 36 is linked
to a DRA vertex 37–1,823 m away (median 405 m), and all 36 route on the c5
network (median 48.4 km).  They cover 512 ha and are in the compiled managed
forest schedule; the DRA graph simply has disconnected source components.  Do not use the DRA-only
fixture as the access baseline, and do not paper over the gap with artificial
connectors.  The block-level explanation is in `dra_unrouted_blocks.csv`.

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

- `route_dra.yaml` — DRA route configuration used for the comparison.
- `dra_unrouted_blocks.csv` — the 36 DRA-only no-route blocks, their DRA
  access distance, and their c5 route length/destination.
- `run_base/`, `run_dra/`, `run_c5/` — WS4 simulation outputs.
- `comparison.json` — machine-readable summary.
- `build_comparison.py` — regenerates `comparison.json`.
