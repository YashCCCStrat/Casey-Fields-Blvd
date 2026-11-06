# Architecture

```
sources/pdfs/ ── tools/georef.py ──────────────► gis/croskell/georeferenced/*.tif
data/reference/croskell/table*.csv ─┐
gis/croskell/v2_from_contribution_plans/ ─┼─ tools/build_croskell_gpkg.py ─► gis/croskell/croskell.gpkg
gis/croskell/vpa_fus_croskell.gpkg ──┘                                        │
                                              tools/build_croskell_app.py ◄─┘ ─► app/croskell/data.js (+ index.html)
```
- `data/reference/plan_figures.json`: each plan map's PDF page and affine (pixels → MGA55).
- `data/reference/export_schema.xlsx`: the owner's project-register layout used by the app's Excel export.
- Joins: everything by the printed project ID (`CK-…`); map features also carry which plan map they belong to.
- The app is static (no server): MapLibre, SheetJS and the fonts are vendored in `app/croskell/vendor/`; edits to
  Land acquired / Status live in the browser (localStorage) and travel via the exported Excel file.

## App (2026-11-15)
- `app/common/viewer.js` + `viewer.css`: one viewer for every plan; `app/index.html` loads every plan's `data.js` (each appends to `window.PLANS`; ids are prefixed with the plan area when merged: meta, maps, images, classes = legend/symbology, features, rows, columns, detail fields, totals, export mapping, printed tables).
- `tools/appdata.py`: shared helpers (`solid()` one-shape-per-item, `image_entry()` plan image + corners, `write_app()`).
- Builders: `tools/build_croskell_gpkg.py` + `build_croskell_app.py`; `tools/collison_tables.py` + `build_collison.py`.

## Editing loop (latest)
```
plan PDFs ─ build_croskell_app.py / build_collison.py ─(first run, or CFB_RESEED)─► gis/edit/casey_fields_blvd.gpkg ◄── QGIS (casey_fields_blvd.qgz)
                       │                                                                   ▲      │
                       └─► data/app/<area>_spec.json (maps, images, legend classes,        │      │
                           columns, export mapping)                                        │      ▼
app "Changes for repo" ─► gis/edit/inbox/*.geojson ─ tools/apply_inbox.py ─────────────────┘  tools/check_edits.py
                                                                                                   │
                         tools/build_app.py (spec + GeoPackage) ─► app/<area>/data.js ◄────────────┤
                         tools/export_shapefiles.py ─► gis/edit/shapefiles/, *_shapefiles.zip ◄────┘
```
- The GitHub Action `rebuild-app.yml` runs apply_inbox → check_edits → build_app → export_shapefiles on push and commits
  the results as the owner. `tools/build_qgis_project.py` (QGIS Python) regenerates the `.qgz` when layers change.
- The builders write the spec every run but seed the GeoPackage only when the area's table is missing, so QGIS edits
  are not overwritten.
- In the browser: table edits in localStorage `casey-fields-blvd-edits-v1`, added features in `cfb-new-features-v1`;
  turf.js (vendored) for the draw filter (buffer, intersects).
