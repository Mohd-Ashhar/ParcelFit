from __future__ import annotations

from dataclasses import dataclass

import geopandas as gpd
from shapely.geometry.base import BaseGeometry

WORKING_CRS = 5070


@dataclass
class Dataset:
    parcels: gpd.GeoDataFrame
    wetlands: gpd.GeoDataFrame
    flood: gpd.GeoDataFrame
    transmission: gpd.GeoDataFrame

    def parcel(self, pid: int) -> gpd.GeoSeries | None:
        if pid not in self.parcels.index:
            return None
        return self.parcels.loc[pid]

    def near(self, layer: str, geom: BaseGeometry) -> gpd.GeoDataFrame:
        """Constraints from `layer` whose bounding box intersects `geom`'s, via the spatial index."""
        gdf = getattr(self, layer)
        if gdf.empty:
            return gdf
        hits = gdf.sindex.query(geom, predicate="intersects")
        return gdf.iloc[hits]


def load_dataset(gpkg_path: str) -> Dataset:
    layers = {}
    for name in ("parcels", "wetlands", "flood", "transmission"):
        gdf = gpd.read_file(gpkg_path, layer=name).to_crs(WORKING_CRS)
        gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty]
        gdf.sindex  # build the index up front
        layers[name] = gdf
    parcels = layers["parcels"].reset_index(drop=True)
    parcels.index.name = "pid"
    layers["parcels"] = parcels
    return Dataset(**layers)
