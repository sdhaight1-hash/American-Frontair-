# Reconstruction status — 2026-11-10

| Layer | State | Historically 1609? |
|---|---|---|
| Geographic pilot region | Defined | No; just a research extent |
| Terrain | Modern Copernicus ingest code implemented; source tiles not bundled | No |
| Modern hydrography | NYS NHD importer and 6 offline tests implemented; live service smoke test on CI | No |
| Historical water features | Evidence contract implemented; zero real features | No |
| Historical temperature/precipitation | DPastCliM-NA source identified, integration pending | No |
| Bedrock, soil, vegetation, Indigenous/colonial land use | Sources identified or to research; integration pending | No |

**No scientifically defensible 1609 geographic reconstruction is included in this checkpoint.** It provides the reproducible, testable foundation for building one.

Acceptance for this checkpoint: unit tests pass; a 2-tile modern DEM clip can be generated given Copernicus source files; manifest hashes and modern-only labels are accurate; unproven historical features are rejected.

Hydrology checkpoint is **modern flowlines only**. New Jersey coverage is missing in the NYS source; HydroSHEDS v2 is not ingested yet; no 1609 water geometries have been digitized.
