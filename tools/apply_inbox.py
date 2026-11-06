"""Apply changes to gis/edit/casey_fields_blvd.gpkg (run by the GitHub Action before rebuilding the app):
1. gis/edit/inbox/*.geojson – 'Changes for repo' files downloaded from the app: new features (geometry + table row) and
   edited table values. Each file is moved to gis/edit/inbox/applied/ once applied.
2. Shapes drawn in QGIS whose project_id is not yet in the projects table get a new table row, made from the shape's
   title / category / note fields, so the app shows them (fill in the rest in the table later)."""
import json, pathlib, shutil, datetime
import pandas as pd, geopandas as gpd, pyogrio, shapely
from shapely.geometry import shape, MultiPolygon, MultiLineString
ROOT = pathlib.Path(__file__).resolve().parents[1]; GPKG = ROOT / 'gis/edit/casey_fields_blvd.gpkg'; INBOX = ROOT / 'gis/edit/inbox'
GT = {'Polygon': 'polygons', 'MultiPolygon': 'polygons', 'LineString': 'lines', 'MultiLineString': 'lines', 'Point': 'points', 'MultiPoint': 'points'}
layers = lambda: [l for l, _ in pyogrio.list_layers(GPKG)]
def table(a): return pyogrio.read_dataframe(GPKG, layer=f'{a}_projects', read_geometry=False)
def save_table(a, t): pyogrio.write_dataframe(t, GPKG, layer=f'{a}_projects', driver='GPKG')
def spec(a): return json.loads((ROOT / f'data/app/{a}_spec.json').read_text(encoding='utf-8'))
changed = 0
for fp in sorted(INBOX.glob('*.geojson')) if INBOX.exists() else []:
    fc = json.loads(fp.read_text(encoding='utf-8')); n_new = n_edit = 0
    for f in fc['features']:
        p = dict(f['properties']); a = p.pop('area'); kind = p.pop('change')
        t = table(a)
        if kind == 'edit':
            rid = p.pop('rid'); m = t.rid == rid
            if not m.any(): print(f'{fp.name}: row {rid} not found – skipped'); continue
            for k, v in p.items():
                if k not in t.columns: t[k] = None
                t.loc[m, k] = v
            save_table(a, t); n_edit += 1; continue
        g = shape(f['geometry']); gt = GT[g.geom_type]
        if gt == 'polygons' and g.geom_type == 'Polygon': g = MultiPolygon([g])
        if gt == 'lines' and g.geom_type == 'LineString': g = MultiLineString([g])
        mp = p.pop('map'); cls = p.pop('cls'); lay = f'{a}_{mp}_{gt}'
        feat = gpd.GeoDataFrame([dict(project_id=p['project_id'], map=mp, cls=cls, legend=spec(a)['classes'].get(cls, {}).get('label'), title=p.get('title'), category=p.get('category'), note='added in the app')],
                                geometry=[g], crs=4326).to_crs(7855)
        if lay in layers():
            cur = gpd.read_file(GPKG, layer=lay); feat = gpd.GeoDataFrame(pd.concat([cur, feat], ignore_index=True), crs=7855)
        feat.to_file(GPKG, layer=lay, driver='GPKG')
        rid = p.pop('rid')
        if rid not in set(t.rid) and not ((t.project_id == p['project_id']) & (t['map'] == mp)).any():   # a shape for an existing project adds no row
            row = {c: None for c in t.columns}; row.update({k: v for k, v in p.items()}); row['rid'] = rid; row['map'] = mp
            t = pd.concat([t, pd.DataFrame([row])], ignore_index=True); save_table(a, t)
        n_new += 1
    (INBOX / 'applied').mkdir(exist_ok=True)
    shutil.move(fp, INBOX / 'applied' / f'{datetime.date.today()}_{fp.name}')
    print(f'{fp.name}: {n_new} new features, {n_edit} edited rows'); changed += 1
# shapes drawn in QGIS: fill in a missing map / legend class from the layer, and add a table row for a new project_id
for a in sorted({l.split('_')[0] for l in layers() if l.endswith('_projects')}):
    t = table(a); ids = set(t.project_id); add = []
    for l in [l for l in layers() if l.startswith(a + '_') and not l.endswith('_projects')]:
        g = gpd.read_file(GPKG, layer=l); _, mp, gt = l.split('_', 2)
        if mp != 'context':
            blank = lambda c: g[c].isna() | (g[c].astype(str).str.strip() == '')
            fix = blank('map') | blank('cls')
            if fix.any():
                g.loc[blank('map'), 'map'] = mp; g.loc[blank('cls'), 'cls'] = f'{mp}_added_{gt}'
                g.loc[fix & blank('legend'), 'legend'] = spec(a)['classes'].get(f'{mp}_added_{gt}', {}).get('label')
                g.to_file(GPKG, layer=l, driver='GPKG'); print(f'{l}: map / legend class filled in for {int(fix.sum())} shapes'); changed += 1
        for r in g.itertuples():
            pid = r.project_id.strip() if isinstance(r.project_id, str) else ''
            if pid and pid not in ids and r.map != 'context':
                row = {c: None for c in t.columns}
                row.update(rid=f'{pid}|{r.map}|added', project_id=pid, map=r.map, title=getattr(r, 'title', None) or pid, category=getattr(r, 'category', None) or 'Added feature',
                           description=getattr(r, 'note', None), component='Added in QGIS – to be confirmed', status='Added in QGIS – fill in details', plan=spec(a)['meta']['plan'], area_name=None)
                add.append({k: v for k, v in row.items() if k in t.columns or k in ('rid', 'project_id', 'map')}); ids.add(pid)
    if add:
        save_table(a, pd.concat([t, pd.DataFrame(add)], ignore_index=True)); print(f'{a}: {len(add)} table rows added for shapes drawn in QGIS: {[x["project_id"] for x in add]}'); changed += 1
print('applied' if changed else 'nothing to apply')
