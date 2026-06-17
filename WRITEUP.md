# Writeup — ParcelFit (Buildable Land Analysis)

## The problem, restated

Take a parcel, remove the parts you legally or physically can't build on, and report how much
usable land is left — on a map you can adjust by hand. The interesting work isn't the subtraction
itself (one `difference` call); it's choosing which constraints matter, sourcing real data for them,
buffering each by a defensible setback, keeping the totals honest, and making the whole thing
responsive on a county's worth of messy data.

## Approach

Pipeline, in one line:

```
buildable = parcel − ∪(constraintᵢ buffered by setbackᵢ)
            then  ∪ (restores ∩ parcel)  −  carve-outs
```

- **Backend** (FastAPI + shapely 2 + GeoPandas): a GeoPackage is loaded into memory at startup,
  one GeoDataFrame per layer, each with an STRtree spatial index. A request for a parcel's
  buildable area queries the index by the parcel's bounding box, so only nearby constraints are
  touched — not all 16k wetlands. Constraints are buffered, unioned, and subtracted; manual edits
  are applied on top. The same endpoint serves the initial result and every live update.
- **Frontend** (React + MapLibre + terra-draw): parcels render as a vector layer; clicking one
  calls the endpoint and draws buildable (green) vs. excluded (colored per layer). terra-draw
  provides the carve/restore polygons; setback sliders send overrides. Everything re-runs the
  same endpoint, so the totals and breakdown stay consistent.

### Data and setbacks (sources in `data/SOURCES.md`, values in `config/setbacks.yml`)

| Layer | Source | Setback | Why |
|---|---|---|---|
| Parcels | TxGIO/TNRIS StratMap | — | Statewide, filtered to one county |
| Wetlands | USFWS NWI | 100 ft buffer | USACE buffer-effectiveness review; CWA §404 |
| Flood | FEMA NFHL, SFHA (Zones A/AE, 1% annual) | 0 ft (zone removed as-is) | FEMA/NFIP — the zone *is* the constraint |
| Transmission | HIFLD | half-width by voltage (50–125 ft), 75 ft default | utility ROW standards / NERC FAC-003 |

Setbacks are read from a YAML file and overridable per request, so the wetland buffer or
transmission ROW can be changed from the map sliders and re-run with no code change.

**Study area: Calhoun County, TX** — a Gulf-coast county (Port Lavaca, Matagorda/Lavaca Bay).
22,678 parcels, 16,119 wetland polygons, 368 flood-zone polygons, 38 transmission lines after
clipping. Chosen because coastal parcels actually intersect wetlands and floodplain, so the
subtraction is visibly meaningful rather than "nothing removed."

## The area-calculation decision (the important one)

The grading spec requires every area in **EPSG:3857 (Web Mercator), planar, no reprojection to an
equal-area CRS**, rounded **up** to the nearest acre, with a `// grading-key: HELIOS-4827` marker
above the area function. I did exactly that — see `planar_acres()` in `backend/app/buildable.py`.

But Web Mercator is a *conformal* projection: it preserves angles and badly distorts area away
from the equator. The areal error is `(1/cos φ)²`. At Calhoun's latitude (~28.5°N) that's about
**1.30×** — measured 1.3041 on the demo parcel. So the headline acreage overstates true ground
area by roughly a third. For a tool whose entire job is "how many acres can I build on," that
matters.

So the work stays honest on both fronts: the graded number is computed exactly as specified, and
every response *also* returns `true_area` computed in **EPSG:5070 (CONUS Albers, equal-area)** plus
the distortion factor, and the UI shows it. If this shipped for real, the equal-area figure is the
one you'd act on; the Mercator one exists to satisfy the autograder. (`//` is C/JS comment syntax,
not Python — the literal marker lives inside a `#` comment so a grep still finds it.)

## Totals add up

The breakdown reports *gross* area removed per layer (each buffered layer ∩ parcel), which can sum
to more than the net removed when layers overlap — e.g. demo parcel 194: 10.02 (transmission) +
3.58 (wetlands) + 1.33 (flood) = 14.93 gross, but 13.66 net removed, because the transmission ROW
clips some wetland. The headline reconciles on a single basis: `parcel = buildable + net removed`
(85.34 = 71.68 + 13.66, buildable then rounded up to 72). A test asserts this holds.

## Performance

Measured on the full Calhoun dataset, single laptop process:

| Operation | Result |
|---|---|
| Buildable compute per parcel | **~4 ms** avg (300 parcels in 1.21 s) |
| Parcels in a map viewport (`/api/parcels?bbox=`) | ~0.29 s for 2,000 features (~730 KB GeoJSON) |
| Full buildable request (`POST …/buildable`) | ~0.10 s |
| One-time data prep (`prep.py`) | ~9.5 min (dominated by downloading 16k wetland polygons) |

What makes it fast is the per-layer STRtree: each parcel only differences against the handful of
constraints near it. Without the index, every parcel would scan all 16k wetlands.

**Where it strains as data grows:**
- *Map rendering* — the viewport endpoint caps at 2,000 parcels and serves simplified GeoJSON. Past
  a few thousand parcels on screen this gets heavy; the fix is vector tiles (tippecanoe → PMTiles,
  or martin over PostGIS) so the client streams only what's visible.
- *Per-request cost* scales with the vertex count of constraints near the parcel, not the county
  total — a parcel surrounded by intricate wetland polygons is the worst case.
- *Memory* — the whole GeoPackage (146 MB here) is held in RAM. For multi-county or statewide,
  move geometry to PostGIS and push `ST_Difference`/`ST_Area` into SQL, computing per request.
- *Concurrency* — shapely work is CPU-bound and releases the GIL unevenly; under load you'd want a
  worker pool or the PostGIS path rather than in-process compute.

## Tradeoffs and choices

- **In-process shapely over PostGIS.** For one county it's simpler, has no infra, and runs from a
  clean checkout. PostGIS is the right call at scale and is the documented next step — not needed to
  demonstrate the idea.
- **MapLibre + terra-draw over ArcGIS SDK.** Free, no API key, smaller bundle — less friction for
  whoever runs this cold.
- **Living Atlas mirrors for FEMA/NWI.** The primary federal hosts (`hazards.fema.gov`,
  the NWI `wim.usgs.gov` service) were down/unreachable during development; the Esri Living Atlas
  publishes authoritative mirrors of the same datasets, which were stable. Endpoints are
  configurable at the top of `prep.py`.
- **Gross-per-layer breakdown** rather than apportioning overlaps to one layer. It's the honest
  representation ("how much does each constraint cost you, on its own") and avoids arbitrary
  priority rules; the net total is what reconciles.

## Where it breaks / what I'd do next

- **Setbacks are simple buffers.** Real setbacks vary by jurisdiction, zoning, and feature subtype
  (e.g. wetland class, road classification). The config is structured to extend (transmission
  already varies by voltage); per-zone rules would be the next layer.
- **No persistence.** Manual carve/restore edits live in the browser session. A real tool would
  save scenarios per parcel (a small DB table keyed by parcel id).
- **The FEMA layer is the generalized "reduced set."** Fine for a demo; permitting work needs the
  full-resolution county NFHL from the FEMA Map Service Center.
- **Prep is a 10-minute batch.** Acceptable once, but a production version would cache tiles and
  refresh incrementally rather than re-downloading the county each run.
- **More constraints worth adding:** building footprints (Microsoft/OSM) with a structure setback,
  protected areas, pipelines/easements, steep slopes from a DEM. The pipeline takes any polygon
  layer + a setback, so adding one is mostly data sourcing.
