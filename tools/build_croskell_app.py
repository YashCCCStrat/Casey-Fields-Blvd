"""Build app/croskell/data.js for the Croskell map-and-table app.

Rows: one per project and levy component, as the export schema (data/reference/export_schema.xlsx) expects:
  Table 5 -> 'Standard levy – transport construction', Table 6 -> 'Supplementary levy – transport construction',
  Table 7 -> 'Standard levy – community & recreation construction', Table 8 -> 'Land component – inner/outer public
  purpose land'. Each row knows which map features show it (construction rows: Plans 2/3; land rows: Plan 4).
Shapes: gis/croskell/croskell.gpkg (tools/build_croskell_gpkg.py). Plan images: gis/croskell/georeferenced/*.tif,
  downsampled to JPEG with their four corners in lon/lat. Corridor segment and default status: the Contribution-Plans
  register (data/reference/corridor_projects.csv covers corridor items; others get the register's Croskell status text)."""
import pathlib, json, base64, io, re
import numpy as np, pandas as pd, geopandas as gpd, rasterio
from PIL import Image
from pyproj import Transformer

ROOT = pathlib.Path(__file__).resolve().parents[1]
GP = ROOT / 'gis/croskell/croskell.gpkg'; REF = ROOT / 'data/reference/croskell'
T = {k: pd.read_csv(REF / f'{k}.csv') for k in ('table5', 'table6', 'table7', 'table8')}
corr = pd.read_csv(ROOT / 'data/reference/corridor_projects.csv')
corr = corr[corr.Plan.str.startswith('Croskell')].drop_duplicates('Project ID').set_index('Project ID')['Corridor segment (approx.)']
STATUS = 'Not known – ICP gazetted Oct 2025; delivery status to confirm with Casey'
CAT = {'SUP': 'Shared path', 'PED': 'Pedestrian signals', 'IN': 'Intersection', 'CU': 'Culvert', 'RD': 'Road', 'SR': 'Sports reserve', 'LP': 'Local park'}
cat = lambda p: CAT[re.search(r'CK-(?:OPPL-)?([A-Z]+)-', p).group(1)]

rows = []
def add(t, comp, plan_map, table, **kw):
    for r in T[t].itertuples():
        rows.append(dict(rid=f'{r.project_id}|{comp}', project_id=r.project_id, plan='Croskell (Employment) ICP', category=cat(r.project_id),
                         title=r.title, description=getattr(r, 'description', None) if isinstance(getattr(r, 'description', None), str) else '',
                         component=comp, table=table, map=plan_map, staging=getattr(r, 'staging', None), apportionment_pct=getattr(r, 'apportionment_pct', None),
                         funding_source=getattr(r, 'funding_source', None), total_cost_aud=getattr(r, 'total_cost_aud', None),
                         cost_to_icp_aud=getattr(r, 'cost_to_icp_aud', None), cost_per_ha_aud=getattr(r, 'cost_per_ha_aud', None),
                         land_ha=getattr(r, 'public_purpose_land_ha', None), footnote=getattr(r, 'footnote', None),
                         corridor_segment=corr.get(r.project_id.replace('CK-OPPL-', 'CK-'), ''), status=STATUS, **kw))
add('table5', 'Standard levy – transport construction', 'plan2', 'Table 5')
add('table6', 'Supplementary levy – transport construction', 'plan2', 'Table 6')
add('table7', 'Standard levy – community & recreation construction', 'plan3', 'Table 7')
for r in T['table8'].itertuples():
    pass
add('table8', 'Land component – inner public purpose land', 'plan4', 'Table 8')
for r in rows:
    if 'OPPL' in r['project_id'] and r['table'] == 'Table 8': r['component'] = 'Land component – outer public purpose land'; r['rid'] = f"{r['project_id']}|{r['component']}"
R = pd.DataFrame(rows).replace({np.nan: None})
print(len(R), 'rows;', R.groupby('table').size().to_dict())

