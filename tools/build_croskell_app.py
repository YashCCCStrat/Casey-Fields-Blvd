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
# culverts: rotate the plan's culvert symbol to run along the road / path it sits on (bearing of the nearby RD-01 or SUP-01)
import shapely, math
_g = gpd.read_file(GP, layer='plan2_construction_points'); _a = gpd.read_file(GP, layer='plan2_construction_areas'); _l = gpd.read_file(GP, layer='plan2_construction_lines')
_along = {'CK-CU-01': _a[_a.project_id == 'CK-RD-01'].geometry.iloc[0], 'CK-CU-02': _l[_l.project_id == 'CK-SUP-01'].geometry.iloc[0]}
ROT = {}
for r in _g[_g.project_id.str.startswith('CK-CU')].itertuples():
    near = _along[r.project_id].intersection(r.geometry.buffer(60))
    rect = (near if not near.is_empty else _along[r.project_id]).minimum_rotated_rectangle
    c = list(rect.exterior.coords); e = max([(c[i], c[i + 1]) for i in range(4)], key=lambda s_: math.dist(*s_))
    bearing = math.degrees(math.atan2(e[1][0] - e[0][0], e[1][1] - e[0][1])) % 180
    ROT[r.project_id] = round(bearing - 90, 1)        # the icon is drawn east-west
for f in feats:
    if f['properties']['project_id'] in ROT and f['properties']['map'] == 'plan2': f['properties']['rot'] = ROT[f['properties']['project_id']]
print('culvert rotation', ROT)
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
# ---------- shared app format (app/common/viewer.js) ----------
import sys; sys.path.insert(0, str(ROOT / 'tools')); from appdata import write_app
def cls_of(p):
    l, m, k, c = p['layer'], p['map'], p.get('kind') or '', p.get('category') or ''
    if m == 'psp': return 'psp'
    if l == 'plan2_other_symbols_points': return 'p2_xing'
    if l == 'plan2_other_symbols_lines': return 'p2_vdp'
    if m == 'plan2': return {'Intersection': 'p2_IN', 'Road': 'p2_RD', 'Shared path': 'p2_SUP', 'Culvert': 'p2_CU', 'Pedestrian signals': 'p2_PED'}[c]
    if m == 'plan3': return 'p3_SR'
    if l == 'plan4_land_vpa_fus': return 'p4_fus'
    return {'Land for intersection': 'p4_IN', 'Land for road': 'p4_RD', 'Outer public purpose land (road)': 'p4_OPPL', 'Land for recreation and open space': 'p4_REC'}[k]
for f_ in feats:
    p = f_['properties']; p['cls'] = cls_of(p)
    if p['map'] == 'plan4fus': p['map'] = 'plan4'
    if p.get('project_id'): p['key'] = p['project_id'] + '|' + p['map']
    else: p.pop('key', None)
    if p['map'] in ('psp', 'plan2other'): p['map'] = '' if p['map'] == 'psp' else 'plan2'
    for k in ('layer', 'kind', 'category'): p.pop(k, None)
classes = {
    'p2_RD': dict(label='Road project (RD)', kind='fill', color='#a6114f', outline='#5c0a2b', map='plan2'),
    'p2_IN': dict(label='Intersection project (IN)', kind='fill', color='#f7941d', outline='#b35f00', map='plan2'),
    'p2_SUP': dict(label='Shared user path project (SUP)', kind='line', color='#111111', dash='dots', width=5, map='plan2'),
    'p2_CU': dict(label='Culvert project (CU)', kind='point', icon='cu', map='plan2', color='#111111'),
    'p2_PED': dict(label='Pedestrian signals project (PED)', kind='point', icon='ped', map='plan2', color='#a5a831'),
    'p2_xing': dict(label='Pedestrian crossing', kind='point', icon='xing', map='plan2', color='#f7941d', context=True),
    'p2_vdp': dict(label='VDP underground cable', kind='line', color='#d42b49', width=2, map='plan2', arrow=True, context=True),
    'p3_SR': dict(label='Local sports reserve (SR)', kind='fill', color='#6f8e3d', outline='#2f4a14', map='plan3'),
    'p4_REC': dict(label='Land for recreation and open space', kind='fill', color='#6f8e3d', outline='#2f4a14', map='plan4'),
    'p4_IN': dict(label='Land for intersection', kind='fill', color='#f7941d', outline='#b35f00', map='plan4'),
    'p4_RD': dict(label='Land for road', kind='fill', color='#a6114f', outline='#5c0a2b', map='plan4'),
    'p4_OPPL': dict(label='Outer public purpose land', kind='fill', color='#a6114f', outline='#111111', pattern='hatch', map='plan4'),
    'p4_fus': dict(label='VPA surveyed land (comparison)', kind='fill', style='outline', color='#0a7d5f', outline='#0a7d5f', map='plan4', on=False),
    'psp': dict(label='Precinct boundary (PSP 1051)', kind='line', color='#24337a', width=2.5, dash='long', map='', context=True)}
