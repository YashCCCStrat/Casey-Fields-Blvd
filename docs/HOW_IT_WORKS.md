# How it works

## Croskell (Employment) ICP
1. **Plan maps on the ground** (`tools/georef.py`). Plans 2, 3 and 4 are the 300 ppi images embedded in the ICP PDF
   (printed pp. 8, 13, 15). The plan's navy dashed PSP boundary is picked out by colour and fitted to the VPA PSP 1051
   boundary (affine, iterative closest point). Fit: median 2.4 m, 90th percentile 4.5 m, for all three. Output:
   `gis/croskell/georeferenced/ICO3_plan{2,3,4}.tif` (EPSG:7855, 1.27 m pixels).
2. **Tables** (`data/reference/croskell/`): Tables 5–8 (and 9/10) as CSV, one row per project; every money, % and
   hectare value is checked against the PDF text. Tables 5 + 6 + 7 "apportioned to ICP" reproduce the printed totals
   ($29,785,696 + $9,215,122 + $3,442,877).
3. **Shapes** (`tools/build_croskell_gpkg.py` → `gis/croskell/croskell.gpkg`):
   - Plan 2 transport construction and Plan 4 land as drawn: from the Contribution-Plans Croskell v2 extraction
     (colour masks from the plan legends, labels removed, land polygons refined with Segment Anything), copied with its
     script in `tools/from_contribution_plans/`.
   - Plan 3 sports reserves: the legend colour on Plan 3; the plan draws SR-01 and SR-02 as one joined shape, split
     along the VPA FUS reserve extents (3.37 / 8.42 ha drawn vs 3.58 / 8.86 ha FUS).
   - **One shape per drawn item** (`solid()` in the build script): pieces of the same project closer than 80 m are joined by a bridge as wide as the bar (minimum spanning tree), holes and notches are filled; Plan 2 intersections take in their node ring (orange disc with white dot, detected on the plan); the outer road land is rebuilt slice by slice (4 m) to fill bites left by the printed street name.
   - **Intersection footprints** (Plan 2 IN-01…06): Plan 2 draws each intersection as a thin bar along the legs it funds. The footprint is the carriageway of the two roads named in Table 5 (`gis/corridor/osm_roads_croskell.gpkg`, OpenStreetMap via Overture, ODbL; 9 m half-width per arterial carriageway, 7 m tertiary) within 22 m of the bar, plus a 20 m junction disc at the plan's node ring, closed by 12 m for rounded corners. Legs not yet built (industrial connectors at IN-01, IN-04, IN-05) keep the plan's bar. Indicative extent, not a design.
   - Plan 4 land from VPA FUS (surveyed; matches Table 8) and the development classes (Tables 4, 9, 10).
   - Non-spatial layers: table5–table9_10 and `projects` (every ID, which tables and plan maps it appears in).
4. **App** (`tools/build_croskell_app.py` → `app/croskell/`): 31 rows, one per project and levy component
   (Table 5 standard transport, 6 supplementary transport, 7 community & recreation, 8 inner/outer public purpose land),
   each linked to its features on its plan map by `project_id` + map. Export follows `data/reference/export_schema.xlsx`.
   "Land cost ($)" is left empty: ICP land is provided in kind and equalised per parcel (Table 11), not costed per project.

## Collison Estate DCP (V4.1, Feb 2025)
1. Figure 3 (printed p. 12, embedded image) placed by its periwinkle precinct line on the DCPO22 overlay boundary: median 1.8 m.
2. Tables 5–8 and T11 read from the PDF text (`data/reference/collison/projects_t5_t8_t11.csv`); T11 subtotals and total checked.
3. Shapes (revised 2026-11-15): label pills are removed first (white lettering inside the bar colour); each road and drainage bar is the traced centre line refitted to the printed pixels (position, and angle on segments over ~90 px) and buffered by its printed half-width; pipes are refitted the same way to the blue dashes; IN02/IN03 are the plan's intersection symbol. Before that: roads (maroon) and drainage channels (dark green) were the plan's colours, each pixel assigned to the nearest
   traced centre line of its class (so RD02/RD03/RD05/RD06 split at Heather Grove / Collison Rd), then one solid shape
   each; intersections are the carriageways of the two named roads (OSM) within the symbol, plus the junction; pipes
   are traced lines (lengths within 2% of T6 except DR15 74 m vs 99 m); CF01 is the community-facility fill by its star.
   Drawn areas are 1–2× the land in T5/T6 because the plan draws bars wider than the land strip.
