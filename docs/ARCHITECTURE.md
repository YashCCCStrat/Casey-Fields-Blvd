# Architecture

- `sources/pdfs/` → `tools/` scripts → `gis/<plan>/` (GeoTIFFs, GeoPackage, QGIS project).
- Plan maps are placed with an affine fitted to the plan's own precinct-boundary line (VPA PSP boundary): `tools/georef_figure_from_contribution_plans.py` (from Contribution-Plans).
- Attributes come from the plans' printed tables, joined by the printed project ID.
