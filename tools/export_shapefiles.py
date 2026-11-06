"""Shapefiles from gis/edit/casey_fields_blvd.gpkg: each shape joined to its projects-table row(s) (one feature per row),
in gis/edit/shapefiles/ plus a zip. Shapefile field names are cut to 10 characters: field_names.csv lists the full names.
For editing, use the GeoPackage (shapefiles are an export only)."""
import pathlib, zipfile, shutil, warnings
warnings.filterwarnings('ignore')
import pandas as pd, geopandas as gpd, pyogrio
ROOT = pathlib.Path(__file__).resolve().parents[1]; GPKG = ROOT / 'gis/edit/casey_fields_blvd.gpkg'; OUT = ROOT / 'gis/edit/shapefiles'
if OUT.exists(): shutil.rmtree(OUT)
OUT.mkdir(parents=True)
names = []
layers = [l for l, _ in pyogrio.list_layers(GPKG)]
for l in [l for l in layers if not l.endswith('_projects')]:
    a = l.split('_')[0]; g = gpd.read_file(GPKG, layer=l)
    if g.empty: continue                                       # empty layers are there for drawing in QGIS only
    t = pyogrio.read_dataframe(GPKG, layer=f'{a}_projects', read_geometry=False)
    j = g.merge(t.drop(columns=['title', 'category'], errors='ignore'), on=['project_id', 'map'], how='left')   # rows of this plan map only
    ren = {}
    for c in j.columns:
        if c == 'geometry': continue
        short = c[:10]; k = 1
        while short in ren.values(): short = c[:8] + f'_{k}'; k += 1
        ren[c] = short; names.append(dict(layer=l, shapefile_field=short, field=c))
    j.rename(columns=ren).to_file(OUT / f'{l}.shp', encoding='utf-8')
pd.DataFrame(names).drop_duplicates().to_csv(OUT / 'field_names.csv', index=False, encoding='utf-8-sig')
for l in [l for l in layers if l.endswith('_projects')]:
    pyogrio.read_dataframe(GPKG, layer=l, read_geometry=False).to_csv(OUT / f'{l}.csv', index=False, encoding='utf-8-sig')
with zipfile.ZipFile(ROOT / 'gis/edit/casey_fields_blvd_shapefiles.zip', 'w', zipfile.ZIP_DEFLATED) as z:
    for p in sorted(OUT.iterdir()):   # fixed timestamps: an unchanged export gives an identical zip (no empty rebuild commits)
        zi = zipfile.ZipInfo(p.name, (2020, 1, 1, 0, 0, 0)); zi.compress_type = zipfile.ZIP_DEFLATED; z.writestr(zi, p.read_bytes())
print(len([p for p in OUT.glob('*.shp')]), 'shapefiles written')
