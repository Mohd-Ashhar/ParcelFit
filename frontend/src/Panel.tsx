import { LAYER_COLORS } from "./MapView";
import type { BuildableResponse, SetbackConfig, Setbacks } from "./types";

interface Props {
  config: SetbackConfig | null;
  setbacks: Setbacks | null;
  onSetbacks: (s: Setbacks) => void;
  result: BuildableResponse | null;
  busy: boolean;
  error: string | null;
  drawMode: "none" | "exclude" | "restore";
  onDrawMode: (m: "none" | "exclude" | "restore") => void;
  editCount: number;
  onClearEdits: () => void;
}

const LAYER_LABELS: Record<string, string> = {
  wetlands: "Wetlands",
  flood: "Flood (SFHA)",
  transmission: "Transmission",
  manual: "Manual carve-out",
};

export default function Panel(props: Props) {
  const { config, setbacks, onSetbacks, result, busy, error, drawMode, onDrawMode, editCount } = props;
  const s = result?.summary;

  const set = (k: keyof Setbacks, v: number) => setbacks && onSetbacks({ ...setbacks, [k]: v });

  return (
    <aside className="panel">
      <h1>ParcelFit</h1>
      <p className="sub">Buildable land analysis &middot; Calhoun County, Texas &middot; click a parcel</p>

      {!result && <p className="hint">Select a parcel on the map to compute its buildable area.</p>}

      {s && (
        <>
          <div className="totals">
            <div className="big">
              <span className="num">{s.buildable_acres}</span>
              <span className="unit">buildable acres</span>
            </div>
            <div className="row"><span>Parcel</span><b>{s.parcel_acres} ac</b></div>
            <div className="row"><span>Removed</span><b>{s.removed_acres} ac</b></div>
          </div>

          <h2>What was removed</h2>
          <table className="breakdown">
            <tbody>
              {s.breakdown.length === 0 && <tr><td className="muted">Nothing — fully buildable</td></tr>}
              {s.breakdown.map((b) => (
                <tr key={b.layer}>
                  <td><span className="dot" style={{ background: LAYER_COLORS[b.layer] }} />{LAYER_LABELS[b.layer] ?? b.layer}</td>
                  <td className="r">{b.removed_acres} ac</td>
                  <td className="r muted">{b.setback_ft != null ? `${b.setback_ft} ft` : ""}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <p className="note">
            Headline acres use EPSG:3857 planar area (grading spec), which overstates ground area by
            {" "}{s.true_area.distortion_factor}&times; here. True (equal-area) buildable:{" "}
            <b>{s.true_area.buildable_acres} ac</b>.
          </p>
        </>
      )}

      <h2>Adjust by hand</h2>
      <div className="btns">
        <button className={drawMode === "exclude" ? "on" : ""}
          disabled={!result}
          onClick={() => onDrawMode(drawMode === "exclude" ? "none" : "exclude")}>
          Carve out
        </button>
        <button className={drawMode === "restore" ? "on" : ""}
          disabled={!result}
          onClick={() => onDrawMode(drawMode === "restore" ? "none" : "restore")}>
          Restore
        </button>
        <button disabled={editCount === 0} onClick={props.onClearEdits}>Clear edits</button>
      </div>
      {drawMode !== "none" && <p className="hint">Click to add vertices, double-click to finish.</p>}

      {config && setbacks && (
        <>
          <h2>Setbacks</h2>
          <Slider label="Wetland buffer" value={setbacks.wetlands_ft} min={0} max={500} step={5}
            onChange={(v) => set("wetlands_ft", v)} hint={config.sources.wetlands} />
          <Slider label="Transmission ROW (half-width)" value={setbacks.transmission_default_ft}
            min={0} max={300} step={5} onChange={(v) => set("transmission_default_ft", v)}
            hint={config.sources.transmission} />
          <p className="src">Flood: {config.sources.flood}</p>
        </>
      )}

      {busy && <p className="status">computing…</p>}
      {error && <p className="status err">{error}</p>}
    </aside>
  );
}

function Slider({ label, value, min, max, step, onChange, hint }: {
  label: string; value: number; min: number; max: number; step: number;
  onChange: (v: number) => void; hint: string;
}) {
  return (
    <div className="slider" title={hint}>
      <div className="slider-top"><span>{label}</span><b>{value} ft</b></div>
      <input type="range" min={min} max={max} step={step} value={value}
        onChange={(e) => onChange(Number(e.target.value))} />
    </div>
  );
}
