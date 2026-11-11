"""Regression and real-documentary-evidence tests: no fabricated 1609 coordinates."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from na1609.historical_constraints import validate_constraints, load_constraints
from na1609.world_package import WorldPackage, export_pilot
from test_world_package import setup_inputs

DATA = Path(__file__).resolve().parents[1] / "data/historical/hudson_1609_documentary_constraints.json"
REGION = {"id": "lower_hudson_pilot", "target_year": 1609, "bbox_wgs84": [-74.12, 40.64, -73.82, 40.90]}


def sample():
    return json.loads(DATA.read_text())


def test_real_documentary_constraints_are_cited_and_unlocated():
    data, stats = load_constraints(DATA, REGION)
    assert stats == {"feature_count": 2, "source_count": 2, "directed_relationship_count": 2}
    assert data["features"][0]["geometry"] is None
    assert data["features"][1]["relations"] == [{"type": "flows_to", "target": "maiden_lane_stream"}]
    assert data["sources"][0]["publication_year"] == 2010
    assert data["sources"][1]["publication_year"] == 1909


@pytest.mark.parametrize("mutation, error", [
    (lambda d: d["features"][0].update(geometry={"type":"Point","coordinates":[-74,40.7]}), "coordinates"),
    (lambda d: d["features"][0].update(confidence="certain"), "confidence"),
    (lambda d: d["features"][0].update(evidence_class="observed_in_1609"), "observed"),
    (lambda d: d["features"][0].update(source_ids=["unknown"]), "source"),
    (lambda d: d["features"][0]["relations"].append({"type":"flows_to","target":"unmapped_channel"}), "relation"),
    (lambda d: d["features"][0]["relations"].append({"type":"flows_to","target":"william_street_tributary"}), "cycle"),
    (lambda d: d["features"][1].update(id="maiden_lane_stream"), "duplicate"),
    (lambda d: d["sources"][0].update(locator=""), "locator"),
])
def test_reject_historical_misrepresentation(mutation, error):
    d = sample()
    mutation(d)
    with pytest.raises(ValueError, match=error):
        validate_constraints(d, REGION)


def test_region_mismatch_refused():
    with pytest.raises(ValueError, match="different region"):
        validate_constraints(sample(), {**REGION, "id": "canadian_pilot"})


def test_export_offline_query_and_integrity(tmp_path):
    # Existing synthetic reference raster/flowline inputs permit an isolated package test;
    # the archival constraints are factual and do not acquire synthetic geometries.
    t, h, e = setup_inputs(tmp_path)
    region = {"id": "test_pilot", "target_year": 1609, "bbox_wgs84": [-74.5, 40.0, -73.5, 41.0]}
    data = sample()
    data["region_id"] = region["id"]
    inp = tmp_path / "archive.json"
    inp.write_text(json.dumps(data))
    output = tmp_path / "world"
    export_pilot(region, t, h, e, output, historic_constraints=inp)
    game = WorldPackage(output)
    evidence = game.historical_water_constraint("maiden_lane_stream")
    assert evidence["geometry"] is None
    assert evidence["relations"][0] == {"type": "flows_to", "target": "east_river"}
    assert game.historical_water_constraint("unknown") is None
    assert game.manifest["is_1609_initial_state"] is False
    assert game.manifest["layers"]["historical_water_constraints"]["counts"]["feature_count"] == 2
    with pytest.raises(RuntimeError, match="NOT available"):
        game.require_1609_initial_state()
    (output / "historical_water_constraints.json").write_text("{}")
    with pytest.raises(ValueError, match="integrity"):
        WorldPackage(output)


def test_deterministic_documentary_export(tmp_path):
    t, h, e = setup_inputs(tmp_path)
    r = {"id": "test_pilot", "target_year": 1609, "bbox_wgs84": [-74.5, 40.0, -73.5, 41.0]}
    d = sample(); d["region_id"] = r["id"]
    inp = tmp_path / "archive.json"; inp.write_text(json.dumps(d))
    export_pilot(r, t, h, e, tmp_path / "a", historic_constraints=inp)
    export_pilot(r, t, h, e, tmp_path / "b", historic_constraints=inp)
    for path in (tmp_path / "a").iterdir():
        assert hashlib.sha256(path.read_bytes()).digest() == hashlib.sha256((tmp_path / "b" / path.name).read_bytes()).digest()


def test_patch_package_preserves_baseline_and_rejects_reinstallation(tmp_path):
    from na1609.world_package import attach_historical_constraints
    t, h, e = setup_inputs(tmp_path)
    r = {"id": "test_pilot", "target_year": 1609, "bbox_wgs84": [-74.5, 40.0, -73.5, 41.0]}
    d = sample(); d["region_id"] = r["id"]
    inp = tmp_path / "archive.json"; inp.write_text(json.dumps(d))
    original = tmp_path / "baseline"
    export_pilot(r, t, h, e, original)
    dest = tmp_path / "with_history"
    result = attach_historical_constraints(r, original, inp, dest)
    assert not (original / "historical_water_constraints.json").exists()
    assert WorldPackage(original).historical_water_constraints is None
    assert WorldPackage(dest).historical_water_constraint("william_street_tributary") is not None
    assert result["is_1609_initial_state"] is False
    assert (original / "terrain.f32").read_bytes() == (dest / "terrain.f32").read_bytes()
    assert (original / "reaches.json").read_bytes() == (dest / "reaches.json").read_bytes()
    with pytest.raises(ValueError, match="already installed"):
        attach_historical_constraints(r, dest, inp, tmp_path / "duplicate")


def test_patch_package_refuses_tampered_world(tmp_path):
    from na1609.world_package import attach_historical_constraints
    t, h, e = setup_inputs(tmp_path)
    r = {"id": "test_pilot", "target_year": 1609, "bbox_wgs84": [-74.5, 40.0, -73.5, 41.0]}
    d = sample(); d["region_id"] = r["id"]
    inp = tmp_path / "archive.json"; inp.write_text(json.dumps(d))
    original = tmp_path / "original"
    export_pilot(r, t, h, e, original)
    (original / "reaches.json").write_text("corrupted")
    with pytest.raises(ValueError, match="integrity"):
        attach_historical_constraints(r, original, inp, tmp_path / "modified")
