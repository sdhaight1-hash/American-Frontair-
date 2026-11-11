"""Only invented *test* networks; none is claimed to describe real 1609 geography."""
import json
from urllib.parse import parse_qs, urlparse

import pytest

from na1609.network import RiverNetwork, build_network, create_network, fetch_features
from na1609.world_package import WorldPackage, export_pilot
from test_world_package import setup_inputs, REGION as REF_REGION

REGION = {"id": "hudson_test", "target_year": 1609, "bbox_wgs84": [-74.12, 40.64, -73.82, 40.90]}
CONTEXT = [-74.17, 40.59, -73.77, 40.95]


def item(comid, start, end, coordinates, *, flowdir="With Digitized", **kwargs):
    return {"type": "Feature", "properties": {
        "comid": comid, "fromnode": start, "tonode": end,
        "flowdir": flowdir, "startflag": 0, "terminalfl": 0, **kwargs},
        "geometry": {"type": "LineString", "coordinates": coordinates}}


def sample_features():
    return [
        item(10, 1, 3, [[-74.08, 40.70], [-74.04, 40.75]], startflag=1),
        item(11, 2, 3, [[-74.07, 40.72], [-74.04, 40.75]], startflag=1),
        item(12, 3, 4, [[-74.04, 40.75], [-73.84, 40.85]]),
        item(13, 4, 5, [[-73.79, 40.85], [-73.78, 40.86]]),
        item(14, 4, 6, [[-73.84, 40.85], [-73.81, 40.93]]),
        item(15, 7, 8, [[-74.02, 40.68], [-73.99, 40.68]], flowdir="Uninitialized"),
    ]


def test_graph_uses_authoritative_nodes_for_confluence_and_divergence():
    graph = build_network(sample_features(), REGION["bbox_wgs84"], CONTEXT)
    net = RiverNetwork(graph)
    assert graph["statistics"]["directed_edge_count"] == 4
    assert graph["statistics"]["cross_pilot_boundary_edge_count"] == 1
    assert net.reaches["nhdplusv2:12"]["upstream_ids"] == ["nhdplusv2:10", "nhdplusv2:11"]
    assert net.reaches["nhdplusv2:12"]["downstream_ids"] == ["nhdplusv2:13", "nhdplusv2:14"]
    assert net.reaches["nhdplusv2:11"]["upstream_end"] == "source_headwater"
    assert net.reaches["nhdplusv2:13"]["downstream_end"] == "unresolved_or_outside_context"
    assert net.reaches["nhdplusv2:15"]["direction_status"] == "unresolved_flow_direction"
    traced = net.trace("nhdplusv2:12")
    assert traced["reach_ids"] == ["nhdplusv2:12", "nhdplusv2:13", "nhdplusv2:14"]
    assert traced["network_complete"] is False
    assert set(traced["unresolved_end_ids"]) == {"nhdplusv2:13", "nhdplusv2:14"}
    assert net.trace("nhdplusv2:12", direction="upstream")["reach_ids"] == ["nhdplusv2:10", "nhdplusv2:11", "nhdplusv2:12"]


def test_duplicate_comid_and_bad_direction_rejected():
    with pytest.raises(ValueError, match="duplicate COMID"):
        build_network(sample_features() + [sample_features()[0]], REGION["bbox_wgs84"], CONTEXT)
    bad = item(16, None, 9, [[-74.01, 40.72], [-74.00, 40.73]])
    with pytest.raises(ValueError, match="fromnode"):
        build_network([bad], REGION["bbox_wgs84"], CONTEXT)


def test_graph_is_not_inferred_from_nearby_coordinates():
    feats = [
        item(1, 10, 11, [[-74.1, 40.7], [-74.0, 40.8]]),
        item(2, 12, 13, [[-74.0, 40.8], [-73.9, 40.8]]),
    ]
    net = RiverNetwork(build_network(feats, REGION["bbox_wgs84"], CONTEXT))
    assert net.reaches["nhdplusv2:1"]["downstream_ids"] == []
    assert net.reaches["nhdplusv2:2"]["upstream_ids"] == []


def test_pagination_uses_number_matched_and_catches_missing_page():
    coords = [[-74, 40.7], [-73.95, 40.75]]
    records = [item(i, i * 10, i * 10 + 1, coords) for i in range(1, 502)]
    def service(url):
        params = parse_qs(urlparse(url).query)
        assert params["limit"] == ["500"]
        offset = int(params["offset"][0])
        page = records[offset:offset + 500]
        return {"type": "FeatureCollection", "numberMatched": 501,
                "numberReturned": len(page), "features": page}
    assert len(fetch_features(tuple(CONTEXT), get_json=service)) == 501
    def incomplete(url):
        out = service(url)
        out["features"] = out["features"][:1]
        out["numberReturned"] = len(out["features"])
        return out
    with pytest.raises(ValueError, match="truncated"):
        fetch_features(tuple(CONTEXT), get_json=incomplete)


def test_graph_source_files_preserved_and_verified(tmp_path):
    def service(url):
        assert "nhdflowline_network" in url
        return {"type": "FeatureCollection", "numberMatched": 6,
                "numberReturned": 6, "features": sample_features()}
    raw, output = tmp_path / "source.geojson", tmp_path / "network.json"
    meta = create_network(REGION, raw, output, get_json=service)
    assert meta["source_id"] == "usgs_nhdplusv2"
    assert meta["statistics"]["pilot_reach_count"] == 5
    graph = json.loads(output.read_text())
    assert graph["is_1609_reconstruction"] is False
    assert len(json.loads(raw.read_text())["features"]) == 6
    assert output.with_suffix(".manifest.json").exists()


def test_reference_package_can_trace_separate_network(tmp_path):
    terrain, flow, evidence = setup_inputs(tmp_path)
    region = REF_REGION
    sample = [item(1, 10, 20, [[-74.4, 40.3], [-74.1, 40.4]]),
              item(2, 20, 30, [[-74.1, 40.4], [-73.8, 40.5]])]
    net_path = tmp_path / "network.json"
    data = build_network(sample, region["bbox_wgs84"], region["bbox_wgs84"])
    net_path.write_text(json.dumps(data))
    from na1609.geo import sha256_file
    net_path.with_suffix(".manifest.json").write_text(json.dumps({
        "region_id": region["id"], "historical_target_year": region["target_year"],
        "layer": "nhdplusv2_network", "role": "modern_reference_only", "is_1609_reconstruction": False,
        "requested_bbox_wgs84": region["bbox_wgs84"],
        "output_sha256": sha256_file(net_path),
    }))
    export_pilot(region, terrain, flow, evidence, tmp_path / "world", network=net_path)
    world = WorldPackage(tmp_path / "world")
    assert world.river_network is not None
    assert world.river_network.trace("nhdplusv2:1")["reach_ids"] == ["nhdplusv2:1", "nhdplusv2:2"]
    assert world.reaches[0]["id"] == "nhd:42"  # separate NHD identity namespace
    assert world.manifest["is_1609_initial_state"] is False
    (tmp_path / "world" / "river_network.json").write_text("{}")
    with pytest.raises(ValueError, match="integrity"):
        WorldPackage(tmp_path / "world")
