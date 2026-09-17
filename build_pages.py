#!/usr/bin/env python3
"""Build 8 D&D 5e reference HTML pages for the PGW site."""

import json, glob, os, re, html as html_mod
from pathlib import Path

BASE = Path('/Users/dylan/.openclaw/workspace/dnd/systems/5e/resource_instances')
OUT  = Path('/Users/dylan/.openclaw/workspace/dnd')
SRD  = Path('/Users/dylan/.openclaw/workspace/dnd/srd')

# ─── Helpers ──────────────────────────────────────────────────────────────────

def sv(d, *keys):
    """Walk nested stats dicts and return .value at the final key."""
    for k in keys:
        if isinstance(d, dict): d = d.get(k, {})
        else: return None
    return d.get('value') if isinstance(d, dict) else d

def esc(s):
    return html_mod.escape(str(s)) if s is not None else ''

def js_str(s):
    """Escape a Python string for embedding in a JS string literal."""
    s = str(s) if s is not None else ''
    return s.replace('\\','\\\\').replace("'","\\'").replace('\n','\\n').replace('\r','')

def get_weight(stats):
    w = stats.get('weight', {})
    if not isinstance(w, dict): return '—'
    wv = w.get('value')
    if isinstance(wv, (int, float)): return str(wv)
    if isinstance(wv, dict) and 'stats' in wv:
        val = wv['stats'].get('value', {})
        if isinstance(val, dict): val = val.get('value')
        if val is not None: return str(val)
    return '—'

def get_cost(stats):
    c = stats.get('cost', {})
    if not isinstance(c, dict): return '—'
    cv = c.get('value')
    if isinstance(cv, dict) and 'stats' in cv:
        cs = cv['stats']
        amt = cs.get('value', {})
        if isinstance(amt, dict): amt = amt.get('value')
        unit = cs.get('unit', {})
        if isinstance(unit, dict): unit = unit.get('value', 'gp')
        else: unit = 'gp'
        if amt is not None: return f"{amt} {unit}"
    elif isinstance(cv, (int, float, str)): return str(cv)
    return '—'

def fmt_cr(cr_str):
    if not cr_str: return '—'
    s = cr_str.replace('cr_', '')
    return {'0':'0','1_8':'1/8','1_4':'1/4','1_2':'1/2'}.get(s, s)

def cr_num(cr_str):
    if not cr_str: return 99
    m = {'cr_0':0,'cr_1_8':0.125,'cr_1_4':0.25,'cr_1_2':0.5}
    if cr_str in m: return m[cr_str]
    try: return float(cr_str.replace('cr_',''))
    except: return 99

def hp_dice(hp_obj):
    if not isinstance(hp_obj, dict): return str(hp_obj) if hp_obj else '—'
    try:
        s = hp_obj['stats']
        da = s['dice_amount']['value']
        dt = s['dice_type']['value']
        c  = (s.get('constant') or {}).get('value', 0) or 0
        if c > 0: return f"{da}{dt}+{c}"
        if c < 0: return f"{da}{dt}{c}"
        return f"{da}{dt}"
    except: return '—'

def ab_mod(score):
    if score is None: return ''
    m = (int(score) - 10) // 2
    return f"+{m}" if m >= 0 else str(m)

def load_all(pattern):
    result = []
    for fp in sorted(glob.glob(str(BASE / pattern))):
        try:
            with open(fp) as f: result.append(json.load(f))
        except: pass
    return result

# ─── Common HTML fragments ─────────────────────────────────────────────────────

PAGE_CSS = ("*{box-sizing:border-box;margin:0;padding:0}"
"body{background:#0e0e14;color:#ddd;font-family:'Segoe UI',sans-serif;font-size:14px}"
"h1{text-align:center;color:#a78bfa;padding:18px;font-size:1.4rem;letter-spacing:2px}"
"h1 span{color:#6d28d9}"
".filters{display:flex;flex-wrap:wrap;gap:9px;padding:12px 18px;background:#15151e;border-bottom:1px solid #2a2a3a;align-items:center}"
".filters input,.filters select{background:#1e1e2e;border:1px solid #3a3a5a;color:#ddd;padding:6px 10px;border-radius:6px;font-size:13px}"
".filters input{width:210px}"
".filters input:focus,.filters select:focus{outline:none;border-color:#7c3aed}"
".count{margin-left:auto;color:#666;font-size:12px;white-space:nowrap}"
".table-wrap{overflow-x:auto;padding:0 10px 40px}"
"table{width:100%;border-collapse:collapse;margin-top:10px}"
"thead th{background:#1a1a2e;color:#a78bfa;font-size:11px;text-transform:uppercase;letter-spacing:1px;padding:9px 11px;text-align:left;cursor:pointer;border-bottom:2px solid #3a2a6a;white-space:nowrap;user-select:none}"
"thead th:hover{color:#c4b5fd}"
"thead th.asc::after{content:' \u25b2'}"
"thead th.desc::after{content:' \u25bc'}"
"tbody tr:not(.desc-row){cursor:pointer;border-bottom:1px solid #1a1a28}"
"tbody tr:not(.desc-row):hover{background:#1a1a2e}"
"tbody tr:not(.desc-row).active{background:#1e1530}"
"td{padding:8px 11px;vertical-align:middle}"
"td:first-child{color:#e2d9f3}"
".desc-row td{padding:0;background:#0d0d18}"
".desc-row{display:none}"
".desc-content{padding:12px 18px;border-left:3px solid #6d28d9;margin:4px 10px 10px;border-radius:0 6px 6px 0;font-size:13px;color:#bbb;line-height:1.6}"
".back{display:block;color:#7c3aed;font-size:12px;padding:8px 18px;text-decoration:none;width:fit-content}"
".back:hover{color:#a78bfa}"
".pager{display:flex;gap:6px;padding:8px 18px;align-items:center;flex-wrap:wrap}"
".pager button{background:#1e1e2e;border:1px solid #3a3a5a;color:#888;padding:4px 10px;border-radius:4px;cursor:pointer;font-size:12px}"
".pager button:hover,.pager button.on{background:#2a1a4a;border-color:#6d28d9;color:#c4b5fd}"
".pager .pi{color:#666;font-size:12px}"
".ab-grid{display:grid;grid-template-columns:repeat(6,1fr);gap:6px;max-width:420px}"
".ab-cell{text-align:center;background:#1a1a2e;border-radius:4px;padding:4px}"
".ab-label{font-size:10px;color:#888;text-transform:uppercase}"
".ab-val{font-size:14px;color:#e2d9f3}"
".ab-mod{font-size:11px;color:#a78bfa}"
"span.nd{color:#555}"
)

SORT_JS = """var _sc=-1,_sa=true;
function sortBy(col){
  document.querySelectorAll('thead th').forEach(function(t){t.classList.remove('asc','desc');});
  if(_sc===col){_sa=!_sa;}else{_sc=col;_sa=true;}
  document.querySelectorAll('thead th')[col].classList.add(_sa?'asc':'desc');
  applyFilters();
}
function toggleRow(tr){
  var next=tr.nextElementSibling;
  if(!next||!next.classList.contains('desc-row'))return;
  var was=tr.classList.contains('active');
  document.querySelectorAll('tbody tr.active').forEach(function(r){r.classList.remove('active');});
  document.querySelectorAll('.desc-row').forEach(function(r){r.style.display='none';});
  if(!was){tr.classList.add('active');next.style.display='';}
}
"""

