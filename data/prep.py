"""Fetch parcels and constraint layers for one Texas county and write a single GeoPackage.

Run once before starting the backend:

    python data/prep.py --county CALHOUN --out data/county.gpkg

Everything is pulled from public ArcGIS REST services (no auth). The authoritative FEMA
and USFWS hosts (hazards.fema.gov, the NWI wim.usgs.gov service) were unreachable / 500ing
during development, so the flood and wetland layers come from the Esri Living Atlas mirrors
of the same federal datasets. Sources are documented in data/SOURCES.md.

Output layers, all stored in EPSG:5070 (NAD83 / CONUS Albers, equal-area metres):
    parcels, wetlands, flood, transmission
"""

import argparse
import sys
import time

import geopandas as gpd
import pandas as pd
import requests
from shapely import make_valid

WORKING_CRS = 5070
PAGE = 2000

PARCELS_URL = (
    "https://feature.geographic.texas.gov/arcgis/rest/services/"
    "Parcels/stratmap_land_parcels_48_most_recent/MapServer/0"
)
WETLANDS_URL = (
    "https://services.arcgis.com/P3ePLMYs2RVChkJx/arcgis/rest/services/"
    "USA_Wetlands/FeatureServer/0"
)
FLOOD_URL = (
    "https://services.arcgis.com/P3ePLMYs2RVChkJx/arcgis/rest/services/"
    "USA_Flood_Hazard_Reduced_Set_gdb/FeatureServer/0"
)
TRANSMISSION_URL = (
    "https://services2.arcgis.com/FiaPA4ga0iQKduv3/arcgis/rest/services/"
    "US_Electric_Power_Transmission_Lines/FeatureServer/0"
)

# Max setback we'll ever apply, used to clip constraints to a tight band around the parcels
# so we don't carry wetlands sitting out in open bay water that can never affect a parcel.
CLIP_PAD_M = 300

session = requests.Session()
session.headers["User-Agent"] = "buildable-land-prep"


def _fetch(url, where="1=1", geometry=None, out_fields="*"):
    """Page through an ArcGIS REST layer and return a GeoDataFrame in EPSG:4326."""
    frames = []
    offset = 0
    while True:
        params = {
            "where": where,
            "outFields": out_fields,
            "outSR": 4326,
            "f": "geojson",
            "resultOffset": offset,
            "resultRecordCount": PAGE,
        }
        if geometry is not None:
            params.update(
                geometry=geometry,
                geometryType="esriGeometryEnvelope",
                inSR=4326,
                spatialRel="esriSpatialRelIntersects",
            )
        for attempt in range(3):
            try:
                r = session.get(url + "/query", params=params, timeout=120)
                r.raise_for_status()
                gj = r.json()
                break
            except (requests.RequestException, ValueError):
                if attempt == 2:
                    raise
                time.sleep(2 * (attempt + 1))
        feats = gj.get("features", [])
        if not feats:
            break
        frames.append(gpd.GeoDataFrame.from_features(feats, crs=4326))
        print(f"    +{len(feats)} (total {sum(len(f) for f in frames)})")
        if not gj.get("properties", {}).get("exceededTransferLimit") and len(feats) < PAGE:
            break
        offset += len(feats)
    if not frames:
        return gpd.GeoDataFrame(geometry=[], crs=4326)
    return gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs=4326)


def _clean(gdf):
    gdf = gdf[~gdf.geometry.is_empty & gdf.geometry.notna()].copy()
    invalid = ~gdf.geometry.is_valid
    if invalid.any():
        gdf.loc[invalid, "geometry"] = gdf.loc[invalid, "geometry"].apply(make_valid)
    return gdf.to_crs(WORKING_CRS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--county", default="CALHOUN")
    ap.add_argument("--out", default="data/county.gpkg")
    args = ap.parse_args()
    county = args.county.upper()

    print(f"parcels: {county}")
    parcels = _fetch(
        PARCELS_URL,
        where=f"county='{county}'",
        out_fields="prop_id,owner_name,situs_addr,situs_city,gis_area,land_value,stat_land_use",
    )
    if parcels.empty:
        sys.exit(f"no parcels found for county {county!r}")
    parcels = _clean(parcels)

    bbox4326 = parcels.to_crs(4326).total_bounds
    env = ",".join(f"{v:.6f}" for v in bbox4326)
    clip_region = parcels.union_all().buffer(CLIP_PAD_M)

    print("wetlands")
    wet = _fetch(WETLANDS_URL, geometry=env, out_fields="WETLAND_TYPE,ATTRIBUTE,SYSTEM_NAME")
    wet = _clean(wet).clip(clip_region)

    print("flood")
    flood = _fetch(FLOOD_URL, geometry=env, out_fields="FLD_ZONE,ZONE_SUBTY,SFHA_TF")
    flood = _clean(flood)
    flood = flood[flood["SFHA_TF"] == "T"].clip(clip_region)  # Special Flood Hazard Area only

    print("transmission")
    trans = _fetch(TRANSMISSION_URL, geometry=env, out_fields="VOLTAGE,VOLT_CLASS,OWNER")
    trans = _clean(trans).clip(clip_region)

    for name, gdf in [("parcels", parcels), ("wetlands", wet), ("flood", flood), ("transmission", trans)]:
        gdf.to_file(args.out, layer=name, driver="GPKG")
        print(f"wrote {name}: {len(gdf)} features")
    print(f"done -> {args.out}")


if __name__ == "__main__":
    main()
