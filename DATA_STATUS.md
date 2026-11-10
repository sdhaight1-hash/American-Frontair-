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
