# Editing the projects: app, QGIS, and back to the repository

The **source of truth** for project shapes and table values is `gis/edit/casey_fields_blvd.gpkg` (EPSG:7855,
GDA2020 / MGA zone 55). The app (`app/*/data.js`) and the shapefiles are rebuilt from it by the GitHub Action
*Rebuild app from GIS edits* (`.github/workflows/rebuild-app.yml`) every time it, or a file in `gis/edit/inbox/`, is
pushed to `main`.

| In the GeoPackage | What it holds |
|---|---|
| `<area>_projects` | The project table: one row per project and levy component (`rid` is the row id) |
| `<area>_<map>_polygons` / `_lines` / `_points` | Shapes per plan map (`plan2`, `plan3`, `plan4`, `fig3`); empty layers are there so any kind of shape can be drawn |
| `<area>_context_polygons` | Plan boundary (not a project) |

Shape fields: `project_id` (links to the table), `map`, `cls` (legend class), `legend`, `title`, `category`, `note`, (`rot`).

## A. In the app (small changes, no GIS software)
1. **Edit table** switch: every column can be edited; edited cells are highlighted; *Discard edits* undoes them.
2. **Add feature** (Point / Line / Polygon, top of the map): click to place points, double-click or Enter to finish, Esc to
   cancel. A form asks for plan area, plan map, legend class, project ID, title and the other values; the row is added to
   the table. Using an existing project ID on the same plan map adds the shape to that project with no new row.
   An added shape can be deleted from its card.
3. **Filter by drawing** (Area / Line ± m): only projects touching the drawn area, or within the buffer of the line, stay in
   the table. Clear with ✕ or Reset.
4. App edits and added features are kept **in your browser only**. To put them in the repository:
   **Changes for repo** → `changes-YYYY-MM-DD.geojson` → save it in `gis/edit/inbox/` in your copy of the repository →
   commit and push (GitHub Desktop). The Action applies it (`tools/apply_inbox.py`), moves the file to
   `gis/edit/inbox/applied/`, and rebuilds the app. Then clear your browser copies (*Discard edits*, and delete
   added shapes) so they are not sent twice. Sending the same file twice adds the shapes twice.
5. **Exports** (for use elsewhere; they never change the repository). All include your edits and added features.

   | Button | Rows | Format |
   |---|---|---|
   | **Export to Excel** (table bar) | The rows the table shows now: search, plan map, category chips, *only projects in map view*, drawn-shape filter; in the table's sort order. With no filter on, every row of the plan areas switched on in the header | Excel: your register schema + *Details* (every column, with Row ID) + the printed tables + *About* (records which filters were on) |
   | **GIS export** | Rows shown, one feature per row with its shape | GeoJSON (opens in QGIS) |
   | **Changes for repo** | Only what you changed: edited rows and added shapes | GeoJSON for `gis/edit/inbox/` |

6. **Import edits** (table bar, next to Export to Excel) restores your changes into this browser, e.g. on another computer or after clearing it:
   - an **Excel file exported by this app**: values in its *Details* sheet that differ from the plan become
     edits, matched by *Row ID*. Every column counts. Rows of added features are not in the plan, so they are skipped;
     the other sheets are ignored. Excel files not made by this app (no *Details* sheet) are refused.
   - a **Changes for repo** file: its edits and added shapes come back. Shapes already in the browser are skipped, so
     importing twice does not duplicate them.
   Import does not change the repository either; for that, push the Changes for repo file (step 4).

## B. In QGIS (reshaping, accurate drawing)
1. Pull the repository (GitHub Desktop → Fetch / Pull).
2. Open `gis/edit/casey_fields_blvd.qgz` (QGIS 3.28 or later). Each plan area is a group: its project table, each plan
   map's shape layers (styled as in the app, labelled by project ID, joined to the table as `table_*` fields) and the
   plan map *as printed* (GeoTIFF, hidden: tick it to trace against it). Esri imagery is at the bottom.
3. Edit:
   - **Reshape**: toggle editing on a layer, use the Vertex tool, save.
   - **Change values**: edit the project table layer (attribute table), save.
   - **Add a shape for an existing project**: draw in the plan map's layer of the right type; set `project_id`
     and pick `cls` from the drop-down.
   - **Add a new project**: draw it, set a new `project_id`, and `title` / `category` / `note`. When pushed, the
     Action adds a table row from them (status *Added in QGIS – fill in details*); fill in the rest in the table later.
     If `map` or `cls` is left empty it is filled in from the layer (the *Added feature* class).
4. Save, close QGIS (it holds the file open), commit `gis/edit/casey_fields_blvd.gpkg` and push.
5. The Action checks the edits (`tools/check_edits.py`): a wrong coordinate system, unknown legend class or duplicate
   row id stops the run and nothing changes; see the run's log on GitHub → Actions. Otherwise it rebuilds
   `app/*/data.js`, `gis/edit/shapefiles/` and the zip, and commits them back. Pull afterwards.

The same steps run locally:
```
python tools/apply_inbox.py && python tools/check_edits.py && python tools/build_app.py && python tools/export_shapefiles.py
```

## Shapefiles
`gis/edit/shapefiles/` (and `gis/edit/casey_fields_blvd_shapefiles.zip`): each shape joined to its table rows **of the
same plan map** (one feature per row); field names cut to 10 characters, full names in `field_names.csv`. They are an
export: edit the GeoPackage, not the shapefiles.

## Re-seeding (rebuilding the GeoPackage from the plan PDFs)
`CFB_RESEED=all python tools/build_croskell_app.py` then `CFB_RESEED=collison python tools/build_collison.py`.
This **overwrites all edits** in the GeoPackage. Only do it on purpose.
