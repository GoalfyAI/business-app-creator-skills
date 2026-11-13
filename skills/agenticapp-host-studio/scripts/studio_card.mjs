#!/usr/bin/env node
// Studio 表单与记忆卡的严格校验和定稿输出；只读输入、只写标准输出。只用 Node 自带模块。
import { existsSync, readFileSync, realpathSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { parseArgs } from 'node:util';

const full = re => new RegExp(`^(?:${re.source})$`);
const FORM_ID = /[a-z0-9][a-z0-9-]{0,63}/;
const QUESTION_ID = /[A-Za-z][A-Za-z0-9_-]{0,63}/;
const VALUE = /[A-Za-z0-9][A-Za-z0-9_.-]{0,63}/;
const LANG = /[a-z]{2,3}(-[A-Za-z0-9]{2,8})*/;
const HEX = /#[0-9a-f]{6}/;
const DATE = /\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])/;
const TIME = /([01]\d|2[0-3]):[0-5]\d/;
const DATETIME = new RegExp(DATE.source + 'T' + TIME.source);
const match = (re, v) => typeof v === 'string' && full(re).test(v);

const COMMON = ['id', 'label', 'type', 'required'];
const CUSTOM = ['allowCustom', 'customLabel', 'customPlaceholder'];
export const TYPES = {
  radio: ['options', 'defaultValue', ...CUSTOM],
  checkbox: ['options', 'maxSelections', 'defaultValue', ...CUSTOM],
  select: ['options', 'defaultValue', ...CUSTOM],
  text: ['placeholder', 'defaultValue'],
  textarea: ['placeholder', 'defaultValue'],
  url: ['placeholder', 'defaultValue'],
  email: ['placeholder', 'defaultValue'],
  tel: ['placeholder', 'defaultValue'],
  number: ['placeholder', 'min', 'max', 'step', 'defaultValue'],
  range: ['min', 'max', 'step', 'defaultValue'],
  date: ['defaultValue'],
  time: ['defaultValue'],
  'datetime-local': ['defaultValue'],
  color: ['options', 'defaultValue'],
  file: ['accept', 'multiple'],
  switch: ['defaultValue'],
  'direction-cards': ['cards', 'defaultValue'],
};
const CHOICE = new Set(['radio', 'checkbox', 'select', 'direction-cards']);
const MAX_OPTIONS = { radio: 7, checkbox: 7, select: 20, color: 7 };
const MEMORY_TYPES = ['user', 'feedback', 'project', 'reference', 'profile', 'rule'];
const FORM_OPEN = /<question-form\b([^>]*)>/g;
const ANY_FORM_TAG = /<(?:question-form|ask-question)\b/gi;
const CARD_OPEN = /<od-card\b([^>]*)>/g;
const ATTR = /\s+([a-z]+)="([^"<>]*)"/g;

const isObj = v => v !== null && typeof v === 'object' && !Array.isArray(v);
const has = (o, k) => Object.hasOwn(o, k);
const isNum = v => typeof v === 'number';
const len = s => [...s].length;
const sorted = a => [...a].sort();
const repr = v => (typeof v === 'string' ? `'${v}'` : v === undefined || v === null ? 'None' : JSON.stringify(v));

function text(errors, path, value, limit) {
  if (typeof value !== 'string' || !value.trim()) errors.push(`${path}：必须是非空字符串`);
  else if (len(value) > limit) errors.push(`${path}：不能超过 ${limit} 个字符，现在 ${len(value)} 个`);
}

function keys(errors, path, obj, allowed, required = []) {
  for (const k of sorted(Object.keys(obj).filter(k => !allowed.includes(k))))
    errors.push(`${path}.${k}：这个字段不允许出现，允许的是 ${sorted(allowed).join(', ')}`);
  for (const k of required) if (!has(obj, k)) errors.push(`${path}.${k}：必须写`);
}

function number(errors, path, value) {
  if (!isNum(value)) {
    errors.push(`${path}：必须是数字（不加引号）`);
    return false;
  }
  return true;
}

