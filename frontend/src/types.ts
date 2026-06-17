export type Geometry = GeoJSON.Geometry;
export type Feature = GeoJSON.Feature;
export type FeatureCollection = GeoJSON.FeatureCollection;

export interface BreakdownRow {
  layer: string;
  removed_acres: number;
  setback_ft: number | null;
}

export interface Summary {
  parcel_acres: number;
  buildable_acres: number;
  buildable_acres_raw: number;
  removed_acres: number;
  breakdown: BreakdownRow[];
  true_area: {
    parcel_acres: number;
    buildable_acres: number;
    distortion_factor: number | null;
  };
}

export interface BuildableResponse {
  pid: number;
  summary: Summary;
  parcel: Feature;
  buildable: Feature;
  excluded: FeatureCollection;
}

export interface Setbacks {
  wetlands_ft: number;
  flood_ft: number;
  transmission_default_ft: number;
}

export interface SetbackConfig extends Setbacks {
  sources: Record<string, string>;
}
