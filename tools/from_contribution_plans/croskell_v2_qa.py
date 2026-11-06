"""Croskell v2: draw the extracted layers over the georeferenced plans (analysis/croskell-gis-v2/qa_*.png)."""
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent)); import config
import rasterio, numpy as np, geopandas as gpd, shapely
from PIL import Image, ImageDraw, ImageFont
O = config.ROOT / 'analysis/croskell-gis-v2'; F = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 26)
for plan, layers in [('ICO3_plan4', ['croskell_plan4_land_as_drawn']), ('ICO3_plan2', ['croskell_plan2_construction_as_drawn', 'croskell_plan2_other_symbols'])]:
    d = rasterio.open(O / f'georeferenced/{plan}.tif'); a = np.dstack([d.read(i) for i in (1, 2, 3)]); inv = ~d.transform
    im = Image.fromarray((a * 0.55 + 110).astype(np.uint8)); dr = ImageDraw.Draw(im)
    for L in layers:
        for r in gpd.read_file(O / 'croskell_gis_v2.gpkg', layer=L).itertuples():
            col = (0, 70, 255) if 'v1' in str(r.method) else (120, 120, 120) if L.endswith('other_symbols') else (230, 0, 0)
            for g in shapely.get_parts(r.geometry):
                if g.geom_type == 'Polygon': dr.polygon([inv * xy for xy in g.exterior.coords], outline=col, width=5)
                elif g.geom_type == 'LineString': dr.line([inv * xy for xy in g.coords], fill=col, width=7)
                else: x, y = inv * (g.x, g.y); dr.ellipse([x - 16, y - 16, x + 16, y + 16], outline=col, width=6)
            if getattr(r, 'proj_id', None):
                q = r.geometry.representative_point(); x, y = inv * (q.x, q.y)
                dr.text((x + 18, y - 34), r.proj_id.replace('CK-', ''), fill=(0, 0, 0), font=F, stroke_width=3, stroke_fill=(255, 255, 255))
    im.crop((300, 250, 3450, 2250)).resize((1575, 1000)).save(O / f'qa_{plan}.png')
