# First authentic historical water evidence — unlocated network constraints

**Status: documentary evidence included; historical GIS geometry NOT included.**

This checkpoint introduces two evidence-backed **topological** water relationships into the Lower Hudson **game/simulation** world package. They represent a 1609 reconstruction published in 1909 and summarized in a 2010 archaeology report; they are **not direct observations from 1609** and are **not georeferenced river traces**.

## Source evidence

1. **Townsend MacCoun (1909)**, *1609. The island of Manhattan (Mannahtin) at the time of its discovery showing its elevations, water-courses, marshes, and shore line*. NYPL Digital Collections image `ps_map_cd3_36`, [catalog](https://old-digitalcollections.nypl.org/items/97ee6342-cec2-2699-e040-e00a18067566). NYPL marks its scan public-domain under US law. This is a **retrospective** depiction, not a 1609 field survey.
2. **AKRF/URS (2010)**, *Fulton Street Transit Center Project: Corbin Building archaeological mitigation report*, [PDF](https://s-media.nyc.gov/agencies/lpc/arch_reports/1237.pdf), printed p. 9, PDF page index 12. The report discusses MacCoun's map and earlier surveys and describes two stream routes. These are paraphrased as factual relationships here; we have **not** copied report graphics or proprietary historical geometry.

## Encoded claims

- **Maiden Lane stream:** A retrospective stream corridor running roughly west-to-east along what is now Maiden Lane, emptying into the East River.
- **William Street-area tributary:** A retrospective southward-flowing tributary near today's William Street, meeting the Maiden Lane stream near their intersection.

The JSON record `data/historical/hudson_1609_documentary_constraints.json` stores stable IDs, source citations and exact locators, **publication year separate from depicted year**, relationship edges, qualitative named-landmark locations and `geometry: null`. `confidence: low` indicates these are hypotheses supported by retrospective documents rather than independent surveyed 1609 coordinates.

The only supported downstream sequence is:

`william_street_tributary -> maiden_lane_stream -> east_river (named external waterbody)`.

It is **not** safe to infer stream width, discharge, hydrological seasonality, geographic polyline, confluence coordinates, coastal polygon, or rivers on the NJ side of the pilot.

## Use from a game

Use these facts as constraints on a future historically reconstructed, connected drainage graph; they are unsuitable as actual simulation water features until georeferenced and reconciled with terrain and other sources. This is distinct from the imported **modern** USGS NHDPlusV2 graph.

```bash
na1609 check-historic-constraints --region regions/hudson_pilot.json --input data/historical/hudson_1609_documentary_constraints.json

# On a pre-existing reference package:
na1609 attach-historic-constraints --region regions/hudson_pilot.json \
  --package data/export/hudson-reference-world \
  --input data/historical/hudson_1609_documentary_constraints.json \
  --output data/export/hudson-reference-with-documentary-constraints

# Or supply --historic-constraints to export-pilot when constructing a new package.
```

The offline `WorldPackage.historical_water_constraint("william_street_tributary")` retrieves the assertion, its source IDs, and downstream relation. Package output is hashed, replayable, and still refuses `require_1609_initial_state()`.

## Historical source access checks (November 2026)

- Welikia's resources page advertises future geographic downloads, but the actual live client component `/_app/immutable/nodes/10.ClAFKQQ7.js` currently shows **"Updated geographic data coming soon."** The older research reports do not establish live access or redistribution rights to current GIS vectors.
- The New Amsterdam History Center displays Mapbox vector sources `mapny.a0lop49m` (Manahatta shoreline) and `mapny.a9o6nugn` (streams circa 1600). Map tiles are not equivalent to a reuse license; none were copied.
- NYPL's MacCoun map is a public-domain US scan, a plausible digitization source; an actual 1609 polyline still requires full-resolution source retrieval, defensible georeferencing with held-out control points, traced features, and independent historical comparison. No such line is asserted here.
- NYBG Conservation's [Blue Zone Analysis](https://github.com/NYBG-Conservation/Blue-Zone-Analysis) lists historical stream, pond, freshwater wetland, tidal creek, beach and marine-water shapefile names, but its README explicitly calls for a **data-sharing agreement** for the underlying Welikia data. The code repo does not confer unrestricted use of those raw maps.

**Next acceptance gate:** Obtain independently usable vector traces or a georeferenced public-domain scanned map; digitize and assess a *specific* real waterway segment with registration residuals, feature-specific uncertainty and comparison against other research. Keep the full 1609 initialization flag false until core environmental layers are ready.
