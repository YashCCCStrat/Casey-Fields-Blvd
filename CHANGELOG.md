# Changelog

## 2026-11-15 (latest)
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
