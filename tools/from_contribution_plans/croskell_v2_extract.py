"""Croskell v2 (standalone, not in run_all): extract the land and construction items drawn on Croskell ICP Plans 2 and 4.

Inputs : analysis/croskell-gis-v2/georeferenced/ICO3_plan{2,4}.tif (croskell_v2_georef.py), the SAM ViT-B checkpoint
         (/root/models/sam_vit_b_01ec64.pth, Meta, Apache-2.0), data/derived/project_shapes.gpkg (to name items),
         data/derived/plan_tables/ICO3.json (Tables 5, 6, 8 as printed)
Method : 1. colour masks from each plan's own legend colours (CIELAB distance), map area only (title and legend masked)
         2. ID label pills (same colour, white text) are found by their letter holes and removed; their centres are kept
            as negative prompts
         3. pieces of one item (hatching, JPEG gaps) are grouped by a morphological closing
         4. each item is segmented with SAM (segment-geospatial's predictor): its box + positive points on its colour
            pixels + negative points on label pills; SAM's mask is kept inside the item's dilated colour area. If SAM
            and the colour mask disagree (IoU < 0.6) the colour mask is used and the item flagged
         5. each item is named by overlap with the VPA FUS asset of the same project (or, for construction items, the
            nearest known project location of the same type), and joined to Tables 5, 6 and 8
Outputs: analysis/croskell-gis-v2/*.shp|gpkg|csv"""
import sys, pathlib, json, re, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent)); import config
import numpy as np, cv2, rasterio, rasterio.features, geopandas as gpd, pandas as pd, shapely
from shapely.geometry import shape

R, W = config.ROOT, config.DERIVED
OUT = R / 'analysis/croskell-gis-v2'
SH = gpd.read_file(W / 'project_shapes.gpkg'); SH = SH[SH.plan == 'Croskell (Employment) ICP']
PR = gpd.read_file(W / 'casey_precincts.gpkg'); PSP = PR[PR.VPA_No.astype(str).str.startswith('1051')].geometry.iloc[0]
_sam = None
def sam():
    global _sam
    if _sam is None:
        from samgeo import SamGeo
        _sam = SamGeo(model_type='vit_b', automatic=False, checkpoint_dir='/root/models', device='cpu')
    return _sam

def load(key):
    d = rasterio.open(OUT / f'georeferenced/{key}.tif')
    a = np.dstack([d.read(i) for i in (1, 2, 3)])
    valid = np.ones(a.shape[:2], bool); valid[:260, :] = False; valid[1880:, :1050] = False; valid[2300:, :] = False
    return d, a, cv2.cvtColor(a, cv2.COLOR_RGB2LAB).astype(np.float32), valid