def page_head(title, icon, subtitle=''):
    s = f'<p style="text-align:center;color:#555;font-size:12px;padding-bottom:12px">{esc(subtitle)}</p>' if subtitle else ''
    return (f'<!DOCTYPE html><html lang="en"><head>'
            f'<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{esc(title)}</title>'
            f'<style>{PAGE_CSS}</style></head><body>'
            f'<a class="back" href="index.html">\u2190 Back to Index</a>'
            f'<h1>{icon} {esc(title)}</h1>{s}')

def nd(s): return f'<span class="nd">{esc(s)}</span>'

# ─── 1. MONSTERS ──────────────────────────────────────────────────────────────

def build_monsters():
    print("Building monsters.html...")
    rows = load_all('monster_*.json')
    data = []
    sources = set()
    cr_vals = set()
    types = set()
    for d in rows:
        s = d['stats']
        name   = sv(s,'name') or ''
        source = sv(s,'source') or 'SRD'
        cr_raw = sv(s,'cr') or ''
        cr_fmt = fmt_cr(cr_raw)
        cr_n   = cr_num(cr_raw)
        mtype  = sv(s,'type') or ''
        tag    = sv(s,'tag') or ''
        ac     = sv(s,'armor_class') or ''
        hp_obj = sv(s,'hit_points')
        hp     = hp_dice(hp_obj) if isinstance(hp_obj, dict) else (str(hp_obj) if hp_obj else '—')
        spd    = sv(s,'speed') or 0
        fly    = sv(s,'fly_speed') or 0
        swim   = sv(s,'swim_speed') or 0
        bur    = sv(s,'burrow_speed') or 0
        cli    = sv(s,'climb_speed') or 0
        xp     = sv(s,'xp') or 0
        str_   = sv(s,'strength_score')
        dex_   = sv(s,'dexterity_score')
        con_   = sv(s,'constitution_score')
        int_   = sv(s,'intelligence_score')
        wis_   = sv(s,'wisdom_score')
        cha_   = sv(s,'charisma_score')

        # speed string
        spd_parts = []
        if spd: spd_parts.append(f"{spd} ft.")
        if fly: spd_parts.append(f"fly {fly}")
        if swim: spd_parts.append(f"swim {swim}")
        if bur: spd_parts.append(f"burrow {bur}")
        if cli: spd_parts.append(f"climb {cli}")
        spd_str = ', '.join(spd_parts) if spd_parts else '0 ft.'

        type_tag = mtype + (f' ({tag})' if tag else '')
        sources.add(source)
        if cr_raw: cr_vals.add(cr_raw)
        if mtype: types.add(mtype)

        data.append({
            'n': name, 'src': source, 'cr': cr_fmt, 'crn': cr_n,
            't': type_tag, 'mt': mtype,
            'ac': ac, 'hp': hp, 'spd': spd_str, 'xp': xp,
            'str': str_, 'dex': dex_, 'con': con_,
            'int': int_, 'wis': wis_, 'cha': cha_,
        })

    # Sort CR options numerically
    cr_sorted = sorted(cr_vals, key=cr_num)
    cr_options = '\n'.join(
        f'<option value="{esc(c)}">{esc(fmt_cr(c))}</option>'
        for c in cr_sorted
    )
    src_options = '\n'.join(f'<option value="{esc(s)}">{esc(s)}</option>' for s in sorted(sources))
    type_options = '\n'.join(f'<option value="{esc(t)}">{esc(t.title())}</option>' for t in sorted(types))

    data_json = json.dumps(data, ensure_ascii=False)

    html = page_head('Monsters — 5e', '🐉', f'{len(data):,} monsters')
    html += f'''
<div class="filters">
  <input type="text" id="fsearch" placeholder="Search name or type…" oninput="applyFilters()">
  <select id="fcr" onchange="applyFilters()"><option value="">All CRs</option>{cr_options}</select>
  <select id="ftype" onchange="applyFilters()"><option value="">All Types</option>{type_options}</select>
  <select id="fsrc" onchange="applyFilters()"><option value="">All Sources</option>{src_options}</select>
  <span class="count" id="cnt"></span>
</div>
<div class="pager" id="pager"></div>
<div class="table-wrap">
<table><thead><tr>
  <th onclick="sortBy(0)">Name</th>
  <th onclick="sortBy(1)">CR</th>
  <th onclick="sortBy(2)">Type</th>
  <th onclick="sortBy(3)">AC</th>
  <th onclick="sortBy(4)">HP</th>
  <th onclick="sortBy(5)">Speed</th>
  <th onclick="sortBy(6)">XP</th>
  <th onclick="sortBy(7)">Source</th>
</tr></thead><tbody id="tbody"></tbody></table>
</div>
<script>
var ALL={data_json};
var _sc=-1,_sa=true,_page=0,_PER=75,_filtered=[];
var _COLS=['n','crn','t','ac','hp','spd','xp','src'];
function sortBy(col){{
  document.querySelectorAll('thead th').forEach(function(t){{t.classList.remove('asc','desc');}});
  if(_sc===col){{_sa=!_sa;}}else{{_sc=col;_sa=true;}}
  document.querySelectorAll('thead th')[col].classList.add(_sa?'asc':'desc');
  _page=0; render();
}}
function applyFilters(){{
  var q=(document.getElementById('fsearch').value||'').toLowerCase();
  var fcr=document.getElementById('fcr').value;
  var ft=document.getElementById('ftype').value;
  var fs=document.getElementById('fsrc').value;
  _filtered=ALL.filter(function(m){{
    if(q && m.n.toLowerCase().indexOf(q)<0 && m.t.toLowerCase().indexOf(q)<0) return false;
    if(fcr && m.cr!==fcr) return false;
    if(ft && m.mt!==ft) return false;
    if(fs && m.src!==fs) return false;
    return true;
  }});
  if(_sc>=0){{
    var col=_COLS[_sc];
    _filtered.sort(function(a,b){{
      var av=a[col]||'',bv=b[col]||'';
      if(typeof av==='number'&&typeof bv==='number') return _sa?av-bv:bv-av;
      av=String(av).toLowerCase(); bv=String(bv).toLowerCase();
      return _sa?(av<bv?-1:av>bv?1:0):(bv<av?-1:bv>av?1:0);
    }});
  }}
  _page=0; render();
}}
function esc(s){{return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}}
function ab(score,label){{
  if(score==null) return '<div class="ab-cell"><div class="ab-label">'+label+'</div><div class="ab-val">—</div><div class="ab-mod"></div></div>';
  var m=Math.floor((score-10)/2); var ms=m>=0?'+'+m:String(m);
  return '<div class="ab-cell"><div class="ab-label">'+label+'</div><div class="ab-val">'+score+'</div><div class="ab-mod">'+ms+'</div></div>';
}}
function render(){{
  var start=_page*_PER, end=Math.min(start+_PER,_filtered.length);
  var html='';
  for(var i=start;i<end;i++){{
    var m=_filtered[i];
    var id='m'+i;
    html+='<tr onclick="toggle(this,\\''+id+'\\')"><td><strong>'+esc(m.n)+'</strong></td>';
    html+='<td>'+esc(m.cr)+'</td><td>'+esc(m.t)+'</td>';
    html+='<td>'+esc(m.ac||'—')+'</td><td>'+esc(m.hp)+'</td>';
    html+='<td style="white-space:nowrap;font-size:12px">'+esc(m.spd)+'</td>';
    html+='<td>'+(m.xp?m.xp.toLocaleString():'—')+'</td>';
    html+='<td style="color:#888;font-size:12px">'+esc(m.src)+'</td></tr>';
    html+='<tr class="desc-row" id="dr'+id+'" style="display:none"><td colspan="8">';
    html+='<div class="desc-content"><div class="ab-grid">';
    html+=ab(m.str,'STR')+ab(m.dex,'DEX')+ab(m.con,'CON');
    html+=ab(m.int,'INT')+ab(m.wis,'WIS')+ab(m.cha,'CHA');
    html+='</div></div></td></tr>';
  }}
  document.getElementById('tbody').innerHTML=html;
  document.getElementById('cnt').textContent=_filtered.length.toLocaleString()+' of '+ALL.length.toLocaleString()+' monsters';
  renderPager(end-start);
}}
function toggle(tr, id){{
  var dr=document.getElementById('dr'+id);
  var was=tr.classList.contains('active');
  document.querySelectorAll('tbody tr.active').forEach(function(r){{r.classList.remove('active');}});
  document.querySelectorAll('.desc-row').forEach(function(r){{r.style.display='none';}});
  if(!was){{tr.classList.add('active');dr.style.display='';}}
}}
function renderPager(){{
  var pages=Math.ceil(_filtered.length/_PER);
  if(pages<=1){{document.getElementById('pager').innerHTML='';return;}}
  var h='<span class="pi">Page:</span> ';
  var start=Math.max(0,_page-4), end=Math.min(pages,_page+5);
  if(start>0) h+='<button onclick="goPage(0)">1</button><span class="pi">…</span> ';
  for(var p=start;p<end;p++){{
    h+='<button class="'+(p===_page?'on':'')+'" onclick="goPage('+p+')">'+(p+1)+'</button> ';
  }}
  if(end<pages) h+='<span class="pi">…</span><button onclick="goPage('+(pages-1)+')">'+pages+'</button>';
  document.getElementById('pager').innerHTML=h;
}}
function goPage(p){{_page=p;render();window.scrollTo(0,0);}}
applyFilters();
</script>
'''.replace('{data_json}', data_json)

    (OUT / 'monsters.html').write_text(html, encoding='utf-8')
    print(f"  monsters.html — {len(data):,} monsters, {len(html)//1024} KB")


