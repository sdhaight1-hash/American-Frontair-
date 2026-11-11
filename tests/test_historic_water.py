"""All historical-looking test geometries here are invented fixtures, NOT 1609 evidence."""
import json
from pathlib import Path

import pytest
from pyproj import Transformer

from na1609.geo import sha256_file
from na1609.historic_water import CANDIDATE_ROLE, ingest_historical_water
from na1609.world_package import WorldPackage, export_pilot
from test_world_package import setup_inputs, REGION as EXPORT_REGION

REGION = {"id": "lower_hudson_pilot", "target_year": 1609,
          "bbox_wgs84": [-74.12, 40.64, -73.82, 40.9]}


def geojson(feature_type="stream", coordinates=None):
    if coordinates is None:
        coordinates = [[-74.03, 40.70], [-74.01, 40.72]]
    return {"type": "FeatureCollection", "features": [{
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": coordinates},
        "properties": {"feature_id": "synthetic-stream-A", "feature_type": feature_type,
                       "valid_years": [1590, 1625], "basis": "historic_map",
                       "confidence": "unknown",
                       "evidence": [{"source_id": "synthetic-fixture", "locator": "synthetic sheet, no historic claim"}]},
    }]}


def meta(space="wgs84"):
    return {"source_id": "synthetic-fixture", "source_url": "https://example.invalid/test-fixture",
            "source_publication_year": 1909, "historical_interval": [1590, 1625],
            "evidence_locator": "synthetic sheet, no historic claim",
            "rights_basis": "synthetic fixture authored for tests", "redistribution_allowed": True,
            "coordinate_space": space, "horizontal_uncertainty_m": 250}


def inputs(tmp_path, *, coordinates=None, metadata=None):
    path = tmp_path / "raw.geojson"
    path.write_text(json.dumps(geojson(coordinates=coordinates)), encoding="utf-8")
    source = tmp_path / "source.json"
    source.write_text(json.dumps(metadata or meta()), encoding="utf-8")
    return path, source


def test_wgs84_historical_candidates_preserve_uncertainty_and_citation(tmp_path):
    source, metadata = inputs(tmp_path)
    out = tmp_path / "candidate.geojson"
    manifest = ingest_historical_water(REGION, source, metadata, out)
    assert manifest["role"] == CANDIDATE_ROLE
    assert manifest["is_1609_reconstruction"] is False
    assert manifest["feature_count"] == 1
    assert manifest["output_sha256"] == sha256_file(out)
    result = json.loads(out.read_text())["features"][0]
    assert result["properties"]["minimum_horizontal_uncertainty_m"] == 250
    assert result["properties"]["source_publication_year"] == 1909
    assert result["properties"]["review_status"] == CANDIDATE_ROLE


def test_rights_required_before_game_export(tmp_path):
    m = meta()
    m["redistribution_allowed"] = False
    source, metadata = inputs(tmp_path, metadata=m)
    with pytest.raises(ValueError, match="rights"):
        ingest_historical_water(REGION, source, metadata, tmp_path / "bad.geojson")
    assert not (tmp_path / "bad.geojson").exists()


def test_historical_period_must_include_1609(tmp_path):
    m = meta()
    m["historical_interval"] = [1700, 1800]
    source, metadata = inputs(tmp_path, metadata=m)
    with pytest.raises(ValueError, match="target historical year"):
        ingest_historical_water(REGION, source, metadata, tmp_path / "bad.geojson")


def test_geometry_must_be_sourced_and_in_region(tmp_path):
    src, met = inputs(tmp_path, coordinates=[[-76, 40], [-75.5, 40.5]])
    with pytest.raises(ValueError, match="does not intersect"):
        ingest_historical_water(REGION, src, met, tmp_path / "bad.geojson")
    raw = geojson()
    raw["features"][0]["properties"]["evidence"] = [{"source_id": "someone-else", "locator": "x"}]
    src.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="citation matching"):
        ingest_historical_water(REGION, src, met, tmp_path / "bad.geojson")


def test_duplicate_feature_ids_rejected(tmp_path):
    src, met = inputs(tmp_path)
    raw = json.loads(src.read_text())
    raw["features"].append(raw["features"][0])
    src.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="duplicate"):
        ingest_historical_water(REGION, src, met, tmp_path / "bad.geojson")