for r in rows:
    r['export'] = [r['plan'], r['project_id'], r['category'], ' – '.join(x for x in (r['title'], r['description']) if x), r['component'], r['land_ha'], None,
                   None, None if r['table'] == 'Table 8' else r['total_cost_aud'], r['corridor_segment'] or None, None]
    r['rid'] = r['project_id'] + '|' + r['component']
ES = json.loads((ROOT / 'data/reference/export_schema.json').read_text())
write_app(ROOT / 'app/croskell/data.js', dict(
    meta=dict(id='croskell', short='Croskell', colour='#0b7a62', title='Croskell (Employment) ICP – projects', subtitle='Plans 2–4 placed on the ground · Tables 5–8 · October 2025', plan='Croskell (Employment) ICP',
              source='Croskell (Employment) Infrastructure Contributions Plan, October 2025', storage_key='croskell-edits-v1', export_prefix='croskell-projects'),
    maps=[dict(id='plan2', title='Plan 2 · Standard and Supplementary Levy Transport Construction Projects'), dict(id='plan3', title='Plan 3 · Standard Levy Community and Recreation Construction Projects'), dict(id='plan4', title='Plan 4 · Public Land Provision')],
    images=IM, classes=classes, features=feats, rows=rows, tables={k.replace('table', 'Table '): v for k, v in {k: T[k].replace({np.nan: None}).to_dict('records') for k in T}.items()},
    columns=[dict(k='project_id', label='Project ID', t='id'), dict(k='category', label='Category'), dict(k='title', label='Title'), dict(k='description', label='Description', show=False),
             dict(k='component', label='Levy component'), dict(k='table', label='Table', show=False), dict(k='staging', label='Staging', show=False), dict(k='land_ha', label='Land ha', t='num'),
             dict(k='total_cost_aud', label='Total cost', t='money'), dict(k='apportionment_pct', label='Appt. %', t='num', show=False), dict(k='cost_to_icp_aud', label='To ICP', t='money'),
             dict(k='cost_per_ha_aud', label='Cost / ha', t='money', show=False), dict(k='corridor_segment', label='Corridor segment', show=False),
             dict(k='acquired', label='Land acquired', t='edit'), dict(k='status', label='Status', t='edit')],
    detail=[dict(k='component', label='Levy component'), dict(k='table', label='Table'), dict(k='land_ha', label='Public purpose land', t='ha'), dict(k='total_cost_aud', label='Total estimated cost', t='money'),
            dict(k='apportionment_pct', label='Apportioned to ICP', t='pct'), dict(k='cost_to_icp_aud', label='Cost to ICP', t='money'), dict(k='cost_per_ha_aud', label='Cost per ha', t='money'),
            dict(k='staging', label='Staging'), dict(k='funding_source', label='Funding source'), dict(k='footnote', label='Footnote'), dict(k='corridor_segment', label='Corridor segment')],
    totals=[dict(k='total_cost_aud', label='cost', t='money'), dict(k='cost_to_icp_aud', label='to ICP', t='money'), dict(k='land_ha', label='land ha', t='num')],
    export=dict(columns=ES['columns'], widths=ES['widths'], acquired_col=6, status_col=10, note='Land cost is not used: ICP land is provided in kind and equalised per parcel (Table 11).')))
