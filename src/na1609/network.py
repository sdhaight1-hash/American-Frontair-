"""Source-directed NHDPlusV2 flowline graph for an offline game world reference.

A spatially buffered subset is NOT a complete catchment or an historical network.
Graph adjacency comes from USGS FromNode/ToNode, not from geometric proximity.
"""
from __future__ import annotations

import json
from collections import defaultdict, deque
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .runtime import sha256_file, validate_bbox, atomic_json

SERVICE = "https://api.water.usgs.gov/fabric/pygeoapi/collections/nhdflowline_network/items"
SCHEMA = "na1609.nhdplusv2-network.v1"
PAGE_SIZE = 500
MAX_FEATURES = 30000
# Degrees are for query context, not a prescribed hydrological or physical buffer.
DEFAULT_PAD_DEGREES = 0.05


def _integer(value, field: str, *, positive=True) -> int:
    if type(value) is int:
        n = value
    elif isinstance(value, float) and value.is_integer() and 0 <= value <= 2**53:
        n = int(value)
    elif isinstance(value, str) and value.isdecimal():
        n = int(value)
    else:
        raise ValueError(f"invalid {field}: {value!r}")
    if positive and n <= 0:
        raise ValueError(f"invalid {field}: {n}")
    return n


def _field(props: dict, name: str):
    return next((v for k, v in props.items() if k.lower() == name.lower()), None)


def _with_digitized(value) -> bool:
    return value == 1 or (isinstance(value, str) and value.lower().replace(" ", "") in ("withdigitized", "1"))


def _extended_bbox(bbox: tuple[float, float, float, float], pad: float) -> tuple[float, float, float, float]:
    if not (0 < pad <= 0.25):
        raise ValueError("context padding must be > 0 and <= 0.25 degrees")
    w, s, e, n = bbox
    return validate_bbox([w - pad, s - pad, e + pad, n + pad])


def fetch_features(bbox: tuple[float, float, float, float], *, get_json=None) -> list[dict]:
    """Read every OGC API Features page; reject mismatched counts and duplicate COMIDs."""
    if get_json is None:
        def get_json(url):
            with urlopen(Request(url, headers={"User-Agent": "NA1609-research/0.2"}), timeout=90) as response:
                return json.load(response)
    records = []
    total = None
    seen = set()
    for offset in range(0, MAX_FEATURES + PAGE_SIZE, PAGE_SIZE):
        if offset == MAX_FEATURES:
            raise ValueError("NHDPlusV2 query exceeds max permitted features")
        url = SERVICE + "?" + urlencode({"bbox": ",".join(map(str, bbox)), "limit": PAGE_SIZE, "offset": offset})
        page = get_json(url)
        if not isinstance(page, dict) or page.get("type") != "FeatureCollection" or not isinstance(page.get("features"), list):
            raise ValueError("invalid NHDPlusV2 OGC API response")
        if isinstance(page.get("numberMatched"), int):
            if total is not None and page["numberMatched"] != total:
                raise ValueError("NHDPlusV2 result count changed during pagination")
            total = page["numberMatched"]
            if total > MAX_FEATURES:
                raise ValueError("NHDPlusV2 query exceeds max permitted features")
        items = page["features"]
        if len(items) > PAGE_SIZE or (isinstance(page.get("numberReturned"), int) and page["numberReturned"] != len(items)):
            raise ValueError("NHDPlusV2 page size inconsistent")
        for item in items:
            key = _integer(_field(item.get("properties", {}), "comid"), "comid")
            if key in seen:
                raise ValueError(f"duplicate COMID in paginated results: {key}")
            seen.add(key)
            records.append(item)
        if total is not None and len(records) >= total:
            if len(records) != total:
                raise ValueError("NHDPlusV2 returned too many records")
            break
        if len(items) < PAGE_SIZE:
            if total is not None and len(records) != total:
                raise ValueError("NHDPlusV2 response truncated before numberMatched")
            break
    else:
        raise ValueError("unbounded NHDPlusV2 pages")
    if not records:
        raise ValueError("no NHDPlusV2 flowlines in query region")
    return records


