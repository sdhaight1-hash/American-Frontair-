# Lower Hudson NHD modern reference QA — 2026-11-10

**NOT a 1609 reconstruction.** This is a modern vector hydrography slice from the New York State GIS Program Office, based on the USGS National Hydrography Dataset.

- Source: https://gisservices.its.ny.gov/arcgis/rest/services/NYS_Hydrography/MapServer/15
- The service description reports the last update on 2020-06-22.
- Live GitHub Actions validation: https://github.com/sdhaight1-hash/American-Frontair-/actions/runs/42914506690
- Research bbox EPSG:4326: [-74.12, 40.64, -73.82, 40.90].
- Object IDs fetched by geographic envelope then full features requested in batches of 100. Result completeness and unique IDs verified.
- **934** original flowline features, **934** derived in-region flowlines, **25** geometries modified by bbox clipping.
- **934** source features had four coordinate ordinates (X, Y, Z, M). The derived geometry discards the last two ordinates for planar processing; original coordinates remain in the raw source file.
- Source FCode counts: 33400:121, 46003:3, 46006:748, 56600:62. Original class codes are retained; they must not all be called natural rivers.
- Source raw file SHA-256: aa861423fb8739bb5be12527ce965d507c380d08d5d16a8ce4b95a365f0675c8.
- Derived geometry SHA-256: 1b04da71b205881e2ae0c493a21ed2c96baf99fc37f80e36e21eb48a2f836776.
- Independently verified both hashes, 934 unique IDs, valid clipped geometries inside the research bbox, and 25 truncation flags.
- Archive: GitHub Actions artifact hudson-modern-nhd-flowlines-not-1609 (seven-day retention) on the linked run.

## Explicit limitations

The source covers New York State only, but the pilot rectangle includes New Jersey. Missing NJ flowlines are **not proof of missing waterways**. This NHD layer mixes natural and artificial paths, canals, coastal and river representations. Clipped endpoints do not establish connectivity. Source heights and measurements were not used to assert a vertical datum.

The historical 1609 evidence GeoJSON still has **zero validated features**. Historical shoreline registration, restored wetlands, and basin-scale water topology remain separate future validation work.
