# NHDPlusV2 directed reference network — checkpoint 2

**Purpose:** Offline, game-readable directed river graph for the Lower Hudson pilot. **Status: modern-reference-only**, not a verified 1609 network or a complete watershed.

## What this adds

The `fetch-network` command queries the publicly documented [USGS NHDPlusV2 OGC API Features `nhdflowline_network` collection](https://api.water.usgs.gov/fabric/pygeoapi/collections/nhdflowline_network), within the pilot bbox plus a configurable **0.05° spatial context**. It downloads **all pages**, preserves uncut GeoJSON source geometries, and writes a derived graph with original COMIDs and FromNode/ToNode relationships. It also emits a source/derived SHA-256 manifest. Both the raw source and result are distinct from the older NYS NHD-derived 934-feature reference layer.

The USGS documents that `FromNode` is the upstream end and `ToNode` is the downstream end of a directional flowline. An edge A → B exists if and only if A.ToNode == B.FromNode and both flowlines have `FlowDir = With Digitized`. This supports tributary confluences and multi-path divergences; **we never connect by geometric proximity**. A reach with `FlowDir = Uninitialized` is retained but excluded from directed connection inference.

Because NHDPlusV2 is a more generalized, **medium-resolution** network than the separate New York NHD flowline collection, source identities are namespaced `nhdplusv2:<COMID>` (not `nhd:<Permanent_Identifier>`). No implicit crosswalk is made.

NHDPlusV2 uses a separate authoritative `PlusFlow` table for some **non-geometric links** (including subterranean/exceptional connections). Node matching alone is a verified subset of connectivity, **not a complete substitute for PlusFlow**. Even with a context pad, unlinked endpoints are treated as `unresolved_or_outside_context` unless a source `startflag`/`terminalfl` expressly identifies a headwater/outlet. The importer does not relabel an unlinked endpoint as a natural outlet.

## Working CLI

```bash
na1609 fetch-network --region regions/hudson_pilot.json --dry-run
na1609 fetch-network --region regions/hudson_pilot.json \
  --raw data/raw/nhdplusv2_flowlines.geojson \
  --output data/derived/hudson_nhdplusv2_network.json
na1609 export-pilot --region regions/hudson_pilot.json \
  --terrain data/derived/hudson_modern_surface.tif \
  --flowlines data/derived/hudson_modern_flowlines.geojson \
  --network data/derived/hudson_nhdplusv2_network.json \
  --evidence data/historical/hudson_1609_evidence.geojson \
  --output data/export/hudson-reference-world
na1609 trace-network --package data/export/hudson-reference-world \
  --comid <REAL_SOURCE_COMID> --direction downstream
```

`--pad-degrees` is a query context only, **not** a hydrological or ecological buffer. Larger basin-scale connectivity will need an independent full-coverage, tiled process; do not grow the pad indefinitely to pretend that a catchment is complete.

## Exported fields and runtime contract

- `river_network.json` retains the source COMID, original geometry, USGS node IDs and flags, ordered upstream/downstream reach ID arrays, `inside_pilot`, and explicit endpoint status.
- The world package manifest names the graph, its SHA-256, source identifier, and statistics; it still sets `is_1609_initial_state = false`.
- `WorldPackage(...).river_network.trace("nhdplusv2:<COMID>", direction="downstream")` traverses all branches, handles loops with a visited set and caps traversal. It reports unresolved ends, and **`network_complete = false`** when the subset does not prove termination.
- Old packages without this optional network remain readable; the older NHD `reaches.json` remains unchanged with unresolved topology rather than a fabricated crosswalk.
- Import and graph processing require Shapely, but the game-facing reader loads without a geospatial library.

## Tests / acceptance gate

- Pagination, declared total counts, duplicates and missing pages checked before derived data is written.
- Edges established exclusively by source-confirmed node IDs; synthetic confluence/divergence, cross-region, missing direction and geometry-proximity traps exercised.
- Raw/derived data hashed; optional graph exported with its own checksum; offline reader catches modified network bytes.
- Real-data CI workflow probes the USGS endpoint and measures the imported graph. Real-data success is recorded separately from synthetic tests; do not declare it complete without a passing run.

## What remains

Verified **full basin connectivity** requires the official PlusFlow table or another comprehensive and internally consistent network. Crosswalk to the higher resolution NHD and physically/archivally reconstructed 1609 rivers are separate tasks. All current geometry is modern and not a representation of precolonial waterways.