def ref_colour(lab, box):
    x0, y0, x1, y1 = box; mx, my = min(6, (x1 - x0) // 4), min(6, (y1 - y0) // 4)
    return np.median(lab[y0 + my:y1 - my, x0 + mx:x1 - mx].reshape(-1, 3), axis=0)

def class_mask(lab, valid, ref, tol=28):
    return (np.sqrt(((lab - ref) ** 2).sum(-1)) < tol) & valid

def pills(m, min_holes=3):
    """Label pills: colour components with letter-shaped holes. Returns (mask of pills, list of pill centres)."""
    n, cc, st, cen = cv2.connectedComponentsWithStats(m.astype(np.uint8), 8)
    pm = np.zeros_like(m); centres = []
    for i in range(1, n):
        x, y, w, h, area = st[i]
        if area < 150 or not (25 <= h <= 70 and 60 <= w <= 160): continue
        sub = (cc[y:y + h, x:x + w] == i).astype(np.uint8)
        cs, hier = cv2.findContours(sub, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        holes = sum(1 for k, c in enumerate(cs) if hier[0][k][3] >= 0 and cv2.contourArea(c) > 8)
        if holes >= min_holes:
            filled = cv2.morphologyEx(sub, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
            pm[y:y + h, x:x + w] |= filled.astype(bool); centres.append((cen[i][0], cen[i][1]))
    return pm, centres

def label_boxes(m, close):
    """ID labels: white letters enclosed by the class colour, grouped into words; returns a mask of the label boxes."""
    g = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((close, close), np.uint8))
    filled = g.copy(); cs, _ = cv2.findContours(g, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE); cv2.drawContours(filled, cs, -1, 1, -1)
    holes = filled.astype(bool) & ~g.astype(bool)
    n, cc, st, cen = cv2.connectedComponentsWithStats(holes.astype(np.uint8), 8)
    let = [(cen[i][0], cen[i][1], st[i]) for i in range(1, n) if 6 <= st[i, 4] <= 600 and st[i, 3] <= 40]
    out = np.zeros_like(m); used = set(); centres = []
    for i, (x, y, _) in enumerate(let):
        if i in used: continue
        grp = [j for j, (x2, y2, _) in enumerate(let) if abs(y2 - y) < 12 and abs(x2 - x) < 75]
        if len(grp) < 3: continue
        used |= set(grp)
        xs = [let[j][2][0] for j in grp] + [let[j][2][0] + let[j][2][2] for j in grp]; ys = [let[j][2][1] for j in grp] + [let[j][2][1] + let[j][2][3] for j in grp]
        x0, x1, y0, y1 = min(xs) - 16, max(xs) + 16, min(ys) - 12, max(ys) + 12
        out[max(0, y0):y1, max(0, x0):x1] = True; centres.append(((x0 + x1) / 2, (y0 + y1) / 2))
    return out, centres

def clean(m, close, open_=5, min_ha=0.12):
    """Colour mask -> item mask: close gaps (hatching, JPEG), cut out ID labels, remove leader lines and specks."""
    lb, centres = label_boxes(m, 3)   # letters are found before the big closing fills them in
    g = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((close, close), np.uint8)).astype(bool) & ~lb
    g = cv2.morphologyEx(g.astype(np.uint8), cv2.MORPH_OPEN, np.ones((open_, open_), np.uint8)).astype(bool)
    # a label printed on top of an item leaves a gap: bridge the item across the label box (only between its parts)
    bridge = cv2.morphologyEx(g.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((61, 61), np.uint8)).astype(bool) & lb
    g |= bridge & cv2.erode(bridge.astype(np.uint8), np.ones((9, 9), np.uint8)).astype(bool) | (bridge & g)
    n, cc, st, _ = cv2.connectedComponentsWithStats(g.astype(np.uint8), 8)
    px = min_ha * 1e4 / (1.27 ** 2)
    return [(cc == i) for i in range(1, n) if st[i, 4] >= px], centres

def objects(m, close=9, min_px=250):
    k = np.ones((close, close), np.uint8)
    g = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_CLOSE, k)
    n, cc, st, _ = cv2.connectedComponentsWithStats(g, 8)
    return [(cc == i) & cv2.dilate(m.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool) | ((cc == i) & (close > 9)) for i in range(1, n) if st[i, 4] >= min_px]

def refine(a, obj, neg_pts, pad=40):
    """SAM on a window around the object: box + up to 6 positive points + negative points on label pills."""
    ys, xs = np.nonzero(obj); x0, y0, x1, y1 = xs.min(), ys.min(), xs.max(), ys.max()
    X0, Y0 = max(0, x0 - 300), max(0, y0 - 300); X1, Y1 = min(a.shape[1], x1 + 300), min(a.shape[0], y1 + 300)
    s = sam(); s.set_image(np.ascontiguousarray(a[Y0:Y1, X0:X1]))
    idx = np.linspace(0, len(xs) - 1, 6).astype(int)
    pos = np.c_[xs[idx] - X0, ys[idx] - Y0]
    neg = np.array([(px - X0, py - Y0) for px, py in neg_pts if x0 - pad <= px <= x1 + pad and y0 - pad <= py <= y1 + pad]).reshape(-1, 2)
    pts = np.r_[pos, neg]; lbl = np.r_[np.ones(len(pos)), np.zeros(len(neg))]
    m, sc, _ = s.predictor.predict(point_coords=pts, point_labels=lbl, box=np.array([x0 - X0 - 3, y0 - Y0 - 3, x1 - X0 + 3, y1 - Y0 + 3]), multimask_output=False)
    full = np.zeros_like(obj); full[Y0:Y1, X0:X1] = m[0]
    zone = cv2.dilate(obj.astype(np.uint8), np.ones((7, 7), np.uint8)).astype(bool)
    full &= zone
    iou = (full & obj).sum() / max((full | obj).sum(), 1)
    return full, float(sc[0]), float(iou)

def polygonise(mask, tr, simplify=0.6):
    gs = [shape(g) for g, v in rasterio.features.shapes(mask.astype(np.uint8), mask=mask, transform=tr) if v == 1]
    g = shapely.unary_union(gs).buffer(0)
    return g.simplify(simplify) if not g.is_empty else g

