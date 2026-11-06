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
# ---- each project as the plan draws it: one solid shape per drawn item. Cutting out ID labels, leader lines and the
# crossing / culvert / node symbols left gaps and holes, so pieces of the same project are joined again (closing by
# d metres, square corners) and holes and notches are filled. Only pieces of the same project are joined.
from shapely.ops import nearest_points
def solid(g, d=4, join=80, w=16, node=0):
    """Pieces of one drawn item, joined back into one shape: pieces closer than `join` m (minimum spanning tree) get a
    bridge as wide as the bar (convex hull of both ends within `w` m of the gap); then holes and notches are filled."""
    g = g.buffer(0).buffer(d, join_style='mitre', mitre_limit=3).buffer(-d, join_style='mitre', mitre_limit=3)   # tidy edges first
    parts = [p for p in shapely.get_parts(g) if p.area > 50]
    if not parts: return g
    edges = sorted((parts[i].distance(parts[j]), i, j) for i in range(len(parts)) for j in range(i + 1, len(parts)))
    grp = list(range(len(parts))); find = lambda i: i if grp[i] == i else find(grp[i]); bridges = []
    for dist, i, j in edges:
        if dist > join or find(i) == find(j): continue
        grp[find(i)] = find(j); p, q = nearest_points(parts[i], parts[j])
        bridges.append(shapely.unary_union([parts[i].intersection(p.buffer(w)), parts[j].intersection(q.buffer(w))]).convex_hull)
        if node: bridges.append(shapely.Point((p.x + q.x) / 2, (p.y + q.y) / 2).buffer(node))   # the intersection's node ring
    c = shapely.unary_union(parts + bridges).buffer(0.3, join_style='mitre').buffer(-0.3, join_style='mitre')
    return shapely.unary_union([shapely.Polygon(p.exterior) for p in shapely.get_parts(c) if p.area > 50]).simplify(0.5)
# node rings on Plan 2: orange discs with a white dot at each intersection; added to the intersection's shape
d2 = rasterio.open(G / 'georeferenced/ICO3_plan2.tif'); a2 = np.dstack([d2.read(i) for i in (1, 2, 3)])
l2 = cv2.cvtColor(a2, cv2.COLOR_RGB2LAB).astype(np.float32)
org = (np.sqrt(((l2 - np.median(l2[1833:1841, 175:220].reshape(-1, 3), axis=0)) ** 2).sum(-1)) < 30).astype(np.uint8)
org[:260] = 0; org[1660:, :780] = 0
wht = ((a2.min(-1) > 235) & (cv2.dilate(org, np.ones((5, 5), np.uint8)) > 0)).astype(np.uint8)
filled = org.copy(); cs, _ = cv2.findContours(org, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE); cv2.drawContours(filled, cs, -1, 1, -1)
holes = ((filled > 0) & (org == 0)).astype(np.uint8)
n, cc, st, cen = cv2.connectedComponentsWithStats(holes, 8)
RINGS = [shapely.Point(d2.transform * (cen[i][0] + 0.5, cen[i][1] + 0.5)) for i in range(1, n) if 15 <= st[i, 4] <= 250 and 0.6 < st[i, 2] / st[i, 3] < 1.6]
print(f'{len(RINGS)} intersection node rings found on Plan 2')
def strip_smooth(poly, step=4, win=9):
    """A road strip with bites taken out by printed lettering: cut it into slices across its long axis and give each
    slice the widest extent found within `win` neighbouring slices, so the bites are filled but width and curve stay."""
    import math
    rect = poly.minimum_rotated_rectangle; c = list(rect.exterior.coords)
    e = max([(c[i], c[i + 1]) for i in range(4)], key=lambda s_: math.dist(*s_)); ang = math.atan2(e[1][1] - e[0][1], e[1][0] - e[0][0])
    o = poly.centroid; r = shapely.affinity.rotate(poly, -ang, origin=o, use_radians=True)
    x0, y0, x1, y1 = r.bounds; xs = np.arange(x0, x1 + step, step); lo, hi = [], []
    for a_ in xs:
        sl = r.intersection(shapely.box(a_, y0 - 1, a_ + step, y1 + 1))
        lo.append(sl.bounds[1] if not sl.is_empty else np.nan); hi.append(sl.bounds[3] if not sl.is_empty else np.nan)
    lo, hi = pd.Series(lo).rolling(win, center=True, min_periods=1).min(), pd.Series(hi).rolling(win, center=True, min_periods=1).max()
    ok = lo.notna() & hi.notna(); pts = [(a_, h) for a_, h, k in zip(xs, hi, ok) if k] + [(a_ + step, l) for a_, l, k in zip(xs, lo, ok) if k][::-1]
    pts = [(a_, h) for a_, h, k in zip(xs, hi, ok) if k] + [(xs[ok.values][-1] + step, hi[ok].iloc[-1])] + [(a_, l) for a_, l, k in list(zip(xs, lo, ok))[::-1] if k]
    out = shapely.Polygon(pts).buffer(0)
    return shapely.affinity.rotate(out, ang, origin=o, use_radians=True).intersection(poly.buffer(25))
import shapely.affinity
C2 = C2.copy()
C2['geometry'] = [(solid(g, join=200, node=13) if p.startswith('CK-IN') else solid(g)) if g.geom_type.endswith('Polygon') else g for p, g in zip(C2.project_id, C2.geometry)]
for i, r in C2[C2.project_id.str.startswith('CK-IN') & C2.geom_type.str.contains('Polygon')].iterrows():
    near = [q for q in RINGS if q.distance(r.geometry) < 25]
    if near: C2.at[i, 'geometry'] = solid(shapely.unary_union([r.geometry] + [q.buffer(11) for q in near]), join=60, w=12)   # ring radius ~11 m at 1:15,000
print('rings added:', {p: sum(q.distance(g) < 25 for q in RINGS) for p, g in zip(C2.project_id, C2.geometry) if p.startswith('CK-IN')})
L4 = L4.copy(); pspg = psp.geometry.iloc[0]
road = solid(shapely.unary_union(list(L4[L4.project_id.isin(['CK-RD-01', 'CK-OPPL-RD-01'])].geometry)), d=7)   # 7 m: smooths the bites left by the street-name lettering
L4.loc[L4.project_id == 'CK-RD-01', 'geometry'] = [solid(road.intersection(pspg), 1, 0)]        # inner land: inside the PSP
L4.loc[L4.project_id == 'CK-OPPL-RD-01', 'geometry'] = [strip_smooth(solid(road.difference(pspg), 1, 0)).difference(pspg)]   # outer land: outside it; slices fill the bites of the street-name lettering
other = ~L4.project_id.isin(['CK-RD-01', 'CK-OPPL-RD-01'])
L4.loc[other, 'geometry'] = [solid(g, 9) for g in L4[other].geometry]                           # parks, reserves, intersections
L4['drawn_ha'] = (L4.area / 1e4).round(4)
for nm, g in (('Plan 2', C2), ('Plan 4', L4)):
    print(nm, 'parts per project:', {p: len(shapely.get_parts(x)) for p, x in zip(g.project_id, g.geometry) if x.geom_type.endswith('Polygon')})
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
