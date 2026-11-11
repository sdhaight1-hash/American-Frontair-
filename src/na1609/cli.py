"""CLI entry point for verifiable research checkpoints."""
from __future__ import annotations

import argparse
import json
from glob import glob
from pathlib import Path

from .download import download_tiles
from .evidence import validate_features
from .geo import create_reference_dem, read_region
from .hydro import create_modern_flowlines, SERVICE
from .network import create_network, RiverNetwork, SERVICE as NETWORK_SERVICE
from .world_package import export_pilot, WorldPackage, attach_historical_constraints
from .historic_water import ingest_historical_water
from .historical_constraints import load_constraints
from .archival_map import acquire_maccoun_map, inspect_archival_map, IMAGE_URLS
from .pixel_traces import preview_pixel_traces, validate_pixel_traces


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="na1609", description="North America 1609 evidence-first GIS pipeline")
    sub = parser.add_subparsers(dest="command", required=True)
    fetch = sub.add_parser("fetch-dem", help="Fetch Copernicus reference COGs; no historical claims")
    fetch.add_argument("--region", type=Path, required=True)
    fetch.add_argument("--destination", type=Path, default=Path("data/raw/copernicus"))
    fetch.add_argument("--dry-run", action="store_true")
    ingest = sub.add_parser("ingest-dem", help="Clip/mosaic local Copernicus DEM COGs")
    ingest.add_argument("--region", type=Path, required=True)
    ingest.add_argument("--input", type=Path, nargs="+", required=True)
    ingest.add_argument("--output", type=Path, required=True)
    hydro = sub.add_parser("fetch-modern-hydro", help="Query NYS/USGS NHD modern-reference flowlines")
    hydro.add_argument("--region", type=Path, required=True)
    hydro.add_argument("--raw", type=Path, default=Path("data/raw/ny_nhd_flowlines.geojson"))
    hydro.add_argument("--output", type=Path, default=Path("data/derived/hudson_modern_flowlines.geojson"))
    hydro.add_argument("--dry-run", action="store_true")
    network = sub.add_parser("fetch-network", help="Fetch NHDPlusV2 source-connected river network (modern reference)")
    network.add_argument("--region", type=Path, required=True)
    network.add_argument("--raw", type=Path, default=Path("data/raw/nhdplusv2_flowlines.geojson"))
    network.add_argument("--output", type=Path, default=Path("data/derived/hudson_nhdplusv2_network.json"))
    network.add_argument("--pad-degrees", type=float, default=0.05)
    network.add_argument("--dry-run", action="store_true")
    historical = sub.add_parser("ingest-historic-water", help="Import cited 1609 water candidate geometry; never marks game world complete")
    historical.add_argument("--region", type=Path, required=True)
    historical.add_argument("--input", type=Path, required=True, help="Digitized source GeoJSON (image pixels or WGS84)")
    historical.add_argument("--metadata", type=Path, required=True, help="Source date, rights, controls, uncertainty, citations")
    historical.add_argument("--output", type=Path, required=True)
    evidence = sub.add_parser("check-evidence", help="Validate GeoJSON spatial historical evidence")
    evidence.add_argument("--region", type=Path, required=True)
    evidence.add_argument("--input", type=Path, required=True)
    package = sub.add_parser("export-pilot", help="Export offline simulation reference package (NOT a 1609 initial state)")
    package.add_argument("--region", type=Path, required=True)
    package.add_argument("--terrain", type=Path, required=True)
    package.add_argument("--flowlines", type=Path, required=True)
    package.add_argument("--evidence", type=Path, required=True)
    package.add_argument("--output", type=Path, required=True)
    package.add_argument("--network", type=Path, help="Optional verified source-connected NHDPlusV2 graph")
    package.add_argument("--historic-water", type=Path, help="Optional sourced historical candidate water, NOT confirmed 1609 state")
    package.add_argument("--historic-constraints", type=Path, help="Optional documentary topology with NO location geometry")
    check_constraints = sub.add_parser("check-historic-constraints", help="Validate documentary water relationships without inferring positions")
    check_constraints.add_argument("--region", type=Path, required=True)
    check_constraints.add_argument("--input", type=Path, required=True)
    overlay = sub.add_parser("attach-historic-constraints", help="Append validated documentary hints to an existing reference world")
    overlay.add_argument("--region", type=Path, required=True)
    overlay.add_argument("--package", type=Path, required=True)
    overlay.add_argument("--input", type=Path, required=True)
    overlay.add_argument("--output", type=Path, required=True)
    archive = sub.add_parser("fetch-archival-map", help="Archive NYPL MacCoun (1909) map scan; NOT georeferenced historical data")
    archive.add_argument("--output", type=Path, required=True)
    archive.add_argument("--quality", choices=sorted(IMAGE_URLS), default="original")
    archive.add_argument("--dry-run", action="store_true")
    inspect = sub.add_parser("inspect-archival-map", help="Verify archived historical image checksum and metadata")
    inspect.add_argument("--input", type=Path, required=True)
    pixel = sub.add_parser("inspect-pixel-traces", help="Validate sourced map-pixel outlines; never infer WGS84 coordinates")
    pixel.add_argument("--image", type=Path, required=True)
    pixel.add_argument("--traces", type=Path, required=True)
    pixel.add_argument("--preview", type=Path, help="Optional cropped visual QA PNG")
    query = sub.add_parser("query-pilot", help="Query exported offline package without GIS runtime")
    query.add_argument("--region", type=Path, required=True)
    query.add_argument("--package", type=Path, required=True)
    query.add_argument("--lon", type=float, required=True)
    query.add_argument("--lat", type=float, required=True)
    trace = sub.add_parser("trace-network", help="Trace upstream/downstream using source-confirmed node links offline")
    trace.add_argument("--package", type=Path, required=True)
    trace.add_argument("--comid", type=int, required=True)
    trace.add_argument("--direction", choices=["upstream", "downstream"], default="downstream")
    args = parser.parse_args(argv)
    if args.command == "fetch-archival-map":
        result = {"url": IMAGE_URLS[args.quality], "quality": args.quality, "dry_run": True} if args.dry_run else acquire_maccoun_map(args.output, quality=args.quality)
        print(json.dumps(result, indent=2))
        return 0
    if args.command == "inspect-archival-map":
        print(json.dumps(inspect_archival_map(args.input), indent=2))
        return 0
    if args.command == "inspect-pixel-traces":
        result = preview_pixel_traces(args.image, args.traces, args.preview) if args.preview else validate_pixel_traces(args.image, args.traces)
        print(json.dumps(result, indent=2))
        return 0
    if args.command == "trace-network":
        world = WorldPackage(args.package)
        if world.river_network is None:
            raise ValueError("package does not include an NHDPlusV2 network")
        print(json.dumps(world.river_network.trace(f"nhdplusv2:{args.comid}", direction=args.direction), indent=2))
        return 0
    region = read_region(args.region)
    if args.command == "fetch-dem":
        downloaded = download_tiles(region["bbox_wgs84"], args.destination, dry_run=args.dry_run)
        print(json.dumps({"downloaded": [str(x) for x in downloaded], "dry_run": args.dry_run}, indent=2))
    elif args.command == "ingest-dem":
        files = [Path(path) for pattern in args.input for path in sorted(glob(str(pattern)))]
        result = create_reference_dem(files, args.output, region)
        print(json.dumps(result, indent=2))
    elif args.command == "fetch-modern-hydro":
        if args.dry_run:
            result = {"source": SERVICE, "bbox_wgs84": region["bbox_wgs84"], "dry_run": True}
        else:
            result = create_modern_flowlines(region, args.raw, args.output)
        print(json.dumps(result, indent=2))
    elif args.command == "fetch-network":
        if args.dry_run:
            result = {"source": NETWORK_SERVICE, "bbox_wgs84": region["bbox_wgs84"],
                      "pad_degrees": args.pad_degrees, "dry_run": True}
        else:
            result = create_network(region, args.raw, args.output, pad=args.pad_degrees)
        print(json.dumps(result, indent=2))
    elif args.command == "ingest-historic-water":
        result = ingest_historical_water(region, args.input, args.metadata, args.output)
        print(json.dumps(result, indent=2))
    elif args.command == "export-pilot":
        result = export_pilot(region, args.terrain, args.flowlines, args.evidence, args.output,
                              network=args.network, historic_water=args.historic_water,
                              historic_constraints=args.historic_constraints)
        print(json.dumps(result, indent=2))
    elif args.command == "check-historic-constraints":
        _, stats = load_constraints(args.input, region)
        print(json.dumps(stats, indent=2))
    elif args.command == "attach-historic-constraints":
        print(json.dumps(attach_historical_constraints(region, args.package, args.input, args.output), indent=2))
    elif args.command == "query-pilot":
        world = WorldPackage(args.package)
        result = {"elevation_modern_reference_m": world.elevation_at(args.lon, args.lat),
                  "nearby_bbox_candidate_reaches": len(world.reaches_in_bbox([args.lon - 0.001, args.lat - 0.001, args.lon + 0.001, args.lat + 0.001])),
                  "is_1609_initial_state": world.manifest["is_1609_initial_state"],
                  "historical_water_documentary_count": len(world.historical_water_constraints["features"]) if world.historical_water_constraints else 0,
                  "historical_water_candidate_count": len(world.historic_water_in_bbox([args.lon - 0.001, args.lat - 0.001, args.lon + 0.001, args.lat + 0.001]))}
        print(json.dumps(result, indent=2))
    else:
        result = validate_features(args.input, year=region["target_year"], bbox=region["bbox_wgs84"])
        print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
