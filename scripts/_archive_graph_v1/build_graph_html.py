#!/usr/bin/env python3
"""build_graph_html.py — Knowledge Base/graph.json → single-file graph.html.

Self-contained HTML with embedded graph data; opens via file:// or any web
server. Uses Cytoscape.js 3.30 from unpkg.
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
KB = HERE.parent / "Knowledge Base"
SRC = KB / "graph.json"
OUT = KB / "graph.html"

CATEGORY_COLORS = {
    "身份":           "#e85d75",
    "认知":           "#5d9ce8",
    "学习":           "#7d5be8",
    "行动":           "#e8a13d",
    "情绪":           "#5de88a",
    "关系与社会":     "#c45de8",
    "系统与策略":     "#5de8e8",
    "意义与目的":     "#e8e85d",
}

EDGE_COLORS = {
    "treats":     "#5de88a",
    "enables":    "#5da5e8",
    "causes":     "#e85d5d",
    "prevents":   "#c45de8",
    "part_of":    "#e8a13d",
    "contrasts":  "#a0e85d",
    "related":    "#2a2f38",
}

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>Water Your Self · 知识图谱</title>
<style>
  :root {
    --bg: #0d0f14;
    --bg-panel: rgba(20,22,30,.92);
    --border: rgba(255,255,255,.08);
    --fg: #e6e6e6;
    --fg-mute: #888;
    --accent: #f0c040;
  }
  body, html { margin: 0; padding: 0; height: 100%; font-family: -apple-system, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif; background: var(--bg); color: var(--fg); overflow: hidden; }
  #cy { width: 100%; height: 100vh; }
  .topbar { position: fixed; top: 14px; left: 50%; transform: translateX(-50%); z-index: 20; background: var(--bg-panel); padding: 8px 14px; border-radius: 10px; border: 1px solid var(--border); display: flex; align-items: center; gap: 12px; backdrop-filter: blur(10px); }
  .topbar .title { font-size: 14px; font-weight: 600; color: #fff; }
  .topbar input { background: #1a1d24; border: 1px solid var(--border); color: var(--fg); padding: 6px 10px; border-radius: 6px; width: 220px; font-size: 13px; outline: none; }
  .topbar input:focus { border-color: var(--accent); }
  .topbar button { background: #1a1d24; border: 1px solid var(--border); color: var(--fg); padding: 6px 12px; border-radius: 6px; font-size: 12px; cursor: pointer; user-select: none; }
  .topbar button:hover { background: #2a2f38; }
  .sidebar { position: fixed; top: 70px; left: 12px; z-index: 10; background: var(--bg-panel); padding: 12px 14px; border-radius: 10px; width: 250px; max-height: calc(100vh - 90px); overflow-y: auto; backdrop-filter: blur(8px); border: 1px solid var(--border); font-size: 12px; transition: transform .25s ease; }
  .sidebar.hidden { transform: translateX(-280px); }
  .sidebar h3 { font-size: 10px; text-transform: uppercase; letter-spacing: 1.5px; color: var(--fg-mute); margin: 14px 0 6px; font-weight: 600; }
  .sidebar h3:first-child { margin-top: 0; }
  .detail { position: fixed; top: 70px; right: 12px; max-width: 360px; max-height: calc(100vh - 90px); overflow-y: auto; background: var(--bg-panel); padding: 16px 18px; padding-top: 36px; border-radius: 10px; backdrop-filter: blur(10px); border: 1px solid var(--border); font-size: 13px; line-height: 1.65; display: none; z-index: 10; box-shadow: 0 8px 32px rgba(0,0,0,.3); }
  .detail.open { display: block; }
  .detail h2 { margin: 0 0 4px; font-size: 16px; color: #fff; padding-right: 28px; }
  .detail .meta { opacity: .5; font-size: 11px; margin-bottom: 12px; font-family: monospace; }
  .detail .summary { background: rgba(255,200,80,.05); padding: 12px 14px; border-left: 3px solid var(--accent); margin: 8px 0 12px; border-radius: 0 6px 6px 0; font-size: 13px; }
  .detail .field { margin-top: 14px; }
  .detail .field-label { font-size: 10px; text-transform: uppercase; letter-spacing: 1.5px; color: var(--accent); opacity: .85; margin-bottom: 5px; font-weight: 600; }
  .detail .tag { display: inline-block; background: #1f242c; padding: 3px 9px; margin: 2px 2px 2px 0; border-radius: 4px; font-size: 11px; }
  .detail ul { margin: 4px 0 8px; padding-left: 18px; }
  .detail li { margin: 3px 0; font-size: 13px; }
  .detail-close { position: absolute; top: 8px; right: 12px; cursor: pointer; opacity: .5; font-size: 22px; background: none; border: none; color: var(--fg); padding: 0 8px; line-height: 1; }
  .detail-close:hover { opacity: 1; }
  .detail .elist { font-size: 12px; }
  .detail .elist .er { display: flex; align-items: center; gap: 6px; padding: 3px 0; opacity: .9; }
  .detail .elist .er:hover { opacity: 1; cursor: pointer; }
  .row { display: flex; align-items: center; gap: 8px; padding: 4px 0; cursor: pointer; user-select: none; }
  .row:hover { background: rgba(255,255,255,.04); }
  .row input { margin: 0 4px 0 0; vertical-align: middle; }
  .row label { display: flex; align-items: center; gap: 8px; cursor: pointer; padding: 4px 6px; border-radius: 4px; flex: 1; }
  .row label:hover { background: rgba(255,255,255,.04); }
  .dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
  .edge-swatch { width: 18px; height: 2px; flex-shrink: 0; opacity: .85; }
  .dim { opacity: 0.06 !important; }
  .search-hit { border-color: var(--accent) !important; border-width: 4px !important; border-opacity: 1 !important; }
  .help { position: fixed; bottom: 12px; left: 12px; background: var(--bg-panel); padding: 8px 12px; border-radius: 6px; font-size: 11px; opacity: .55; border: 1px solid var(--border); pointer-events: none; }
  kbd { background: #2a2f38; padding: 1px 5px; border-radius: 3px; font-family: monospace; font-size: 10px; }
  .loading { position: fixed; inset: 0; display: flex; align-items: center; justify-content: center; z-index: 100; background: var(--bg); transition: opacity .35s ease; }
  .loading.hide { opacity: 0; pointer-events: none; }
  .spinner { width: 32px; height: 32px; border: 3px solid rgba(255,255,255,.1); border-top-color: var(--accent); border-radius: 50%; animation: spin .8s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }
  .stat { font-size: 11px; opacity: .55; line-height: 1.7; }
</style>
<script src="https://unpkg.com/cytoscape@3.30.2/dist/cytoscape.min.js"></script>
</head>
<body>

<div class="loading" id="loading"><div class="spinner"></div></div>

<div class="topbar">
  <span class="title">🕸 Water Your Self</span>
  <input type="search" id="search" placeholder="搜索 K-id · 名称 · 摘要…" autocomplete="off" />
  <button id="fit-btn">居中</button>
  <button id="relayout-btn">重排</button>
  <button id="toggle-sidebar">📋 侧栏</button>
</div>

<div class="sidebar" id="sidebar">
  <h3>枢纽 · Top 10</h3>
  <div id="hubs"></div>
  <h3>分类</h3>
  <div id="cat-filter"></div>
  <h3>边类型</h3>
  <div id="edge-filter"></div>
  <h3>图例</h3>
  <div id="edge-legend"></div>
  <h3>统计</h3>
  <div class="stat" id="stats"></div>
</div>

<div class="detail" id="detail">
  <button class="detail-close" id="detail-close" aria-label="关闭">×</button>
  <div id="detail-body"></div>
</div>

<div id="cy"></div>

<div class="help">
  <kbd>拖动</kbd> 平移 · <kbd>滚轮</kbd> 缩放 · <kbd>点节点</kbd> 详情 · <kbd>点空白</kbd> 关闭 · <kbd>搜索</kbd> 检索 · <kbd>Esc</kbd> 清空
</div>

<script>
const DATA = __DATA__;
const CATEGORY_COLORS = __COLORS__;
const EDGE_COLORS = __EDGE_COLORS__;
const ALL_TYPES = ["related", "treats", "enables", "causes", "prevents", "part_of", "contrasts"];
const EDGE_TYPE_DESC = {
  treats: "对策",
  enables: "促成",
  causes: "引发",
  prevents: "阻碍",
  part_of: "组成",
  contrasts: "对照",
  related: "泛指",
};

const searchIndex = DATA.nodes.map(n => ({
  id: n.id,
  blob: (n.id + " " + n.label + " " + n.category + " " + (n.props.summary || "") + " " + (n.props.diagnosis_tags || []).join(" ")).toLowerCase(),
}));

const nodes = DATA.nodes.map(n => ({ data: { id: n.id, label: n.label, category: n.category, ...n.props } }));
const edges = DATA.edges.map(e => ({
  data: { id: `${e.source}__${e.target}__${e.type}`, source: e.source, target: e.target, type: e.type, weight: e.weight }
}));

const cy = cytoscape({
  container: document.getElementById('cy'),
  elements: [...nodes, ...edges],
  style: [
    {
      selector: 'node',
      style: {
        'background-color': '#888',
        'label': 'data(label)',
        'color': '#e6e6e6',
        'font-size': 10,
        'text-valign': 'bottom',
        'text-halign': 'center',
        'text-margin-y': 5,
        'text-background-color': '#0d0f14',
        'text-background-opacity': 0.95,
        'text-background-padding': '3px',
        'text-background-shape': 'round-rectangle',
        'border-width': 2,
        'border-color': '#0d0f14',
        'width': 'data(degree_size)',
        'height': 'data(degree_size)',
      }
    },
    { selector: 'node:selected', style: { 'border-color': '#f0c040', 'border-width': 3, 'text-background-color': '#1a1d24' } },
    {
      selector: 'edge',
      style: {
        'curve-style': 'bezier',
        'control-point-step-size': 40,
        'line-color': '#2a2f38',
        'width': 0.6,
        'opacity': 0.32,
        'target-arrow-shape': 'triangle',
        'target-arrow-color': '#2a2f38',
        'arrow-scale': 0.7,
      }
    },
    ...ALL_TYPES.filter(t => t !== 'related').map(t => ({
      selector: `edge[type = "${t}"]`,
      style: {
        'line-color': EDGE_COLORS[t],
        'line-style': t === 'contrasts' ? 'dashed' : 'solid',
        'opacity': 0.9,
        'width': 2,
        'label': t,
        'font-size': 9,
        'color': '#bbb',
        'text-rotation': 'autorotate',
        'text-background-color': '#0d0f14',
        'text-background-opacity': 0.95,
        'text-background-padding': '2px',
        'text-background-shape': 'rectangle',
        'target-arrow-color': EDGE_COLORS[t],
      }
    })),
    { selector: '.dim', style: { 'opacity': 0.05 } },
    { selector: '.search-hit', style: { 'border-color': '#f0c040', 'border-width': 4 } },
  ],
  layout: {
    name: 'cose',
    animate: false,
    nodeRepulsion: 12000,
    idealEdgeLength: 110,
    edgeElasticity: 0.45,
    gravity: 0.30,
    numIter: 2000,
    coolingFactor: 0.99,
    randomize: true,
    padding: 30,
  },
  minZoom: 0.2,
  maxZoom: 3,
  wheelSensitivity: 0.2,
});

// Per-node degrees & colors
cy.batch(() => {
  cy.nodes().forEach(node => {
    const deg = node.degree();
    const sz = Math.max(12, Math.min(38, 12 + deg * 2));
    node.data('degree_size', sz);
    node.style('background-color', CATEGORY_COLORS[node.data('category')] || '#888');
  });
});
cy.style().update();

// Hide loading once first layout settles
cy.one('layoutstop', () => document.getElementById('loading').classList.add('hide'));

// State
const catFilter = {};
const edgeFilter = {};
DATA.nodes.forEach(n => catFilter[n.category] = true);
ALL_TYPES.forEach(t => edgeFilter[t] = true);

// Sidebar content
const hubsDiv = document.getElementById('hubs');
DATA.stats.top_connected.forEach(h => {
  const row = document.createElement('div');
  row.className = 'row';
  row.innerHTML = `<span class="dot" style="background:${CATEGORY_COLORS[h.category]}"></span><span style="flex:1;font-size:12px">${h.id} · ${h.label}</span><span style="opacity:.4;font-size:11px">${h.degree}</span>`;
  row.addEventListener('click', () => focusNode(h.id));
  hubsDiv.appendChild(row);
});

const cats = [...new Set(DATA.nodes.map(n => n.category))].sort();
const catFilterDiv = document.getElementById('cat-filter');
cats.forEach(c => {
  const row = document.createElement('div');
  row.className = 'row';
  const lbl = document.createElement('label');
  lbl.innerHTML = `<input type="checkbox" checked><span class="dot" style="background:${CATEGORY_COLORS[c]}"></span>${c}`;
  lbl.querySelector('input').addEventListener('change', e => {
    catFilter[c] = e.target.checked;
    applyFilter();
  });
  row.appendChild(lbl);
  catFilterDiv.appendChild(row);
});

const edgeFilterDiv = document.getElementById('edge-filter');
ALL_TYPES.forEach(t => {
  const row = document.createElement('div');
  row.className = 'row';
  const lbl = document.createElement('label');
  lbl.innerHTML = `<input type="checkbox" checked><span class="dot" style="background:${EDGE_COLORS[t]}"></span>${t}`;
  lbl.querySelector('input').addEventListener('change', e => {
    edgeFilter[t] = e.target.checked;
    applyFilter();
  });
  row.appendChild(lbl);
  edgeFilterDiv.appendChild(row);
});

const edgeLegendDiv = document.getElementById('edge-legend');
ALL_TYPES.forEach(t => {
  const row = document.createElement('div');
  row.className = 'row';
  const css = t === 'contrasts' ? `border-top: 2px dashed ${EDGE_COLORS[t]};` : `background:${EDGE_COLORS[t]};`;
  const op = t === 'related' ? 0.4 : 1;
  row.innerHTML = `<span class="edge-swatch" style="${css}opacity:${op}"></span><span style="flex:1">${t}</span><span style="opacity:.4;font-size:10px">${EDGE_TYPE_DESC[t]}</span>`;
  edgeLegendDiv.appendChild(row);
});

document.getElementById('stats').innerHTML =
  `${DATA.stats.nodes} 节点<br>${DATA.stats.edges} 边<br>${DATA.stats.categories} 分类<br>高自由度 · 平均 ${DATA.stats.avg_degree}`;

function applyFilter() {
  cy.batch(() => {
    cy.nodes().forEach(n => n.toggleClass('dim', !catFilter[n.data('category')]));
    cy.edges().forEach(e => e.toggleClass('dim', !edgeFilter[e.data('type')]));
  });
}

function focusNode(id) {
  const n = cy.getElementById(id);
  if (!n.length) return;
  const nb = n.closedNeighborhood();
  cy.elements().addClass('dim');
  nb.removeClass('dim').select();
  cy.fit(nb, 80);
  showDetail(id);
}

function showDetail(id) {
  const node = DATA.nodes.find(n => n.id === id);
  if (!node) return;
  const p = node.props || {};
  const rels = DATA.edges.filter(e => e.source === id || e.target === id);
  const outE = rels.filter(e => e.source === id);
  const inE = rels.filter(e => e.target === id);
  const labelMap = {};
  DATA.nodes.forEach(n => labelMap[n.id] = n.label);

  const listHtml = list => list && list.length ? `<ul>${list.map(s => `<li>${s}</li>`).join('')}</ul>` : '<span style="opacity:.35">—</span>';
  const tagsHtml = list => list && list.length ? list.map(s => `<span class="tag">${s}</span>`).join('') : '';
  const edgesHtml = (es, dir) => {
    if (!es.length) return '<div style="opacity:.4;font-size:11px;padding:4px 0">无</div>';
    return es.map(e => {
      const other = e.source === id ? e.target : e.source;
      const color = EDGE_COLORS[e.type];
      const arrow = dir === 'out' ? '→' : '←';
      return `<div class="er" data-id="${other}"><span style="color:${color};font-weight:600">${arrow}</span><span style="color:var(--accent);font-family:monospace;font-size:11px">${other}</span><span style="flex:1;opacity:.85">${labelMap[other]}</span><span style="opacity:.4;font-size:10px">${e.type}</span></div>`;
    }).join('');
  };

  document.getElementById('detail-body').innerHTML = `
    <h2>${node.label}</h2>
    <div class="meta">${node.id} · ${node.category}</div>
    ${p.summary ? `<div class="summary">${p.summary}</div>` : ''}
    ${p.diagnosis_tags && p.diagnosis_tags.length ? `<div class="field"><div class="field-label">诊断标签</div>${tagsHtml(p.diagnosis_tags)}</div>` : ''}
    ${p.trigger && p.trigger.length ? `<div class="field"><div class="field-label">触发场景</div>${listHtml(p.trigger)}</div>` : ''}
    ${p.symptoms && p.symptoms.length ? `<div class="field"><div class="field-label">表现症状</div>${listHtml(p.symptoms)}</div>` : ''}
    ${p.root_causes && p.root_causes.length ? `<div class="field"><div class="field-label">根因</div>${listHtml(p.root_causes)}</div>` : ''}
    ${p.interventions && p.interventions.length ? `<div class="field"><div class="field-label">干预方法</div>${listHtml(p.interventions)}</div>` : ''}
    ${p.reflection_questions && p.reflection_questions.length ? `<div class="field"><div class="field-label">自省问题</div>${listHtml(p.reflection_questions)}</div>` : ''}
    <div class="field"><div class="field-label">出边 (${outE.length})</div><div class="elist">${edgesHtml(outE, 'out')}</div></div>
    <div class="field"><div class="field-label">入边 (${inE.length})</div><div class="elist">${edgesHtml(inE, 'in')}</div></div>
  `;
  document.getElementById('detail').classList.add('open');
  // Make related items navigable
  document.querySelectorAll('#detail-body .er').forEach(el => {
    el.addEventListener('click', () => focusNode(el.dataset.id));
  });
}

function hideDetail() {
  document.getElementById('detail').classList.remove('open');
}

// Events
cy.on('tap', 'node', evt => focusNode(evt.target.id()));
cy.on('tap', evt => {
  if (evt.target === cy) {
    cy.elements().removeClass('dim').removeClass('search-hit');
    hideDetail();
  }
});
document.getElementById('detail-close').onclick = hideDetail;
document.getElementById('detail').addEventListener('click', e => {
  if (e.target.tagName !== 'BUTTON' && !e.target.closest('.er')) {
    // no-op for clicks inside (let .er handle its own)
  }
});

// Toolbar
document.getElementById('fit-btn').onclick = () => {
  cy.elements().removeClass('dim').removeClass('search-hit');
  cy.fit(undefined, 60);
};
document.getElementById('relayout-btn').onclick = () => {
  cy.layout({
    name: 'cose',
    animate: true,
    animationDuration: 800,
    nodeRepulsion: 12000,
    idealEdgeLength: 110,
    gravity: 0.30,
    numIter: 2000,
    randomize: true,
    padding: 30,
  }).run();
};
const sb = document.getElementById('sidebar');
document.getElementById('toggle-sidebar').onclick = () => sb.classList.toggle('hidden');

// Search
const searchInput = document.getElementById('search');
searchInput.addEventListener('input', e => {
  const q = e.target.value.trim().toLowerCase();
  if (!q) {
    cy.nodes().removeClass('search-hit');
    applyFilter(); // reset dim state
    return;
  }
  const hits = new Set();
  searchIndex.forEach(item => { if (item.blob.includes(q)) hits.add(item.id); });
  cy.batch(() => {
    cy.nodes().forEach(n => {
      const isHit = hits.has(n.id);
      n.toggleClass('search-hit', isHit);
      n.toggleClass('dim', !isHit && hits.size > 0);
    });
    cy.edges().forEach(e => {
      const either = hits.has(e.data('source')) || hits.has(e.data('target'));
      e.toggleClass('dim', !either && hits.size > 0);
    });
  });
  if (hits.size > 0) cy.fit(cy.nodes('.search-hit'), 80);
});
searchInput.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    searchInput.value = '';
    cy.nodes().removeClass('search-hit');
    applyFilter();
  }
});

// Initial fit
setTimeout(() => cy.fit(undefined, 60), 250);
</script>
</body>
</html>
"""


def main() -> None:
    graph = json.load(SRC.open(encoding="utf-8"))
    rendered = (
        HTML_TEMPLATE
        .replace("__DATA__", json.dumps(graph, ensure_ascii=False))
        .replace("__COLORS__", json.dumps(CATEGORY_COLORS, ensure_ascii=False))
        .replace("__EDGE_COLORS__", json.dumps(EDGE_COLORS, ensure_ascii=False))
    )
    OUT.write_text(rendered, encoding="utf-8")
    size_kb = OUT.stat().st_size / 1024
    print(f"Wrote {OUT.relative_to(KB.parent)}  ({size_kb:.1f} KB)")
    print(f"  open via file:// or any web server.")


if __name__ == "__main__":
    main()