# ─── 2. WEAPONS ───────────────────────────────────────────────────────────────

def build_weapons():
    print("Building weapons.html...")
    rows = load_all('weapon_*.rpg.json')
    sources = set()
    cats = set()
    wtypes = set()

    def get_damage(s):
        dd = sv(s,'damage_dice')
        if isinstance(dd, list) and dd:
            try:
                dice = dd[0]['stats']['dices']['value']
                if dice:
                    da = dice[0]['stats']['dice_amount']['value']
                    dt = dice[0]['stats']['dice_type']['value']
                    dtype = dd[0]['stats'].get('type', {})
                    if isinstance(dtype, dict): dtype = dtype.get('value', '')
                    return f"{da}{dt}", str(dtype) if dtype else '—'
            except: pass
        return '—', '—'

    def get_props(s):
        props = []
        if sv(s,'is_finesse'): props.append('Finesse')
        if sv(s,'is_reach'): props.append('Reach')
        if sv(s,'is_two_handed'): props.append('Two-handed')
        if sv(s,'is_versatile'): props.append('Versatile')
        if sv(s,'is_thrown'):
            tr_ = sv(s,'thrown_range')
            props.append(f"Thrown ({tr_})" if tr_ else 'Thrown')
        if sv(s,'is_light'): props.append('Light')
        if sv(s,'is_heavy'): props.append('Heavy')
        if sv(s,'is_loading'): props.append('Loading')
        if sv(s,'is_range'): props.append('Ranged')
        return ', '.join(props) if props else '—'

    tbody = ''
    all_rows = []
    for d in rows:
        s = d['stats']
        name   = sv(s,'name') or ''
        source = (sv(s,'source') or 'SRD').upper()
        is_sim = sv(s,'is_simple')
        cat    = 'Simple' if is_sim else 'Martial'
        wtype  = (sv(s,'type') or '').replace('_',' ').title()
        dmg, dmg_type = get_damage(s)
        props  = get_props(s)
        cost   = get_cost(s)
        weight = get_weight(s)
        sources.add(source)
        cats.add(cat)
        if wtype: wtypes.add(wtype)
        all_rows.append((name, cat, wtype, dmg, dmg_type, props, cost, weight, source))

    # Build sortable rows
    for (name, cat, wtype, dmg, dmg_type, props, cost, weight, source) in sorted(all_rows, key=lambda x: x[0].lower()):
        dc = f'data-name="{esc(name.lower())}" data-cat="{esc(cat)}" data-type="{esc(wtype)}" data-src="{esc(source)}"'
        tbody += f'<tr {dc} onclick="toggleRow(this)"><td><strong>{esc(name)}</strong></td>'
        tbody += f'<td>{esc(cat)}</td><td style="font-size:12px">{esc(wtype)}</td>'
        tbody += f'<td>{esc(dmg)}</td><td>{esc(dmg_type)}</td>'
        tbody += f'<td style="font-size:12px">{esc(props)}</td>'
        tbody += f'<td style="font-size:12px">{esc(cost)}</td>'
        tbody += f'<td style="font-size:12px">{esc(weight)}</td>'
        tbody += f'<td style="color:#888;font-size:12px">{esc(source)}</td></tr>'
        tbody += f'<tr class="desc-row"><td colspan="9"></td></tr>'

    cat_opts = '\n'.join(f'<option value="{esc(c)}">{esc(c)}</option>' for c in sorted(cats))
    type_opts = '\n'.join(f'<option value="{esc(t)}">{esc(t)}</option>' for t in sorted(wtypes))
    src_opts  = '\n'.join(f'<option value="{esc(s)}">{esc(s)}</option>' for s in sorted(sources))

    html = page_head('Weapons — 5e', '⚔️', f'{len(all_rows)} weapons')
    html += f'''
<div class="filters">
  <input type="text" id="fsearch" placeholder="Search name…" oninput="applyFilters()">
  <select id="fcat" onchange="applyFilters()"><option value="">All Categories</option>{cat_opts}</select>
  <select id="ftype" onchange="applyFilters()"><option value="">All Types</option>{type_opts}</select>
  <select id="fsrc" onchange="applyFilters()"><option value="">All Sources</option>{src_opts}</select>
  <span class="count" id="cnt"></span>
</div>
<div class="table-wrap">
<table><thead><tr>
  <th onclick="sortBy(0)">Name</th>
  <th onclick="sortBy(1)">Category</th>
  <th onclick="sortBy(2)">Type</th>
  <th onclick="sortBy(3)">Damage</th>
  <th onclick="sortBy(4)">Dmg Type</th>
  <th onclick="sortBy(5)">Properties</th>
  <th onclick="sortBy(6)">Cost</th>
  <th onclick="sortBy(7)">Weight</th>
  <th onclick="sortBy(8)">Source</th>
</tr></thead><tbody id="tbody">{tbody}</tbody></table>
</div>
<script>
{SORT_JS}
function applyFilters(){{
  var q=(document.getElementById('fsearch').value||'').toLowerCase();
  var fcat=document.getElementById('fcat').value;
  var ft=document.getElementById('ftype').value;
  var fs=document.getElementById('fsrc').value;
  var rows=document.querySelectorAll('#tbody tr:not(.desc-row)');
  var vis=0;
  rows.forEach(function(tr){{
    var nm=tr.getAttribute('data-name')||'';
    var cat=tr.getAttribute('data-cat')||'';
    var wt=tr.getAttribute('data-type')||'';
    var src=tr.getAttribute('data-src')||'';
    var show=(!q||nm.indexOf(q)>=0)&&(!fcat||cat===fcat)&&(!ft||wt===ft)&&(!fs||src===fs);
    tr.style.display=show?'':'none';
    var next=tr.nextElementSibling;
    if(next&&next.classList.contains('desc-row'))next.style.display='none';
    if(show)vis++;
  }});
  if(_sc>=0) sortRows();
  document.getElementById('cnt').textContent=vis+' weapons';
}}
function sortRows(){{
  var tbody=document.getElementById('tbody');
  var mainRows=[...tbody.querySelectorAll('tr:not(.desc-row)')].filter(r=>r.style.display!=='none');
  mainRows.sort(function(a,b){{
    var av=a.querySelectorAll('td')[_sc]?.textContent||'';
    var bv=b.querySelectorAll('td')[_sc]?.textContent||'';
    return _sa?(av<bv?-1:av>bv?1:0):(bv<av?-1:bv>av?1:0);
  }});
  mainRows.forEach(function(tr){{
    var next=tr.nextElementSibling;
    tbody.appendChild(tr);
    if(next&&next.classList.contains('desc-row'))tbody.appendChild(next);
  }});
}}
applyFilters();
</script>
'''
    (OUT / 'weapons.html').write_text(html, encoding='utf-8')
    print(f"  weapons.html — {len(all_rows)} weapons, {len(html)//1024} KB")


