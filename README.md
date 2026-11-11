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

### Acquire modern NHD flowlines (New York coverage only)

```bash
na1609 fetch-modern-hydro --region regions/hudson_pilot.json --dry-run
na1609 fetch-modern-hydro --region regions/hudson_pilot.json \
  --raw data/raw/ny_nhd_flowlines.geojson \
  --output data/derived/hudson_modern_flowlines.geojson
```

This queries the official NYS GIS Program Office's USGS NHD flowline layer via ArcGIS REST using an explicit region envelope and object-ID pagination. The original returned source features are saved to the ignored `data/raw` directory; derived vectors are clipped to the pilot and written alongside a hashed provenance manifest. **These flowlines are modern references, not 1609.** This New York State source does not cover the New Jersey part of the pilot; missing NJ features cannot be assumed absent. Flowline classes include constructed waterways and artificial paths, not simply natural streams.

See [historical water evidence gates](docs/historical_water_reconstruction.md) and the [historical source registry](catalog/hudson_historical_sources.json).


### Export a game/simulation-readable reference package (not historical 1609 yet)

After running the above DEM and NHD commands, create a deterministic offline package:

~~~bash
na1609 export-pilot --region regions/hudson_pilot.json --terrain data/derived/hudson_modern_surface.tif --flowlines data/derived/hudson_modern_flowlines.geojson --evidence data/historical/hudson_1609_evidence.geojson --output data/export/hudson-reference-world
na1609 query-pilot --region regions/hudson_pilot.json --package data/export/hudson-reference-world --lon -74.02 --lat 40.72
~~~

The package contains binary little-endian float32 terrain, a GeoJSON-compatible river reach collection with stable NHD source IDs, dated evidence features, and a checksummed JSON manifest. A game runtime can read it **offline without GDAL**. The bundled Python `WorldPackage` provides a reference reader and explicitly refuses requests to initialize a fully historical 1609 world from modern sources. The water graph connectivity is **unresolved**, not fabricated; river geometry overlaps are currently bounding-box *candidates*, not proven crossings. See [simulation export format](docs/world_package_v1.md) and [end-goal contract](docs/simulation_dataset_contract.md).

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
2. Ingest authoritative current NYS/USGS NHD flowlines and validate counts, clipping and source attribution; subsequently add cross-border NJ and HydroSHEDS v2 for independent comparison.
3. Digitize and georeference genuinely sourced historical shorelines/wetlands from Welikia and archival documents, recording licensing, evidence dates, and registration error.
4. Reconstruct historically constrained surface-water and floodplain features, retaining alternatives where evidence is insufficient.
5. Add DPastCliM-NA temperature/precipitation baseline as modeled 1590–1629 climate, not measured 1609 weather.

`catalog/sources.json` is a source research inventory, not proof that source files are presently incorporated. `data/raw` and `data/derived` are intentionally not committed.


### USGS-directed NHDPlusV2 river graph (modern reference)

The package can optionally include a separate, source-directed network using USGS NHDPlusV2 `FromNode`/`ToNode`; source and output are independently checksummed. This medium-resolution graph does **not** automatically correspond to the original 934 NHD flowlines.

```bash
na1609 fetch-network --region regions/hudson_pilot.json --dry-run
na1609 fetch-network --region regions/hudson_pilot.json --raw data/raw/nhdplusv2_flowlines.geojson --output data/derived/hudson_nhdplusv2_network.json
# Add --network data/derived/hudson_nhdplusv2_network.json to export-pilot.
# Then use: na1609 trace-network --package data/export/hudson-reference-world --comid COMID
```

See [river network implementation and limitations](docs/river_network_v1.md). The graph is partial; genuine 1609 hydrology is still missing.


**Verified network results:** See [Hudson real NHDPlusV2 QA](docs/hudson_modern_nhdplusv2_qa.md) (424 buffered reaches, 428 source-confirmed edges). This is deliberately a **partial modern reference graph**, not a verified 1609 drainage network.
