#!/usr/bin/env node
// 把 Studio 开发文档的数据生成 index.html，生成前逐条校验。只用 Node 自带模块：Studio 随包带 Node，不一定有 Python。
import { createHash } from 'node:crypto';
import { existsSync, mkdirSync, readFileSync, realpathSync, statSync, writeFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { dirname, isAbsolute, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const USAGE = `把 Studio 开发文档的数据生成 index.html，生成前逐条校验。

用法：
  node build_studio_doc.mjs <prd|proposal|progress|acceptance> <data.json> [-o 输出文件]
  node build_studio_doc.mjs shot <index.html> <应用的 frontend 目录>   # 400px、900px 各截一张图到同目录 .shots/，报页面脚本错误
  node build_studio_doc.mjs extract <index.html> <目录>   # 从保存过的一版取回 data.json（方案连同 Demo 文件）写进目录
  node build_studio_doc.mjs verify <index.html>   # 保存前核对：是脚本生成的、生成后没被改过

data.json 放在应用工程 docs/studio/<documentType>/ 下；方案的 Demo、验收报告的截图按 data.json 里写的相对路径找。
退出码：0 已生成，最后几行列出调 studio_write_proposal 时 files 要放的文件；1 有问题，逐条列出位置和改法；2 用法错误。`;

const SHELL = join(dirname(fileURLToPath(import.meta.url)), '..', 'assets', '开发文档外壳.html');
const DOC_TYPES = ['prd', 'proposal', 'progress', 'acceptance'];
const DOC_NAMES = { prd: '需求说明', proposal: '方案', progress: '制作进度', acceptance: '验收报告' };
const BY = { user: '使用者', app: '应用自动处理', ai: 'AI' };
const CONDITION_KEYS = [
  ['data', '数据从哪里来、多久更新一次？'],
  ['account', '要准备什么账号，谁来授权？'],
  ['cost', '哪些地方要花钱？'],
  ['access', '谁能看到、谁能改这些数据，存多久？'],
  ['effects', '会不会自动对外做事，资料会交给谁？'],
];
const BACKEND_STATES = ['做好了，实际跑过', '做好了，只用模拟数据试过', '做好了，等在线预览时实际跑', '在做', '没开始', '不需要'];
const CELL_STATES = ['做好了', '在做', '没开始', '不需要'];
const EVENT_STATES = ['done', 'doing', 'todo', 'blocked'];
// 原型里没有、已并到别处的旧字段：字段 → 写到哪
const MOVED_KEYS = {
  prd: {
    users: '谁来用写进 overview.audience',
    records: '会记下来的东西写进保存那一步节点的 rule',
    cost: '花多少写进方案 conditions.cost；花费上限在聊天里问，记工单',
    side_effects: '费用与副作用写进方案 conditions.cost 和 conditions.effects',
    external: '外部数据写进方案 conditions.data',
    needs: '要他提供的写进方案 conditions.account',
    cannot: '替代做法写进被替代那一步节点的 rule，环节 verified 写「做不到，见替代」',
    automations: '自动发生的事画成「到点开始」的 app 节点',
    others: '非刚需写进方案 scope.summary',
    out_of_scope: '这次不做的写进方案 scope.summary',
    defaults: '按默认定下的在节点 rule 原处标「按默认」',
    screens: '界面写进方案 features（每个功能的页面）',
    launch_scope: '上线范围不写进文档',
    decisions: '还要他定的事在聊天里用表单问',
  },
  proposal: {
    steps: '每一步用什么、花多少写在需求说明 AI 节点的 tier 和 cost',
    cost_review: '费用复核写进 conditions.cost 和 conditions.effects',
    summary: '一共要做什么写进 scope.summary',
  },
  progress: {
    trials: '「我先跑了一遍」只在聊天的进度消息里发；跑过的那一次在 events 里记一条',
    pages: '页面说明只在聊天的进度消息里写，页面长什么样看方案「功能与页面设计」',
    problems: '卡在哪写成 events 里一条 status 为 blocked 的事件，detail 写原因、影响哪个功能、谁在处理、什么时候能继续',
  },
  acceptance: {
    results: '实际跑出的结果写进那一条条目的 seen；要他判断的写进 actual',
    automation: '自动发生的那件事按它的验收条目写，挂到路径里到点开始的那一步',
    costs: '每次花了多少、和估算比、要等多久写进跑它的那一条条目的 seen；总花费在聊天交接里说',
    fix_log: '这一版改了什么、重测了哪几条写进 changes',
  },
};
const RESULTS = ['通过', '没通过', '好不好你说了算', '未测'];
const RESULT_CLASS = { 通过: 'pass', 没通过: 'fail', 好不好你说了算: 'judge', 未测: 'untested' };
const NODE_STATES = { pass: '通过', fail: '没通过', blocked: '受阻', unknown: '未验证' };
const UNTESTED = {
  // 类别：[原因原文, 这意味着, 要不要补 detail]。第二项只说没确认过什么，不请开发者去看、去试。
  login: ['要用真实账号登录才看得到：平台登录身份', '按真实账号显示的内容没确认过', false],
  bridge: ['要在 GoalfyMax 里打开才看得到：提醒、授权和付款窗口', '从提醒跳进应用、授权和付款这几处没确认过', false],
  studio: ['要在 Studio 窗口里打开才看得到', '页面在 Studio 窗口里的样子没确认过，内容和演示一致', false],
  cannot_run: ['演示版跑不起来', '页面上的操作没确认过', true],
  not_placed: ['你说先不放到在线预览', '放到在线预览后的表现没确认过', false],
  sample: ['缺你手上的样本', '用你的真实样本时的结果没确认过', true],
  online_page: ['在线预览里的页面我打不开', '在线预览里页面能不能打开、保存和读取走不走得通没确认过', false],
  schedule: ['到点触发要等真实时间', '到点会不会自动开始没确认过；发布并在「自动化」面板打开规则后才会自动跑', false],
  catalog: ['从目录或分享打开要先发布', '使用者从目录或分享打开的样子没确认过', false],
  cannot_fail: ['测试中造不出这种失败', '真遇到这种失败时页面怎么提示没确认过', true],
};
const LAUNCH_TITLES = ['上线的版本', '④ 验过什么', '未测的', '实际花了多少', '发布会怎样', '发布要准备的', '你可以做的事'];
// 给开发者看的文字里不该出现的词：词 → 改说什么
const BANNED = {
  冒泡: '「用测试数据跑一遍」',
  真跑: '「用真实数据跑一遍」',
  部署: '「放到在线预览」',
  本机: '不提本地的事',
  本地: '不提本地的事',
  工单: '不提',
  施工: '不提',
  演练: '写清跑了什么、用的什么数据',
  空跑: '写清跑了什么、用的什么数据',
  替身: '写清是测试数据',
  schema: '说成业务话',
  project_id: '不写核对字段',
  '【填': '换成真实内容',
  前端: '说成页面',
  后端: '说成后台的计算或保存',
  幂等: '「重复提交不会多建一条」',
  反读: '「保存后重新打开能看到」',
  增删改查: '「新增、查看、修改、删除」',
  类型检查: '写清查了什么、结果怎样',
  声明检查: '写清查了什么、结果怎样',
  非法值: '「不合规则的内容会被拦住」',
  测试回执: '说成业务话',
  模型任务: '「AI 处理」',
  工作集: '不提',
};
const BANNED_WORDS = {
  FA: '「模型步骤」',
  TPE: '「这一步」或路线的业务名',
  tokens: '只说积分',
  sandbox: '「沙盒」',
  completed: '中文结果，如「已完成」',
  succeeded: '中文结果，如「成功」',
  passed: '中文结果，如「通过」',
};
const EXEMPT_KEYS = new Set(['evidence', 'shots', 'demo', 'time', 'id', 'kind', 'by', 'status', 'state', 'tone', 'result']);
const DEMO_FORBIDDEN = [
  [/<\s*form\b/i, '不用 <form>：Studio 会把整个表单删掉；用 div 包住，按钮绑 click'],
  [/<\s*(iframe|object|embed|link|base|meta|style)\b/i, 'Demo 里不放 iframe、link、style 这类标签，样式只用外壳里的类名和行内 style'],
  [/<\s*script\b[^>]*\bsrc\s*=/i, '不引外部脚本'],
  [/\b(fetch|XMLHttpRequest|WebSocket|EventSource|sendBeacon)\b/i, '不联网：Demo 只用页面里写好的示例数据'],
  [/\b(localStorage|sessionStorage|indexedDB|document\.cookie)\b/i, '不存东西：刷新或点「重置示例」就回到初始状态'],
  [/\b(window\.parent|parent\.|window\.top|top\.location|opener|window\.open)\b/i, '不碰宿主窗口'],
  [/\blocation\s*\.\s*(href|assign|replace)|\blocation\s*=/i, '不跳转页面'],
  [/\bimport\s*\(/i, '不动态加载代码'],
  [/https?:\/\//i, '不引外部网址：图片用 data: 或纯 CSS 画'],
];
const VOID_TAGS = new Set(['input', 'img', 'br', 'hr', 'select', 'textarea', 'option']);

class Problems {
  constructor() { this.items = []; }
  add(where, msg) { this.items.push(`${where}：${msg}`); }
}

// data.json 来自助手手写，取值和真假按 JSON 的意思判断：空字符串、空列表、空对象、0 都算没写
const isObj = v => v !== null && typeof v === 'object' && !Array.isArray(v);
const truthy = v => !(v == null || v === false || v === 0 || v === '' || (Array.isArray(v) && !v.length) || (isObj(v) && !Object.keys(v).length));
const get = (o, k, d) => (isObj(o) && Object.hasOwn(o, k) ? o[k] : d);
const list = v => (Array.isArray(v) ? v : typeof v === 'string' ? [...v] : isObj(v) ? Object.keys(v) : []);
const str = v => (v == null ? 'None' : v === true ? 'True' : v === false ? 'False' : typeof v === 'object' ? JSON.stringify(v) : String(v));
const chars = v => [...String(v)];
const pad2 = n => String(n).padStart(2, '0');
const pyList = a => `[${a.join(', ')}]`;
const roundHalfEven = x => { const f = Math.floor(x), r = x - f; return r > 0.5 || (r === 0.5 && f % 2 !== 0) ? f + 1 : f; };
const sha256 = s => createHash('sha256').update(s, 'utf8').digest('hex');
const isFile = p => { try { return statSync(p).isFile(); } catch { return false; } };
// 和 str.replace 一样替换全部，替换内容原样放（不解释 $&）
const replaceAll = (s, a, b) => s.split(a).join(b);
const replaceFirst = (s, a, b) => { const i = s.indexOf(a); return i < 0 ? s : s.slice(0, i) + b + s.slice(i + a.length); };

const ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#x27;' };
const escape = s => String(s).replace(/[&<>"']/g, c => ESC[c]);
/** 转义并把换行变成 <br>。 */
const e = value => escape(value == null ? '' : str(value)).replaceAll('\n', '<br>');

function text(p, data, key, where, required = true, maxLen = null) {
  const value = get(data, key);
  if (value == null || (typeof value === 'string' && !value.trim())) {
    if (required) p.add(`${where}.${key}`, '必填，不能为空');
    return '';
  }
  if (!['string', 'number', 'boolean'].includes(typeof value)) {
    p.add(`${where}.${key}`, '要写成一段文字');
    return '';
  }
  const out = str(value).trim();
  const n = chars(out).length;
  if (maxLen && n > maxLen) p.add(`${where}.${key}`, `一行一项，最多 ${maxLen} 字（现在 ${n} 字）`);
  return out;
}

function items(p, data, key, where, required = true, minLen = 1) {
  const value = get(data, key);
  if (value == null) {
    if (required) p.add(`${where}.${key}`, '必填');
    return [];
  }
  if (!Array.isArray(value)) {
    p.add(`${where}.${key}`, '要写成列表 [...]');
    return [];
  }
  if (required && value.length < minLen) p.add(`${where}.${key}`, `至少 ${minLen} 项`);
  return value;
}

function scanWords(p, value, where) {
  if (isObj(value)) {
    for (const [k, v] of Object.entries(value)) if (!EXEMPT_KEYS.has(k)) scanWords(p, v, `${where}.${k}`);
  } else if (Array.isArray(value)) {
    value.forEach((v, i) => scanWords(p, v, `${where}[${i}]`));
  } else if (typeof value === 'string') {
    for (const [word, fix] of Object.entries(BANNED)) if (value.includes(word)) p.add(where, `开发者看得到这里，不写「${word}」，改成${fix}`);
    for (const [word, fix] of Object.entries(BANNED_WORDS))
      if (new RegExp(`(?<![A-Za-z])${word}(?![A-Za-z])`).test(value)) p.add(where, `开发者看得到这里，不写「${word}」，改成${fix}`);
  }
}

function common(p, data, docType) {
  const app = text(p, data, 'app', 'data');
  let version = get(data, 'version');
  if (!Number.isInteger(version) || version < 1) {
    p.add('data.version', '写整数版本号，第一版是 1，每保存一版加一');
    version = 0;
  }
  const updated = text(p, data, 'updated', 'data');
  if (updated && !/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/.test(updated)) p.add('data.updated', '写成 2026-11-05 14:20 这样的实际时间');
  const changes = items(p, data, 'changes', 'data', version > 1);
  if (version > 1 && !changes.length) p.add('data.changes', '第 2 版起写清这一版改了什么，一条一句');
  return { app, version, updated, changes, name: DOC_NAMES[docType] };
}

function head(c, eyebrow, h1, lead, tag = '') {
  const out = [`<main class="doc"><div class="eyebrow">${e(eyebrow)}</div>`,
    `<div class="doc-head"><div><h1>${e(h1)}</h1><p class="lead">${e(lead)}</p></div>${tag}</div>`,
    `<div class="meta">${e(c.app)} · 第 ${c.version} 版 · 更新于 ${e(c.updated)}</div>`];
  if (c.changes.length) {
    const lis = c.changes.map(x => `<li>${e(x)}</li>`).join('');
    out.push(`<details class="changes" open><summary>这一版改了什么</summary><ul>${lis}</ul></details>`);
  }
  return out.join('');
}

const foot = c => `<div class="footer">${e(c.name)} · 第 ${c.version} 版 · 更新于 ${e(c.updated)}</div></main>`;
const fold = (title, body, open = false) => `<details class="fold"${open ? ' open' : ''}><summary>${e(title)}</summary><div class="fold-body">${body}</div></details>`;
function table(headers, rows) {
  const th = headers.map(h => `<th>${e(h)}</th>`).join('');
  const trs = rows.map(row => '<tr>' + row.map(c => `<td>${c}</td>`).join('') + '</tr>').join('');
  return `<div class="table-wrap"><table><thead><tr>${th}</tr></thead><tbody>${trs}</tbody></table></div>`;
}
const ul = values => '<ul class="plain">' + list(values).map(v => `<li>${e(v)}</li>`).join('') + '</ul>';
const kv = pairs => '<dl class="kv">' + pairs.filter(([, v]) => truthy(v)).map(([k, v]) => `<dt>${e(k)}</dt><dd>${e(v)}</dd>`).join('') + '</dl>';

// ---------------- 需求说明 ----------------

function buildPrd(p, d) {
  const c = common(p, d, 'prd');
  const ov = get(d, 'overview') || {};
  const rows = [['audience', '服务对象'], ['problem', '业务问题'], ['goal', '建设目标'], ['approach', '设计思路']]
    .map(([key, label]) => `<div class="row"><small>${label}</small><p>${e(text(p, ov, key, 'overview', true, 60))}</p></div>`);
  const out = [head(c, '01 / 需求说明', c.app, '给谁用、要解决什么，每一步谁来做。点流程图里的一步看详情。'),
    `<div class="overview">${rows.join('')}</div>`];

  const phases = items(p, d, 'phases', 'data');
  const nodeIds = new Map();
  const graphCols = [], tabs = [], edges = [], details = [], phaseHeads = [];
  let n = 0;
  phases.forEach((ph, k) => {
    const where = `phases[${k}]`;
    const title = text(p, ph, 'title', where);
    tabs.push(`<button type="button" data-phase="${k}" aria-pressed="false">${pad2(k + 1)} ${e(title)}</button>`);
    const verified = text(p, ph, 'verified', where);
    if (verified && !['已试过，能做', '能做', '要新做，没试过', '做不到，见替代'].includes(verified))
      p.add(`${where}.verified`, '只写四种之一：已试过，能做 / 能做 / 要新做，没试过 / 做不到，见替代');
    const evidence = text(p, ph, 'evidence', where);
    const vtag = `<span class="tag ${verified.includes('没试过') || verified.includes('做不到') ? 'warn' : ''} verified" title="${e(evidence)}">${e(verified)}</span>`;
    phaseHeads.push(`<p class="muted" style="font-size:12px">${vtag} ${e(evidence)}</p>`);
    const colNodes = [];
    const phNodes = items(p, ph, 'nodes', where);
    const first = n;
    phNodes.forEach((node, j) => {
      const w = `${where}.nodes[${j}]`;
      const nt = text(p, node, 'title', w);
      let by = get(node, 'by');
      if (!Object.hasOwn(BY, by)) {
        p.add(`${w}.by`, '只写 user（使用者）、app（应用自动处理）、ai（AI）');
        by = 'app';
      }
      if (nodeIds.has(nt)) p.add(`${w}.title`, `节点名「${nt}」重复了，回环要按名字找节点`);
      nodeIds.set(nt, n);
      const pairs = [['输入', text(p, node, 'input', w)], ['输出', text(p, node, 'output', w)],
        ['重要信息', text(p, node, 'rule', w)], ['做不成时', text(p, node, 'fail', w, false)]];
      if (by === 'ai') pairs.push(['用哪一档、每次约', `${text(p, node, 'tier', w)} · ${text(p, node, 'cost', w)}`]);
      const sub = `${title} · ${BY[by]}`;
      const grid = pairs.filter(([, b]) => b).map(([a, b]) => `<section><h4>${e(a)}</h4><p>${e(b)}</p></section>`).join('');
      details.push([k, `<details data-detail="${n}"><summary>${pad2(n + 1)} ${e(nt)} <small>${e(BY[by])}</small></summary>`
        + `<div class="detail-src" data-sub="${e(sub)}"><div class="detail-grid">${grid}</div></div></details>`]);
      colNodes.push(`<button type="button" class="node by-${by}" data-node="${n}" data-phase="${k}" aria-pressed="false">`
        + `<small><span><i class="dot ${by}"></i>${e(BY[by])}</span><span>${pad2(n + 1)}</span></small><b>${e(nt)}</b></button>`);
      if (j > 0) edges.push({ from: n - 1, to: n });
      n += 1;
    });
    if (k > 0 && phNodes.length && first > 0) edges.push({ from: first - 1, to: first });
    graphCols.push(`<div class="phase"><div class="phase-title"><span class="num">${pad2(k + 1)}</span>${e(title)} ${vtag}</div><div class="nodes">${colNodes.join('')}</div></div>`);
  });
  items(p, d, 'loops', 'data', false).forEach((loop, i) => {
    const a = get(loop, 'from'), b = get(loop, 'to');
    if (!nodeIds.has(a) || !nodeIds.has(b)) {
      p.add(`loops[${i}]`, 'from、to 要写成上面节点的名字（一字不差）');
      return;
    }
    edges.push({ from: nodeIds.get(a), to: nodeIds.get(b), loop: true, label: chars(str(get(loop, 'label', ''))).slice(0, 16).join('') });
  });
  const cols = Math.min(Math.max(phases.length, 1), 4);
  const legend = '<div class="legend"><span><i class="dot user"></i>使用者</span><span><i class="dot"></i>应用自动处理</span><span><i class="dot ai"></i>AI</span><span>虚线：返回或复用</span></div>';
  const nodeList = phases.map((ph, k) => `<section><h3 style="margin-top:14px">${pad2(k + 1)} ${e(get(ph, 'title', ''))}</h3>${phaseHeads[k]}`
    + details.filter(([kk]) => kk === k).map(([, h]) => h).join('') + '</section>').join('');
  out.push(`<section class="section"><div class="section-head"><h2>完整业务流程</h2></div>${legend}`
    + `<div class="phase-tabs">${tabs.join('')}</div>`
    + `<div class="graph" style="--cols:${cols}"><svg class="edges" aria-hidden="true"></svg>${graphCols.join('')}</div>`
    + `<script type="application/json" id="graph-edges">${JSON.stringify(edges)}</script>`
    + '<div class="card node-panel" id="node-panel" hidden><div class="detail-head"><div><h3 class="panel-title"></h3><small class="panel-sub"></small></div>'
    + '<div class="detail-nav"><button type="button" id="node-prev" aria-label="上一个节点">←</button><button type="button" id="node-next" aria-label="下一个节点">→</button></div></div><div class="panel-body"></div></div>'
    + `<div class="node-list">${nodeList}</div></section>`);
  out.push(foot(c));
  return out.join('');
}

// ---------------- 方案 ----------------

function injectPins(src, where, p) {
  const found = [];
  const out = src.replace(/<([a-zA-Z][a-zA-Z0-9]*)(\s[^<>]*?\bdata-pin="(\d+)"[^<>]*)>/g, (m, tag, _attrs, num) => {
    tag = tag.toLowerCase();
    num = Number(num);
    if (VOID_TAGS.has(tag)) {
      p.add(where, `data-pin="${num}" 放在了 <${tag}> 上，改放到包住它的元素上`);
      return m;
    }
    found.push(num);
    return m + `<span class="pin">${num}</span>`;
  });
  return [out, found];
}

function buildProposal(p, d, base) {
  const c = common(p, d, 'proposal');
  const prdV = get(d, 'prd_version');
  if (!Number.isInteger(prdV)) p.add('data.prd_version', '写依据的需求说明版本号（整数）');
  const out = [head(c, '02 / 方案', '应用设计方案', '按业务过程看页面怎么用、每个编号是什么意思、最后得到什么。',
    `<span class="tag accent">依据需求说明第 ${e(prdV)} 版</span>`)];
  const scope = get(d, 'scope') || {};
  const route = items(p, scope, 'route', 'scope', true, 2);
  out.push(fold('制作范围与预期产出', '<div class="route">' + route.map(x => `<span>${e(x)}</span>`).join('<i>→</i>') + '</div>'
    + `<p class="muted" style="margin-top:10px">${e(text(p, scope, 'summary', 'scope'))}</p>`, true));
  const conds = get(d, 'conditions') || {};
  const blocks = [];
  CONDITION_KEYS.forEach(([key, q], i) => {
    const cd = get(conds, key);
    const where = `conditions.${key}`;
    if (!isObj(cd)) {
      p.add(where, '五件事都要写：data、account、cost、access、effects');
      return;
    }
    const now = text(p, cd, 'now', where);
    const impact = text(p, cd, 'impact', where);
    const decide = get(cd, 'decide'), settled = get(cd, 'settled');
    if (truthy(decide) && truthy(settled)) p.add(where, 'decide（还要他定的问题）和 settled（已经定了的结论）只写一个');
    const box = truthy(decide) ? `<div class="decide"><b>需要你决定</b><p>${e(decide)}</p></div>`
      : truthy(settled) ? `<p class="now">${e(settled)}</p>` : '';
    const question = get(cd, 'question');
    blocks.push(`<article class="condition"><h3>${i + 1}. ${e(truthy(question) ? question : q)}</h3><p class="now">${e(now)}</p><p class="impact">${e(impact)}</p>${box}</article>`);
  });
  out.push('<section class="section"><div class="section-head"><h2><span class="num">01</span>运行条件说明</h2></div>'
    + '<p class="intro">真正用起来之前，要说清楚下面五件事。</p>' + blocks.join('') + '</section>');

  const feats = items(p, d, 'features', 'data');
  const brand = get(d, 'brand') || {};
  const brandName = text(p, brand, 'name', 'brand');
  const workspace = text(p, brand, 'workspace', 'brand', false) || '我的工作台';
  const pick = (f, ...keys) => { for (const k of keys) { const v = get(f, k); if (truthy(v)) return str(v); } return ''; };
  const navPages = feats.map(f => pick(f, 'page', 'title'));
  // 目录按功能名：几个功能可以在同一页，用页面名会重名
  const titles = feats.map(f => pick(f, 'title'));
  titles.forEach((t, i) => {
    if (t && titles.indexOf(t) !== i)
      p.add(`features[${i}].title`, `和第 ${titles.indexOf(t) + 1} 个功能同名「${t}」：每个功能按它完成的业务起名，例如「输入文案和上限」「检查并显示结果」`);
  });
  const jump = '<nav class="jump">' + titles.map((x, i) => `<a href="#feature-${i}">${i + 1}. ${e(x)}</a>`).join('') + '</nav>';
  const featHtml = [], scripts = [];
  feats.forEach((f, i) => {
    const where = `features[${i}]`;
    const title = text(p, f, 'title', where);
    const how = text(p, f, 'how', where);
    const page = text(p, f, 'page', where);
    const demoRel = text(p, f, 'demo', where);
    let demoSrc = '', script = '';
    if (demoRel) {
      const path = resolve(base, demoRel);
      if (!isFile(path)) {
        p.add(`${where}.demo`, `找不到文件 ${demoRel}（相对 data.json 所在目录）`);
      } else {
        let raw = readFileSync(path, 'utf8');
        const m = /<script>([\s\S]*?)<\/script>\s*$/.exec(raw);
        if (m) {
          script = m[1];
          raw = raw.slice(0, m.index);
        }
        if (raw.includes('<script')) p.add(`${where}.demo`, 'Demo 里只能在文件最后放一个 <script>…</script>');
        for (const [pat, why] of DEMO_FORBIDDEN) if (pat.test(raw + script)) p.add(`${where}.demo`, why);
        let pins;
        [demoSrc, pins] = injectPins(raw, `${where}.demo`, p);
        const notesN = list(get(f, 'notes') || []).length;
        const uniq = [...new Set(pins)].sort((a, b) => a - b);
        if (uniq.join() !== Array.from({ length: notesN }, (_, k) => k + 1).join() || pins.length !== uniq.length)
          p.add(`${where}.demo`, `页面上的 data-pin 编号是 ${pyList([...pins].sort((a, b) => a - b))}，要和 notes 的条数对上：1 到 ${notesN} 各出现一次`);
      }
    }
    const notes = items(p, f, 'notes', where, true, 1);
    const noteHtml = notes.map((nt, j) => {
      const w = `${where}.notes[${j}]`;
      let extra = '';
      const ins = list(get(nt, 'input') || []);
      if (j === 0) {
        if (!ins.length) p.add(`${w}.input`, '第一条说明写「要先准备的」：这一步要用到什么、从哪来、要什么授权（一条一句）');
        extra += ins.map((x, k) => `<p>${k === 0 ? '<b>要先准备的：</b>' : ''}${e(x)}</p>`).join('');
      } else if (ins.length) {
        p.add(`${w}.input`, '只有第一条写「要先准备的」，中间的只写操作说明');
      }
      const outp = get(nt, 'output');
      if (j === notes.length - 1) {
        if (!truthy(outp)) p.add(`${w}.output`, '最后一条说明写「做完后得到」：做完得到什么、存在哪');
        extra += truthy(outp) ? `<p><b>做完后得到：</b>${e(outp)}</p>` : '';
      } else if (truthy(outp)) {
        p.add(`${w}.output`, '只有最后一条写「做完后得到」');
      }
      return `<div class="note" data-note="${j + 1}"><strong>${j + 1} · ${e(text(p, nt, 'title', w))}</strong><p>${e(text(p, nt, 'text', w))}</p>${extra}</div>`;
    });
    const ctx = get(f, 'context');
    let ctxHtml = '';
    if (truthy(ctx)) {
      const tone = get(ctx, 'tone') === 'warn' ? 'warn' : 'info';
      ctxHtml = `<details class="context ${tone}"><summary><span><b>${e(get(ctx, 'title'))}</b> · ${e(get(ctx, 'impact'))}</span><span>${e(get(ctx, 'action', '查看'))} ⌄</span></summary>`
        + `<div class="context-body">${ul(get(ctx, 'items') || [])}</div></details>`;
    }
    const side = navPages.map((x, k) => `<a href="#feature-${k}" data-goto="${k}" class="${k === i ? 'current' : ''}">${e(x)}</a>`).join('');
    const shell = `<div class="app-shell"><aside class="app-side"><div class="app-logo"><b>${e(chars(brandName).slice(0, 1).join(''))}</b>${e(brandName)}</div>${side}</aside>`
      + `<div class="app-work"><div class="app-top"><span>${e(workspace)} / <strong>${e(page)}</strong></span><span>示例数据</span></div>`
      + `<div class="app-body">${ctxHtml}${demoSrc}</div></div></div>`;
    featHtml.push(
      `<article class="feature" id="feature-${i}"><div class="feature-head"><div><h3><span class="num">2.${i + 1}</span>${e(title)}</h3><p>${e(how)}</p></div>`
      + `<button type="button" data-reset="${i}">↺ 重置示例</button></div>`
      + '<div class="demo-label"><span>完整页面示例</span><span>按栏宽缩放 · 可以直接点</span></div>'
      + `<div class="demo" data-demo="${i}"><div class="demo-stage">${shell}</div></div>`
      + `<div class="notes">${noteHtml.join('')}</div></article>`);
    if (script.trim()) scripts.push(`<script>window.__studioDemos=window.__studioDemos||{};window.__studioDemos["${i}"]=function(root){\n${script}\n};</script>`);
  });
  out.push(`<section class="section"><div class="section-head"><h2><span class="num">02</span>功能与页面设计<small>（Demo 仅供参考，不代表最终成果）</small></h2><small>${feats.length} 个功能</small></div>`
    + '<p class="intro">页面按使用顺序排。示例可以直接操作，用的是写好的示例数据，不连真实服务；每个编号对应下面一条说明。</p>'
    + `${jump}${featHtml.join('')}</section>`);

  // 验收条目只校验、不显示：页面上不出现，随 acceptance.json 一起保存
  const acc = items(p, d, 'acceptance', 'data');
  const ids = new Set();
  acc.forEach((a, i) => {
    const w = `acceptance[${i}]`;
    const aid = text(p, a, 'id', w);
    if (ids.has(aid)) p.add(`${w}.id`, `编号 ${aid} 重复`);
    ids.add(aid);
    const judge = text(p, a, 'judge', w);
    if (judge && !['AI 能判断', '要人判断'].includes(judge)) p.add(`${w}.judge`, '只写「AI 能判断」或「要人判断」');
    for (const key of ['who', 'entry', 'do', 'get', 'pass']) text(p, a, key, w);
  });
  const planFile = join(base, 'acceptance.json');
  if (isFile(planFile)) {
    let plan;
    try {
      plan = JSON.parse(readFileSync(planFile, 'utf8'));
    } catch (exc) {
      p.add('acceptance.json', `不是合法 JSON：${exc.message}`);
    }
    if (plan !== undefined)
      for (const cr of list(get(plan, 'crud') || [])) if (!ids.has(str(get(cr, 'id')))) p.add('acceptance.json', `crud 里的 ${str(get(cr, 'id'))} 在验收条目里找不到同编号的一条`);
  } else {
    p.add('acceptance.json', '方案要和 data.json 放在同一目录下的 acceptance.json 一起保存（格式见 studio_write_proposal 的说明）');
  }
  out.push(foot(c));
  return [out.join(''), scripts.join('')];
}

// ---------------- 制作进度 ----------------

function featureDone(f) {
  const b = get(f, 'backend'), pg = get(f, 'page'), da = get(f, 'data');
  const okB = str(b).startsWith('做好了') || b === '不需要';
  const okC = x => x === '做好了' || x === '不需要';
  if (okB && okC(pg) && okC(da)) return 'done';
  if ([b, pg, da].every(x => x === '没开始' || x === '不需要')) return 'todo';
  return 'doing';
}

/** 时间轴下面折叠的「交付范围与待明确条件」：原型里制作进度只有摘要、时间轴和这一块。 */
function journalSide(p, d, feats) {
  const word = { done: '做好了', doing: '在做', todo: '没开始' };
  let rows = feats.filter(isObj).map(f => `<div class="dependency">${e(get(f, 'name'))}<small>${word[featureDone(f)]} · 后台 ${e(get(f, 'backend'))} · 页面 ${e(get(f, 'page'))} · 存数据 ${e(get(f, 'data'))}</small></div>`).join('');
  const diffs = items(p, d, 'diffs', 'data', false);
  if (diffs.length) rows += diffs.map(x => `<div class="dependency">和方案不一样<small>${e(x)}</small></div>`).join('');
  let out = `<section><h3>本轮交付范围</h3>${rows}</section>`;
  const pend = items(p, d, 'pending', 'data', false);
  pend.forEach((x, i) => {
    text(p, x, 'what', `pending[${i}]`);
    text(p, x, 'affects', `pending[${i}]`);
  });
  if (pend.length) out += '<section><h3>仍需明确的条件</h3>' + pend.map(x => `<div class="dependency">${e(get(x, 'what'))}<small>影响：${e(get(x, 'affects'))}</small></div>`).join('') + '</section>';
  return `<details class="journal-side"><summary>交付范围与待明确条件</summary>${out}</details>`;
}

function buildProgress(p, d) {
  const c = common(p, d, 'progress');
  const feats = items(p, d, 'features', 'data');
  feats.forEach((f, i) => {
    const w = `features[${i}]`;
    text(p, f, 'name', w);
    if (!BACKEND_STATES.includes(get(f, 'backend'))) p.add(`${w}.backend`, '只写：' + BACKEND_STATES.join(' / '));
    for (const key of ['page', 'data']) if (!CELL_STATES.includes(get(f, key))) p.add(`${w}.${key}`, '只写：' + CELL_STATES.join(' / '));
  });
  const states = feats.map(featureDone);
  const count = s => states.filter(x => x === s).length;
  const done = count('done'), doing = count('doing'), todo = count('todo');
  const total = feats.length;
  const state = get(d, 'state');
  if (!['working', 'done', 'blocked'].includes(state)) p.add('data.state', '只写 working（在做）、done（都做完了）、blocked（卡住了）');
  if (state === 'done' && done !== total) p.add('data.state', `还有 ${total - done} 个功能没做好，不能写 done`);
  if (state === 'blocked' && !list(get(d, 'events') || []).some(ev => isObj(ev) && ev.status === 'blocked'))
    p.add('data.events', '写了卡住了，就要在时间轴上有一条 blocked 事件，detail 写卡在哪、影响哪个功能、谁在处理、什么时候能继续');
  const label = { working: '制作中', done: '都做完了', blocked: '卡住了' }[state] || '';
  const notReal = feats.filter(f => ['做好了，只用模拟数据试过', '做好了，等在线预览时实际跑'].includes(get(f, 'backend'))).length;
  let caveat = notReal ? `其中 ${notReal} 个的后台还没用真实数据跑过。` : '';
  caveat += '做好了不等于验收通过，验收结果看验收报告。';
  const now = get(d, 'now') || {};
  const nxt = get(d, 'next') || {};
  const out = [head(c, '03 / 制作进度', '制作进度', '按功能看做到哪，沿时间看做了什么。'),
    `<section class="summary-card state-${e(state)}"><div class="summary-top"><span><i class="state-dot"></i>${label}</span><span>更新于 ${e(c.updated)}</span></div>`
    + `<h2>${e(text(p, now, 'title', 'now'))}</h2><p class="muted">${e(text(p, now, 'detail', 'now', false))}</p>`
    + `<div class="bigline"><b>${done}</b>/ ${total} 个功能做好了 · ${doing} 个在做 · ${todo} 个没开始</div>`
    + `<div class="bar" style="--w:${total ? roundHalfEven(done * 100 / total) : 0}%"><i></i></div>`
    + `<p class="muted" style="font-size:12px;margin-top:8px">${caveat}</p>`
    + (truthy(get(nxt, 'title')) ? `<div class="next"><small>下一步</small><div><b>${e(get(nxt, 'title'))}</b><p class="muted">${e(get(nxt, 'detail', ''))}</p></div></div>` : '')
    + '</section>'];
  const events = items(p, d, 'events', 'data');
  const evHtml = events.map((ev, i) => {
    const w = `events[${i}]`;
    const st = get(ev, 'status');
    if (!EVENT_STATES.includes(st))
      p.add(`${w}.status`, '只写 done（做完了）、doing（在做）、todo（没开始）、blocked（受阻，detail 写卡在哪）；'
        + '整份卡住时另把 data.state 写成 blocked。不要因为这里报错就手写 index.html');
    const tmRaw = get(ev, 'time');
    const tm = truthy(tmRaw) ? str(tmRaw) : '';
    if (['done', 'doing', 'blocked'].includes(st) && !/^(\d{2}-\d{2} )?\d{2}:\d{2}$/.test(tm))
      p.add(`${w}.time`, '做过的事写实际时间（14:20 或 11-05 14:20），从工作记录里取，不估');
    const subs = list(get(ev, 'steps') || []).map((s, j) => {
      const sst = get(s, 'status');
      if (!EVENT_STATES.includes(sst)) p.add(`${w}.steps[${j}].status`, '只写 done、doing、todo、blocked');
      const sym = { done: '✓ 做完了', doing: '◉ 在做', todo: '○ 没开始', blocked: '! 受阻' }[sst] || '';
      return `<div class="substep"><span><small>${e(get(s, 'time', ''))}</small> ${e(get(s, 'title'))}</span><span>${sym}</span></div>`;
    });
    const mark = { done: '✓', doing: '◉', todo: '○', blocked: '!' }[st] || '';
    const tag = { done: '<span class="tag">做完了</span>', doing: '<span class="tag warn">在做</span>', todo: '<span class="tag unknown">没开始</span>',
      blocked: '<span class="tag fail">受阻</span>' }[st] || '';
    const subHtml = subs.length ? `<details${['doing', 'blocked'].includes(st) ? ' open' : ''}><summary>${subs.length} 个小步骤</summary>${subs.join('')}</details>` : '';
    return `<article class="event ${e(st)}"><time>${e(tm || '—')}</time><div class="track"><span class="mark">${mark}</span></div>`
      + `<div class="body"><h3>${e(text(p, ev, 'title', w))} ${tag}</h3><p>${e(text(p, ev, 'detail', w))}</p>${subHtml}</div></article>`;
  });
  out.push('<section class="section"><div class="section-head"><h2>制作时间轴</h2><span><button type="button" data-play="progress">▶ 回放</button> '
    + '<button type="button" data-stop="progress">停止</button></span></div>'
    + `<div class="timeline">${evHtml.join('')}</div><p class="muted" style="font-size:12px">回放只按上面已有的记录走一遍。</p>`
    + journalSide(p, d, feats) + '</section>');
  out.push(foot(c));
  return out.join('');
}

// ---------------- 验收报告 ----------------

/** 结论数下面的「逐条看全部」：不点路径也能逐条核对，按 没通过 → 要你判断 → 未测 → 通过 排。 */
function allItems(rows, counts, total) {
  const order = ['没通过', '好不好你说了算', '未测', '通过'];
  const sorted = order.flatMap(r => rows.filter(x => x.res === r));
  const filters = [['all', `全部 ${total}`], ...order.map(r => [RESULT_CLASS[r], `${r === '好不好你说了算' ? '要你判断' : r} ${counts[r]}`])];
  const lis = sorted.map(x => `<li class="all-row" data-r="${RESULT_CLASS[x.res]}"><div class="all-top"><b>${e(x.title)}</b>`
    + `<span class="all-tag ${RESULT_CLASS[x.res]}">${e(x.label)}</span></div>${kv(x.pairs)}</li>`).join('');
  return `<details class="all-items"><summary><span>逐条看全部 ${total} 条</span><span class="all-hint">点上面的数字只看那一类</span></summary>`
    + '<div class="all-filter" role="group" aria-label="按结论筛选">'
    + filters.map(([f, t], i) => `<button type="button" data-filter="${f}" aria-pressed="${i === 0}">${e(t)}</button>`).join('')
    + `</div><p class="all-count" aria-live="polite"></p><ol class="all-list">${lis}</ol></details>`;
}

function buildAcceptance(p, d, base) {
  const c = common(p, d, 'acceptance');
  const its = items(p, d, 'items', 'data');
  const byId = new Map(), shotsAll = [];
  const counts = Object.fromEntries(RESULTS.map(r => [r, 0]));
  const rows = [];
  const records = new Map();
  its.forEach((it, i) => {
    const w = `items[${i}]`;
    const iid = text(p, it, 'id', w);
    if (byId.has(iid)) p.add(`${w}.id`, `编号 ${iid} 重复`);
    byId.set(iid, it);
    const title = text(p, it, 'title', w);
    const res = get(it, 'result');
    if (!RESULTS.includes(res)) {
      p.add(`${w}.result`, '只写：通过 / 没通过 / 好不好你说了算 / 未测');
      return;
    }
    counts[res] += 1;
    if (['通过', '没通过', '好不好你说了算'].includes(res)) for (const key of ['how', 'seen', 'evidence']) text(p, it, key, w);
    if (res === '好不好你说了算' && !truthy(get(it, 'actual'))) p.add(`${w}.actual`, '要你判断的条目附上实际结果原文（报告全文、内容原文、前后对比）');
    let whyUntested = '';
    if (res === '未测') {
      const un = get(it, 'untested') || {};
      const kind = get(un, 'kind');
      if (!Object.hasOwn(UNTESTED, kind)) {
        p.add(`${w}.untested.kind`, '未测只能是这几类：' + Object.keys(UNTESTED).join('、'));
      } else {
        const [reason, later, need] = UNTESTED[kind];
        const detail = get(un, 'detail');
        if (need && !truthy(detail)) p.add(`${w}.untested.detail`, `「${reason}」要补上具体情况（做过的处理和错误原文 / 哪一份样本 / 试过哪些做法）`);
        whyUntested = reason + (truthy(detail) ? '：' + str(detail) : '') + '。' + later;
      }
    }
    let shotHtml = '';
    for (const s of list(get(it, 'shots') || [])) {
      if (!isFile(join(base, str(s)))) p.add(`${w}.shots`, `找不到截图 ${str(s)}（相对 data.json 所在目录）`);
      else if (!/^shots\/[\p{L}\p{N}_.-]+\.(png|jpg|jpeg|webp)$/u.test(s)) p.add(`${w}.shots`, '截图放在 shots/ 下，文件名只用字母数字和 - _ .，格式 png/jpg/webp');
      else {
        shotsAll.push(s);
        shotHtml += `<img src="${e(s)}" alt="${e(title)} 的截图">`;
      }
    }
    const resCls = RESULT_CLASS[res];
    const label = res + (res === '没通过' && truthy(get(it, 'accepted')) ? '，你选了接受' : '');
    const pairs = [['怎么测的', get(it, 'how', '')], ['看到的结果', get(it, 'seen', '')], ['实际结果', get(it, 'actual', '')],
      ['证据', get(it, 'evidence', '')], ['为什么没测', whyUntested]];
    records.set(iid, `<span class="item-record"><b>${e(title)}</b> <span class="result-${resCls}">${e(label)}</span>${kv(pairs)}`
      + (shotHtml ? `<span class="shots">${shotHtml}</span>` : '') + '</span>');
    rows.push({ res, title, label: res === '好不好你说了算' ? '要你判断' : label, pairs: pairs.filter(([k]) => k !== '证据') });
  });
  items(p, d, 'extra_untested', 'data', false).forEach((x, i) => {
    const w = `extra_untested[${i}]`;
    const kind = get(x, 'kind');
    if (!Object.hasOwn(UNTESTED, kind)) {
      p.add(`${w}.kind`, '未测只能是这几类：' + Object.keys(UNTESTED).join('、'));
      return;
    }
    const [reason, later, need] = UNTESTED[kind];
    const detail = get(x, 'detail');
    if (need && !truthy(detail)) p.add(`${w}.detail`, `「${reason}」要补上具体情况`);
    const title = text(p, x, 'title', w);
    rows.push({ res: '未测', title, label: '未测', pairs: [['为什么没测', reason + (truthy(detail) ? '：' + str(detail) : '') + '。' + later]] });
    counts['未测'] += 1;
  });
  const total = Object.values(counts).reduce((a, b) => a + b, 0);
  const out = [head(c, '04 / 验收报告', '验收报告', '按业务路径看每一步走没走通，结论都有依据。')];
  const stat = (cls, n, lbl) => `<div class="stat-card ${cls}" data-filter="${cls}"><p>${lbl}</p><strong>${n}</strong><p class="go">查看详情 →</p></div>`;
  out.push('<div class="stats">' + stat('fail', counts['没通过'], '没通过') + stat('pass', counts['通过'], '通过')
    + stat('judge', counts['好不好你说了算'], '要你判断') + stat('untested', counts['未测'], '未测')
    + `</div><p style="margin-top:10px">共 ${total} 条：没通过 ${counts['没通过']} · 通过 ${counts['通过']} · 要你判断 ${counts['好不好你说了算']} · 未测 ${counts['未测']}。${e(text(p, d, 'impact', 'data'))}</p>`
    + allItems(rows, counts, total));
  const paths = items(p, d, 'paths', 'data');
  const plist = [], pflows = [];
  const shown = new Set();
  paths.forEach((pa, i) => {
    const w = `paths[${i}]`;
    const nodes = items(p, pa, 'nodes', w, true, 2);
    const links = list(get(pa, 'links') || []);
    if (links.length !== Math.max(nodes.length - 1, 0)) p.add(`${w}.links`, `${nodes.length} 个节点之间要写 ${nodes.length - 1} 句衔接`);
    const states = [];
    const nHtml = [];
    nodes.forEach((nd, j) => {
      const nw = `${w}.nodes[${j}]`;
      let st = get(nd, 'state');
      if (!Object.hasOwn(NODE_STATES, st)) {
        p.add(`${nw}.state`, '只写 pass、fail、blocked、unknown');
        st = 'unknown';
      }
      states.push(st);
      const refs = list(get(nd, 'items') || []);
      refs.forEach(r => shown.add(r));
      if ((st === 'pass' || st === 'fail') && !refs.length) p.add(`${nw}.items`, '通过、没通过的节点要写依据哪几条验收条目（编号）');
      for (const r of refs) {
        if (!byId.has(r)) p.add(`${nw}.items`, `条目 ${str(r)} 不在 items 里`);
        else if (st === 'pass' && get(byId.get(r), 'result') !== '通过') p.add(`${nw}.state`, `标了通过，但条目 ${str(r)} 的结论是「${str(get(byId.get(r), 'result'))}」`);
      }
      if (st === 'fail' && refs.length && !refs.some(r => get(byId.get(r) || {}, 'result') === '没通过'))
        p.add(`${nw}.state`, '标了没通过，依据的条目里要有一条结论是「没通过」');
      if ((st === 'blocked' || st === 'unknown') && !truthy(get(nd, 'note'))) p.add(`${nw}.note`, '受阻、未验证的节点写清为什么');
      const ev = refs.map(r => records.get(r) || '').join('');
      nHtml.push(`<button type="button" class="pnode ${st}"><span>${pad2(j + 1)} ${e(text(p, nd, 'title', nw))}</span><span class="st">${NODE_STATES[st]}</span>`
        + `<span class="node-ev"><span class="label">第 ${j + 1} 步 · ${NODE_STATES[st]}</span><b>${e(get(nd, 'title'))}</b><p>${e(get(nd, 'note', ''))}</p>${ev}</span></button>`);
      if (j < nodes.length - 1 && j < links.length) {
        const nxt = get(nodes[j + 1], 'state', 'unknown');
        nHtml.push(`<div class="plink ${e(nxt)}">↓ ${e(links[j])}</div>`);
      }
    });
    const overall = states.includes('fail') ? 'fail' : states.includes('blocked') ? 'blocked' : states.includes('unknown') ? 'unknown' : 'pass';
    const tagCls = { pass: '', fail: 'fail', blocked: 'warn', unknown: 'unknown' }[overall];
    const name = text(p, pa, 'name', w);
    plist.push(`<button type="button" data-path="${i}" aria-pressed="false"><span class="sdot ${overall}"></span>${e(name)}<small>${NODE_STATES[overall]}</small></button>`);
    const detail = e(text(p, pa, 'detail', w));
    pflows.push(`<div class="path-flow" data-path="${i}"><div class="path-title"><b>${e(name)}</b><span class="tag ${tagCls}">${NODE_STATES[overall]}</span></div>`
      + `${nHtml.join('')}<div class="evidence-box"><p>${detail}</p></div><div class="path-detail-src" hidden><p>${detail}</p><small class="muted">点任意一步看依据。</small></div></div>`);
  });
  for (const iid of byId.keys()) if (!shown.has(iid)) p.add('data.paths', `条目 ${iid} 没挂到任何一步上，页面上看不到它；写进它验证的那一步的 items`);
  out.push('<section class="section"><div class="section-head"><h2>业务路径检查</h2><span><button type="button" data-play="paths">▶ 回放这条路径</button> '
    + '<button type="button" data-stop="paths">停止</button></span></div>'
    + `<div class="checks"><div class="path-list">${plist.join('')}</div><div>${pflows.join('')}</div></div>`
    + '<p class="muted" style="font-size:12px;margin-top:8px">回放只按已有的验收记录走一遍，不是重新测试。</p></section>');
  const launch = get(d, 'launch');
  if (truthy(launch)) {
    const li = list(get(launch, 'items') || []);
    if (li.map(x => get(x, 'title')).join('\u0000') !== LAUNCH_TITLES.join('\u0000') || li.length !== LAUNCH_TITLES.length)
      p.add('launch.items', '上线结果按顺序写这七项：' + LAUNCH_TITLES.join('、'));
    out.push('<section class="section"><div class="section-head"><h2>上线结果</h2></div>'
      + table(['项', '内容'], li.map(x => [e(get(x, 'title')), e(get(x, 'text'))])) + '</section>');
  }
  out.push(foot(c));
  return [out.join(''), shotsAll];
}

// ---------------- 入口 ----------------

const DATA_RE = /<script type="application\/json" id="doc-data">([\s\S]*?)<\/script>/;

function extract(path, outDir) {
  const m = DATA_RE.exec(readFileSync(path, 'utf8'));
  if (!m) {
    console.error('这份 index.html 里没有数据块，不是用 build_studio_doc.mjs 生成的（旧 Skill 手写的页面）。'
      + '下一步：按这份文档的数据说明，照这份页面的内容新写 data.json，version 接着旧版加一，再跑 build_studio_doc.mjs 生成');
    return 1;
  }
  const data = JSON.parse(m[1].replaceAll('<\\/', '</'));
  const sources = data._demo_sources || {};
  delete data._demo_sources;
  mkdirSync(outDir, { recursive: true });
  const root = resolve(outDir);
  for (const [rel, src] of Object.entries(sources)) {
    const target = resolve(root, rel);
    const inside = relative(root, target);
    if (!inside || inside.startsWith('..') || isAbsolute(inside)) {
      console.error(`跳过不在目录内的 Demo 路径 ${rel}`);
      continue;
    }
    mkdirSync(dirname(target), { recursive: true });
    writeFileSync(target, src, 'utf8');
  }
  const n = Object.keys(sources).length;
  writeFileSync(join(outDir, 'data.json'), JSON.stringify(data, null, 2) + '\n', 'utf8');
  console.log(`已取回 ${join(outDir, 'data.json')}` + (n ? ` 和 ${n} 个 Demo 文件` : ''));
  return 0;
}

const SHOT_JS = [
  "const { chromium } = require('@playwright/test');",
  "(async () => {",
  "  const [file, outDir] = process.argv.slice(1);",
  "  const browser = await chromium.launch();",
  "  let bad = 0;",
  "  for (const w of [400, 900]) {",
  "    const page = await browser.newPage({ viewport: { width: w, height: 900 } });",
  "    const errs = [];",
  "    page.on('pageerror', e => errs.push(e.message));",
  "    page.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });",
  "    await page.goto('file://' + file);",
  "    await page.waitForTimeout(800);",
  "    for (const b of await page.$$('[data-reset]')) { await b.click(); }",
  "    await page.waitForTimeout(300);",
  "    const out = `${outDir}/shot-${w}.png`;",
  "    await page.screenshot({ path: out, fullPage: true });",
  "    console.log(`${w}px：${out}` + (errs.length ? `；页面脚本报错：${errs.join(' | ')}` : ''));",
  "    if (errs.length) bad = 1;",
  "    await page.close();",
  "  }",
  "  await browser.close();",
  "  process.exit(bad);",
  "})().catch(e => { console.error('截图失败：' + e.message); process.exit(2); });",
].join('\n');

function shot(index, frontend) {
  const outDir = join(dirname(index), '.shots');
  mkdirSync(outDir, { recursive: true });
  // 用跑这个脚本的同一个 Node（Studio 随包的那个），在应用的 frontend 目录里找 @playwright/test
  const run = spawnSync(process.execPath, ['-e', SHOT_JS, resolve(index), resolve(outDir)], { cwd: frontend, encoding: 'utf8', timeout: 180000 });
  if (run.error) {
    console.error(`截图没跑成：${run.error.message}`);
    return 2;
  }
  console.log(((run.stdout || '') + (run.stderr || '')).trim());
  if (run.status === 2) console.error('前端目录里要有 @playwright/test 和浏览器（npx playwright install chromium）；截不了图时按检查清单逐条读生成的页面');
  return run.status ?? 2;
}

const MARK_RE = /<meta name="studio-doc" content="(prd|proposal|progress|acceptance);sha256=([0-9a-f]{64})">/;

/** 生成标记：页面其余部分的 sha256。手写或手改过的页面对不上。 */
const marker = (docType, page) => `<meta name="studio-doc" content="${docType};sha256=${sha256(page)}">`;

function verify(index) {
  const page = readFileSync(index, 'utf8');
  const m = MARK_RE.exec(page);
  if (!m) {
    console.error(`${index} 不是 build_studio_doc.mjs 生成的（没有标记），不能保存：改 data.json 后重新生成`);
    return 1;
  }
  if (sha256(replaceFirst(page, m[0], '')) !== m[2]) {
    console.error(`${index} 生成后被改过，不能保存：改 data.json 后重新生成`);
    return 1;
  }
  console.log(`${index} 是生成的${DOC_NAMES[m[1]]}，没被改过`);
  return 0;
}

export function main(argv) {
  if (argv.length >= 2 && argv[0] === 'verify') return verify(argv[1]);
  if (argv.length >= 3 && argv[0] === 'extract') return extract(argv[1], argv[2]);
  if (argv.length >= 3 && argv[0] === 'shot') return shot(argv[1], argv[2]);
  if (argv.length < 2 || !DOC_TYPES.includes(argv[0])) {
    console.error(USAGE);
    return 2;
  }
  const docType = argv[0], dataPath = resolve(argv[1]);
  const outPath = argv.includes('-o') ? resolve(argv[argv.indexOf('-o') + 1]) : join(dirname(dataPath), 'index.html');
  let data;
  try {
    data = JSON.parse(readFileSync(dataPath, 'utf8'));
  } catch (exc) {
    console.error(`读不了 ${dataPath}：${exc.message}`);
    return 1;
  }
  const p = new Problems();
  const base = dirname(dataPath);
  let body, demos = '', shots = [];
  if (docType === 'prd') body = buildPrd(p, data);
  else if (docType === 'proposal') [body, demos] = buildProposal(p, data, base);
  else if (docType === 'progress') body = buildProgress(p, data);
  else [body, shots] = buildAcceptance(p, data, base);
  scanWords(p, data, 'data');
  for (const [key, whereTo] of Object.entries(MOVED_KEYS[docType] || {}))
    if (isObj(data) && Object.hasOwn(data, key)) p.add(`data.${key}`, `这一项不在${DOC_NAMES[docType]}里显示，删掉：${whereTo}`);
  if (isFile(outPath)) {
    const m = DATA_RE.exec(readFileSync(outPath, 'utf8'));
    if (m) {
      try {
        const oldV = get(JSON.parse(m[1].replaceAll('<\\/', '</')), 'version');
        if (Number.isInteger(oldV) && Number.isInteger(get(data, 'version')) && data.version < oldV)
          p.add('data.version', `上一次生成的是第 ${oldV} 版，版本号不能变小`);
      } catch { /* 旧页面的数据块坏了就不比版本号 */ }
    }
  }
  if (p.items.length) {
    console.log(`${DOC_NAMES[docType]}有 ${p.items.length} 处要改，改完再跑：`);
    for (const x of p.items) console.log('  ✗ ' + x);
    return 1;
  }
  const shell = readFileSync(SHELL, 'utf8');
  const stored = { ...data };
  if (docType === 'proposal')
    stored._demo_sources = Object.fromEntries(list(get(data, 'features', [])).filter(f => truthy(get(f, 'demo'))).map(f => [f.demo, readFileSync(join(base, f.demo), 'utf8')]));
  const payload = JSON.stringify(stored).replaceAll('</', '<\\/');
  let page = shell;
  page = replaceAll(page, '<!--TITLE-->', escape(`${DOC_NAMES[docType]} · ${str(data.app)}`));
  page = replaceAll(page, '<!--BODY-->', body);
  page = replaceAll(page, '<!--DEMOS-->', demos);
  page = replaceAll(page, '<!--DATA-->', payload);
  page = replaceFirst(page, '<head>', '<head>' + marker(docType, page));
  writeFileSync(outPath, page, 'utf8');
  const outDir = dirname(outPath);
  const files = ['index.html', ...(docType === 'proposal' ? ['acceptance.json'] : []), ...shots];
  const size = files.reduce((n, f) => n + (isFile(join(outDir, f)) ? statSync(join(outDir, f)).size : 0), 0);
  console.log(`已生成 ${outPath}（${Math.floor(Buffer.byteLength(page, 'utf8') / 1024)} KB）`);
  console.log('studio_write_proposal 的 files 放：' + files.join('、') + `（合计 ${Math.floor(size / 1024)} KB，上限 8 MB）`);
  return 0;
}

// Node 24.2 起有 import.meta.main；更早的版本按启动文件判断（插件目录可能是软链，比真实路径）。
// node -e 时 argv[1] 是 -e 代码的参数，不是启动文件
const evalMode = process.execArgv.some(x => /^(-e|-p|--eval|--print)(=|$)/.test(x));
const invoked = import.meta.main ?? (!evalMode && !!process.argv[1] && existsSync(process.argv[1]) && realpathSync(process.argv[1]) === realpathSync(fileURLToPath(import.meta.url)));
if (invoked) process.exitCode = main(process.argv.slice(2));
