# Changelog

## 2026-11-14
### Fixed (owner feedback)
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
