#!/usr/bin/env node
// T-3269: 本地反馈报告与决定校验；只写报告文件，不调用应用写接口。只用 Node 自带模块。
import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { existsSync, lstatSync, mkdirSync, readFileSync, realpathSync, statSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseArgs } from 'node:util';

export const BEGIN = '<!-- feedback-decisions:v1 -->';
export const END = '<!-- /feedback-decisions:v1 -->';
const FIELDS = ['issue_id', 'business_ui_id', 'feedback_ids', 'decision', 'rejection_reason', 'developer_notes', 'implementation_status'];
const STATES = ['not_started', 'in_progress', 'review_ready', 'blocked'];
const MAX_ID = 2n ** 64n - 1n;
const ID = /^[1-9][0-9]{0,19}$/;
// 应用 ID（public_id）：存量为十进制数字串，新应用为含至少一个字母的 8 位小写字母数字短码。 [需求:T-4735]
const APP_ID = '[1-9][0-9]{0,19}|(?=[0-9]*[a-z])[a-z0-9]{8}';
const ISSUE = new RegExp(`^BUI-(${APP_ID})-I[0-9]{3,}$`);
const IMAGE_ID = /^[A-Za-z0-9_-]{1,128}$/;
const EXT = { 'image/png': 'png', 'image/jpeg': 'jpg', 'image/webp': 'webp' };
// 和 Python re.M 一致：^ 只认开头或 \n 之后，$ 只认结尾或 \n 之前
const BLOCK = /(?<=^|\n)```yaml feedback-decision\n([\s\S]*?)\n```(?=\n|$)/g;

export class ValueError extends Error {
  constructor(message) { super(message); this.name = 'ValueError'; }
}

/** JSON 里带小数点或指数的数（1.0、1e2）：Python 读成 float，写回是 1.0、100.0，摘要要跟着一样。 */
class PyFloat extends Number {}

const isObj = v => v !== null && typeof v === 'object' && !Array.isArray(v) && !(v instanceof PyFloat);
const get = (o, k, d) => (isObj(o) && Object.hasOwn(o, k) ? o[k] : d);
const truthy = v => !(v == null || v === false || v === 0 || v === '' || (v instanceof PyFloat && !Number(v)) || (Array.isArray(v) && !v.length) || (isObj(v) && !Object.keys(v).length));
const pyStr = v => (v == null ? 'None' : v === true ? 'True' : v === false ? 'False' : v instanceof PyFloat ? pyFloat(Number(v)) : typeof v === 'number' ? pyNumber(v) : String(v));

/** 读 JSON：超出安全范围的整数保留成 BigInt（旧接口的应用 ID 最大到 2^64-1），浮点数记成 PyFloat。 */
export function parseJson(text) {
  return JSON.parse(text, (_k, v, ctx) => {
    if (typeof v !== 'number' || !ctx) return v;
    if (/[.eE]/.test(ctx.source)) return new PyFloat(v);
    return Number.isSafeInteger(v) ? v : BigInt(ctx.source);
  });
}

/** Python float repr：最短位数，指数 <-4 或 >=16 时用科学计数、指数至少两位，整数值带 .0。 */
function pyFloat(n) {
  if (!Number.isFinite(n)) return Number.isNaN(n) ? 'NaN' : n > 0 ? 'Infinity' : '-Infinity';
  if (Object.is(n, -0)) return '-0.0';
  const [digits, exp] = n.toExponential().split('e');
  const e = Number(exp);
  if (e < -4 || e >= 16) return `${digits}e${e < 0 ? '-' : '+'}${String(Math.abs(e)).padStart(2, '0')}`;
  const s = String(n);
  return s.includes('.') ? s : s + '.0';
}

const pyNumber = n => (Number.isInteger(n) ? String(n) : pyFloat(n));
// Python 按码点排序键；JS 默认按 UTF-16 码元，表情这类字符会排错
const byCodePoint = (a, b) => { const x = [...a], y = [...b]; for (let i = 0; i < Math.min(x.length, y.length); i++) if (x[i] !== y[i]) return x[i].codePointAt(0) - y[i].codePointAt(0); return x.length - y.length; };

