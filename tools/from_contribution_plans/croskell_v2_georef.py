"""Croskell v2 (standalone, not in run_all): write Plan 2 and Plan 4 of the Croskell ICP (Oct 2025) as GeoTIFFs.

The embedded 300 ppi page images are placed with the affine fitted to the PSP boundary (pipeline/georef_figure.py;
median 2.4 m, 90th percentile 4.6 m). Output: analysis/croskell-gis-v2/georeferenced/ICO3_plan{2,4}.tif (EPSG:7855)."""
import sys, pathlib, json
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent)); import config
import numpy as np, rasterio
from rasterio.transform import Affine
from georef_figure import figure_image

OUT = config.ROOT / 'analysis/croskell-gis-v2/georeferenced'; OUT.mkdir(parents=True, exist_ok=True)
F = json.loads((config.ROOT / 'data/reference/plan_figures/plan_figures.json').read_text())
for key in ('ICO3_plan2', 'ICO3_plan4'):
    f = F[key]; T = np.array(f['affine'])
    a = np.array(figure_image(f))                                   # rows, cols, RGB
    # the fitted affine maps pixel centres (x, y) to metres; GeoTIFF transforms map pixel corners
    tr = Affine(T[0, 0], T[1, 0], T[2, 0], T[0, 1], T[1, 1], T[2, 1]) * Affine.translation(-0.5, -0.5)
    with rasterio.open(OUT / f'{key}.tif', 'w', driver='GTiff', height=a.shape[0], width=a.shape[1], count=3, dtype='uint8',
                       crs='EPSG:7855', transform=tr, compress='jpeg', jpeg_quality=90, photometric='YCBCR', tiled=True) as d:
        for i in range(3): d.write(a[..., i], i + 1)
        d.update_tags(source=f"{f['pdf']} PDF p{f['pdf_page']} (printed p{f['printed_page']})", fit=f.get('fit', ''))
    print(key, a.shape, 'pixel', round(abs(T[0, 0]), 3), 'm', (OUT / f'{key}.tif').stat().st_size // 1024, 'KB')
