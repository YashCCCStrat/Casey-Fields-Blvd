"""Check gis/edit/casey_fields_blvd.gpkg before the app is rebuilt from it (run by the GitHub Action; fails on errors).
Errors: wrong coordinate system, a shape whose project_id is not in its area's projects table, unknown legend class,
duplicate row ids. Warnings: invalid geometry (repaired when building), projects without any shape."""
import sys, json, pathlib
import geopandas as gpd, pyogrio
ROOT = pathlib.Path(__file__).resolve().parents[1]; GPKG = ROOT / 'gis/edit/casey_fields_blvd.gpkg'
err, warn = [], []
layers = [l for l, _ in pyogrio.list_layers(GPKG)]
for spec_p in sorted((ROOT / 'data/app').glob('*_spec.json')):
    spec = json.loads(spec_p.read_text(encoding='utf-8')); a = spec['meta']['id']
    if f'{a}_projects' not in layers: err.append(f'{a}: table {a}_projects missing'); continue
    rows = pyogrio.read_dataframe(GPKG, layer=f'{a}_projects', read_geometry=False)
    if rows.rid.duplicated().any(): err.append(f'{a}: duplicate row ids {sorted(rows.rid[rows.rid.duplicated()])}')
    ids = set(rows.project_id); shaped = set()
    for l in [l for l in layers if l.startswith(a + '_') and l != f'{a}_projects']:
        g = gpd.read_file(GPKG, layer=l)
        if g.crs is None or g.crs.to_epsg() != 7855: err.append(f'{l}: coordinate system must be EPSG:7855 (GDA2020 / MGA zone 55), found {g.crs}')
        for i, r in g.iterrows():
            pid = r.get('project_id'); cls = r.get('cls')
            if cls not in spec['classes']: err.append(f'{l} feature {i}: legend class "{cls}" unknown (use one of {sorted(spec["classes"])})')
            if isinstance(pid, str) and pid.strip():
                if pid.strip() not in ids: err.append(f'{l} feature {i}: project_id "{pid}" is not in {a}_projects')
                shaped.add(pid.strip())
            if r.geometry is None or r.geometry.is_empty: warn.append(f'{l} feature {i} ({pid}): no geometry')
            elif not r.geometry.is_valid: warn.append(f'{l} feature {i} ({pid}): invalid geometry (will be repaired)')
    missing = sorted(ids - shaped)
    if missing: warn.append(f'{a}: projects without a shape: {", ".join(missing)}')
for w in warn: print('WARNING', w)
for e in err: print('ERROR  ', e)
print(f'{len(err)} errors, {len(warn)} warnings'); sys.exit(1 if err else 0)
