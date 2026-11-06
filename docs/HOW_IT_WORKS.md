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
   - Plan 4 land from VPA FUS (surveyed; matches Table 8) and the development classes (Tables 4, 9, 10).
   - Non-spatial layers: table5–table9_10 and `projects` (every ID, which tables and plan maps it appears in).
4. **App** (`tools/build_croskell_app.py` → `app/croskell/`): 31 rows, one per project and levy component
   (Table 5 standard transport, 6 supplementary transport, 7 community & recreation, 8 inner/outer public purpose land),
   each linked to its features on its plan map by `project_id` + map. Export follows `data/reference/export_schema.xlsx`.
   "Land cost ($)" is left empty: ICP land is provided in kind and equalised per parcel (Table 11), not costed per project.
