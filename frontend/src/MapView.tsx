import { useEffect, useRef } from "react";
import maplibregl, { type GeoJSONSource } from "maplibre-gl";
import { TerraDraw, TerraDrawPolygonMode } from "terra-draw";
import { TerraDrawMapLibreGLAdapter } from "terra-draw-maplibre-gl-adapter";
import { fetchParcels } from "./api";
import type { BuildableResponse, Geometry } from "./types";

const CALHOUN_CENTER: [number, number] = [-96.62, 28.52];

export const LAYER_COLORS: Record<string, string> = {
  wetlands: "#2563eb",
  flood: "#06b6d4",
  transmission: "#f59e0b",
  manual: "#dc2626",
};

interface Props {
  result: BuildableResponse | null;
  drawMode: "none" | "exclude" | "restore";
  onSelectParcel: (pid: number) => void;
  onDrawComplete: (geom: Geometry, mode: "exclude" | "restore") => void;
}

const EMPTY: GeoJSON.FeatureCollection = { type: "FeatureCollection", features: [] };

export default function MapView({ result, drawMode, onSelectParcel, onDrawComplete }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const draw = useRef<TerraDraw | null>(null);
  const drawModeRef = useRef(drawMode);
  const onDrawCompleteRef = useRef(onDrawComplete);
  drawModeRef.current = drawMode;
  onDrawCompleteRef.current = onDrawComplete;

  useEffect(() => {
    if (!container.current) return;
    const m = new maplibregl.Map({
      container: container.current,
      style: "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
      center: CALHOUN_CENTER,
      zoom: 11,
    });
    map.current = m;
    if (import.meta.env.DEV) (window as unknown as { __map?: maplibregl.Map }).__map = m;

    m.on("load", () => {
      m.addSource("parcels", { type: "geojson", data: EMPTY });
      m.addLayer({ id: "parcels-fill", type: "fill", source: "parcels",
        paint: { "fill-color": "#94a3b8", "fill-opacity": 0.08 } });
      m.addLayer({ id: "parcels-line", type: "line", source: "parcels",
        paint: { "line-color": "#64748b", "line-width": 0.6 } });

      m.addSource("excluded", { type: "geojson", data: EMPTY });
      m.addLayer({ id: "excluded-fill", type: "fill", source: "excluded",
        paint: {
          "fill-color": ["match", ["get", "layer"],
            "wetlands", LAYER_COLORS.wetlands, "flood", LAYER_COLORS.flood,
            "transmission", LAYER_COLORS.transmission, "manual", LAYER_COLORS.manual, "#999"],
          "fill-opacity": 0.5,
        } });

      m.addSource("buildable", { type: "geojson", data: EMPTY });
      m.addLayer({ id: "buildable-fill", type: "fill", source: "buildable",
        paint: { "fill-color": "#16a34a", "fill-opacity": 0.5 } });

      m.addSource("selected", { type: "geojson", data: EMPTY });
      m.addLayer({ id: "selected-line", type: "line", source: "selected",
        paint: { "line-color": "#1d4ed8", "line-width": 2.5 } });

      m.on("click", "parcels-fill", (e) => {
        const f = e.features?.[0];
        if (f && drawModeRef.current === "none") onSelectParcel(f.properties!.pid as number);
      });
      m.on("mouseenter", "parcels-fill", () => { m.getCanvas().style.cursor = "pointer"; });
      m.on("mouseleave", "parcels-fill", () => { m.getCanvas().style.cursor = ""; });

      const loadParcels = async () => {
        const b = m.getBounds();
        try {
          const fc = await fetchParcels([b.getWest(), b.getSouth(), b.getEast(), b.getNorth()]);
          (m.getSource("parcels") as GeoJSONSource)?.setData(fc);
        } catch { /* out of county / transient */ }
      };
      m.on("moveend", loadParcels);
      loadParcels();

      draw.current = new TerraDraw({
        adapter: new TerraDrawMapLibreGLAdapter({ map: m }),
        modes: [new TerraDrawPolygonMode()],
      });
      draw.current.start();
      if (import.meta.env.DEV) (window as unknown as { __draw?: TerraDraw }).__draw = draw.current;
      draw.current.on("finish", (id) => {
        const feat = draw.current!.getSnapshot().find((f) => f.id === id);
        const mode = drawModeRef.current;
        if (feat && feat.geometry.type === "Polygon" && mode !== "none") {
          onDrawCompleteRef.current(feat.geometry as Geometry, mode);
        }
        draw.current!.clear();
      });
    });

    return () => { m.remove(); };
  }, [onSelectParcel]);

  useEffect(() => {
    const d = draw.current;
    if (!d) return;
    d.setMode(drawMode === "none" ? "static" : "polygon");
  }, [drawMode]);

  useEffect(() => {
    const m = map.current;
    if (!m || !m.isStyleLoaded()) return;
    const setData = (id: string, data: GeoJSON.GeoJSON) =>
      (m.getSource(id) as GeoJSONSource)?.setData(data);
    if (result) {
      setData("buildable", result.buildable);
      setData("excluded", result.excluded);
      setData("selected", result.parcel);
    } else {
      setData("buildable", EMPTY);
      setData("excluded", EMPTY);
      setData("selected", EMPTY);
    }
  }, [result]);

  return <div ref={container} className="map" />;
}
