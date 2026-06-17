from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache

import yaml

FT_TO_M = 0.3048

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SETBACKS_PATH = os.environ.get("SETBACKS_PATH", os.path.join(ROOT, "config", "setbacks.yml"))
GPKG_PATH = os.environ.get("GPKG_PATH", os.path.join(ROOT, "data", "county.gpkg"))


@dataclass
class Setbacks:
    """Setback distances in feet, plus the flood zone filter. Loaded from setbacks.yml and
    overridable per request so the map controls can re-run without touching the file."""

    wetlands_ft: float
    flood_ft: float
    transmission_default_ft: float
    transmission_by_voltage: list[dict] = field(default_factory=list)

    def transmission_ft(self, voltage_kv: float | None) -> float:
        if voltage_kv is None:
            return self.transmission_default_ft
        width = self.transmission_default_ft
        for row in sorted(self.transmission_by_voltage, key=lambda r: r["min"]):
            if voltage_kv >= row["min"]:
                width = row["half_width_ft"]
        return width

    def with_overrides(self, **overrides) -> "Setbacks":
        clean = {k: v for k, v in overrides.items() if v is not None}
        return Setbacks(
            wetlands_ft=clean.get("wetlands_ft", self.wetlands_ft),
            flood_ft=clean.get("flood_ft", self.flood_ft),
            transmission_default_ft=clean.get("transmission_default_ft", self.transmission_default_ft),
            transmission_by_voltage=self.transmission_by_voltage,
        )


@lru_cache
def load_setbacks() -> Setbacks:
    with open(SETBACKS_PATH) as f:
        cfg = yaml.safe_load(f)
    t = cfg["transmission"]
    return Setbacks(
        wetlands_ft=cfg["wetlands"]["buffer_ft"],
        flood_ft=cfg["flood"]["buffer_ft"],
        transmission_default_ft=t["default_ft"],
        transmission_by_voltage=t["by_voltage_kv"],
    )
