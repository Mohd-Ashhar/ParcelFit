import { useCallback, useEffect, useRef, useState } from "react";
import MapView from "./MapView";
import Panel from "./Panel";
import { fetchBuildable, fetchSetbackConfig } from "./api";
import type { BuildableResponse, Geometry, SetbackConfig, Setbacks } from "./types";

export default function App() {
  const [config, setConfig] = useState<SetbackConfig | null>(null);
  const [setbacks, setSetbacks] = useState<Setbacks | null>(null);
  const [pid, setPid] = useState<number | null>(null);
  const [result, setResult] = useState<BuildableResponse | null>(null);
  const [excludes, setExcludes] = useState<Geometry[]>([]);
  const [restores, setRestores] = useState<Geometry[]>([]);
  const [drawMode, setDrawMode] = useState<"none" | "exclude" | "restore">("none");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchSetbackConfig().then((c) => {
      setConfig(c);
      setSetbacks({ wetlands_ft: c.wetlands_ft, flood_ft: c.flood_ft,
        transmission_default_ft: c.transmission_default_ft });
    });
  }, []);

  // Reset hand edits only when a different parcel is chosen. Re-selecting the same parcel
  // (which can happen from a stray click right after finishing a drawn polygon) keeps them.
  useEffect(() => {
    setExcludes([]);
    setRestores([]);
  }, [pid]);

  const recompute = useCallback(async () => {
    if (pid == null || !setbacks) return;
    setBusy(true);
    setError(null);
    try {
      setResult(await fetchBuildable(pid, setbacks, excludes, restores));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }, [pid, setbacks, excludes, restores]);

  // Debounce so dragging a setback slider doesn't fire a request per pixel.
  const timer = useRef<number | undefined>(undefined);
  useEffect(() => {
    if (pid == null) return;
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(recompute, 180);
    return () => window.clearTimeout(timer.current);
  }, [recompute, pid]);

  const onSelectParcel = useCallback((p: number) => setPid(p), []);

  const onDrawComplete = useCallback((geom: Geometry, mode: "exclude" | "restore") => {
    if (mode === "exclude") setExcludes((xs) => [...xs, geom]);
    else setRestores((xs) => [...xs, geom]);
    setDrawMode("none");
  }, []);

  const clearEdits = () => { setExcludes([]); setRestores([]); };

  return (
    <div className="app">
      <MapView
        result={result}
        drawMode={drawMode}
        onSelectParcel={onSelectParcel}
        onDrawComplete={onDrawComplete}
      />
      <Panel
        config={config}
        setbacks={setbacks}
        onSetbacks={setSetbacks}
        result={result}
        busy={busy}
        error={error}
        drawMode={drawMode}
        onDrawMode={setDrawMode}
        editCount={excludes.length + restores.length}
        onClearEdits={clearEdits}
      />
    </div>
  );
}
