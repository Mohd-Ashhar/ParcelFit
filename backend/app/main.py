from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from shapely.geometry import box

from . import buildable, geojson
from .config import GPKG_PATH, load_setbacks
from .data import WORKING_CRS, load_dataset
from .models import BuildableRequest

MAX_PARCELS_PER_VIEW = 2000
DISPLAY_SIMPLIFY_M = 2.0

state: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    state["ds"] = load_dataset(GPKG_PATH)
    state["setbacks"] = load_setbacks()
    yield
    state.clear()


app = FastAPI(title="ParcelFit — Buildable Land Analysis", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def ds():
    return state["ds"]


@app.get("/api/health")
def health():
    d = ds()
    return {"parcels": len(d.parcels), "wetlands": len(d.wetlands),
            "flood": len(d.flood), "transmission": len(d.transmission)}


@app.get("/api/config/setbacks")
def setbacks_config():
    s = state["setbacks"]
    return {
        "wetlands_ft": s.wetlands_ft,
        "flood_ft": s.flood_ft,
        "transmission_default_ft": s.transmission_default_ft,
        "sources": {
            "wetlands": "USACE 'Wetland Buffers: Use and Effectiveness'; CWA Section 404. 100 ft default.",
            "flood": "FEMA NFHL Special Flood Hazard Area (1% annual chance). Zone removed, no buffer.",
            "transmission": "Utility ROW standards (AEP) / NERC FAC-003. Half-width scales with kV.",
        },
    }


@app.get("/api/parcels")
def list_parcels(bbox: str = Query(..., description="minLon,minLat,maxLon,maxLat (EPSG:4326)")):
    try:
        minx, miny, maxx, maxy = (float(v) for v in bbox.split(","))
    except ValueError:
        raise HTTPException(400, "bbox must be 'minLon,minLat,maxLon,maxLat'")
    view = geojson.from_4326(box(minx, miny, maxx, maxy).__geo_interface__)
    d = ds()
    hits = d.parcels.iloc[d.parcels.sindex.query(view, predicate="intersects")]
    truncated = len(hits) > MAX_PARCELS_PER_VIEW
    hits = hits.head(MAX_PARCELS_PER_VIEW)
    features = [
        geojson.feature(
            row.geometry,
            {"pid": int(pid), "address": row.get("situs_addr"), "use": row.get("stat_land_use")},
            simplify_m=DISPLAY_SIMPLIFY_M,
        )
        for pid, row in hits.iterrows()
    ]
    return {"type": "FeatureCollection", "features": features, "truncated": truncated}


@app.get("/api/parcels/{pid}")
def get_parcel(pid: int):
    row = ds().parcel(pid)
    if row is None:
        raise HTTPException(404, "parcel not found")
    return geojson.feature(row.geometry, {"pid": pid, "address": row.get("situs_addr")})


@app.post("/api/parcels/{pid}/buildable")
def parcel_buildable(pid: int, req: BuildableRequest):
    d = ds()
    row = d.parcel(pid)
    if row is None:
        raise HTTPException(404, "parcel not found")

    setbacks = state["setbacks"].with_overrides(
        wetlands_ft=req.setbacks.wetlands_ft,
        flood_ft=req.setbacks.flood_ft,
        transmission_default_ft=req.setbacks.transmission_default_ft,
    )
    excludes = [geojson.from_4326(g) for g in req.excludes]
    restores = [geojson.from_4326(g) for g in req.restores]

    result = buildable.compute(d, row.geometry, setbacks, excludes, restores)
    summary = buildable.summarize(result)

    excl_features = [
        geojson.feature(geom, {"layer": layer}, simplify_m=DISPLAY_SIMPLIFY_M)
        for layer, geom in result.exclusions.items()
        if not geom.is_empty
    ]
    return {
        "pid": pid,
        "summary": summary,
        "parcel": geojson.feature(result.parcel, {"pid": pid}, simplify_m=DISPLAY_SIMPLIFY_M),
        "buildable": geojson.feature(result.buildable, {"kind": "buildable"}, simplify_m=DISPLAY_SIMPLIFY_M),
        "excluded": {"type": "FeatureCollection", "features": excl_features},
    }