# ─── 3. ARMOR ─────────────────────────────────────────────────────────────────

def build_armor():
    print("Building armor.html...")
    rows = load_all('armor_*.rpg.json')
    sources = set()
    types_ = set()
    all_rows = []
    for d in rows:
        s = d['stats']
        name    = sv(s,'name') or ''
        source  = (sv(s,'source') or 'SRD').upper()
        atype   = (sv(s,'type') or '').title()
        base_ac = sv(s,'base_ac') or '—'
        req_str = sv(s,'required_strength') or '—'
        stealth = sv(s,'impose_stealth_disadvantage')
        stealth_str = '✓' if stealth else '—'
        cost    = get_cost(s)
        weight  = get_weight(s)
        sources.add(source)
        if atype: types_.add(atype)
        all_rows.append((name, atype, base_ac, req_str, stealth_str, cost, weight, source))

    tbody = ''
    for (name, atype, base_ac, req_str, stealth_str, cost, weight, source) in sorted(all_rows, key=lambda x: x[0].lower()):
        dc = f'data-name="{esc(name.lower())}" data-type="{esc(atype)}" data-src="{esc(source)}"'
        tbody += f'<tr {dc}><td><strong>{esc(name)}</strong></td>'
        tbody += f'<td>{esc(atype)}</td><td>{esc(str(base_ac))}</td>'
        tbody += f'<td>{esc(str(req_str))}</td>'
        tbody += (f'<td style="color:#f87171">{esc(stealth_str)}</td>'
                  if stealth_str=='✓' else f'<td>{nd("—")}</td>')
        tbody += f'<td style="font-size:12px">{esc(cost)}</td>'
        tbody += f'<td style="font-size:12px">{esc(weight)}</td>'
        tbody += f'<td style="color:#888;font-size:12px">{esc(source)}</td></tr>'

    type_opts = '\n'.join(f'<option value="{esc(t)}">{esc(t)}</option>' for t in sorted(types_))
    src_opts  = '\n'.join(f'<option value="{esc(s)}">{esc(s)}</option>' for s in sorted(sources))

    html = page_head('Armor — 5e', '🛡️', f'{len(all_rows)} armor pieces')
    html += f'''
<div class="filters">
  <input type="text" id="fsearch" placeholder="Search name…" oninput="applyFilters()">
  <select id="ftype" onchange="applyFilters()"><option value="">All Types</option>{type_opts}</select>
  <select id="fsrc" onchange="applyFilters()"><option value="">All Sources</option>{src_opts}</select>
  <span class="count" id="cnt"></span>
</div>
<div class="table-wrap">
<table><thead><tr>
  <th onclick="sortBy(0)">Name</th>
  <th onclick="sortBy(1)">Type</th>
  <th onclick="sortBy(2)">Base AC</th>
  <th onclick="sortBy(3)">Req STR</th>
  <th onclick="sortBy(4)">Stealth Disadv</th>
  <th onclick="sortBy(5)">Cost</th>
  <th onclick="sortBy(6)">Weight</th>
  <th onclick="sortBy(7)">Source</th>
</tr></thead><tbody id="tbody">{tbody}</tbody></table>
</div>
<script>
{SORT_JS}
function applyFilters(){{
  var q=(document.getElementById('fsearch').value||'').toLowerCase();
  var ft=document.getElementById('ftype').value;
  var fs=document.getElementById('fsrc').value;
  var rows=document.querySelectorAll('#tbody tr');
  var vis=0;
  rows.forEach(function(tr){{
    var nm=tr.getAttribute('data-name')||'';
    var t=tr.getAttribute('data-type')||'';
    var s=tr.getAttribute('data-src')||'';
    var show=(!q||nm.indexOf(q)>=0)&&(!ft||t===ft)&&(!fs||s===fs);
    tr.style.display=show?'':'none';
    if(show)vis++;
  }});
  document.getElementById('cnt').textContent=vis+' items';
}}
applyFilters();
</script>
'''
    (OUT / 'armor.html').write_text(html, encoding='utf-8')
    print(f"  armor.html — {len(all_rows)} pieces, {len(html)//1024} KB")


# ─── 4. ITEMS ─────────────────────────────────────────────────────────────────

