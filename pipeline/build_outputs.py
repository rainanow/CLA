#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stage 3: 汇总产出。

输入:  <out>/results/*.json
输出:  <out>/输出/事件索引表.md / .csv
       <out>/输出/事件/<年>.md
       <out>/输出/可视化.html   （日历热力图 + 大事件时间轴 + 统计）
"""
import json
import csv
import os
import sys
import glob

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import get_config, paths


def load_all(results_dir):
    days = {}
    for fp in glob.glob(os.path.join(results_dir, '*.json')):
        try:
            r = json.load(open(fp, encoding='utf-8'))
        except Exception:
            continue
        d = r.get('date') or os.path.basename(fp)[:-5]
        days[d] = r
    return days


def build_index(days, out_dir):
    rows = []
    for d in sorted(days):
        r = days[d]
        for e in r.get('events', []):
            rows.append({
                '日期': d, '时间': e.get('time', ''),
                '等级': e.get('level', ''), '事件': e.get('title', ''),
                '描述': e.get('desc', ''),
                '当日浓度': r.get('intensity', ''),
                '极性': r.get('polarity', ''),
            })
    if not rows:
        print('[Stage3] 无事件可索引')
        return rows
    with open(os.path.join(out_dir, '事件索引表.csv'), 'w',
              encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    with open(os.path.join(out_dir, '事件索引表.md'), 'w', encoding='utf-8') as f:
        big = sum(1 for r in rows if r['等级'] == '大')
        f.write('# 事件索引表\n\n')
        f.write(f'共 {len(days)} 天分析结果，{len(rows)} 条事件，其中大事件 {big} 条。\n\n')
        f.write('| 日期 | 时间 | 等级 | 事件 | 当日浓度 | 极性 |\n')
        f.write('|------|------|------|------|----------|------|\n')
        for r in rows:
            ev = r['事件'].replace('|', '/').replace('\n', ' ')
            f.write(f"| {r['日期']} | {r['时间']} | {r['等级']} | {ev} | "
                    f"{r['当日浓度']} | {r['极性']} |\n")
    return rows


def build_event_docs(days, out_dir):
    ev_dir = os.path.join(out_dir, '事件')
    os.makedirs(ev_dir, exist_ok=True)
    years = {}
    for d in sorted(days):
        r = days[d]
        evs = r.get('events', [])
        if evs:
            years.setdefault(d[:4], []).append((d, r, evs))
    for y, items in sorted(years.items()):
        with open(os.path.join(ev_dir, f'{y}.md'), 'w', encoding='utf-8') as f:
            f.write(f'## {y}年 事件记录\n\n')
            f.write(f'{y}年共 {len(items)} 天有事件。\n\n')
            for d, r, evs in items:
                f.write(f"### {d}（浓度{r['intensity']}·{r['polarity']}）\n\n")
                f.write(f"{r.get('day_summary', '')}\n\n")
                for e in evs:
                    f.write(f"- **{e['level']}** {e['time']} {e['title']}：{e['desc']}\n")
                f.write('\n')


def build_viz(days, out_dir):
    data = []
    for d in sorted(days):
        r = days[d]
        big = [e for e in r.get('events', []) if e.get('level') == '大']
        data.append({
            'd': d, 'i': r.get('intensity', 3), 'p': r.get('polarity', '中'),
            's': r.get('day_summary', ''),
            'e': [{'t': e.get('title', ''), 'lv': e.get('level', '')}
                  for e in r.get('events', [])],
            'big': [{'t': e.get('title', ''), 'tm': e.get('time', '')} for e in big],
        })
    if not data:
        return
    payload = json.dumps(data, ensure_ascii=False)
    html = HTML_TEMPLATE.replace('__DATA__', payload)
    with open(os.path.join(out_dir, '可视化.html'), 'w', encoding='utf-8') as f:
        f.write(html)


HTML_TEMPLATE = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>聊天记录：情绪浓度日历</title>
<style>
  :root { --pos:#d43f3f; --neg:#2e8b57; --mix:#8b5fbf; --neu:#7a8ba0; }
  * { box-sizing:border-box; }
  body { font-family:"PingFang SC","Microsoft YaHei",sans-serif; margin:0; padding:24px; background:#f7f8fa; color:#2c3e50; }
  h1 { font-size:22px; } h2 { font-size:18px; margin-top:36px; }
  .legend { display:flex; gap:18px; align-items:center; margin:12px 0; font-size:13px; flex-wrap:wrap; }
  .chip { display:inline-block; width:14px; height:14px; border-radius:3px; margin-right:5px; vertical-align:-2px; }
  .cal { display:flex; flex-wrap:wrap; gap:14px; margin:8px 0 26px; }
  .month { background:#fff; border-radius:10px; padding:10px 12px; box-shadow:0 1px 4px rgba(0,0,0,.08); }
  .month h3 { margin:0 0 6px; font-size:13px; font-weight:600; text-align:center; }
  table.cal-t { border-collapse:collapse; }
  td.cell { width:15px; height:15px; border-radius:3px; background:#e8eaee; cursor:pointer; }
  td.cell:hover { outline:2px solid #34495e; }
  td.cell.big-event { box-shadow: inset 0 0 0 2px #2c3e50; }
  th { font-size:10px; color:#95a5a6; font-weight:normal; padding:0; width:15px; }
  .tip { position:fixed; background:#2c3e50; color:#fff; padding:8px 10px; border-radius:6px; font-size:12px; max-width:320px; pointer-events:none; display:none; z-index:99; line-height:1.6; }
  .stats { display:flex; flex-wrap:wrap; gap:12px; margin:14px 0; }
  .stat-card { background:#fff; border-radius:10px; padding:12px 18px; box-shadow:0 1px 4px rgba(0,0,0,.08); min-width:130px; }
  .stat-card .num { font-size:26px; font-weight:700; }
  .stat-card .lbl { font-size:12px; color:#7f8c8d; }
  .tl-wrap { background:#fff; border-radius:10px; padding:18px; box-shadow:0 1px 4px rgba(0,0,0,.08); overflow-x:auto; }
  .tl-label { font-size:12px; fill:#34495e; }
  text.tl-ev { font-size:11px; fill:#2c3e50; }
  .tl-ctrl { display:flex; gap:8px; align-items:center; flex-wrap:wrap; margin:6px 0 12px; font-size:13px; }
  .tl-ctrl button { border:1px solid #dfe4ea; background:#fff; color:#2c3e50; border-radius:6px; padding:5px 12px; cursor:pointer; font-size:13px; }
  .tl-ctrl button.active { background:#2c3e50; color:#fff; border-color:#2c3e50; }
  .tl-ctrl .sep { width:1px; height:18px; background:#dfe4ea; margin:0 4px; }
  .tl-ctrl .hint { color:#95a5a6; font-size:12px; }
  circle.tl-hit { cursor:pointer; }
  circle.tl-hit:hover { stroke:#2c3e50; stroke-width:2; }
</style>
</head>
<body>
<h1>聊天记录：情绪浓度日历</h1>
<div class="legend">
  <span><span class="chip" style="background:var(--pos)"></span>正</span>
  <span><span class="chip" style="background:var(--neg)"></span>负</span>
  <span><span class="chip" style="background:var(--mix)"></span>混合</span>
  <span><span class="chip" style="background:var(--neu)"></span>中</span>
  <span>颜色深浅 = 情绪浓度（1-5）</span>
  <span><span class="chip" style="box-shadow: inset 0 0 0 2px #2c3e50; background:#e8eaee"></span>含大事件</span>
  <span><span class="chip" style="background:#e8eaee"></span>无聊天（不评分）</span>
</div>
<div class="stats" id="stats"></div>
<div id="cals"></div>
<h2>大事件时间轴</h2>
<div class="tl-ctrl" id="tlCtrl"></div>
<div class="tl-wrap" id="tlWrap"><svg id="tl" height="620"></svg></div>
<div class="tip" id="tip"></div>
<script>
const DATA = __DATA__;
const byDate = {}; DATA.forEach(x => byDate[x.d] = x);
const OPACITY = [0, .22, .45, .68, .85, 1];

(function(){
  const el = document.getElementById('stats');
  const n = DATA.length;
  const dist = [0,0,0,0,0,0]; DATA.forEach(x => dist[x.i]++);
  const pos = DATA.filter(x=>x.p==='正').length, neg = DATA.filter(x=>x.p==='负').length;
  const mix = DATA.filter(x=>x.p==='混合').length;
  const bigDays = DATA.filter(x=>x.big.length>0).length;
  const avg = (DATA.reduce((a,x)=>a+x.i,0)/n).toFixed(2);
  const cards = [
    [n+' 天','有聊天的天数'],
    [avg,'平均情绪浓度'],
    ['1:'+dist[1]+' / 2:'+dist[2]+' / 3:'+dist[3],'低浓度天数(1-3分)'],
    ['4:'+dist[4]+' / 5:'+dist[5],'高浓度天数(4-5分)'],
    ['正 '+pos+' / 负 '+neg+' / 混 '+mix,'极性分布'],
    [bigDays+' 天','含大事件'],
  ];
  el.innerHTML = cards.map(c=>`<div class="stat-card"><div class="num">${c[0]}</div><div class="lbl">${c[1]}</div></div>`).join('');
})();

(function(){
  const tip = document.getElementById('tip');
  const tipEl = (ev, html) => {
    tip.innerHTML = html; tip.style.display='block';
    tip.style.left = Math.min(ev.clientX+14, innerWidth-340)+'px';
    tip.style.top = (ev.clientY+14)+'px';
  };
  const hideTip = () => tip.style.display='none';
  const years = [...new Set(DATA.map(x=>x.d.slice(0,4)))];
  const calsEl = document.getElementById('cals');
  years.forEach(y => {
    const yh = document.createElement('h2'); yh.textContent = y+' 年'; calsEl.appendChild(yh);
    const wrap = document.createElement('div'); wrap.className='cal'; calsEl.appendChild(wrap);
    for (let m=0; m<12; m++){
      const first = new Date(y, m, 1);
      if (first > new Date()) continue;
      const mo = document.createElement('div'); mo.className='month';
      mo.innerHTML = `<h3>${m+1}月</h3>`;
      const t = document.createElement('table'); t.className='cal-t';
      const head = document.createElement('tr');
      ['一','二','三','四','五','六','日'].forEach(w=>{const th=document.createElement('th');th.textContent=w;head.appendChild(th)});
      t.appendChild(head);
      let row = document.createElement('tr');
      for(let i=0;i<(first.getDay()+6)%7;i++) row.appendChild(document.createElement('td'));
      const dim = new Date(y, m+1, 0).getDate();
      for (let day=1; day<=dim; day++){
        const ds = `${y}-${String(m+1).padStart(2,'0')}-${String(day).padStart(2,'0')}`;
        const td = document.createElement('td'); td.className='cell';
        const rec = byDate[ds];
        if (rec){
          const key = rec.p==='正'?'--pos':rec.p==='负'?'--neg':rec.p==='混合'?'--mix':'--neu';
          td.style.background = `color-mix(in srgb, var(${key}) ${OPACITY[rec.i]*100}%, #e8eaee)`;
          if (rec.big.length) td.classList.add('big-event');
          td.onmousemove = ev => tipEl(ev,
            `<b>${ds}</b> 浓度 ${rec.i} · ${rec.p}` +
            (rec.big.length?`<br>大事件: ${rec.big.map(b=>b.t).join('；')}`:'') +
            (rec.e.length?`<br>事件: ${rec.e.map(e=>e.t).join('；').slice(0,120)}`:'<br>（无事件）') +
            `<br><span style="opacity:.85">${rec.s.slice(0,90)}</span>`);
          td.onmouseleave = hideTip;
        }
        row.appendChild(td);
        if (row.children.length===7){ t.appendChild(row); row=document.createElement('tr'); }
      }
      if (row.children.length) t.appendChild(row);
      mo.appendChild(t); wrap.appendChild(mo);
    }
  });
})();

// ---- 大事件时间轴：年份筛选 + 缩放 + 自动避让排布 ----
(function(){
  const svg = document.getElementById('tl');
  const ctrl = document.getElementById('tlCtrl');
  const tipEl = document.getElementById('tip');
  const LANE_H = 26, MAX_LANE = 10, GAP = 14;
  let ppd = 10, year = 'all';

  const esc = s => String(s).replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
  const events = [];
  DATA.forEach(r => (r.big || []).forEach(b => events.push({d: r.d, t: b.t, p: r.p, i: r.i, s: r.s})));
  events.sort((a, b) => a.d < b.d ? -1 : (a.d > b.d ? 1 : 0));
  const years = [...new Set(DATA.map(x => x.d.slice(0, 4)))];

  function bounds(){
    if (year === 'all'){
      const t0 = new Date(DATA[0].d + 'T00:00:00').getTime();
      const t1 = new Date(DATA[DATA.length-1].d + 'T00:00:00').getTime() + 86400000;
      return {t0, t1};
    }
    return {t0: new Date(year + '-01-01T00:00:00').getTime(),
            t1: new Date((Number(year)+1) + '-01-01T00:00:00').getTime()};
  }

  function renderCtrl(visCount){
    ctrl.innerHTML =
      '<span>范围</span>' +
      ['all'].concat(years).map(y =>
        `<button data-year="${y}" class="${y === year ? 'active' : ''}">${y === 'all' ? '全部' : y}</button>`).join('') +
      '<span class="sep"></span><span>缩放</span>' +
      [[4,'紧凑'],[10,'标准'],[22,'宽松']].map(([v, n]) =>
        `<button data-ppd="${v}" class="${v === ppd ? 'active' : ''}">${n}</button>`).join('') +
      `<span class="hint">此范围含 ${visCount} 个大事件 · 横向滚动查看 · 悬停看详情</span>`;
    ctrl.querySelectorAll('button').forEach(btn => {
      btn.onclick = () => {
        if (btn.dataset.year !== undefined) year = btn.dataset.year;
        if (btn.dataset.ppd !== undefined) ppd = Number(btn.dataset.ppd);
        render();
      };
    });
  }

  function render(){
    const {t0, t1} = bounds();
    const days = (t1 - t0) / 86400000;
    const M = 60, axisY = 300, H = 620;
    const W = Math.max(720, Math.round(M * 2 + days * ppd));
    svg.setAttribute('width', W);
    svg.setAttribute('height', H);
    const x = ds => M + (new Date(ds + 'T00:00:00').getTime() - t0) / 86400000 * ppd;
    const vis = events.filter(e => {
      const v = new Date(e.d + 'T00:00:00').getTime();
      return v >= t0 && v < t1;
    });

    let s = '';
    // 季度刻度，年初加粗
    let cur = new Date(t0);
    cur = new Date(cur.getFullYear(), Math.floor(cur.getMonth() / 3) * 3, 1);
    while (cur.getTime() < t1){
      const xx = M + (cur.getTime() - t0) / 86400000 * ppd;
      if (xx >= M - 1 && xx <= W - M + 1){
        const isJan = cur.getMonth() === 0;
        s += `<line x1="${xx}" y1="${axisY - 8}" x2="${xx}" y2="${axisY + 8}" stroke="${isJan ? '#7f8c8d' : '#c8d0d8'}" stroke-width="${isJan ? 1.6 : 1}"/>`;
        s += `<text class="tl-label" x="${xx}" y="${H - 24}" text-anchor="middle" opacity="${isJan ? 1 : .6}">${cur.getFullYear()}.${cur.getMonth() + 1}</text>`;
      }
      cur = new Date(cur.getFullYear(), cur.getMonth() + 3, 1);
    }
    s += `<line x1="${M}" y1="${axisY}" x2="${W - M}" y2="${axisY}" stroke="#bdc3c7" stroke-width="2"/>`;

    // 上下两侧分别避让：同侧相邻竖线至少间隔 GAP 像素，撞不下就换 lane
    const lanes = {pos: [], neg: []};
    const placed = [];
    vis.forEach(e => {
      const side = e.p === '负' ? 'neg' : 'pos';
      const xx = x(e.d);
      let li = lanes[side].findIndex(end => end + GAP <= xx);
      if (li === -1){
        if (lanes[side].length < MAX_LANE){ lanes[side].push(-Infinity); li = lanes[side].length - 1; }
        else { li = lanes[side].indexOf(Math.min.apply(null, lanes[side])); }
      }
      lanes[side][li] = xx;
      placed.push({
        e, side, lane: li, x: xx,
        y: side === 'pos' ? axisY - 18 - li * LANE_H : axisY + 18 + li * LANE_H,
        color: side === 'pos' ? 'var(--pos)' : 'var(--neg)',
        idx: placed.length,
      });
    });

    // 常驻标签：同一 lane 内有空间才画，放不下就只留悬停
    const lastRight = {};
    const labeled = new Set();
    placed.slice().sort((a, b) => a.x - b.x).forEach(p => {
      const key = p.side + '-' + p.lane;
      const text = p.e.t.length > 10 ? p.e.t.slice(0, 10) + '…' : p.e.t;
      const w = text.length * 11.5 + 6;
      if ((lastRight[key] === undefined ? -1e9 : lastRight[key]) + 6 <= p.x - w / 2){
        lastRight[key] = p.x + w / 2;
        labeled.add(p.idx);
        p.labelText = text;
      }
    });

    placed.forEach(p => {
      s += `<line x1="${p.x}" y1="${axisY}" x2="${p.x}" y2="${p.y}" stroke="${p.color}" stroke-width="1" opacity=".45"/>`;
      if (labeled.has(p.idx)){
        s += `<text class="tl-ev" x="${p.x}" y="${p.y + (p.side === 'pos' ? -9 : 15)}" text-anchor="middle">${esc(p.labelText)}</text>`;
      }
      s += `<circle class="tl-hit" data-idx="${p.idx}" cx="${p.x}" cy="${p.y}" r="5" fill="${p.color}"/>`;
    });

    svg.innerHTML = s;
    svg.querySelectorAll('.tl-hit').forEach(c => {
      const p = placed[Number(c.dataset.idx)];
      c.onmousemove = ev => {
        tipEl.innerHTML = `<b>${p.e.d}</b> · 浓度${p.e.i} · ${p.e.p}<br>${esc(p.e.t)}` +
          (p.e.s ? `<br><span style="opacity:.85">${esc(p.e.s.slice(0, 80))}</span>` : '');
        tipEl.style.display = 'block';
        tipEl.style.left = Math.min(ev.clientX + 14, innerWidth - 340) + 'px';
        tipEl.style.top = (ev.clientY + 14) + 'px';
      };
      c.onmouseleave = () => { tipEl.style.display = 'none'; };
    });

    renderCtrl(vis.length);
  }
  render();
})();
</script>
</body>
</html>'''


def run(cfg):
    p = paths(cfg.out)
    os.makedirs(p['output'], exist_ok=True)
    days = load_all(p['results'])
    print(f'[Stage3] 载入 {len(days)} 天结果')
    rows = build_index(days, p['output'])
    print(f'[Stage3] 索引表 {len(rows)} 条事件')
    build_event_docs(days, p['output'])
    build_viz(days, p['output'])
    print(f"[Stage3] 产出完成 -> {p['output']}")


if __name__ == '__main__':
    cfg = get_config('Stage3 汇总产出')
    run(cfg)