function checkOptions(errors, path, q, qtype) {
  const opts = q.options;
  const limit = MAX_OPTIONS[qtype];
  if (opts == null) return [];
  if (!Array.isArray(opts) || opts.length < 2 || opts.length > limit) {
    errors.push(`${path}.options：必须是 2–${limit} 项的数组`);
    return [];
  }
  const allowed = ['label', 'value', 'description', ...(qtype === 'select' ? ['group', 'trailingLabel'] : [])];
  const values = [];
  opts.forEach((o, i) => {
    const p = `${path}.options[${i}]`;
    if (!isObj(o)) {
      errors.push(`${p}：必须是对象 {"label", "value"}，不能只写字符串`);
      return;
    }
    keys(errors, p, o, allowed, ['label', 'value']);
    text(errors, `${p}.label`, o.label, 40);
    const v = o.value;
    const pattern = qtype === 'color' ? HEX : VALUE;
    const hint = qtype === 'color' ? '#rrggbb 小写' : '英文字母、数字、.、-、_，以字母或数字开头';
    if (!match(pattern, v)) errors.push(`${p}.value：必须是 ${hint}`);
    else if (values.includes(v)) errors.push(`${p}.value：和前面的选项重复（${v}）`);
    values.push(v);
    for (const [k, limitK] of [['description', 120], ['group', 20], ['trailingLabel', 12]]) if (has(o, k)) text(errors, `${p}.${k}`, o[k], limitK);
  });
  return values;
}

function checkCards(errors, path, q) {
  const cards = q.cards;
  if (!Array.isArray(cards) || cards.length < 2 || cards.length > 4) {
    errors.push(`${path}.cards：必须是 2–4 张卡的数组`);
    return [];
  }
  const ids = [];
  cards.forEach((c, i) => {
    const p = `${path}.cards[${i}]`;
    if (!isObj(c)) {
      errors.push(`${p}：必须是对象`);
      return;
    }
    const fields = ['id', 'label', 'mood', 'references', 'palette', 'displayFont', 'bodyFont'];
    keys(errors, p, c, fields, fields);
    const cid = c.id;
    if (!match(VALUE, cid)) errors.push(`${p}.id：必须是英文字母、数字、.、-、_`);
    else if (ids.includes(cid)) errors.push(`${p}.id：和前面的卡重复（${cid}）`);
    ids.push(cid);
    text(errors, `${p}.label`, c.label, 40);
    text(errors, `${p}.mood`, c.mood, 120);
    for (const k of ['displayFont', 'bodyFont']) text(errors, `${p}.${k}`, c[k], 80);
    const refs = c.references;
    if (!Array.isArray(refs) || refs.length < 1 || refs.length > 4) errors.push(`${p}.references：必须是 1–4 项的字符串数组`);
    else refs.forEach((r, j) => text(errors, `${p}.references[${j}]`, r, 40));
    const pal = c.palette;
    if (!Array.isArray(pal) || pal.length < 4 || pal.length > 6) errors.push(`${p}.palette：必须是 4–6 个颜色`);
    else pal.forEach((col, j) => { if (!match(HEX, col)) errors.push(`${p}.palette[${j}]：必须是 #rrggbb 小写`); });
  });
  return ids;
}

/** 和 Python float() 一样认的数字串：允许前后空白、科学计数、inf/nan，不认十六进制和空串。 */
function toFloat(s) {
  const t = s.trim();
  if (/^[+-]?(inf|infinity)$/i.test(t)) return t.startsWith('-') ? -Infinity : Infinity;
  if (/^[+-]?nan$/i.test(t)) return NaN;
  const plain = t.replace(/(?<=\d)_(?=\d)/g, '');
  if (!/^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$/.test(plain)) return null;
  return Number(plain);
}