def build_items():
    print("Building items.html...")
    rows = load_all('item_*.rpg.json')
    sources = set()
    rarities = set()
    types_ = set()
    all_rows = []
    for d in rows:
        s = d['stats']
        name    = sv(s,'name') or ''
        itype   = (sv(s,'type') or '').replace('_',' ').title()
        rarity  = (sv(s,'rarity') or 'common').title()
        is_magic = bool(sv(s,'is_magic'))
        attune  = bool(sv(s,'requires_attunement'))
        cursed  = bool(sv(s,'is_cursed'))
        weight  = get_weight(s)
        # Try direct weight value
        if weight == '—':
            wv = s.get('weight', {})
            if isinstance(wv, dict):
                weight = str(wv.get('value', '—')) if wv.get('value') not in (None, '') else '—'
        desc    = sv(s,'description') or ''
        source  = (sv(s,'source') or 'SRD').upper()
        sources.add(source)
        if rarity: rarities.add(rarity)
        if itype:  types_.add(itype)
        all_rows.append((name, itype, rarity, is_magic, attune, cursed, weight, desc, source))

    tbody = ''
    for (name, itype, rarity, is_magic, attune, cursed, weight, desc, source) in sorted(all_rows, key=lambda x: x[0].lower()):
        dc = (f'data-name="{esc(name.lower())}" data-rarity="{esc(rarity.lower())}"'
              f' data-type="{esc(itype)}" data-src="{esc(source)}"'
              f' data-magic="{str(is_magic).lower()}"')
        tbody += f'<tr {dc} onclick="toggleRow(this)"><td><strong>{esc(name)}</strong></td>'
        tbody += f'<td style="font-size:12px">{esc(itype) or nd("—")}</td>'
        tbody += f'<td>{esc(rarity)}</td>'
        tbody += f'<td>{"✓" if is_magic else nd("—")}</td>'
        tbody += f'<td>{"✓" if attune else nd("—")}</td>'
        tbody += f'<td>{"✓" if cursed else nd("—")}</td>'
        tbody += f'<td style="font-size:12px">{esc(weight)}</td>'
        tbody += f'<td style="color:#888;font-size:12px">{esc(source)}</td></tr>'
        tbody += f'<tr class="desc-row"><td colspan="8"><div class="desc-content"><p>{esc(desc) if desc else nd("No description.")}</p></div></td></tr>'

    rar_opts  = '\n'.join(f'<option value="{esc(r.lower())}">{esc(r)}</option>' for r in ['Common','Uncommon','Rare','Very Rare','Legendary'])
    type_opts = '\n'.join(f'<option value="{esc(t)}">{esc(t)}</option>' for t in sorted(types_))
    src_opts  = '\n'.join(f'<option value="{esc(s)}">{esc(s)}</option>' for s in sorted(sources))

    html = page_head('Magic Items & Equipment — 5e', '💎', f'{len(all_rows)} items')
    html += f'''
<div class="filters">
  <input type="text" id="fsearch" placeholder="Search name…" oninput="applyFilters()">
  <select id="frarity" onchange="applyFilters()"><option value="">All Rarities</option>{rar_opts}</select>
  <select id="ftype" onchange="applyFilters()"><option value="">All Types</option>{type_opts}</select>
  <select id="fmagic" onchange="applyFilters()"><option value="">Magic: All</option><option value="true">Magic Only</option><option value="false">Non-magic Only</option></select>
  <select id="fsrc" onchange="applyFilters()"><option value="">All Sources</option>{src_opts}</select>
  <span class="count" id="cnt"></span>
</div>
<div class="table-wrap">
<table><thead><tr>
  <th onclick="sortBy(0)">Name</th>
  <th onclick="sortBy(1)">Type</th>
  <th onclick="sortBy(2)">Rarity</th>
  <th onclick="sortBy(3)">Magic</th>
  <th onclick="sortBy(4)">Attunement</th>
  <th onclick="sortBy(5)">Cursed</th>
  <th onclick="sortBy(6)">Weight</th>
  <th onclick="sortBy(7)">Source</th>
</tr></thead><tbody id="tbody">{tbody}</tbody></table>
</div>
<script>
{SORT_JS}
function applyFilters(){{
  var q=(document.getElementById('fsearch').value||'').toLowerCase();
  var fr=document.getElementById('frarity').value;
  var ft=document.getElementById('ftype').value;
  var fm=document.getElementById('fmagic').value;
  var fs=document.getElementById('fsrc').value;
  var rows=document.querySelectorAll('#tbody tr:not(.desc-row)');
  var vis=0;
  rows.forEach(function(tr){{
    var nm=tr.getAttribute('data-name')||'';
    var ra=tr.getAttribute('data-rarity')||'';
    var ty=tr.getAttribute('data-type')||'';
    var mg=tr.getAttribute('data-magic')||'';
    var sr=tr.getAttribute('data-src')||'';
    var show=(!q||nm.indexOf(q)>=0)&&(!fr||ra===fr)&&(!ft||ty===ft)&&(!fm||mg===fm)&&(!fs||sr===fs);
    tr.style.display=show?'':'none';
    var next=tr.nextElementSibling;
    if(next&&next.classList.contains('desc-row'))next.style.display='none';
    if(show)vis++;
  }});
  document.getElementById('cnt').textContent=vis+' items';
}}
applyFilters();
</script>
'''
    (OUT / 'items.html').write_text(html, encoding='utf-8')
    print(f"  items.html — {len(all_rows)} items, {len(html)//1024} KB")


# ─── 5. CONDITIONS ────────────────────────────────────────────────────────────

def parse_conditions_srd():
    """Parse srd-conditions.md into list of (name, summary, full_text)."""
    path = SRD / 'srd-conditions.md'
    if not path.exists():
        return []
    text = path.read_text(encoding='utf-8')

    NAMES = ['Blinded','Charmed','Deafened','Exhaustion','Frightened','Grappled',
             'Incapacitated','Invisible','Paralyzed','Petrified','Poisoned',
             'Prone','Restrained','Stunned','Unconscious']

    conditions = []
    # Split by condition name headers
    for i, name in enumerate(NAMES):
        # Find the section for this condition
        start = text.find('\n' + name + '\n')
        if start < 0:
            start = text.find('\n' + name.lower() + '\n')
        if start < 0:
            conditions.append((name, f'See rulebook for {name} condition.', ''))
            continue
        # Find end (next condition name or end of relevant section)
        end = len(text)
        for other in NAMES:
            if other == name: continue
            pos = text.find('\n' + other + '\n', start + 1)
            if pos > start and pos < end:
                end = pos
        block = text[start:end].strip()
        lines = block.split('\n')
        # First line is the condition name, rest is description
        desc_lines = lines[1:] if lines[0].strip() == name else lines
        desc = ' '.join(l.strip() for l in desc_lines if l.strip()).strip()
        # Summary = first bullet point or first sentence
        summary = ''
        for l in desc_lines:
            l = l.strip()
            if l.startswith('•'):
                summary = l.lstrip('•').strip()
                break
            elif l and not l.startswith('#'):
                summary = l[:120]
                break
        conditions.append((name, summary, '\n'.join(desc_lines).strip()))
    return conditions

