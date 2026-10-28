"""Road-status record contract for the FRESH ecosystem.

This is the proposed ``fresh.road.status.v1`` record. It keeps the source
ALSroads state class separate from an interpretation such as "open" or
"decommissioned"; the latter is a management decision, not an ALS measurement.
"""

from __future__ import annotations

import copy
import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

SCHEMA_VERSION = "fresh.road.status.v1"
STATUS_VALUES = frozenset(
    {"class_1", "class_2", "class_3", "class_4", "unknown"}
)
PASSABILITY_VALUES = frozenset({"unknown", "open", "restricted", "blocked"})
REQUIRED_FIELDS = (
    "schema_version",
    "segment_id",
    "status",
    "passability",
    "source",
    "source_date",
    "retrieved_utc",
    "geometry",
    "crs",
)
OPTIONAL_FIELDS = (
    "surface",
    "road_class",
    "source_feature_id",
    "alsroads_class",
    "state_score",
    "road_width_m",
    "drivable_width_m",
    "percent_above_road",
    "shoulders",
    "sinuosity",
    "conductivity",
    "notes",
)
ALLOWED_FIELDS = frozenset(REQUIRED_FIELDS + OPTIONAL_FIELDS)


class RoadStatusError(ValueError):
    """Raised when a road-status record violates the contract."""


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RoadStatusError(f"{field} must be a non-empty string")
    return value.strip()


