"""Build gis/edit/casey_fields_blvd.qgz: the editable GeoPackage layers styled as in the app, the printed plan maps
(GeoTIFFs) underneath, Esri imagery, project-ID labels, and each shape layer joined to its projects table so Identify
shows the table values. Paths are relative, so the project works wherever the repository is cloned.
Run with QGIS's Python:  QT_QPA_PLATFORM=offscreen python3.12 tools/build_qgis_project.py  (writes a preview PNG too)."""
import json, pathlib, sys
from qgis.core import (QgsApplication, QgsProject, QgsVectorLayer, QgsRasterLayer, QgsCategorizedSymbolRenderer, QgsRendererCategory,
                       QgsSymbol, QgsWkbTypes, QgsVectorLayerJoinInfo, QgsPalLayerSettings, QgsVectorLayerSimpleLabeling, QgsTextFormat,
                       QgsTextBufferSettings, QgsCoordinateReferenceSystem, QgsMapSettings, QgsMapRendererParallelJob, QgsRectangle,
                       QgsSimpleFillSymbolLayer, QgsLinePatternFillSymbolLayer, QgsFillSymbol, QgsEditorWidgetSetup)
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtCore import QSize, Qt

ROOT = pathlib.Path(__file__).resolve().parents[1]
GPKG = ROOT / 'gis/edit/casey_fields_blvd.gpkg'; OUT = ROOT / 'gis/edit/casey_fields_blvd.qgz'
TIFS = {('croskell', 'plan2'): 'gis/croskell/georeferenced/ICO3_plan2.tif', ('croskell', 'plan3'): 'gis/croskell/georeferenced/ICO3_plan3.tif',
        ('croskell', 'plan4'): 'gis/croskell/georeferenced/ICO3_plan4.tif', ('collison', 'fig3'): 'gis/collison/georeferenced/DCPO22_fig3.tif'}
app = QgsApplication([], False); app.initQgis()
P = QgsProject.instance(); P.clear(); P.setCrs(QgsCoordinateReferenceSystem('EPSG:7855')); P.setFileName(str(OUT))
P.writeEntryBool('Paths', '/Absolute', False)
root = P.layerTreeRoot()
import sqlite3
layers = [r[0] for r in sqlite3.connect(GPKG).execute('select table_name from gpkg_contents order by table_name')]

def symbol_for(c, gtype):
    sym = QgsSymbol.defaultSymbol(gtype)
    col = QColor(c.get('color', '#888888')); out = QColor(c.get('outline', c.get('color', '#333333')))
    if gtype == QgsWkbTypes.PolygonGeometry:
        if c.get('pattern') == 'hatch':
            sym = QgsFillSymbol.createSimple({'color': c['color'], 'outline_color': '#111111', 'outline_width': '0.3'})
            hatch = QgsLinePatternFillSymbolLayer(); hatch.setLineAngle(45); hatch.setDistance(1.5); hatch.setColor(QColor('#111111')); sym.appendSymbolLayer(hatch)
        elif c.get('style') == 'outline':
            sym = QgsFillSymbol.createSimple({'color': '0,0,0,0', 'outline_color': c['color'], 'outline_width': '0.5', 'outline_style': 'dash'})
        else:
            sym = QgsFillSymbol.createSimple({'color': c['color'], 'outline_color': c.get('outline', c['color']), 'outline_width': '0.3'}); sym.setOpacity(0.85)
    elif gtype == QgsWkbTypes.LineGeometry:
        sym.setColor(col); sym.setWidth(max(0.4, c.get('width', 3) * 0.25))
        if c.get('dash'): sym.symbolLayer(0).setPenStyle(Qt.DotLine if c['dash'] == 'dots' else Qt.DashLine)
    else:
        sym.setColor(col); sym.setSize(4)
        sl = sym.symbolLayer(0)
        try: sl.setShape({'ped': 0, 'cu': 6, 'xing': 7, 'star': 9}.get(c.get('icon'), 2) if False else sl.shape())
        except Exception: pass
    return sym

