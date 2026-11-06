"""Build app/<area>/data.js from gis/edit/casey_fields_blvd.gpkg (shapes and project tables, edited in QGIS) and
data/app/<area>_spec.json (legend, columns, plan images – written by the extraction builders).
Light: needs only geopandas/pyogrio, so the GitHub Action can run it after each push. Usage: python tools/build_app.py [area …]"""
import sys, json, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import numpy as np, pandas as pd, geopandas as gpd, pyogrio, shapely
from appdata import ROOT, GPKG, write_js

def build(area):
    spec = json.loads((ROOT / f'data/app/{area}_spec.json').read_text(encoding='utf-8'))
    layers = [l for l, _ in pyogrio.list_layers(GPKG) if l.startswith(area + '_') and l != f'{area}_projects']
    feats = []
    for l in sorted(layers):
        g = gpd.read_file(GPKG, layer=l)
        if g.empty: continue
        g = g[g.geometry.notna() & ~g.geometry.is_empty]
        g['geometry'] = g.geometry.make_valid(); g = g.to_crs(4326)
        for r in g.itertuples():
            m = '' if r.map in (None, 'context') else r.map
            pid = r.project_id if isinstance(r.project_id, str) and r.project_id.strip() else None
            props = dict(cls=r.cls, map=m)
            if pid: props.update(project_id=pid.strip(), key=f'{pid.strip()}|{m}')
            if getattr(r, 'rot', None) is not None and r.rot == r.rot: props['rot'] = float(r.rot)
            feats.append(dict(type='Feature', properties=props, geometry=shapely.geometry.mapping(r.geometry)))
    rows = pyogrio.read_dataframe(GPKG, layer=f'{area}_projects', read_geometry=False)
    rows = rows.astype(object).where(rows.notna(), None).to_dict('records')
    for r in rows:
        for k, v in list(r.items()):
            if isinstance(v, (np.integer,)): r[k] = int(v)
            elif isinstance(v, (np.floating,)): r[k] = float(v)
    write_js(ROOT / f'app/{area}/data.js', dict(spec, features=feats, rows=rows))

if __name__ == '__main__':
    for a in sys.argv[1:] or [p.name.split('_spec')[0] for p in sorted((ROOT / 'data/app').glob('*_spec.json'))]:
        build(a)
