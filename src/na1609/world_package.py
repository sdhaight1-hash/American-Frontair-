"""Deterministic offline package for game/simulation consumers.

Current exporter creates *modern reference* data only. A complete 1609
initialization must never be inferred from a source's target_year field.
"""
from __future__ import annotations

import json
import math
import shutil
import struct
import tempfile
from pathlib import Path

import numpy as np
import rasterio

from .evidence import validate_features
from .geo import sha256_file, validate_bbox

SCHEMA = "na1609.reference-package.v1"


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def _verified_manifest(data_path: Path, expected_role: str, expected_layer: str, region: dict) -> dict:
    manifest_path = data_path.with_suffix(".manifest.json")
    source = json.loads(manifest_path.read_text(encoding="utf-8"))
    if source.get("role") != expected_role or source.get("is_1609_reconstruction") is not False:
        raise ValueError(f"not a verified modern reference: {data_path}")
    if source.get("layer") != expected_layer or source.get("region_id") != region["id"]:
        raise ValueError(f"source/region mismatch: {data_path}")
    if source.get("historical_target_year") != region["target_year"]:
        raise ValueError(f"target year mismatch: {data_path}")
    if list(source.get("requested_bbox_wgs84", [])) != list(region["bbox_wgs84"]):
        raise ValueError(f"source bounds mismatch: {data_path}")
    if sha256_file(data_path) != source.get("output_sha256"):
        raise ValueError(f"source SHA-256 mismatch: {data_path}")
    return source


def export_pilot(region: dict, terrain: Path, flowlines: Path, evidence: Path, output: Path) -> dict:
    """Export one offline region; never promote its modern data to historical state."""
    bbox = validate_bbox(region["bbox_wgs84"])
    dem_meta = _verified_manifest(terrain, "modern_reference_only", "terrain_elevation", region)
    water_meta = _verified_manifest(flowlines, "modern_reference_only", "flowlines", region)
    check = validate_features(evidence, year=region["target_year"], bbox=bbox)
    features = json.loads(evidence.read_text(encoding="utf-8"))["features"]
    source = json.loads(flowlines.read_text(encoding="utf-8"))
    if source.get("type") != "FeatureCollection" or not isinstance(source.get("features"), list):
        raise ValueError("flowlines must be a GeoJSON FeatureCollection")
    reaches = []
    seen = set()
    for feature in source["features"]:
        props = feature.get("properties", {})
        permanent_id = props.get("Permanent_Identifier")
        if not isinstance(permanent_id, (str, int)) or not str(permanent_id).strip():
            raise ValueError("flowline lacks permanent NHD identifier; cannot promise stable identity")
        stable_id = f"nhd:{permanent_id}"
        if stable_id in seen:
            raise ValueError(f"duplicate permanent flowline ID: {stable_id}")
        seen.add(stable_id)
        geometry = feature.get("geometry")
        if geometry is None or geometry.get("type") not in ("LineString", "MultiLineString"):
            raise ValueError("invalid flowline geometry")
        # The derived NHD importer has already validated and clipped geometry.
        # These bounds power an offline spatial prefilter; no topology is invented.
        coords = geometry["coordinates"]
        lines = [coords] if geometry["type"] == "LineString" else coords
        xy = [(p[0], p[1]) for line in lines for p in line]
        if not xy or not all(len(p) == 2 and all(math.isfinite(float(v)) for v in p) for p in xy):
            raise ValueError("invalid flowline coordinates")
        reaches.append({
            "id": stable_id,
            "geometry": geometry,
            "bbox_wgs84": [min(x for x, _ in xy), min(y for _, y in xy), max(x for x, _ in xy), max(y for _, y in xy)],
            "name": props.get("GNIS_Name"), "fcode": props.get("FCode"),
            "reach_code": props.get("ReachCode"), "source_object_id": props.get("OBJECTID"),
            "source_flowdir_code": props.get("FlowDir"),
            "clipped_to_region": props.get("clipped_to_pilot_bbox") is True,
            "topology": {"status": "unresolved", "upstream_ids": None, "downstream_ids": None,
                         "may_continue_outside_region": props.get("clipped_to_pilot_bbox") is True},
        })
    reaches.sort(key=lambda entry: entry["id"])

    output = Path(output)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite package: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix=".world-package-", dir=output.parent))
    try:
        with rasterio.open(terrain) as dem:
            if dem.crs is None or dem.crs.to_epsg() != 4326 or dem.count != 1:
                raise ValueError("terrain must be one-band EPSG:4326")
            t = dem.transform
            if t.b != 0 or t.d != 0 or t.a <= 0 or t.e >= 0:
                raise ValueError("pilot export supports north-up georeferenced terrain only")
            arr = dem.read(1).astype("<f4", copy=True)
            arr[~np.isfinite(arr)] = np.float32(np.nan)
            (temp / "terrain.f32").write_bytes(arr.tobytes(order="C"))
            terrain_info = {
                "file": "terrain.f32", "encoding": "little-endian IEEE754 float32, row-major",
                "width": dem.width, "height": dem.height, "affine_wgs84": [t.a, t.b, t.c, t.d, t.e, t.f],
                "nodata": "NaN", "units": "metres", "vertical_datum": "unchanged from Copernicus source; unverified",
                "role": "modern_reference_only", "source_id": dem_meta["source_id"],
                "sha256": sha256_file(temp / "terrain.f32"),
            }
        _write_json(temp / "reaches.json", {"schema_version": 1, "role": "modern_reference_only", "reaches": reaches})
        _write_json(temp / "historical_evidence.json", {"schema_version": 1, "target_year": region["target_year"],
                                                     "features": sorted(features, key=lambda f: f["properties"]["feature_id"])})
        layers = {
            "terrain": terrain_info,
            "flowlines": {"file": "reaches.json", "sha256": sha256_file(temp / "reaches.json"),
                          "role": "modern_reference_only", "count": len(reaches), "topology": "unresolved",
                          "source_id": water_meta["source_id"], "coverage": "New York State subset; New Jersey not covered"},
            "historical_evidence": {"file": "historical_evidence.json", "sha256": sha256_file(temp / "historical_evidence.json"),
                                    "count": check["feature_count"], "completeness": "partial_or_missing"},
            "climate": {"available": False}, "soils": {"available": False},
            "vegetation": {"available": False}, "historical_water_network": {"available": False},
        }
        manifest = {
            "schema": SCHEMA, "region_id": region["id"], "target_year": region["target_year"],
            "bbox_wgs84": list(bbox), "crs": "OGC:CRS84 (longitude, latitude)",
            "package_status": "modern_reference_only", "is_1609_initial_state": False,
            "layers": layers,
            "source_manifests": {"terrain_sha256": sha256_file(terrain.with_suffix(".manifest.json")),
                                 "flowlines_sha256": sha256_file(flowlines.with_suffix(".manifest.json")),
                                 "evidence_sha256": sha256_file(evidence)},
            "limitations": ["Do not use terrain or flowlines as 1609 conditions.",
                            "NHD identifiers are stable within source; downstream/upstream graph unresolved.",
                            "Target year describes research goal, not verified historical coverage."],
        }
        _write_json(temp / "manifest.json", manifest)
        temp.rename(output)
        return manifest
    finally:
        if temp.exists():
            shutil.rmtree(temp)


