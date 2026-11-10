"""Fetch an auditable *modern* NHD reference flowline slice for the Hudson pilot.

This module never reconstructs waterways in 1609. It does not infer river
connectivity after clipping, and it does not silently discard canal/ditch or
artificial path classes present in the published NHD service.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from shapely.geometry import box, mapping, shape

from .geo import sha256_file, validate_bbox

SERVICE = "https://gisservices.its.ny.gov/arcgis/rest/services/NYS_Hydrography/MapServer/15/query"
FIELDS = "OBJECTID,Permanent_Identifier,GNIS_Name,ReachCode,FType,FCode,FlowDir,InNetwork"
MAX_FEATURES = 50000
BATCH_SIZE = 100


def _request(params: dict[str, str], *, get_json=None) -> dict:
    """Call ArcGIS REST with an injectable JSON reader for offline tests."""
    url = SERVICE + "?" + urlencode(params)
    if get_json is None:
        def get_json(u: str):
            with urlopen(Request(u, headers={"User-Agent": "NorthAmerica1609-research/0.1"}), timeout=90) as res:
                return json.load(res)
    response = get_json(url)
    if not isinstance(response, dict) or "error" in response:
        raise ValueError(f"NHD service error: {response.get('error') if isinstance(response, dict) else response}")
    return response


def _query_ids(bbox: tuple[float, float, float, float], *, get_json=None) -> list[int]:
    params = {
        "f": "json", "where": "1=1", "geometry": ",".join(map(str, bbox)),
        "geometryType": "esriGeometryEnvelope", "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects", "returnIdsOnly": "true",
    }
    obj = _request(params, get_json=get_json)
    ids = obj.get("objectIds")
    if not isinstance(ids, list):
        raise ValueError("NHD service did not return an objectIds list")
    if len(ids) != len(set(ids)) or any(type(x) is not int for x in ids):
        raise ValueError("NHD service returned duplicate or invalid object IDs")
    if len(ids) > MAX_FEATURES:
        raise ValueError("NHD query exceeds pilot safety limit of 50,000 features")
    return sorted(ids)


def _query_features(ids: list[int], *, get_json=None) -> list[dict]:
    features = []
    for offset in range(0, len(ids), BATCH_SIZE):
        chunk = ids[offset:offset + BATCH_SIZE]
        params = {
            "f": "geojson", "objectIds": ",".join(map(str, chunk)),
            "outFields": FIELDS, "returnGeometry": "true", "outSR": "4326",
        }
        obj = _request(params, get_json=get_json)
        if obj.get("type") != "FeatureCollection" or not isinstance(obj.get("features"), list):
            raise ValueError("NHD service returned invalid GeoJSON feature collection")
        features.extend(obj["features"])
    return features


def _atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".partial")
    try:
        temp.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def _geometry_2d(geometry: dict) -> tuple[dict, bool]:
    """Drop measured/elevation ordinates for 2D clipping; keep raw source intact."""
    kind = geometry.get("type")
    if kind not in ("LineString", "MultiLineString"):
        raise ValueError("NHD flowline must be linear geometry")
    changed = False

    def line(points):
        nonlocal changed
        output = []
        for point in points:
            if not isinstance(point, (list, tuple)) or len(point) < 2 or len(point) > 4:
                raise ValueError("NHD coordinate must have 2-4 ordinates")
            changed = changed or len(point) != 2
            output.append(point[:2])
        return output

    c = geometry.get("coordinates")
    if not isinstance(c, list):
        raise ValueError("NHD geometry lacks coordinate array")
    coords = line(c) if kind == "LineString" else [line(part) for part in c]
    return {"type": kind, "coordinates": coords}, changed


def create_modern_flowlines(region: dict, raw_path: Path, output: Path, *, get_json=None) -> dict:
    """Preserve uncut NHD features and write a derived clipped-only reference."""
    bbox = validate_bbox(region["bbox_wgs84"])
    if raw_path == output:
        raise ValueError("raw and derived paths must be different")
    ids = _query_ids(bbox, get_json=get_json)
    if not ids:
        raise ValueError("NHD returned no flowlines in research extent")
    raw = _query_features(ids, get_json=get_json)
    actual = []
    for feat in raw:
        fid = feat.get("properties", {}).get("OBJECTID")
        if type(fid) is not int:
            raise ValueError("NHD feature missing integer OBJECTID")
        actual.append(fid)
    if len(actual) != len(set(actual)) or set(actual) != set(ids):
        raise ValueError("NHD returned missing, extra or duplicate features")
    raw.sort(key=lambda feat: feat["properties"]["OBJECTID"])
    bounds = box(*bbox)
    derived_features = []
    clipped_count = 0
    fcodes = {}
    dimensionality_reduced = 0
    for feat in raw:
        geometry = feat.get("geometry")
        if not geometry:
            raise ValueError("NHD flowline missing geometry")
        simplified_geometry, had_extra_ordinates = _geometry_2d(geometry)
        dimensionality_reduced += int(had_extra_ordinates)
        original = shape(simplified_geometry)
        if original.is_empty or not original.is_valid or original.geom_type not in ("LineString", "MultiLineString"):
            raise ValueError("NHD supplied invalid or non-linear flowline geometry")
        if not original.intersects(bounds):
            raise ValueError("NHD returned an out-of-region feature in the requested ID set")
        clipped = original.intersection(bounds)
        if clipped.is_empty or clipped.geom_type not in ("LineString", "MultiLineString"):
            continue
        cut = not clipped.equals(original)
        clipped_count += int(cut)
        props = dict(feat["properties"])
        props["source_feature_id"] = str(props["OBJECTID"])
        props["clipped_to_pilot_bbox"] = cut
        props["dataset_role"] = "modern_reference_only"
        fcode = str(props.get("FCode"))
        fcodes[fcode] = fcodes.get(fcode, 0) + 1
        derived_features.append({"type": "Feature", "geometry": mapping(clipped), "properties": props})
    if not derived_features:
        raise ValueError("no linear flowline segments fall inside bbox")
    raw_collection = {"type": "FeatureCollection", "features": raw}
    derived_collection = {"type": "FeatureCollection", "features": derived_features}
    _atomic_json(raw_path, raw_collection)
    _atomic_json(output, derived_collection)
    manifest = {
        "schema_version": 1,
        "region_id": region["id"],
        "historical_target_year": region["target_year"],
        "layer": "flowlines",
        "role": "modern_reference_only",
        "is_1609_reconstruction": False,
        "crs": "OGC:CRS84 (GeoJSON longitude, latitude)",
        "requested_bbox_wgs84": list(bbox),
        "source_id": "nys_nhd_flowlines_2020",
        "source_url": SERVICE.rsplit("/query", 1)[0],
        "source_credits": "U.S. Geological Survey; New York State GIS Program Office",
        "raw_feature_count": len(raw),
        "derived_feature_count": len(derived_features),
        "bbox_truncated_features": clipped_count,
        "features_reduced_to_xy": dimensionality_reduced,
        "fcode_counts": dict(sorted(fcodes.items())),
        "source_object_ids_sha256": hashlib.sha256(json.dumps(ids).encode()).hexdigest(),
        "raw_file": raw_path.name,
        "raw_sha256": sha256_file(raw_path),
        "output_file": output.name,
        "output_sha256": sha256_file(output),
        "limitations": [
            "Modern NHD reference, not an observed or reconstructed 1609 waterway.",
            "NYS service only covers New York State, not the New Jersey portion of the pilot.",
            "The flowline layer includes artificial paths, conduits, canals and coastline classes, not only natural rivers.",
            "Clipping can truncate network reaches at the bbox; adjacency/direction cannot be inferred from clipped endpoints.",
            "Extra Z/M coordinate ordinates are preserved in raw source and removed from 2D derived geometries.",
            "No waterbody polygons, historical wetlands, or validated 1609 shoreline are included.",
        ],
    }
    _atomic_json(output.with_suffix(".manifest.json"), manifest)
    return manifest