def build_conditions():
    print("Building conditions.html...")
    conditions = parse_conditions_srd()
    if not conditions:
        # Hardcode fallback
        conditions = [
            ('Blinded', "Can't see; auto-fails sight checks; attacks against have advantage.", ''),
            ('Charmed', "Can't attack charmer; charmer has advantage on social checks.", ''),
            ('Deafened', "Can't hear; auto-fails hearing checks.", ''),
            ('Exhaustion', 'Measured in 6 levels; each level applies cumulative effects.', ''),
            ('Frightened', 'Disadvantage on checks/attacks while source in sight; can\'t move closer.', ''),
            ('Grappled', 'Speed becomes 0; ends if grappler is incapacitated.', ''),
            ('Incapacitated', "Can't take actions or reactions.", ''),
            ('Invisible', 'Unseen; advantage on attacks; disadvantage on attacks against.', ''),
            ('Paralyzed', 'Incapacitated; auto-fails STR/DEX saves; attacks from adj have advantage and crit.', ''),
            ('Petrified', 'Turned to stone; incapacitated; resistance to all damage.', ''),
            ('Poisoned', 'Disadvantage on attack rolls and ability checks.', ''),
            ('Prone', 'Movement costs double; melee attacks have advantage; ranged attacks have disadvantage.', ''),
            ('Restrained', 'Speed 0; attack rolls have disadvantage; DEX saves have disadvantage.', ''),
            ('Stunned', 'Incapacitated; auto-fails STR/DEX saves; attacks have advantage.', ''),
            ('Unconscious', 'Incapacitated, drops prone; auto-fails STR/DEX saves; attacks crit within 5 ft.', ''),
        ]

    tbody = ''
    for name, summary, full in conditions:
        full_escaped = esc(full).replace('\n', '<br>') if full else esc(summary)
        tbody += f'<tr onclick="toggleRow(this)"><td><strong>{esc(name)}</strong></td>'
        tbody += f'<td style="font-size:13px;color:#bbb">{esc(summary[:120])}{"…" if len(summary)>120 else ""}</td></tr>'
        tbody += f'<tr class="desc-row"><td colspan="2"><div class="desc-content"><p>{full_escaped}</p></div></td></tr>'

    html = page_head('Conditions — 5e', '⚠️', '15 standard conditions')
    html += f'''
<div class="filters">
  <input type="text" id="fsearch" placeholder="Search conditions…" oninput="applyFilters()">
  <span class="count" id="cnt"></span>
</div>
<div class="table-wrap">
<table><thead><tr>
  <th onclick="sortBy(0)">Condition</th>
  <th onclick="sortBy(1)">Summary</th>
</tr></thead><tbody id="tbody">{tbody}</tbody></table>
</div>
<script>
{SORT_JS}
function applyFilters(){{
  var q=(document.getElementById('fsearch').value||'').toLowerCase();
  var rows=document.querySelectorAll('#tbody tr:not(.desc-row)');
  var vis=0;
  rows.forEach(function(tr){{
    var text=tr.textContent.toLowerCase();
    var show=!q||text.indexOf(q)>=0;
    tr.style.display=show?'':'none';
    var next=tr.nextElementSibling;
    if(next&&next.classList.contains('desc-row'))next.style.display='none';
    if(show)vis++;
  }});
  document.getElementById('cnt').textContent=vis+' conditions';
}}
applyFilters();
</script>
'''
    (OUT / 'conditions.html').write_text(html, encoding='utf-8')
    print(f"  conditions.html — {len(conditions)} conditions, {len(html)//1024} KB")


# ─── 6. BACKGROUNDS ───────────────────────────────────────────────────────────

def build_backgrounds():
    print("Building backgrounds.html...")
    rows = load_all('background_*.rpg.json')
    sources = set()
    all_rows = []

    for d in rows:
        s = d['stats']
        name   = sv(s,'name') or ''
        source = (sv(s,'source') or 'PHB').upper()
        sources.add(source)

        # Skill proficiencies
        skills = []
        sp_list = sv(s,'skill_proficiencies') or []
        if isinstance(sp_list, list):
            for sp in sp_list:
                opts = sp.get('stats',{}).get('options',{}).get('value',[])
                if isinstance(opts, list):
                    skills.extend(opts)
                elif isinstance(opts, str):
                    skills.append(opts)
        skills_str = ', '.join(s_.replace('_',' ').title() for s_ in skills[:4]) if skills else '—'

        # Tool proficiencies
        tools = []
        tp_list = sv(s,'tool_proficiencies') or []
        if isinstance(tp_list, list):
            for tp in tp_list:
                opts = tp.get('stats',{}).get('options',{}).get('value',[])
                if isinstance(opts, str): tools.append(opts)
                elif isinstance(opts, list): tools.extend(opts)
        tools_str = ', '.join(tools[:2]) if tools else '—'

        # Feature name + description
        feats_ = sv(s,'features') or []
        feat_name = ''
        feat_desc = ''
        if isinstance(feats_, list) and feats_:
            fn = feats_[0].get('stats',{}).get('name',{}).get('value','')
            feat_name = fn or ''
            descs = feats_[0].get('stats',{}).get('descriptions',{}).get('value',[])
            if isinstance(descs, list) and descs:
                feat_desc = descs[0].get('stats',{}).get('description',{}).get('value','') if isinstance(descs[0], dict) else ''

        all_rows.append((name, source, skills_str, tools_str, feat_name, feat_desc))

    tbody = ''
    for (name, source, skills, tools, feat_name, feat_desc) in sorted(all_rows, key=lambda x: x[0].lower()):
        dc = f'data-name="{esc(name.lower())}" data-src="{esc(source)}"'
        tbody += f'<tr {dc} onclick="toggleRow(this)"><td><strong>{esc(name)}</strong></td>'
        tbody += f'<td style="color:#888;font-size:12px">{esc(source)}</td>'
        tbody += f'<td style="font-size:12px">{esc(skills)}</td>'
        tbody += f'<td style="font-size:12px">{esc(tools)}</td>'
        tbody += f'<td style="font-size:12px;color:#c4b5fd">{esc(feat_name) or nd("—")}</td></tr>'
        desc_html = ''
        if feat_name:
            desc_html += f'<p><strong style="color:#a78bfa">{esc(feat_name)}</strong></p><p>{esc(feat_desc)}</p>'
        if not desc_html:
            desc_html = nd('No additional details.')
        tbody += f'<tr class="desc-row"><td colspan="5"><div class="desc-content">{desc_html}</div></td></tr>'

    src_opts = '\n'.join(f'<option value="{esc(s)}">{esc(s)}</option>' for s in sorted(sources))

    html = page_head('Backgrounds — 5e', '📜', f'{len(all_rows)} backgrounds')
    html += f'''
<div class="filters">
  <input type="text" id="fsearch" placeholder="Search name or feature…" oninput="applyFilters()">
  <select id="fsrc" onchange="applyFilters()"><option value="">All Sources</option>{src_opts}</select>
  <span class="count" id="cnt"></span>
</div>
<div class="table-wrap">
<table><thead><tr>
  <th onclick="sortBy(0)">Background</th>
  <th onclick="sortBy(1)">Source</th>
  <th onclick="sortBy(2)">Skills</th>
  <th onclick="sortBy(3)">Tool Prof.</th>
  <th onclick="sortBy(4)">Feature</th>
</tr></thead><tbody id="tbody">{tbody}</tbody></table>
</div>
<script>
{SORT_JS}
function applyFilters(){{
  var q=(document.getElementById('fsearch').value||'').toLowerCase();
  var fs=document.getElementById('fsrc').value;
  var rows=document.querySelectorAll('#tbody tr:not(.desc-row)');
  var vis=0;
  rows.forEach(function(tr){{
    var nm=tr.getAttribute('data-name')||'';
    var sr=tr.getAttribute('data-src')||'';
    var text=tr.textContent.toLowerCase();
    var show=(!q||nm.indexOf(q)>=0||text.indexOf(q)>=0)&&(!fs||sr===fs);
    tr.style.display=show?'':'none';
    var next=tr.nextElementSibling;
    if(next&&next.classList.contains('desc-row'))next.style.display='none';
    if(show)vis++;
  }});
  document.getElementById('cnt').textContent=vis+' backgrounds';
}}
applyFilters();
</script>
'''
    (OUT / 'backgrounds.html').write_text(html, encoding='utf-8')
    print(f"  backgrounds.html — {len(all_rows)} backgrounds, {len(html)//1024} KB")