def _number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RoadStatusError(f"{field} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise RoadStatusError(f"{field} must be finite")
    return number


def _timestamp(value: object, field: str) -> str:
    text = _text(value, field)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise RoadStatusError(f"{field} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise RoadStatusError(f"{field} must include a timezone")
    return text


def _geometry(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise RoadStatusError("geometry must be a GeoJSON mapping")
    geometry_type = _text(value.get("type"), "geometry.type")
    if geometry_type not in {"LineString", "MultiLineString"}:
        raise RoadStatusError("geometry.type must be LineString or MultiLineString")
    coordinates = value.get("coordinates")
    if not isinstance(coordinates, list) or not coordinates:
        raise RoadStatusError("geometry.coordinates must be a non-empty list")
    return dict(value)


def road_status_schema() -> dict[str, object]:
    """Return a JSON-schema-like description of a road-status record."""
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://femic.ubc.ca/schemas/road-status.v1.json",
        "title": "FRESH road.status.v1 record",
        "type": "object",
        "additionalProperties": False,
        "required": list(REQUIRED_FIELDS),
        "properties": {
            "schema_version": {"const": SCHEMA_VERSION},
            "segment_id": {"type": "string", "minLength": 1},
            "status": {"type": "string", "enum": sorted(STATUS_VALUES)},
            "passability": {"type": "string", "enum": sorted(PASSABILITY_VALUES)},
            "surface": {"type": ["string", "null"]},
            "road_class": {"type": ["string", "null"]},
            "source_feature_id": {"type": ["integer", "string", "null"]},
            "alsroads_class": {"type": ["integer", "null"]},
            "state_score": {"type": ["number", "null"]},
            "road_width_m": {"type": ["number", "null"]},
            "drivable_width_m": {"type": ["number", "null"]},
            "percent_above_road": {"type": ["number", "null"]},
            "shoulders": {"type": ["number", "null"]},
            "sinuosity": {"type": ["number", "null"]},
            "conductivity": {"type": ["number", "null"]},
            "source": {"type": "string", "minLength": 1},
            "source_date": {"type": "string"},
            "retrieved_utc": {"type": "string", "format": "date-time"},
            "geometry": {"type": "object"},
            "crs": {"type": "string", "minLength": 1},
            "notes": {"type": ["string", "null"]},
        },
    }


def validate_road_status(record: Mapping[str, object]) -> None:
    """Validate one road-status record.

    Raises
    ------
    RoadStatusError
        If fields are missing, unknown, malformed, or outside the allowed
        domain.
    """
    if not isinstance(record, Mapping):
        raise RoadStatusError("road status must be a mapping")
    unknown = set(record) - ALLOWED_FIELDS
    if unknown:
        raise RoadStatusError(f"unknown road-status fields: {sorted(unknown)}")
    missing = [field for field in REQUIRED_FIELDS if field not in record]
    if missing:
        raise RoadStatusError(f"missing road-status fields: {', '.join(missing)}")
    if record["schema_version"] != SCHEMA_VERSION:
        raise RoadStatusError(f"schema_version must be {SCHEMA_VERSION}")
    _text(record["segment_id"], "segment_id")
    status = _text(record["status"], "status")
    if status not in STATUS_VALUES:
        raise RoadStatusError(f"status must be one of: {sorted(STATUS_VALUES)}")
    passability = _text(record["passability"], "passability")
    if passability not in PASSABILITY_VALUES:
        raise RoadStatusError(
            f"passability must be one of: {sorted(PASSABILITY_VALUES)}"
        )
    _text(record["source"], "source")
    _text(record["source_date"], "source_date")
    _timestamp(record["retrieved_utc"], "retrieved_utc")
    _geometry(record["geometry"])
    _text(record["crs"], "crs")
    for field in (
        "state_score",
        "road_width_m",
        "drivable_width_m",
        "percent_above_road",
        "shoulders",
        "sinuosity",
        "conductivity",
    ):
        value = record.get(field)
        if value is not None:
            _number(value, field)
    alsroads_class = record.get("alsroads_class")
    if alsroads_class is not None and (
        isinstance(alsroads_class, bool) or not isinstance(alsroads_class, int)
    ):
        raise RoadStatusError("alsroads_class must be an integer or null")


@dataclass(frozen=True)
class RoadStatus:
    """One road segment with source-preserving road-state metrics."""

    segment_id: str
    status: str
    passability: str
    source: str
    source_date: str
    retrieved_utc: str
    geometry: dict[str, Any]
    crs: str
    surface: str | None = None
    road_class: str | None = None
    source_feature_id: int | str | None = None
    alsroads_class: int | None = None
    state_score: float | None = None
    road_width_m: float | None = None
    drivable_width_m: float | None = None
    percent_above_road: float | None = None
    shoulders: float | None = None
    sinuosity: float | None = None
    conductivity: float | None = None
    notes: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Return the full contract record."""
        payload: dict[str, object] = {
            "schema_version": SCHEMA_VERSION,
            "segment_id": self.segment_id,
            "status": self.status,
            "passability": self.passability,
            "source": self.source,
            "source_date": self.source_date,
            "retrieved_utc": self.retrieved_utc,
            "geometry": self.geometry,
            "crs": self.crs,
            "surface": self.surface,
            "road_class": self.road_class,
            "source_feature_id": self.source_feature_id,
            "alsroads_class": self.alsroads_class,
            "state_score": self.state_score,
            "road_width_m": self.road_width_m,
            "drivable_width_m": self.drivable_width_m,
            "percent_above_road": self.percent_above_road,
            "shoulders": self.shoulders,
            "sinuosity": self.sinuosity,
            "conductivity": self.conductivity,
            "notes": self.notes,
        }
        validate_road_status(payload)
        return payload


def status_from_alsroads_class(value: object) -> str:
    """Map the source ALSroads class to a contract status token.

    The mapping is intentionally literal: ``1`` becomes ``class_1``. It does
    not turn a class into an operational open/closed label.
    """
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "unknown"
    try:
        class_number = int(float(str(value)))
    except (TypeError, ValueError):
        return "unknown"
    if class_number in {1, 2, 3, 4}:
        return f"class_{class_number}"
    return "unknown"


def schema_copy() -> dict[str, object]:
    """Return a defensive copy of the schema."""
    return copy.deepcopy(road_status_schema())
