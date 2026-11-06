"""Build gis/croskell/croskell.gpkg: Croskell (Employment) ICP projects, land and tables, linked by project_id.

Shapes
- Plan 2 (transport construction) and Plan 4 (public land, as drawn): from the Contribution-Plans "Croskell GIS v2"
  extraction (tools/from_contribution_plans/croskell_v2_extract.py; colour masks + Segment Anything), copied in
  gis/croskell/v2_from_contribution_plans/.
- Plan 3 (community & recreation construction, SR-01/02): extracted here from ICO3_plan3.tif by the plan's legend colour.
- Plan 4 land from the VPA Future Urban Structure layer (surveyed; matches Table 8) and the development classes
  (Tables 4, 9, 10) from gis/croskell/v2_from_contribution_plans/.
Tables: data/reference/croskell/table5..table9_10.csv (checked against the PDF text).
Every map layer carries project_id plus the fields of its table(s), so each layer can be filtered on its own."""
import pathlib, warnings
warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, geopandas as gpd, shapely, cv2, rasterio, rasterio.features
from shapely.geometry import shape

ROOT = pathlib.Path(__file__).resolve().parents[1]
G, REF = ROOT / 'gis/croskell', ROOT / 'data/reference/croskell'
V2 = G / 'v2_from_contribution_plans/croskell_gis_v2.gpkg'
OUT = G / 'croskell.gpkg'
T = {k: pd.read_csv(REF / f'{k}.csv') for k in ('table5', 'table6', 'table7', 'table8', 'table9_10')}
pr = gpd.read_file(ROOT / 'gis/corridor/vpa_precincts_casey.gpkg'); psp = pr[pr.VPA_No == '1051']

# ---- Plan 3: sports reserves as drawn (legend colour, labels cut out, specks removed)
d = rasterio.open(G / 'georeferenced/ICO3_plan3.tif'); a = np.dstack([d.read(i) for i in (1, 2, 3)])
lab = cv2.cvtColor(a, cv2.COLOR_RGB2LAB).astype(np.float32)
ref = np.median(lab[2184:2207, 166:239].reshape(-1, 3), axis=0)                    # 'local sports reserve (SR)' swatch
m = np.sqrt(((lab - ref) ** 2).sum(-1)) < 26
m[:260, :] = False; m[2060:, :920] = False; m[2300:, :] = False
m = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE); cv2.drawContours(m, cs, -1, 1, -1)   # fill the white label text
m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((7, 7), np.uint8)).astype(bool)
polys = [shape(g) for g, v in rasterio.features.shapes(m.astype(np.uint8), mask=m, transform=d.transform) if v == 1]
polys = [p.buffer(0).simplify(0.6) for p in polys if p.area > 5000]
fus_sr = gpd.read_file(V2, layer='croskell_plan4_land_vpa_fus')
# Plan 3 draws SR-01 and SR-02 as one joined green shape: split it along the VPA FUS reserve extents
# (local sports reserve + existing open space with the same asset ID); any remainder goes to the nearer reserve.
FUS = gpd.read_file(G / 'vpa_fus_croskell.gpkg')
ext = FUS[FUS.ASSET_ID.isin(['CK-SR-01', 'CK-SR-02'])].dissolve('ASSET_ID').reset_index()
whole = shapely.unary_union(polys); sr = []
for r in ext.itertuples(): sr.append(dict(project_id=r.ASSET_ID, geometry=whole.intersection(r.geometry.buffer(12))))
rest = whole.difference(shapely.unary_union([s_['geometry'] for s_ in sr]))
for part in shapely.get_parts(rest):
    if part.area < 200: continue
    i = int(np.argmin([part.distance(r.geometry) for r in ext.itertuples()])); sr[i]['geometry'] = sr[i]['geometry'].union(part)
P3 = gpd.GeoDataFrame(sr, geometry='geometry', crs=7855)
P3 = P3.merge(T['table7'], on='project_id', how='left'); P3['drawn_ha'] = (P3.area / 1e4).round(3)
P3.insert(1, 'map', 'Plan 3 · Standard levy community & recreation construction projects (printed p. 13)')
P3['shape_source'] = 'Plan 3 as drawn (legend colour, labels filled)'
print('Plan 3:', P3[['project_id', 'drawn_ha', 'total_cost_aud']].to_string(index=False))

# ---- Plan 2 and Plan 4 layers, re-joined to the clean tables
def attach(gdf, tables, id_col='proj_id'):
    g = gdf.rename(columns={id_col: 'project_id'})[['project_id', 'geometry'] + [c for c in ('cls', 'method', 'drawn_ha', 'drawn_m', 'fus_ha', 'drawn_pct') if c in gdf]]
    for k in tables:
        t = T[k].drop(columns=['source']).add_prefix(f'{k.replace("table", "t")}_').rename(columns={f'{k.replace("table", "t")}_project_id': 'project_id'})
        g = g.merge(t, on='project_id', how='left')
    return g
