"""Collison Estate DCP (V4.1, Feb 2025): Tables 5-8 (projects) and Table 11 (levy calculation) -> data/reference/collison/.
Read from the PDF text layout; checked against the printed subtotals and total of Table 11."""
import pathlib, re, subprocess
import pandas as pd
ROOT = pathlib.Path(__file__).resolve().parents[1]
PDF = ROOT / 'sources/pdfs/Collison Estate Development Contributions Plan V4.1 Feb25.pdf'
OUT = ROOT / 'data/reference/collison'; OUT.mkdir(parents=True, exist_ok=True)
txt = lambda a, b: subprocess.run(['pdftotext', '-f', str(a), '-l', str(b), '-layout', str(PDF), '-'], capture_output=True, text=True).stdout
ID = re.compile(r'^\s*((?:RD|IN|DR|CF|PR)\d{2})\b')
TYPE = re.compile(r'\s{2,}(Land & Construction|Construction|Land|Other)\s*$')
GROUP = {'RD': 'Roads', 'IN': 'Intersections', 'DR': 'Drainage', 'CF': 'Community facilities', 'PR': 'Other DCP projects'}

# Tables 5-8: description lines before and after each ID line belong to that ID (wrapped text is centred on the ID line)
rows, pend = {}, []
lines = [l for l in txt(17, 19).splitlines()]
cur = None
for l in lines:
    if re.match(r'^\s*(T\d+\.|Project ID|Project Title|Roads Projects|Intersection Projects|ID\s|/ Other|Other\s*$|Collison Estate|\d\.\d)', l) or not l.strip(): 
        if not l.strip() or re.match(r'^\s*(T\d+\.|\d\.\d|Collison)', l): cur = None; pend = []
        continue
    m = ID.match(l)
    t = TYPE.search(l); kind = t.group(1) if t else None
    body = (l[:t.start()] if t else l)
    if m:
        pid = m.group(1); body = body[m.end():]
        rows[pid] = dict(project_id=pid, group=GROUP[pid[:2]], text=' '.join(pend + [body.strip()]).strip(), type=kind); cur = pid; pend = []
    elif cur and l.startswith(' ' * 10) and len(l) - len(l.lstrip()) >= 10 and not kind:
        # continuation: either the tail of `cur` or the head of the next ID; decide by whether `cur` text ended a sentence
        s = body.strip()
        if rows[cur]['text'].rstrip().endswith(('.', ')', ').')) and not rows[cur]['text'].rstrip().endswith('hectares)') or s[:1].isupper() and rows[cur]['text'].rstrip()[-1:] in '.)':
            pend.append(s)
        else: rows[cur]['text'] += ' ' + s
    elif not cur and len(l) - len(l.lstrip()) >= 10: pend.append(body.strip())
P = pd.DataFrame(rows.values())
P['text'] = P.text.str.replace(r'^(Construction / Land( /)?\s*)', '', regex=True).str.replace(r'\s+', ' ', regex=True)
P['title'] = P.text.str.split(r' [-–] ', n=1, regex=True).str[0].str.strip(' -–')
P['description'] = P.text.str.split(r' [-–] ', n=1, regex=True).str[1].fillna('').str.strip(' -–')
P['land_ha'] = P.text.str.extract(r'\(([\d.]+)\s*hectares')[0].astype(float)
P['pipe'] = P.text.str.extract(r'(\d+Ø)')[0]; P['pipe_length_m'] = P.text.str.extract(r'@\s*([\d.]+)\s*m?\s*linear')[0].astype(float)
P['table'] = P.project_id.str[:2].map({'RD': 'T5', 'IN': 'T5', 'DR': 'T6', 'CF': 'T7', 'PR': 'T8'})

# Table 11
money = lambda s: float(s.replace('$', '').replace(',', ''))
t11 = []
for l in txt(24, 25).splitlines():
    m = ID.match(l)
    if not m: continue
    toks = re.findall(r'\$[\d,]+\.\d{2}|\d+(?:\.\d+)?%|\b\d+\.\d{2}\b', l[m.end():])
    i = next(k for k, t in enumerate(toks) if t.endswith('%')); pre = [money(t) for t in toks[:i] if t.startswith('$')]
    land, constr, total = (pre if len(pre) == 3 else [None] + pre if len(pre) == 2 else [None, None] + pre)
    post = toks[i + 1:]
    t11.append(dict(project_id=m.group(1), land_cost_aud=land, construction_cost_aud=constr, total_cost_aud=total, apportionment_pct=float(toks[i][:-1]),
                    cost_to_mca_aud=money(post[0]), demand_units_ndha=float(post[1]), levy_per_ndha_aud=money(post[2])))
T = pd.DataFrame(t11)
tot = dict(land_cost_aud=29851528.07, construction_cost_aud=43164322.23, total_cost_aud=73015850.31, cost_to_mca_aud=64792267.99, levy_per_ndha_aud=945577.66)
for c, v in tot.items(): assert abs(T[c].fillna(0).sum() - v) < 0.05, (c, T[c].sum(), v)
for g, v in {'RD': 286096.15, 'IN': 58968.27, 'DR': 425968.31, 'CF': 163800.63, 'PR': 10744.29}.items():
    assert abs(T[T.project_id.str.startswith(g)].levy_per_ndha_aud.sum() - v) < 0.05, g
assert set(T.project_id) == set(P.project_id), set(T.project_id) ^ set(P.project_id)
P = P.merge(T, on='project_id').drop(columns='text')
P['source'] = 'Collison Estate DCP V4.1 (Feb 2025), ' + P.table.map({'T5': 'T5 (printed p. 13)', 'T6': 'T6 (p. 14)', 'T7': 'T7 (p. 15)', 'T8': 'T8 (p. 15)'}) + '; T11 (pp. 20-21)'
P.to_csv(OUT / 'projects_t5_t8_t11.csv', index=False, encoding='utf-8-sig')
print(len(P), 'projects; T11 totals and subtotals match'); print(P[['project_id', 'title', 'type', 'land_ha', 'pipe_length_m', 'total_cost_aud', 'levy_per_ndha_aud']].to_string(index=False))
