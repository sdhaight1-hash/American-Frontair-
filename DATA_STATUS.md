# Reconstruction status — 2026-11-10

| Layer | State | Historically 1609? |
|---|---|---|
| Geographic pilot region | Defined | No; just a research extent |
| Terrain | Copernicus modern-reference importer implemented; real-data CI run succeeded; raw tiles not committed | No |
| Modern hydrography | NYS NHD flowline importer and mock-data tests implemented; real-data workflow pending verification | No |
| Historical water features | Evidence contract implemented; zero real features | No |
| Historical temperature/precipitation | DPastCliM-NA source identified, integration pending | No |
| Bedrock, soil, vegetation, Indigenous/colonial land use | Sources identified or to research; integration pending | No |

**No scientifically defensible 1609 geographic reconstruction is included in this checkpoint.** It provides the reproducible, testable foundation for building one.

Previous elevation checkpoint completed in GitHub Actions. New hydrology acceptance: real NHD features imported, clipped with original IDs and FCode retained, source and derived SHA-256 manifests, cross-border limitation documented, independent CI smoke pass.

Acceptance for original checkpoint: unit tests pass; a 2-tile modern DEM clip can be generated given Copernicus source files; manifest hashes and modern-only labels are accurate; unproven historical features are rejected.

## Game/simulation export checkpoint

Versioned offline **modern-reference-only** world package implemented and locally tested against real Hudson terrain and 934 modern NHD flowlines. `WorldPackage` supports elevation lookup and bounding-box candidate reach queries with SHA-256 verification; export is deterministic for identical inputs. Historical initial state is **false**; all 1609 hydrography, soils, climate, ecology, and verified graph topology remain unavailable. See `docs/world_package_v1.md`.


## Directed network checkpoint — 2026-11-11

Implemented an optional, separately namespaced USGS NHDPlusV2 graph importer; authoritative `FromNode`/`ToNode` adjacency, paginated download, buffered query context, explicit incomplete/unknown endpoints, source hashes, and offline traversal. Modern-only; not a 1609 reconstruction. The medium-resolution NHDPlusV2 graph does not automatically align with the older NYS NHD flowlines. Local regression suite passes; inspect the new real-network GitHub Actions smoke job before claiming successful live import.

## First historical-water candidate processing checkpoint — 2026-11-11

- Implemented sourced WGS84 vector / image-pixel digitized water importer (shorelines, streams, wetlands, ponds).
- Historical target period, map publication year, citations, source rights assertions, spatial uncertainty and raw-data SHA-256 are recorded separately.
- Map controls use an EPSG:32618 affine fit with >=4 fit and >=2 **holdout** GCPs; an error ceiling rejects bad registration; it cannot prove historic accuracy of the map itself.
- Optional candidate layer integrates into offline world package without adding a runtime GIS dependency, while `is_1609_initial_state=false` remains mandatory.
- Regression suite: **37 passing** synthetic/reference tests locally. Source acquisition/rights and real 1609 candidate creation remain incomplete.
- New actual-source leads: NYPL MacCoun 1909 (retrospective public-domain scan); New Amsterdam History Center Mapbox 1609 shoreline/stream layers (redistribution rights unknown); Welikia GIS downloads advertised (contents/rights not verified).
- **Historical candidate input features in repository: 0.** The importer does not manufacture any real historical features.

## First historically sourced documentary constraints — November 11, 2026

- **2** cited hypothetical 1609 stream features: Maiden Lane and William Street-area tributary, both unlocated in GIS coordinates.
- **2** directional relationships: tributary -> Maiden Lane stream -> East River; 2 sources (NYPL MacCoun 1909, NYC archaeological report 2010).
- Sources have publication years, precise archive/page locators, `retrospective_reconstruction` evidence classification, low confidence, and **null geometry**.
- Export supports embedded constraints or a separately hashed additive overlay to already-verified game packages. Underlying modern terrain and rivers remain unchanged; offline reader can query the constraints.
- This is **historical documentary knowledge, not historically validated 1609 geographic geometry**. Shoreline GIS and 1609 initial state remain unavailable. Source limitations and exact citations in `docs/first_archival_water_constraints.md`.

## NYPL public-domain historical source acquisition (2026-11-11)

- Added reproducible download/verification for Townsend MacCoun's 1909 retrospective map of Manhattan as depicted in 1609, with separate publication and depicted year, NYPL rights statement, byte-for-byte SHA-256, dimensions, and non-georeferenced source status.
- Added fail-closed preservation (no overwrite, invalid raster rejection, no silent original-to-preview substitution, explicit low-resolution-preview flag).
- Added independent preview acquisition GitHub workflow and nine synthetic-image regression tests. This is an archival **source**, not yet a historical shoreline, georeferenced map, or 1609 simulation state.
- Before incorporating a single waterway polyline, we still need a detailed image source, independent georeferencing controls, actual feature tracing, and historical-position validation.