# ─── 7. RACES ─────────────────────────────────────────────────────────────────

def build_races():
    print("Building races.html...")
    rows = load_all('race_*.rpg.json')
    sources = set()
    all_rows = []

    for d in rows:
        s = d['stats']
        name    = sv(s,'name') or ''
        source  = (sv(s,'source') or 'PHB').upper()
        sources.add(source)

        # Ability score increases (list of options)
        asi_list = sv(s,'ability_score_increases') or []
        asi_parts = []
        if isinstance(asi_list, list):
            for asi in asi_list[:3]:
                opts = asi.get('stats',{}).get('modifier_options',{}).get('value',[])
                mod  = asi.get('stats',{}).get('modifier',{}).get('value','')
                if isinstance(opts, list) and opts:
                    short = '/'.join(o[:3].upper() for o in opts[:2])
                    asi_parts.append(f"{short} +{mod}" if mod else short)
        asi_str = ', '.join(asi_parts) if asi_parts else '—'

        # Traits
        trait_list = sv(s,'traits') or []
        trait_names = []
        trait_details = []
        if isinstance(trait_list, list):
            for t in trait_list:
                tn = t.get('stats',{}).get('name',{}).get('value','')
                if tn: trait_names.append(tn)
                descs = t.get('stats',{}).get('descriptions',{}).get('value',[])
                if isinstance(descs, list) and descs:
                    td = descs[0].get('stats',{}).get('description',{}).get('value','') if isinstance(descs[0], dict) else ''
                    if tn and td:
                        trait_details.append(f"<p><strong style='color:#a78bfa'>{esc(tn)}</strong><br>{esc(td)}</p>")
        traits_str = ', '.join(trait_names[:4]) if trait_names else '—'
        if len(trait_names) > 4: traits_str += f' +{len(trait_names)-4} more'

        # Subraces
        sub_list = sv(s,'subraces') or []
        sub_count = len(sub_list) if isinstance(sub_list, list) else 0
        sub_names = []
        if isinstance(sub_list, list):
            for sub in sub_list:
                sn = sub.get('stats',{}).get('name',{}).get('value','')
                if sn: sub_names.append(sn)

        all_rows.append((name, source, asi_str, traits_str, sub_count,
                         '\n'.join(trait_details), sub_names))

    tbody = ''
    for (name, source, asi, traits, sub_count, detail_html, sub_names) in sorted(all_rows, key=lambda x: x[0].lower()):
        dc = f'data-name="{esc(name.lower())}" data-src="{esc(source)}"'
        tbody += f'<tr {dc} onclick="toggleRow(this)"><td><strong>{esc(name)}</strong></td>'
        tbody += f'<td style="color:#888;font-size:12px">{esc(source)}</td>'
        tbody += f'<td style="font-size:12px;color:#bbb">{esc(asi)}</td>'
        tbody += f'<td style="font-size:12px">{esc(traits)}</td>'
        tbody += f'<td style="color:#888">{sub_count if sub_count else nd("—")}</td></tr>'
        dh = detail_html or ''
        if sub_names:
            dh += f'<p style="margin-top:8px"><strong style="color:#a78bfa">Subraces:</strong> {esc(", ".join(sub_names))}</p>'
        if not dh:
            dh = '<p style="color:#555">No additional details.</p>'
        tbody += f'<tr class="desc-row"><td colspan="5"><div class="desc-content">{dh}</div></td></tr>'

    src_opts = '\n'.join(f'<option value="{esc(s)}">{esc(s)}</option>' for s in sorted(sources))

    html = page_head('Races — 5e', '🧝', f'{len(all_rows)} races & subraces')
    html += f'''
<div class="filters">
  <input type="text" id="fsearch" placeholder="Search name or trait…" oninput="applyFilters()">
  <select id="fsrc" onchange="applyFilters()"><option value="">All Sources</option>{src_opts}</select>
  <span class="count" id="cnt"></span>
</div>
<div class="table-wrap">
<table><thead><tr>
  <th onclick="sortBy(0)">Race</th>
  <th onclick="sortBy(1)">Source</th>
  <th onclick="sortBy(2)">ASI</th>
  <th onclick="sortBy(3)">Key Traits</th>
  <th onclick="sortBy(4)"># Subraces</th>
</tr></thead><tbody id="tbody">{tbody}</tbody></table>
</div>
<script>
{SORT_JS}
function applyFilters(){{
  var q=(document.getElementById('fsearch').value||'').toLowerCase();
  var fs=document.getElementById('fsrc').value;
  var rows=document.querySelectorAll('#tbody tr:not(.desc-row)');
  var vis=0;
  rows.forEach(function(tr){{
    var nm=tr.getAttribute('data-name')||'';
    var sr=tr.getAttribute('data-src')||'';
    var text=tr.textContent.toLowerCase();
    var show=(!q||nm.indexOf(q)>=0||text.indexOf(q)>=0)&&(!fs||sr===fs);
    tr.style.display=show?'':'none';
    var next=tr.nextElementSibling;
    if(next&&next.classList.contains('desc-row'))next.style.display='none';
    if(show)vis++;
  }});
  document.getElementById('cnt').textContent=vis+' races';
}}
applyFilters();
</script>
'''
    (OUT / 'races.html').write_text(html, encoding='utf-8')
    print(f"  races.html — {len(all_rows)} races, {len(html)//1024} KB")


# ─── 8. CLASSES ───────────────────────────────────────────────────────────────

