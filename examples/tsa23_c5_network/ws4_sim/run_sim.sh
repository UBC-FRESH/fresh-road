#!/usr/bin/env bash
# Reproduce the TSA23 no-road / c5 WS4 simulation comparison.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATASET="${WS4_DATASET:-/srv/shared-data/gep/iversen-jamie-msc-thesis/femic-tsa23-instance/runtime/ws4/compiled}"
SCHEDULE="${WS4_SCHEDULE:-/srv/shared-data/gep/iversen-jamie-msc-thesis/femic-tsa23-instance/runtime/ws4/schedule_baseline.csv}"
YEARS="${WS4_YEARS:-5}"

rm -rf "$HERE/run_base" "$HERE/run_c5"
ws4 simulate --dataset "$DATASET" --schedule "$SCHEDULE" --years "$YEARS" \
  --out "$HERE/run_base"
ws4 simulate --dataset "$DATASET" --schedule "$SCHEDULE" --years "$YEARS" \
  --route-config "$HERE/../ws4_report/route.yaml" --out "$HERE/run_c5"
python3 "$HERE/build_comparison.py"
