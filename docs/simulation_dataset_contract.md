# Product contract — simulation-ready North America circa 1609

## End goal

Build a **historically grounded, machine-readable world dataset for video games and environmental simulations**, covering Canada, the United States and Mexico with a **circa-1609 initialization state**. Accuracy and physical coherence matter because this is a starting world that may evolve under simulated weather, water, vegetation, land use, and human action.

This is **not** simply a visual map, game engine, rendering asset, GIS research publication, or static snapshot. The GIS acquisition/reconstruction pipeline is upstream infrastructure; the deliverable consumed by games/simulations is a simulation-ready world package.

## Two separate products

1. **Evidence and reconstruction archive (offline):** Unchanged upstream source files; citations/licenses; modern reference layers; historical records; explicit dating and uncertainty; reconstruction algorithms and their versioned outputs. Source confidence must not be replaced with fabricated precision.
2. **Simulation package (exported from archive):** Tiles and indexed spatial features with stable IDs, explicit units and coordinates, structured properties, connectivity and boundaries, baseline circa-1609 state, and metadata marking whether values are evidenced, inferred, or procedurally filled. The export must be deterministic given source versions/configuration/seed.

These products have distinct roles. Heavy GIS processing and historical research occur offline. Game runtimes read compact, structured, streamable data without requiring Python, GIS services or live network access.

## Minimum interoperable domain model

- **Terrain:** ground elevations, terrain material/soil attributes, water/land masks, and localized uncertainty; preserve geodetic source coordinates and vertical datum. No assumption that DSM is bare earth.
- **Water network:** river reaches with stable IDs, upstream/downstream connections, outlets and basin IDs; polygonal lakes, wetlands, coastlines, floodplains; seasonal regimes and levels where supported. Boundary-clipped reaches need retained external connections or explicit boundary flags; no fake dead ends.
- **Climate:** monthly baseline distributions (temperature, precipitation, etc.), seasonality, uncertainty, and provenance, separately from generated daily/annual weather.
- **Ground & ecology:** geology, soil texture/profile, drainage, moisture capacity, vegetation communities, possible species, canopy and disturbance regimes; do not infer individual historic trees.
- **Historical context:** Indigenous and colonial settlements/land use where supported; evidence time intervals, alternatives and source citations. 1609 is not a blank wilderness.
- **Spatial/time metadata:** stable geographic location, tile or region ID, units, data resolution, model version, and historical validity period.

Do **not** force every property into a 30 m cell. Represent networks as graphs, surface fields as rasters, zones as polygons, and time series as arrays, then export only the appropriate detail for each simulation scale.

## Immutable baseline vs mutable simulation state

- **Baseline (immutable):** reconstructed initial conditions and provenance, with explicit missing/uncertain values.
- **Runtime simulation state (mutable):** groundwater, soil moisture, vegetation age, sediment, fire, land-use changes, river flow, weather and player/NPC modifications as modeled by each simulation.
- **Derived state:** e.g., current biome or navigability computed from climate, terrain and changed conditions. A classification should not silently replace the variables needed to reproduce it.

Allow reloading the 1609 initial state, advancing time, changing an area, and saving only modifications or snapshots without mutating source archives.

## Technical output requirements

- **Georeferencing:** latitude/longitude authoritative where appropriate, local/projected tile coordinates for efficient simulation, unambiguous transforms and units, stable tile boundaries.
- **Spatial queries:** lookup at a geographic point, intersect a region, list all reaches of a basin, traverse upstream/downstream, and retrieve seasonal/soil/vegetation attributes.
- **Streaming:** bounded tile/region reads, versioned schema, and independently loadable nearby regions. Preserve cross-tile connectivity.
- **Determinism:** identical source hashes, pipeline version, processing options, and optional random seed produce identical simulation packages.
- **Honesty about resolution:** input grid size, spatial error, historical confidence, and inferred detail must survive the export; “visually plausible” is not “historically observed.”
- **Portability:** documented schema and a straightforward game-agnostic reader; eventual exporters can target Rust, C++, Godot, Unity, Unreal, or other runtimes without rewriting the historical model.

## First playable-data vertical slice: Lower Hudson

A developer should be able to load the exported pilot **offline** and:

1. Query land elevation/ground material and the source/uncertainty of each result.
2. Trace one river reach through the local hydrological graph, including the pilot's boundaries.
3. Identify candidate 1609 shorelines/wetlands separately from the modern reference and see the evidence/uncertainty attached.
4. Query monthly climate and soil/vegetation properties once those datasets are available (missing data must be explicit until then).
5. Initialize mutable simulation state, change water/vegetation locally, and reload an identical 1609 baseline.

A demo must fail visibly for missing historical layers; it must not silently substitute modern rivers/shorelines as 1609 geography. Keep the public source catalog and tests that verify the source-to-package transformation.

## Priority adjustment

Continue the current historical hydrology checkpoint, but implement it with future simulation use in mind:

1. Preserve raw NHD/HydroSHEDS geometries and source provenance.
2. Normalize **reach IDs, directed topology, waterbody/wetland membership and boundary connectors**.
3. Integrate substantiated historical geometry as an alternate, dated layer; do not overwrite modern references.
4. Produce a small **versioned, machine-readable pilot export** and an offline read/query test.
5. Continue climate/soil/ecology ingestion only after the minimal export contract has been validated.

Graphics, low-poly styling, roads, buildings, NPCs, and gameplay mechanics are downstream clients, **not requirements for the dataset itself**.