def build_classes():
    print("Building classes.html...")
    rows = load_all('class_*.rpg.json')
    all_rows = []

    for d in rows:
        s = d['stats']
        name    = sv(s,'name') or ''
        source  = (sv(s,'source') or 'PHB').upper()
        hit_die = sv(s,'hit_die') or '—'
        spell_ab = sv(s,'spellcasting_ability') or '—'
        if spell_ab != '—': spell_ab = spell_ab.title()

        # Saving throws from proficiency fields
        saves = []
        for stat in ['strength','dexterity','constitution','intelligence','wisdom','charisma']:
            if sv(s, f'{stat}_saving_throw_proficiency'):
                saves.append(stat[:3].upper())
        saves_str = ', '.join(saves) if saves else '—'

        # Archetypes / subclasses
        arc_list = sv(s,'archetypes') or []
        arc_names = []
        if isinstance(arc_list, list):
            for arc in arc_list:
                an = arc.get('stats',{}).get('name',{}).get('value','')
                if an: arc_names.append(an)
        arc_count = len(arc_names)

        # Primary ability (from hp_modifiers or best guess)
        hp_mods = sv(s,'hp_modifiers') or []
        hp_mod_str = ', '.join(hp_mods).title() if isinstance(hp_mods, list) else '—'

        all_rows.append((name, source, hit_die, spell_ab, saves_str, arc_count, arc_names))

    tbody = ''
    for (name, source, hit_die, spell_ab, saves, arc_count, arc_names) in sorted(all_rows, key=lambda x: x[0].lower()):
        tbody += f'<tr onclick="toggleRow(this)"><td><strong>{esc(name)}</strong></td>'
        tbody += f'<td style="color:#888;font-size:12px">{esc(source)}</td>'
        tbody += f'<td style="color:#a78bfa">{esc(hit_die)}</td>'
        tbody += f'<td style="font-size:12px">{esc(spell_ab)}</td>'
        tbody += f'<td style="font-size:12px">{esc(saves)}</td>'
        tbody += f'<td style="color:#888">{arc_count if arc_count else nd("—")}</td></tr>'
        arc_html = ''
        if arc_names:
            arc_html = '<p><strong style="color:#a78bfa">Subclasses:</strong><br>' + esc(', '.join(arc_names)) + '</p>'
        else:
            arc_html = '<p style="color:#555">No subclasses in dataset.</p>'
        tbody += f'<tr class="desc-row"><td colspan="6"><div class="desc-content">{arc_html}</div></td></tr>'

    html = page_head('Classes — 5e', '⚡', f'{len(all_rows)} classes')
    html += f'''
<div class="filters">
  <input type="text" id="fsearch" placeholder="Search class name…" oninput="applyFilters()">
  <span class="count" id="cnt"></span>
</div>
<div class="table-wrap">
<table><thead><tr>
  <th onclick="sortBy(0)">Class</th>
  <th onclick="sortBy(1)">Source</th>
  <th onclick="sortBy(2)">Hit Die</th>
  <th onclick="sortBy(3)">Spellcasting</th>
  <th onclick="sortBy(4)">Saving Throws</th>
  <th onclick="sortBy(5)"># Subclasses</th>
</tr></thead><tbody id="tbody">{tbody}</tbody></table>
</div>
<script>
{SORT_JS}
function applyFilters(){{
  var q=(document.getElementById('fsearch').value||'').toLowerCase();
  var rows=document.querySelectorAll('#tbody tr:not(.desc-row)');
  var vis=0;
  rows.forEach(function(tr){{
    var text=tr.textContent.toLowerCase();
    var show=!q||text.indexOf(q)>=0;
    tr.style.display=show?'':'none';
    var next=tr.nextElementSibling;
    if(next&&next.classList.contains('desc-row'))next.style.display='none';
    if(show)vis++;
  }});
  document.getElementById('cnt').textContent=vis+' classes';
}}
applyFilters();
</script>
'''
    (OUT / 'classes.html').write_text(html, encoding='utf-8')
    print(f"  classes.html — {len(all_rows)} classes, {len(html)//1024} KB")


# ─── Update index.html ────────────────────────────────────────────────────────

def update_index():
    print("Updating index.html...")
    idx = (OUT / 'index.html').read_text(encoding='utf-8')

    new_cards = '''
    <div class="card">
      <div class="card-header">
        <span class="card-icon">🐉</span>
        <span class="card-title">Monsters</span>
      </div>
      <div class="card-body">
        <p class="card-desc">1,400+ monsters with CR, AC, HP, speed, ability scores, and type filters. Paginated for performance.</p>
        <a class="btn btn-primary" href="monsters.html">Monster Reference</a>
      </div>
    </div>

    <div class="card">
      <div class="card-header">
        <span class="card-icon">⚔️</span>
        <span class="card-title">Weapons</span>
      </div>
      <div class="card-body">
        <p class="card-desc">All weapons with damage, properties, cost, and weight. Filter by Simple/Martial and type.</p>
        <a class="btn btn-primary" href="weapons.html">Weapon Reference</a>
      </div>
    </div>

    <div class="card">
      <div class="card-header">
        <span class="card-icon">🛡️</span>
        <span class="card-title">Armor</span>
      </div>
      <div class="card-body">
        <p class="card-desc">All armor with base AC, STR requirement, stealth disadvantage, cost, and weight.</p>
        <a class="btn btn-primary" href="armor.html">Armor Reference</a>
      </div>
    </div>

    <div class="card">
      <div class="card-header">
        <span class="card-icon">💎</span>
        <span class="card-title">Items &amp; Equipment</span>
      </div>
      <div class="card-body">
        <p class="card-desc">700+ items with rarity, magic, attunement, and curse filters. Click to expand descriptions.</p>
        <a class="btn btn-primary" href="items.html">Item Reference</a>
      </div>
    </div>

    <div class="card">
      <div class="card-header">
        <span class="card-icon">⚠️</span>
        <span class="card-title">Conditions</span>
      </div>
      <div class="card-body">
        <p class="card-desc">All 15 standard 5e conditions with full descriptions from the SRD. Click to expand.</p>
        <a class="btn btn-primary" href="conditions.html">Conditions Reference</a>
      </div>
    </div>

    <div class="card">
      <div class="card-header">
        <span class="card-icon">📜</span>
        <span class="card-title">Backgrounds</span>
      </div>
      <div class="card-body">
        <p class="card-desc">All backgrounds with skill proficiencies, tool proficiencies, and feature names.</p>
        <a class="btn btn-primary" href="backgrounds.html">Backgrounds Reference</a>
      </div>
    </div>

    <div class="card">
      <div class="card-header">
        <span class="card-icon">🧝</span>
        <span class="card-title">Races</span>
      </div>
      <div class="card-body">
        <p class="card-desc">All races with ability score increases, traits, and subraces. Click to expand trait details.</p>
        <a class="btn btn-primary" href="races.html">Races Reference</a>
      </div>
    </div>

    <div class="card">
      <div class="card-header">
        <span class="card-icon">⚡</span>
        <span class="card-title">Classes</span>
      </div>
      <div class="card-body">
        <p class="card-desc">All classes with hit die, spellcasting ability, saving throws, and subclass list.</p>
        <a class="btn btn-primary" href="classes.html">Classes Reference</a>
      </div>
    </div>'''

    # Insert before closing </div> of .grid
    if new_cards.strip() not in idx:
        idx = idx.replace('  </div>\n</body>', new_cards + '\n\n  </div>\n</body>')
        (OUT / 'index.html').write_text(idx, encoding='utf-8')
        print("  index.html updated with 8 new cards")
    else:
        print("  index.html already has new cards, skipping")


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    build_monsters()
    build_weapons()
    build_armor()
    build_items()
    build_conditions()
    build_backgrounds()
    build_races()
    build_classes()
    update_index()
    print("\nDone! All 8 pages generated.")
