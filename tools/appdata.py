"""Shared helpers for the plan builds and the map-and-table app (app/common/viewer.js)."""
import base64, io, json, pathlib
import numpy as np, shapely
from shapely.ops import nearest_points

def solid(g, d=4, join=80, w=16, node=0):
    """Pieces of one drawn item joined into one shape: tidy edges, bridge pieces closer than `join` m (minimum spanning
    tree, bridge as wide as the bar), fill holes and notches."""
    g = g.buffer(0).buffer(d, join_style='mitre', mitre_limit=3).buffer(-d, join_style='mitre', mitre_limit=3)
    parts = [p for p in shapely.get_parts(g) if p.area > 50]
    if not parts: return g
    edges = sorted((parts[i].distance(parts[j]), i, j) for i in range(len(parts)) for j in range(i + 1, len(parts)))
    grp = list(range(len(parts))); find = lambda i: i if grp[i] == i else find(grp[i]); bridges = []
    for dist, i, j in edges:
        if dist > join or find(i) == find(j): continue
        grp[find(i)] = find(j); p, q = nearest_points(parts[i], parts[j])
        bridges.append(shapely.unary_union([parts[i].intersection(p.buffer(w)), parts[j].intersection(q.buffer(w))]).convex_hull)
        if node: bridges.append(shapely.Point((p.x + q.x) / 2, (p.y + q.y) / 2).buffer(node))
    c = shapely.unary_union(parts + bridges).buffer(0.3, join_style='mitre').buffer(-0.3, join_style='mitre')
    return shapely.unary_union([shapely.Polygon(p.exterior) for p in shapely.get_parts(c) if p.area > 50]).simplify(0.5)

