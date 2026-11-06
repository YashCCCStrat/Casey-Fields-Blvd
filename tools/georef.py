"""Place a plan map on the ground and write it as a GeoTIFF.

Usage: python tools/georef.py <figure key in data/reference/plan_figures.json> [--write]
The plan's own PSP boundary line (navy dashed) is picked out by colour and matched to the VPA PSP boundary
(gis/corridor/vpa_precincts_casey.gpkg) by iterative closest point, starting from the stored affine. Prints the fit
(median / 90th percentile distance of the boundary pixels from the VPA boundary). With --write the affine is stored and
gis/croskell/georeferenced/<key>.tif is written (EPSG:7855, 1.27 m pixels for the 300 ppi Croskell maps)."""
import sys, json, pathlib, subprocess, tempfile
import numpy as np, geopandas as gpd, shapely, rasterio
from shapely.ops import nearest_points
from rasterio.transform import Affine
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
FIG = ROOT / 'data/reference/plan_figures.json'

def figure_image(f):
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(['pdfimages', '-j', '-f', str(f['pdf_page']), '-l', str(f['pdf_page']), str(ROOT / f['pdf']), f'{d}/i'], check=True)
        return Image.open(sorted(pathlib.Path(d).glob('i-*'))[f['image_index']]).convert('RGB')

def boundary_mask(a, f):
    r, g, b = [a[..., i].astype(int) for i in range(3)]
    if f.get('boundary') == 'periwinkle':                         # Collison Estate: light blue-violet precinct boundary
        m = (b > 200) & (r > 90) & (r < 175) & (g > 90) & (g < 175) & (b - r > 60) & (abs(r - g) < 25)
    else:
        m = (b - r > 45) & (b < 150) & (r < 70)                  # navy dashed PSP boundary
    x0, y0, x1, y1 = f['region']; keep = np.zeros_like(m); keep[y0:y1, x0:x1] = True
    return m & keep

def fit(key, write=False):
    F = json.loads(FIG.read_text()); f = F[key]
    im = figure_image(f); a = np.array(im); ys, xs = np.nonzero(boundary_mask(a, f)); P = np.c_[xs, ys, np.ones(len(xs))]
    kind, code = f['fit_to'].split(':')
    if kind == 'overlay':
        ov = gpd.read_file(ROOT / 'gis/corridor/contribution_overlays_casey.gpkg'); geom = ov[ov.ZONE_CODE == code].geometry.iloc[0]
    else:
        pr = gpd.read_file(ROOT / 'gis/corridor/vpa_precincts_casey.gpkg'); geom = pr[pr.VPA_No == code].geometry.iloc[0]
    ring = max(shapely.get_parts(geom), key=lambda x: x.area).exterior
    T = np.array(f['affine'])
    for tol in [80, 60, 40] + [25] * 12:
        G = P @ T; d = shapely.distance(shapely.points(G), ring); k = np.nonzero(d < tol)[0][::3]
        T = np.linalg.lstsq(P[k], np.array([nearest_points(ring, shapely.Point(p))[0].coords[0] for p in G[k]]), rcond=None)[0]
    d = shapely.distance(shapely.points(P @ T), ring); d = d[d < 25]
    f['fit'] = f'boundary pixels: median {np.median(d):.1f} m, 90th percentile {np.percentile(d, 90):.1f} m from the {"DCPO22 overlay" if kind == "overlay" else "VPA PSP"} boundary ({len(d)} px)'
    print(key, f['fit'], f'; {np.hypot(*T[0]):.3f} m/px')
    if write:
        f['affine'] = T.tolist(); FIG.write_text(json.dumps(F, indent=1))
        out = ROOT / ('gis/collison/georeferenced' if 'DCPO22' in key else 'gis/croskell/georeferenced'); out.mkdir(parents=True, exist_ok=True)
        tr = Affine(T[0, 0], T[1, 0], T[2, 0], T[0, 1], T[1, 1], T[2, 1]) * Affine.translation(-0.5, -0.5)   # pixel centre -> corner
        with rasterio.open(out / f'{key}.tif', 'w', driver='GTiff', height=a.shape[0], width=a.shape[1], count=3, dtype='uint8', crs='EPSG:7855',
                           transform=tr, compress='jpeg', jpeg_quality=90, photometric='YCBCR', tiled=True) as dst:
            for i in range(3): dst.write(a[..., i], i + 1)
            dst.update_tags(title=f['title'], source=f"{f['pdf']} PDF p{f['pdf_page']} (printed p{f['printed_page']})", fit=f['fit'])

if __name__ == '__main__':
    fit(sys.argv[1], '--write' in sys.argv)