/** 和 Python json.dumps(ensure_ascii=False) 一样的输出：源数据摘要和决定块都靠它，换了写法旧报告就对不上。 */
export function pyDumps(v, { compact = false, sortKeys = false, indent = null } = {}, level = 0) {
  const [comma, colon] = compact ? [',', ':'] : [indent === null ? ', ' : ',', ': '];
  const nl = indent === null ? '' : '\n' + ' '.repeat(indent * (level + 1));
  const end = indent === null ? '' : '\n' + ' '.repeat(indent * level);
  if (v === null || v === undefined) return 'null';
  if (v === true) return 'true';
  if (v === false) return 'false';
  if (typeof v === 'bigint') return v.toString();
  if (v instanceof PyFloat) return pyFloat(Number(v));
  if (typeof v === 'number') return pyNumber(v);
  if (typeof v === 'string') return JSON.stringify(v);
  const opts = { compact, sortKeys, indent };
  if (Array.isArray(v)) {
    if (!v.length) return '[]';
    return '[' + nl + v.map(x => pyDumps(x, opts, level + 1)).join(comma + nl) + end + ']';
  }
  const keys = Object.keys(v);
  if (!keys.length) return '{}';
  if (sortKeys) keys.sort(byCodePoint);
  return '{' + nl + keys.map(k => JSON.stringify(k) + colon + pyDumps(v[k], opts, level + 1)).join(comma + nl) + end + '}';
}

/** 规范化应用 ID：旧报告与旧接口的整数转十进制串，字符串须符合 public_id 规则。 */
export function appId(value) {
  if ((typeof value === 'bigint' && value > 0n && value <= MAX_ID) || (typeof value === 'number' && Number.isInteger(value) && value > 0 && value <= 2 ** 64 - 1))
    return BigInt(value).toString();
  if (typeof value === 'string' && new RegExp(`^(?:${APP_ID})$`).test(value) && (!/^[0-9]+$/.test(value) || BigInt(value) <= MAX_ID)) return value;
  throw new ValueError('invalid business_ui_id');
}

function load(path) {
  const text = readFileSync(path, 'utf8');
  try {
    return parseJson(text);
  } catch (e) {
    // V8 的报错会带一小段原文，附件元数据里是签名地址，不带出来
    if (e instanceof SyntaxError) throw new ValueError(`${path} 不是合法 JSON`);
    throw e;
  }
}
export const digest = data => createHash('sha256').update(data).digest('hex');
const sourceHash = raw => digest(Buffer.from(pyDumps(raw, { compact: true, sortKeys: true }), 'utf8'));

const ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#x27;', '`': '&#96;', '*': '&#42;', _: '&#95;', '[': '&#91;', ']': '&#93;', '\\': '&#92;' };
// 原文永远不是 Markdown 结构或 HTML。保留逐行原文；原字节另存 JSON。
const literal = value => pyStr(value).split('\n').map(line => '> ' + line.replace(/[&<>"'`*_[\]\\]/g, c => ESC[c])).join('\n');

function records(raw) {
  const result = new Map();
  for (const row of raw.items) {
    const key = get(row, 'feedback_id');
    if (typeof key !== 'string' || !ID.test(key) || BigInt(key) > MAX_ID || result.has(key)) throw new ValueError('invalid/duplicate feedback_id');
    appId(get(row, 'business_ui_id'));
    if (typeof get(row, 'content') !== 'string' || !Array.isArray(get(row, 'images'))) throw new ValueError('missing original feedback');
    result.set(key, row);
  }
  return result;
}

const sameKeys = (a, b) => a.length === b.length && a.every(k => b.includes(k));
const sameList = (a, b) => Array.isArray(a) && Array.isArray(b) && a.length === b.length && a.every((x, i) => x === b[i]);

function checkDecision(d, source) {
  if (!sameKeys(Object.keys(d), FIELDS) || typeof d.issue_id !== 'string') throw new ValueError('unknown decision format');
  const m = ISSUE.exec(d.issue_id);
  let app;
  try {
    app = appId(d.business_ui_id);
  } catch (e) {
    if (!(e instanceof ValueError)) throw e;
    app = null;
  }
  if (!m || app === null || m[1] !== app) throw new ValueError('issue/application mismatch');
  const ids = d.feedback_ids;
  if (!Array.isArray(ids) || !ids.length || ids.some(x => typeof x !== 'string') || new Set(ids).size !== ids.length) throw new ValueError('invalid feedback_ids');
  if (ids.some(x => !source.has(x) || appId(source.get(x).business_ui_id) !== app)) throw new ValueError('feedback/application mismatch');
  if (!['pending', 'accepted', 'rejected'].includes(d.decision) || !STATES.includes(d.implementation_status)) throw new ValueError('invalid decision/status');
  if (['rejection_reason', 'developer_notes'].some(x => typeof d[x] !== 'string')) throw new ValueError('decision notes must be strings');
  if (d.decision === 'rejected' && !d.rejection_reason.trim()) throw new ValueError('rejected requires a reason');
  if (d.decision !== 'accepted' && ['in_progress', 'review_ready'].includes(d.implementation_status)) throw new ValueError('unaccepted issue cannot be implemented');
}

const count = (s, sub) => s.split(sub).length - 1;
// 和 Python str.splitlines() 一样的换行字符；结尾的换行不多出一行
const splitlines = s => (s ? s.replace(/(\r\n|[\n\r\v\f\x1c-\x1e\x85\u2028\u2029])$/, '').split(/\r\n|[\n\r\v\f\x1c-\x1e\x85\u2028\u2029]/) : []);

function jsonValue(text) {
  try {
    return parseJson(text);
  } catch (e) {
    throw new ValueError(e.message);
  }
}

function parseDecisions(text, source) {
  if (count(text, BEGIN) !== 1 || count(text, END) !== 1) throw new ValueError('missing/duplicate decision section');
  const [before, tail] = text.split(BEGIN);
  const parts = tail.split(END);
  if (parts.length !== 2) throw new ValueError('decision section end marker comes before its start marker');
  const [area, after] = parts;
  if ((before + after).includes('```yaml feedback-decision')) throw new ValueError('decision block outside decision section');
  const blocks = [...area.matchAll(BLOCK)].map(m => m[1]);
  if (area.replace(BLOCK, '').trim()) throw new ValueError('unknown content in decision section');
  const result = new Map();
  for (const block of blocks) {
    // 有意只支持模板的单层 YAML 子集：JSON 数组/引号字符串、整数（旧报告的 business_ui_id）与未加引号枚举。
    const d = {};
    for (const line of splitlines(block)) {
      const i = line.indexOf(':');
      const key = i < 0 ? line : line.slice(0, i);
      if (i < 0 || !FIELDS.includes(key) || Object.hasOwn(d, key)) throw new ValueError('invalid/duplicate decision field');
      const value = line.slice(i + 1).trim();
      if (!value) throw new ValueError('use quoted empty string');
      if (key === 'business_ui_id') {
        try {
          d[key] = parseJson(value);
        } catch {
          throw new ValueError('business_ui_id must be a JSON number or quoted string');
        }
      } else if ('["'.includes(value[0])) {
        d[key] = jsonValue(value);
      } else if (/^[A-Za-z0-9_-]+$/.test(value)) {
        d[key] = value;
      } else {
        throw new ValueError('use JSON quoted string for notes');
      }
    }
    checkDecision(d, source);
    if (result.has(d.issue_id)) throw new ValueError('duplicate issue_id');
    result.set(d.issue_id, d);
  }
  return result;
}

export function validate(report, raw, issues) {
  const source = records(raw);
  if (count(report, '<!-- feedback-source-sha256:') !== 1 || !report.includes('<!-- feedback-source-sha256:' + sourceHash(raw) + ' -->'))
    throw new ValueError('raw evidence changed; rebuild and re-read the report');
  const decisions = parseDecisions(report, source);
  const expected = new Map(issues.map(i => [i.issue_id, i]));
  if (expected.size !== issues.length || !sameKeys([...decisions.keys()], [...expected.keys()])) throw new ValueError('decision/issue inventory mismatch');
  for (const [key, d] of decisions) {
    const issue = expected.get(key);
    if (appId(d.business_ui_id) !== appId(issue.business_ui_id) || !sameList(d.feedback_ids, issue.feedback_ids)) throw new ValueError('decision associations changed');
  }
  const all = [...decisions.values()];
  return {
    report_sha256: digest(Buffer.from(report, 'utf8')),
    accepted: all.filter(d => d.decision === 'accepted' && d.implementation_status !== 'review_ready'),
    decisions: all,
  };
}

const isRealFile = p => { try { return statSync(p).isFile() && !lstatSync(p).isSymbolicLink(); } catch { return false; } };
const cmp = (a, b) => { for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return a[i] < b[i] ? -1 : 1; return 0; };

export function render(raw, issues, previous = null, imageDir = null) {
  const source = records(raw);
  const old = previous != null ? parseDecisions(previous, source) : new Map();
  const decisions = [];
  const seen = new Set();
  const scope = get(raw, 'scope', {});
  const lines = [
    '# 智能应用用户反馈报告',
    '<!-- feedback-source-sha256:' + sourceHash(raw) + ' -->',
    '',
    literal('business_ui_id：' + get(scope, 'business_ui_ids', []).map(pyStr).join(', ')),
    '',
    literal('使用范围：' + get({ formal: '正式使用', preview: '预览' }, get(scope, 'usage_mode', 'formal'), '未提供')),
    '',
    literal('截至：' + pyStr(get(raw, 'snapshot_at', '未提供'))),
    '',
    '反馈数量：' + source.size,
  ];
  for (const [field, label] of [['from', '开始时间'], ['to', '结束时间（不含）']]) {
    const v = get(scope, field);
    if (truthy(v)) lines.push('', literal(label + '：' + pyStr(v)));
  }
  if (get(raw, 'complete') !== true || get(raw, 'has_more') !== false) lines.push('', '反馈未取全，以下仅为已读取的内容。');
  if (!source.size) lines.push('', '本次查询未读取到反馈。');
  const category = i => get(i, 'category', '待分类');
  let group = null;
  const ordered = [...issues].sort((a, b) => cmp([appId(a.business_ui_id), category(a), a.issue_id], [appId(b.business_ui_id), category(b), b.issue_id]));
  for (const issue of ordered) {
    const current = [appId(issue.business_ui_id), category(issue)];
    if (!group || cmp(current, group)) {
      lines.push('', '## 应用 ' + current[0], literal('问题类型：' + current[1]));
      group = current;
    }
    const key = issue.issue_id;
    if (seen.has(key)) throw new ValueError('duplicate issue_id');
    seen.add(key);
    const decision = old.get(key) ?? {
      issue_id: key,
      business_ui_id: appId(issue.business_ui_id),
      feedback_ids: issue.feedback_ids,
      decision: 'pending',
      rejection_reason: '',
      developer_notes: '',
      implementation_status: 'not_started',
    };
    if (appId(decision.business_ui_id) !== appId(issue.business_ui_id) || !sameList(decision.feedback_ids, issue.feedback_ids))
      throw new ValueError('existing issue associations changed; create a new pending issue');
    checkDecision(decision, source);
    decisions.push(decision);
    const reporters = new Set(issue.feedback_ids.map(x => get(source.get(x), 'reporter_ref')).filter(x => x != null));
    lines.push(
      '',
      '### ' + key,
      literal(get(issue, 'title', '待分类问题')),
      literal(`应用：${pyStr(issue.business_ui_id)}；分类：${pyStr(category(issue))}；反馈：${issue.feedback_ids.length} 条；已知独立用户：${reporters.size}`),
      literal('来源：' + issue.feedback_ids.join(', ')),
    );
    for (const [field, label] of [['analysis', '分析'], ['suggestion', '建议'], ['implementation_result', '处理结果']])
      if (truthy(get(issue, field))) lines.push('', literal(label + '：' + issue[field]));
  }
  if ([...old.keys()].some(k => !seen.has(k))) throw new ValueError('refresh cannot discard existing decisions');
  if (decisions.length) lines.push('', '## 创建者决定', '', '只编辑下方决定块；备注用 JSON 双引号字符串。');
  lines.push('', BEGIN);
  for (const d of decisions) lines.push('```yaml feedback-decision', ...Object.entries(d).map(([k, v]) => k + ': ' + pyDumps(v)), '```');
  lines.push(END, '', '## 反馈原文');
  for (const [key, row] of source) {
    lines.push(
      '',
      '### 反馈 ' + key,
      '',
      literal('business_ui_id：' + pyStr(row.business_ui_id)),
      '',
      literal('提交时间：' + pyStr(get(row, 'created_at', '未提供'))),
      '',
      literal('上报版本：' + pyStr(get(get(row, 'context', {}), 'app_version', '未提供'))),
      '',
      literal(row.content),
      '',
    );
    if (Object.hasOwn(row, 'status')) {
      const status = row.status;
      const label = get({ pending: '待处理', completed: '已完成', rejected: '不予处理' }, status, '未知状态');
      lines.push(literal('处理状态：' + label), '');
      if (status === 'rejected') lines.push(literal('原因：' + pyStr(get(row, 'rejection_reason', '未提供'))), '');
      else if (status === 'completed')
        lines.push(literal('完成版本：' + pyStr(get(row, 'completed_version', '未提供'))), '', literal('处理说明：' + pyStr(get(row, 'resolution_note', '未提供'))), '');
    }
    for (const im of row.images) {
      const ext = get(EXT, get(im, 'content_type'));
      const iid = get(im, 'image_id', '');
      if (typeof iid !== 'string' || !IMAGE_ID.test(iid) || !ext) throw new ValueError('invalid image metadata');
      const name = key + '-' + iid + '.' + ext;
      const file = imageDir ? join(imageDir, name) : null;
      if (file && isRealFile(file) && digest(readFileSync(file)) === get(im, 'sha256')) lines.push('![反馈图片](images/' + name + ')');
      else lines.push('图片未读取：' + iid);
    }
  }
  const output = lines.join('\n') + '\n';
  validate(output, raw, issues);
  return output;
}

class HTTPError extends Error {
  constructor(message) { super(message); this.name = 'HTTPError'; }
}

const LIMIT = 10 * 1024 * 1024;

export async function download(metadata, feedbackId, imageId, outputDir) {
  if (!ID.test(feedbackId) || !IMAGE_ID.test(imageId)) throw new ValueError('invalid attachment identity');
  let url;
  try {
    url = new URL(metadata.url);
  } catch {
    throw new ValueError('HTTPS attachment URL required');
  }
  if (url.protocol !== 'https:' || !url.hostname || url.username || url.password) throw new ValueError('HTTPS attachment URL required');
  const ext = get(EXT, get(metadata, 'content_type'));
  const sha = get(metadata, 'sha256', '');
  if (!ext || typeof sha !== 'string' || !/^[a-f0-9]{64}$/.test(sha)) throw new ValueError('invalid attachment metadata');
  // 和 urllib 的 timeout 一样按单次读写限时 30 秒：每收到一段就重新计时，慢网下大图也能下完
  const ctrl = new AbortController();
  let timer;
  const arm = () => { clearTimeout(timer); timer = setTimeout(() => ctrl.abort(new DOMException('timed out', 'TimeoutError')), 30000); };
  const chunks = [];
  try {
    arm();
    const response = await fetch(metadata.url, { redirect: 'manual', signal: ctrl.signal });
    if ([301, 302, 303, 307, 308].includes(response.status)) throw new ValueError('unexpected image redirect; request a fresh attachment URL');
    if (!response.ok) throw new HTTPError(String(response.status));
    let size = 0;
    for await (const chunk of response.body) {
      arm();
      chunks.push(chunk);
      size += chunk.length;
      if (size > LIMIT) break;
    }
  } finally {
    clearTimeout(timer);
  }
  const body = Buffer.concat(chunks).subarray(0, LIMIT + 1);
  if (body.length > LIMIT || digest(body) !== sha || body.length !== Number(get(metadata, 'size_bytes'))) throw new ValueError('attachment size/digest mismatch');
  mkdirSync(outputDir, { recursive: true });
  const target = join(outputDir, feedbackId + '-' + imageId + '.' + ext);
  // 不覆盖已存在的本地证据；相同摘要重放可直接复用。
  let stat = null;
  try {
    stat = lstatSync(target);
  } catch (e) {
    if (e.code !== 'ENOENT') throw e;
  }
  if (stat) {
    if (stat.isSymbolicLink() || digest(readFileSync(target)) !== sha) throw new ValueError('existing attachment differs');
  } else {
    writeFileSync(target, body, { flag: 'wx' });
  }
  return target;
}

const USAGE = `用法：
  node feedback_report.mjs render --raw <原始反馈.json> --issues <问题.json> --report <报告.md>
  node feedback_report.mjs validate --raw <原始反馈.json> --issues <问题.json> --report <报告.md> [--expected-sha256 <摘要>]
  node feedback_report.mjs download --metadata <附件元数据.json> --feedback-id <反馈 ID> --image-id <图片 ID> --output-dir <目录>`;

const ARGS = {
  render: ['raw', 'issues', 'report'],
  validate: ['raw', 'issues', 'report'],
  download: ['metadata', 'feedback-id', 'image-id', 'output-dir'],
};

// 只输出异常类型；业务校验错误输出原因。HTTP 异常正文可能包含签名 URL，不输出。
const PROXY_ENV = ['HTTPS_PROXY', 'https_proxy', 'HTTP_PROXY', 'http_proxy'];
const ERRNO = { ENOENT: 'FileNotFoundError', EACCES: 'PermissionError', EISDIR: 'IsADirectoryError', ENOTDIR: 'NotADirectoryError', EEXIST: 'FileExistsError' };
function describe(exc) {
  if (exc instanceof ValueError || exc instanceof SyntaxError) return exc.message;
  if (exc?.code && ERRNO[exc.code]) return ERRNO[exc.code];
  if (exc?.name === 'TimeoutError' || exc?.name === 'AbortError') return 'TimeoutError';
  if (exc instanceof TypeError && exc.message === 'fetch failed') return 'URLError';
  return exc?.name || 'Error';
}

export async function main(argv) {
  let a;
  try {
    const cmd = argv[0];
    if (!Object.hasOwn(ARGS, cmd)) throw new Error('第一个参数写 render、validate 或 download');
    const options = Object.fromEntries([...ARGS[cmd], ...(cmd === 'validate' ? ['expected-sha256'] : [])].map(k => [k, { type: 'string' }]));
    const { values } = parseArgs({ args: argv.slice(1), options });
    const missing = ARGS[cmd].filter(k => values[k] === undefined);
    if (missing.length) throw new Error('缺少参数：' + missing.map(k => '--' + k).join(', '));
    a = { cmd, ...values };
  } catch (e) {
    process.stderr.write(`${USAGE}\n${e.message}\n`);
    return 2;
  }
  try {
    if (a.cmd === 'download') {
      if (!process.env.NODE_USE_ENV_PROXY && PROXY_ENV.some(k => process.env[k])) {
        // Node 自带的 fetch 默认不走 HTTPS_PROXY（urllib 会），打开 NODE_USE_ENV_PROXY 重跑一次
        const run = spawnSync(process.execPath, [fileURLToPath(import.meta.url), ...argv], { stdio: 'inherit', env: { ...process.env, NODE_USE_ENV_PROXY: '1' } });
        return run.status ?? 2;
      }
      process.stdout.write((await download(load(a.metadata), a['feedback-id'], a['image-id'], a['output-dir'])) + '\n');
      return 0;
    }
    const report = a.report;
    let link = null;
    try {
      link = lstatSync(report);
    } catch (e) {
      if (e.code !== 'ENOENT') throw e;
    }
    if (link?.isSymbolicLink()) throw new ValueError('report symlink is not supported');
    const previous = link ? readFileSync(report, 'utf8') : null;
    const raw = load(a.raw), issues = load(a.issues);
    if (a.cmd === 'render') {
      const content = render(raw, issues, previous, join(dirname(report), 'images'));
      writeFileSync(report, content, 'utf8');
      process.stdout.write(pyDumps({ report_sha256: digest(Buffer.from(content, 'utf8')) }) + '\n');
    } else {
      if (previous === null) throw new ValueError('report not found');
      const result = validate(previous, raw, issues);
      if (a['expected-sha256'] && a['expected-sha256'] !== result.report_sha256) throw new ValueError('report changed; re-read creator decisions');
      process.stdout.write(pyDumps(result, { indent: 2 }) + '\n');
    }
    return 0;
  } catch (exc) {
    process.stderr.write(describe(exc) + '\n');
    return 2;
  }
}

// Node 24.2 起有 import.meta.main；更早的版本按启动文件判断（插件目录可能是软链，比真实路径）。
// node -e 时 argv[1] 是 -e 代码的参数，不是启动文件
const evalMode = process.execArgv.some(x => /^(-e|-p|--eval|--print)(=|$)/.test(x));
const invoked = import.meta.main ?? (!evalMode && !!process.argv[1] && existsSync(process.argv[1]) && realpathSync(process.argv[1]) === realpathSync(fileURLToPath(import.meta.url)));
if (invoked) process.exitCode = await main(process.argv.slice(2));
