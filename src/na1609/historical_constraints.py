"""Sourced, non-geometric historical water relationships for simulation initialization.

These constrain possible reconstructions but are NOT raster, vector, observed 1609
locations or ready-to-simulate water reaches. The source's depicted year must be
separate from its publication year and source-period evidence.
"""
from __future__ import annotations

import json
from pathlib import Path

SCHEMA = "na1609.water-constraints.v1"
ROLE = "historical_documentary_constraints_not_georeferenced"
ALLOWED_KINDS = {"stream", "river", "shoreline", "pond", "wetland"}
ALLOWED_CONFIDENCES = {"low", "medium", "high"}
ALLOWED_RELATIONS = {"flows_to", "receives_from"}


def validate_constraints(data: dict, region: dict) -> dict:
    """Validate historical references, topology, dating and lack of invented geometry."""
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        raise ValueError("unsupported documentary constraint schema")
    if data.get("region_id") != region["id"] or data.get("target_year") != region["target_year"]:
        raise ValueError("historical constraints target a different region or year")
    if data.get("role") != ROLE or data.get("coordinate_status") != "not_georeferenced":
        raise ValueError("historical documentary geometry must remain unlocated")
    sources = data.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("documentary constraints require archival sources")
    source_ids = set()
    for source in sources:
        if not isinstance(source, dict):
            raise ValueError("invalid source record")
        sid = source.get("id")
        if not isinstance(sid, str) or not sid.strip() or sid in source_ids:
            raise ValueError("duplicate or absent source id")
        source_ids.add(sid)
        if (not isinstance(source.get("url"), str) or not source["url"].startswith("https://") or
                not isinstance(source.get("locator"), str) or not source["locator"].strip() or
                type(source.get("publication_year")) is not int or source["publication_year"] < 1609):
            raise ValueError(f"source {sid}: publication year, URL, or exact locator missing")
    features = data.get("features")
    if not isinstance(features, list) or not features:
        raise ValueError("at least one sourced historical constraint required")
    known = set()
    for feature in features:
        if not isinstance(feature, dict):
            raise ValueError("invalid historical feature")
        fid = feature.get("id")
        if not isinstance(fid, str) or not fid.strip() or fid in known:
            raise ValueError("duplicate or absent historical feature id")
        known.add(fid)
        if feature.get("kind") not in ALLOWED_KINDS or feature.get("confidence") not in ALLOWED_CONFIDENCES:
            raise ValueError(f"{fid}: invalid kind or historical confidence")
        if feature.get("geometry") is not None or "coordinates" in feature or "bbox_wgs84" in feature:
            raise ValueError(f"{fid}: unsourced historical coordinates are forbidden")
        if feature.get("evidence_class") != "retrospective_reconstruction":
            raise ValueError(f"{fid}: historical assertions must not be presented as observed")
        if type(feature.get("depicted_year")) is not int or feature["depicted_year"] != region["target_year"]:
            raise ValueError(f"{fid}: unsupported depicted year")
        if not isinstance(feature.get("location_description"), str) or not feature["location_description"].strip():
            raise ValueError(f"{fid}: named location description required")
        refs = feature.get("source_ids")
        if not isinstance(refs, list) or not refs or any(ref not in source_ids for ref in refs):
            raise ValueError(f"{fid}: unresolved historical source citation")
        if not isinstance(feature.get("relations"), list):
            raise ValueError(f"{fid}: relationships must be explicit")
    external = data.get("named_external_waterbodies", [])
    if not isinstance(external, list) or any(not isinstance(x, str) or not x.strip() or x in known for x in external) or len(external) != len(set(external)):
        raise ValueError("invalid named external waterbodies")
    reachable = known | set(external)
    downstream = {fid: [] for fid in known}
    for feature in features:
        for edge in feature["relations"]:
            if not isinstance(edge, dict) or set(edge) != {"type", "target"}:
                raise ValueError("bad historical relation")
            relation, target = edge["type"], edge["target"]
            if relation not in ALLOWED_RELATIONS or target not in reachable or target == feature["id"]:
                raise ValueError("invalid historical relation target")
            if relation == "receives_from" and target in external:
                raise ValueError("external waterbody cannot be a source without feature evidence")
            if relation == "flows_to":
                downstream[feature["id"]].append(target)
            else:
                downstream[target].append(feature["id"])
    # A downstream relationship is directional evidence, not a measured flow rate.
    for fid, children in downstream.items():
        if len(children) != len(set(children)):
            raise ValueError(f"{fid}: duplicate or contradictory downstream relationship")
    color = {}
    def visit(node: str) -> None:
        if node in external:
            return
        if color.get(node) == 1:
            raise ValueError("directed cycle in historical water constraints")
        if color.get(node) == 2:
            return
        color[node] = 1
        for nxt in downstream[node]:
            visit(nxt)
        color[node] = 2
    for node in sorted(known):
        visit(node)
    return {"feature_count": len(features), "source_count": len(sources),
            "directed_relationship_count": sum(map(len, downstream.values()))}


def load_constraints(path: Path, region: dict) -> tuple[dict, dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    stats = validate_constraints(data, region)
    return data, stats
