# WS4 web map layers

Generated inspection layers for the TSA 23 c5 network.  The GeoJSON files are
large local artifacts and are ignored by git.

```bash
ws4 serve \
  --dataset /srv/shared-data/gep/iversen-jamie-msc-thesis/femic-tsa23-instance/runtime/ws4/compiled \
  --runs examples/tsa23_c5_network/ws4_sim \
  --geometry examples/tsa23_c5_network/ws4_map/blocks_points.geojson \
  --roads examples/tsa23_c5_network/ws4_map/roads_c5_full.geojson \
  --crs EPSG:3005 \
  --host 127.0.0.1 --port 8042
```

`blocks_points.geojson` is the 102,128-block centroid layer.  `roads_c5_full.geojson`
is the deduplicated c5 network (existing roads plus one potential-grid variant).
