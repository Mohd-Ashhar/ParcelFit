# Data sources

All public, no auth, pulled live by `data/prep.py` from ArcGIS REST services.

| Layer | Source | Endpoint used | Notes |
|---|---|---|---|
| Parcels | Texas Geographic Information Office (TxGIO/TNRIS) StratMap Land Parcels | `feature.geographic.texas.gov/.../Parcels/stratmap_land_parcels_48_most_recent/MapServer/0` | Statewide; filtered to one county. Served in EPSG:3857. |
| Wetlands | USFWS National Wetlands Inventory (via Esri Living Atlas mirror) | `services.arcgis.com/P3ePLMYs2RVChkJx/.../USA_Wetlands/FeatureServer/0` | `WETLAND_TYPE`, `ATTRIBUTE`. |
| Flood | FEMA National Flood Hazard Layer (via Esri Living Atlas mirror) | `services.arcgis.com/P3ePLMYs2RVChkJx/.../USA_Flood_Hazard_Reduced_Set_gdb/FeatureServer/0` | Filtered to `SFHA_TF='T'` (1% annual chance Special Flood Hazard Area). |
| Transmission | HIFLD Electric Power Transmission Lines | `services2.arcgis.com/FiaPA4ga0iQKduv3/.../US_Electric_Power_Transmission_Lines/FeatureServer/0` | Lines; `VOLTAGE` drives ROW half-width. |

## Why the Living Atlas mirrors for FEMA and wetlands

The primary federal hosts were unreachable during development: `hazards.fema.gov`
(FEMA NFHL) failed TLS handshake, and the USFWS NWI service at `wim.usgs.gov` returned
HTTP 500. The Esri Living Atlas publishes authoritative mirrors of the same federal
datasets, which were stable, so `prep.py` uses those. The endpoints are configurable at
the top of `prep.py` if the primary hosts come back.

The FEMA layer is the "reduced set" (lightly generalized) NFHL — fine for this exercise;
for permitting work you'd pull the full-resolution county NFHL from the FEMA Map Service
Center.

## Setback distances

See `config/setbacks.yml` for values and citations. Summary:

- **Wetlands — 100 ft** buffer. USACE *Wetland Buffers: Use and Effectiveness*; Clean Water
  Act §404 context. 100 ft is the width most consistently cited as effective for water
  quality and habitat.
- **Flood (SFHA) — 0 ft** extra buffer; the 1% annual chance zone is removed as-is (FEMA NFIP).
- **Transmission — half-width by voltage** (50 ft <100 kV up to 125 ft at 500 kV+),
  75 ft default for unknown voltage. Utility ROW standards (AEP transmission facts) and
  NERC FAC-003 vegetation clearance practice.
