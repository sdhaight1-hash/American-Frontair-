"""Synthetic scans test the map-pixel contract; no synthetic outline is historical evidence."""
import io
import json

import pytest
from PIL import Image

from na1609.archival_map import acquire_maccoun_map
from na1609.cli import main
from na1609.pixel_traces import ROLE, preview_pixel_traces, validate_pixel_traces


def fixture(tmp_path):
    image = Image.new("RGB", (3200, 900), (180, 180, 170))
    buf = io.BytesIO()
    image.save(buf, format="JPEG")
    path = tmp_path / "source.jpg"
    meta = acquire_maccoun_map(path, quality="original", fetch=lambda url: buf.getvalue())
    f = {
        "type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[300, 200], [340, 200], [340, 250], [300, 250], [300, 200]]]},
        "properties": {
            "feature_id": "test-pond", "feature_type": "pond", "name": "synthetic test polygon", "valid_years": [1609, 1609],
            "source_publication_year": 1909, "basis": "historic_map", "confidence": "low", "source_coordinate_space": "image_pixels_y_down",
            "review_status": "source_pixel_trace_not_georeferenced", "pixel_boundary_uncertainty_px": 3,
            "evidence": [{"source_id": meta["source_id"], "locator": "synthetic fixture"}],
        },
    }
    obj = {
        "type": "FeatureCollection", "source_id": meta["source_id"], "source_image_id": meta["source_image_id"],
        "source_image_sha256": meta["image_sha256"],
        "pixel_coordinate_system": {"origin": "top-left", "x": "right", "y": "down", "units": "scan_pixels", "width": 3200, "height": 900},
        "features": [f],
    }
    json_file = tmp_path / "traces.geojson"
    json_file.write_text(json.dumps(obj))
    return path, json_file, obj


def test_valid_trace_is_explicitly_not_world_geometry(tmp_path):
    image, traces, _ = fixture(tmp_path)
    report = validate_pixel_traces(image, traces)
    assert report["role"] == ROLE
    assert report["feature_count"] == 1
    assert report["georeferenced"] is False
    assert report["is_1609_reconstruction"] is False
    assert report["image_pixel_feature_bounds"] == [[300.0, 200.0, 340.0, 250.0]]


def test_review_image_and_cli(tmp_path, capsys):
    image, traces, _ = fixture(tmp_path)
    output = tmp_path / "qa.png"
    assert main(["inspect-pixel-traces", "--image", str(image), "--traces", str(traces), "--preview", str(output)]) == 0
    r = json.loads(capsys.readouterr().out)
    assert r["feature_count"] == 1 and output.exists()
    with Image.open(output) as preview:
        assert preview.width < 1000
    with pytest.raises(FileExistsError):
        preview_pixel_traces(image, traces, output)


def test_source_image_identity_rejected(tmp_path):
    image, traces, obj = fixture(tmp_path)
    obj["source_image_sha256"] = "0" * 64
    traces.write_text(json.dumps(obj))
    with pytest.raises(ValueError, match="verified source"):
        validate_pixel_traces(image, traces)


def test_out_of_image_and_fake_geo_coordinates_rejected(tmp_path):
    image, traces, obj = fixture(tmp_path)
    obj["features"][0]["geometry"]["coordinates"][0][1] = [5000, 200]
    traces.write_text(json.dumps(obj))
    with pytest.raises(ValueError, match="out-of-image"):
        validate_pixel_traces(image, traces)


def test_duplicate_identifiers_rejected(tmp_path):
    image, traces, obj = fixture(tmp_path)
    obj["features"].append(json.loads(json.dumps(obj["features"][0])))
    traces.write_text(json.dumps(obj))
    with pytest.raises(ValueError, match="duplicate"):
        validate_pixel_traces(image, traces)


def test_incorrect_dates_and_missing_citations_rejected(tmp_path):
    image, traces, obj = fixture(tmp_path)
    obj["features"][0]["properties"]["valid_years"] = [1909, 1909]
    traces.write_text(json.dumps(obj))
    with pytest.raises(ValueError, match="dating"):
        validate_pixel_traces(image, traces)
    obj["features"][0]["properties"]["valid_years"] = [1609, 1609]
    obj["features"][0]["properties"]["evidence"] = []
    traces.write_text(json.dumps(obj))
    with pytest.raises(ValueError, match="citation"):
        validate_pixel_traces(image, traces)


def test_unreviewed_preview_scan_rejected(tmp_path):
    image, traces, obj = fixture(tmp_path)
    manifest = image.with_suffix(".manifest.json")
    meta = json.loads(manifest.read_text())
    meta["quality_requested"] = "preview"
    manifest.write_text(json.dumps(meta))
    with pytest.raises(ValueError, match="full-resolution"):
        validate_pixel_traces(image, traces)