function checkDefault(errors, path, q, qtype, values) {
  if (!has(q, 'defaultValue')) return;
  const d = q.defaultValue;
  const p = `${path}.defaultValue`;
  if (CHOICE.has(qtype)) {
    errors.push(`${p}：选择题禁止预选，推荐项写在 label 末尾「（推荐）」`);
    return;
  }
  if (typeof d !== 'string') {
    errors.push(`${p}：必须是字符串（数字也加引号，例如 "20"）`);
    return;
  }
  if (qtype === 'color') {
    if (!match(HEX, d)) errors.push(`${p}：必须是 #rrggbb 小写`);
    else if (values.length && !values.includes(d)) errors.push(`${p}：必须是 options 里的一个 value`);
  } else if (qtype === 'number' || qtype === 'range') {
    const n = toFloat(d);
    if (n === null) {
      errors.push(`${p}：必须是数字字符串`);
      return;
    }
    const lo = q.min, hi = q.max;
    if ((isNum(lo) && n < lo) || (isNum(hi) && n > hi)) errors.push(`${p}：必须在 min 和 max 之间`);
  } else if (qtype === 'date' && !match(DATE, d)) errors.push(`${p}：必须是 YYYY-MM-DD`);
  else if (qtype === 'time' && !match(TIME, d)) errors.push(`${p}：必须是 HH:MM（24 小时）`);
  else if (qtype === 'datetime-local' && !match(DATETIME, d)) errors.push(`${p}：必须是 YYYY-MM-DDTHH:MM`);
  else if (qtype === 'switch' && d !== 'true' && d !== 'false') errors.push(`${p}：必须是 "true" 或 "false"`);
  else if (!d.trim()) errors.push(`${p}：不能是空字符串，没有已定的值就不写`);
}

function checkQuestion(errors, path, q) {
  if (!isObj(q)) {
    errors.push(`${path}：必须是对象`);
    return null;
  }
  const qtype = q.type;
  if (typeof qtype !== 'string' || !has(TYPES, qtype)) {
    errors.push(`${path}.type：必须是 ${Object.keys(TYPES).join(', ')} 之一，现在是 ${repr(qtype)}`);
    return q.id;
  }
  keys(errors, path, q, [...COMMON, ...TYPES[qtype]], ['id', 'label', 'type']);
  const qid = q.id;
  if (!match(QUESTION_ID, qid)) errors.push(`${path}.id：必须以英文字母开头，只含字母、数字、-、_`);
  text(errors, `${path}.label`, q.label, 120);
  if (has(q, 'required') && typeof q.required !== 'boolean') errors.push(`${path}.required：必须是 true 或 false`);
  let values = [];
  if (['radio', 'checkbox', 'select'].includes(qtype)) {
    if (!has(q, 'options')) errors.push(`${path}.options：${qtype} 必须写选项`);
    values = checkOptions(errors, path, q, qtype);
  } else if (qtype === 'color') {
    values = checkOptions(errors, path, q, qtype);
  } else if (qtype === 'direction-cards') {
    values = checkCards(errors, path, q);
  }
  if (q.allowCustom != null && typeof q.allowCustom !== 'boolean') errors.push(`${path}.allowCustom：必须是 true 或 false`);
  for (const [k, limit] of [['customLabel', 30], ['customPlaceholder', 60], ['placeholder', 60], ['accept', 120]]) if (has(q, k)) text(errors, `${path}.${k}`, q[k], limit);
  if ((q.customLabel || q.customPlaceholder) && q.allowCustom !== true) errors.push(`${path}.customLabel：写了自定义文案就必须同时写 allowCustom: true`);
  if (qtype === 'checkbox' && has(q, 'maxSelections')) {
    const m = q.maxSelections;
    if (!Number.isInteger(m) || m < 1 || m > Math.max(values.length, 1)) errors.push(`${path}.maxSelections：必须是 1 到选项数之间的整数`);
  }
  if (qtype === 'file' && has(q, 'multiple') && typeof q.multiple !== 'boolean') errors.push(`${path}.multiple：必须是 true 或 false`);
  if (qtype === 'number' || qtype === 'range') {
    const present = ['min', 'max', 'step'].filter(k => has(q, k) && number(errors, `${path}.${k}`, q[k]));
    if (qtype === 'range') for (const k of ['min', 'max']) if (!has(q, k)) errors.push(`${path}.${k}：range 必须写`);
    if (present.includes('min') && present.includes('max') && q.min >= q.max) errors.push(`${path}.max：必须大于 min`);
    if (present.includes('step') && q.step <= 0) errors.push(`${path}.step：必须大于 0`);
  }
  checkDefault(errors, path, q, qtype, values);
  return qid;
}

