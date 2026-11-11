# 1609 Lower Hudson waters — evidence gate

The hydrology importer adds **modern** NHD reference flowlines, not 1609 watercourses. The pilot crosses the NY/NJ state border; the NYS service omits New Jersey. Absent NJ lines do not imply dry terrain.

## Historical map candidates

See catalog/hudson_historical_sources.json. The 1909 Townsend MacCoun map at NYPL is a retrospective depiction of 1609. Welikia is an independent scholarly reconstruction; its GIS vector redistribution rights are **not established**. The Mannahatta waters report is a methodological reference, not a downloadable historical geometry dataset.

**There are no digitized, verified 1609 shorelines yet.** The historical FeatureCollection remains empty. Do not derive the historical shoreline from contouring a modern DSM or arbitrarily redraw the present waterfront.

## Next historical-feature acceptance gate

1. Obtain a rights-cleared, high-resolution scanned historical shoreline map.
2. Select independently identifiable ground-control points; document original pixel positions, world positions, and uncertainties.
3. Georeference with a documented transform, and evaluate on *withheld* control points; report positional error in meters.
4. Digitize watercourses, marshes and shorelines only where the original map depicts them, preserving 1909 retrospective versus 1609-survey provenance.
5. Attach source IDs, locators, temporal validity, method, uncertainty and confidence to each geometry.
6. Compare against independent archival/archaeological evidence and retain alternatives when reconstructions disagree.
7. Check water/land topology and connectivity. Only then publish a clearly labeled historical reconstruction.

## Modern reference acceptance gate

- Preserve original source features, IDs and feature classes; never silently reclassify artificial paths and canals as natural streams.
- Independently clip derived lines; record truncations and reject incomplete, duplicate, invalid or non-linear source geometries.
- Record source, CRS, bbox, hashes, feature counts and cross-border gaps in the sidecar manifest.
- Verify the network-connected import separately from synthetic regression fixtures using GitHub Actions.
