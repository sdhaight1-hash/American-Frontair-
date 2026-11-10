# American Frontair — North America 1609 data pipeline

This repository is the starting point for an evidence-traceable reconstruction of the **physical and ecological landscape of North America circa 1609** (Canada, United States, Mexico). It is deliberately **not** a renderer, game, nor a completed historical map.

**Checkpoint 0 status:** one modern elevation reference importer, a historical evidence validation contract, source inventory, and automated tests. No 1609 geography has been manufactured or asserted. The included historical GeoJSON has zero features until supported evidence has been digitized.

## Reproducible pilot: Lower Hudson River / New York Harbor

The pilot region is `regions/hudson_pilot.json`, EPSG:4326 bounds `[-74.12, 40.64, -73.82, 40.90]` and target year 1609. That bbox crosses the -74° meridian and requires **two** Copernicus one-degree DEM tiles. It is a research extent, not a claimed historical boundary.

### Environment

Python 3.10+ with local `rasterio`/GDAL support:

```bash
python -m pip install -e '.[test]'
pytest -q
```

### Acquire modern Copernicus DEM reference tiles

```bash
na1609 fetch-dem --region regions/hudson_pilot.json --dry-run
na1609 fetch-dem --region regions/hudson_pilot.json --destination data/raw/copernicus
```

The second command downloads public Copernicus DEM GeoTIFFs from the documented AWS S3 layout, directly to ignored `data/raw/copernicus/`. It has no AWS credentials requirement. It must be run in a network-enabled environment. Files are not redistributed here; comply with the Copernicus DEM license and attribution.

### Create an auditable modern reference elevation layer

```bash
na1609 ingest-dem \
  --region regions/hudson_pilot.json \
  --input data/raw/copernicus/*.tif \
  --output data/derived/hudson_modern_surface.tif
```

The output is a GeoTIFF and `hudson_modern_surface.manifest.json` containing the region, modern-reference-only status, input and output SHA-256 hashes, output dimensions, nodata coverage, limitations, and source identifiers. The importer will fail for incompatible CRS or no data coverage.

**Important:** Copernicus GLO-30 is a modern **digital surface model**, not a bare-earth DEM nor 1609 geography. It may contain modern building and tree canopy elevations, altered riverbanks, engineered shorelines, and infrastructure. The output is intentionally labeled `modern_reference_only`. No claims about 1609 should be derived from the raster without a separate, evidenced reconstruction.

### Check historical evidence features

```bash
na1609 check-evidence \
  --region regions/hudson_pilot.json \
  --input data/historical/hudson_1609_evidence.geojson
```

A historical feature must have valid GeoJSON geometry within the region, a unique `feature_id`, `valid_years` including 1609, a `basis` (`historic_map`, `archaeology`, `paleoenvironment`, `document`, `model`, or `inference`), a confidence category, and at least one citation specifying `source_id` and a retrievable `locator` (e.g. archive folio or publication figure). The empty starter collection is syntactically valid but **constitutes no historical evidence**.


### Acquire modern NHD reference flowlines (New York coverage only)

~~~bash
na1609 fetch-modern-hydro --region regions/hudson_pilot.json --dry-run
na1609 fetch-modern-hydro --region regions/hudson_pilot.json --raw data/raw/ny_nhd_flowlines.geojson --output data/derived/hudson_modern_flowlines.geojson
~~~

This queries the official NYS GIS Program Office USGS NHD flowline layer using an explicit bounding envelope plus object-ID batches. Original source features remain in ignored data/raw; the clipped derivatives get hashed provenance manifests. **This is modern reference data, not a 1609 reconstruction.** NYS coverage omits the New Jersey portion of the pilot; its feature codes include artificial channels, canals and coastline reaches. See [real-data NHD QA](docs/hudson_modern_hydro_qa.md). See [historical water research](docs/historical_water_reconstruction.md) and [source candidates](catalog/hudson_historical_sources.json).

## Dataset design principles

1. Preserve raw source bytes and processing checksums; do not modify originals.
2. Keep modern, reconstructed, and directly documented historical layers separate.
3. Retain native resolutions and coordinate references, exposing an integrated geospatial query interface later; do not upsample uncertainty into apparent accuracy.
4. Represent disagreements as alternate hypotheses, not as erased features.
5. Validate watershed connectivity, land/water topology, historical evidence, and modeled ecological consistency independently.
6. Preserve Indigenous and colonial-era landscape modifications; never treat 1609 as an uninhabited world.
7. Label missing datasets and gaps plainly; don't manufacture historical conditions to fill them.

## Next checkpoint

1. Successfully ingest and inspect real Copernicus tiles with their edit/quality masks, replace DSM artifacts with regional bare-earth terrain where available, and validate against independent elevation samples.
2. Add current river-network vectors for the Lower Hudson from HydroSHEDS v2 / authoritative regional hydrography and label them modern references.
3. Digitize and georeference genuinely sourced historical shorelines/wetlands from Welikia and archival documents, recording licensing, evidence dates, and registration error.
4. Reconstruct historically constrained surface-water and floodplain features, retaining alternatives where evidence is insufficient.
5. Add DPastCliM-NA temperature/precipitation baseline as modeled 1590–1629 climate, not measured 1609 weather.

`catalog/sources.json` is a source research inventory, not proof that source files are presently incorporated. `data/raw` and `data/derived` are intentionally not committed.
