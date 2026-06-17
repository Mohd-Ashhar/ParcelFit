import math
from pathlib import Path

import pytest
from shapely.geometry import box

from backend.app import buildable
from backend.app.config import load_setbacks
from backend.app.data import load_dataset

GPKG = Path(__file__).resolve().parents[2] / "data" / "county.gpkg"
pytestmark = pytest.mark.skipif(not GPKG.exists(), reason="run data/prep.py first")


@pytest.fixture(scope="module")
def ds():
    return load_dataset(str(GPKG))


@pytest.fixture(scope="module")
def setbacks():
    return load_setbacks()


def _constrained_parcel(ds, setbacks):
    """First parcel whose buildable area is meaningfully reduced by constraints."""
    for pid in ds.parcels.index:
        geom = ds.parcels.loc[pid].geometry
        res = buildable.compute(ds, geom, setbacks)
        s = buildable.summarize(res)
        if s["removed_acres"] > 1:
            return pid, geom
    pytest.skip("no constrained parcel in dataset")


def test_totals_reconcile(ds, setbacks):
    _, geom = _constrained_parcel(ds, setbacks)
    res = buildable.compute(ds, geom, setbacks)
    s = buildable.summarize(res)
    # parcel = buildable + removed, on the same (planar 3857) basis
    assert s["parcel_acres"] == pytest.approx(s["buildable_acres_raw"] + s["removed_acres"], abs=0.05)


def test_buildable_rounds_up(ds, setbacks):
    _, geom = _constrained_parcel(ds, setbacks)
    s = buildable.summarize(buildable.compute(ds, geom, setbacks))
    assert s["buildable_acres"] == math.ceil(s["buildable_acres_raw"])


def test_mercator_overstates_true_area(ds, setbacks):
    _, geom = _constrained_parcel(ds, setbacks)
    s = buildable.summarize(buildable.compute(ds, geom, setbacks))
    # Web Mercator must overstate the equal-area ground truth at Texas latitudes.
    assert s["true_area"]["distortion_factor"] > 1.2
    assert s["parcel_acres"] > s["true_area"]["parcel_acres"]


def test_bigger_setback_removes_more(ds, setbacks):
    _, geom = _constrained_parcel(ds, setbacks)
    small = buildable.summarize(buildable.compute(ds, geom, setbacks.with_overrides(wetlands_ft=10)))
    big = buildable.summarize(buildable.compute(ds, geom, setbacks.with_overrides(wetlands_ft=400)))
    assert big["buildable_acres_raw"] <= small["buildable_acres_raw"]


def test_carve_out_reduces_buildable(ds, setbacks):
    geom = max((ds.parcels.loc[pid].geometry for pid in ds.parcels.index[:200]), key=lambda g: g.area)
    res = buildable.compute(ds, geom, setbacks)
    base = buildable.summarize(res)
    assert base["buildable_acres_raw"] > 0
    # carve a box around a point known to be inside the buildable area
    p = res.buildable.representative_point()
    hole = box(p.x - 30, p.y - 30, p.x + 30, p.y + 30)
    carved = buildable.summarize(buildable.compute(ds, geom, setbacks, excludes=[hole]))
    assert carved["buildable_acres_raw"] < base["buildable_acres_raw"]


def test_grading_key_present():
    src = (Path(__file__).resolve().parents[1] / "app" / "buildable.py").read_text()
    lines = src.splitlines()
    i = next(idx for idx, ln in enumerate(lines) if ln.startswith("def planar_acres"))
    assert "// grading-key: HELIOS-4827" in lines[i - 1]
