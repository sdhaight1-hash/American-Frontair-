# Lower Hudson real-data reference QA (2026-11-10)

**Status:** Modern elevation reference only. **NOT reconstructed 1609 terrain.**

GitHub Actions run: https://github.com/sdhaight1-hash/American-Frontair-/actions/runs/42912228395

- Upstream: Copernicus DEM GLO-30 (public AWS tiles N40 W075 and N40 W074). Copernicus Digital Elevation Model (DEM), accessed 2026-11-10, https://registry.opendata.aws/copernicus-dem/.
- Requested WGS84 extent: west -74.12, south 40.64, east -73.82, north 40.90.
- Output CRS: EPSG:4326; cell size: 1/3600 degree (approx 30 m).
- Output dimensions: **1080 columns × 936 rows**.
- Finite sample fraction: **1.0** (note ocean 0 m is classified as finite and should NOT be confused with all-land coverage).
- Sample min / median / max: **-15.12931 / 11.272808 / 186.326 metres**.
- Approximately **16.61%** of pixels equal 0 m (may contain sea/flat-water cells; this is not verified land cover).
- Two source files with SHA-256 checksums and generated GeoTIFF SHA-256 are recorded in the CI artifact sidecar manifest.
- Output SHA-256: `d0824ba43fd8834a3be2dc549235d0e081700cf2e5d7932ea573a8814d4360cc`.

CI accepted only basic import integrity: downloaded files, created and inspected raster, nonempty finite data, checksums, explicit modern-reference metadata.

**Not yet validated:** ground-vs-canopy/building elevation errors, vertical datum consistency with other data, modern engineered shorelines, floodplain geometry, historical waterways, wetlands, coastlines, 1609 relevance, or independent survey comparison.

The generated dataset is available as the **hudson-modern-reference-not-1609** artifact on the linked workflow run (short retention). Do not treat the terrain raster as evidence of 1609 shorelines or habitat.