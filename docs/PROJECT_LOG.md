# Project log

## 2026-11-14
- Owner asked for map-and-table linking (hover, click to highlight and zoom both ways, shared filters) and an Excel export in their schema (`export_schema.xlsx`). **Decision:** a static web app rather than a QGIS project, because the linking is interactive; the GeoPackage and GeoTIFFs remain for QGIS.
- Export rows: one per project and levy component, so a project with both construction and land (e.g. IN-01: Table 5 and Table 8) has two rows. "Land acquired" and "Current status" are not in the plan: the owner fills them in the app.
- Plan 3 draws SR-01 and SR-02 as one joined shape; split along the VPA FUS reserve extents.

## 2026-11-13
- Owner created this repository for the Casey Fields Boulevard project only, after saving the Contribution-Plans website work (commit `ad2cb2b`). A website or dashboard for this project is still to be decided.
- First task (owner): Croskell – georeference its two major maps, make them filterable, and connect each layer and feature to the plan's tables. Symbology to use github.com/GISsymbology: its usable parts here are the Mapbox Maki icons and road signs (CC0) and north arrows (CC BY-SA 2.5); its geology and seismic sets do not apply.
