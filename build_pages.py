#!/usr/bin/env python3
"""Build 8 D&D 5e reference HTML pages for the PGW site."""

import json, glob, os, re
from pathlib import Path

BASE = Path('/Users/dylan/.openclaw/workspace/dnd')
DATA_DIR = BASE / 'systems/5e/resource_instances'
SRD_DIR  = BASE / 'srd'

# ─── helpers ───────────────────────────────────────────────────────────────

def esc(s):
    return str(s).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('"','&quot;')

def gv(d, *path, default=''):
    for k in path:
        if not isinstance(d, dict):
            return default
        d = d.get(k, {})
    if isinstance(d, dict):
        v = d.get('value')
        return v if v is not None else default
    return default

def load_json(fp):
    try:
        with open(fp, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None

def cost_str(stats):
    c = (stats.get('cost') or {}).get('value', {})
    if isinstance(c, dict):
        cs = c.get('stats', {})
        v = ((cs.get('value') or {}).get('value') or 0)
        u = ((cs.get('unit') or {}).get('value') or '')
        if v:
            sh = {'gold':'gp','silver':'sp','copper':'cp',
                  'electrum':'ep','platinum':'pp'}.get(str(u), str(u))
            return f"{int(v)} {sh}"
    return ''

def weight_str(stats):
    w = (stats.get('weight') or {}).get('value', {})
    if isinstance(w, dict):
        ws = w.get('stats', {})
        v = ((ws.get('value') or {}).get('value') or 0)
        if v:
            return f"{float(v):g} lb"
    return ''

def cr_disp(cr):
    if not cr: return ''
    s = str(cr).replace('cr_', '')
    return {'1_8':'1/8','1_4':'1/4','1_2':'1/2','0':'0'}.get(s, s)

def cr_num(cr):
    sp = {'cr_0':0,'cr_1_8':0.125,'cr_1_4':0.25,'cr_1_2':0.5}
    if cr in sp: return sp[cr]
    try: return float(str(cr).replace('cr_', ''))
    except: return 999

def abmod(n):
    try:
        m = (int(n) - 10) // 2
        return f"+{m}" if m >= 0 else str(m)
    except: return '+0'

# ─── shared CSS / page wrapper ─────────────────────────────────────────────

CSS = (
    "*{box-sizing:border-box;margin:0;padding:0}"
    "body{background:#0e0e14;color:#ddd;font-family:'Segoe UI',sans-serif;font-size:14px}"
    "h1{text-align:center;color:#a78bfa;padding:18px;font-size:1.4rem;letter-spacing:2px}"
    "h1 span{color:#6d28d9}"
    ".filters{display:flex;flex-wrap:wrap;gap:9px;padding:12px 18px;"
    "background:#15151e;border-bottom:1px solid #2a2a3a;align-items:center}"
    ".filters input,.filters select{background:#1e1e2e;border:1px solid #3a3a5a;"
    "color:#ddd;padding:6px 10px;border-radius:6px;font-size:13px}"
    ".filters input{width:200px}"
    ".filters input:focus,.filters select:focus{outline:none;border-color:#7c3aed}"
    ".count{margin-left:auto;color:#666;font-size:12px;white-space:nowrap}"
    ".table-wrap{overflow-x:auto;padding:0 10px 40px}"
    "table{width:100%;border-collapse:collapse;margin-top:10px}"
    "thead th{background:#1a1a2e;color:#a78bfa;font-size:11px;text-transform:uppercase;"
    "letter-spacing:1px;padding:9px 11px;text-align:left;cursor:pointer;"
    "border-bottom:2px solid #3a2a6a;white-space:nowrap;user-select:none}"
    "thead th:hover{color:#c4b5fd}"
    "thead th.asc::after{content:' \u25b2'}thead th.desc::after{content:' \u25bc'}"
    "tbody tr:not(.desc-row){cursor:pointer;border-bottom:1px solid #1a1a28}"
    "tbody tr:not(.desc-row):hover{background:#1a1a2e}"
    "tbody tr:not(.desc-row).active{background:#1e1530}"
    "td{padding:8px 11px;vertical-align:middle}"
    "td:first-child{color:#e2d9f3}"
    ".desc-row td{padding:0;background:#0d0d18}"
    ".desc-content{padding:12px 18px;border-left:3px solid #6d28d9;"
    "margin:4px 10px 10px;border-radius:0 6px 6px 0;"
    "font-size:13px;color:#bbb;line-height:1.6;white-space:pre-wrap}"
    ".back{display:block;text-align:center;padding:10px;color:#7c3aed;"
    "font-size:13px;text-decoration:none}.back:hover{color:#a78bfa}"
    ".pgn{display:flex;gap:6px;justify-content:center;padding:10px;flex-wrap:wrap}"
    ".pgn button{background:#1e1e2e;border:1px solid #3a3a5a;color:#888;"
    "padding:4px 12px;border-radius:4px;cursor:pointer;font-size:12px}"
    ".pgn button.act{background:#2a1a4a;color:#c4b5fd;border-color:#6d28d9}"
    ".tag{display:inline-block;font-size:10px;font-weight:bold;padding:2px 5px;"
    "border-radius:4px;background:#1e3a5f;color:#60a5fa;margin-left:3px}"
    ".ck{color:#4ade80}.cx{color:#555}"
)

# Shared JS sort engine (injected into each page's <script>)
JS_SORT = """
let sC=-1,sA=true;
function srt(c){
  if(sC===c)sA=!sA;else{sC=c;sA=true;}
  F.sort((a,b)=>{
    let va=SK[c](a),vb=SK[c](b);
    if(typeof va==='number'&&typeof vb==='number')return sA?(va-vb):(vb-va);
    va=String(va);vb=String(vb);
    return sA?va.localeCompare(vb,void 0,{numeric:true}):vb.localeCompare(va,void 0,{numeric:true});
  });
  document.querySelectorAll('thead th').forEach((th,i)=>th.className=i===sC?(sA?'asc':'desc'):'');
  open=-1;render();
}
"""

def page(title, icon, filters_html, thead_html, script, pagination=''):
    return (f'<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{esc(title)}</title>'
            f'<style>{CSS}</style></head><body>\n'
            f'<h1>{icon} {esc(title)}</h1>\n'
            f'<a class="back" href="index.html">&larr; Back to Campaign Hub</a>\n'
            f'<div class="filters">{filters_html}'
            f'<span class="count" id="cnt"></span></div>\n'
            f'<div class="table-wrap"><table>'
            f'<thead><tr>{thead_html}</tr></thead>'
            f'<tbody id="tb"></tbody></table></div>'
            f'{pagination}\n'
            f'<script>function esc(s){{return String(s)'
            f".replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}}\n"
            f'{script}</script></body></html>')

def th(labels):
    return ''.join(f'<th onclick="srt({i})">{h}</th>' for i, h in enumerate(labels))

def sel_opts(values, current_val='', label_fn=None):
    out = []
    for v in values:
        lbl = label_fn(v) if label_fn else str(v)
        sel = ' selected' if v == current_val else ''
        out.append(f'<option value="{esc(v)}"{sel}>{esc(lbl)}</option>')
    return ''.join(out)

# ─── 1. monsters ───────────────────────────────────────────────────────────

def build_monsters():
    files = sorted(glob.glob(str(DATA_DIR / 'monster_*.json')))
    rows = []
    sources, crs = set(), set()

    for fp in files:
        d = load_json(fp)
        if not d: continue
        s = d.get('stats', {})
        name = gv(s, 'name') or ''
        if not name: continue
        source = gv(s, 'source') or ''
        cr     = gv(s, 'cr') or ''
        mtype  = gv(s, 'type') or ''
        tag    = gv(s, 'tag') or ''
        ac     = gv(s, 'armor_class') or 0
        xp     = gv(s, 'xp') or 0

        # HP dice notation
        hp_obj = (s.get('hit_points') or {}).get('value', {})
        hp = ''
        if isinstance(hp_obj, dict):
            hs  = hp_obj.get('stats', {})
            amt = ((hs.get('dice_amount') or {}).get('value') or 0)
            dt  = ((hs.get('dice_type')   or {}).get('value') or '')
            con = ((hs.get('constant')    or {}).get('value') or 0)
            if amt and dt:
                hp = f"{amt}{dt}" + (f"+{con}" if con else "")

        # Speed
        spd   = int(gv(s, 'speed')        or 0)
        fly   = int(gv(s, 'fly_speed')    or 0)
        swim  = int(gv(s, 'swim_speed')   or 0)
        climb = int(gv(s, 'climb_speed')  or 0)
        sp_parts = [f"{spd} ft"]
        if fly:   sp_parts.append(f"fly {fly}")
        if swim:  sp_parts.append(f"swim {swim}")
        if climb: sp_parts.append(f"climb {climb}")
        speed = ', '.join(sp_parts)

        STR = int(gv(s, 'strength_score')     or 10)
        DEX = int(gv(s, 'dexterity_score')    or 10)
        CON = int(gv(s, 'constitution_score') or 10)
        INT = int(gv(s, 'intelligence_score') or 10)
        WIS = int(gv(s, 'wisdom_score')       or 10)
        CHA = int(gv(s, 'charisma_score')     or 10)

        sources.add(source)
        crs.add(cr)
        rows.append({
            'n': name, 'src': source, 'cr': cr, 'crn': cr_num(cr), 'crd': cr_disp(cr),
            'tp': mtype, 'tag': tag, 'ac': int(ac), 'hp': hp, 'sp': speed,
            'xp': int(xp),
            'S': STR, 'D': DEX, 'C': CON, 'I': INT, 'W': WIS, 'H': CHA,
            'sm': abmod(STR), 'dm': abmod(DEX), 'cm': abmod(CON),
            'im': abmod(INT), 'wm': abmod(WIS), 'hm': abmod(CHA),
        })

    cr_sorted = sorted({r['cr'] for r in rows if r['cr']}, key=lambda x: cr_num(x))
    src_sorted = sorted(sources)

    cr_opts  = ''.join(f'<option value="{c}">{cr_disp(c)}</option>' for c in cr_sorted)
    src_opts = ''.join(f'<option value="{s}">{s.upper()}</option>' for s in src_sorted)

    filters = (
        f'<input type="text" id="qs" placeholder="Search name, type, tag\u2026" oninput="fil()">'
        f'<label>CR<select id="fcr" onchange="fil()"><option value="">All CR</option>{cr_opts}</select></label>'
        f'<label>Source<select id="fsr" onchange="fil()"><option value="">All Sources</option>{src_opts}</select></label>'
    )

    data_js = json.dumps(rows, ensure_ascii=False)

    js = f"""const DATA={data_js};
let F=DATA.slice(),open=-1,pg=0;
const PS=100;
const SK=[r=>r.n,r=>r.crn,r=>r.tp,r=>r.ac,r=>r.hp,r=>r.sp,r=>r.xp,r=>r.src];
{JS_SORT}
function render(){{
  const sl=F.slice(pg*PS,(pg+1)*PS);
  const h=[];
  sl.forEach((r,i)=>{{
    const gi=pg*PS+i;
    const tg=r.tag&&r.tag!==r.tp?`<span class="tag">${{esc(r.tag)}}</span>`:'';
    h.push(`<tr onclick="tog(${{gi}})"${{open===gi?' class="active"':''}}>`+
      `<td>${{esc(r.n)}}</td><td>${{esc(r.crd||'\u2014')}}</td>`+
      `<td>${{esc(r.tp)}}${{tg}}</td><td>${{r.ac||'\u2014'}}</td>`+
      `<td>${{esc(r.hp||'\u2014')}}</td><td>${{esc(r.sp)}}</td>`+
      `<td>${{r.xp||'\u2014'}}</td><td>${{esc(r.src).toUpperCase()}}</td></tr>`);
    h.push(`<tr class="desc-row" style="display:${{open===gi?'':'none'}}"><td colspan="8">`+
      `<div class="desc-content">`+
      `STR ${{r.S}} (${{r.sm}})\u2003DEX ${{r.D}} (${{r.dm}})\u2003CON ${{r.C}} (${{r.cm}})`+
      `\u2003INT ${{r.I}} (${{r.im}})\u2003WIS ${{r.W}} (${{r.wm}})\u2003CHA ${{r.H}} (${{r.hm}})`+
      `</div></td></tr>`);
  }});
  document.getElementById('tb').innerHTML=h.join('');
  document.getElementById('cnt').textContent=F.length+'/'+DATA.length;
  const tot=Math.ceil(F.length/PS),pb=[];
  for(let i=0;i<tot;i++)pb.push(`<button class="${{pg===i?'act':''}}" onclick="gp(${{i}})">${{i+1}}</button>`);
  document.getElementById('pgn').innerHTML=pb.join('');
}}
function gp(p){{pg=p;open=-1;render();}}
function tog(i){{open=open===i?-1:i;render();}}
function fil(){{
  const q=document.getElementById('qs').value.toLowerCase();
  const fc=document.getElementById('fcr').value;
  const fs=document.getElementById('fsr').value;
  F=DATA.filter(r=>
    (!q||(r.n+' '+r.tp+' '+r.tag).toLowerCase().includes(q))&&
    (!fc||r.cr===fc)&&(!fs||r.src===fs));
  pg=0;open=-1;render();
}}
render();"""

    return page(
        'Monsters \u2014 5e Reference', '\U0001f479',
        filters,
        th(['Name','CR','Type','AC','HP','Speed','XP','Source']),
        js, '<div class="pgn" id="pgn"></div>'
    )

# ─── 2. weapons ────────────────────────────────────────────────────────────

def build_weapons():
    files = sorted(glob.glob(str(DATA_DIR / 'weapon_*.rpg.json')))
    rows = []
    sources = set()

    for fp in files:
        d = load_json(fp)
        if not d: continue
        s = d.get('stats', {})
        name = gv(s, 'name') or ''
        if not name: continue
        source    = gv(s, 'source') or ''
        wtype     = gv(s, 'type') or ''
        is_simple = gv(s, 'is_simple')
        cat = 'Simple' if is_simple else 'Martial'

        # Damage
        dmg_arr = (s.get('damage_dice') or {}).get('value', [])
        dmg, dmg_type = '', ''
        if dmg_arr and isinstance(dmg_arr, list):
            dd = dmg_arr[0] if dmg_arr else {}
            ds = dd.get('stats', {}) if isinstance(dd, dict) else {}
            dices = (ds.get('dices') or {}).get('value', [])
            if dices and isinstance(dices, list):
                d0 = dices[0] if dices else {}
                d0s = d0.get('stats', {}) if isinstance(d0, dict) else {}
                amt = ((d0s.get('dice_amount') or {}).get('value') or 0)
                dt  = ((d0s.get('dice_type')   or {}).get('value') or '')
                if amt and dt:
                    dmg = f"{amt}{dt}"
            dmg_type = ((ds.get('damage_type') or {}).get('value') or '')

        # Versatile damage
        vers_arr = (s.get('versatile_damage_dice') or {}).get('value', [])
        vers_dmg = ''
        if vers_arr and isinstance(vers_arr, list):
            vd = vers_arr[0] if vers_arr else {}
            vds = vd.get('stats', {}) if isinstance(vd, dict) else {}
            vdices = (vds.get('dices') or {}).get('value', [])
            if vdices:
                v0 = vdices[0] if vdices else {}
                v0s = v0.get('stats', {}) if isinstance(v0, dict) else {}
                vamt = ((v0s.get('dice_amount') or {}).get('value') or 0)
                vdt  = ((v0s.get('dice_type')   or {}).get('value') or '')
                if vamt and vdt:
                    vers_dmg = f"{vamt}{vdt}"

        # Properties
        props = []
        if gv(s, 'is_finesse'):    props.append('Finesse')
        if gv(s, 'is_thrown'):     props.append('Thrown')
        if gv(s, 'is_light'):      props.append('Light')
        if gv(s, 'is_versatile'):
            props.append(f'Versatile ({vers_dmg})' if vers_dmg else 'Versatile')
        if gv(s, 'is_reach'):      props.append('Reach')
        if gv(s, 'is_two_handed'): props.append('Two-Handed')
        if gv(s, 'is_heavy'):      props.append('Heavy')
        if gv(s, 'is_loading'):    props.append('Loading')
        if gv(s, 'is_ammunition') or gv(s, 'is_ranged'):
            props.append('Ammunition')

        sources.add(source)
        rows.append({
            'n': name, 'src': source, 'tp': wtype, 'cat': cat,
            'dmg': dmg, 'dtp': dmg_type,
            'props': ', '.join(props) if props else '\u2014',
            'cost': cost_str(s), 'wt': weight_str(s),
        })

    src_opts = ''.join(f'<option value="{s}">{s.upper()}</option>' for s in sorted(sources))
    filters = (
        f'<input type="text" id="qs" placeholder="Search weapons\u2026" oninput="fil()">'
        f'<label>Category<select id="fcat" onchange="fil()"><option value="">All</option>'
        f'<option value="Simple">Simple</option><option value="Martial">Martial</option></select></label>'
        f'<label>Source<select id="fsr" onchange="fil()"><option value="">All Sources</option>{src_opts}</select></label>'
    )

    data_js = json.dumps(rows, ensure_ascii=False)
    js = f"""const DATA={data_js};
let F=DATA.slice(),open=-1;
const SK=[r=>r.n,r=>r.cat,r=>r.dmg,r=>r.dtp,r=>r.props,r=>r.cost,r=>r.wt,r=>r.src];
{JS_SORT}
function render(){{
  const h=[];
  F.forEach((r,i)=>{{
    h.push(`<tr onclick="tog(${{i}})"${{open===i?' class="active"':''}}>`+
      `<td>${{esc(r.n)}}</td><td>${{esc(r.cat)}}</td>`+
      `<td>${{esc(r.dmg||'\u2014')}}</td><td>${{esc(r.dtp||'\u2014')}}</td>`+
      `<td style="font-size:12px">${{esc(r.props)}}</td>`+
      `<td>${{esc(r.cost||'\u2014')}}</td><td>${{esc(r.wt||'\u2014')}}</td>`+
      `<td>${{esc(r.src).toUpperCase()}}</td></tr>`);
    h.push(`<tr class="desc-row" style="display:${{open===i?'':'none'}}"><td colspan="8">`+
      `<div class="desc-content">`+
      `Type: ${{esc(r.tp||'\u2014')}}\u2003Category: ${{esc(r.cat)}}\u2003Properties: ${{esc(r.props)}}`+
      `</div></td></tr>`);
  }});
  document.getElementById('tb').innerHTML=h.join('');
  document.getElementById('cnt').textContent=F.length+'/'+DATA.length;
}}
function tog(i){{open=open===i?-1:i;render();}}
function fil(){{
  const q=document.getElementById('qs').value.toLowerCase();
  const fc=document.getElementById('fcat').value;
  const fs=document.getElementById('fsr').value;
  F=DATA.filter(r=>
    (!q||(r.n+' '+r.tp+' '+r.props).toLowerCase().includes(q))&&
    (!fc||r.cat===fc)&&(!fs||r.src===fs));
  open=-1;render();
}}
render();"""

    return page(
        'Weapons \u2014 5e Reference', '\u2694\ufe0f',
        filters,
        th(['Name','Category','Damage','Dmg Type','Properties','Cost','Weight','Source']),
        js
    )

# ─── 3. armor ──────────────────────────────────────────────────────────────

def build_armor():
    files = sorted(glob.glob(str(DATA_DIR / 'armor_*.rpg.json')))
    rows = []
    sources, types = set(), set()

    for fp in files:
        d = load_json(fp)
        if not d: continue
        s = d.get('stats', {})
        name = gv(s, 'name') or ''
        if not name: continue
        source  = gv(s, 'source') or ''
        atype   = gv(s, 'type') or ''
        base_ac = gv(s, 'base_ac') or 0
        req_str = gv(s, 'required_strength') or 0
        stealth = gv(s, 'impose_stealth_disadvantage') or False
        is_magic = gv(s, 'is_magic') or False

        sources.add(source)
        types.add(atype)
        rows.append({
            'n': name, 'src': source, 'tp': atype, 'tpd': atype.title(),
            'ac': int(base_ac), 'str': int(req_str) if req_str else 0,
            'stl': bool(stealth), 'mag': bool(is_magic),
            'cost': cost_str(s), 'wt': weight_str(s),
        })

    src_opts  = ''.join(f'<option value="{s}">{s.upper()}</option>' for s in sorted(sources))
    type_opts = ''.join(f'<option value="{t}">{t.title()}</option>' for t in sorted(types) if t)
    filters = (
        f'<input type="text" id="qs" placeholder="Search armor\u2026" oninput="fil()">'
        f'<label>Type<select id="ftp" onchange="fil()"><option value="">All Types</option>{type_opts}</select></label>'
        f'<label>Source<select id="fsr" onchange="fil()"><option value="">All Sources</option>{src_opts}</select></label>'
    )

    data_js = json.dumps(rows, ensure_ascii=False)
    js = f"""const DATA={data_js};
let F=DATA.slice(),open=-1;
const SK=[r=>r.n,r=>r.tpd,r=>r.ac,r=>r.str,r=>r.stl?1:0,r=>r.cost,r=>r.wt,r=>r.src];
{JS_SORT}
function ck(v){{return v?'<span class="ck">\u2713</span>':'<span class="cx">\u2014</span>';}}
function render(){{
  const h=[];
  F.forEach((r,i)=>{{
    h.push(`<tr onclick="tog(${{i}})"${{open===i?' class="active"':''}}>`+
      `<td>${{esc(r.n)}}${{r.mag?' <span class="tag">magic</span>':''}}</td>`+
      `<td>${{esc(r.tpd)}}</td><td>${{r.ac||'\u2014'}}</td>`+
      `<td>${{r.str||'\u2014'}}</td><td>${{ck(r.stl)}}</td>`+
      `<td>${{esc(r.cost||'\u2014')}}</td><td>${{esc(r.wt||'\u2014')}}</td>`+
      `<td>${{esc(r.src).toUpperCase()}}</td></tr>`);
    h.push(`<tr class="desc-row" style="display:${{open===i?'':'none'}}"><td colspan="8">`+
      `<div class="desc-content">`+
      `Type: ${{esc(r.tpd)}}\u2003Base AC: ${{r.ac}}`+
      `${{r.str?' \u2003Req STR: '+r.str:''}}`+
      `${{r.stl?' \u2003\u26a0\ufe0f Stealth Disadvantage':''}}`+
      `${{r.mag?' \u2003\u2728 Magic item':''}}`+
      `</div></td></tr>`);
  }});
  document.getElementById('tb').innerHTML=h.join('');
  document.getElementById('cnt').textContent=F.length+'/'+DATA.length;
}}
function tog(i){{open=open===i?-1:i;render();}}
function fil(){{
  const q=document.getElementById('qs').value.toLowerCase();
  const ft=document.getElementById('ftp').value;
  const fs=document.getElementById('fsr').value;
  F=DATA.filter(r=>
    (!q||r.n.toLowerCase().includes(q))&&
    (!ft||r.tp===ft)&&(!fs||r.src===fs));
  open=-1;render();
}}
render();"""

    return page(
        'Armor \u2014 5e Reference', '\U0001f6e1\ufe0f',
        filters,
        th(['Name','Type','Base AC','Req STR','Stealth Disadv','Cost','Weight','Source']),
        js
    )

# ─── 4. items ──────────────────────────────────────────────────────────────

RARITY_ORDER = ['none','common','uncommon','rare','very rare','legendary','artifact']

def build_items():
    files = sorted(glob.glob(str(DATA_DIR / 'item_*.rpg.json')))
    rows = []
    sources, types, rarities = set(), set(), set()

    for fp in files:
        d = load_json(fp)
        if not d: continue
        s = d.get('stats', {})
        name = gv(s, 'name') or ''
        if not name: continue
        source = gv(s, 'source') or ''
        itype  = gv(s, 'type') or ''
        rarity = gv(s, 'rarity') or ''
        is_magic = gv(s, 'is_magic') or False
        attune   = gv(s, 'requires_attunement') or False
        cursed   = gv(s, 'is_cursed') or False
        desc     = gv(s, 'description') or ''

        sources.add(source)
        types.add(itype)
        rarities.add(rarity)
        rar_n = RARITY_ORDER.index(rarity) if rarity in RARITY_ORDER else 99
        rows.append({
            'n': name, 'src': source, 'tp': itype,
            'rar': rarity, 'rarn': rar_n,
            'mag': bool(is_magic), 'att': bool(attune), 'cur': bool(cursed),
            'wt': weight_str(s), 'desc': desc,
        })

    src_opts  = ''.join(f'<option value="{s}">{s.upper()}</option>' for s in sorted(sources))
    type_opts = ''.join(f'<option value="{t}">{t.title()}</option>' for t in sorted(types) if t)
    rar_opts  = ''.join(f'<option value="{r}">{r.title()}</option>'
                        for r in RARITY_ORDER if r in rarities)
    filters = (
        f'<input type="text" id="qs" placeholder="Search items\u2026" oninput="fil()">'
        f'<label>Type<select id="ftp" onchange="fil()"><option value="">All Types</option>{type_opts}</select></label>'
        f'<label>Rarity<select id="frar" onchange="fil()"><option value="">All Rarities</option>{rar_opts}</select></label>'
        f'<label>Magic<select id="fmag" onchange="fil()"><option value="">Magic: All</option>'
        f'<option value="1">Magic only</option><option value="0">Non-magic</option></select></label>'
        f'<label>Source<select id="fsr" onchange="fil()"><option value="">All Sources</option>{src_opts}</select></label>'
    )

    data_js = json.dumps(rows, ensure_ascii=False)
    js = f"""const DATA={data_js};
let F=DATA.slice(),open=-1;
const SK=[r=>r.n,r=>r.tp,r=>r.rarn,r=>r.mag?1:0,r=>r.att?1:0,r=>r.cur?1:0,r=>r.wt,r=>r.src];
{JS_SORT}
function ck(v){{return v?'<span class="ck">\u2713</span>':'<span class="cx">\u2014</span>';}}
function render(){{
  const h=[];
  F.forEach((r,i)=>{{
    h.push(`<tr onclick="tog(${{i}})"${{open===i?' class="active"':''}}>`+
      `<td>${{esc(r.n)}}</td><td>${{esc(r.tp||'\u2014')}}</td>`+
      `<td>${{esc(r.rar||'\u2014')}}</td>`+
      `<td>${{ck(r.mag)}}</td><td>${{ck(r.att)}}</td><td>${{ck(r.cur)}}</td>`+
      `<td>${{esc(r.wt||'\u2014')}}</td><td>${{esc(r.src).toUpperCase()}}</td></tr>`);
    h.push(`<tr class="desc-row" style="display:${{open===i?'':'none'}}"><td colspan="8">`+
      `<div class="desc-content">${{esc(r.desc||'No description available.')}}</div></td></tr>`);
  }});
  document.getElementById('tb').innerHTML=h.join('');
  document.getElementById('cnt').textContent=F.length+'/'+DATA.length;
}}
function tog(i){{open=open===i?-1:i;render();}}
function fil(){{
  const q=document.getElementById('qs').value.toLowerCase();
  const ft=document.getElementById('ftp').value;
  const fr=document.getElementById('frar').value;
  const fm=document.getElementById('fmag').value;
  const fs=document.getElementById('fsr').value;
  F=DATA.filter(r=>
    (!q||(r.n+' '+r.tp+' '+r.rar).toLowerCase().includes(q))&&
    (!ft||r.tp===ft)&&(!fr||r.rar===fr)&&
    (fm===''||(fm==='1'?r.mag:!r.mag))&&
    (!fs||r.src===fs));
  open=-1;render();
}}
render();"""

    return page(
        'Items \u2014 5e Reference', '\U0001f4a0',
        filters,
        th(['Name','Type','Rarity','Magic','Attunement','Cursed','Weight','Source']),
        js
    )

# ─── 5. conditions ─────────────────────────────────────────────────────────

COND_NAMES = [
    'Blinded','Charmed','Deafened','Exhaustion','Frightened',
    'Grappled','Incapacitated','Invisible','Paralyzed','Petrified',
    'Poisoned','Prone','Restrained','Stunned','Unconscious'
]

def build_conditions():
    cond_file = SRD_DIR / 'srd-conditions.md'
    rows = []

    if cond_file.exists():
        text = cond_file.read_text(encoding='utf-8')
        # Build a map of name -> body text
        # Strategy: split on condition name lines, collect until next known name or EOF
        # We'll do a multi-pass: find each condition's section
        for name in COND_NAMES:
            # Match the condition name as a standalone line (with optional surrounding whitespace)
            # then capture everything until the next condition name or end
            others = '|'.join(COND_NAMES)
            pat = rf'(?m)^{re.escape(name)}\s*\n(.*?)(?=\n(?:{others})\s*\n|\Z)'
            m = re.search(pat, text, re.DOTALL | re.IGNORECASE)
            body = ''
            summary = ''
            if m:
                body = m.group(1).strip()
                # First non-empty line as summary (strip bullet chars)
                lines = [l.strip() for l in body.split('\n') if l.strip()]
                if lines:
                    summary = re.sub(r'^[•\-\*]\s*', '', lines[0])
                    if len(summary) > 140:
                        summary = summary[:137] + '...'
            if not summary:
                summary = 'See full description.'
            rows.append({'n': name, 'sum': summary, 'desc': body})
    else:
        # Hardcode basic descriptions
        hardcoded = {
            'Blinded':        "Can't see; auto-fails sight checks; attacks against have advantage.",
            'Charmed':        "Can't attack the charmer; charmer has advantage on social checks.",
            'Deafened':       "Can't hear; auto-fails hearing checks.",
            'Exhaustion':     "Cumulative penalties by level: disadvantage, halved speed, death at 6.",
            'Frightened':     "Disadvantage on checks/attacks while source is visible; can't approach.",
            'Grappled':       "Speed becomes 0; ends if grappler is incapacitated or target moved away.",
            'Incapacitated':  "Can't take actions or reactions.",
            'Invisible':      "Can't be seen; attacks against have disadvantage; own attacks have advantage.",
            'Paralyzed':      "Incapacitated; can't move or speak; auto-fails STR/DEX saves; crit within 5 ft.",
            'Petrified':      "Transformed to solid inanimate substance; incapacitated; resistance to all damage.",
            'Poisoned':       "Disadvantage on attack rolls and ability checks.",
            'Prone':          "Melee attacks against have advantage; own attacks have disadvantage; costs half move to stand.",
            'Restrained':     "Speed 0; attacks against have advantage; own attacks have disadvantage; DEX save disadvantage.",
            'Stunned':        "Incapacitated; can't move; auto-fails STR/DEX saves; attacks against have advantage.",
            'Unconscious':    "Incapacitated; can't move/speak; unaware; drops items; falls prone; auto-fails STR/DEX saves; crits within 5 ft.",
        }
        for name in COND_NAMES:
            rows.append({'n': name, 'sum': hardcoded.get(name,''), 'desc': hardcoded.get(name,'')})

    filters = '<input type="text" id="qs" placeholder="Search conditions\u2026" oninput="fil()">'
    data_js = json.dumps(rows, ensure_ascii=False)
    js = f"""const DATA={data_js};
let F=DATA.slice(),open=-1;
const SK=[r=>r.n,r=>r.sum];
{JS_SORT}
function render(){{
  const h=[];
  F.forEach((r,i)=>{{
    h.push(`<tr onclick="tog(${{i}})"${{open===i?' class="active"':''}}>`+
      `<td style="width:160px;font-weight:600">${{esc(r.n)}}</td>`+
      `<td style="font-size:13px;color:#aaa">${{esc(r.sum)}}</td></tr>`);
    h.push(`<tr class="desc-row" style="display:${{open===i?'':'none'}}"><td colspan="2">`+
      `<div class="desc-content">${{esc(r.desc||r.sum)}}</div></td></tr>`);
  }});
  document.getElementById('tb').innerHTML=h.join('');
  document.getElementById('cnt').textContent=F.length+'/'+DATA.length;
}}
function tog(i){{open=open===i?-1:i;render();}}
function fil(){{
  const q=document.getElementById('qs').value.toLowerCase();
  F=DATA.filter(r=>(!q||(r.n+' '+r.sum+' '+r.desc).toLowerCase().includes(q)));
  open=-1;render();
}}
render();"""

    return page(
        'Conditions \u2014 5e Reference', '\u26a1',
        filters,
        th(['Condition','Summary (click to expand)']),
        js
    )

# ─── 6. backgrounds ────────────────────────────────────────────────────────

def build_backgrounds():
    files = sorted(glob.glob(str(DATA_DIR / 'background_*.rpg.json')))
    rows = []
    sources = set()

    for fp in files:
        d = load_json(fp)
        if not d: continue
        s = d.get('stats', {})
        name = gv(s, 'name') or ''
        if not name: continue
        source = gv(s, 'source') or ''
        gold   = gv(s, 'gold_pieces') or 0

        # Features (class features embedded in background)
        feats_val = (s.get('features') or {}).get('value', [])
        feat_names, feat_descs = [], []
        for f in feats_val:
            if not isinstance(f, dict): continue
            fs     = f.get('stats', {})
            fname  = (fs.get('name') or {}).get('value', '')
            if fname: feat_names.append(fname)
            descs_val = (fs.get('descriptions') or {}).get('value', [])
            for dd in descs_val:
                if not isinstance(dd, dict): continue
                desc = ((dd.get('stats',{}).get('description') or {}).get('value') or '')
                if desc:
                    feat_descs.append(f"{fname}:\n{desc}")
                    break

        # Skill proficiencies
        skills_val = (s.get('skill_proficiencies') or {}).get('value', [])
        skill_names = []
        for sk in skills_val:
            if not isinstance(sk, dict): continue
            opts = ((sk.get('stats',{}).get('options') or {}).get('value') or [])
            if isinstance(opts, list):
                skill_names.extend(str(o).replace('_',' ').title() for o in opts if isinstance(o, str))
            elif isinstance(opts, str):
                skill_names.append(opts.replace('_',' ').title())

        sources.add(source)
        rows.append({
            'n': name, 'src': source,
            'gold': int(gold) if gold else 0,
            'feat': feat_names[0] if feat_names else '\u2014',
            'skills': ', '.join(skill_names) if skill_names else '\u2014',
            'desc': '\n\n'.join(feat_descs) if feat_descs else '',
        })

    src_opts = ''.join(f'<option value="{s}">{s.upper()}</option>' for s in sorted(sources))
    filters = (
        f'<input type="text" id="qs" placeholder="Search backgrounds\u2026" oninput="fil()">'
        f'<label>Source<select id="fsr" onchange="fil()"><option value="">All Sources</option>{src_opts}</select></label>'
    )
    data_js = json.dumps(rows, ensure_ascii=False)
    js = f"""const DATA={data_js};
let F=DATA.slice(),open=-1;
const SK=[r=>r.n,r=>r.src,r=>r.feat,r=>r.skills,r=>r.gold];
{JS_SORT}
function render(){{
  const h=[];
  F.forEach((r,i)=>{{
    h.push(`<tr onclick="tog(${{i}})"${{open===i?' class="active"':''}}>`+
      `<td>${{esc(r.n)}}</td><td>${{esc(r.src).toUpperCase()}}</td>`+
      `<td>${{esc(r.feat)}}</td><td style="font-size:12px">${{esc(r.skills)}}</td>`+
      `<td>${{r.gold||'\u2014'}} gp</td></tr>`);
    h.push(`<tr class="desc-row" style="display:${{open===i?'':'none'}}"><td colspan="5">`+
      `<div class="desc-content">${{esc(r.desc||'No description available.')}}</div></td></tr>`);
  }});
  document.getElementById('tb').innerHTML=h.join('');
  document.getElementById('cnt').textContent=F.length+'/'+DATA.length;
}}
function tog(i){{open=open===i?-1:i;render();}}
function fil(){{
  const q=document.getElementById('qs').value.toLowerCase();
  const fs=document.getElementById('fsr').value;
  F=DATA.filter(r=>
    (!q||(r.n+' '+r.feat+' '+r.skills).toLowerCase().includes(q))&&
    (!fs||r.src===fs));
  open=-1;render();
}}
render();"""

    return page(
        'Backgrounds \u2014 5e Reference', '\U0001f4dc',
        filters,
        th(['Name','Source','Feature','Skill Proficiencies','Starting Gold']),
        js
    )

# ─── 7. races ──────────────────────────────────────────────────────────────

def build_races():
    files = sorted(glob.glob(str(DATA_DIR / 'race_*.rpg.json')))
    rows = []
    sources = set()

    for fp in files:
        d = load_json(fp)
        if not d: continue
        s = d.get('stats', {})
        name = gv(s, 'name') or ''
        if not name: continue
        source = gv(s, 'source') or ''
        speed  = int(gv(s, 'speed') or 30)
        fly    = int(gv(s, 'fly_speed') or 0)
        swim   = int(gv(s, 'swim_speed') or 0)
        climb  = int(gv(s, 'climb_speed') or 0)
        size   = gv(s, 'size') or ''

        sp_parts = [f"{speed} ft"]
        if fly:   sp_parts.append(f"fly {fly} ft")
        if swim:  sp_parts.append(f"swim {swim} ft")
        if climb: sp_parts.append(f"climb {climb} ft")
        speed_str = ', '.join(sp_parts)

        # ASIs
        asis_val = (s.get('ability_score_increases') or {}).get('value', [])
        asi_strs = []
        for a in asis_val:
            if not isinstance(a, dict): continue
            av = ((a.get('stats',{}).get('value') or {}).get('value') or 0)
            opts = ((a.get('stats',{}).get('modifier_options') or {}).get('value') or [])
            if av and opts and isinstance(opts, list):
                asi_strs.append(f"+{av} {'/'.join(str(o).title() for o in opts)}")

        # Traits
        traits_val = (s.get('traits') or {}).get('value', [])
        trait_names, trait_descs = [], []
        for t in traits_val:
            if not isinstance(t, dict): continue
            ts    = t.get('stats', {})
            tname = (ts.get('name') or {}).get('value', '')
            if tname: trait_names.append(tname)
            descs_val = (ts.get('descriptions') or {}).get('value', [])
            for dd in descs_val:
                if not isinstance(dd, dict): continue
                desc = ((dd.get('stats',{}).get('description') or {}).get('value') or '')
                if desc:
                    trait_descs.append(f"{tname}:\n{desc}")
                    break

        sources.add(source)
        rows.append({
            'n': name, 'src': source,
            'sz': size.title() if size else '\u2014',
            'sp': speed_str,
            'asi': ', '.join(asi_strs) if asi_strs else '\u2014',
            'traits': ', '.join(trait_names) if trait_names else '\u2014',
            'desc': '\n\n'.join(trait_descs) if trait_descs else '',
        })

    src_opts = ''.join(f'<option value="{s}">{s.upper()}</option>' for s in sorted(sources))
    filters = (
        f'<input type="text" id="qs" placeholder="Search races, traits\u2026" oninput="fil()">'
        f'<label>Source<select id="fsr" onchange="fil()"><option value="">All Sources</option>{src_opts}</select></label>'
    )
    data_js = json.dumps(rows, ensure_ascii=False)
    js = f"""const DATA={data_js};
let F=DATA.slice(),open=-1;
const SK=[r=>r.n,r=>r.src,r=>r.sz,r=>r.sp,r=>r.asi,r=>r.traits];
{JS_SORT}
function render(){{
  const h=[];
  F.forEach((r,i)=>{{
    h.push(`<tr onclick="tog(${{i}})"${{open===i?' class="active"':''}}>`+
      `<td>${{esc(r.n)}}</td><td>${{esc(r.src).toUpperCase()}}</td>`+
      `<td>${{esc(r.sz)}}</td><td>${{esc(r.sp)}}</td>`+
      `<td style="font-size:12px">${{esc(r.asi)}}</td>`+
      `<td style="font-size:12px">${{esc(r.traits)}}</td></tr>`);
    h.push(`<tr class="desc-row" style="display:${{open===i?'':'none'}}"><td colspan="6">`+
      `<div class="desc-content">${{esc(r.desc||r.traits)}}</div></td></tr>`);
  }});
  document.getElementById('tb').innerHTML=h.join('');
  document.getElementById('cnt').textContent=F.length+'/'+DATA.length;
}}
function tog(i){{open=open===i?-1:i;render();}}
function fil(){{
  const q=document.getElementById('qs').value.toLowerCase();
  const fs=document.getElementById('fsr').value;
  F=DATA.filter(r=>
    (!q||(r.n+' '+r.traits+' '+r.asi).toLowerCase().includes(q))&&
    (!fs||r.src===fs));
  open=-1;render();
}}
render();"""

    return page(
        'Races \u2014 5e Reference', '\U0001f9dd',
        filters,
        th(['Name','Source','Size','Speed','Ability Score Increase','Racial Traits']),
        js
    )

# ─── 8. classes ────────────────────────────────────────────────────────────

def build_classes():
    files = sorted(glob.glob(str(DATA_DIR / 'class_*.rpg.json')))
    rows = []
    sources = set()

    for fp in files:
        d = load_json(fp)
        if not d: continue
        s = d.get('stats', {})
        name = gv(s, 'name') or ''
        if not name: continue
        source   = gv(s, 'source') or ''
        hit_die  = gv(s, 'hit_die') or ''
        spell_ab = gv(s, 'spellcasting_ability') or ''

        # Saving throw proficiencies -> hints at primary ability
        saves = []
        for ab in ['strength','dexterity','constitution','intelligence','wisdom','charisma']:
            if gv(s, f'{ab}_saving_throw_proficiency'):
                saves.append(ab.title())

        primary = spell_ab.title() if spell_ab else (', '.join(saves[:2]) if saves else '\u2014')

        # Archetypes / subclasses
        archetypes_val = (s.get('archetypes') or {}).get('value', [])
        sub_names = []
        if isinstance(archetypes_val, list):
            for a in archetypes_val:
                if isinstance(a, dict):
                    an = ((a.get('stats',{}).get('name') or {}).get('value') or '')
                    if an: sub_names.append(an)

        # Features
        feats_val = (s.get('features') or {}).get('value', [])
        feat_names = []
        for f in feats_val:
            if isinstance(f, dict):
                fn = ((f.get('stats',{}).get('name') or {}).get('value') or '')
                if fn: feat_names.append(fn)

        desc_parts = []
        if sub_names:
            desc_parts.append(f"Subclasses ({len(sub_names)}):\n{', '.join(sub_names)}")
        if feat_names:
            desc_parts.append(f"Class Features:\n{', '.join(feat_names)}")

        sources.add(source)
        rows.append({
            'n': name, 'src': source, 'hd': hit_die, 'prim': primary,
            'nsub': len(sub_names), 'subs': sub_names,
            'desc': '\n\n'.join(desc_parts) if desc_parts else '',
        })

    src_opts = ''.join(f'<option value="{s}">{s.upper()}</option>' for s in sorted(sources))
    filters = (
        f'<input type="text" id="qs" placeholder="Search classes\u2026" oninput="fil()">'
        f'<label>Source<select id="fsr" onchange="fil()"><option value="">All Sources</option>{src_opts}</select></label>'
    )
    data_js = json.dumps(rows, ensure_ascii=False)
    js = f"""const DATA={data_js};
let F=DATA.slice(),open=-1;
const SK=[r=>r.n,r=>r.src,r=>r.hd,r=>r.prim,r=>r.nsub];
{JS_SORT}
function render(){{
  const h=[];
  F.forEach((r,i)=>{{
    h.push(`<tr onclick="tog(${{i}})"${{open===i?' class="active"':''}}>`+
      `<td>${{esc(r.n)}}</td><td>${{esc(r.src).toUpperCase()}}</td>`+
      `<td>${{esc(r.hd||'\u2014')}}</td><td>${{esc(r.prim)}}</td>`+
      `<td>${{r.nsub}}</td></tr>`);
    h.push(`<tr class="desc-row" style="display:${{open===i?'':'none'}}"><td colspan="5">`+
      `<div class="desc-content">${{esc(r.desc||'\u2014')}}</div></td></tr>`);
  }});
  document.getElementById('tb').innerHTML=h.join('');
  document.getElementById('cnt').textContent=F.length+'/'+DATA.length;
}}
function tog(i){{open=open===i?-1:i;render();}}
function fil(){{
  const q=document.getElementById('qs').value.toLowerCase();
  const fs=document.getElementById('fsr').value;
  F=DATA.filter(r=>
    (!q||(r.n+' '+r.prim+' '+r.hd).toLowerCase().includes(q))&&
    (!fs||r.src===fs));
  open=-1;render();
}}
render();"""

    return page(
        'Classes \u2014 5e Reference', '\U0001f4da',
        filters,
        th(['Name','Source','Hit Die','Primary Ability','# Subclasses']),
        js
    )

# ─── run all ───────────────────────────────────────────────────────────────

PAGES = [
    ('monsters.html',    build_monsters),
    ('weapons.html',     build_weapons),
    ('armor.html',       build_armor),
    ('items.html',       build_items),
    ('conditions.html',  build_conditions),
    ('backgrounds.html', build_backgrounds),
    ('races.html',       build_races),
    ('classes.html',     build_classes),
]

if __name__ == '__main__':
    print(f"Output dir: {BASE}\n")
    for fname, fn in PAGES:
        print(f"Building {fname}...")
        try:
            html = fn()
            out  = BASE / fname
            out.write_text(html, encoding='utf-8')
            size = out.stat().st_size
            print(f"  \u2713 {fname}: {size:,} bytes")
        except Exception as e:
            import traceback
            print(f"  \u2717 {fname}: {e}")
            traceback.print_exc()
    print("\nDone!")