def image_entry(tif, title, scale=2):
    """A georeferenced plan image for the app: JPEG (data URL) and its four corners in lon/lat."""
    import rasterio; from PIL import Image; from pyproj import Transformer
    d = rasterio.open(tif); a = np.dstack([d.read(i) for i in (1, 2, 3)]); H, W = a.shape[:2]
    to = Transformer.from_crs(d.crs, 4326, always_xy=True)
    c = [d.transform * xy for xy in ((0, 0), (W, 0), (W, H), (0, H))]
    im = Image.fromarray(a);
    if scale > 1: im = im.resize((W // scale, H // scale), Image.LANCZOS)
    b = io.BytesIO(); im.save(b, 'JPEG', quality=80, optimize=True)
    return dict(title=title, coords=[[round(v, 7) for v in to.transform(x, y)] for x, y in c], img='data:image/jpeg;base64,' + base64.b64encode(b.getvalue()).decode(), fit=d.tags().get('fit', ''))

def _round(c): return [_round(x) for x in c] if isinstance(c[0], (list, tuple)) else [round(c[0], 7), round(c[1], 7)]

def write_js(path, data):
    for f in data['features']: f['geometry'] = dict(type=f['geometry']['type'], coordinates=_round(f['geometry']['coordinates']))
    clean = lambda v: None if isinstance(v, float) and v != v else v
    data['rows'] = [{k: clean(v) if not isinstance(v, list) else [clean(x) for x in v] for k, v in r.items()} for r in data['rows']]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('window.PLANS = (window.PLANS || []).concat([' + json.dumps(data, ensure_ascii=False) + ']);\n', encoding='utf-8')
    print(path.relative_to(path.parents[2]), path.stat().st_size // 1024, 'KB;', len(data['rows']), 'rows,', len(data['features']), 'features')

# ---------------------------------------------------------------------------------------------------------------------
# Editable source of truth: gis/edit/casey_fields_blvd.gpkg (shapes per plan map + one projects table per plan area).
# The extraction builders call write_app(); it saves the area's spec (legend, columns, plan images …) to
# data/app/<area>_spec.json, seeds the GeoPackage the first time (or when CFB_RESEED names the area / 'all'), and then
# builds app/<area>/data.js from the GeoPackage via build_app.py – so edits made in QGIS always win.
ROOT = pathlib.Path(__file__).resolve().parents[1]
GPKG = ROOT / 'gis/edit/casey_fields_blvd.gpkg'
GTYPE = {'Polygon': 'polygons', 'MultiPolygon': 'polygons', 'LineString': 'lines', 'MultiLineString': 'lines', 'Point': 'points', 'MultiPoint': 'points'}

def _seed(area, data):
    import os, geopandas as gpd, pandas as pd, pyogrio
    want = os.environ.get('CFB_RESEED', '')
    have = set(l for l, _ in pyogrio.list_layers(GPKG)) if GPKG.exists() else set()
    if f'{area}_projects' in have and want not in ('all', area): return False
    GPKG.parent.mkdir(parents=True, exist_ok=True)
    if have:                                                    # reseed: drop this area's layers first
        import sqlite3; con = sqlite3.connect(GPKG)
        for l in [l for l in have if l.startswith(area + '_')]:
            con.execute(f'DROP TABLE IF EXISTS "{l}"'); [con.execute(f'DELETE FROM {t} WHERE table_name=?', (l,)) for t in ('gpkg_contents', 'gpkg_geometry_columns', 'gpkg_ogr_contents')]
        con.commit(); con.close()
    g = gpd.GeoDataFrame.from_features(data['features'], crs=4326).to_crs(7855)
    g['legend'] = g.cls.map(lambda c: data['classes'][c]['label'])
    g['map'] = g['map'].fillna('').replace('', 'context')
    g['title'] = None; g['category'] = None; g['note'] = None   # filled in only for features added in QGIS (a new table row is made from them)
    cols = ['project_id', 'map', 'cls', 'legend', 'title', 'category', 'note'] + (['rot'] if 'rot' in g else []) + ['geometry']
    for c in cols[:-1]:
        if c not in g: g[c] = None
    from shapely.geometry import MultiPolygon, MultiLineString, MultiPoint
    multi = {'Polygon': MultiPolygon, 'LineString': MultiLineString, 'Point': MultiPoint}
    for (m, gt), part in g.groupby([g['map'], g.geom_type.map(GTYPE)]):
        part = part.copy()
        if gt != 'points': part['geometry'] = part.geometry.apply(lambda x: multi[x.geom_type]([x]) if x.geom_type in multi else x)   # multi-part, so parts can be added in QGIS
        part[cols].to_file(GPKG, layer=f'{area}_{m}_{gt}', driver='GPKG')
    ensure_layers(area, [m['id'] for m in data['maps']], 'rot' in g)
    rows = pd.DataFrame([{k: v for k, v in r.items() if k not in ('export', 'key')} for r in data['rows']])
    pyogrio.write_dataframe(rows, GPKG, layer=f'{area}_projects', driver='GPKG')
    print(f'seeded {GPKG.relative_to(ROOT)} for {area}: {len(g)} shapes, {len(rows)} project rows')
    return True

def ensure_layers(area, maps, rot=False):
    """An (empty) points, lines and polygons layer for every plan map, so any kind of shape can be drawn in QGIS."""
    import geopandas as gpd, pyogrio
    have = set(l for l, _ in pyogrio.list_layers(GPKG))
    cols = ['project_id', 'map', 'cls', 'legend', 'title', 'category', 'note'] + (['rot'] if rot else [])
    for m in maps:
        for gt, geom in (('polygons', 'MultiPolygon'), ('lines', 'MultiLineString'), ('points', 'Point')):
            if f'{area}_{m}_{gt}' not in have:
                empty = gpd.GeoDataFrame({c: pd_series(c) for c in cols}, geometry=gpd.GeoSeries([], crs=7855), crs=7855)
                pyogrio.write_dataframe(empty, GPKG, layer=f'{area}_{m}_{gt}', driver='GPKG', geometry_type=geom)

def pd_series(c):
    import pandas as pd
    return pd.Series([], dtype='float64' if c == 'rot' else 'object')

USER = {'polygons': ('fill', '#e0218a'), 'lines': ('line', '#e0218a'), 'points': ('point', '#e0218a')}
def add_user_classes(data):
    """One 'added feature' class per plan map and geometry type, for shapes drawn by the owner (app or QGIS)."""
    for m in data['maps']:
        for gt, (kind, col) in USER.items():
            data['classes'][f"{m['id']}_added_{gt}"] = dict(label=f'Added feature ({gt[:-1]})', kind=kind, color=col, outline='#7a0f4b', width=3, map=m['id'], user=True)

def write_app(path, data):
    area = data['meta']['id']
    add_user_classes(data)
    spec = {k: v for k, v in data.items() if k not in ('features', 'rows')}
    (ROOT / 'data/app').mkdir(parents=True, exist_ok=True)
    (ROOT / f'data/app/{area}_spec.json').write_text(json.dumps(spec, ensure_ascii=False), encoding='utf-8')
    _seed(area, data)
    import build_app; build_app.build(area)
