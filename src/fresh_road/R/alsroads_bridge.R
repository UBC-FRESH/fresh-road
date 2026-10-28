#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(lidR)
  library(sf)
  library(raster)
  library(ALSroads)
})

args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 4) {
  stop("usage: alsroads_bridge.R LAS DTM ROADS OUT_GPKG")
}
las_path <- args[[1]]
dtm_path <- args[[2]]
roads_path <- args[[3]]
out_path <- args[[4]]

options(ALSroads.debug.verbose = FALSE)
options(ALSroads.debug.progress = FALSE)

ctg <- readLAScatalog(las_path)
if (!lidR::is.indexed(ctg)) {
  message("creating LAS spatial index")
  lidR:::catalog_laxindex(ctg)
}
dtm <- raster(dtm_path)
roads <- st_read(roads_path, quiet = TRUE)
target_crs <- st_crs(ctg)
if (is.na(target_crs)) stop("could not determine LAS CRS")
roads <- st_transform(roads, target_crs)

out <- list()
for (index in seq_len(nrow(roads))) {
  road <- roads[index, ]
  geometry <- st_geometry(road)
  if (inherits(geometry, "sfc_MULTILINESTRING")) {
    geometry <- st_line_merge(geometry)
  }
  geometry <- st_cast(geometry, "LINESTRING")
  road <- st_sf(st_drop_geometry(road), geometry = geometry)
  message("processing road ", road$DIGITAL_ROAD_ATLAS_LINE_ID)
  result <- tryCatch(
    measure_road(ctg, road, dtm = dtm),
    error = function(error) {
      message("ALSroads error: ", conditionMessage(error))
      NULL
    }
  )
  if (!is.null(result)) {
    out[[length(out) + 1]] <- result
  }
}

if (length(out) == 0) {
  stop("ALSroads produced no results")
}
result <- do.call(rbind, out)
st_write(result, out_path, driver = "GPKG", delete_dsn = TRUE)