export function checkForm(data) {
  const errors = [];
  if (!isObj(data)) return ['表单体：必须是对象 {"lang", "questions"}，不能是数组'];
  keys(errors, '表单体', data, ['lang', 'submitLabel', 'questions'], ['lang', 'questions']);
  if (!match(LANG, data.lang)) errors.push('表单体.lang：必须是语言标签，例如 "zh-CN"');
  if (has(data, 'submitLabel')) text(errors, '表单体.submitLabel', data.submitLabel, 12);
  const qs = data.questions;
  if (!Array.isArray(qs) || qs.length < 1 || qs.length > 5) {
    errors.push('表单体.questions：必须是 1–5 道题的数组');
    return errors;
  }
  const seen = new Set();
  qs.forEach((q, i) => {
    const qid = checkQuestion(errors, `questions[${i}]`, q);
    if (typeof qid === 'string' && seen.has(qid)) errors.push(`questions[${i}].id：和前面的题重复（${qid}）`);
    seen.add(qid);
  });
  return errors;
}

export function checkMemory(data) {
  const errors = [];
  if (!isObj(data)) return ['卡片体：必须是对象 {"summary", "used"}'];
  keys(errors, '卡片体', data, ['summary', 'used'], ['summary', 'used']);
  text(errors, '卡片体.summary', data.summary, 80);
  const used = data.used;
  if (!Array.isArray(used) || used.length < 1 || used.length > 10) {
    errors.push('卡片体.used：必须是 1–10 项的数组');
    return errors;
  }
  used.forEach((u, i) => {
    const p = `used[${i}]`;
    if (!isObj(u)) {
      errors.push(`${p}：必须是对象`);
      return;
    }
    keys(errors, p, u, ['type', 'name', 'id'], ['type', 'name']);
    if (!MEMORY_TYPES.includes(u.type)) errors.push(`${p}.type：必须是 ${sorted(MEMORY_TYPES).join(', ')} 之一`);
    text(errors, `${p}.name`, u.name, 40);
    if (has(u, 'id') && !match(VALUE, u.id)) errors.push(`${p}.id：必须是英文字母、数字、.、-、_`);
  });
  return errors;
}

const compact = data => JSON.stringify(data);

function loadJson(raw, label) {
  try {
    return [JSON.parse(raw), []];
  } catch (e) {
    return [null, [`${label}：不是合法 JSON（${e.message}）`]];
  }
}

const attrsOf = s => Object.fromEntries([...s.matchAll(ATTR)].map(m => [m[1], m[2]]));

