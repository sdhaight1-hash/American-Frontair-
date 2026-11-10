"""Synthetic fixture tests for an offline game-facing reference package.

These samples are not historic environmental evidence.
"""
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from na1609.cli import main
from na1609.geo import sha256_file
from na1609.world_package import WorldPackage, export_pilot

REGION = {"id": "test_pilot", "target_year": 1609, "bbox_wgs84": [-74.5, 40.0, -73.5, 41.0]}


def setup_inputs(tmp_path):
    terrain = tmp_path / "terrain_reference.tif"
    with rasterio.open(terrain, "w", driver="GTiff", width=2, height=2, count=1,
                       dtype="float32", crs="EPSG:4326", nodata=np.nan,
                       transform=from_origin(-74.5, 41.0, 0.5, 0.5)) as t:
        t.write(np.array([[10, 20], [30, np.nan]], dtype="float32"), 1)
    flowlines = tmp_path / "flow_reference.geojson"
    flowlines.write_text(json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": "LineString", "coordinates": [[-74.4, 40.2], [-74.2, 40.4]]},
         "properties": {"Permanent_Identifier": "42", "OBJECTID": 9, "FCode": 46006,
                        "clipped_to_pilot_bbox": True, "GNIS_Name": "Test", "FlowDir": 1}},
    ]}))
    evidence = tmp_path / "evidence.geojson"
    evidence.write_text(json.dumps({"type": "FeatureCollection", "features": []}))
    for file, role, layer, source in (
        (terrain, "modern_reference_only", "terrain_elevation", "test_dem"),
        (flowlines, "modern_reference_only", "flowlines", "test_nhd"),
    ):
        file.with_suffix(".manifest.json").write_text(json.dumps({
            "role": role, "is_1609_reconstruction": False, "layer": layer, "region_id": REGION["id"],
            "historical_target_year": 1609, "requested_bbox_wgs84": REGION["bbox_wgs84"],
            "output_sha256": sha256_file(file), "source_id": source,
        }))
    return terrain, flowlines, evidence


def test_export_and_offline_reader_preserve_modern_label(tmp_path):
    terrain, flow, evidence = setup_inputs(tmp_path)
    output = tmp_path / "world"
    result = export_pilot(REGION, terrain, flow, evidence, output)
    assert result["schema"].endswith(".v1")
    assert result["is_1609_initial_state"] is False
    assert result["layers"]["flowlines"]["topology"] == "unresolved"
    world = WorldPackage(output)
    assert world.elevation_at(-74.25, 40.75) == pytest.approx(10)
    assert world.elevation_at(-73.75, 40.75) == pytest.approx(20)
    assert world.elevation_at(-73.75, 40.25) is None  # nodata
    assert world.elevation_at(-74.6, 40.5) is None  # outside pilot
    assert world.reaches_in_bbox([-74.45, 40.15, -74.15, 40.45])[0]["id"] == "nhd:42"
    assert world.reaches_in_bbox([-73.9, 40.8, -73.8, 40.9]) == []
    assert world.reaches[0]["topology"]["upstream_ids"] is None
    assert world.reaches[0]["topology"]["may_continue_outside_region"] is True
    with pytest.raises(RuntimeError, match="NOT available"):
        world.require_1609_initial_state()


def test_export_is_byte_deterministic(tmp_path):
    terrain, flow, evidence = setup_inputs(tmp_path)
    export_pilot(REGION, terrain, flow, evidence, tmp_path / "one")
    export_pilot(REGION, terrain, flow, evidence, tmp_path / "two")
    a = tmp_path / "one"
    b = tmp_path / "two"
    for file in a.iterdir():
        assert hashlib.sha256(file.read_bytes()).digest() == hashlib.sha256((b / file.name).read_bytes()).digest()


def test_reject_tampered_reference_manifest(tmp_path):
    terrain, flow, evidence = setup_inputs(tmp_path)
    flow.write_text(flow.read_text() + "\n")
    with pytest.raises(ValueError, match="SHA-256"):
        export_pilot(REGION, terrain, flow, evidence, tmp_path / "world")


def test_reject_duplicate_permanent_ids(tmp_path):
    terrain, flow, evidence = setup_inputs(tmp_path)
    doc = json.loads(flow.read_text())
    doc["features"].append(doc["features"][0])
    flow.write_text(json.dumps(doc))
    info = json.loads(flow.with_suffix(".manifest.json").read_text())
    info["output_sha256"] = sha256_file(flow)
    flow.with_suffix(".manifest.json").write_text(json.dumps(info))
    with pytest.raises(ValueError, match="duplicate permanent"):
        export_pilot(REGION, terrain, flow, evidence, tmp_path / "world")


def test_refuse_to_overwrite_and_verify_integrity(tmp_path):
    terrain, flow, evidence = setup_inputs(tmp_path)
    out = tmp_path / "world"
    export_pilot(REGION, terrain, flow, evidence, out)
    with pytest.raises(FileExistsError):
        export_pilot(REGION, terrain, flow, evidence, out)
    (out / "reaches.json").write_text("{}")
    with pytest.raises(ValueError, match="integrity"):
        WorldPackage(out)


def test_cli_exports_and_queries_offline(tmp_path, capsys):
    terrain, flow, evidence = setup_inputs(tmp_path)
    reg = tmp_path / "region.json"
    reg.write_text(json.dumps(REGION))
    out = tmp_path / "pilot"
    assert main(["export-pilot", "--region", str(reg), "--terrain", str(terrain),
                 "--flowlines", str(flow), "--evidence", str(evidence), "--output", str(out)]) == 0
    capsys.readouterr()
    assert main(["query-pilot", "--region", str(reg), "--package", str(out),
                 "--lon", "-74.25", "--lat", "40.75"]) == 0
    response = json.loads(capsys.readouterr().out)
    assert response["elevation_modern_reference_m"] == 10.0
    assert response["is_1609_initial_state"] is False
