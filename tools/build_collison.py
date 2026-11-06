"""Collison Estate DCP (V4.1, Feb 2025): Figure 3 'Infrastructure map – DCP items' (printed p. 12) -> GIS + app data.

Inputs : gis/collison/georeferenced/DCPO22_fig3.tif (tools/georef.py; median 1.8 m from the DCPO22 overlay boundary)
         data/reference/collison/projects_t5_t8_t11.csv (tools/collison_tables.py; T11 totals checked)
         data/reference/collison/fig3_seed_lines_v1.json (hand-traced centre lines from Contribution-Plans, same image)
         gis/corridor/osm_roads_collison.gpkg (OpenStreetMap via Overture, ODbL)
Method : roads (maroon) and drainage channels (dark green) are the plan's own colour, each pixel given to the nearest
         seed line of its class (so joined bars split at junctions), then one solid shape per project; intersections
         (orange symbols) are footprints of the two named roads' carriageways within the symbol's extent plus the
         junction; pipes (dashed blue) are the traced centre lines; CF01 is the community-facility fill by its star.
Outputs: gis/collison/collison.gpkg, app/collison/data.js"""
import pathlib, json, sys, warnings
warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, geopandas as gpd, shapely, cv2, rasterio, rasterio.features
from shapely.geometry import shape
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from appdata import solid, image_entry, write_app

ROOT = pathlib.Path(__file__).resolve().parents[1]
G = ROOT / 'gis/collison'; REF = ROOT / 'data/reference/collison'
T = pd.read_csv(REF / 'projects_t5_t8_t11.csv')
d = rasterio.open(G / 'georeferenced/DCPO22_fig3.tif'); a = np.dstack([d.read(i) for i in (1, 2, 3)]); H, W = a.shape[:2]
lab = cv2.cvtColor(a, cv2.COLOR_RGB2LAB).astype(np.float32)
px2xy = lambda x, y: d.transform * (x + 0.5, y + 0.5)
def cmask(rgb, tol):
    ref = cv2.cvtColor(np.uint8([[rgb]]), cv2.COLOR_RGB2LAB).astype(np.float32)[0, 0]
    return np.sqrt(((lab - ref) ** 2).sum(-1)) < tol

seeds = json.loads((REF / 'fig3_seed_lines_v1.json').read_text())['items']
seeds['RD02'] = {'kind': 'Road', 'px': [[545, 1097], [880, 1112]]}           # Heather Grove east of RD03 (not traced in v1)
seeds['IN01'] = {'kind': 'Intersection', 'px': [[500, 160]]}; seeds['IN02'] = {'kind': 'Intersection', 'px': [[488, 410]]}; seeds['IN03'] = {'kind': 'Intersection', 'px': [[352, 1455]]}
seeds['RD03'] = {'kind': 'Road', 'px': [[415, 1080], [540, 1095]]}
seedline = {k: shapely.LineString(v['px']) if len(v['px']) > 1 else shapely.Point(v['px'][0]) for k, v in seeds.items()}

def split_by_seed(mask, ids, maxd=40):
    ys, xs = np.nonzero(mask); pts = shapely.points(np.c_[xs, ys])
    D = np.stack([shapely.distance(pts, seedline[i]) for i in ids]); k = D.argmin(0); ok = D.min(0) < maxd
    out = {}
    for j, pid in enumerate(ids):
        m = np.zeros(mask.shape, np.uint8); sel = ok & (k == j); m[ys[sel], xs[sel]] = 1
        out[pid] = m
    return out

def polys(m):
    gs = [shape(g) for g, v in rasterio.features.shapes(m, mask=m.astype(bool), transform=d.transform) if v == 1]
    return shapely.unary_union(gs).buffer(0)

