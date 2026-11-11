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

from .runtime import sha256_file, validate_bbox
from .network import RiverNetwork, SCHEMA as NETWORK_SCHEMA

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


def export_pilot(region: dict, terrain: Path, flowlines: Path, evidence: Path, output: Path, *, network: Path | None = None, historic_water: Path | None = None, historic_constraints: Path | None = None) -> dict:
    """Export one offline region; never promote its modern data to historical state."""
    import numpy as np
    import rasterio
    from .evidence import validate_features

    bbox = validate_bbox(region["bbox_wgs84"])
    dem_meta = _verified_manifest(terrain, "modern_reference_only", "terrain_elevation", region)
    water_meta = _verified_manifest(flowlines, "modern_reference_only", "flowlines", region)
    graph = None
    if network is not None:
        _verified_manifest(network, "modern_reference_only", "nhdplusv2_network", region)
        graph = json.loads(network.read_text(encoding="utf-8"))
        if graph.get("schema") != NETWORK_SCHEMA or list(graph.get("bbox_wgs84", [])) != list(bbox):
            raise ValueError("network source schema or geographic region mismatch")
        RiverNetwork(graph)  # Verify reciprocity before exporting to the game.
    candidate_geojson = None
    if historic_water is not None:
        from .historic_water import CANDIDATE_ROLE
        historic_water = Path(historic_water)
        candidate_manifest = json.loads(historic_water.with_suffix(".manifest.json").read_text(encoding="utf-8"))
        if (candidate_manifest.get("role") != CANDIDATE_ROLE or
                candidate_manifest.get("is_1609_reconstruction") is not False or
                candidate_manifest.get("historical_target_year") != region["target_year"] or
                candidate_manifest.get("region_id") != region["id"] or
                list(candidate_manifest.get("requested_bbox_wgs84", [])) != list(bbox) or
                candidate_manifest.get("output_sha256") != sha256_file(historic_water)):
            raise ValueError("historic water candidate manifest or SHA-256 invalid")
        validate_features(historic_water, year=region["target_year"], bbox=bbox)
        candidate_geojson = json.loads(historic_water.read_text(encoding="utf-8"))
        if len(candidate_geojson["features"]) != candidate_manifest.get("feature_count"):
            raise ValueError("historic water candidate feature count mismatch")
        for feature in candidate_geojson["features"]:
            if feature["properties"].get("review_status") != CANDIDATE_ROLE:
                raise ValueError("historical water claims must remain explicitly candidate-only")
    constraint_document, constraint_stats = (None, None)
    if historic_constraints is not None:
        from .historical_constraints import load_constraints
        historic_constraints = Path(historic_constraints)
        constraint_document, constraint_stats = load_constraints(historic_constraints, region)
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
        if graph is not None:
            _write_json(temp / "river_network.json", graph)
        if candidate_geojson is not None:
            _write_json(temp / "historic_water_candidates.geojson", candidate_geojson)
        if constraint_document is not None:
            _write_json(temp / "historical_water_constraints.json", constraint_document)
        _write_json(temp / "historical_evidence.json", {"schema_version": 1, "target_year": region["target_year"],
                                                     "features": sorted(features, key=lambda f: f["properties"]["feature_id"])})
        layers = {
            "terrain": terrain_info,
            "flowlines": {"file": "reaches.json", "sha256": sha256_file(temp / "reaches.json"),
                          "role": "modern_reference_only", "count": len(reaches), "topology": "unresolved",
                          "source_id": water_meta["source_id"], "coverage": "New York State subset; New Jersey not covered"},
            "historical_evidence": {"file": "historical_evidence.json", "sha256": sha256_file(temp / "historical_evidence.json"),
                                    "count": check["feature_count"], "completeness": "partial_or_missing"},
            "river_network": {
                "available": graph is not None,
                "role": "modern_reference_only" if graph else None,
                "source_id": "usgs_nhdplusv2" if graph else None,
                **({"file": "river_network.json", "sha256": sha256_file(temp / "river_network.json"),
                    "topology": "source_nodes_partial_buffered", "statistics": graph["statistics"]} if graph else {}),
            },
            "historic_water_candidates": {
                "available": candidate_geojson is not None,
                "role": "historical_candidate_not_validated" if candidate_geojson is not None else None,
                **({"file": "historic_water_candidates.geojson",
                    "sha256": sha256_file(temp / "historic_water_candidates.geojson"),
                    "count": len(candidate_geojson["features"])} if candidate_geojson is not None else {}),
            },
            "historical_water_constraints": {
                "available": constraint_document is not None,
                "role": "historical_documentary_constraints_not_georeferenced" if constraint_document else None,
                **({"file": "historical_water_constraints.json",
                    "sha256": sha256_file(temp / "historical_water_constraints.json"),
                    "counts": constraint_stats} if constraint_document is not None else {}),
            },
            "climate": {"available": False}, "soils": {"available": False},
            "vegetation": {"available": False}, "historical_water_network": {"available": False},
        }
        manifest = {
            "schema": SCHEMA, "region_id": region["id"], "target_year": region["target_year"],
            "bbox_wgs84": list(bbox), "crs": "OGC:CRS84 (longitude, latitude)",
            "package_status": "modern_reference_only", "is_1609_initial_state": False,
            "layers": layers,
            "source_manifests": {"network_sha256": sha256_file(network.with_suffix(".manifest.json")) if network else None,
                                 "terrain_sha256": sha256_file(terrain.with_suffix(".manifest.json")),
                                 "flowlines_sha256": sha256_file(flowlines.with_suffix(".manifest.json")),
                                 "evidence_sha256": sha256_file(evidence),
                                 "historic_water_manifest_sha256": sha256_file(historic_water.with_suffix(".manifest.json")) if historic_water else None,
                                 "historic_constraints_sha256": sha256_file(historic_constraints) if historic_constraints else None},
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
        h_layer = self.manifest["layers"].get("historic_water_candidates", {})
        self.historic_water_candidates = (json.loads((self.root / h_layer["file"]).read_text(encoding="utf-8"))["features"]
                                           if h_layer.get("available") else [])
        constraints_layer = self.manifest["layers"].get("historical_water_constraints", {})
        self.historical_water_constraints = (json.loads((self.root / constraints_layer["file"]).read_text(encoding="utf-8"))
                                             if constraints_layer.get("available") else None)
        graph_layer = self.manifest["layers"].get("river_network", {})
        self.river_network = (RiverNetwork(json.loads((self.root / graph_layer["file"]).read_text(encoding="utf-8")))
                              if graph_layer.get("available") else None)

    def historical_water_constraint(self, feature_id: str) -> dict | None:
        """Return evidence-based topological hints, never implied coordinates."""
        if self.historical_water_constraints is None:
            return None
        return next((item for item in self.historical_water_constraints["features"]
                     if item["id"] == feature_id), None)

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

    def historic_water_in_bbox(self, bbox: list[float]) -> list[dict]:
        """Bounding-box prefilter for sourced historical hypotheses (stdlib-only)."""
        west, south, east, north = validate_bbox(bbox)
        result = []
        for feature in self.historic_water_candidates:
            x0, y0, x1, y1 = feature["properties"]["bbox_wgs84"]
            if x0 <= east and x1 >= west and y0 <= north and y1 >= south:
                result.append(feature)
        return result

    def require_1609_initial_state(self) -> None:
        if not self.manifest.get("is_1609_initial_state", False):
            raise RuntimeError("historical 1609 initial state is NOT available; package holds modern references only")


def attach_historical_constraints(region: dict, source_package: Path, constraint_path: Path, output: Path) -> dict:
    """Add sourced unlocated water constraints to an already verified offline world.

    Does not modify terrain, rivers, or the original package, and does NOT
    promote a modern reference into a completed 1609 historical initial state.
    """
    from .historical_constraints import load_constraints, ROLE

    source = WorldPackage(source_package)  # Verify every existing package-file hash.
    if source.manifest.get("region_id") != region["id"] or source.manifest.get("target_year") != region["target_year"]:
        raise ValueError("input game package region/year mismatch")
    if list(source.manifest.get("bbox_wgs84", [])) != list(region["bbox_wgs84"]):
        raise ValueError("input game package bounds mismatch")
    if source.manifest.get("is_1609_initial_state") is not False:
        raise ValueError("documentary overlay is only valid for unfinished historical reference packages")
    existing = source.manifest["layers"].get("historical_water_constraints", {})
    if existing.get("available"):
        raise ValueError("historical documentary constraints already installed; version explicitly instead")
    constraints, stats = load_constraints(constraint_path, region)
    output = Path(output)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing world package: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix=".constraints-overlay-", dir=output.parent))
    try:
        for entry in source.root.iterdir():
            if not entry.is_file():
                raise ValueError("unexpected nested world package entry")
            shutil.copy2(entry, temp / entry.name)
        _write_json(temp / "historical_water_constraints.json", constraints)
        manifest = json.loads((temp / "manifest.json").read_text(encoding="utf-8"))
        manifest["layers"]["historical_water_constraints"] = {
            "available": True, "role": ROLE, "counts": stats,
            "file": "historical_water_constraints.json",
            "sha256": sha256_file(temp / "historical_water_constraints.json"),
        }
        manifest.setdefault("source_manifests", {})["historic_constraints_sha256"] = sha256_file(constraint_path)
        manifest["is_1609_initial_state"] = False
        _write_json(temp / "manifest.json", manifest)
        WorldPackage(temp)  # End-to-end integrity check before publishing.
        temp.rename(output)
        return manifest
    finally:
        if temp.exists():
            shutil.rmtree(temp)