def pixel_inputs(tmp_path, *, offset_holdout=False):
    e0, n0 = Transformer.from_crs("EPSG:4326", "EPSG:32618", always_xy=True).transform(-74.02, 40.75)
    to_ll = Transformer.from_crs("EPSG:32618", "EPSG:4326", always_xy=True)
    positions = [(150, 150), (850, 150), (150, 850), (850, 850), (500, 200),
                 (500, 500), (650, 700)]
    controls = []
    for index, (x, y) in enumerate(positions):
        e = e0 + 2.2 * (x - 500) + 0.3 * (y - 500)
        n = n0 - 0.1 * (x - 500) - 2.3 * (y - 500)
        if offset_holdout and index == 6:
            e += 250
        controls.append({"pixel_xy": [x, y], "lon_lat": list(to_ll.transform(e, n)),
                         "role": "fit" if index < 5 else "holdout"})
    config = meta("image_pixels")
    config.update({"image_width": 1000, "image_height": 1000,
                   "control_points": controls, "max_holdout_error_m": 25.0,
                   "source_image": "synthetic_map.png"})
    (tmp_path / "synthetic_map.png").write_bytes(b"test-only synthetic bytes")
    src, meta_file = inputs(tmp_path, coordinates=[[460, 450], [520, 510]], metadata=config)
    return src, meta_file


def test_pixel_registration_with_independent_holdout(tmp_path):
    src, metadata = pixel_inputs(tmp_path)
    out = tmp_path / "candidate.geojson"
    manifest = ingest_historical_water(REGION, src, metadata, out)
    assert manifest["registration"]["control_fit_count"] == 5
    assert manifest["registration"]["control_holdout_count"] == 2
    assert manifest["registration"]["holdout_max_m"] < 0.001
    assert len(manifest["source_image_sha256"]) == 64
    xy = json.loads(out.read_text())["features"][0]["geometry"]["coordinates"]
    assert -74.12 < xy[0][0] < -73.82
    assert 40.64 < xy[0][1] < 40.9


def test_pixel_registration_rejects_bad_holdout(tmp_path):
    src, metadata = pixel_inputs(tmp_path, offset_holdout=True)
    with pytest.raises(ValueError, match="holdout registration error"):
        ingest_historical_water(REGION, src, metadata, tmp_path / "candidate.geojson")


def test_pixel_registration_rejects_missing_original_map(tmp_path):
    src, metadata = pixel_inputs(tmp_path)
    (tmp_path / "synthetic_map.png").unlink()
    with pytest.raises(FileNotFoundError):
        ingest_historical_water(REGION, src, metadata, tmp_path / "candidate.geojson")


def test_offline_world_export_keeps_candidate_separate_from_start_state(tmp_path):
    terrain, flowlines, evidence = setup_inputs(tmp_path)
    src, meta_file = inputs(tmp_path)
    # Export fixture covers the test bbox (which also covers the historical candidate).
    hist = tmp_path / "candidate.geojson"
    candidate_region = dict(EXPORT_REGION)
    ingest_historical_water(candidate_region, src, meta_file, hist)
    target = tmp_path / "world"
    manifest = export_pilot(EXPORT_REGION, terrain, flowlines, evidence, target, historic_water=hist)
    assert manifest["layers"]["historic_water_candidates"]["count"] == 1
    assert manifest["is_1609_initial_state"] is False
    offline = WorldPackage(target)
    assert len(offline.historic_water_in_bbox([-74.1, 40.69, -74, 40.75])) == 1
    assert offline.historic_water_in_bbox([-74.3, 40.8, -74.2, 40.9]) == []
    with pytest.raises(RuntimeError, match="NOT available"):
        offline.require_1609_initial_state()
    (target / "historic_water_candidates.geojson").write_text("{}")
    with pytest.raises(ValueError, match="integrity"):
        WorldPackage(target)


def test_world_rejects_tampered_candidate_hash(tmp_path):
    terrain, flowlines, evidence = setup_inputs(tmp_path)
    src, meta_file = inputs(tmp_path)
    hist = tmp_path / "candidate.geojson"
    ingest_historical_water(EXPORT_REGION, src, meta_file, hist)
    hist.write_text(hist.read_text() + " ")
    with pytest.raises(ValueError, match="SHA-256"):
        export_pilot(EXPORT_REGION, terrain, flowlines, evidence, tmp_path / "world", historic_water=hist)