valid = np.zeros((H, W), bool); valid[60:1880, 380:1010] = True                 # map area, clear of both legends
def label_pills(m, grow=3):
    """ID labels printed on the bars ('RD05', 'DR01'): rounded pills of the bar colour with white lettering. Found by
    their letter holes (3+ small white holes in a row); returns a mask of the pills (bounding box of the letters + margin)."""
    g = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    filled = g.copy(); cs, _ = cv2.findContours(g, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE); cv2.drawContours(filled, cs, -1, 1, -1)
    holes = ((filled > 0) & (g == 0)).astype(np.uint8)
    n, cc, st, cen = cv2.connectedComponentsWithStats(holes, 8)
    let = [i for i in range(1, n) if 4 <= st[i, 4] <= 250 and st[i, 2] <= 18 and st[i, 3] <= 18]
    out = np.zeros_like(g); used = set()
    for i in let:
        if i in used: continue
        grp = [j for j in let if np.hypot(*(cen[j] - cen[i])) < 30]
        if len(grp) < 3: continue
        used |= set(grp)
        x0 = min(st[j, 0] for j in grp); y0 = min(st[j, 1] for j in grp); x1 = max(st[j, 0] + st[j, 2] for j in grp); y1 = max(st[j, 1] + st[j, 3] for j in grp)
        # the pill around the letters: the bar-coloured component that encloses them
        k = cc[int(cen[i][1]), int(cen[i][0])]
        box = np.zeros_like(g); box[max(0, y0 - 12):y1 + 12, max(0, x0 - 12):x1 + 12] = 1
        out |= box & cv2.dilate(filled, np.ones((3, 3), np.uint8))
    return cv2.dilate(out, np.ones((2 * grow + 1, 2 * grow + 1), np.uint8)).astype(bool)
def fit_polyline(P, ys, xs, corridor, extend=True):
    """Hand-traced vertices P (pixels) refitted to the printed pixels: each segment shifted onto the median of the pixels
    in its corridor; corners where consecutive fitted lines cross (midpoint if nearly parallel); the ends extended or
    trimmed to where the pixels stop. Returns the vertices and the bar's half width (pixels)."""
    pts_ = np.c_[xs, ys].astype(float); L = []; hws = []
    for k in range(len(P) - 1):
        p, q = np.array(P[k], float), np.array(P[k + 1], float); dv = (q - p) / np.linalg.norm(q - p); nv = np.array([-dv[1], dv[0]])
        t = (pts_ - p) @ dv; off = (pts_ - p) @ nv; ln = np.linalg.norm(q - p)
        sel = (t > -25) & (t < ln + 25) & (np.abs(off) < corridor)
        if sel.sum() < 15: L.append((p, dv, t, sel)); continue
        for _ in range(2):                                              # fit position and angle (PCA), then reselect around it
            c = pts_[sel]; mu = np.median(c, axis=0); _, _, vt = np.linalg.svd(c - c.mean(0)); dn = vt[0] * np.sign(vt[0] @ dv)
            if dn @ dv > 0.985 and ln > 90: dv, p = dn, mu - ((mu - p) @ dn) * dn   # long segments: accept the fitted angle if within ~10 degrees of the trace
            else: p = p + np.median((c - p) @ nv) * nv
            nv = np.array([-dv[1], dv[0]]); t = (pts_ - p) @ dv; off = (pts_ - p) @ nv
            sel = (t > -25) & (t < ln + 25) & (np.abs(off) < corridor)
        o = np.median(off[sel]); hws.append(np.percentile(np.abs(off[sel] - o), 92)); L.append((p + o * nv, dv, t, sel))
    out = []
    a0, d0, t0, s0 = L[0]; out.append(a0 + (t0[s0].min() if s0.any() and extend else (np.array(P[0], float) - a0) @ d0) * d0)
    for k in range(len(L) - 1):
        a1, d1 = L[k][:2]; a2, d2 = L[k + 1][:2]
        if abs(d1 @ d2) > 0.97: out.append((a1 + ((a2 - a1) @ d1) * d1 + a2) / 2)          # nearly parallel: no crossing
        else: tt = np.linalg.solve(np.c_[d1, -d2], a2 - a1); out.append(a1 + tt[0] * d1)
    a1, d1, t1, s1 = L[-1]; ln = np.linalg.norm(np.array(P[-1], float) - np.array(P[-2], float)) if len(P) > 1 else 0
    out.append(a1 + (t1[s1].max() if s1.any() and extend else (np.array(P[-1], float) - a1) @ d1) * d1)
    return out, (np.median(hws) if hws else 4.0)

