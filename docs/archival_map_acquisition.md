# Historical map acquisition — NYPL MacCoun 1909

**What this actually delivers:** an immutable, checksummed **archival image** made in 1909, retrospectively portraying Manhattan in 1609. **It does not produce a georeferenced shoreline, stream or simulation-ready 1609 terrain.**

## Source and rights

- Townsend MacCoun, *1609. The island of Manhattan (Mannahtin) at the time of its discovery showing its elevations, water-courses, marshes, and shore line*, issued **1909**.
- NYPL source and rights statement: <https://old-digitalcollections.nypl.org/items/97ee6342-cec2-2699-e040-e00a18067566>, image ID `ps_map_cd3_36`.
- NYPL says it believes the item is **public domain under United States law**, without determining rights in other jurisdictions. It requests optional credit “From The New York Public Library” with a link. This is not an endorsement or a license to Welikia or NAHC proprietary vectors.
- The **publication year (1909)** and **depicted year (1609)** are stored independently. The image remains a *secondary/retrospective* map and can disagree with other historic records.

## Reproducible acquisition

```bash
# Source preview for research only, usually ~760 px wide, NOT enough for precise digitization.
na1609 fetch-archival-map --quality preview --output data/raw/nypl_maccoun_1909_preview.jpg
na1609 inspect-archival-map --input data/raw/nypl_maccoun_1909_preview.jpg

# Try the original-resolution NYPL image; NEVER fall back to a preview silently.
na1609 fetch-archival-map --quality original --output data/raw/nypl_maccoun_1909_original.jpg
na1609 inspect-archival-map --input data/raw/nypl_maccoun_1909_original.jpg
```

When the NYPL IIIF original endpoint is unavailable, the command fails instead of pretending a 760-pixel thumbnail is a detailed scan. Source bytes are stored outside Git in `data/raw/` with a JSON sidecar recording URL, image ID, exact SHA-256 hash, dimensions, image format, dates, classification, and caveats. The CLI refuses to overwrite an existing archive.

An original image passing the minimal 3,000-pixel long-axis **image suitability check** may be reviewed for manual feature tracing; this threshold is **not** proof that the historical map is accurate or correctly positioned. No existing georeferencing or control-point coordinates are assumed.

## Geographic reconstruction gate (not yet achieved)

1. Obtain sufficiently detailed image source and record its exact SHA-256.
2. Establish real, independent control points with externally verified WGS84 coordinates and capture them in a separate georeferencing metadata file.
3. Digitize clearly depicted water features in **pixel coordinates**; use `na1609 ingest-historic-water` for a held-out georeferencing check, with a conservative historical uncertainty estimate, and documented rights.
4. Compare with independently sourced shoreline or landscape histories; a low affine registration error by itself says nothing about 1909-to-1609 cartographic accuracy.
5. Keep all actual game geometry labelled historical **candidate** until independent accuracy and terrain/network reconciliation gates pass.

Historical water **geometry remains empty** in this checkpoint. Documentary constraints (Maiden Lane and William Street streams) are separate and unlocated.
