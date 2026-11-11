# Offline world package v1 — modern reference checkpoint

A first interoperable **data export**, designed for game/simulation clients. This implementation is deliberately a **modern reference package**, not a scientifically reconstructed 1609 world. `target_year = 1609` expresses the research target only.

## Files and units

- `manifest.json` — canonical sorted JSON; `schema = na1609.reference-package.v1`; geographic bounds as `[west, south, east, north]` in WGS84 longitude/latitude; role and historical availability; source file SHA-256 hashes; paths and format metadata.
- `terrain.f32` — `width * height` samples as **little-endian float32** in north-to-south row-major order; `NaN` indicates no data. Values are meters in original Copernicus vertical datum, **not validated historical bare-earth elevation**. No land/water mask is inferred from zero values. Affine transform `[a,b,c,d,e,f]` gives sample upper-left pixel corner; pixel centers are at half-cell offset.
- `reaches.json` — deterministic list sorted by `nhd:<Permanent_Identifier>`. Each reach has geographic geometry, geographic bbox, source metadata, and `topology.status = unresolved`. Null upstream/downstream IDs **do not** mean a headwater or outlet. `clipped_to_region` and `may_continue_outside_region` distinguish boundary cuts from true terminal endpoints.
- `historical_evidence.json` — historical features, when evidence actually exists, validated by the existing evidence importer. The current collection is empty.
- `river_network.json` (optional) — separate medium-resolution NHDPlusV2 source-directed `FromNode`/`ToNode` graph. Identity is `nhdplusv2:<COMID>`, NOT the original NHD `nhd:<Permanent_Identifier>` identity; endpoint statuses may remain unresolved. Imported with `--network`, accessed via `WorldPackage.river_network.trace()` for bounded, cycle-safe traversal. The manifest hashes this graph independently. See [network limitations](river_network_v1.md).

For explicit missing layers (climate, soils, vegetation, reconstructed water graph), the manifest has `{ "available": false }`. The package sets `is_1609_initial_state = false`. Clients must refuse to initialize a complete historical simulation from this package; `WorldPackage.require_1609_initial_state()` demonstrates the guard.

## Source-to-game boundary

GIS dependencies (rasterio, Shapely) are used by the **offline export pipeline only**. `WorldPackage` uses the Python standard library alone and reads only packaged files. Other runtimes can implement the same file format directly. The initial pilot fits in one region; the format is not yet a multiscale, tiled continental streaming architecture.

## Guarantees / acceptance

- Preserve original modern DEM/NHD inputs, immutable and checksummed; verify derived source-manifest SHA-256 before export.
- Identical inputs yield identical package file bytes and stable NHD reach IDs.
- Reject mismatched region, target year, tampered source bytes, duplicate permanent reach IDs and attempts to overwrite output.
- Query terrain pixel values and bounding-box **candidates** for water reaches offline; do not represent candidate hits as exact geometry intersections or directed river connectivity.
- Historical evidence, completeness and uncertainties remain explicit; no implicit fallback to a 1609 reconstruction.

## Still required for actual simulation-ready 1609 data

Historical shoreline/wetland digitization and documented corrections, full basin connectivity from authoritative PlusFlow including non-geometric connections, cross-region coverage and scientifically supported historical waterways, bare-earth survey comparison, bathymetry, modeled climate, soil and habitat attributes, world tiling, and mutable simulation state are **not** implemented by this checkpoint. The next checkpoint should acquire authoritative NHDPlus/HydroSHEDS topology fields instead of inferring connectivity from proximity alone.
