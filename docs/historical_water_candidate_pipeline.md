# Historical water candidate pipeline — Lower Hudson, circa 1609

**Status:** The importer, georeferencing QA, and game exporter are implemented. **No verified historical shoreline/stream/wetland vector has been ingested yet**. All 37 automated tests use explicitly synthetic fixtures. The modern reference is not 1609.

## Sources investigated (2026-11-11)

1. [NYPL Townsend MacCoun 1909 retrospective map of Manhattan 1609](https://old-digitalcollections.nypl.org/items/97ee6342-cec2-2699-e040-e00a18067566): map scan explicitly described by NYPL as free to use without restriction. It was **drawn in 1909**, so its depiction of 1609 is retrospective, not an observed 1609 shoreline. Needs independent image control points and manual vector tracing. Its use cannot establish a historically exact coastline by itself.
2. [New Amsterdam History Center early-NYC map viewer](https://nahc-mapping.org/mappingNY/): publicly displays “Manahatta Shoreline” and “Streams (c 1600)”. Its deployed `timeline/js/layersList.js` associates the shoreline layer with `mapbox://mapny.a0lop49m` (source layer `manahatta_shoreline-1xswf8`) and the streams with `mapbox://mapny.a9o6nugn` (source layer `manahatta_area_streams-a2x39f`). **Viewing map tiles is not proof of rights to extract and redistribute the underlying vectors**. No vectors from the map were copied into this repository. Confirm source methodology, geographic accuracy and explicit game-dataset distribution permission first.
3. [Welikia Project](https://www.welikia.org/resources): publicly advertises geographic data / DEM download archives. Specific vector contents, accuracy, download links and commercial redistribution rights have **not yet been inspected or verified**. Contact the NYBG maintainers where required. Source imagery and historical maps should be cross-validated, not treated as directly observed 1609 measurements.
4. [Historical Ecology of Mannahatta's Waters](https://www.hudsonriver.org/wp-content/uploads/library/Sanderson_001_08A_final_report.pdf): a documented methodology using several historical maps and correcting for colonial landfill. This provides methodological context, not an automatically licensed GIS export.

## Steps to create a candidate, without fabricating source geometry

- Obtain source material with explicit legal rights for redistribution in a **video-game dataset**.
- If working from a scanned historical map, preserve the raw image and SHA-256. Digitize lines and polygons **in source image pixel coordinates**; mark the map's creation year separately from the time it claims to depict.
- Supply at least **four fit controls and two independently surveyed holdout controls**, each with `pixel_xy`, `lon_lat`, and `role`. Validate the affine registration using projected metre coordinates; reject singular control geometry or held-out errors above the research threshold. A small holdout error still **does not prove the historical shoreline**.
- If licensed historical vectors are already in WGS84, the importer accepts them directly with recorded source properties and a conservative horizontal uncertainty. There is no invented registration score for pre-georeferenced geometry.
- For each traced feature, require a stable ID, geometry type (`shoreline`, `stream`, `wetland`, `pond`), date interval covering 1609, evidence basis and confidence, and citations to the exact source/locator. The source's metadata must agree with feature dates and IDs.
- Run `na1609 ingest-historic-water` with a metadata JSON and digitized GeoJSON. The importer checks geometry, date scope, access rights assertion, registration, independent holdout, source hashes, region bounds, and duplicate IDs; it refuses to overwrite.
- Export with `na1609 export-pilot ... --historic-water data/derived/hudson_candidates.geojson`. The optional candidate layer can be queried with `WorldPackage.historic_water_in_bbox()` but **`is_1609_initial_state` remains false**.
- Independently assess cartographic historical accuracy and source agreement before a feature can ever be promoted from `historical_candidate_not_validated` to a reconstructed historical state. **The promotion path is not implemented** and must have separate acceptance criteria.

## Metadata contract

JSON fields: `source_id`, `source_url`, `source_publication_year`, `historical_interval: [start,end]`, `evidence_locator`, `rights_basis`, `redistribution_allowed`, `coordinate_space` (`wgs84` or `image_pixels`), and `horizontal_uncertainty_m` (conservative positive estimate). For pixels, also supply `source_image` relative to metadata, mandatory `source_image_sha256`, actual `image_width` and `image_height`, `control_points`, and `max_holdout_error_m`. Both image hash and raster dimensions must match the archived scan or the candidate is rejected.

The `redistribution_allowed` flag is a **researcher's signed-off assertion**, not a legal certification produced by the code. Never set it to true merely because data can be viewed online.

Each GeoJSON feature must contain `properties.feature_id`, `feature_type`, `valid_years` matching the source period, `basis`, `confidence`, and `evidence: [{source_id, locator}]` referencing the source metadata. The output is GeoJSON in WGS84 plus a SHA-256 manifest. The importer records the map publication year, source evidence, clipped geometry, and minimum spatial uncertainty. `bbox_wgs84` supports an offline stdlib-only spatial prefilter (it is not an exact intersection test).

## Testable gates

- [x] Candidate source import and provenance hashing.
- [x] Reject absent rights, missing citations, conflicting temporal coverage, duplicate IDs, invalid/out-of-region geometry.
- [x] Image-pixel affine registration with independent metre-based holdout validation.
- [x] Reject out-of-tolerance held-out registration, missing source image, and unverified candidate manifest.
- [x] Offline game export preserves candidates and prevents false complete-1609 status.
- [ ] Inspect legally downloadable original historical geographic vectors or scan; hash and preserve them.
- [ ] Create at least one genuine, licensed, cited candidate shoreline or waterbody geometry.
- [ ] Verify historical positioning independently, document cartographic error and date uncertainty, and compare alternative sources.
- [ ] Reconcile historical features with terrain and network (without silently replacing modern source IDs or topology).

**This checkpoint delivers software that can process real evidence, not a new empirically verified historical shoreline.**
