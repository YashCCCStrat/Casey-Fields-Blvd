/* Contribution plans viewer: several plan areas on one map, linked to one table of their projects.
   Data: window.PLANS (each built by tools/build_*.py via tools/appdata.write_app). Libraries: MapLibre GL JS, SheetJS. */
'use strict';
(() => {
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
const money = v => v == null || v === '' ? '' : '$' + Math.round(v).toLocaleString('en-AU');
const fmtv = (v, t) => v == null || v === '' ? '' : t === 'money' ? money(v) : t === 'num' ? (+v).toLocaleString('en-AU', {maximumFractionDigits: 4}) : t === 'ha' ? v + ' ha' : t === 'm' ? v + ' m' : t === 'pct' ? v + '%' : v;
const store = {get: (k, d) => { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch (e) { return d; } }, set: (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} }};

// ---------- merge the plan areas (ids prefixed with the area) ----------
const PL = window.PLANS || [];
const AREAS = PL.map(P => ({id: P.meta.id, name: P.meta.plan, short: P.meta.short, colour: P.meta.colour, source: P.meta.source, note: P.export.note}));
const D = {maps: [], images: {}, classes: {}, features: [], rows: [], tables: {}, columns: [], detail: {}, totals: [], export: PL[0].export};
const addUnique = (arr, items) => items.forEach(c => { if (!arr.some(x => x.k === c.k)) arr.push(c); });
for (const P of PL) {
  const a = P.meta.id, pre = x => x ? a + ':' + x : '';
  P.maps.forEach(m => D.maps.push({...m, id: pre(m.id), area: a}));
  Object.entries(P.images).forEach(([k, v]) => D.images[pre(k)] = v);
  Object.entries(P.classes).forEach(([k, c]) => D.classes[pre(k)] = {...c, map: pre(c.map), area: a});
  P.features.forEach(f => D.features.push({...f, properties: {...f.properties, cls: pre(f.properties.cls), map: pre(f.properties.map), area: a, ...(f.properties.key ? {key: a + ':' + f.properties.key.split('|')[0] + '|' + pre(f.properties.key.split('|')[1])} : {})}}));
  P.rows.forEach(r => D.rows.push({...r, rid: a + ':' + r.rid, map: pre(r.map), area: a, area_name: P.meta.short}));
  Object.entries(P.tables || {}).forEach(([k, t]) => D.tables[P.meta.short + ' ' + k] = t);
  addUnique(D.columns, P.columns); D.detail[a] = P.detail; addUnique(D.totals, (P.totals || []).map(t => t.k === 'total_cost_aud' ? {...t, label: 'total cost'} : t));
}
D.columns.splice(1, 0, {k: 'area_name', label: 'Plan area'});
D.columns.sort((x, y) => (x.t === 'edit') - (y.t === 'edit'));   // Land acquired and Status last
const AREA = Object.fromEntries(AREAS.map(x => [x.id, x]));
const SK = 'casey-fields-blvd-edits-v1';
let EDITS = store.get(SK, null);
if (!EDITS) { EDITS = {}; PL.forEach(P => Object.entries(store.get(P.meta.storage_key, {})).forEach(([k, v]) => EDITS[P.meta.id + ':' + k] = v)); }   // carry over earlier per-plan edits
const ROWS = D.rows.map(r => ({...r, key: r.area + ':' + r.project_id + '|' + r.map}));
const val = (r, k) => k === 'acquired' ? (EDITS[r.rid]?.acquired ?? '') : k === 'status' ? (EDITS[r.rid]?.status ?? r.status ?? '') : r[k];
D.features.forEach((f, i) => { f.id = i; });
const FBYKEY = {}; D.features.forEach(f => { if (f.properties.key) (FBYKEY[f.properties.key] ??= []).push(f); });
const rowsFor = key => ROWS.filter(r => r.key === key);
const CLS = D.classes, clsOfKey = k => (FBYKEY[k] || [])[0]?.properties.cls;
const colorOf = r => CLS[clsOfKey(r.key)]?.color || '#888';
const AON = new Set(store.get('cfb-areas', AREAS.map(a => a.id)).filter(a => AREA[a]));
if (!AON.size) AREAS.forEach(a => AON.add(a.id));
const IMGON = new Set();                                   // plan maps shown as printed (image)
const MAPON = new Set(D.maps.map(m => m.id));              // plans switched on: their legend items and rows

// ---------- page ----------
document.title = 'Casey Fields Boulevard Plans';
document.body.innerHTML = `
<header class="top"><div class="brand"><div class="logo"></div><div><h1>Casey Fields Boulevard – contribution plans</h1><p>Plan maps placed on the ground, linked to each plan's project tables</p></div></div>
  <div class="areas" id="areas"></div><div class="sp"></div>
  <button class="btn" id="bImp" title="Load Land acquired / Status back from an exported file">Import edits</button><input type="file" id="fImp" accept=".xlsx" hidden>
  <button class="btn primary" id="bExp">Export to Excel</button></header>
<div id="wrap">
  <div id="map">
    <aside id="panel" class="card"><div class="hd" id="phd"><span>Plan maps &amp; layers</span><span class="chev">▾</span></div><div class="bd">
      <div class="row" style="margin-top:8px"><span class="muted" style="width:70px">Basemap</span><select id="base" style="flex:1"><option value="imagery">Imagery</option><option value="streets">Streets</option><option value="none">None</option></select></div>
      <div class="row" style="margin-top:8px"><span class="muted" style="width:70px" title="Transparency of the printed plans: 0% = solid, 100% = invisible">Transparency</span><input type="range" id="opac" min="0" max="95" value="35"><span id="opacV" style="width:34px;text-align:right">35%</span></div>
      <div id="lyr"></div>
      <label class="lyr" style="margin-top:8px"><input type="checkbox" id="lblOn" checked> Project ID labels</label>
    </div></aside>
    <aside id="detail" class="card hidden"></aside>
  </div>
  <div id="resizer" title="Drag to resize"></div>
  <section id="bottom">
    <div class="toolbar">
      <div class="search">🔎<input id="q" placeholder="Project ID (e.g. IN02)"></div>
      <select id="mapF" title="Show the projects of one plan map"><option value="">All plan maps</option></select>
      <div class="chips" id="chips"></div>
      <div class="brk"></div>
      <label class="toggle"><input type="checkbox" id="fView"> only projects in map view</label>
      <button class="btn" id="bClear">Reset</button>
      <span class="summary" id="summary"></span>
      <div class="pop" id="colPop"><button class="btn" id="bCols">Columns ▾</button><div class="menu" id="colMenu"></div></div>
      <button class="btn" id="bExpF">Export shown rows</button>
    </div>
    <div id="tablewrap"><table><thead id="th"></thead><tbody id="tb"></tbody></table></div>
  </section>
</div>`;

// ---------- map ----------
const b64 = s => Uint8Array.from(atob(s), c => c.charCodeAt(0)).buffer;
maplibregl.addProtocol('glyphs', async p => { const k = p.url.split('/').pop().replace('.pbf', ''); return {data: window.GLYPHS?.[k] ? b64(window.GLYPHS[k]) : new ArrayBuffer(0)}; });
const ESRI = n => `https://server.arcgisonline.com/ArcGIS/rest/services/${n}/MapServer/tile/{z}/{y}/{x}`;
const map = new maplibregl.Map({container: 'map', attributionControl: {compact: true}, center: [145.33, -38.10], zoom: 13.5, maxZoom: 19,
  style: {version: 8, glyphs: 'glyphs://{fontstack}/{range}', sources: {
    imagery: {type: 'raster', tiles: [ESRI('World_Imagery')], tileSize: 256, maxzoom: 19, attribution: 'Esri World Imagery'},
    streets: {type: 'raster', tiles: [ESRI('World_Street_Map')], tileSize: 256, maxzoom: 19, attribution: 'Esri, © OpenStreetMap contributors'}},
    layers: [{id: 'bg', type: 'background', paint: {'background-color': '#eef0ec'}}, {id: 'imagery', type: 'raster', source: 'imagery'}, {id: 'streets', type: 'raster', source: 'streets', layout: {visibility: 'none'}}]}});
map.addControl(new maplibregl.NavigationControl({showCompass: false}), 'top-right');
map.addControl(new maplibregl.ScaleControl({unit: 'metric'}), 'bottom-right');
const canvasImage = (draw, w = 28, h = 28) => { const c = document.createElement('canvas'); c.width = w; c.height = h; draw(c.getContext('2d'), w, h); return c.getContext('2d').getImageData(0, 0, w, h); };
const ICONS = {   // plan-legend symbols: [draw, w, h, legend svg]
  cu: [x => { x.strokeStyle = '#111'; x.lineWidth = 3.2; x.lineCap = 'round'; x.lineJoin = 'round'; x.beginPath(); x.moveTo(3, 7); x.lineTo(10, 13); x.lineTo(30, 13); x.lineTo(37, 7); x.moveTo(3, 27); x.lineTo(10, 21); x.lineTo(30, 21); x.lineTo(37, 27); x.stroke(); }, 40, 34,
       '<svg width="22" height="16" viewBox="0 0 40 34"><path d="M3 7L10 13H30L37 7M3 27L10 21H30L37 27" stroke="#111" stroke-width="3.2" fill="none" stroke-linecap="round"/></svg>'],
  ped: [x => { x.fillStyle = '#fff'; x.fillRect(5, 5, 18, 18); x.fillStyle = '#a5a831'; x.fillRect(7, 7, 14, 14); x.fillStyle = '#fff'; x.fillRect(11, 11, 6, 6); }, 28, 28,
        '<svg width="16" height="16" viewBox="0 0 28 28"><rect x="5" y="5" width="18" height="18" fill="#a5a831"/><rect x="11" y="11" width="6" height="6" fill="#fff"/></svg>'],
  xing: [x => { x.strokeStyle = '#fff'; x.lineWidth = 9; x.beginPath(); x.moveTo(6, 6); x.lineTo(24, 24); x.moveTo(24, 6); x.lineTo(6, 24); x.stroke(); x.strokeStyle = '#f7941d'; x.lineWidth = 5; x.beginPath(); x.moveTo(7, 7); x.lineTo(23, 23); x.moveTo(23, 7); x.lineTo(7, 23); x.stroke(); }, 30, 30,
         '<svg width="16" height="16" viewBox="0 0 30 30"><path d="M6 6L24 24M24 6L6 24" stroke="#fff" stroke-width="9"/><path d="M7 7L23 23M23 7L7 23" stroke="#f7941d" stroke-width="5"/></svg>'],
  star: [x => { x.strokeStyle = '#e2dd23'; x.lineWidth = 5; x.lineCap = 'round'; x.beginPath(); for (let i = 0; i < 4; i++) { const a = i * Math.PI / 4; x.moveTo(17 + 13 * Math.cos(a), 17 + 13 * Math.sin(a)); x.lineTo(17 - 13 * Math.cos(a), 17 - 13 * Math.sin(a)); } x.stroke(); }, 34, 34,
         '<svg width="16" height="16" viewBox="0 0 34 34"><path d="M30 17H4M26 26L8 8M17 30V4M26 8L8 26" stroke="#e2dd23" stroke-width="5" stroke-linecap="round"/></svg>']};
const DASH = {dots: [0.1, 2], dash: [2, 1.4], long: [3, 2]};
function swatch(c) {
  if (c.kind === 'point') return ICONS[c.icon]?.[3] || `<svg width="14" height="14"><circle cx="7" cy="7" r="5" fill="${c.color}"/></svg>`;
  if (c.kind === 'line') { const da = c.dash === 'dots' ? 'stroke-dasharray="0.1 5" stroke-linecap="round"' : c.dash ? 'stroke-dasharray="5 3"' : '';
    return `<svg width="26" height="12"><path d="M2 6H24" stroke="${c.color}" stroke-width="${c.dash === 'dots' ? 4 : 3}" ${da}/>${c.arrow ? `<path d="M19 2L24 6L19 10" stroke="${c.color}" stroke-width="2" fill="none"/>` : ''}</svg>`; }
  const bg = c.pattern === 'hatch' ? `repeating-linear-gradient(135deg,${c.color} 0 4px,#111 4px 6px)` : c.color;
  return `<span style="display:block;width:24px;height:14px;border-radius:3px;background:${bg};border:1.5px solid ${c.outline || c.color}${c.style === 'outline' ? ';background:transparent;border-style:dashed' : ''}"></span>${c.icon ? `<span style="margin-left:-20px">${ICONS[c.icon][3]}</span>` : ''}`;
}
const VIS = Object.fromEntries(Object.entries(CLS).map(([k, c]) => [k, c.on !== false]));
let READY = false, SEL = null, HOV = null;
const LIDS = [];   // [layer id, class]
map.on('load', () => {
  map.addSource('f', {type: 'geojson', data: {type: 'FeatureCollection', features: D.features}});
  for (const [k, im] of Object.entries(D.images)) { map.addSource('img-' + k, {type: 'image', url: im.img, coordinates: im.coords}); map.addLayer({id: 'img-' + k, type: 'raster', source: 'img-' + k, layout: {visibility: 'none'}, paint: {'raster-opacity': .65, 'raster-fade-duration': 0}}); }
  for (const [k, [draw, w, h]] of Object.entries(ICONS)) map.addImage(k, canvasImage(draw, w, h));
  const hov = ['boolean', ['feature-state', 'hover'], false], sel = ['boolean', ['feature-state', 'sel'], false], is = c => ['==', ['get', 'cls'], c];
  const hl = (n, h) => ['case', sel, h + 2, hov, h, n], hc = base => ['case', sel, '#ffb000', hov, '#2f7fbf', base];
  const rank = {fill: 0, line: 1, point: 2};
  for (const [k, c] of Object.entries(CLS).sort((a, b) => rank[a[1].kind] - rank[b[1].kind])) {
    const add = l => { map.addLayer(l); LIDS.push([l.id, k]); };
    if (c.kind === 'fill') {
      if (c.pattern === 'hatch') map.addImage('hatch-' + k, canvasImage((x, w, h) => { x.fillStyle = c.color; x.globalAlpha = .7; x.fillRect(0, 0, w, h); x.globalAlpha = 1; x.strokeStyle = '#111'; x.lineWidth = 3; for (let i = -h; i < w; i += 9) { x.beginPath(); x.moveTo(i, h); x.lineTo(i + h, 0); x.stroke(); } }, 18, 18));
      if (c.style !== 'outline') add({id: 'c-' + k, type: 'fill', source: 'f', filter: is(k), paint: c.pattern === 'hatch' ? {'fill-pattern': 'hatch-' + k} : {'fill-color': c.color, 'fill-opacity': ['case', sel, .95, hov, .9, .78]}});
      add({id: 'c-' + k + '-o', type: 'line', source: 'f', filter: is(k), paint: {'line-color': hc(c.outline || c.color), 'line-width': hl(c.style === 'outline' ? 2 : .8, 3.5), ...(c.style === 'outline' ? {'line-dasharray': [2, 1]} : {})}});
    } else if (c.kind === 'line') {
      add({id: 'c-' + k + '-h', type: 'line', source: 'f', filter: is(k), layout: {'line-cap': 'round', 'line-join': 'round'}, paint: {'line-color': ['case', sel, '#ffb000', '#2f7fbf'], 'line-width': (c.width || 3) + 8, 'line-opacity': ['case', sel, .9, hov, .7, 0]}});
      add({id: 'c-' + k, type: 'line', source: 'f', filter: is(k), layout: {'line-cap': c.dash === 'dots' ? 'round' : 'butt', 'line-join': 'round'}, paint: {'line-color': c.color, 'line-width': c.width || 3, ...(c.dash ? {'line-dasharray': DASH[c.dash]} : {})}});
    } else {
      add({id: 'c-' + k + '-h', type: 'circle', source: 'f', filter: is(k), paint: {'circle-radius': 17, 'circle-color': 'rgba(0,0,0,0)', 'circle-stroke-width': ['case', sel, 3, hov, 3, 0], 'circle-stroke-color': ['case', sel, '#ffb000', '#2f7fbf']}});
      add({id: 'c-' + k, type: 'symbol', source: 'f', filter: is(k), layout: {'icon-image': c.icon || 'xing', 'icon-allow-overlap': true, 'icon-rotate': ['coalesce', ['get', 'rot'], 0], 'icon-rotation-alignment': 'map', 'icon-size': ['interpolate', ['linear'], ['zoom'], 13, .7, 16, 1.1, 18, 2]}});
    }
    if (c.icon && c.kind === 'fill') add({id: 'c-' + k + '-i', type: 'symbol', source: 'f', filter: is(k), layout: {'icon-image': c.icon, 'icon-allow-overlap': true}});
  }
  map.addLayer({id: 'labels', type: 'symbol', source: 'f', filter: ['has', 'project_id'], layout: {'text-field': ['get', 'project_id'], 'text-font': ['Noto Sans Regular'], 'text-size': 11, 'text-offset': [0, 1.3], 'text-padding': 3}, paint: {'text-color': '#17222b', 'text-halo-color': '#fff', 'text-halo-width': 2}});
  READY = true; applyVis(); fitAll();
  const pickable = () => LIDS.filter(([id, k]) => !CLS[k].context && map.getLayoutProperty(id, 'visibility') !== 'none' && !id.endsWith('-i')).map(([id]) => id);
  const tip = new maplibregl.Popup({closeButton: false, closeOnClick: false, offset: 14, maxWidth: '320px'});
  map.on('mousemove', e => {
    const f = map.queryRenderedFeatures(e.point, {layers: pickable()}).find(x => x.properties.key);
    const k = f?.properties.key || null; map.getCanvas().style.cursor = k ? 'pointer' : '';
    if (k !== HOV) setHover(k);
    if (k) { const rs = rowsFor(k); tip.setLngLat(e.lngLat).setHTML(`<b>${esc(rs[0]?.project_id)}</b> · ${esc(rs[0]?.title || '')}<div style="color:var(--muted)">${esc(rs[0]?.area_name)}</div>${rs.map(r => `<div style="color:var(--muted)">${esc(r.component)}${r.total_cost_aud ? ' · ' + money(r.total_cost_aud) : r.land_ha ? ' · ' + r.land_ha + ' ha' : ''}</div>`).join('')}`).addTo(map); }
    else tip.remove();
  });
  map.on('mouseout', () => { setHover(null); tip.remove(); });
  map.on('click', e => { const f = map.queryRenderedFeatures(e.point, {layers: pickable()}).find(x => x.properties.key); select(f ? f.properties.key : null, {zoom: false, scroll: true}); });
  map.on('moveend', () => { if ($('fView').checked) render(); });
});
const vis = (id, on) => map.getLayer(id) && map.setLayoutProperty(id, 'visibility', on ? 'visible' : 'none');
const classShown = k => VIS[k] && AON.has(CLS[k].area) && (!CLS[k].map || MAPON.has(CLS[k].map));
function applyVis() {
  if (READY) { LIDS.forEach(([id, k]) => vis(id, classShown(k))); Object.keys(D.images).forEach(m => vis('img-' + m, IMGON.has(m) && MAPON.has(m) && AON.has(m.split(':')[0]))); vis('labels', $('lblOn').checked); }
  buildAreas(); buildLayerList(); buildMapFilter(); buildChips(); render();
}
// plan-area switches in the header
function buildAreas() {
  $('areas').innerHTML = AREAS.map(a => { const n = ROWS.filter(r => r.area === a.id).length;
    return `<button class="area ${AON.has(a.id) ? 'on' : ''}" data-a="${a.id}" title="Show / hide ${esc(a.name)} (${n} rows: one per project and levy component)"><span class="tick" style="--c:${a.colour}">${AON.has(a.id) ? '✓' : ''}</span>${esc(a.name)}<span class="n">${n}</span></button>`; }).join('');
  $('areas').querySelectorAll('.area').forEach(b => b.onclick = () => { const a = b.dataset.a; AON.has(a) ? AON.delete(a) : AON.add(a); store.set('cfb-areas', [...AON]);
    if (SEL && !AON.has(SEL.split(':')[0])) select(null); applyVis(); fitAll(); });
}
function buildLayerList() {
  const count = k => new Set(D.features.filter(f => f.properties.cls === k && f.properties.key).map(f => f.properties.key)).size;
  const row = k => `<div class="lyr ${VIS[k] ? '' : 'off'} ${CLS[k].map && !MAPON.has(CLS[k].map) ? 'dis' : ''}" data-k="${k}"><span class="sw">${swatch(CLS[k])}</span><span>${esc(CLS[k].label)}</span>${count(k) ? `<span class="n">${count(k)}</span>` : ''}</div>`;
  $('lyr').innerHTML = AREAS.filter(a => AON.has(a.id)).map(a => `<div class="areahd"><span class="dot" style="background:${a.colour}"></span>${esc(a.name)}</div>` +
    D.maps.filter(m => m.area === a.id).map(m => `<div class="maphd"><label class="pm" title="Switch this plan's projects on or off (map and table)"><input type="checkbox" data-m="${m.id}" ${MAPON.has(m.id) ? 'checked' : ''}><span>${esc(m.title)}</span></label>${D.images[m.id] && MAPON.has(m.id) ? `<button class="printed ${IMGON.has(m.id) ? 'on' : ''}" data-i="${m.id}" title="Show the plan as printed, placed on the ground">🗺 ${IMGON.has(m.id) ? 'Hide' : 'Show'} printed plan</button>` : ''}${IMGON.has(m.id) && MAPON.has(m.id) ? `<div class="fit">${esc(D.images[m.id].fit.replace('boundary pixels: ', 'Placed by its boundary: ').replace(/ \(\d+ px\)/, ''))}</div>` : ''}</div>` +
      Object.keys(CLS).filter(k => CLS[k].map === m.id).map(row).join('')).join('') +
    Object.keys(CLS).filter(k => CLS[k].area === a.id && !CLS[k].map).map(row).join('')).join('') || '<div class="fit">Turn on a plan area at the top.</div>';
  $('lyr').querySelectorAll('.lyr:not(.dis)').forEach(el => el.onclick = () => { VIS[el.dataset.k] = !VIS[el.dataset.k]; applyVis(); });
  $('lyr').querySelectorAll('.printed').forEach(b => b.onclick = () => { const m = b.dataset.i; IMGON.has(m) ? IMGON.delete(m) : IMGON.add(m); applyVis(); });
  $('lyr').querySelectorAll('.pm input').forEach(cb => cb.onchange = () => { cb.checked ? MAPON.add(cb.dataset.m) : MAPON.delete(cb.dataset.m);
    if (SEL && !MAPON.has(SEL.split('|')[1])) select(null); applyVis(); });
}
function buildMapFilter() {
  const v = $('mapF').value;
  $('mapF').innerHTML = '<option value="">All plan maps</option>' + D.maps.filter(m => AON.has(m.area) && MAPON.has(m.id)).map(m => `<option value="${m.id}">${esc(AREA[m.area].short)} · ${esc(m.title)}</option>`).join('');
  $('mapF').value = [...$('mapF').options].some(o => o.value === v) ? v : '';
}
$('lblOn').onchange = applyVis;
$('phd').onclick = () => $('panel').classList.toggle('closed');
$('opac').oninput = e => { $('opacV').textContent = e.target.value + '%'; Object.keys(D.images).forEach(m => map.setPaintProperty('img-' + m, 'raster-opacity', 1 - e.target.value / 100)); };
$('base').onchange = e => { vis('imagery', e.target.value === 'imagery'); vis('streets', e.target.value === 'streets'); };
function bboxOf(fs) { let b = [180, 90, -180, -90]; const w = c => typeof c[0] === 'number' ? (b = [Math.min(b[0], c[0]), Math.min(b[1], c[1]), Math.max(b[2], c[0]), Math.max(b[3], c[1])]) : c.forEach(w); fs.forEach(f => w(f.geometry.coordinates)); return b; }
function fitAll() { if (!READY) return; const fs = D.features.filter(f => f.properties.key && AON.has(f.properties.area)); if (!fs.length) return; const b = bboxOf(fs); map.fitBounds([[b[0], b[1]], [b[2], b[3]]], {padding: {top: 40, bottom: 40, left: 320, right: 60}, duration: 500}); }

// ---------- selection ----------
const setState = (key, st, on) => (FBYKEY[key] || []).forEach(f => map.setFeatureState({source: 'f', id: f.id}, {[st]: on}));
function setHover(key) {
  if (HOV) setState(HOV, 'hover', false); HOV = key; if (key) setState(key, 'hover', true);
  document.querySelectorAll('#tb tr').forEach(tr => tr.classList.toggle('hov', !!key && tr.dataset.key === key));
}
function select(key, {zoom = true, scroll = false} = {}) {
  if (SEL) setState(SEL, 'sel', false); SEL = key; if (key) setState(key, 'sel', true);
  document.querySelectorAll('#tb tr').forEach(tr => tr.classList.toggle('sel', !!key && tr.dataset.key === key));
  if (!key) { $('detail').classList.add('hidden'); return; }
  const k = clsOfKey(key); if (k && !VIS[k]) { VIS[k] = true; applyVis(); }
  showDetail(key);
  const tr = document.querySelector(`#tb tr[data-key="${CSS.escape(key)}"]`); if (scroll && tr) tr.scrollIntoView({block: 'nearest', behavior: 'smooth'});
  const fs = FBYKEY[key] || []; if (zoom && fs.length) { const b = bboxOf(fs); map.fitBounds([[b[0], b[1]], [b[2], b[3]]], {padding: {top: 80, bottom: 80, left: 340, right: 420}, maxZoom: 17.5, duration: 700}); }
}
function showDetail(key) {
  const rs = rowsFor(key); if (!rs.length) return; const r = rs[0], c = CLS[clsOfKey(key)] || {}, light = ['#ffdf87', '#e2dd23', '#f7941d'].includes(c.color);
  const m = D.maps.find(x => x.id === r.map);
  $('detail').innerHTML = `<button class="x" id="dx" title="Close">✕</button><div class="dar"><span class="dot" style="background:${AREA[r.area].colour}"></span>${esc(AREA[r.area].name)}</div>
    <span class="pid" style="background:${c.color || '#555'};${light ? 'color:#222' : ''}">${esc(r.project_id)}</span> <span class="tag">${esc(r.category)}</span>
    <h2>${esc(r.title)}</h2><div class="desc">${esc(r.description || '')}</div>` +
    rs.map(x => `<dl>${D.detail[x.area].map(f => { const v = x[f.k]; return v == null || v === '' ? '' : `<dt>${esc(f.label)}</dt><dd>${esc(fmtv(v, f.t))}</dd>`; }).join('')}
      <dt>Land acquired</dt><dd>${esc(val(x, 'acquired')) || '<span style="color:var(--muted)">–</span>'}</dd><dt>Status</dt><dd style="text-align:left">${esc(val(x, 'status'))}</dd></dl>`).join('') +
    `<div class="actions"><button class="btn" id="dz">Zoom to</button>${m && D.images[m.id] ? `<button class="btn" id="dm">${IMGON.has(m.id) ? 'Hide' : 'Show'} plan map</button>` : ''}</div>
    <div class="fit" style="margin-top:8px">${esc(m ? m.title : '')}${(FBYKEY[key] || []).length ? '' : ' · not drawn on the plan map'}</div>`;
  $('detail').classList.remove('hidden'); $('dx').onclick = () => select(null); $('dz').onclick = () => select(key, {zoom: true});
  if ($('dm')) $('dm').onclick = () => { IMGON.has(m.id) ? IMGON.delete(m.id) : IMGON.add(m.id); MAPON.add(m.id); applyVis(); showDetail(key); };
}

// ---------- table, filters, columns ----------
const COLS = D.columns.map(c => ({...c, show: store.get('cfb-cols', null)?.[c.k] ?? (c.show !== false)}));
let CATON = new Set();
function buildChips() {
  const cats = [...new Set(ROWS.filter(r => AON.has(r.area)).map(r => r.category))];
  CATON = new Set([...CATON].filter(c => cats.includes(c)));
  $('chips').innerHTML = cats.map(c => `<button class="chip ${CATON.has(c) ? 'on' : ''}" data-c="${esc(c)}"><span class="dot" style="background:${colorOf(ROWS.find(x => x.category === c && AON.has(x.area)))}"></span>${esc(c)}</button>`).join('');
  $('chips').querySelectorAll('.chip').forEach(b => b.onclick = () => { const c = b.dataset.c; CATON.has(c) ? CATON.delete(c) : CATON.add(c); b.classList.toggle('on'); render(); });
}
function colMenu() {
  $('colMenu').innerHTML = COLS.map((c, i) => `<label><input type="checkbox" data-i="${i}" ${c.show ? 'checked' : ''}> ${esc(c.label)}</label>`).join('');
  $('colMenu').querySelectorAll('input').forEach(cb => cb.onchange = () => { COLS[cb.dataset.i].show = cb.checked; store.set('cfb-cols', Object.fromEntries(COLS.map(c => [c.k, c.show]))); render(); });
}
$('bCols').onclick = e => { e.stopPropagation(); colMenu(); const r = $('bCols').getBoundingClientRect(), m = $('colMenu'); m.style.top = (r.bottom + 6) + 'px'; m.style.left = Math.min(r.left, window.innerWidth - 236) + 'px'; m.style.maxHeight = (window.innerHeight - r.bottom - 20) + 'px'; $('colPop').classList.toggle('open'); };
document.addEventListener('click', e => { if (!$('colPop').contains(e.target)) $('colPop').classList.remove('open'); });
let SORT = {k: null, dir: 1};
function filtered() {
  const q = $('q').value.trim().toLowerCase(), mf = $('mapF').value; let inView = null;
  if ($('fView').checked && READY) { const b = map.getBounds(); inView = new Set(); D.features.forEach(f => { if (!f.properties.key) return; const x = bboxOf([f]); if (x[2] >= b.getWest() && x[0] <= b.getEast() && x[3] >= b.getSouth() && x[1] <= b.getNorth()) inView.add(f.properties.key); }); }
  let rs = ROWS.filter(r => AON.has(r.area) && MAPON.has(r.map) && (!q || r.project_id.toLowerCase().includes(q)) && (!CATON.size || CATON.has(r.category)) && (!mf || r.map === mf) && (!inView || inView.has(r.key)));
  if (SORT.k) rs = rs.slice().sort((a, b) => { const x = val(a, SORT.k), y = val(b, SORT.k); return (typeof x === 'number' || typeof y === 'number' ? (x ?? -1) - (y ?? -1) : String(x ?? '').localeCompare(String(y ?? ''), undefined, {numeric: true})) * SORT.dir; });
  return rs;
}
function render() {
  const rs = filtered(), keys = [...new Set(rs.map(r => r.key))], cols = COLS.filter(c => c.show);
  $('th').innerHTML = '<tr>' + cols.map(c => `<th data-k="${c.k}" class="${['money', 'num'].includes(c.t) ? 'num' : ''}">${esc(c.label)}${SORT.k === c.k ? (SORT.dir > 0 ? ' ▲' : ' ▼') : ''}</th>`).join('') + '</tr>';
  $('th').querySelectorAll('th').forEach(th => th.onclick = () => { SORT = {k: th.dataset.k, dir: SORT.k === th.dataset.k ? -SORT.dir : 1}; render(); });
  $('tb').innerHTML = rs.length ? rs.map(r => `<tr data-key="${esc(r.key)}" data-rid="${esc(r.rid)}" class="${r.key === SEL ? 'sel' : ''}">` + cols.map(c =>
      c.t === 'edit' ? `<td class="edit"><input data-f="${c.k}" value="${esc(val(r, c.k))}" placeholder="${c.k === 'acquired' ? (r.land_ha != null ? 'Yes / No / part' : '') : ''}"></td>`
      : c.t === 'id' ? `<td class="id"><i style="background:${colorOf(r)}"></i>${esc(r.project_id)}</td>`
      : c.k === 'area_name' ? `<td><span class="atag" style="--c:${AREA[r.area].colour}">${esc(r.area_name)}</span></td>`
      : c.k === 'component' ? `<td><span class="tag">${esc(r.component)}</span></td>`
      : `<td class="${['money', 'num'].includes(c.t) ? 'num' : ''}">${esc(fmtv(val(r, c.k), c.t))}</td>`).join('') + '</tr>').join('')
    : `<tr><td class="empty" colspan="${cols.length}">${AON.size ? 'No projects match. <a href="#" id="rst">Reset filters</a>' : 'Turn on Croskell or Collison Estate at the top.'}</td></tr>`;
  const tot = (D.totals || []).filter(t => rs.some(r => r[t.k] != null)).map(t => `${t.label} <b>${fmtv(rs.reduce((a, r) => a + (r[t.k] || 0), 0), t.t)}</b>`).join(' · ');
  $('summary').innerHTML = `<b>${rs.length}</b> of ${ROWS.filter(r => AON.has(r.area)).length} rows${tot ? ' · ' + tot : ''}`;
  if (READY) LIDS.concat([['labels', null]]).forEach(([id, k]) => { if (k && CLS[k].context) return; const base = k ? ['==', ['get', 'cls'], k] : ['has', 'project_id'];
    map.setFilter(id, ['all', base, ['any', ['!', ['has', 'key']], ['in', ['get', 'key'], ['literal', keys]]], ...(k ? [] : [['in', ['get', 'cls'], ['literal', Object.keys(CLS).filter(classShown)]]])]); });
  $('tb').querySelectorAll('tr[data-key]').forEach(tr => {
    tr.onmouseenter = () => setHover(tr.dataset.key); tr.onmouseleave = () => setHover(null);
    tr.onclick = e => { if (e.target.tagName !== 'INPUT') select(tr.dataset.key === SEL ? null : tr.dataset.key); };
    tr.querySelectorAll('input').forEach(inp => inp.onchange = () => { (EDITS[tr.dataset.rid] ??= {})[inp.dataset.f] = inp.value; store.set(SK, EDITS); if (SEL === tr.dataset.key) showDetail(SEL); });
  });
  $('rst')?.addEventListener('click', e => { e.preventDefault(); reset(); });
}
function reset() { $('q').value = ''; $('mapF').value = ''; CATON = new Set(); $('fView').checked = false; select(null); buildChips(); render(); fitAll(); }
$('q').oninput = render; $('fView').onchange = render; $('mapF').onchange = render; $('bClear').onclick = reset;
(() => { const bt = $('bottom'), h0 = store.get('cfb-h', null); if (h0) bt.style.height = h0 + 'px'; let y0, hh;
  $('resizer').onmousedown = e => { y0 = e.clientY; hh = bt.offsetHeight; const mv = ev => { bt.style.height = Math.max(110, Math.min(window.innerHeight - 220, hh - (ev.clientY - y0))) + 'px'; map.resize(); };
    const up = () => { document.removeEventListener('mousemove', mv); document.removeEventListener('mouseup', up); store.set('cfb-h', bt.offsetHeight); }; document.addEventListener('mousemove', mv); document.addEventListener('mouseup', up); }; })();

// ---------- Excel ----------
function exportXlsx(rows, label) {
  const E = D.export, aoa = [E.columns], today = new Date().toISOString().slice(0, 10);
  rows.forEach(r => { const a = r.export.slice(); a[E.acquired_col] = val(r, 'acquired') || null; a[E.status_col] = val(r, 'status') || null; aoa.push(a); });
  const ws = XLSX.utils.aoa_to_sheet(aoa); ws['!cols'] = E.widths.map(w => ({wch: w}));
  for (let i = 2; i <= aoa.length; i++) { for (const c of ['H', 'I']) if (ws[c + i]) ws[c + i].z = '"$"#,##0.00'; if (ws['F' + i]) ws['F' + i].z = '0.0000'; }
  const wb = XLSX.utils.book_new(); XLSX.utils.book_append_sheet(wb, ws, ('project-register-' + today).slice(0, 31));
  const det = rows.map(r => Object.fromEntries([['Row ID', r.rid], ...D.columns.map(c => [c.label, val(r, c.k)])]));
  const wd = XLSX.utils.json_to_sheet(det); wd['!cols'] = Object.keys(det[0] || {}).map(k => ({wch: Math.max(10, Math.min(40, k.length + 4))})); XLSX.utils.book_append_sheet(wb, wd, 'Details');
  const areasIn = new Set(rows.map(r => r.area_name));
  for (const [k, t] of Object.entries(D.tables)) if ([...areasIn].some(a => k.startsWith(a + ' '))) XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(t), k.slice(0, 31));
  const n = XLSX.utils.aoa_to_sheet([['Casey Fields Boulevard – contribution plans: project register export'], ['Exported', today], ['Rows', rows.length + ' (' + label + ')'],
    ['Plan areas', [...areasIn].join(', ')],
    ['Filters', [$('q').value && 'ID "' + $('q').value + '"', $('mapF').value && 'plan map: ' + $('mapF').selectedOptions[0].text, CATON.size && 'categories: ' + [...CATON].join(', '), $('fView').checked && 'in map view'].filter(Boolean).join('; ') || 'none'],
    ...AREAS.filter(a => [...areasIn].includes(a.short)).map(a => [a.short, a.source + (a.note ? ' – ' + a.note : '')]),
    ['Edits', '"Land acquired" and "Current status" are entered in the app; "Import edits" restores them from this file.']]);
  n['!cols'] = [{wch: 14}, {wch: 120}]; XLSX.utils.book_append_sheet(wb, n, 'About');
  XLSX.writeFile(wb, `casey-fields-blvd-projects-${today}.xlsx`);
}
$('bExp').onclick = () => exportXlsx(ROWS.filter(r => AON.has(r.area)), 'all rows of the plan areas shown');
$('bExpF').onclick = () => exportXlsx(filtered(), 'rows shown');
$('bImp').onclick = () => $('fImp').click();
$('fImp').onchange = async e => { const f = e.target.files[0]; if (!f) return; const wb = XLSX.read(await f.arrayBuffer()); let n = 0;
  (wb.Sheets.Details ? XLSX.utils.sheet_to_json(wb.Sheets.Details) : []).forEach(r => { let rid = r['Row ID']; if (rid && !ROWS.some(x => x.rid === rid)) rid = ROWS.find(x => x.rid.endsWith(':' + rid))?.rid;
    if (rid && ROWS.some(x => x.rid === rid)) { EDITS[rid] = {acquired: r['Land acquired'] ?? '', status: r['Status'] ?? r['Current status'] ?? ''}; n++; } });
  store.set(SK, EDITS); render(); if (SEL) showDetail(SEL); alert(`${n} rows restored from ${f.name}`); e.target.value = ''; };
window.APP = {map, select, get READY() { return READY; }, get SEL() { return SEL; }, FBYKEY, AON, IMGON, MAPON, applyVis};
applyVis();
})();
