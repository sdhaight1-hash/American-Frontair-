"""Import evidence-based historical water geometry as *candidates* for a game dataset.

This is not an automatic reconstruction: coordinates must be provided in a sourced
vector or explicitly digitized from a cited map. Never declare complete 1609 state.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from pyproj import Transformer
from shapely.geometry import box, mapping, shape
from shapely.ops import transform

from .evidence import validate_features
from .geo import sha256_file, validate_bbox

CANDIDATE_ROLE = "historical_candidate_not_validated"
KINDS = {"shoreline": ("LineString", "MultiLineString"),
         "stream": ("LineString", "MultiLineString"),
         "wetland": ("Polygon", "MultiPolygon"),
         "pond": ("Polygon", "MultiPolygon")}


def _require_positive_number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{label} must be a finite positive number")
    return float(value)


def _control_fit(config: dict) -> tuple[object, dict]:
    """Least-squares pixel -> UTM18 (metres), tested on held-out control points."""
    controls = config.get("control_points")
    if not isinstance(controls, list):
        raise ValueError("image_pixels source requires control_points")
    fits = [p for p in controls if p.get("role") == "fit"]
    holdouts = [p for p in controls if p.get("role") == "holdout"]
    if len(fits) < 4 or len(holdouts) < 2:
        raise ValueError("at least four fitted and two independent holdout controls required")
    width = _require_positive_number(config.get("image_width"), "image_width")
    height = _require_positive_number(config.get("image_height"), "image_height")
    to_utm = Transformer.from_crs("EPSG:4326", "EPSG:32618", always_xy=True)
    to_wgs = Transformer.from_crs("EPSG:32618", "EPSG:4326", always_xy=True)
    def parse(item):
        p = item.get("pixel_xy")
        ll = item.get("lon_lat")
        if not (isinstance(p, list) and len(p) == 2 and isinstance(ll, list) and len(ll) == 2):
            raise ValueError("every control needs pixel_xy and lon_lat pairs")
        if not all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) for x in p+ll):
            raise ValueError("control coordinates must be finite numbers")
        if not (0 <= p[0] <= width and 0 <= p[1] <= height and -180 <= ll[0] <= 180 and -90 <= ll[1] <= 90):
            raise ValueError("control lies outside image or geographic domain")
        xy = to_utm.transform(*ll)
        return [float(p[0]), float(p[1]), 1.0], xy
    parsed = [parse(p) for p in fits + holdouts]
    all_pixels = [(p[0][0], p[0][1]) for p in parsed]
    if len(all_pixels) != len(set(all_pixels)):
        raise ValueError("duplicate controls cannot provide independent validation")
    # Center/scale pixels to prevent high-resolution scans from ill-conditioning.
    fit_arr = np.array([p[0] for p in parsed[:len(fits)]], dtype=float)
    mean = fit_arr[:, :2].mean(axis=0)
    scale = np.maximum(fit_arr[:, :2].std(axis=0), 1.0)
    def design(rows):
        a = np.array(rows, dtype=float)
        return np.column_stack(((a[:, 0]-mean[0])/scale[0], (a[:, 1]-mean[1])/scale[1], np.ones(len(a))))
    X = design([p[0] for p in parsed[:len(fits)]])
    Y = np.array([p[1] for p in parsed[:len(fits)]], dtype=float)
    coeffs, _, rank, _ = np.linalg.lstsq(X, Y, rcond=None)
    if rank != 3 or np.linalg.cond(X) > 50:
        raise ValueError("ill-conditioned or collinear map control points")
    def errors(rows):
        return np.linalg.norm(design([p[0] for p in rows]) @ coeffs - np.array([p[1] for p in rows]), axis=1)
    fit_error = errors(parsed[:len(fits)])
    holdout_error = errors(parsed[len(fits):])
    limit = _require_positive_number(config.get("max_holdout_error_m"), "max_holdout_error_m")
    if float(holdout_error.max()) > limit:
        raise ValueError(f"holdout registration error {holdout_error.max():.1f}m exceeds {limit:.1f}m")
    def convert(x, y, z=None):
        u = (x-mean[0])/scale[0]
        v = (y-mean[1])/scale[1]
        e = coeffs[0, 0]*u + coeffs[1, 0]*v + coeffs[2, 0]
        n = coeffs[0, 1]*u + coeffs[1, 1]*v + coeffs[2, 1]
        return to_wgs.transform(e, n)
    info = {
        "method": "pixel_affine_to_EPSG32618_then_WGS84",
        "control_fit_count": len(fits), "control_holdout_count": len(holdouts),
        "fit_rmse_m": round(float(np.sqrt(np.mean(fit_error**2))), 3),
        "holdout_rmse_m": round(float(np.sqrt(np.mean(holdout_error**2))), 3),
        "holdout_max_m": round(float(holdout_error.max()), 3),
        "holdout_threshold_m": limit,
        "caveat": "Control-point residuals do not measure historical map surveying error, drawing error or coastline migration.",
    }
    return convert, info


def ingest_historical_water(region: dict, source: Path, metadata_path: Path, output: Path) -> dict:
    """Export only sourced, rights-cleared candidate geometries; no claimed 1609 truth."""
    bbox = validate_bbox(region["bbox_wgs84"])
    source, metadata_path, output = map(Path, (source, metadata_path, output))
    if source.resolve() == output.resolve() or metadata_path.resolve() == output.resolve():
        raise ValueError("do not overwrite raw sources or metadata")
    if output.exists() or output.with_suffix(".manifest.json").exists():
        raise FileExistsError("refusing to overwrite historical candidate")
    meta = json.loads(metadata_path.read_text(encoding="utf-8"))
    required = ("source_id", "source_url", "source_publication_year", "historical_interval",
                "evidence_locator", "rights_basis", "redistribution_allowed", "coordinate_space")
    if any(key not in meta for key in required):
        raise ValueError("source metadata lacks required provenance and rights fields")
    if any(not isinstance(meta[k], str) or not meta[k].strip() for k in ("source_id", "source_url", "evidence_locator", "rights_basis")):
        raise ValueError("source citation and redistribution rights must be nonempty")
    if meta["redistribution_allowed"] is not True:
        raise ValueError("redistribution rights not confirmed; cannot produce game export")
    interval = meta["historical_interval"]
    if not (isinstance(interval, list) and len(interval) == 2 and
            all(type(x) is int for x in interval) and interval[0] <= region["target_year"] <= interval[1]):
        raise ValueError("source does not support the target historical year")
    if type(meta["source_publication_year"]) is not int:
        raise ValueError("source publication year must be an integer")
    uncertainty = _require_positive_number(meta.get("horizontal_uncertainty_m"), "horizontal_uncertainty_m")
    if meta["coordinate_space"] not in ("wgs84", "image_pixels"):
        raise ValueError("coordinate_space must be wgs84 or image_pixels")
    converter, registration = (None, {"method": "sourced_pregeoreferenced_vector", "holdout_max_m": None})
    if meta["coordinate_space"] == "image_pixels":
        converter, registration = _control_fit(meta)
        image = meta.get("source_image")
        if not isinstance(image, str) or not image:
            raise ValueError("pixel digitization requires a real local source_image")
        image_path = (metadata_path.parent / image).resolve()
        if not image_path.is_file():
            raise FileNotFoundError(image_path)
        image_sha = sha256_file(image_path)
        if meta.get("source_image_sha256") != image_sha:
            raise ValueError("historical source_image_sha256 missing or mismatched; scan identity not verified")
        # Image-pixel traces must refer to the exact dimensions of the *actual*
        # archived raster, not an asserted canvas size in a metadata file.
        from PIL import Image, UnidentifiedImageError
        try:
            with Image.open(image_path) as im:
                im.verify()
            with Image.open(image_path) as im:
                actual_dimensions = im.size
        except (OSError, UnidentifiedImageError) as exc:
            raise ValueError("historic source_image is not a readable raster") from exc
        if actual_dimensions != (meta["image_width"], meta["image_height"]):
            raise ValueError("source_image dimensions differ from georeferencing control canvas")
    else:
        image_sha = None
    raw = json.loads(source.read_text(encoding="utf-8"))
    if raw.get("type") != "FeatureCollection" or not isinstance(raw.get("features"), list):
        raise ValueError("historical water input must be GeoJSON FeatureCollection")
    if not raw["features"]:
        raise ValueError("refusing to export an empty claimed historical water layer")
    extent = box(*bbox)
    candidates = []
    for idx, feature in enumerate(raw["features"]):
        props = feature.get("properties")
        if feature.get("type") != "Feature" or not isinstance(props, dict) or not feature.get("geometry"):
            raise ValueError(f"feature {idx}: missing geometry/properties")
        fid = props.get("feature_id")
        kind = props.get("feature_type")
        if not isinstance(fid, str) or not fid.strip() or kind not in KINDS:
            raise ValueError(f"feature {idx}: missing feature_id or supported historical water type")
        geom = shape(feature["geometry"])
        if geom.geom_type not in KINDS[kind] or not geom.is_valid or geom.is_empty:
            raise ValueError(f"feature {fid}: incompatible or invalid geometry for {kind}")
        if converter:
            image_box = box(0, 0, meta["image_width"], meta["image_height"])
            if not image_box.covers(geom):
                raise ValueError(f"feature {fid}: traced geometry is outside source image")
            geom = transform(converter, geom)
        if not geom.is_valid or geom.is_empty:
            raise ValueError(f"feature {fid}: invalid after transformation")
        if not extent.intersects(geom):
            raise ValueError(f"feature {fid}: does not intersect region")
        clipped = geom.intersection(extent)
        if clipped.is_empty or clipped.geom_type not in KINDS[kind]:
            raise ValueError(f"feature {fid}: invalid clipping result")
        if props.get("valid_years") != interval:
            raise ValueError(f"feature {fid}: asserted period conflicts with documented source scope")
        if props.get("basis") not in ("historic_map", "archaeology", "paleoenvironment", "document", "model", "inference"):
            raise ValueError(f"feature {fid}: missing source basis")
        cited = props.get("evidence")
        if not isinstance(cited, list) or not any(isinstance(c, dict) and c.get("source_id") == meta["source_id"] and c.get("locator") for c in cited):
            raise ValueError(f"feature {fid}: no citation matching source metadata")
        entry = dict(props)
        entry.update({
            "source_publication_year": meta["source_publication_year"],
            "source_url": meta["source_url"],
            "registration_holdout_max_m": registration["holdout_max_m"],
            "minimum_horizontal_uncertainty_m": max(uncertainty, registration["holdout_max_m"] or 0),
            "review_status": CANDIDATE_ROLE,
            "bbox_wgs84": list(clipped.bounds),
            "clipped_to_region": not geom.equals(clipped),
        })
        candidates.append({"type": "Feature", "geometry": mapping(clipped), "properties": entry})
    candidates.sort(key=lambda f: f["properties"]["feature_id"])
    if len({f["properties"]["feature_id"] for f in candidates}) != len(candidates):
        raise ValueError("duplicate historical feature IDs")
    from .evidence import validate_collection
    collection = {"type": "FeatureCollection", "features": candidates}
    validate_collection(collection, year=region["target_year"], bbox=bbox)
    # Commit atomically only after every feature and registration check passes.
    output.parent.mkdir(parents=True, exist_ok=True)
    import tempfile
    import os
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=output.parent, delete=False, suffix=".partial") as stream:
        temp = Path(stream.name)
        json.dump(collection, stream, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        stream.write("\n")
    try:
        manifest = {
            "schema_version": 1, "layer": "historic_water_candidates", "role": CANDIDATE_ROLE,
            "is_1609_reconstruction": False, "historical_target_year": region["target_year"],
            "region_id": region["id"], "requested_bbox_wgs84": list(bbox),
            "source_id": meta["source_id"], "source_url": meta["source_url"],
            "source_publication_year": meta["source_publication_year"],
            "historical_interval": interval, "source_locator": meta["evidence_locator"],
            "rights_basis": meta["rights_basis"], "source_file_sha256": sha256_file(source),
            "source_metadata_sha256": sha256_file(metadata_path), "source_image_sha256": image_sha,
            "registration": registration, "feature_count": len(candidates),
            "output_sha256": sha256_file(temp),
            "limitations": ["Candidate reconstruction based on cited source; not an observed 1609 position.",
                            "Geometric registration errors omit historic depiction and environmental change uncertainty.",
                            "Not a complete 1609 hydrological network or world initialization."],
        }
        temp.replace(output)
        output.with_suffix(".manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        return manifest
    finally:
        temp.unlink(missing_ok=True)
