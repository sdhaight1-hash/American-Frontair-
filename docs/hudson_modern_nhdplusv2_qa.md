# Lower Hudson NHDPlusV2 directed network real-data QA — 2026-11-11

**Modern reference only; NOT a 1609 reconstruction.**

Verification: [GitHub Actions real NHDPlusV2 network integration, run 43087894777](https://github.com/sdhaight1-hash/American-Frontair-/actions/runs/43087894777) — **success** (the importer, graph assertions, and artifact upload all passed).

Source: [USGS Water Data / NHDPlusV2 network OGC API](https://api.water.usgs.gov/fabric/pygeoapi/collections/nhdflowline_network). Research extent: [-74.12, 40.64, -73.82, 40.90] (CRS84), expanded by 0.05° on each side to capture context reaches. This context query is *not* a complete catchment.

| Measured statistic | Value |
|---|---:|
| NHDPlusV2 source flowlines in context | 424 |
| Flowlines intersecting pilot extent | 243 |
| USGS FromNode/ToNode directed links | 428 |
| Links crossing pilot inclusion boundary | 26 |
| Flowlines with source-unknown flow direction | 0 |
| Endpoints unresolved upstream in context | 74 |
| Endpoints unresolved downstream in context | 12 |

The measured graph supports a 22-reach sample downstream traversal from source `nhdplusv2:6231412`, with **at least one unresolved end**. The traversal properly reports `network_complete: false`.

The exported game world package was also tested locally with **the real elevation reference**, **934 separate NYS NHD features**, and this **424-reach NHDPlusV2 graph**. The two networks are intentionally **not automatically crosswalked**. The `WorldPackage` offline reader loaded, checked its SHA-256 manifest, and traversed the source-confirmed graph without GIS libraries or network calls. `is_1609_initial_state` stayed **false**.

Important limitations: an NHDPlusV2 node graph is not identical to the complete NHDPlus V2 PlusFlow table (which can encode non-geometric connections), NHDPlusV2 is medium-resolution rather than complete modern local hydrography, and neither source is a historical 1609 waterways dataset. Absence of a loaded neighbor is NOT evidence of a headwater or outlet. No source-based mapping to the 934 higher-resolution NHD reaches has been established.
