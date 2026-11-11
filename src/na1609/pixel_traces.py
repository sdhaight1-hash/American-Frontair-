"""Inspect evidence contours in archival scan pixels, without inventing geographic positions.

A checked source-pixel trace is NOT a georeferenced historical GIS feature; it must
pass independent ground-control/registration review before historic_water import.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from PIL import Image, ImageDraw
from shapely.geometry import Polygon, box, shape

from .archival_map import inspect_archival_map
from .geo import sha256_file

ROLE = "archival_image_pixel_trace_not_georeferenced"


def validate_pixel_traces(image_path: Path, trace_path: Path) -> dict:
    image_path, trace_path = Path(image_path), Path(trace_path)
    scan = inspect_archival_map(image_path)
    if scan["quality_requested"] != "original" or not scan["eligible_for_precision_tracing_review"]:
        raise ValueError("pixel tracing requires the original full-resolution archival scan")
    obj = json.loads(trace_path.read_text(encoding="utf-8"))
    grid = obj.get("pixel_coordinate_system", {})
    expected = {"origin": "top-left", "x": "right", "y": "down", "units": "scan_pixels", "width": scan["width_px"], "height": scan["height_px"]}
    if grid != expected:
        raise ValueError("pixel coordinate system does not match this archival image")
    if obj.get("type") != "FeatureCollection" or obj.get("source_id") != scan["source_id"] or obj.get("source_image_id") != scan["source_image_id"] or obj.get("source_image_sha256") != scan["image_sha256"]:
        raise ValueError("archival trace does not match verified source scan")
    features = obj.get("features")
    if not isinstance(features, list) or not features:
        raise ValueError("no archival pixel traces supplied")
    full = box(0, 0, scan["width_px"], scan["height_px"])
    ids = set()
    extents = []
    for f in features:
        if f.get("type") != "Feature" or not isinstance(f.get("properties"), dict):
            raise ValueError("invalid pixel trace feature")
        prop = f["properties"]
        fid = prop.get("feature_id")
        if not isinstance(fid, str) or not fid or fid in ids:
            raise ValueError("missing or duplicate pixel trace feature ID")
        ids.add(fid)
        if prop.get("feature_type") != "pond" or prop.get("valid_years") != [1609, 1609] or prop.get("source_publication_year") != 1909:
            raise ValueError("unsupported feature type or historical dating")
        if prop.get("basis") != "historic_map" or prop.get("confidence") not in ("low", "medium") or prop.get("review_status") != "source_pixel_trace_not_georeferenced":
            raise ValueError("trace must be labeled as an unregistered archival hypothesis")
        if prop.get("source_coordinate_space") != "image_pixels_y_down":
            raise ValueError("trace must use source image pixel coordinates")
        u = prop.get("pixel_boundary_uncertainty_px")
        if not isinstance(u, (int, float)) or isinstance(u, bool) or not math.isfinite(u) or u <= 0:
            raise ValueError("trace uncertainty must be positive pixels")
        citation = prop.get("evidence")
        if not isinstance(citation, list) or not any(isinstance(c, dict) and c.get("source_id") == scan["source_id"] and c.get("locator") for c in citation):
            raise ValueError("trace requires a source-image citation locator")
        geom = shape(f.get("geometry"))
        if not isinstance(geom, Polygon) or geom.is_empty or not geom.is_valid or geom.area < 20 or not full.covers(geom):
            raise ValueError("invalid or out-of-image pond outline")
        extents.append(geom.bounds)
    return {
        "schema_version": 1,
        "role": ROLE,
        "is_1609_reconstruction": False,
        "georeferenced": False,
        "publication_year": 1909,
        "depicted_year": 1609,
        "source_id": scan["source_id"],
        "source_page": scan["source_page"],
        "source_image_sha256": scan["image_sha256"],
        "trace_sha256": sha256_file(trace_path),
        "feature_count": len(ids),
        "feature_ids": sorted(ids),
        "image_pixel_feature_bounds": [list(x) for x in extents],
        "limitations": [
            "Features are image pixel traces of a 1909 retrospective map, not WGS84 geometry.",
            "Blue ink borders have scan/symbol uncertainty; these were not observed or surveyed in 1609.",
            "Independent fitted and held-out ground controls are required before geographic export.",
            "This file is not part of the 1609 simulation initial state.",
        ],
    }


def preview_pixel_traces(image_path: Path, trace_path: Path, output: Path, *, padding: int = 60) -> dict:
    """Render a review overlay without editing the original, and report provenance."""
    result = validate_pixel_traces(image_path, trace_path)
    trace = json.loads(Path(trace_path).read_text(encoding="utf-8"))
    geom_list = [shape(f["geometry"]) for f in trace["features"]]
    with Image.open(image_path) as source:
        image = source.convert("RGB")
    bounds = [g.bounds for g in geom_list]
    l = max(0, int(min(v[0] for v in bounds)) - padding)
    t = max(0, int(min(v[1] for v in bounds)) - padding)
    r = min(image.width, int(max(v[2] for v in bounds)) + padding)
    b = min(image.height, int(max(v[3] for v in bounds)) + padding)
    canvas = image.crop((l, t, r, b))
    draw = ImageDraw.Draw(canvas)
    for geom in geom_list:
        path = [(round(x - l), round(y - t)) for x, y in geom.exterior.coords]
        draw.line(path, fill=(255, 35, 35), width=3, joint="curve")
    output = Path(output)
    if output.resolve() in (Path(image_path).resolve(), Path(trace_path).resolve()):
        raise ValueError("review preview cannot overwrite source image or trace")
    if output.exists():
        raise FileExistsError("review preview already exists")
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, format="PNG")
    return {**result, "review_image": str(output), "review_sha256": sha256_file(output), "review_crop_pixels": [l, t, r, b]}
