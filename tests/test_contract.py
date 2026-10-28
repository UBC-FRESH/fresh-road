"""Tests for the road-status contract and ALSroads ingestion."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import LineString

from fresh_road.alsroads import records_from_alsroads
from fresh_road.contract import (
    RoadStatus,
    RoadStatusError,
    status_from_alsroads_class,
    validate_road_status,
)


def _record() -> dict[str, object]:
    return RoadStatus(
        segment_id="dra:123",
        status="class_1",
        passability="unknown",
        source="ALSroads test",
        source_date="2023-10-31",
        retrieved_utc="2026-10-28T00:00:00+00:00",
        geometry={"type": "LineString", "coordinates": [[0, 0], [10, 0]]},
        crs="EPSG:3005",
        surface="loose",
        road_class="resource",
        source_feature_id=123,
        alsroads_class=1,
        state_score=75.0,
        road_width_m=7.0,
        drivable_width_m=7.0,
        percent_above_road=0.2,
        shoulders=20.0,
        sinuosity=1.0,
        conductivity=0.88,
        notes="test",
    ).to_dict()


def test_status_mapping_is_literal() -> None:
    """ALSroads classes stay source-native and are not operational labels."""
    assert status_from_alsroads_class(1) == "class_1"
    assert status_from_alsroads_class(4) == "class_4"
    assert status_from_alsroads_class(0) == "unknown"
    assert status_from_alsroads_class(None) == "unknown"


def test_contract_accepts_valid_record() -> None:
    """A complete source-preserving record validates."""
    validate_road_status(_record())


def test_contract_rejects_bad_status() -> None:
    """Unknown status tokens are rejected."""
    record = _record()
    record["status"] = "open"
    with pytest.raises(RoadStatusError, match="status must be one of"):
        validate_road_status(record)


def test_ingest_alsroads_gpkg(tmp_path: Path) -> None:
    """ALSroads columns become a road.status record."""
    path = tmp_path / "alsroads.gpkg"
    frame = gpd.GeoDataFrame(
        {
            "DIGITAL_ROAD_ATLAS_LINE_ID": [123],
            "ROAD_SURFACE": ["loose"],
            "ROAD_CLASS": ["resource"],
            "ROADWIDTH": [7.0],
            "DRIVABLEWIDTH": [6.8],
            "PERCABOVEROAD": [1.0],
            "SHOULDERS": [20.0],
            "SINUOSITY": [1.01],
            "CONDUCTIVITY": [0.88],
            "SCORE": [75.0],
            "CLASS": [1],
        },
        geometry=[LineString([(0, 0), (10, 0)])],
        crs="EPSG:3005",
    )
    frame.to_file(path, driver="GPKG")
    records = records_from_alsroads(path)
    assert len(records) == 1
    assert records[0]["segment_id"] == "dra:123"
    assert records[0]["status"] == "class_1"
    assert records[0]["surface"] == "loose"
    assert records[0]["road_width_m"] == 7.0
    assert records[0]["passability"] == "unknown"
