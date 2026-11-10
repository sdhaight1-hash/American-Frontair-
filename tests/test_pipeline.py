import json
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from na1609.download import tile_urls
from na1609.evidence import validate_features
from na1609.geo import create_reference_dem, read_region, validate_bbox


def region():
    return {"id": "test", "target_year": 1609, "bbox_wgs84": [-74.5, 40.0, -73.5, 41.0]}


def test_hudson_needs_two_actual_copernicus_degree_tiles():
    urls = tile_urls([-74.12, 40.64, -73.82, 40.90])
    assert len(urls) == 2
    assert "W075_00" in urls[0]
    assert "W074_00" in urls[1]
    assert urls[0].endswith("_DEM.tif")


def test_bad_bbox_rejected():
    with pytest.raises(ValueError):
        validate_bbox([-73, 40, -74, 41])


def _raster(path: Path, west, values, crs="EPSG:4326"):
    with rasterio.open(
        path, "w", driver="GTiff", height=2, width=2, count=1, dtype="float32",
        crs=crs, transform=from_origin(west, 41, 0.5, 0.5), nodata=-9999,
    ) as ds:
        ds.write(np.asarray(values, dtype="float32"), 1)


def test_mosaic_provenance_and_data(tmp_path):
    left = tmp_path / "left.tif"
    right = tmp_path / "right.tif"
    _raster(left, -74.5, [[1, 2], [3, -9999]])
    _raster(right, -73.5, [[5, 6], [7, 8]])
    r = {"id": "test", "target_year": 1609, "bbox_wgs84": [-74.5, 40, -72.5, 41]}
    dest = tmp_path / "terrain.tif"
    manifest = create_reference_dem([left, right], dest, r)
    assert manifest["role"] == "modern_reference_only"
    assert manifest["is_1609_reconstruction"] is False
    assert manifest["valid_pixel_fraction"] == 0.875
    assert len(manifest["source_files"][0]["sha256"]) == 64
    assert dest.with_suffix(".manifest.json").exists()
    with rasterio.open(dest) as raster:
        cells = raster.read(1)
        assert cells.shape == (2, 4)
        assert cells[0].tolist() == [1, 2, 5, 6]
        assert np.isnan(cells[1, 1])
        assert raster.tags()["historical_reconstruction"] == "false"


def test_wrong_crs_rejected(tmp_path):
    p = tmp_path / "bad.tif"
    _raster(p, -74.5, [[1, 2], [3, 4]], crs="EPSG:3857")
    with pytest.raises(ValueError, match="WGS84"):
        create_reference_dem([p], tmp_path / "out.tif", region())


def test_no_intersection_rejected(tmp_path):
    p = tmp_path / "far.tif"
    _raster(p, -80, [[1, 2], [3, 4]])
    with pytest.raises(ValueError):
        create_reference_dem([p], tmp_path / "out.tif", region())


def _feature(basis="historic_map", year_range=(1590, 1620), citations=None):
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [-74, 40.75]},
        "properties": {
            "feature_id": "evidence-one",
            "feature_type": "historical_feature",
            "valid_years": list(year_range),
            "basis": basis,
            "confidence": "medium",
            "evidence": citations if citations is not None else [{"source_id": "archive", "locator": "folio 3"}],
        },
    }


def _write_features(path, features):
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}))


def test_evidence_requires_citation_and_year(tmp_path):
    file = tmp_path / "features.geojson"
    _write_features(file, [_feature()])
    result = validate_features(file, year=1609, bbox=[-74.2, 40.6, -73.8, 40.9])
    assert result["feature_count"] == 1
    _write_features(file, [_feature(citations=[])])
    with pytest.raises(ValueError, match="citation"):
        validate_features(file, year=1609, bbox=[-74.2, 40.6, -73.8, 40.9])
    _write_features(file, [_feature(year_range=(1700, 1750))])
    with pytest.raises(ValueError, match="1609"):
        validate_features(file, year=1609, bbox=[-74.2, 40.6, -73.8, 40.9])


def test_empty_evidence_collection_is_valid_but_not_evidence(tmp_path):
    file = tmp_path / "empty.geojson"
    _write_features(file, [])
    assert validate_features(file, year=1609, bbox=[-74.2, 40.6, -73.8, 40.9])["feature_count"] == 0
