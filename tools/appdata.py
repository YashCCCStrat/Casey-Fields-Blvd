"""Shared helpers for the plan builds and the map-and-table app (app/common/viewer.js)."""
import base64, io, json, pathlib
import numpy as np, rasterio, shapely
from shapely.ops import nearest_points
from PIL import Image
from pyproj import Transformer

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
    d = rasterio.open(tif); a = np.dstack([d.read(i) for i in (1, 2, 3)]); H, W = a.shape[:2]
    to = Transformer.from_crs(d.crs, 4326, always_xy=True)
    c = [d.transform * xy for xy in ((0, 0), (W, 0), (W, H), (0, H))]
    im = Image.fromarray(a);
    if scale > 1: im = im.resize((W // scale, H // scale), Image.LANCZOS)
    b = io.BytesIO(); im.save(b, 'JPEG', quality=80, optimize=True)
    return dict(title=title, coords=[[round(v, 7) for v in to.transform(x, y)] for x, y in c], img='data:image/jpeg;base64,' + base64.b64encode(b.getvalue()).decode(), fit=d.tags().get('fit', ''))

def _round(c): return [_round(x) for x in c] if isinstance(c[0], (list, tuple)) else [round(c[0], 7), round(c[1], 7)]

def write_app(path, data):
    for f in data['features']: f['geometry'] = dict(type=f['geometry']['type'], coordinates=_round(f['geometry']['coordinates']))
    clean = lambda v: None if isinstance(v, float) and v != v else v
    data['rows'] = [{k: clean(v) if not isinstance(v, list) else [clean(x) for x in v] for k, v in r.items()} for r in data['rows']]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('window.PLAN = ' + json.dumps(data, ensure_ascii=False) + ';\n', encoding='utf-8')
    print(path.relative_to(path.parents[2]), path.stat().st_size // 1024, 'KB;', len(data['rows']), 'rows,', len(data['features']), 'features')
