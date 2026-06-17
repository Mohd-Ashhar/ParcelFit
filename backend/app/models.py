from __future__ import annotations

from pydantic import BaseModel, Field


class SetbackOverrides(BaseModel):
    wetlands_ft: float | None = Field(default=None, ge=0, le=2000)
    flood_ft: float | None = Field(default=None, ge=0, le=2000)
    transmission_default_ft: float | None = Field(default=None, ge=0, le=2000)


class BuildableRequest(BaseModel):
    setbacks: SetbackOverrides = Field(default_factory=SetbackOverrides)
    # GeoJSON geometries (EPSG:4326) drawn on the map.
    excludes: list[dict] = Field(default_factory=list)
    restores: list[dict] = Field(default_factory=list)
