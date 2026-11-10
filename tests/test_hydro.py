"""Offline contract tests; synthetic waterway geometry is never historical data."""
import json
from urllib.parse import parse_qs, urlparse

import pytest
from shapely.geometry import shape

from na1609.cli import main
from na1609.hydro import create_modern_flowlines, _query_ids

REGION = {"id": "lower_hudson_pilot", "target_year": 1609, "bbox_wgs84": [-74.12, 40.64, -73.82, 40.90]}


def fake_feature(fid, coordinates, fcode=46006):
    return {"type": "Feature",
            "properties": {"OBJECTID": fid, "Permanent_Identifier": f"NHD-{fid}", "FCode": fcode},
            "geometry": {"type": "LineString", "coordinates": coordinates}}


def fake_service(url):
    p = parse_qs(urlparse(url).query)
    if p.get("returnIdsOnly") == ["true"]:
        assert p["geometry"] == ["-74.12,40.64,-73.82,40.9"]
        assert p["inSR"] == ["4326"]
        return {"objectIdFieldName": "OBJECTID", "objectIds": [7, 3]}
    assert p["f"] == ["geojson"]
    assert p["outSR"] == ["4326"]
    assert p["objectIds"] == ["3,7"]
    return {"type": "FeatureCollection", "features": [
        fake_feature(7, [[-74.1, 40.75], [-73.9, 40.8]]),
        fake_feature(3, [[-74.2, 40.7], [-73.9, 40.7]], fcode=55800),
    ]}


def test_query_contract_spatially_bounded():
    assert _query_ids(REGION["bbox_wgs84"], get_json=fake_service) == [3, 7]


def test_raw_geometry_clipping_and_provenance(tmp_path):
    raw = tmp_path / "raw.geojson"
    output = tmp_path / "derived.geojson"
    m = create_modern_flowlines(REGION, raw, output, get_json=fake_service)
    assert (m["raw_feature_count"], m["derived_feature_count"], m["bbox_truncated_features"]) == (2, 2, 1)
    assert m["role"] == "modern_reference_only"
    assert m["is_1609_reconstruction"] is False
    assert m["fcode_counts"] == {"46006": 1, "55800": 1}
    assert len(m["raw_sha256"]) == 64
    assert output.with_suffix(".manifest.json").exists()
    raw_features = json.loads(raw.read_text())["features"]
    derived = json.loads(output.read_text())["features"]
    assert [f["properties"]["OBJECTID"] for f in derived] == [3, 7]
    assert raw_features[0]["geometry"]["coordinates"][0] == [-74.2, 40.7]
    assert shape(derived[0]["geometry"]).bounds[0] == pytest.approx(-74.12)
    assert derived[0]["properties"]["clipped_to_pilot_bbox"] is True
    assert derived[1]["properties"]["clipped_to_pilot_bbox"] is False
    assert "not the New Jersey portion" in " ".join(m["limitations"])


def test_missing_features_rejected_before_writing(tmp_path):
    def broken(url):
        r = fake_service(url)
        if "features" in r:
            r["features"] = r["features"][:1]
        return r
    output = tmp_path / "out.geojson"
    with pytest.raises(ValueError, match="missing, extra or duplicate"):
        create_modern_flowlines(REGION, tmp_path / "raw.geojson", output, get_json=broken)
    assert not output.exists()


def test_duplicate_features_rejected(tmp_path):
    def broken(url):
        r = fake_service(url)
        if "features" in r:
            r["features"][1]["properties"]["OBJECTID"] = 7
        return r
    with pytest.raises(ValueError, match="duplicate"):
        create_modern_flowlines(REGION, tmp_path / "raw.geojson", tmp_path / "out.geojson", get_json=broken)


def test_service_error_and_empty_ids_rejected(tmp_path):
    with pytest.raises(ValueError, match="service error"):
        create_modern_flowlines(REGION, tmp_path / "raw.geojson", tmp_path / "out.geojson", get_json=lambda u: {"error": {"code": 500}})
    with pytest.raises(ValueError, match="no flowlines"):
        create_modern_flowlines(REGION, tmp_path / "raw.geojson", tmp_path / "out.geojson", get_json=lambda u: {"objectIds": []})


def test_cli_dry_run_has_no_side_effects(tmp_path, capsys):
    file = tmp_path / "region.json"
    file.write_text(json.dumps(REGION))
    assert main(["fetch-modern-hydro", "--region", str(file), "--dry-run"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["dry_run"] is True
    assert data["source"].startswith("https://gisservices.its.ny.gov/")
    assert not (tmp_path / "data").exists()
