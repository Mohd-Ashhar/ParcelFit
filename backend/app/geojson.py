from __future__ import annotations

from shapely.geometry import mapping, shape
from shapely.geometry.base import BaseGeometry

from .buildable import _reproject
from .data import WORKING_CRS


def to_4326(geom: BaseGeometry):
    return mapping(_reproject(geom, WORKING_CRS, 4326))


def from_4326(geojson_geom: dict) -> BaseGeometry:
    return _reproject(shape(geojson_geom), 4326, WORKING_CRS)


def feature(geom_5070: BaseGeometry, props: dict, simplify_m: float = 0.0) -> dict:
    if simplify_m and not geom_5070.is_empty:
        geom_5070 = geom_5070.simplify(simplify_m, preserve_topology=True)
    return {"type": "Feature", "properties": props, "geometry": to_4326(geom_5070)}