class WorldPackage:
    """Offline stdlib-only reader; no GDAL/rasterio required in a game client."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.manifest = json.loads((self.root / "manifest.json").read_text(encoding="utf-8"))
        if self.manifest.get("schema") != SCHEMA:
            raise ValueError("unsupported world-package schema")
        for name, layer in self.manifest["layers"].items():
            if "file" in layer and sha256_file(self.root / layer["file"]) != layer["sha256"]:
                raise ValueError(f"package integrity failed for {name}")
        t = self.manifest["layers"]["terrain"]
        if (self.root / t["file"]).stat().st_size != t["width"] * t["height"] * 4:
            raise ValueError("incorrect terrain sample count")
        self.reaches = json.loads((self.root / "reaches.json").read_text(encoding="utf-8"))["reaches"]

    def elevation_at(self, lon: float, lat: float) -> float | None:
        t = self.manifest["layers"]["terrain"]
        a, b, c, d, e, f = t["affine_wgs84"]
        col, row = math.floor((lon - c) / a), math.floor((lat - f) / e)
        if not (0 <= col < t["width"] and 0 <= row < t["height"]):
            return None
        with (self.root / t["file"]).open("rb") as handle:
            handle.seek(4 * (row * t["width"] + col))
            value = struct.unpack("<f", handle.read(4))[0]
        return value if math.isfinite(value) else None

    def reaches_in_bbox(self, bbox: list[float]) -> list[dict]:
        west, south, east, north = validate_bbox(bbox)
        return [r for r in self.reaches if r["bbox_wgs84"][0] <= east and r["bbox_wgs84"][2] >= west
                and r["bbox_wgs84"][1] <= north and r["bbox_wgs84"][3] >= south]

    def require_1609_initial_state(self) -> None:
        if not self.manifest.get("is_1609_initial_state", False):
            raise RuntimeError("historical 1609 initial state is NOT available; package holds modern references only")