# map features (EPSG:4326), each tagged with the map it belongs to
to4326 = lambda g: g.to_crs(4326)
LAY = {'plan2_construction_areas': 'plan2', 'plan2_construction_lines': 'plan2', 'plan2_construction_points': 'plan2', 'plan3_community_recreation': 'plan3',
       'plan4_land_as_drawn': 'plan4', 'plan4_land_vpa_fus': 'plan4fus', 'plan2_other_symbols_points': 'plan2other', 'plan2_other_symbols_lines': 'plan2other', 'psp_boundary': 'psp'}
feats = []
for lyr, m in LAY.items():
    g = to4326(gpd.read_file(GP, layer=lyr))
    for r in g.itertuples():
        pid = getattr(r, 'project_id', None)
        props = dict(layer=lyr, map=m, project_id=pid, kind=getattr(r, 'land_type', None) or getattr(r, 'type', None) or getattr(r, 'cls', None) or ('PSP boundary' if m == 'psp' else None),
                     category=cat(pid) if pid else None)
        feats.append(dict(type='Feature', geometry=json.loads(gpd.GeoSeries([r.geometry]).to_json())['features'][0]['geometry'], properties=props))
for f in feats:   # round coordinates to ~1 cm
    def rnd(c): return [rnd(x) for x in c] if isinstance(c[0], list) else [round(c[0], 7), round(c[1], 7)]
    f['geometry']['coordinates'] = rnd(f['geometry']['coordinates'])
print(len(feats), 'features')

# plan images
to_ll = Transformer.from_crs(7855, 4326, always_xy=True); IM = {}
for key, title in (('ICO3_plan2', 'Plan 2 · Standard and supplementary levy transport construction projects (p. 8)'), ('ICO3_plan3', 'Plan 3 · Standard levy community & recreation construction projects (p. 13)'), ('ICO3_plan4', 'Plan 4 · Public land provision (p. 15)')):
    d = rasterio.open(ROOT / f'gis/croskell/georeferenced/{key}.tif'); a = np.dstack([d.read(i) for i in (1, 2, 3)])
    H, W = a.shape[:2]; c = [d.transform * xy for xy in ((0, 0), (W, 0), (W, H), (0, H))]
    im = Image.fromarray(a).resize((W // 2, H // 2), Image.LANCZOS); b = io.BytesIO(); im.save(b, 'JPEG', quality=80, optimize=True)
    IM[key.split('_')[1]] = dict(title=title, coords=[[round(v, 7) for v in to_ll.transform(x, y)] for x, y in c], img='data:image/jpeg;base64,' + base64.b64encode(b.getvalue()).decode(), fit=d.tags().get('fit', ''))
icons = {n: (ROOT / f'symbology/maki/{n}-15.svg').read_text() for n in ('park', 'pitch', 'cricket', 'square-stroke', 'circle-stroked', 'roadblock', 'triangle')}
schema = {'columns': ['Plan', 'Project ID', 'Category', 'Project description', 'Levy component', ' land area (ha)', 'Land acquired ', 'Land cost ($)', 'Construction cost ($)', 'Corridor segment (approx.)', 'Current status / completion stage'],
          'widths': [5.0, 9.43, 8.57, 17.86, 15.14, 14.14, 9.14, 12.29, 19.57, 25.14, 30.71]}
tables = {k: T[k].replace({np.nan: None}).to_dict('records') for k in T}
out = dict(rows=R.to_dict('records'), features=dict(type='FeatureCollection', features=feats), images=IM, icons=icons, schema=schema, tables=tables,
           built='2026-11-13', source='Croskell (Employment) ICP, October 2025')
(ROOT / 'app/croskell/data.js').write_text('window.CK = ' + json.dumps(out, ensure_ascii=False) + ';\n', encoding='utf-8')
print('data.js', (ROOT / 'app/croskell/data.js').stat().st_size // 1024, 'KB')
