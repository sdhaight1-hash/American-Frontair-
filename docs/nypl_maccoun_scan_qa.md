# Real NYPL MacCoun 1909 image acquisition QA

Verified in GitHub Actions on **November 11, 2026**:

- Run: <https://github.com/sdhaight1-hash/American-Frontair-/actions/runs/43101814395> — completed **successfully**.
- Source: New York Public Library image ID `ps_map_cd3_36`, public domain under US law according to NYPL. Original item: <https://old-digitalcollections.nypl.org/items/97ee6342-cec2-2699-e040-e00a18067566>.
- Verified archival **preview**: **757 × 213 pixels**, JPEG, **240,263 bytes**.
- Preview SHA-256: `33cba617bf62ab0b7d629322ca307e0678b6db9f8cf9d0c88c64e47c0c333900`.
- The image and manifest are stored in the GitHub Actions artifact `nypl-maccoun-1909-original-source-preview-not-georeferenced` (short retention). Raw third-party bytes are not committed to Git.
- **1909** map publication year; **1609** reconstructed/deprecated time depiction. The image is neither an observation nor a historically surveyed map from 1609.
- The 757-pixel preview **failed** the 3000-pixel precision tracing gate, correctly. This is a hard limitation for reconstructing 1609 shoreline geometry.
- The original-resolution NYPL IIIF endpoint remains a separate acquisition attempt. Failure of that endpoint must not cause silently upscaled previews or fabricated detail. The separate CI probe is recorded in subsequent runs.

**Next needed for actual historic geometry:** working original-resolution scan, independent georeferencing ground-control points, traced data, positional error analysis, cross-source agreement, terrain/hydrology reconciliation.

## Original-resolution NYPL scan verified (later CI run)

- Successful original + preview acquisition: https://github.com/sdhaight1-hash/American-Frontair-/actions/runs/43102314464
- Original scan: JPEG **7,004 × 1,970 pixels**, **2,159,834 bytes**.
- Original SHA-256: `57fc9c31128bfbfd1fc9928f6e6b295940001c22faa04b8cd196e5229caca00a`.
- Source image eligible for registration **review only**, not yet georeferenced or interpreted as a precise 1609 coastline.
- The exact image bytes and checksum manifest are available in the successful run's artifact (7-day retention).
- The unfilled [registration template](../data/historical/nypl_maccoun_1909_registration_template.json) records the actual source hash and dimensions but deliberately includes **zero** invented ground controls and **no rights sign-off**. The game export validator rejects it until valid controls and historical geometry are supplied.