def build_network(features: list[dict], bbox: list[float], context_bbox: list[float]) -> dict:
    """Build authoritative node-joined edges only when the USGS flow direction is usable."""
    from shapely.geometry import box, shape

    region = box(*validate_bbox(bbox))
    context = box(*validate_bbox(context_bbox))
    reaches = []
    seen = set()
    starts = defaultdict(list)
    ends = defaultdict(list)
    for feat in features:
        props = feat.get("properties")
        if not isinstance(props, dict):
            raise ValueError("flowline missing properties")
        comid = _integer(_field(props, "comid"), "comid")
        if comid in seen:
            raise ValueError(f"duplicate COMID: {comid}")
        seen.add(comid)
        geom = feat.get("geometry")
        if not isinstance(geom, dict) or geom.get("type") not in ("LineString", "MultiLineString"):
            raise ValueError(f"COMID {comid}: no linear geometry")
        linear = shape(geom)
        if linear.is_empty or not linear.is_valid or not linear.intersects(context):
            raise ValueError(f"COMID {comid}: invalid or outside requested context")
        direction = _with_digitized(_field(props, "flowdir"))
        upstream_node = _field(props, "fromnode")
        downstream_node = _field(props, "tonode")
        if direction:
            upstream_node = _integer(upstream_node, "fromnode")
            downstream_node = _integer(downstream_node, "tonode")
        else:
            upstream_node = downstream_node = None
        rid = f"nhdplusv2:{comid}"
        item = {
            "id": rid, "comid": comid, "source": "usgs_nhdplusv2",
            "geometry": geom,
            "name": _field(props, "gnis_name"), "fcode": _field(props, "fcode"),
            "stream_order": _field(props, "streamorde"),
            "from_node": upstream_node, "to_node": downstream_node,
            "direction_status": "confirmed_from_usgs_nodes" if direction else "unresolved_flow_direction",
            "inside_pilot": linear.intersects(region),
            "upstream_ids": [], "downstream_ids": [],
            "upstream_end": "unresolved", "downstream_end": "unresolved",
            "source_startflag": _field(props, "startflag"),
            "source_terminalflag": _field(props, "terminalfl"),
        }
        reaches.append(item)
        if direction:
            starts[upstream_node].append(rid)
            ends[downstream_node].append(rid)
    reaches.sort(key=lambda x: x["comid"])
    directed_edges = 0
    boundary_edges = 0
    by_id = {r["id"]: r for r in reaches}
    for r in reaches:
        if r["direction_status"] != "confirmed_from_usgs_nodes":
            continue
        r["upstream_ids"] = sorted((x for x in ends[r["from_node"]] if x != r["id"]), key=lambda x: int(x.split(":")[1]))
        r["downstream_ids"] = sorted((x for x in starts[r["to_node"]] if x != r["id"]), key=lambda x: int(x.split(":")[1]))
        r["upstream_end"] = "linked" if r["upstream_ids"] else ("source_headwater" if str(r["source_startflag"]) == "1" else "unresolved_or_outside_context")
        r["downstream_end"] = "linked" if r["downstream_ids"] else ("source_terminal" if str(r["source_terminalflag"]) == "1" else "unresolved_or_outside_context")
        for nxt in r["downstream_ids"]:
            directed_edges += 1
            boundary_edges += r["inside_pilot"] != by_id[nxt]["inside_pilot"]
    return {
        "schema": SCHEMA, "role": "modern_reference_only", "is_1609_reconstruction": False,
        "source_id": "usgs_nhdplusv2", "source_url": SERVICE,
        "bbox_wgs84": list(bbox), "query_context_bbox_wgs84": list(context_bbox),
        "coverage": "buffered_spatial_subset; unresolved ends are NOT automatically headwaters or outlets",
        "identity_namespace": "nhdplusv2:COMID; NOT equivalent to NHD Permanent_Identifier",
        "reaches": reaches,
        "statistics": {
            "reach_count": len(reaches),
            "pilot_reach_count": sum(r["inside_pilot"] for r in reaches),
            "directed_edge_count": directed_edges,
            "cross_pilot_boundary_edge_count": boundary_edges,
            "unresolved_upstream_ends": sum(r["upstream_end"] == "unresolved_or_outside_context" for r in reaches),
            "unresolved_downstream_ends": sum(r["downstream_end"] == "unresolved_or_outside_context" for r in reaches),
            "unknown_flow_direction": sum(r["direction_status"] == "unresolved_flow_direction" for r in reaches),
        },
    }


