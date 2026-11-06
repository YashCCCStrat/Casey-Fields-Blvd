"""Tool (not part of run_all): fit the affine that places a plan figure on the map.

Usage: python pipeline/georef_figure.py <figure key in data/reference/plan_figures/plan_figures.json> [--write]

The figure must show the boundary named by 'fit_to' ("overlay:DCPO22" or "psp:14") as a coloured line; 'boundary' names
the colour rule ('periwinkle': Collison Estate, about RGB 135,133,225; 'navy': VPA PSP boundary, about RGB 32,64,128)
and 'region' (x0, y0, x1, y1) limits the search to the map, away from the figure's legend and title bar. A figure is
either the JPEG embedded on the page ('image_index') or the page rendered at 'render_dpi' (vector maps).
1. Pixels of that colour (right of the figure's own legend) are found. The first affine comes from the stored one, or for
   a new figure from 'seed_corners_px' (the boundary's NW, NE, SE, SW corners read off the image) matched to the
   overlay polygon's corners.
2. Every boundary pixel is then matched to the nearest point on the overlay boundary and the affine re-solved by least
   squares, 15 times (iterative closest point).
Prints the median / 90th percentile distance of the boundary pixels from the overlay boundary. With --write the affine
is stored back in plan_figures.json. Always check the result by drawing OpenStreetMap roads on the figure.
"""
import sys, pathlib, json, subprocess, tempfile
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent)); import config
import numpy as np, geopandas as gpd, shapely
from shapely.ops import nearest_points
from PIL import Image

FIG = config.ROOT / 'data/reference/plan_figures/plan_figures.json'

def figure_image(f):
    """The figure as a PIL image: the JPEG embedded on the PDF page, or the page rendered at render_dpi."""
    with tempfile.TemporaryDirectory() as d:
        if f.get('render_dpi'):
            subprocess.run(['pdftoppm', '-f', str(f['pdf_page']), '-l', str(f['pdf_page']), '-r', str(f['render_dpi']), '-png',
                            str(config.ROOT / f['pdf']), f'{d}/p'], check=True)
            return Image.open(sorted(pathlib.Path(d).glob('p*.png'))[0]).convert('RGB')
        subprocess.run(['pdfimages', '-j', '-f', str(f['pdf_page']), '-l', str(f['pdf_page']), str(config.ROOT / f['pdf']), f'{d}/i'], check=True)
        p = sorted(pathlib.Path(d).glob('i-*'))[f['image_index']]
        return Image.open(p).convert('RGB')

RULES = {
    'periwinkle': lambda r, g, b: (b > 200) & (r > 90) & (r < 175) & (g > 90) & (g < 175) & (b - r > 60) & (abs(r - g) < 25),
    'navy': lambda r, g, b: (b - r > 45) & (b < 150) & (r < 70)}

def boundary_mask(a, f):
    r, g, b = [a[..., i].astype(int) for i in range(3)]
    m = RULES[f.get('boundary', 'periwinkle')](r, g, b)
    x0, y0, x1, y1 = f.get('region', [int(m.shape[1] * 0.30), 0, m.shape[1], m.shape[0]])
    keep = np.zeros_like(m); keep[y0:y1, x0:x1] = True
    return m & keep

def target_ring(spec):
    kind, code = spec.split(':')
    if kind == 'overlay':
        ov = gpd.read_file(config.DERIVED / 'casey_overlays.gpkg'); g = ov[ov.ZONE_CODE == code].geometry.iloc[0]
    else:
        pr = gpd.read_file(config.DERIVED / 'casey_precincts.gpkg'); g = pr[pr.VPA_No.astype(str).str.replace(r'\.0$', '', regex=True) == code].geometry.iloc[0]
    return max(shapely.get_parts(g), key=lambda x: x.area).exterior

def fit(key):
    F = json.loads(FIG.read_text()); f = F[key]
    a = np.array(figure_image(f)); ys, xs = np.nonzero(boundary_mask(a, f)); P = np.c_[xs, ys, np.ones(len(xs))]
    ring = target_ring(f['fit_to'])
    c = np.array(ring.coords)[:, :2]; X, Y = c[:, 0], c[:, 1]
    geo = {'NW': c[np.argmax(Y - X)], 'NE': c[np.argmax(X + Y)], 'SE': c[np.argmax(X - Y)], 'SW': c[np.argmin(X + Y)]}
    if f.get('affine'):
        T = np.array(f['affine'])            # refine the stored fit
    else:                                    # first fit: four boundary corners read off the figure, NW, NE, SE, SW (pixels)
        A = np.array([[*p, 1] for p in f['seed_corners_px']]); B = np.array([geo[k] for k in ('NW', 'NE', 'SE', 'SW')])
        T = np.linalg.lstsq(A, B, rcond=None)[0]
    for tol in [80, 60, 40] + [25] * 12:      # start wide: seed corners read off the figure can be 20-30 m out
        G = P @ T; d = shapely.distance(shapely.points(G), ring); k = np.nonzero(d < tol)[0][::3]
        tgt = np.array([nearest_points(ring, shapely.Point(p))[0].coords[0] for p in G[k]])
        T = np.linalg.lstsq(P[k], tgt, rcond=None)[0]
    d = shapely.distance(shapely.points(P @ T), ring); d = d[d < 25]
    print(f"{key}: {len(d)} boundary pixels, median {np.median(d):.1f} m, 90th percentile {np.percentile(d, 90):.1f} m; "
          f"scale {np.hypot(*T[0]):.3f} m/px, rotation {np.degrees(np.arctan2(T[0, 1], T[0, 0])):.2f}°")
    if '--write' in sys.argv:
        f['affine'] = T.tolist(); FIG.write_text(json.dumps(F, indent=1)); print('written to', FIG)

if __name__ == '__main__':
    fit(sys.argv[1])