/** 校验整条最终回复：最多一张表单且在最后，卡片和表单都不在代码块里，体都合格。 */
export function checkReply(reply) {
  const errors = [];
  const fences = [...reply.matchAll(/^\s*```/gm)].map(m => m.index);
  const inFence = pos => fences.filter(f => f < pos).length % 2 === 1;
  const tags = [...reply.matchAll(ANY_FORM_TAG)];
  if (tags.some(m => m[0].toLowerCase() !== '<question-form')) errors.push('回复：标签必须写 <question-form>，不能写 <ask-question> 或改大小写');
  const forms = [...reply.matchAll(FORM_OPEN)];
  if (forms.length > 1) errors.push(`回复：一轮只能有一张表单，现在有 ${forms.length} 张`);
  for (const m of forms) {
    if (inFence(m.index)) errors.push('回复：表单不能放进代码块');
    const attrs = attrsOf(m[1]);
    const ks = Object.keys(attrs);
    if (ks.length !== 2 || !has(attrs, 'id') || !has(attrs, 'title') || m[1].replace(ATTR, '').trim()) errors.push('回复：开标签必须正好是 <question-form id="…" title="…">');
    if (!match(FORM_ID, attrs.id ?? '')) errors.push('回复：表单 id 只能用小写英文、数字、-');
    text(errors, '回复：表单 title', attrs.title, 30);
    const end = reply.indexOf('</question-form>', m.index + m[0].length);
    if (end < 0) {
      errors.push('回复：表单缺闭合标签 </question-form>');
      continue;
    }
    const body = reply.slice(m.index + m[0].length, end).trim();
    if (body.startsWith('```')) errors.push('回复：表单体不能包代码围栏');
    const [data, err] = loadJson(body, '回复：表单体');
    errors.push(...(err.length ? err : checkForm(data)));
    if (reply.slice(end + '</question-form>'.length).trim()) errors.push('回复：</question-form> 后面不能再有任何文字，表单必须是这一轮的最后输出');
  }
  const cards = [...reply.matchAll(CARD_OPEN)];
  for (const m of cards) {
    if (inFence(m.index)) errors.push('回复：记忆卡不能放进代码块');
    const attrs = attrsOf(m[1]);
    if (Object.keys(attrs).length !== 1 || attrs.type !== 'memory-applied' || m[1].replace(ATTR, '').trim()) errors.push('回复：记忆卡开标签必须正好是 <od-card type="memory-applied">');
    const end = reply.indexOf('</od-card>', m.index + m[0].length);
    if (end < 0) {
      errors.push('回复：记忆卡缺闭合标签 </od-card>');
      continue;
    }
    const [data, err] = loadJson(reply.slice(m.index + m[0].length, end).trim(), '回复：记忆卡体');
    errors.push(...(err.length ? err : checkMemory(data)));
  }
  if (cards.length > 1) errors.push('回复：一轮最多一张记忆卡');
  return errors;
}

const USAGE = `用法：
  node studio_card.mjs form --id <表单 id> --title <标题> <表单体 JSON 文件，- 表示标准输入>   # 校验表单体，合格时输出整段 <question-form>
  node studio_card.mjs memory <记忆卡 JSON 文件或 ->   # 校验记忆卡，合格时输出整段 <od-card>
  node studio_card.mjs reply <整条回复的文件或 ->   # 校验一整条最终回复里的表单和记忆卡`;

const readInput = path => readFileSync(path === '-' ? 0 : path, 'utf8');

export function main(argv) {
  let args;
  try {
    const { values, positionals } = parseArgs({ args: argv, allowPositionals: true, options: { id: { type: 'string' }, title: { type: 'string' } } });
    const [cmd, input, ...rest] = positionals;
    if (!['form', 'memory', 'reply'].includes(cmd)) throw new Error('第一个参数写 form、memory 或 reply');
    if (input === undefined) throw new Error('缺少输入文件（用 - 表示标准输入）');
    if (rest.length) throw new Error(`多出参数：${rest.join(' ')}`);
    if (cmd === 'form' && (values.id === undefined || values.title === undefined)) throw new Error('form 要写 --id 和 --title');
    if (cmd !== 'form' && (values.id !== undefined || values.title !== undefined)) throw new Error(`${cmd} 不用 --id、--title`);
    args = { cmd, input, ...values };
  } catch (e) {
    console.error(`${USAGE}\n${e.message}`);
    return 2;
  }
  const raw = readInput(args.input);
  let errors, out;
  if (args.cmd === 'reply') {
    errors = checkReply(raw);
    out = '回复合格';
  } else {
    let data;
    [data, errors] = loadJson(raw, '输入');
    if (args.cmd === 'form') {
      if (!match(FORM_ID, args.id)) errors.push('--id：只能用小写英文、数字、-');
      if (!args.title.trim() || len(args.title) > 30 || /["<>]/.test(args.title)) errors.push('--title：必须是 1–30 个字符，不能含 " < >');
      if (data !== null) errors.push(...checkForm(data));
      out = `<question-form id="${args.id}" title="${args.title}">${compact(data)}</question-form>`;
    } else {
      if (data !== null) errors.push(...checkMemory(data));
      out = `<od-card type="memory-applied">${compact(data)}</od-card>`;
    }
  }
  if (errors.length) {
    console.error('不合格，按下面逐条改完再运行一次：');
    for (const e of errors) console.error(`- ${e}`);
    return 1;
  }
  console.log(out);
  return 0;
}

// Node 24.2 起有 import.meta.main；更早的版本按启动文件判断（插件目录可能是软链，比真实路径）。
// node -e 时 argv[1] 是 -e 代码的参数，不是启动文件
const evalMode = process.execArgv.some(x => /^(-e|-p|--eval|--print)(=|$)/.test(x));
const invoked = import.meta.main ?? (!evalMode && !!process.argv[1] && existsSync(process.argv[1]) && realpathSync(process.argv[1]) === realpathSync(fileURLToPath(import.meta.url)));
if (invoked) process.exitCode = main(process.argv.slice(2));