def create_network(region: dict, raw_path: Path, output: Path, *, pad: float = DEFAULT_PAD_DEGREES, get_json=None) -> dict:
    """Acquire a bounded spatial subset; preserve fetched source, graph, hashes."""
    bbox = validate_bbox(region["bbox_wgs84"])
    ext = _extended_bbox(bbox, pad)
    if raw_path == output:
        raise ValueError("raw source and derived network paths must differ")
    records = fetch_features(ext, get_json=get_json)
    graph = build_network(records, bbox, ext)
    graph["region_id"] = region["id"]
    graph["target_year"] = region["target_year"]
    atomic_json(raw_path, {"type": "FeatureCollection", "features": sorted(records, key=lambda f: _integer(_field(f["properties"], "comid"), "comid"))})
    atomic_json(output, graph)
    manifest = {
        "schema_version": 1, "region_id": region["id"], "historical_target_year": region["target_year"],
        "layer": "nhdplusv2_network", "role": "modern_reference_only", "is_1609_reconstruction": False,
        "requested_bbox_wgs84": list(bbox), "context_bbox_wgs84": list(ext),
        "source_id": "usgs_nhdplusv2", "source_url": SERVICE,
        "source_dataset": "National Hydrography Dataset Plus Version 2 (medium-resolution network)",
        "raw_sha256": sha256_file(raw_path), "output_sha256": sha256_file(output),
        "statistics": graph["statistics"],
        "limitations": ["Modern NHDPlusV2; not historical 1609 drainage.",
                        "Graph is partial; endpoints outside the queried context remain unresolved.",
                        "Do not merge this COMID graph with the separate NHD Permanent_Identifier reaches without an explicit supported crosswalk.",
                        "FromNode/ToNode do not capture all non-geometric flow table connections; a complete graph requires the authoritative PlusFlow table."],
    }
    atomic_json(output.with_suffix(".manifest.json"), manifest)
    return manifest


class RiverNetwork:
    """Simple offline traversal of one verified graph; topology is never augmented by proximity."""

    def __init__(self, network: dict):
        if network.get("schema") != SCHEMA or network.get("role") != "modern_reference_only":
            raise ValueError("unsupported network or historical network mislabeled")
        self.network = network
        self.reaches = {r["id"]: r for r in network["reaches"]}
        if len(self.reaches) != len(network["reaches"]):
            raise ValueError("duplicate graph reach IDs")
        for reach in self.reaches.values():
            for neighbor in reach["upstream_ids"]:
                if neighbor not in self.reaches or reach["id"] not in self.reaches[neighbor]["downstream_ids"]:
                    raise ValueError("non-reciprocal upstream link")
            for neighbor in reach["downstream_ids"]:
                if neighbor not in self.reaches or reach["id"] not in self.reaches[neighbor]["upstream_ids"]:
                    raise ValueError("non-reciprocal downstream link")

    def trace(self, start_id: str, *, direction: str = "downstream", max_reaches: int = 10000) -> dict:
        if start_id not in self.reaches:
            raise KeyError(start_id)
        if direction not in ("upstream", "downstream"):
            raise ValueError("direction must be upstream or downstream")
        if not 1 <= max_reaches <= 100000:
            raise ValueError("invalid traversal limit")
        edge_key = f"{direction}_ids"
        end_key = f"{direction}_end"
        visited = set()
        pending = deque([start_id])
        unresolved = []
        while pending and len(visited) < max_reaches:
            rid = pending.popleft()
            if rid in visited:
                continue
            visited.add(rid)
            r = self.reaches[rid]
            if r[end_key] in ("unresolved", "unresolved_or_outside_context"):
                unresolved.append(rid)
            pending.extend(n for n in r[edge_key] if n not in visited)
        return {"reach_ids": sorted(visited, key=lambda x: int(x.split(":")[1])),
                "unresolved_end_ids": sorted(unresolved), "limit_reached": bool(pending),
                "network_complete": not pending and not unresolved}