C2 = attach(gpd.read_file(V2, layer='croskell_plan2_construction_as_drawn'), ['table5', 'table6'])
C2['standard_levy'] = C2.project_id.isin(T['table5'].project_id); C2['supplementary_levy'] = C2.project_id.isin(T['table6'].project_id)
C2['type'] = C2.project_id.str.extract(r'CK-([A-Z]+)-')[0].map({'IN': 'Intersection', 'RD': 'Road', 'SUP': 'Shared user path', 'CU': 'Culvert', 'PED': 'Pedestrian signals'})
C2.insert(1, 'map', 'Plan 2 · Standard and supplementary levy transport construction projects (printed p. 8)')
O2 = gpd.read_file(V2, layer='croskell_plan2_other_symbols')
# Plan 2 prints two pedestrian crossings, both on RD-01 (Casey Fields Blvd) where SUP-01 crosses it; the other two
# detections were intersection node markers (IN-02, IN-05), so keep only crossings within 40 m of RD-01
_rd = gpd.read_file(V2, layer='croskell_plan2_construction_as_drawn'); _rd = _rd[_rd.proj_id == 'CK-RD-01'].geometry.iloc[0]
O2 = O2[(O2.cls != 'pedestrian crossing') | (O2.distance(_rd) < 40)]
assert (O2.cls == 'pedestrian crossing').sum() == 2, O2.cls.value_counts()
L4 = attach(gpd.read_file(V2, layer='croskell_plan4_land_as_drawn'), ['table8'])
F4 = attach(gpd.read_file(V2, layer='croskell_plan4_land_vpa_fus'), ['table8'])
for g in (L4, F4):
    g['land_type'] = g.project_id.map(lambda p: 'Outer public purpose land (road)' if 'OPPL' in p else 'Land for road' if '-RD-' in p else 'Land for intersection' if '-IN-' in p else 'Land for recreation and open space')
    g.insert(1, 'map', 'Plan 4 · Public land provision (printed p. 15)')
L4['shape_source'] = 'Plan 4 as drawn'; F4['shape_source'] = 'VPA Future Urban Structure (surveyed)'
DC = gpd.read_file(G / 'v2_from_contribution_plans/croskell_development_classes.gpkg')

# ---- one projects table (every ID in Tables 5-8) for filtering and relations
ids = sorted(set().union(*[set(T[k].project_id) for k in ('table5', 'table6', 'table7', 'table8')]))
PJ = pd.DataFrame(dict(project_id=ids))
PJ['in_table5'] = PJ.project_id.isin(T['table5'].project_id); PJ['in_table6'] = PJ.project_id.isin(T['table6'].project_id)
PJ['in_table7'] = PJ.project_id.isin(T['table7'].project_id); PJ['in_table8'] = PJ.project_id.isin(T['table8'].project_id)
PJ['title'] = PJ.project_id.map(pd.concat([T[k].set_index('project_id').title for k in ('table8', 'table7', 'table6', 'table5')]).groupby(level=0).last())
PJ['construction_cost_aud'] = PJ.project_id.map(pd.concat([T['table5'].set_index('project_id').total_cost_aud, T['table7'].set_index('project_id').total_cost_aud]).groupby(level=0).first())
PJ['cost_to_icp_aud'] = PJ.project_id.map(pd.concat([T['table5'].set_index('project_id').cost_to_icp_aud, T['table6'].set_index('project_id').cost_to_icp_aud, T['table7'].set_index('project_id').cost_to_icp_aud]).groupby(level=0).sum())
PJ['public_purpose_land_ha'] = PJ.project_id.map(T['table8'].set_index('project_id').public_purpose_land_ha)
PJ['on_plan2'] = PJ.project_id.isin(C2.project_id); PJ['on_plan3'] = PJ.project_id.isin(P3.project_id); PJ['on_plan4'] = PJ.project_id.isin(L4.project_id)
assert abs(PJ.cost_to_icp_aud.sum() - (29785696 + 9215122 + 3442877)) <= 2, PJ.cost_to_icp_aud.sum()   # Tables 5 + 6 + 7 totals as printed (rounding)

if OUT.exists(): OUT.unlink()
layers = {'psp_boundary': psp[['VPA_No', 'PSP_NAME', 'geometry']],
          'plan2_construction_areas': C2[C2.geom_type.str.contains('Polygon')], 'plan2_construction_lines': C2[C2.geom_type.str.contains('Line')],
          'plan2_construction_points': C2[C2.geom_type.str.contains('Point')], 'plan2_other_symbols_points': O2[O2.geom_type.str.contains('Point')],
          'plan2_other_symbols_lines': O2[O2.geom_type.str.contains('Line')], 'plan3_community_recreation': P3,
          'plan4_land_as_drawn': L4, 'plan4_land_vpa_fus': F4, 'plan4_development_classes': DC}
for k, g in layers.items():
    g = gpd.GeoDataFrame(g, geometry='geometry', crs=7855)
    if g.geom_type.str.startswith('Multi').any(): g['geometry'] = g.geometry.apply(lambda x: x if x.geom_type.startswith('Multi') else {'Point': shapely.MultiPoint, 'LineString': shapely.MultiLineString, 'Polygon': shapely.MultiPolygon}[x.geom_type]([x]))
    g.to_file(OUT, layer=k); print(f'{k}: {len(g)}')
import sqlite3
con = sqlite3.connect(OUT)
for k, t in list(T.items()) + [('projects', PJ)]:
    t.to_sql(k, con, index=False)
    con.execute("INSERT OR REPLACE INTO gpkg_contents (table_name, data_type, identifier) VALUES (?, 'attributes', ?)", (k, k))
con.commit(); con.close()
print('tables:', ', '.join(list(T) + ['projects']))
