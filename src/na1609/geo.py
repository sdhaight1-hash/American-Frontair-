"""Create an auditable modern *reference* elevation raster from local source COGs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.merge import merge
from rasterio.warp import transform_bounds


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_bbox(bbox: list[float] | tuple[float, ...]) -> tuple[float, float, float, float]:
    if len(bbox) != 4 or not all(np.isfinite(bbox)):
        raise ValueError("bbox must contain four finite numbers: west south east north")
    west, south, east, north = map(float, bbox)
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise ValueError("invalid WGS84 bbox or antimeridian-crossing bbox")
    return west, south, east, north


def read_region(path: Path) -> dict:
    region = json.loads(path.read_text(encoding="utf-8"))
    region["bbox_wgs84"] = validate_bbox(region["bbox_wgs84"])
    if not isinstance(region.get("target_year"), int):
        raise ValueError("region target_year must be an integer")
    return region


def create_reference_dem(input_paths: list[Path], output: Path, region: dict) -> dict:
    """Mosaic and clip source rasters; fail if missing coverage or incompatible CRS.

    This is NOT a 1609 bare-earth reconstruction. The label is enforced in metadata.
    """
    if not input_paths:
        raise ValueError("at least one DEM source file is required")
    paths = [Path(path) for path in input_paths]
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(path)
    bbox = validate_bbox(region["bbox_wgs84"])
    sources = []
    try:
        for path in paths:
            ds = rasterio.open(path)
            sources.append(ds)
            if ds.count != 1:
                raise ValueError(f"expected single-band DEM: {path}")
            if ds.crs is None or ds.crs.to_epsg() != 4326:
                raise ValueError(f"only WGS84 geographic DEM tiles supported in pilot: {path}")
            if ds.res[0] <= 0 or ds.res[1] <= 0:
                raise ValueError(f"invalid cell size: {path}")
        # A mosaic is clipped to the requested geographic bbox. Use the finest
        # source resolution so input ordering cannot silently reduce detail.
        resolution = (min(ds.res[0] for ds in sources), min(ds.res[1] for ds in sources))
        mosaic, transform = merge(
            sources,
            bounds=bbox,
            res=resolution,
            nodata=np.nan,
            masked=True,
            dtype="float32",
        )
        data = np.asarray(mosaic[0].filled(np.nan), dtype=np.float32)
        finite = np.isfinite(data)
        if not finite.any():
            raise ValueError("no valid DEM samples intersect region")
        output.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(
            output,
            "w",
            driver="GTiff",
            height=data.shape[0],
            width=data.shape[1],
            count=1,
            dtype="float32",
            crs="EPSG:4326",
            transform=transform,
            nodata=np.nan,
            compress="deflate",
            predictor=3,
        ) as dst:
            dst.write(data, 1)
            dst.update_tags(
                dataset_role="modern_reference_only",
                target_historical_year=str(region["target_year"]),
                historical_reconstruction="false",
            )
    finally:
        for ds in sources:
            ds.close()

    manifest = {
        "schema_version": 1,
        "region_id": region["id"],
        "historical_target_year": region["target_year"],
        "layer": "terrain_elevation",
        "role": "modern_reference_only",
        "is_1609_reconstruction": False,
        "source_id": "copernicus_dem_glo30",
        "vertical_units": "metres (source elevation datum retained; no vertical datum conversion)",
        "crs": "EPSG:4326",
        "requested_bbox_wgs84": list(bbox),
        "sample_dimensions": [int(data.shape[0]), int(data.shape[1])],
        "valid_pixel_fraction": round(float(finite.mean()), 8),
        "source_files": [
            {"name": p.name, "sha256": sha256_file(p)} for p in paths
        ],
        "output_file": output.name,
        "output_sha256": sha256_file(output),
        "limitations": [
            "Copernicus GLO-30 is a modern digital surface model, not historical bare-earth elevation.",
            "No historical shoreline, river, reservoir, building, or vegetation height correction applied.",
            "Nodata and ocean cells may be present; the output is a regional clip, not a complete continent.",
        ],
    }
    manifest_path = output.with_suffix(".manifest.json")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest
