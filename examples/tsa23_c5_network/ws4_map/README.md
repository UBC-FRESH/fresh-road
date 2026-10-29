# WS4 web map layers

Generated inspection layers for the TSA 23 c5 network.  The GeoJSON files are
large local artifacts and are ignored by git.

```bash
ws4 serve \
  --dataset /srv/shared-data/gep/iversen-jamie-msc-thesis/femic-tsa23-instance/runtime/ws4/compiled \
  --runs examples/tsa23_c5_network/ws4_sim \
  --geometry examples/tsa23_c5_network/ws4_map/blocks_scheduled.geojson \
  --roads examples/tsa23_c5_network/ws4_map/roads_map.geojson \
  --crs EPSG:3005 \
  --host 127.0.0.1 --port 8042
```

`blocks_scheduled.geojson` is the 2,000-block schedule layer; using polygons avoids
the 102,128-point clutter.  `roads_map.geojson` contains the existing road network
plus the c5 routes used by the simulation.  The disconnected DRA-only orphan
components have been discarded; they are not part of the c5 planned network.
