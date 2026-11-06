# Croskell (Employment) ICP – GIS v2 (trial, not on the website)

Extracted from the plan's own maps: **Plan 2** Standard and supplementary levy transport construction projects (printed
p. 8) and **Plan 4** Public land provision (printed p. 15) of the Croskell ICP, October 2025. Attributes from Tables 5, 6
(printed pp. 10–12) and Table 8 (pp. 16–17). Coordinate system **GDA2020 / MGA zone 55 (EPSG:7855)**.
Built by `pipeline/croskell_v2_georef.py`, `croskell_v2_extract.py`, `croskell_v2_qa.py` (not part of `run_all.py`).

## Files
| File | What |
|---|---|
| `georeferenced/ICO3_plan2.tif`, `ICO3_plan4.tif` | The two plan pages as GeoTIFFs (1.27 m pixels), placed by fitting the plan's PSP boundary line to the VPA PSP boundary: median 2.4 m, 90th percentile 4.6 m. Checked against OpenStreetMap roads. |
| `croskell_plan4_land_as_drawn_pg.shp` | **Land projects** as drawn on Plan 4: IN-01…05 (land for intersection), LP-01…05 and SR-01/02 (recreation and open space), CK-RD-01 (land for road, inside the PSP) and CK-OPPL-RD-01 (outer public purpose land, hatched, outside the PSP). |
| `croskell_plan4_land_vpa_fus_pg.shp` | The same land items from the VPA Future Urban Structure layer, for comparison (surveyed shapes). |
| `croskell_plan2_construction_as_drawn_{pg,ln,pt}.shp` | **Construction projects** as drawn on Plan 2: IN-01…06 and RD-01 (symbol footprints), SUP-01/03/04 (lines), PED-01/02 and CU-01/02 (points). |
| `croskell_plan2_other_symbols_{ln,pt}.shp` | Also on Plan 2 but not ICP projects: pedestrian crossings, the VDP underground cable. |
| `croskell_gis_v2.gpkg` | All four layers in one GeoPackage (full-length text). `*.csv` attribute tables. |
| `qa_ICO3_plan2.png`, `qa_ICO3_plan4.png` | The layers drawn over the plans (red = extracted, blue = v1 hand-digitised fallback). |

## Fields
`proj_id` (as printed), `map`, `cls` (legend class), `method` (how the shape was made), `sam_iou` (agreement between the
SAM mask and the colour mask), `reg_cat`, `est_2627` (2026-27 cost estimate, register). Table 8: `t8_title`, `t8_ppl_ha`
(public purpose land, ha), `t8_more` (description). Tables 5/6: `t5_/t6_title`, `_staging`, `_app_pct` (apportionment to
this ICP), `_fund`, `_cost` (total), `_cost_ic` (apportioned to ICP), `_cost_ha`, `_more`, `t5_note` (footnote, IN-01).
`drawn_ha` / `drawn_m` (size as drawn), `fus_ha` (VPA FUS area), `drawn_pct` (drawn area as % of Table 8).

## Method
1. **Colour masks** from each plan's own legend colours (CIELAB distance; each pixel goes to its nearest legend colour, so
   the red VDP cable is not mistaken for the maroon road).
2. **ID labels removed**: the white letters inside a same-coloured pill are found and grouped into words; the label box is
   cut out. Leader lines and specks are removed by a small opening.
3. **Land polygons refined with SAM** (Segment Anything ViT-B via `segment-geospatial`): each item's box, six positive
   points on its colour pixels and negative points on nearby labels; SAM's mask is kept within the item's colour area.
   13 of 14 land items use SAM (agreement with the colour mask, IoU 0.65–0.95); SR-01 (thin L-shaped strips) uses the
   colour mask because SAM disagreed (IoU 0.59).
4. **Construction symbols** (thin bars, dots, small symbols) come from the colour masks: bars as footprints, the shared
   user paths as straight lines through each row of dots, signals and culverts as symbol centres. SAM is not used for
   these: it segments areas, not lines.
5. **Naming**: land items by overlap with the VPA FUS asset of the same project; construction items by the nearest known
   location of the same type. Three small symbols were not found automatically and keep their v1 hand-digitised shape
   (`method` says so): CU-02, SUP-03, SUP-04.

## Findings
- **Every Table 8 land item and every Table 5/6 project is on the map** (14 + 14).
- **The plan draws land generously.** Areas as drawn vs Table 8: intersections +8% to +32%, local parks −7% to +13%,
  sports reserves −8% / −14%, outer road land +24%. The plan is a 1:15,000 diagram; for land areas the VPA FUS polygons
  (`_vpa_fus`) match Table 8 to four decimals and are the better source. CK-RD-01 inner land is only 63% as drawn because
  its labels cover part of it.
- **CU-01 moved 146 m.** The previous layer placed it with a road-network rule; Plan 2's culvert symbol shows its position.
- FUS holds CK-RD-01's inner and outer land and more as one 2.44 ha polygon, so its `fus_ha` is not comparable.

## Reproduce
Needs `segment-geospatial`, PyTorch (CPU), scikit-image and the SAM ViT-B checkpoint `sam_vit_b_01ec64.pth`
(dl.fbaipublicfiles.com) in `/root/models`. About 2 minutes on CPU.