# ---------------- Plan 4: public purpose land ----------------
d, a, lab, valid = load("ICO3_plan4")
RUN4 = "--skip4" not in sys.argv
LEG4 = {'recreation and open space': (160, 2010, 245, 2048), 'intersection': (160, 2065, 245, 2100), 'road': (160, 2120, 245, 2158)}
rows = []
for cls, box in (LEG4.items() if RUN4 else []):
    m = class_mask(lab, valid, ref_colour(lab, box))
    objs, centres = clean(m, close=19 if cls == 'road' else 5)
    for obj in objs:
        sm, score, iou = refine(a, obj, centres)
        use = sm if iou >= 0.6 else obj
        rows.append(dict(cls=cls, geometry=polygonise(use, d.transform), sam_score=round(score, 3), sam_iou=round(iou, 3),
                         method='SAM (box + points)' if iou >= 0.6 else 'colour mask (SAM disagreed)'))
if RUN4:
    P4 = gpd.GeoDataFrame(rows, geometry='geometry', crs=7855)
    print(f'Plan 4: {len(P4)} land objects'); print(P4.drop(columns='geometry').assign(ha=(P4.area / 1e4).round(4)).to_string())
    P4.to_file(OUT / '_plan4_objects_raw.gpkg')

# ---------------- Plan 2: construction projects (line and point symbols) ----------------
from skimage.morphology import skeletonize
def centrelines(mask, tr, min_len_m=15):
    """Skeleton of a symbol mask traced into lines (pixel graph: nodes where degree != 2)."""
    sk = skeletonize(mask); ys, xs = np.nonzero(sk); pts = set(zip(ys.tolist(), xs.tolist()))
    nb = lambda p: [(p[0] + dy, p[1] + dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if (dy or dx) and (p[0] + dy, p[1] + dx) in pts]
    deg = {p: len(nb(p)) for p in pts}; seen = set(); lines = []
    starts = [p for p in pts if deg[p] != 2] or list(pts)[:1]
    for s0 in starts:
        for n1 in nb(s0):
            if (s0, n1) in seen: continue
            path = [s0, n1]; seen |= {(s0, n1), (n1, s0)}
            while deg.get(path[-1]) == 2:
                nxt = [q for q in nb(path[-1]) if q != path[-2] and (path[-1], q) not in seen]
                if not nxt: break
                seen |= {(path[-1], nxt[0]), (nxt[0], path[-1])}; path.append(nxt[0])
            if len(path) > 2: lines.append(shapely.LineString([tr * (x + 0.5, y + 0.5) for y, x in path]))
    g = shapely.line_merge(shapely.unary_union(lines)) if lines else shapely.GeometryCollection()
    ring = lambda l: shapely.Point(l.coords[0]).distance(shapely.Point(l.coords[-1])) < 6 and l.length < 120   # closed loops
    parts = [l for l in shapely.get_parts(g) if l.length >= min_len_m and not ring(l)]
    return shapely.MultiLineString(parts).simplify(1.0) if parts else shapely.GeometryCollection()

d2, a2, lab2, valid2 = load('ICO3_plan2'); valid2[1670:, :780] = False
rows2 = []
LEG2 = {'road project': (165, 1776, 230, 1784), 'intersection project': (165, 1833, 230, 1841), 'vdp': (175, 2166, 235, 2176)}
REF2 = {k: ref_colour(lab2, b) for k, b in LEG2.items()}
D2 = np.stack([np.sqrt(((lab2 - r) ** 2).sum(-1)) for r in REF2.values()]); NEAR2 = D2.argmin(0)   # each pixel's nearest legend colour
def nearest_mask(k, tol): i = list(REF2).index(k); return (NEAR2 == i) & (D2[i] < tol) & valid2
def roundness(sub):
    cs, _ = cv2.findContours(sub.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE); c = max(cs, key=cv2.contourArea)
    return 4 * np.pi * cv2.contourArea(c) / max(cv2.arcLength(c, True) ** 2, 1)
for cls in ('road project', 'intersection project'):
    objs, _ = clean(nearest_mask(cls, 30), close=5, open_=3, min_ha=0.03)
    for obj in objs:
        ys, xs = np.nonzero(obj)
        if (xs.max() - xs.min()) < 45 and (ys.max() - ys.min()) < 45:     # a small symbol, not a bar
            if cls == 'intersection project' and roundness(obj[ys.min():ys.max() + 1, xs.min():xs.max() + 1]) < 0.6:   # an X, not a node ring
                rows2.append(dict(cls='pedestrian crossing', geometry=shapely.Point(d2.transform * (xs.mean() + 0.5, ys.mean() + 0.5)), method='colour mask (X symbol centre)'))
            continue
        rows2.append(dict(cls=cls, geometry=polygonise(obj, d2.transform), method='colour mask (symbol footprint as drawn)'))
# pedestrian signals: olive squares
m = class_mask(lab2, valid2, ref_colour(lab2, (183, 2038, 190, 2062)), tol=18)   # the olive ring, not its white centre
n, cc, st, cen = cv2.connectedComponentsWithStats(m.astype(np.uint8), 8)
for i in range(1, n):
    x, y, w, h, ar = st[i]
    if not (120 <= ar <= 1500 and 0.75 < w / h < 1.33 and 18 <= w <= 45): continue
    sub = (cc[y:y + h, x:x + w] == i).astype(np.uint8); cs, hier = cv2.findContours(sub, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if sum(1 for k in range(len(cs)) if hier[0][k][3] >= 0 and cv2.contourArea(cs[k]) > 15) == 1:   # a square ring
        rows2.append(dict(cls='pedestrian signals', geometry=shapely.Point(d2.transform * (cen[i][0] + 0.5, cen[i][1] + 0.5)), method='colour mask (symbol centre)'))
# VDP underground cable (context, not an ICP project)
objs, _ = clean(nearest_mask('vdp', 30), close=3, open_=1, min_ha=0.02)
for obj in objs: rows2.append(dict(cls='VDP underground cable (context)', geometry=centrelines(obj, d2.transform, 40), method='colour mask -> centreline'))
# shared user paths: chains of black dots
blk = (lab2[..., 0] < 70) & valid2
n, cc, st, cen = cv2.connectedComponentsWithStats(blk.astype(np.uint8), 8)
dots = np.array([cen[i] for i in range(1, n) if 25 <= st[i, 4] <= 160 and 0.7 < st[i, 2] / max(st[i, 3], 1) < 1.4 and st[i, 2] <= 16 and st[i, 4] / (st[i, 2] * st[i, 3]) > 0.55])
used = np.zeros(len(dots), bool); chains = []
for i in range(len(dots)):
    if used[i]: continue
    ch = [i]; used[i] = True; k = 0
    while k < len(ch):
        dd = np.hypot(*(dots - dots[ch[k]]).T); new = np.nonzero((dd < 26) & ~used)[0]
        used[new] = True; ch += new.tolist(); k += 1
    if len(ch) >= 3: chains.append(dots[ch])
for c in chains:
    u, s_, vt = np.linalg.svd(c - c.mean(0)); t = (c - c.mean(0)) @ vt[0]; o = c[np.argsort(t)]
    if np.abs((c - c.mean(0)) @ vt[1]).max() > 8: continue                          # not in a straight row (text, symbols)
    rows2.append(dict(cls='shared user path', geometry=shapely.LineString([d2.transform * (x + 0.5, y + 0.5) for x, y in o[[0, -1]]]), method=f'chain of {len(c)} dots'))
# culverts: black ")(" symbols near a path or road (black components of symbol size that are not dots or text)
for i in range(1, n):
    x, y, w, h, ar = st[i]
    if 150 <= ar <= 900 and 25 <= max(w, h) <= 70 and ar / (w * h) < 0.45:
        rows2.append(dict(cls='culvert (candidate)', geometry=shapely.Point(d2.transform * (cen[i][0] + 0.5, cen[i][1] + 0.5)), method='black symbol (shape filter)'))
P2 = gpd.GeoDataFrame(rows2, geometry='geometry', crs=7855)
P2 = P2[~P2.geometry.is_empty]
print(f'Plan 2: {len(P2)} objects'); print(P2.groupby('cls').size().to_string())
P2.to_file(OUT / '_plan2_objects_raw.gpkg')

# ---------------- name the objects, attach Tables 5, 6 and 8, write ----------------
P4 = gpd.read_file(OUT / '_plan4_objects_raw.gpkg')
prior = SH.copy(); prior['pre'] = prior.project_key.str.extract(r'^CK-([A-Z]+)-')[0]
fus = prior[prior.confidence == 'Asset']
# FUS also gives CK-SR-01/02 their neighbouring *existing* open space; Table 8 is only the 'Local Open Space' part
import os
_f = gpd.read_file(config.AD / [x for x in os.listdir(config.AD) if x.startswith('FUS_')][0]).to_crs(7855)
_sr = _f[_f.ASSET_ID.isin(['CK-SR-01', 'CK-SR-02']) & (_f.LU_TYPE == 'Local Open Space')].dissolve('ASSET_ID').reset_index()
fus = pd.concat([fus[~fus.project_key.isin(['CK-SR-01', 'CK-SR-02'])], gpd.GeoDataFrame(dict(project_key=_sr.ASSET_ID, pre='SR', confidence='Asset', geometry=_sr.geometry), crs=7855)])
fus = gpd.GeoDataFrame(fus, geometry='geometry', crs=7855)
ATTR = {L: gpd.read_file(R / 'gis/contribution_plans_gis.gpkg', layer=f'croskell_ico3__{L}').drop(columns='geometry') for L in ('plan2_transport_projects', 'plan4_public_land')}
keep_cols = lambda df: [c for c in df.columns if c.startswith(('t5_', 't6_', 't8_')) or c in ('proj_id', 'reg_cat', 'est_2627')]

land = []
for r in P4.itertuples():
    pres = {'recreation and open space': ('LP', 'SR'), 'intersection': ('IN',), 'road': ('RD',)}[r.cls]
    cand = fus[fus.pre.isin(pres)]
    if r.cls == 'road':
        for part, pid in ((r.geometry.intersection(PSP), 'CK-RD-01'), (r.geometry.difference(PSP), 'CK-OPPL-RD-01')):
            if part.area > 300: land.append(dict(proj_id=pid, cls=r.cls, method=r.method, sam_iou=r.sam_iou, geometry=part))
        continue
    ov = cand.geometry.intersection(r.geometry).area
    pid = cand.project_key.iloc[int(ov.values.argmax())] if ov.max() > 0 else cand.project_key.iloc[int(cand.distance(r.geometry).values.argmin())]
    land.append(dict(proj_id=pid, cls=r.cls, method=r.method, sam_iou=r.sam_iou, geometry=r.geometry))
L4 = gpd.GeoDataFrame(land, geometry='geometry', crs=7855).dissolve('proj_id', aggfunc={'cls': 'first', 'method': 'first', 'sam_iou': 'min'}).reset_index()
L4 = L4.merge(ATTR['plan4_public_land'][keep_cols(ATTR['plan4_public_land'])], on='proj_id', how='left')
L4['drawn_ha'] = (L4.area / 1e4).round(4)
fa = fus.dissolve('project_key').area / 1e4
L4['fus_ha'] = L4.proj_id.map(lambda p: round(fa.get(p, np.nan), 4) if p != 'CK-OPPL-RD-01' else np.nan)
L4['drawn_pct'] = (100 * L4.drawn_ha / L4.t8_ppl_ha).round(0)
L4.insert(1, 'map', 'Plan 4 · Public land provision (printed p. 15)')
print('\nPlan 4 land as drawn vs Table 8 vs FUS (ha):'); print(L4[['proj_id', 'cls', 'method', 'drawn_ha', 't8_ppl_ha', 'fus_ha', 'drawn_pct']].to_string(index=False))
missing = sorted(set(ATTR['plan4_public_land'].proj_id) - set(L4.proj_id)); print('Table 8 items not found on Plan 4:', missing)

P2 = gpd.read_file(OUT / '_plan2_objects_raw.gpkg')
v1 = gpd.read_file(W / 'digitised_locations.gpkg'); v1 = v1[v1.plan == 'Croskell (Employment) ICP']
pri = pd.concat([prior[['project_key', 'pre', 'geometry']], v1.assign(project_key=v1.project_id, pre=v1.project_id.str.extract(r'^CK-([A-Z]+)-')[0])[['project_key', 'pre', 'geometry']]])
pri = gpd.GeoDataFrame(pri, geometry='geometry', crs=7855)
con, other = [], []
for r in P2.itertuples():
    pre = {'road project': 'RD', 'intersection project': 'IN', 'shared user path': 'SUP', 'pedestrian signals': 'PED', 'culvert (candidate)': 'CU'}.get(r.cls)
    if pre is None: other.append(dict(cls=r.cls.replace(' (context)', ''), method=r.method, geometry=r.geometry)); continue
    c = pri[pri.pre == pre]; dd = c.distance(r.geometry.centroid if pre in ('SUP',) else r.geometry)
    if dd.min() > {'PED': 60}.get(pre, 150): continue
    con.append(dict(proj_id=c.project_key.iloc[int(dd.values.argmin())], cls=r.cls.replace(' (candidate)', ''), method=r.method, geometry=r.geometry))
C2 = gpd.GeoDataFrame(con, geometry='geometry', crs=7855)
for pid in sorted(set(ATTR['plan2_transport_projects'].proj_id) - set(C2.proj_id)):   # not found automatically: keep the v1 hand-digitised shape
    g = v1[v1.project_id == pid]
    if len(g): C2 = pd.concat([C2, gpd.GeoDataFrame([dict(proj_id=pid, cls=g.kind.iloc[0].lower(), method='v1 hand-digitised (symbol not found automatically)', geometry=g.geometry.iloc[0])], crs=7855)])
C2 = gpd.GeoDataFrame(C2, geometry='geometry', crs=7855).dissolve('proj_id', aggfunc={'cls': 'first', 'method': 'first'}).reset_index()
C2['geometry'] = C2.geometry.apply(lambda g: g.centroid if g.geom_type == 'MultiPoint' else g)   # both halves of a ')(' symbol -> its centre
C2 = C2.merge(ATTR['plan2_transport_projects'][keep_cols(ATTR['plan2_transport_projects'])], on='proj_id', how='left')
C2.insert(1, 'map', 'Plan 2 · Standard and supplementary levy transport construction projects (printed p. 8)')
C2['drawn_m'] = C2.length.where(C2.geom_type.str.contains('Line')).round(0); C2['drawn_ha'] = (C2.area / 1e4).where(C2.geom_type.str.contains('Polygon')).round(4)
print('\nPlan 2 construction items:'); print(C2[['proj_id', 'cls', 'method', 'drawn_m', 't5_cost']].to_string(index=False))
print('Table 5/6 items not found on Plan 2:', sorted(set(ATTR['plan2_transport_projects'].proj_id) - set(C2.proj_id)))
O2 = gpd.GeoDataFrame(other, geometry='geometry', crs=7855)
xs = O2[O2.cls == 'pedestrian crossing']; keep = []
for i, r in xs.iterrows():
    if all(r.geometry.distance(xs.loc[j].geometry) > 25 for j in keep): keep.append(i)
O2 = pd.concat([O2[O2.cls != 'pedestrian crossing'], xs.loc[keep]]); O2 = gpd.GeoDataFrame(O2, geometry='geometry', crs=7855)
O2.insert(0, 'map', 'Plan 2 (printed p. 8) – shown on the plan, not ICP projects')

# write: shapefiles by geometry type, one GeoPackage, CSV attribute tables, README, zip
import zipfile, shutil
for p in OUT.glob('croskell_*'): p.unlink()
gpkg = OUT / 'croskell_gis_v2.gpkg'
if gpkg.exists(): gpkg.unlink()
FUS4 = fus[fus.project_key.isin(L4.proj_id)].dissolve('project_key').reset_index().rename(columns={'project_key': 'proj_id'})[['proj_id', 'geometry']]
FUS4 = FUS4.merge(ATTR['plan4_public_land'][keep_cols(ATTR['plan4_public_land'])], on='proj_id', how='left'); FUS4['fus_ha'] = (FUS4.area / 1e4).round(4)
layers = {'croskell_plan4_land_as_drawn': L4, 'croskell_plan4_land_vpa_fus': FUS4, 'croskell_plan2_construction_as_drawn': C2, 'croskell_plan2_other_symbols': O2}
for name, G in layers.items():
    G = G.copy(); G.columns = [c if c == 'geometry' else c[:10] for c in G.columns]
    G.to_file(gpkg, layer=name)
    for suf, types in (('pt', ('Point', 'MultiPoint')), ('ln', ('LineString', 'MultiLineString')), ('pg', ('Polygon', 'MultiPolygon'))):
        part = G[G.geom_type.isin(types)]
        if len(part):
            part = part.copy()
            if (part.geom_type == types[1]).any():   # a shapefile holds one type: promote singles to multi
                mk = {'pt': shapely.MultiPoint, 'ln': shapely.MultiLineString, 'pg': shapely.MultiPolygon}[suf]
                part['geometry'] = part.geometry.apply(lambda g: mk([g]) if g.geom_type == types[0] else g)
            part.to_file(OUT / f'{name}_{suf}.shp', encoding='utf-8')
    G.drop(columns='geometry').to_csv(OUT / f'{name}.csv', index=False, encoding='utf-8-sig')
print('\nwritten:', sorted(p.name for p in OUT.glob('croskell_*.shp')))
