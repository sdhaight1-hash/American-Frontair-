"""Validate spatially explicit historical evidence; never invent features."""
from __future__ import annotations

import json
from pathlib import Path

from shapely.geometry import box, shape

from .geo import validate_bbox

VALID_KINDS = {"historic_map", "archaeology", "paleoenvironment", "document", "model", "inference"}
VALID_CONFIDENCE = {"high", "medium", "low", "unknown"}


def validate_features(path: Path, *, year: int, bbox: list[float]) -> dict:
    """Accept only documented, spatially valid features relevant to target year."""
    obj = json.loads(path.read_text(encoding="utf-8"))
    if obj.get("type") != "FeatureCollection" or not isinstance(obj.get("features"), list):
        raise ValueError("expected GeoJSON FeatureCollection")
    extent = box(*validate_bbox(bbox))
    seen = set()
    for index, feature in enumerate(obj["features"]):
        props = feature.get("properties", {})
        identifier = props.get("feature_id")
        if not isinstance(identifier, str) or not identifier.strip() or identifier in seen:
            raise ValueError(f"feature {index}: missing or duplicate feature_id")
        seen.add(identifier)
        period = props.get("valid_years")
        if not isinstance(period, list) or len(period) != 2 or not all(isinstance(n, int) and not isinstance(n, bool) for n in period):
            raise ValueError(f"feature {identifier}: valid_years must be [start_year, end_year]")
        if not period[0] <= year <= period[1]:
            raise ValueError(f"feature {identifier}: evidence period does not cover {year}")
        if props.get("basis") not in VALID_KINDS:
            raise ValueError(f"feature {identifier}: invalid historical basis")
        if props.get("confidence") not in VALID_CONFIDENCE:
            raise ValueError(f"feature {identifier}: missing confidence")
        evidence = props.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            raise ValueError(f"feature {identifier}: at least one evidence citation is required")
        for citation in evidence:
            if not isinstance(citation, dict) or not all(citation.get(k) for k in ("source_id", "locator")):
                raise ValueError(f"feature {identifier}: citation must have source_id and locator")
        if feature.get("type") != "Feature" or not feature.get("geometry"):
            raise ValueError(f"feature {identifier}: missing geometry")
        geometry = shape(feature["geometry"])
        if geometry.is_empty or not geometry.is_valid or not geometry.intersects(extent):
            raise ValueError(f"feature {identifier}: invalid, empty or out-of-region geometry")
    return {"target_year": year, "region_bbox": list(bbox), "feature_count": len(seen), "validated_ids": sorted(seen)}
