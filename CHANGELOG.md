# Changelog

## Latest – import and export clarified
### Changed
- **Import edits** also takes a *Changes for repo* file (restores edits and added shapes, no duplicates on re-import); for Excel files it now says how many rows were not found, and refuses files without the app's *Details* sheet. Its tooltip no longer says it only covers Land acquired / Status (it restores every column).
- Tooltips on **Export to Excel** (all rows of the areas switched on, filters ignored) and **Export shown rows** (only the filtered rows, in table order). `docs/EDITING.md` has a table of the exports and what Import accepts.

## Owner corrections (Collison)
### Fixed
- Five Collison shapes redrawn to the owner's marked-up locations: **CF01** (0.54 ha), **IN04**, **DR10** (now including its western end, 0.70 ha), **DR16** (along the printed pipe dots south of the old line and up the west side of DR09, 317 m) and **DR17** (onto the printed dots east of the old line, from DR14 to channel DR07, 51 m). Kept in `data/reference/collison/owner_revisions.geojson` so a re-seed keeps them.

## Editing, QGIS round trip, drawing
### Added
- **Edit every column** in the table (Edit table switch); Excel export and Import edits carry all columns.
- **Draw to add a feature** (point, line or polygon) on the map: a form fills in the new project row (plan area, plan map, legend class, ID, title, costs, status …); kept in the browser, deletable from the project card. New legend class *Added feature* per plan map.
- **Filter by drawing** an area, or a line with a buffer (default ± 50 m): the table keeps only projects touching it.
- **Changes for repo**: downloads your edits and added features as GeoJSON for `gis/edit/inbox/`; the GitHub Action applies them to the GeoPackage and rebuilds the app.
- **GIS export** (GeoJSON, one feature per table row, with edits).
- **Editable GeoPackage** `gis/edit/casey_fields_blvd.gpkg` as the source of truth, with a ready **QGIS project** `gis/edit/casey_fields_blvd.qgz` (styled as the app, joined to the tables, printed plans underneath) and **shapefiles** with their table attributes (`gis/edit/shapefiles/`, zip). Shapes drawn in QGIS with a new project ID get a table row automatically. See `docs/EDITING.md`.

## 2026-11-15 (later still)
### Fixed (owner feedback, Collison)
- ID label pills (RD05, DR01 …) are no longer part of the road and drainage shapes: labels are found by their white lettering and removed, and each bar is rebuilt as straight segments fitted to the printed colour at its printed width (RD02, RD05 straight; drainage channel areas now within ~10% of T6).
- Pipes fitted to the printed blue dashes (DR16 moved onto them; lengths within 4% of T6 except DR15).
- IN02 and IN03 drawn as the plan's intersection symbol (cross with ring).
### Changed
- Moving the Transparency slider shows the printed plan if none is shown yet (the first ticked plan of each area, e.g. Collison Figure 3).
- The printed-plan slider is now **Transparency** (0% = solid, default 35%); it was opacity, so 0% hid the plan. "Show printed plan" buttons made more visible.
- Each plan's tick box now switches the whole plan on or off: all its legend items leave the map (and its rows leave the table); its legend items are greyed out until it is ticked again. Individual items can still be toggled while the plan is on. The printed plan has its own "Show printed plan" button.
- Area counts in the header are table rows (Croskell 31, Collison 30), not distinct project IDs.

## 2026-11-15 (later)
### Changed
- **One page for all plan areas** (`app/index.html`): Croskell and Collison on the same map and table. Area switches in the header (both on by default) filter map, legend, table, totals and export; any number of plan maps can be shown as printed at once (tick them in the panel, or "Show plan map" on a project's card); "All plan maps" filter in the toolbar; a "Plan area" column. Edits from the earlier per-plan pages carry over.
- Croskell plan maps named in full: Plan 2 · Standard and Supplementary Levy Transport Construction Projects; Plan 3 · Standard Levy Community and Recreation Construction Projects; Plan 4 · Public Land Provision.

## 2026-11-15
### Added
- **Collison Estate DCP** (`gis/collison/`, `app/collison/`): Figure 3 placed on the ground (median 1.8 m), all 28 mapped projects as one shape each – roads and drainage channels in the plan's colours (split at junctions by nearest traced centre line), intersections IN01–IN04 as road footprints, pipes DR11–DR17 as lines, community facility CF01 – joined to Tables 5–8 and T11 (land, construction, total, apportionment, cost to MCA, levy; totals match the printed $73,015,850 / $64,792,268 / $945,578). `tools/collison_tables.py`, `tools/build_collison.py`.
### Changed
- **New app layout, shared by all plans** (`app/common/viewer.js`, `viewer.css`; `app/index.html` lists the plans): map on top, table below in a resizable panel; plan-map tabs; floating detail card; legend items are click-to-hide toggles; category chips, project-ID search, "in map view", and a column chooser decide what is shown; modern styling with light/dark support.

## 2026-11-14
### Fixed (owner feedback)
- **Intersection construction projects (Plan 2 IN-01…06) drawn as intersection footprints**: the carriageways of the two roads named in Table 5 (OpenStreetMap centrelines, widened per carriageway), limited to the extent of the plan's bar, plus the junction and rounded corners; future legs not yet in OSM keep the plan's bar. Search box now matches project ID only.
- **Each project is one solid shape as drawn.** Cutting out ID labels, leader lines and symbols had split items and left holes. Pieces of the same project are now joined with a bar-wide bridge, holes and notches filled, and Plan 2 intersections include their node ring (found on the plan). Result: Plan 2 IN-01…06 and RD-01 one polygon each; Plan 4 RD-01 two (north and south pieces), OPPL-RD-01 one (smoothed where the street name bit into it), LP-03 a closed square.
- Symbols as in the plans' legends: culvert drawn as the plan's culvert symbol along its road/path, pedestrian signals as the olive square, pedestrian crossings as an orange X with white outline; legend redrawn per plan. Maki sports icon removed.
- Only the two pedestrian crossings printed on Plan 2 (on RD-01) are kept; two false detections at IN-02 and IN-05 removed. Crossings, VDP cable and Plan 2 items no longer show with Plan 3 or Plan 4: choosing a plan map shows that plan's layers and labels only.
- Plan 3 projects (SR-01, SR-02) now highlight on hover and selection (outline layer added).
### Added
- **Croskell plan maps on the ground:** Plans 2, 3 and 4 as GeoTIFFs (median 2.4 m from the VPA PSP boundary).
- **Croskell GeoPackage** (`gis/croskell/croskell.gpkg`): transport construction (Plan 2), community & recreation (Plan 3), public land as drawn and from VPA FUS (Plan 4), development classes, and Tables 5–10 as linked tables.
- **Croskell app** (`app/croskell/index.html`): plan maps as overlays, hover and click linked between map and table, filters applied to both, editable Land acquired / Status, Excel export in the project-register schema and re-import.

## 2026-11-13
### Added
- Repository started. Starter material from Contribution-Plans (`ad2cb2b`): corridor plan documents, draft corridor line and buffers, VPA precincts and DCPO/ICO overlays (Casey only), the 37 corridor projects, the Croskell GIS v2 trial layers, CC0 map icons.
