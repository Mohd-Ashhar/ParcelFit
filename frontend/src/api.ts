import type {
  BuildableResponse,
  FeatureCollection,
  Geometry,
  Setbacks,
  SetbackConfig,
} from "./types";

export async function fetchSetbackConfig(): Promise<SetbackConfig> {
  const r = await fetch("/api/config/setbacks");
  return r.json();
}

export async function fetchParcels(bbox: [number, number, number, number]): Promise<FeatureCollection> {
  const r = await fetch(`/api/parcels?bbox=${bbox.join(",")}`);
  if (!r.ok) throw new Error("failed to load parcels");
  return r.json();
}

export async function fetchBuildable(
  pid: number,
  setbacks: Partial<Setbacks>,
  excludes: Geometry[],
  restores: Geometry[],
): Promise<BuildableResponse> {
  const r = await fetch(`/api/parcels/${pid}/buildable`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ setbacks, excludes, restores }),
  });
  if (!r.ok) throw new Error("failed to compute buildable area");
  return r.json();
}
