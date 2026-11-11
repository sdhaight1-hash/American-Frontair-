# MacCoun pond image-pixel traces — archival source checkpoint

## What exists

Two **source-image pixel polygons**, `data/historical/source_pixels/maccoun_ponds_1909.geojson`, were digitized from the **verified authentic** NYPL scan of Townsend MacCoun's 1909 retrospective Manhattan map depicting 1609 (`ps_map_cd3_36`; 7,004 × 1,970 pixels). The two conspicuous blue inland pond bodies are depicted near the Bowery/Lafayette Street vicinity. **Their identification as the original Collect Pond system is tentative pending independent map research.**

NYPL source: https://old-digitalcollections.nypl.org/items/97ee6342-cec2-2699-e040-e00a18067566 (NYPL marks unrestricted reuse). Hash of the particular scan used to trace:

`57fc9c31128bfbfd1fc9928f6e6b295940001c22faa04b8cd196e5229caca00a`

### How digitized

An analyst examined the source map in pixel coordinates and used a **bounded blue-ink color mask** over scan rectangle `[630,1040,860,1220]` to assist manual review. OpenCV HSV H 95–130, S 20–255, V 50–240, morphological 3×3 closing twice, contour selection of the two large components (approx. 2,760 and 1,254 square pixels), and Douglas–Peucker contour simplification of 1.4 pixels produced the stored outlines. An independent visual overlay inspection confirmed the contours follow the two blue pond patches, while accepting ~3-pixel drawing/scan ambiguity. Contour extraction is an **annotation of a printed map symbol**, not a scientific reconstruction of 1609 water edges.

Raw scan: fetched with `na1609 fetch-archival-map --quality original`. The original image bytes are retained in ignored `data/raw/nypl`, **not committed to Git**.

### Verification

```bash
na1609 inspect-pixel-traces \
  --image data/raw/nypl/nypl_maccoun_1909_original.jpg \
  --traces data/historical/source_pixels/maccoun_ponds_1909.geojson \
  --preview data/derived/maccoun_ponds_pixel_review.png
```

This rejects mismatched archival image bytes and dimensions, duplicate IDs, invalid or out-of-image polygons, incorrect dates, unsupported feature roles, and missing citations. It creates a **non-destructive visual QA crop**.

## What emphatically does not exist yet

- No geodetic (WGS84) placement, map transformation, or ground-control-point holdout result exists for these polygons.
- They have **no world-space size, position, simulation water level, discharge, or outlet connectivity**.
- No verified 1609 geographic shape has been inserted into `WorldPackage`; its historical initial-state flag remains false.
- A 1909 interpretation cannot be treated as measured evidence from 1609.

**Next acceptance gate:** identify ≥4 spatially dispersed modern/archival tie points visible on this particular source map; reserve ≥2 *independent* holdout control points; obtain authoritative modern coordinates for the control features; compute transformation and residuals; verify distortion and alternative historical references; only then reproject a pixel trace using `ingest-historic-water`. Do not satisfy the gate using guessed coordinates or using the same tie points for fitting and validation.
