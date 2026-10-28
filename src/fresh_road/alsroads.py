"""ALSroads bridge and road-status ingestion."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import CRS

from .contract import (
    SCHEMA_VERSION,
    RoadStatus,
    status_from_alsroads_class,
    validate_road_status,
)

DEFAULT_SOURCE = "ALSroads 0.2.0 + LidarBC OP24BMRS001 + BC DRA"
DEFAULT_SOURCE_DATE = "2023-10-31"


class RoadError(RuntimeError):
    """Raised when an ALSroads run or ingest cannot complete."""


def _number_or_none(value: object) -> float | None:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    try:
        number = float(str(value))
    except (TypeError, ValueError):
        return None
    return number if np.isfinite(number) else None


def _int_or_none(value: object) -> int | None:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return None


def _text_or_none(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    if text.strip() in {"", "nan", "<NA>"}:
        return None
    return text


def records_from_alsroads(
    gpkg_path: Path,
    *,
    source: str = DEFAULT_SOURCE,
    source_date: str = DEFAULT_SOURCE_DATE,
    retrieved_utc: str | None = None,
    target_crs: str = "EPSG:3005",
) -> list[dict[str, object]]:
    """Convert an ALSroads result layer to ``fresh.road.status.v1`` records."""
    if not gpkg_path.exists():
        raise RoadError(f"ALSroads result does not exist: {gpkg_path}")
    frame = gpd.read_file(gpkg_path)
    if frame.empty:
        raise RoadError("ALSroads result has no features")
    if "DIGITAL_ROAD_ATLAS_LINE_ID" not in frame.columns:
        raise RoadError("ALSroads result is missing DIGITAL_ROAD_ATLAS_LINE_ID")
    if frame.crs is None:
        raise RoadError("ALSroads result has no CRS")
    frame = frame.to_crs(target_crs)
    timestamp = retrieved_utc or datetime.now(UTC).isoformat()
    records: list[dict[str, object]] = []
    for _, row in frame.iterrows():
        feature_id: int | str | None = _int_or_none(
            row.get("DIGITAL_ROAD_ATLAS_LINE_ID")
        )
        if feature_id is None:
            feature_id = _text_or_none(row.get("DIGITAL_ROAD_ATLAS_LINE_ID"))
        if feature_id is None:
            continue
        class_value = _int_or_none(row.get("CLASS"))
        geometry = json.loads(
            json.dumps(dict(row.geometry.__geo_interface__), default=float)
        )
        record = RoadStatus(
            segment_id=f"dra:{feature_id}",
            status=status_from_alsroads_class(class_value),
            passability="unknown",
            source=source,
            source_date=source_date,
            retrieved_utc=timestamp,
            geometry=dict(geometry),
            crs=CRS.from_user_input(target_crs).to_string(),
            surface=_text_or_none(row.get("ROAD_SURFACE")),
            road_class=_text_or_none(row.get("ROAD_CLASS")),
            source_feature_id=feature_id,
            alsroads_class=class_value,
            state_score=_number_or_none(row.get("SCORE")),
            road_width_m=_number_or_none(row.get("ROADWIDTH")),
            drivable_width_m=_number_or_none(row.get("DRIVABLEWIDTH")),
            percent_above_road=_number_or_none(row.get("PERCABOVEROAD")),
            shoulders=_number_or_none(row.get("SHOULDERS")),
            sinuosity=_number_or_none(row.get("SINUOSITY")),
            conductivity=_number_or_none(row.get("CONDUCTIVITY")),
            notes=(
                "ALSroads state class is source-preserving; passability is not "
                "inferred. DRA surface/class are source attributes."
            ),
        ).to_dict()
        validate_road_status(record)
        records.append(record)
    if not records:
        raise RoadError("no usable road records were found")
    return records


def write_road_status_json(path: Path, records: list[dict[str, object]]) -> None:
    """Write a road-status JSON table."""
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "records": records,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def write_road_status_csv(path: Path, records: list[dict[str, object]]) -> None:
    """Write a flat road-status CSV for inspection and joins."""
    path.parent.mkdir(parents=True, exist_ok=True)
    flat: list[dict[str, Any]] = []
    for record in records:
        item = dict(record)
        item["geometry"] = ""
        flat.append(item)
    frame = pd.DataFrame(flat)
    frame.to_csv(path, index=False)


def _rscript() -> str:
    path = shutil.which("Rscript")
    if path is None:
        raise RoadError("Rscript was not found")
    return path


def _r_env() -> dict[str, str]:
    environment = os.environ.copy()
    environment.setdefault("R_LIBS_USER", str(Path.home() / "R" / "library"))
    return environment


def alsroads_version() -> str:
    """Return the installed ALSroads version."""
    result = subprocess.run(
        [
            _rscript(),
            "--vanilla",
            "-e",
            'cat(as.character(packageVersion("ALSroads")))',
        ],
        check=False,
        capture_output=True,
        text=True,
        env=_r_env(),
    )
    if result.returncode != 0:
        raise RoadError(
            "ALSroads is not installed. Install it with "
            "`remotes::install_github(\"r-lidar-lab/ALSroads\")`. "
            f"R stderr: {result.stderr.strip()[:500]}"
        )
    return result.stdout.strip()


def run_alsroads(
    las_path: Path,
    dtm_path: Path,
    roads_path: Path,
    out_path: Path,
    *,
    r_libs_user: Path | None = None,
) -> dict[str, object]:
    """Run the reference ALSroads implementation through the bundled R bridge."""
    for path in (las_path, dtm_path, roads_path):
        if not path.exists():
            raise RoadError(f"missing ALSroads input: {path}")
    script = Path(__file__).with_name("R") / "alsroads_bridge.R"
    if not script.exists():
        raise RoadError(f"ALSroads bridge is missing: {script}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    environment = _r_env()
    if r_libs_user is not None:
        environment["R_LIBS_USER"] = str(r_libs_user)
    result = subprocess.run(
        [
            _rscript(),
            "--vanilla",
            str(script),
            str(las_path),
            str(dtm_path),
            str(roads_path),
            str(out_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    if result.returncode != 0:
        raise RoadError(
            "ALSroads bridge failed. "
            f"stdout: {result.stdout.strip()[:1000]} "
            f"stderr: {result.stderr.strip()[:1000]}"
        )
    return {
        "output": str(out_path),
        "alsroads_version": alsroads_version(),
        "stdout": result.stdout,
        "stderr": result.stderr,
    }
