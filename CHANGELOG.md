# Changelog

## 2026-11-14
### Fixed (owner feedback)
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
