# Croskell projects app

Open `index.html` in a browser (double-click; no install or server needed – the imagery basemap needs internet).

- **Plan map as printed:** Plan 2, 3 or 4 placed on the ground (opacity slider). Placed by its PSP boundary line, median 2.4 m.
- **Hover** a project on the map or in the table: both highlight, with a tooltip.
- **Click** a table row: the project is selected and the map zooms to it. **Click** a project on the map: its row is selected and scrolled into view.
- **Filters** (search, category, levy component, plan map, only in map view) apply to the table and the map together.
- **Land acquired / Status** cells are editable; entries are saved in this browser.
- **Export filtered / Export all** writes `.xlsx` in the project-register schema (`data/reference/export_schema.xlsx`), plus Details, the tables as printed and an About sheet. **Import edits** loads Land acquired / Status back from an exported file.

Rebuild the data with `python tools/build_croskell_gpkg.py` then `python tools/build_croskell_app.py`.
Libraries (vendored): MapLibre GL JS 4.7.1 (BSD-3), SheetJS 0.18.5 (Apache-2.0), Noto Sans glyphs (OFL). Icons: Mapbox Maki (CC0).
