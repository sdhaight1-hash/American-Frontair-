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
from .world_package import export_pilot, WorldPackage


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
    evidence = sub.add_parser("check-evidence", help="Validate GeoJSON spatial historical evidence")
    evidence.add_argument("--region", type=Path, required=True)
    evidence.add_argument("--input", type=Path, required=True)
    package = sub.add_parser("export-pilot", help="Export offline simulation reference package (NOT a 1609 initial state)")
    package.add_argument("--region", type=Path, required=True)
    package.add_argument("--terrain", type=Path, required=True)
    package.add_argument("--flowlines", type=Path, required=True)
    package.add_argument("--evidence", type=Path, required=True)
    package.add_argument("--output", type=Path, required=True)
    query = sub.add_parser("query-pilot", help="Query exported offline package without GIS runtime")
    query.add_argument("--region", type=Path, required=True)
    query.add_argument("--package", type=Path, required=True)
    query.add_argument("--lon", type=float, required=True)
    query.add_argument("--lat", type=float, required=True)
    args = parser.parse_args(argv)
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
    elif args.command == "export-pilot":
        result = export_pilot(region, args.terrain, args.flowlines, args.evidence, args.output)
        print(json.dumps(result, indent=2))
    elif args.command == "query-pilot":
        world = WorldPackage(args.package)
        result = {"elevation_modern_reference_m": world.elevation_at(args.lon, args.lat),
                  "nearby_bbox_candidate_reaches": len(world.reaches_in_bbox([args.lon - 0.001, args.lat - 0.001, args.lon + 0.001, args.lat + 0.001])),
                  "is_1609_initial_state": world.manifest["is_1609_initial_state"]}
        print(json.dumps(result, indent=2))
    else:
        result = validate_features(args.input, year=region["target_year"], bbox=region["bbox_wgs84"])
        print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