feats = []
# roads and drainage channels
for ids, rgb, tol, cls in ((['RD01', 'RD02', 'RD03', 'RD04', 'RD05', 'RD06'], (154, 45, 90), 32, 'road'),
                           ([f'DR{i:02d}' for i in range(1, 11)], (22, 81, 47), 30, 'drain')):
    mm = cmask(rgb, tol) & valid; pills = label_pills(mm); mm &= ~pills
    print(f'{cls}: {pills.sum()} label-pill pixels removed')
    for pid, m in split_by_seed(mm, ids).items():
        ys_, xs_ = np.nonzero(cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)))
        pts, hw = fit_polyline(seeds[pid]['px'], ys_, xs_, 14 if cls == 'road' else 18)
        line = shapely.LineString([px2xy(*p) for p in pts]); hw_m = (hw + 0.5) * abs(d.transform.a)
        feats.append(dict(project_id=pid, cls=cls, geometry=line.buffer(hw_m, cap_style='flat', join_style='mitre', mitre_limit=3),
                          method=f'Figure 3 bar: centre line fitted to the printed {cls} colour (labels removed), drawn at its printed width ({2 * hw_m:.0f} m)'))
# pipes: each traced segment re-fitted to the blue dashes printed along it (robust line fit), corners at the fitted lines' crossings
bl = a.astype(int); blue = (bl[..., 2] > 140) & (bl[..., 0] < 90) & (bl[..., 1] < 90) & valid; blue &= ~label_pills(blue)
bys, bxs = np.nonzero(blue)
for i in range(11, 18):
    pid = f'DR{i}'; pts, _ = fit_polyline(seeds[pid]['px'], bys, bxs, 16, extend=False)
    feats.append(dict(project_id=pid, cls='pipe', geometry=shapely.LineString([px2xy(*p) for p in pts]), method='traced on Figure 3, each segment fitted to the printed blue dashes'))
