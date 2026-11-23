#!/usr/bin/env node
// 声明文件 declaration.json：生成空模板、检查、给开发者的确认单、走查项清单。
// 只读声明文件，不解析应用代码，不连平台。只用 Node 自带模块。
import { existsSync, readFileSync, realpathSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

export const FIXED_DONE = '返回数据即完成';

export class ValueError extends Error {
  constructor(message) { super(message); this.name = 'ValueError'; }
}

const isObj = v => v !== null && typeof v === 'object' && !Array.isArray(v);
const blank = v => typeof v !== 'string' || !v.trim();
const hasCJK = s => typeof s === 'string' && /[㐀-鿿]/.test(s);
const PERMISSION = /^[^.\s]+\.[^.\s]+$/;
const isNone = v => isObj(v) && Object.hasOwn(v, 'none');

// 每类实体的中文名、字段与中文标签。字段顺序就是检查时列缺项的顺序。
const ENTITY = {
  app: '应用',
  roles: '角色',
  resourceControls: '资源控制点',
  tables: '数据表',
  taskflows: 'TaskFlow',
  automations: '自动任务',
  pages: '页面',
};
const LABEL = {
  version: '版本', key: '标识', name: '中文名称', description: '说明', summary: '功能说明',
  problem: '要解决的问题', users: '使用对象', doneWell: '做好的标准', scope: '范围', tradeoffs: '关键取舍',
  permissions: '权限点', partition: '划分', input: '输入', output: '输出', effect: '读还是写',
  permission: '权限点', doneWhen: '完成标准', uses: '用到的东西', schedule: '触发周期', call: '指向的 TaskFlow',
  notifyOnIncomplete: '未完成时通知谁', calls: '调用的 TaskFlow', none: '不适用的原因',
  by: '按哪个资源控制点', column: '对应的列', tools: '工具', agents: 'Agent', reads: '读的表', writes: '写的表',
};
const FIELDS = {
  top: ['version', 'app', 'roles', 'resourceControls', 'tables', 'taskflows', 'automations', 'pages'],
  app: ['name', 'problem', 'users', 'doneWell', 'scope', 'tradeoffs'],
  roles: ['key', 'name', 'permissions'],
  resourceControls: ['key', 'name', 'description'],
  tables: ['key', 'name', 'description', 'partition'],
  taskflows: ['key', 'name', 'summary', 'input', 'output', 'effect', 'permission', 'scope', 'doneWhen', 'uses'],
  automations: ['key', 'name', 'schedule', 'call', 'notifyOnIncomplete'],
  pages: ['key', 'name', 'summary', 'calls'],
  uses: ['tools', 'agents', 'reads', 'writes'],
};
const lab = f => `${LABEL[f] || f}（${f}）`;

/** 空模板：每类实体一条空示例项，值都是空字符串；数组里放一个空字符串，逼写的人改成真实内容或写明空数组。 */
export function template() {
  return {
    version: 1,
    app: { name: '', problem: '', users: '', doneWell: '', scope: '', tradeoffs: '' },
    roles: [{ key: '', name: '', permissions: [''] }],
    resourceControls: [{ key: '', name: '', description: '' }],
    tables: [{ key: '', name: '', description: '', partition: { by: '', column: '' } }],
    taskflows: [{
      key: '', name: '', summary: '', input: '', output: '', effect: '', permission: '',
      scope: { '': '' }, doneWhen: '', uses: { tools: [''], agents: [''], reads: [''], writes: [''] },
    }],
    automations: [{ key: '', name: '', schedule: '', call: '', notifyOnIncomplete: '' }],
    pages: [{ key: '', name: '', summary: '', calls: [''] }],
  };
}

/** 生成空模板文件；文件已存在时拒绝覆盖。 */
export function init(path) {
  if (existsSync(path)) throw new ValueError(`${path} 已存在，不覆盖；要重写请先自己改名或删掉`);
  writeFileSync(path, JSON.stringify(template(), null, 2) + '\n', { encoding: 'utf8', flag: 'wx' });
  return path;
}

/** 读声明文件；不是合法 JSON 时抛 ValueError。 */
export function load(path) {
  const text = readFileSync(path, 'utf8');
  try {
    return JSON.parse(text);
  } catch {
    throw new ValueError(`${path} 不是合法 JSON`);
  }
}

const listOf = v => (Array.isArray(v) ? v : []);
const tag = (o, i) => {
  const key = isObj(o) && !blank(o.key) ? o.key : null;
  const name = isObj(o) && !blank(o.name) ? o.name : null;
  if (key) return name ? `「${key}」（${name}）` : `「${key}」`;
  return `第 ${i + 1} 项`;
};

/**
 * 检查声明文件。返回 { ok, must: [...], notice: [...] }。
 * 每条：{ level, entity, item, problem, fix }；「请留意」另带 plain：给开发者看的业务话，不含标识与英文字段名。
 */
export function check(decl) {
  const must = [], notice = [];
  const M = (entity, item, problem, fix) => must.push({ level: '必须改', entity, item, problem, fix });
  const N = (entity, item, problem, fix, plain) => notice.push({ level: '请留意', entity, item, problem, fix, plain });

  if (!isObj(decl)) {
    M('声明文件', '', '整个文件不是一个 JSON 对象', '用 init 重新生成模板再填');
    return { ok: false, must, notice };
  }
  const extra = (entity, item, obj, allowed) => {
    const more = Object.keys(obj).filter(k => !allowed.includes(k));
    if (more.length) M(entity, item, `多出声明里没有的项：${more.join('、')}`, '删掉，或改成规定的项名（常见是拼错了）');
  };
  extra('声明文件', '', decl, FIELDS.top);
  if (decl.version !== 1) M('声明文件', '', `版本（version）应为 1，现在是 ${JSON.stringify(decl.version)}`, '写 "version": 1');

  // 一个对象里逐项看是否缺或为空，缺的合成一条
  const fieldsCheck = (entity, item, obj, fields, special = {}) => {
    const missing = [], at = must.length;
    for (const f of fields) {
      if (special[f]) { const r = special[f](obj[f]); if (r === 'missing') missing.push(lab(f)); continue; }
      if (blank(obj[f])) missing.push(lab(f));
    }
    // 缺项那条排在这一项其他问题前面
    if (missing.length) must.splice(at, 0, { level: '必须改', entity, item, problem: `缺这几项或还是空的：${missing.join('、')}`, fix: '逐项写上；不适用的写明取值和原因，不留空' });
  };
  const strList = (entity, item, f, { allowEmpty }) => v => {
    if (!Array.isArray(v)) return 'missing';
    if (!v.length) {
      if (allowEmpty) return 'ok';
      M(entity, item, `${lab(f)}是空数组，至少要有一项`, `写上${LABEL[f]}`);
      return 'ok';
    }
    if (v.some(blank)) { M(entity, item, `${lab(f)}里有空的一项（还是模板占位）`, allowEmpty ? '写上真实内容；确实没有就写成空数组 []' : '写上真实内容或删掉这一项'); return 'ok'; }
    const dup = v.filter((x, i) => v.indexOf(x) !== i);
    if (dup.length) M(entity, item, `${lab(f)}里有重复：${[...new Set(dup)].join('、')}`, '删掉重复的');
    return 'ok';
  };
  const textOrList = (entity, item, f) => v => {
    if (Array.isArray(v)) return strList(entity, item, f, { allowEmpty: false })(v);
    return blank(v) ? 'missing' : 'ok';
  };
  const noneOr = (entity, item, f, inner) => v => {
    if (!isObj(v)) return 'missing';
    if (isNone(v)) {
      extra(entity, item, v, ['none']);
      if (blank(v.none)) M(entity, item, `${lab(f)}写了不适用，但没写原因（none 为空）`, '在 none 里写一句为什么不适用');
      return 'ok';
    }
    return inner(v);
  };
  const cjkName = (entity, item, obj) => {
    if (!blank(obj.name) && !hasCJK(obj.name)) M(entity, item, `中文名称（name）「${obj.name}」里没有中文`, '写开发者看得懂的中文名称；英文标识放在 key 里');
  };
  const dupKeys = (entity, items) => {
    const seen = new Map();
    items.forEach((o, i) => {
      if (!isObj(o) || blank(o.key)) return;
      if (seen.has(o.key)) M(entity, tag(o, i), `标识（key）和第 ${seen.get(o.key) + 1} 项重复`, '每一项的标识各不相同');
      else seen.set(o.key, i);
    });
  };
  const arrayEntity = (field, { allowNone }) => {
    const entity = ENTITY[field], v = decl[field];
    if (allowNone && isObj(v) && isNone(v)) {
      extra(entity, '', v, ['none']);
      if (blank(v.none)) M(entity, '', `写了没有${entity}，但没写原因（none 为空）`, '在 none 里写一句为什么没有');
      return [];
    }
    if (!Array.isArray(v)) {
      M(entity, '', `缺${entity}（${field}）或格式不对`, allowNone ? `写成数组；确实没有就写 {"none": "原因"}` : '写成数组，至少一项');
      return [];
    }
    if (!v.length) {
      M(entity, '', `${entity}（${field}）是空数组`, allowNone ? `至少写一项；确实没有就写 {"none": "原因"}` : '至少写一项');
      return [];
    }
    v.forEach((o, i) => { if (!isObj(o)) M(entity, tag(o, i), '这一项不是 JSON 对象', '按模板的样子写'); });
    dupKeys(entity, v);
    return v.filter(isObj);
  };

  // 应用
  if (!isObj(decl.app)) M('应用', '', '缺应用（app）或格式不对', '按模板写出应用的六项');
  else {
    extra('应用', '', decl.app, FIELDS.app);
    fieldsCheck('应用', '', decl.app, FIELDS.app);
  }

  // 角色
  const roles = arrayEntity('roles', { allowNone: false });
  roles.forEach((o, i) => {
    const t = tag(o, i);
    extra('角色', t, o, FIELDS.roles);
    fieldsCheck('角色', t, o, FIELDS.roles, { permissions: strList('角色', t, 'permissions', { allowEmpty: false }) });
    cjkName('角色', t, o);
    for (const p of listOf(o.permissions)) if (!blank(p) && !PERMISSION.test(p)) M('角色', t, `权限点「${p}」不是「资源.动作」的写法`, '写成「资源.动作」，例如 lead.read');
  });

  // 资源控制点
  const rcs = arrayEntity('resourceControls', { allowNone: true });
  rcs.forEach((o, i) => {
    const t = tag(o, i);
    extra('资源控制点', t, o, FIELDS.resourceControls);
    fieldsCheck('资源控制点', t, o, FIELDS.resourceControls);
    cjkName('资源控制点', t, o);
  });
  const rcKeys = new Set(rcs.filter(o => !blank(o.key)).map(o => o.key));

  // 数据表
  const tables = arrayEntity('tables', { allowNone: false });
  tables.forEach((o, i) => {
    const t = tag(o, i);
    extra('数据表', t, o, FIELDS.tables);
    fieldsCheck('数据表', t, o, FIELDS.tables, {
      partition: noneOr('数据表', t, 'partition', p => {
        extra('数据表', t, p, ['by', 'column']);
        const miss = ['by', 'column'].filter(k => blank(p[k]));
        if (miss.length) { M('数据表', t, `划分（partition）缺：${miss.map(lab).join('、')}`, '写按哪个资源控制点划分、对应哪一列；不划分就写 {"none": "原因"}'); return 'ok'; }
        if (!rcKeys.has(p.by)) M('数据表', t, `划分用的资源控制点「${p.by}」没有定义`, '改成 resourceControls 里已有的标识，或先在 resourceControls 里定义它');
        return 'ok';
      }),
    });
    cjkName('数据表', t, o);
  });
  const tableKeys = new Set(tables.filter(o => !blank(o.key)).map(o => o.key));

  // TaskFlow
  const permsInRoles = new Set(roles.flatMap(r => listOf(r.permissions)).filter(p => !blank(p)));
  const taskflows = arrayEntity('taskflows', { allowNone: false });
  taskflows.forEach((o, i) => {
    const t = tag(o, i);
    extra('TaskFlow', t, o, FIELDS.taskflows);
    fieldsCheck('TaskFlow', t, o, FIELDS.taskflows, {
      input: textOrList('TaskFlow', t, 'input'),
      output: textOrList('TaskFlow', t, 'output'),
      scope: noneOr('TaskFlow', t, 'scope', s => {
        const keys = Object.keys(s);
        if (!keys.length) { M('TaskFlow', t, '范围限制（scope）是空对象', '写「资源控制点标识: 输入里的字段」；不按资源控制点限制就写 {"none": "原因"}'); return 'ok'; }
        for (const k of keys) {
          if (blank(k) || blank(s[k])) { M('TaskFlow', t, '范围限制（scope）里有空的一项（还是模板占位）', '写「资源控制点标识: 输入里的字段」；不按资源控制点限制就写 {"none": "原因"}'); continue; }
          if (!rcKeys.has(k)) M('TaskFlow', t, `范围限制用的资源控制点「${k}」没有定义`, '改成 resourceControls 里已有的标识，或先在 resourceControls 里定义它');
        }
        return 'ok';
      }),
      uses: u => {
        if (!isObj(u)) return 'missing';
        extra('TaskFlow', t, u, FIELDS.uses);
        const miss = FIELDS.uses.filter(k => !Array.isArray(u[k]));
        if (miss.length) M('TaskFlow', t, `用到的东西（uses）缺：${miss.map(lab).join('、')}`, '四项都要写成数组；没有就写空数组 []');
        for (const k of FIELDS.uses) if (Array.isArray(u[k])) strList('TaskFlow', t, k, { allowEmpty: true })(u[k]);
        for (const k of ['tools', 'agents']) for (const x of listOf(u[k])) if (!blank(x) && !hasCJK(x)) M('TaskFlow', t, `${lab(k)}「${x}」里没有中文`, '写开发者看得懂的中文名称；对应的平台资产写进施工单');
        for (const k of ['reads', 'writes']) for (const x of listOf(u[k])) if (!blank(x) && !tableKeys.has(x)) M('TaskFlow', t, `${lab(k)}里的「${x}」不是已定义的数据表`, '改成 tables 里已有的标识，或先在 tables 里定义这张表');
        return 'ok';
      },
    });
    cjkName('TaskFlow', t, o);
    if (!blank(o.effect) && !['read', 'write'].includes(o.effect)) M('TaskFlow', t, `读还是写（effect）只能是 read 或 write，现在是「${o.effect}」`, '只读数据写 read；会改数据或对外做事写 write');
    if (!blank(o.permission)) {
      if (!PERMISSION.test(o.permission)) M('TaskFlow', t, `权限点「${o.permission}」不是「资源.动作」的写法`, '写成「资源.动作」，例如 lead.read');
      else if (!permsInRoles.has(o.permission)) M('TaskFlow', t, `权限点「${o.permission}」不在任何角色里，没有人能做这件事`, '把它加进该能做这件事的角色的 permissions，或改成角色里已有的权限点');
    }
    const u = isObj(o.uses) ? o.uses : {};
    if (o.effect === 'read' && listOf(u.writes).some(x => !blank(x))) M('TaskFlow', t, '读还是写写的是 read，却列了写的表（writes）', '会改数据就把 effect 改成 write；只读就清空 writes');
    if (o.doneWhen === FIXED_DONE) {
      const why = [];
      if (o.effect !== 'read') why.push('不是只读（effect 不是 read）');
      if (listOf(u.tools).length) why.push('用了工具');
      if (listOf(u.agents).length) why.push('用了 Agent');
      if (listOf(u.writes).length) why.push('写了表');
      if (why.length) M('TaskFlow', t, `完成标准用了固定取值「${FIXED_DONE}」，但这件事${why.join('、')}`, '写一句能判断的完成标准：做完后看得到什么、库里多了或改了什么');
    }
  });
  const tfByKey = new Map(taskflows.filter(o => !blank(o.key)).map(o => [o.key, o]));

  // 自动任务
  const automations = arrayEntity('automations', { allowNone: true });
  automations.forEach((o, i) => {
    const t = tag(o, i);
    extra('自动任务', t, o, FIELDS.automations);
    fieldsCheck('自动任务', t, o, FIELDS.automations);
    cjkName('自动任务', t, o);
    if (!blank(o.call) && !tfByKey.has(o.call)) M('自动任务', t, `指向的 TaskFlow「${o.call}」不存在`, '改成 taskflows 里已有的标识，或先声明这个 TaskFlow');
  });

  // 页面
  const pages = arrayEntity('pages', { allowNone: false });
  pages.forEach((o, i) => {
    const t = tag(o, i);
    extra('页面', t, o, FIELDS.pages);
    fieldsCheck('页面', t, o, FIELDS.pages, { calls: strList('页面', t, 'calls', { allowEmpty: false }) });
    cjkName('页面', t, o);
    for (const c of listOf(o.calls)) if (!blank(c) && !tfByKey.has(c)) M('页面', t, `调用的 TaskFlow「${c}」不存在`, '改成 taskflows 里已有的标识，或先声明这个 TaskFlow');
  });

  // 请留意：只在引用能对上时才有意义，按已定义的东西算
  const nameOf = (map, k) => (map.get(k)?.name && !blank(map.get(k).name) ? map.get(k).name : k);
  const tableByKey = new Map(tables.filter(o => !blank(o.key)).map(o => [o.key, o]));
  const rcByKey = new Map(rcs.filter(o => !blank(o.key)).map(o => [o.key, o]));
  const called = new Set([...pages.flatMap(p => listOf(p.calls)), ...automations.map(a => a.call)]);
  for (const [k, tf] of tfByKey) {
    if (!called.has(k)) N('TaskFlow', tag(tf, 0), '没有任何页面或自动任务发起它', '在要用它的页面 calls 里加上，或加一个自动任务指向它；确实不要就删掉', `「${tf.name}」这件事目前没有页面或自动任务能发起，使用者用不到它。`);
  }
  const touched = new Set(taskflows.flatMap(tf => (isObj(tf.uses) ? [...listOf(tf.uses.reads), ...listOf(tf.uses.writes)] : [])));
  for (const [k, tb] of tableByKey) {
    if (!touched.has(k)) N('数据表', tag(tb, 0), '没有任何 TaskFlow 读或写这张表', '在读写它的 TaskFlow 的 reads 或 writes 里加上；确实用不到就删掉', `「${tb.name}」这份数据目前没有任何一件事会读或写它。`);
  }
  const usedRc = new Set(tables.filter(tb => isObj(tb.partition) && !isNone(tb.partition)).map(tb => tb.partition.by));
  for (const [k, rc] of rcByKey) {
    if (!usedRc.has(k)) N('资源控制点', tag(rc, 0), '定义了，但没有任何数据表按它划分', '在要按它划分的数据表 partition 里用上；确实不分就删掉它', `数据说要按「${rc.name}」分开，但目前没有哪一份数据真按它分。`);
  }
  const usedPerms = new Set(taskflows.map(tf => tf.permission));
  roles.forEach((r, i) => {
    for (const p of listOf(r.permissions)) {
      if (blank(p) || usedPerms.has(p)) continue;
      N('角色', tag(r, i), `权限点「${p}」没有任何 TaskFlow 使用`, '删掉这个权限点，或补上用它的 TaskFlow', `「${r.name}」有一项权限没有对应任何一件事，给了也用不上。`);
    }
  });
  for (const [, tf] of tfByKey) {
    if (!isObj(tf.uses)) continue;
    const scoped = isObj(tf.scope) && !isNone(tf.scope) ? new Set(Object.keys(tf.scope)) : new Set();
    const lacking = new Map();
    for (const tk of new Set([...listOf(tf.uses.reads), ...listOf(tf.uses.writes)])) {
      const tb = tableByKey.get(tk);
      if (!tb || !isObj(tb.partition) || isNone(tb.partition) || !rcKeys.has(tb.partition.by)) continue;
      if (!scoped.has(tb.partition.by)) lacking.set(tk, tb.partition.by);
    }
    for (const [tk, rk] of lacking) {
      N('TaskFlow', tag(tf, 0), `读写的数据表「${tk}」按资源控制点「${rk}」划分，自己的范围限制（scope）里却没有「${rk}」`, `在 scope 里加上「${rk}: 输入里的字段」；确实要跨${nameOf(rcByKey, rk)}处理的，在说明里写清原因`, `「${tf.name}」会用到按「${nameOf(rcByKey, rk)}」分开的「${nameOf(tableByKey, tk)}」，但它自己不按「${nameOf(rcByKey, rk)}」限制，可能会处理到不该看的${nameOf(rcByKey, rk)}的数据。`);
    }
  }
  automations.forEach((a, i) => {
    const tf = tfByKey.get(a.call);
    if (tf && tf.doneWhen === FIXED_DONE) N('自动任务', tag(a, i), `指向的 TaskFlow「${a.call}」完成标准是固定取值「${FIXED_DONE}」`, '自动任务跑完没人看，给它写一句能判断的完成标准，或确认只取数据就够', `自动任务「${a.name}」到点做的是「${tf.name}」，它只取数据、不留下结果，确认一下这是不是你要的。`);
  });

  return { ok: !must.length, must, notice };
}

const line = (x, i) => `${i + 1}. 【${x.entity}${x.item ? ' ' + x.item : ''}】${x.problem}。怎么改：${x.fix}。`;

/** check 结果的中文文字版。 */
export function formatCheck(result) {
  const out = [`检查结果：必须改 ${result.must.length} 条，请留意 ${result.notice.length} 条。`];
  if (result.must.length) out.push('', '必须改（改完重跑 check，直到这里没有）：', ...result.must.map(line));
  else out.push('没有必须改的。');
  if (result.notice.length) out.push('', '请留意（不拦，会写进确认单给开发者看）：', ...result.notice.map(line));
  return out.join('\n') + '\n';
}

function requireOk(decl) {
  const r = check(decl);
  if (!r.ok) throw new ValueError(`声明文件还有 ${r.must.length} 条必须改，先跑 check 改完：\n` + formatCheck(r));
  return r;
}

const join = xs => xs.join('、');
const tfIndex = decl => new Map(decl.taskflows.map(t => [t.key, t]));

/** 给开发者看的确认单（Markdown）：全部用业务话，不出现标识、英文字段名、权限点。 */
export function confirm(decl) {
  const r = requireOk(decl);
  const tfs = tfIndex(decl);
  const tables = new Map(decl.tables.map(t => [t.key, t]));
  const rcList = Array.isArray(decl.resourceControls) ? decl.resourceControls : [];
  const rcs = new Map(rcList.map(x => [x.key, x]));
  const autos = Array.isArray(decl.automations) ? decl.automations : [];
  const a = decl.app;
  const out = [`# 确认单：${a.name}`, '', '下面按你的业务把这个应用要做成的样子列出来。哪一条不对，直接说是哪一条、应该是什么。', ''];

  out.push('## 这个应用', '', `- 要解决的问题：${a.problem}`, `- 给谁用：${a.users}`, `- 做到什么算做好：${a.doneWell}`, `- 这次做哪些、不做哪些：${a.scope}`, `- 关键取舍：${a.tradeoffs}`, '');

  out.push('## 谁能用、各能做什么', '');
  for (const role of decl.roles) {
    const can = decl.taskflows.filter(t => role.permissions.includes(t.permission)).map(t => `「${t.name}」`);
    const cannot = decl.taskflows.filter(t => !role.permissions.includes(t.permission)).map(t => `「${t.name}」`);
    out.push(`### ${role.name}`, '', `- 能做：${can.length ? join(can) : '没有能做的事'}`, `- 不能做：${cannot.length ? join(cannot) : '没有，所有事都能做'}`, '');
  }

  out.push('## 数据怎么分', '');
  if (isNone(decl.resourceControls)) out.push(`- 不按范围分开管：${decl.resourceControls.none}`);
  else {
    out.push('数据按下面几样分开管，谁只能看、只能改自己那一份：', '');
    for (const rc of rcList) out.push(`- 按「${rc.name}」分：${rc.description}`);
  }
  out.push('', '每份数据怎么分：', '');
  for (const tb of decl.tables) {
    const how = isNone(tb.partition) ? `不分开，${tb.partition.none}` : `按「${rcs.get(tb.partition.by).name}」分开`;
    out.push(`- 「${tb.name}」（${tb.description}）：${how}`);
  }
  out.push('');

  out.push('## 有哪些页面、各能做什么', '');
  for (const p of decl.pages) out.push(`- 「${p.name}」：${p.summary}。在这一页能做：${join(p.calls.map(k => `「${tfs.get(k).name}」`))}`);
  out.push('');

  out.push('## 每件事做到什么算完成', '');
  for (const t of decl.taskflows) {
    const from = [
      ...decl.pages.filter(p => p.calls.includes(t.key)).map(p => `「${p.name}」页面`),
      ...autos.filter(x => x.call === t.key).map(x => `自动任务「${x.name}」`),
    ];
    const scope = isNone(t.scope) ? `不会：${t.scope.none}` : `会，只处理有权限的${join(Object.keys(t.scope).map(k => `「${rcs.get(k).name}」`))}里的数据`;
    out.push(
      `### ${t.name}`, '',
      `- 做什么：${t.summary}`,
      `- 做到什么算完成：${t.doneWhen}`,
      `- 从哪里发起：${from.length ? join(from) : '目前没有地方能发起'}`,
      `- 会用到的外部工具：${t.uses.tools.length ? join(t.uses.tools.map(x => `「${x}」`)) : '不用'}`,
      `- 交给模型判断的：${t.uses.agents.length ? join(t.uses.agents.map(x => `「${x}」`)) : '没有'}`,
      `- 会改哪些数据：${t.uses.writes.length ? join(t.uses.writes.map(k => `「${tables.get(k).name}」`)) : '不改数据'}`,
      `- 会不会按范围限制：${scope}`,
      '',
    );
  }

  out.push('## 自动任务', '');
  if (isNone(decl.automations)) out.push(`- 没有自动任务：${decl.automations.none}`);
  else for (const x of autos) out.push(`- 「${x.name}」：${x.schedule}，做「${tfs.get(x.call).name}」；没做完时通知${x.notifyOnIncomplete}`);
  out.push('');

  out.push('## 需要你留意的', '');
  if (r.notice.length) r.notice.forEach((n, i) => out.push(`${i + 1}. ${n.plain}`));
  else out.push('没有。');
  return out.join('\n') + '\n';
}

const CATEGORIES = ['功能', '工具', '权限', '自动任务'];
const expectDone = t => (t.doneWhen === FIXED_DONE ? `${FIXED_DONE}：拿到数据并显示出来，没有报错` : `完成标准：${t.doneWhen}`);

/** 走查项清单：{ items: [{ id, category, how, expect }], counts, total }。编号由标识组成，声明不变就不变。 */
export function walkthrough(decl) {
  requireOk(decl);
  const tfs = tfIndex(decl);
  const rcs = new Map((Array.isArray(decl.resourceControls) ? decl.resourceControls : []).map(x => [x.key, x]));
  const autos = Array.isArray(decl.automations) ? decl.automations : [];
  const items = [];
  const add = (id, category, how, expect) => items.push({ id, category, how, expect });

  for (const p of decl.pages) for (const k of p.calls) {
    const t = tfs.get(k);
    add(`功能-${p.key}-${k}`, '功能', `在「${p.name}」页面发起一次「${t.name}」`, expectDone(t));
  }
  for (const x of autos) {
    const t = tfs.get(x.call);
    add(`功能-${x.key}-${t.key}`, '功能', `由自动任务「${x.name}」发起一次「${t.name}」（手动触发）`, expectDone(t));
  }
  for (const t of decl.taskflows) {
    if (t.effect !== 'write' && !t.uses.tools.length) continue;
    add(`功能-${t.key}-做不成`, '功能', `发起「${t.name}」，造一次做不成（${t.uses.tools.length ? '让用到的工具返回失败、' : ''}输入缺必要信息或依赖的数据不存在）`, '结果是未完成并带原因，原因写明使用者下一步该做什么；已有数据没有被改坏');
  }
  for (const t of decl.taskflows) for (const tool of t.uses.tools) {
    add(`工具-${t.key}-${tool}`, '工具', `用真实参数调用一次「${tool}」（「${t.name}」用到的）`, '返回真实数据：不是空、不是模拟数据、不是报错');
  }
  for (const role of decl.roles) for (const t of decl.taskflows) {
    const can = role.permissions.includes(t.permission);
    add(`权限-${role.key}-${t.key}`, '权限', `以「${role.name}」的身份发起「${t.name}」`, can ? '能做' : '被拒绝');
  }
  for (const t of decl.taskflows) {
    if (isNone(t.scope)) continue;
    for (const [rk, field] of Object.entries(t.scope)) {
      const rc = rcs.get(rk);
      const who = decl.roles.find(r => r.permissions.includes(t.permission));
      add(`权限-${t.key}-${rk}-越界`, '权限', `用「${who.name}」身份、只被授权一个「${rc.name}」，发起「${t.name}」，输入里的 ${field} 填另一个「${rc.name}」`, `取不到：被拒绝或返回空，不出现另一个「${rc.name}」的数据，也不改它的数据`);
    }
  }
  for (const x of autos) {
    const t = tfs.get(x.call);
    add(`自动任务-${x.key}`, '自动任务', `让「${x.name}」到点（${x.schedule}）或手动触发跑一次`, `跑了一次「${t.name}」，结果对照${expectDone(t)}；没做完时通知到${x.notifyOnIncomplete}`);
  }
  const counts = Object.fromEntries(CATEGORIES.map(c => [c, items.filter(i => i.category === c).length]));
  return { items, counts, total: items.length };
}

const cell = s => String(s).replace(/\|/g, '\\|').replace(/\n/g, ' ');

/** 走查项清单的 Markdown。 */
export function walkthroughMarkdown(result) {
  const { items, counts, total } = result;
  const out = ['# 走查项', '', `按声明文件列出，共 ${total} 项。逐项去走，结论只用：通过 / 没通过 / 好不好你说了算 / 未测。`, ''];
  for (const c of CATEGORIES) {
    out.push(`## ${c}`, '');
    const rows = items.filter(i => i.category === c);
    if (!rows.length) { out.push('没有。', ''); continue; }
    out.push('| 编号 | 做法 | 预期 |', '|---|---|---|', ...rows.map(i => `| ${cell(i.id)} | ${cell(i.how)} | ${cell(i.expect)} |`), '');
  }
  out.push('## 项数', '', '| 类别 | 项数 |', '|---|---|', ...CATEGORIES.map(c => `| ${c} | ${counts[c]} |`), `| 合计 | ${total} |`);
  return out.join('\n') + '\n';
}

const USAGE = `用法：
  node declaration.mjs init <declaration.json>          生成空模板（文件已存在则拒绝）
  node declaration.mjs check <declaration.json> [--json]  检查；有「必须改」时退出码 1
  node declaration.mjs confirm <declaration.json>         输出给开发者看的确认单（Markdown）
  node declaration.mjs walkthrough <declaration.json> [--json]  输出走查项清单`;

export function main(argv) {
  const json = argv.includes('--json');
  const args = argv.filter(x => x !== '--json');
  const [cmd, path] = args;
  if (!['init', 'check', 'confirm', 'walkthrough'].includes(cmd) || !path || args.length !== 2) {
    process.stderr.write(USAGE + '\n');
    return 2;
  }
  try {
    if (cmd === 'init') {
      init(path);
      process.stdout.write(`已生成空模板：${path}。逐项填写后运行 check。\n`);
      return 0;
    }
    let decl;
    try {
      decl = load(path);
    } catch (e) {
      if (e.code === 'ENOENT') throw new ValueError(`找不到 ${path}；先用 init 生成模板`);
      throw e;
    }
    if (cmd === 'check') {
      const r = check(decl);
      process.stdout.write(json ? JSON.stringify(r, null, 2) + '\n' : formatCheck(r));
      return r.ok ? 0 : 1;
    }
    if (cmd === 'confirm') {
      process.stdout.write(confirm(decl));
      return 0;
    }
    const w = walkthrough(decl);
    process.stdout.write(json ? JSON.stringify(w, null, 2) + '\n' : walkthroughMarkdown(w));
    return 0;
  } catch (e) {
    if (e instanceof ValueError) {
      process.stderr.write(e.message + '\n');
      return 1;
    }
    throw e;
  }
}

const evalMode = process.execArgv.some(x => /^(-e|-p|--eval|--print)(=|$)/.test(x));
const invoked = import.meta.main ?? (!evalMode && !!process.argv[1] && existsSync(process.argv[1]) && realpathSync(process.argv[1]) === realpathSync(fileURLToPath(import.meta.url)));
if (invoked) process.exitCode = main(process.argv.slice(2));
