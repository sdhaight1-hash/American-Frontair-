# Real NYPL MacCoun 1909 image acquisition QA

Verified by GitHub Actions on **November 11, 2026**:

- Run: https://github.com/sdhaight1-hash/American-Frontair-/actions/runs/43101814395 — completed successfully.
- Source: New York Public Library, image ID `ps_map_cd3_36`. Original item: https://old-digitalcollections.nypl.org/items/97ee6342-cec2-2699-e040-e00a18067566
- Verified archival **preview**: **757 × 213 pixels**, JPEG, **240,263 bytes**.
- SHA-256: `33cba617bf62ab0b7d629322ca307e0678b6db9f8cf9d0c88c64e47c0c333900`.
- Image + sidecar manifest available in the GitHub Actions artifact `nypl-maccoun-1909-original-source-preview-not-georeferenced` with limited retention.
- **Publication: 1909. Depicted period: 1609.** This is a retrospective map, not a 1609 survey.
- The image **fails** the 3,000-pixel precision-review image-size gate and is unsuitable for accurate shoreline digitization.
- Rights: NYPL believes the work is public domain under US law. This does not establish international status or grant rights to unrelated modern cartography.
- Later CI runs independently attempt the original-resolution NYPL IIIF endpoint. A failed fetch is recorded explicitly; the importer does not silently substitute a thumbnail.

**Still required for actual historic geometry:** original high-resolution scan, ground-control points independently identified and georeferenced, traced water lines, error bounds, and independent historic comparisons. No 1609 shoreline geometry is asserted by this checkpoint.