# community facility: fill colour by the star
cf = cmask((254, 223, 135), 18) & valid; sx, sy = seeds['CF01']['px'][0]
n, cc, st, _ = cv2.connectedComponentsWithStats(cf.astype(np.uint8), 8)
near = [i for i in range(1, n) if st[i, 4] > 200 and abs(st[i, 0] + st[i, 2] / 2 - sx) < 90 and abs(st[i, 1] + st[i, 3] / 2 - sy) < 90]
cfm = np.isin(cc, near).astype(np.uint8) | (cv2.circle(np.zeros((H, W), np.uint8), (sx, sy), 22, 1, -1) & cmask((226, 221, 35), 40).astype(np.uint8))
cfm = cv2.morphologyEx(cfm, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
feats.append(dict(project_id='CF01', cls='cf', geometry=solid(polys(cfm), d=3), method='community facility fill and star on Figure 3'))
# intersections: road footprints
OSM = gpd.read_file(ROOT / 'gis/corridor/osm_roads_collison.gpkg')
HW = {'trunk': 9, 'primary': 9, 'secondary': 9, 'tertiary': 7, 'residential': 6, 'unclassified': 6}
IN = {'IN01': ('Linsell Boulevard', 'Casey Fields Boulevard'), 'IN02': ('Casey Fields Boulevard', 'Sargent Street'),
      'IN03': ('Casey Fields Boulevard', 'Beagle Street'), 'IN04': ('Berwick - Cranbourne Road', 'Collison Road')}
org = (cmask((247, 148, 30), 34)).astype(np.uint8); org[:, 1000:] = 0
SYMBOL = {'IN02', 'IN03'}   # owner, 2026-11-15: these two as the plan's intersection symbol (cross with ring)
for pid, (r1, r2) in IN.items():
    sx, sy = seeds[pid]['px'][0]
    n, cc, st, cen = cv2.connectedComponentsWithStats(org, 8)
    comp = [i for i in range(1, n) if st[i, 4] > 150 and np.hypot(cen[i][0] - sx, cen[i][1] - sy) < 60]
    sym = polys(np.isin(cc, comp).astype(np.uint8)) if comp else shapely.Point(px2xy(sx, sy)).buffer(30)
    if pid in SYMBOL:
        lb = label_pills(org.astype(bool))                      # drop the 'IN02' label pill next to the symbol
        symm = (np.isin(cc, comp) & ~lb).astype(np.uint8)
        symm = cv2.morphologyEx(symm, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
        g = solid(polys(symm), d=2, join=20, w=6)
        feats.append(dict(project_id=pid, cls='int', geometry=max(shapely.get_parts(g), key=lambda p: p.area), method='Figure 3 intersection symbol (cross with ring) as drawn'))
        continue
    reach = sym.envelope.buffer(10); node = shapely.Point(px2xy(sx, sy))
    parts = [node.buffer(18)]
    for nm in (r1, r2):
        for g, k in zip(OSM[(OSM.name == nm) & OSM.intersects(reach)].geometry, OSM[(OSM.name == nm) & OSM.intersects(reach)]['class']):
            parts.append(g.intersection(reach).buffer(HW.get(k, 6), cap_style='flat'))
    fp = shapely.unary_union(parts).buffer(10).buffer(-10)
    fp = max(shapely.get_parts(fp), key=lambda p: p.area if p.intersects(node.buffer(20)) else 0)
    feats.append(dict(project_id=pid, cls='int', geometry=shapely.Polygon(fp.exterior).simplify(0.8), method='road footprint: OSM carriageways of the two named roads within the Figure 3 symbol, plus the junction'))
F = gpd.GeoDataFrame(feats, geometry='geometry', crs=7855)
F['parts'] = [len(shapely.get_parts(g)) for g in F.geometry]
F['drawn_ha'] = (F.area / 1e4).where(F.geom_type.str.contains('Polygon')).round(4)
F['drawn_m'] = F.length.where(F.geom_type.str.contains('Line')).round(1)
F = F.merge(T, on='project_id', how='left')
chk = F[['project_id', 'parts', 'drawn_ha', 'land_ha', 'drawn_m', 'pipe_length_m']]
print(chk.to_string(index=False))
ov = gpd.read_file(ROOT / 'gis/corridor/contribution_overlays_casey.gpkg'); bnd = ov[ov.ZONE_CODE == 'DCPO22'][['ZONE_CODE', 'geometry']]
out = G / 'collison.gpkg'
if out.exists(): out.unlink()
for k, sel in (('roads', F.cls == 'road'), ('intersections', F.cls == 'int'), ('drainage_channels', F.cls == 'drain'), ('underground_pipes', F.cls == 'pipe'), ('community_facility', F.cls == 'cf')):
    F[sel].to_file(out, layer=k)
bnd.to_file(out, layer='dcp_boundary')
import sqlite3
con = sqlite3.connect(out); T.to_sql('t5_t8_t11', con, index=False)
con.execute("INSERT INTO gpkg_contents (table_name, data_type, identifier) VALUES ('t5_t8_t11', 'attributes', 't5_t8_t11')"); con.commit(); con.close()

# ---------- app data ----------
corr = pd.read_csv(ROOT / 'data/reference/corridor_projects.csv'); corr = corr[corr.Plan.str.startswith('Collison')].drop_duplicates('Project ID').set_index('Project ID')['Corridor segment (approx.)']
CAT = {'RD': 'Road', 'IN': 'Intersection', 'CF': 'Community facility', 'PR': 'Plan preparation'}
cat = lambda p: CAT.get(p[:2]) or ('Underground pipe' if int(p[2:]) > 10 else 'Drainage channel')
STATUS = 'Not known – delivery status to confirm with Casey'
rows = []
for r in T.itertuples():
    comp = 'Development infrastructure levy – ' + r.group
    rows.append(dict(rid=f'{r.project_id}|fig3', project_id=r.project_id, map='fig3', category=cat(r.project_id), title=r.title, description=r.description,
                     component=comp, table='T5–T8, T11', type=r.type, land_ha=None if pd.isna(r.land_ha) else r.land_ha,
                     pipe_m=None if pd.isna(r.pipe_length_m) else r.pipe_length_m, land_cost_aud=None if pd.isna(r.land_cost_aud) else r.land_cost_aud,
                     construction_cost_aud=r.construction_cost_aud, total_cost_aud=r.total_cost_aud, apportionment_pct=r.apportionment_pct,
                     cost_to_mca_aud=r.cost_to_mca_aud, levy_per_ndha_aud=r.levy_per_ndha_aud, corridor_segment=corr.get(r.project_id, ''), status=STATUS,
                     export=['Collison Estate DCP', r.project_id, cat(r.project_id), f'{r.title} – {r.description}', comp, None if pd.isna(r.land_ha) else r.land_ha, None,
                             None if pd.isna(r.land_cost_aud) else r.land_cost_aud, r.construction_cost_aud, corr.get(r.project_id, '') or None, None]))
classes = {
    'road': dict(label='Road (RD)', kind='fill', color='#93305b', outline='#5a1634', map='fig3'),
    'int': dict(label='Intersection (IN)', kind='fill', color='#f7941d', outline='#b35f00', map='fig3'),
    'drain': dict(label='Drainage channel (DR01–DR10)', kind='fill', color='#16512f', outline='#0b2e1a', map='fig3'),
    'pipe': dict(label='Underground pipes (DR11–DR17)', kind='line', color='#2f35d6', dash='dash', width=3, map='fig3'),
    'cf': dict(label='Community facility (CF)', kind='fill', color='#ffdf87', outline='#c9a400', icon='star', map='fig3'),
    'bnd': dict(label='DCP boundary (precinct)', kind='line', color='#7b7bf0', width=2.5, dash='dash', map='', context=True)}
fc = []
for r in F.to_crs(4326).itertuples():
    fc.append(dict(type='Feature', properties=dict(project_id=r.project_id, key=f'{r.project_id}|fig3', map='fig3', cls=r.cls), geometry=shapely.geometry.mapping(r.geometry)))
for g in bnd.to_crs(4326).geometry: fc.append(dict(type='Feature', properties=dict(cls='bnd', map=''), geometry=shapely.geometry.mapping(g)))
tables = {'T5–T8, T11': T.drop(columns=['source']).replace({np.nan: None}).to_dict('records')}
write_app(ROOT / 'app/collison/data.js', dict(
    meta=dict(id='collison', short='Collison', colour='#7b4fd6', title='Collison Estate DCP – projects', subtitle='Figure 3 placed on the ground · Tables 5–8 and 11 · V4.1 Feb 2025', plan='Collison Estate DCP',
              source='Collison Estate Development Contributions Plan V4.1, February 2025', storage_key='collison-edits-v1', export_prefix='collison-projects'),
    maps=[dict(id='fig3', title='Figure 3 · Infrastructure Map – DCP Items')],
    images={'fig3': image_entry(G / 'georeferenced/DCPO22_fig3.tif', 'Figure 3 · Infrastructure map – DCP items (p. 12)', scale=1)},
    classes=classes, features=fc, rows=rows, tables=tables,
    columns=[dict(k='project_id', label='Project ID', t='id'), dict(k='category', label='Category'), dict(k='title', label='Title'), dict(k='description', label='Description', show=False),
             dict(k='type', label='Construction / land'), dict(k='land_ha', label='Land ha', t='num'), dict(k='pipe_m', label='Pipe m', t='num', show=False),
             dict(k='land_cost_aud', label='Land cost', t='money'), dict(k='construction_cost_aud', label='Construction', t='money'), dict(k='total_cost_aud', label='Total cost', t='money'),
             dict(k='apportionment_pct', label='Appt. %', t='num', show=False), dict(k='cost_to_mca_aud', label='Cost to MCA', t='money'), dict(k='levy_per_ndha_aud', label='Levy / NDHa', t='money'),
             dict(k='corridor_segment', label='Corridor segment', show=False), dict(k='acquired', label='Land acquired', t='edit'), dict(k='status', label='Status', t='edit')],
    detail=[dict(k='component', label='Levy component'), dict(k='type', label='Construction / land'), dict(k='land_ha', label='Land', t='ha'), dict(k='pipe_m', label='Pipe length', t='m'),
            dict(k='land_cost_aud', label='Land cost', t='money'), dict(k='construction_cost_aud', label='Construction cost', t='money'), dict(k='total_cost_aud', label='Total cost', t='money'),
            dict(k='apportionment_pct', label='Apportionment to MCA', t='pct'), dict(k='cost_to_mca_aud', label='Cost to MCA', t='money'), dict(k='levy_per_ndha_aud', label='Levy per NDHa', t='money'),
            dict(k='corridor_segment', label='Corridor segment')],
    totals=[dict(k='total_cost_aud', label='total cost', t='money'), dict(k='cost_to_mca_aud', label='to MCA', t='money'), dict(k='levy_per_ndha_aud', label='levy / NDHa', t='money')],
    export=dict(columns=json.loads((ROOT / 'data/reference/export_schema.json').read_text())['columns'], widths=json.loads((ROOT / 'data/reference/export_schema.json').read_text())['widths'],
                acquired_col=6, status_col=10, note='Land cost and construction cost from T11 (July 2024 dollars).')))