for spec_p in sorted((ROOT / 'data/app').glob('*_spec.json')):
    spec = json.loads(spec_p.read_text(encoding='utf-8')); a = spec['meta']['id']; cls = spec['classes']
    grp = root.addGroup(spec['meta']['plan'])
    tbl = QgsVectorLayer(f'{GPKG}|layername={a}_projects', f'{spec["meta"]["short"]} – project table (edit values here)', 'ogr'); P.addMapLayer(tbl, False); grp.addLayer(tbl)
    for m in spec['maps']:
        mg = grp.addGroup(m['title'])
        for l in [l for l in layers if l.startswith(f'{a}_{m["id"]}_')]:
            vl = QgsVectorLayer(f'{GPKG}|layername={l}', f'{m["title"].split(" · ")[0]} – {l.rsplit("_", 1)[1]}', 'ogr'); P.addMapLayer(vl, False)
            cats = [QgsRendererCategory(k, symbol_for(c, vl.geometryType()), c['label']) for k, c in cls.items() if c.get('map', '') == m['id']]
            vl.setRenderer(QgsCategorizedSymbolRenderer('cls', cats))
            # 'cls' as a drop-down of the legend classes, so new shapes get a valid class
            vl.setEditorWidgetSetup(vl.fields().indexOf('cls'), QgsEditorWidgetSetup('ValueMap', {'map': [{c['label']: k} for k, c in cls.items() if c.get('map', '') == m['id']]}))
            j = QgsVectorLayerJoinInfo(); j.setJoinLayer(tbl); j.setJoinFieldName('project_id'); j.setTargetFieldName('project_id'); j.setUsingMemoryCache(True); j.setPrefix('table_')
            j.setJoinFieldNamesSubset(['title', 'category', 'component', 'land_ha', 'total_cost_aud', 'status']); vl.addJoin(j)
            ls = QgsPalLayerSettings(); ls.fieldName = 'project_id'; ls.enabled = True
            tf = QgsTextFormat(); tf.setSize(8); b = QgsTextBufferSettings(); b.setEnabled(True); b.setSize(1); tf.setBuffer(b); ls.setFormat(tf)
            vl.setLabeling(QgsVectorLayerSimpleLabeling(ls)); vl.setLabelsEnabled(True)
            mg.addLayer(vl)
        tif = TIFS.get((a, m['id']))
        if tif:
            rl = QgsRasterLayer(str(ROOT / tif), f'{m["title"].split(" · ")[0]} as printed'); rl.renderer().setOpacity(0.65); P.addMapLayer(rl, False)
            node = mg.addLayer(rl); node.setItemVisibilityChecked(False)
    for l in [l for l in layers if l.startswith(f'{a}_context_')]:
        vl = QgsVectorLayer(f'{GPKG}|layername={l}', 'Boundary / context', 'ogr'); P.addMapLayer(vl, False)
        vl.setRenderer(QgsCategorizedSymbolRenderer('cls', [QgsRendererCategory(k, QgsFillSymbol.createSimple({'color': '0,0,0,0', 'outline_color': c['color'], 'outline_width': '0.6', 'outline_style': 'dash'}), c['label']) for k, c in cls.items() if not c.get('map')]))
        grp.addLayer(vl)
img = QgsRasterLayer('type=xyz&url=https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/%7Bz%7D/%7By%7D/%7Bx%7D&zmax=19&zmin=0', 'Esri World Imagery', 'wms')
P.addMapLayer(img, False); root.addLayer(img)
P.write()
print('written', OUT.relative_to(ROOT), len(P.mapLayers()), 'layers')
# preview (without the imagery, which this environment cannot reach)
ms = QgsMapSettings(); ms.setLayers([l for l in P.mapLayers().values() if l.name() != 'Esri World Imagery' and l.type() == 0 and 'table' not in l.name()])
ms.setDestinationCrs(P.crs()); ms.setOutputSize(QSize(1400, 1100)); ms.setBackgroundColor(QColor('white'))
ext = QgsRectangle(); [ext.combineExtentWith(l.extent()) for l in ms.layers()]; ext.scale(1.05); ms.setExtent(ext)
job = QgsMapRendererParallelJob(ms); job.start(); job.waitForFinished(); job.renderedImage().save(sys.argv[1] if len(sys.argv) > 1 else '/tmp/qgis_preview.png')
app.exitQgis()
