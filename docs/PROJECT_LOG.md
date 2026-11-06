# Project log

## Latest
- Owner wants to edit every column, keep the shapes as shapefiles with their table for QGIS, make them more accurate there and push back; add points, lines and polygons with an automatic table row; and filter projects by drawing. **Decision:** one GeoPackage (`gis/edit/`) is the editable source of truth; a GitHub Action rebuilds the app and shapefiles from it. Shapefiles are export-only (10-character field names, no multi-layer joins). App changes reach the repository as a GeoJSON file in `gis/edit/inbox/` that the Action applies, because the static app cannot write to GitHub without a token in the page.
- The Action cannot be tested from the sandbox; its steps were run locally (apply, check, build, export) on a test inbox file and a QGIS-drawn point.

## 2026-11-15
- Owner wants Croskell and Collison viewable together, not chosen on a landing page. **Decision:** one page; plan areas are on/off switches; printed plan maps are independent overlays.

## 2026-11-14
- Owner asked for intersection construction projects to look like intersections (red outlines as reference). **Decision:** derive the footprint from the named roads' OSM carriageways within the plan bar's extent, rather than widening the bar; the plan bar still decides which legs are included.
- Owner asked for map-and-table linking (hover, click to highlight and zoom both ways, shared filters) and an Excel export in their schema (`export_schema.xlsx`). **Decision:** a static web app rather than a QGIS project, because the linking is interactive; the GeoPackage and GeoTIFFs remain for QGIS.
- Export rows: one per project and levy component, so a project with both construction and land (e.g. IN-01: Table 5 and Table 8) has two rows. "Land acquired" and "Current status" are not in the plan: the owner fills them in the app.
- Plan 3 draws SR-01 and SR-02 as one joined shape; split along the VPA FUS reserve extents.

## 2026-11-13
- Owner created this repository for the Casey Fields Boulevard project only, after saving the Contribution-Plans website work (commit `ad2cb2b`). A website or dashboard for this project is still to be decided.
- First task (owner): Croskell – georeference its two major maps, make them filterable, and connect each layer and feature to the plan's tables. Symbology to use github.com/GISsymbology: its usable parts here are the Mapbox Maki icons and road signs (CC0) and north arrows (CC BY-SA 2.5); its geology and seismic sets do not apply.
