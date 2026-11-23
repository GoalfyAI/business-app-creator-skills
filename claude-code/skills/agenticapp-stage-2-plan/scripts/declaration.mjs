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
// 还没问清的占位字样；「」里的原样算业务话（例如状态叫「待确认」）
const PLACEHOLDER = /待开发者回答|待定|待确认|待补|TODO|TBD|同上|暂无/i;
// 落差的固定写法：三段都在，用「；」隔开，顺序不限
export const GAP_FORMAT = '要的：…；做不到：…；替代：…';
/** 认落差：含「做不到：」才算；返回三段，缺的为空串。不是落差返回 null。 */
export function parseGap(text) {
  if (typeof text !== 'string' || !/做不到[：:]/.test(text)) return null;
  const part = k => (new RegExp(`(?:^|[；;])\\s*${k}[：:]([^；;]*)`).exec(text)?.[1] || '').trim();
  return { 要的: part('要的'), 做不到: part('做不到'), 替代: part('替代') };
}
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

  // 占位字样：值里写着「待开发者回答」这类话，等于还没问清，不能算填了
  const holes = new Map();
  const walk = (v, path, entity, item) => {
    if (typeof v === 'string') {
      if (PLACEHOLDER.test(v.replace(/「[^」]*」/g, ''))) {
        const k = `${entity}\u0000${item}`;
        if (!holes.has(k)) holes.set(k, { entity, item, fields: [] });
        const f = path.join('.');
        const head = path.find(x => typeof x === 'string' && LABEL[x]) || path[0];
        const label = `${LABEL[head] || head}（${f}）`;
        if (!holes.get(k).fields.includes(label)) holes.get(k).fields.push(label);
      }
    } else if (Array.isArray(v)) v.forEach(x => walk(x, path, entity, item));
    else if (isObj(v)) for (const [k, x] of Object.entries(v)) walk(x, [...path, k], entity, item);
  };
  if (isObj(decl.app)) walk(decl.app, [], '应用', '');
  for (const list of ['roles', 'resourceControls', 'tables', 'taskflows', 'automations', 'pages']) {
    const v = decl[list];
    if (Array.isArray(v)) v.forEach((o, i) => walk(o, [], ENTITY[list], tag(o, i)));
    else if (isObj(v)) walk(v, [list], ENTITY[list], '');
  }
  for (const h of holes.values()) M(h.entity, h.item, `这几项写的是占位字样（如「待开发者回答」「待定」）：${h.fields.join('、')}`, '这一项还没问清：先问开发者，答完再填');

  // 落差：开发者要的现有平台做不到，按「要的：…；做不到：…；替代：…」写在不适用的原因或使用对象里
  const gapSpots = [];
  if (isObj(decl.app)) gapSpots.push({ entity: '应用', item: '', field: 'users', text: decl.app.users, where: '谁来用' });
  if (isNone(decl.resourceControls)) gapSpots.push({ entity: '资源控制点', item: '', field: 'none', text: decl.resourceControls.none, where: '数据怎么分', vague: true });
  if (isNone(decl.automations)) gapSpots.push({ entity: '自动任务', item: '', field: 'none', text: decl.automations.none, where: '自动任务' });
  tables.forEach((o, i) => { if (isNone(o.partition)) gapSpots.push({ entity: '数据表', item: tag(o, i), field: 'partition.none', text: o.partition.none, where: `「${o.name}」怎么分`, vague: true }); });
  taskflows.forEach((o, i) => { if (isNone(o.scope)) gapSpots.push({ entity: 'TaskFlow', item: tag(o, i), field: 'scope.none', text: o.scope.none, where: `「${o.name}」限不限范围`, vague: true }); });
  for (const s of gapSpots) {
    if (blank(s.text)) continue;
    const gap = parseGap(s.text);
    if (gap === null) {
      if (s.vague && /平台/.test(s.text) && /每人|每个人|每个使用者|一份/.test(s.text)) N(s.entity, s.item, `${s.field} 只写了平台怎么做，看不出开发者原本要不要分开管`, `开发者要的就是不分，写清业务上的原因；要分而做不到，改写成「${GAP_FORMAT}」`, `${s.where}这里只写了平台现在怎么做，没写你原本要的是什么；如果你原本要分开管，告诉我，我把做不到的地方和替代做法写清楚。`);
      continue;
    }
    const miss = ['要的', '做不到', '替代'].filter(k => blank(gap[k]));
    if (miss.length) { M(s.entity, s.item, `${s.field} 写了落差，但缺：${miss.join('、')}`, `三段写全：「${GAP_FORMAT}」`); continue; }
    N(s.entity, s.item, `${s.field} 写了一处做不到的落差`, '确认单会列出它；交接消息里点出来，请开发者定接受替代还是改需求', `${s.where}：你要的是${gap['要的']}；现在做不到的是${gap['做不到']}；替代做法是${gap['替代']}。请定：接受这个替代，还是改需求。`);
  }

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
      `- 做到什么算完成：${t.doneWhen === FIXED_DONE ? '查到并显示出来就算完成' : t.doneWhen}`,
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
  const tables = new Map(decl.tables.map(x => [x.key, x]));
  const autos = Array.isArray(decl.automations) ? decl.automations : [];
  const items = [];
  // refs 记这一项涉及哪些对象（标识），impact 与 diff 据此挑出要重走的项
  const add = (id, category, how, expect, refs) => items.push({ id, category, how, expect, refs });
  // 从页面发起的功能项用第一个能做这件事的角色去做；这一项走通就证明了这个角色能做，权限里不再单列
  const firstRole = t => decl.roles.find(r => r.permissions.includes(t.permission));
  const proven = new Set();

  for (const p of decl.pages) for (const k of p.calls) {
    const t = tfs.get(k), who = firstRole(t);
    proven.add(`${who.key}:${k}`);
    add(`功能-${p.key}-${k}`, '功能', `以「${who.name}」的身份，在「${p.name}」页面发起一次「${t.name}」`, expectDone(t), { page: p.key, taskflow: k, role: who.key });
  }
  const tableNames = ks => ks.map(k => `「${tables.get(k).name}」`).join('、');
  for (const t of decl.taskflows) {
    if (t.effect !== 'write' && !t.uses.tools.length) continue;
    const ways = [
      ...t.uses.tools.map(x => `让「${x}」返回失败`),
      ...t.uses.agents.map(x => `让「${x}」给不出结果`),
      ...(t.uses.reads.length ? [`${tableNames(t.uses.reads)}里没有要用的那一行`] : []),
      ...(t.uses.writes.length ? [`写${tableNames(t.uses.writes)}时被拒`] : []),
      '输入缺必要信息',
    ];
    add(`功能-${t.key}-做不成`, '功能', `发起「${t.name}」，造一次做不成，从这几种里选能造出来的：${ways.join('；')}`, '结果是未完成并带原因，原因写明使用者下一步该做什么；已有数据没有被改坏', { taskflow: t.key });
  }
  for (const t of decl.taskflows) for (const tool of t.uses.tools) {
    add(`工具-${t.key}-${tool}`, '工具', `用真实参数调用一次「${tool}」（「${t.name}」用到的）`, '返回真实数据：不是空、不是模拟数据、不是报错', { taskflow: t.key, tool });
  }
  for (const role of decl.roles) for (const t of decl.taskflows) {
    const can = role.permissions.includes(t.permission);
    if (can && proven.has(`${role.key}:${t.key}`)) continue;
    add(`权限-${role.key}-${t.key}`, '权限', `以「${role.name}」的身份发起「${t.name}」`, can ? '能做' : '被拒绝', { role: role.key, taskflow: t.key });
  }
  for (const t of decl.taskflows) {
    if (isNone(t.scope)) continue;
    for (const [rk, field] of Object.entries(t.scope)) {
      const rc = rcs.get(rk);
      const who = firstRole(t);
      add(`权限-${t.key}-${rk}-越界`, '权限', `用「${who.name}」身份、只被授权一个「${rc.name}」，发起「${t.name}」，输入里的 ${field} 填另一个「${rc.name}」`, `取不到：被拒绝或返回空，不出现另一个「${rc.name}」的数据，也不改它的数据`, { taskflow: t.key, resourceControl: rk, role: who.key });
    }
  }
  for (const x of autos) {
    const t = tfs.get(x.call);
    add(`自动任务-${x.key}-立即`, '自动任务', `立即运行一次「${x.name}」（手动触发），让它做一次「${t.name}」`, `结果对照${expectDone(t)}`, { automation: x.key, taskflow: t.key });
    add(`自动任务-${x.key}-到点`, '自动任务', `等「${x.name}」到点（${x.schedule}）自动运行一次，并让这一次做不成`, `到点自己开始了，没有人手动触发；没做完时通知到了${x.notifyOnIncomplete}`, { automation: x.key, taskflow: t.key });
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

// ---------------------------------------------------------------- impact 与 diff

const TYPES = ['角色', '权限点', '资源控制点', '数据表', '工具', 'Agent', 'TaskFlow', '页面', '自动任务'];
const AFFECTED_TYPES = ['数据表', 'TaskFlow', '页面', '自动任务', '角色'];
const uniq = xs => [...new Set(xs)];
const nid = (type, key) => `${type}:${key}`;

/** 把声明整理成对象表与依赖关系。权限点、工具、Agent 没有单独的项，按出现过的字符串算一个对象。 */
function model(decl) {
  const arr = v => (Array.isArray(v) ? v : []);
  const roles = decl.roles, tfs = decl.taskflows, tables = decl.tables, pages = decl.pages;
  const rcs = arr(decl.resourceControls), autos = arr(decl.automations);
  const objs = new Map();
  const put = (type, key, name, extra = {}) => { if (!objs.has(nid(type, key))) objs.set(nid(type, key), { type, key, name, ...extra }); };
  roles.forEach(o => put('角色', o.key, o.name, { about: `能做的权限点：${o.permissions.join('、')}` }));
  rcs.forEach(o => put('资源控制点', o.key, o.name, { about: o.description }));
  tables.forEach(o => put('数据表', o.key, o.name, { about: o.description }));
  tfs.forEach(o => put('TaskFlow', o.key, o.name, { about: o.summary }));
  pages.forEach(o => put('页面', o.key, o.name, { about: o.summary }));
  autos.forEach(o => put('自动任务', o.key, o.name, { about: `${o.schedule}，指向 ${o.call}` }));
  uniq([...roles.flatMap(r => r.permissions), ...tfs.map(t => t.permission)]).forEach(p => put('权限点', p, p));
  uniq(tfs.flatMap(t => t.uses.tools)).forEach(x => put('工具', x, x));
  uniq(tfs.flatMap(t => t.uses.agents)).forEach(x => put('Agent', x, x));

  const scoped = t => (isNone(t.scope) ? [] : Object.keys(t.scope));
  const canDo = (r, t) => r.permissions.includes(t.permission);
  const tfIds = list => list.map(t => nid('TaskFlow', t.key));
  // 谁依赖它：改了它，这些跟着受影响
  const dependents = id => {
    const { type, key } = objs.get(id);
    switch (type) {
      case '数据表': return tfIds(tfs.filter(t => t.uses.reads.includes(key) || t.uses.writes.includes(key)));
      case '工具': return tfIds(tfs.filter(t => t.uses.tools.includes(key)));
      case 'Agent': return tfIds(tfs.filter(t => t.uses.agents.includes(key)));
      case '资源控制点': return [...tables.filter(b => !isNone(b.partition) && b.partition.by === key).map(b => nid('数据表', b.key)), ...tfIds(tfs.filter(t => scoped(t).includes(key)))];
      case '权限点': return [...tfIds(tfs.filter(t => t.permission === key)), ...roles.filter(r => r.permissions.includes(key)).map(r => nid('角色', r.key))];
      case 'TaskFlow': {
        const t = tfs.find(x => x.key === key);
        return [...pages.filter(p => p.calls.includes(key)).map(p => nid('页面', p.key)), ...autos.filter(a => a.call === key).map(a => nid('自动任务', a.key)), ...roles.filter(r => canDo(r, t)).map(r => nid('角色', r.key))];
      }
      case '页面': {
        const p = pages.find(x => x.key === key);
        return roles.filter(r => tfs.some(t => p.calls.includes(t.key) && canDo(r, t))).map(r => nid('角色', r.key));
      }
      default: return [];
    }
  };
  // 它用到的：和 dependents 合起来就是直接连着的
  const uses = id => {
    const { type, key } = objs.get(id);
    switch (type) {
      case '数据表': { const b = tables.find(x => x.key === key); return isNone(b.partition) ? [] : [nid('资源控制点', b.partition.by)]; }
      case 'TaskFlow': {
        const t = tfs.find(x => x.key === key);
        return [...uniq([...t.uses.reads, ...t.uses.writes]).map(k => nid('数据表', k)), ...t.uses.tools.map(k => nid('工具', k)), ...t.uses.agents.map(k => nid('Agent', k)), nid('权限点', t.permission), ...scoped(t).map(k => nid('资源控制点', k))];
      }
      case '页面': return pages.find(x => x.key === key).calls.map(k => nid('TaskFlow', k));
      case '自动任务': return [nid('TaskFlow', autos.find(x => x.key === key).call)];
      case '角色': { const r = roles.find(x => x.key === key); return [...r.permissions.map(p => nid('权限点', p)), ...tfIds(tfs.filter(t => canDo(r, t)))]; }
      default: return [];
    }
  };
  const relation = (a, b) => {
    const [x, y] = [objs.get(a), objs.get(b)];
    const pair = x.type === 'TaskFlow' && y.type === '数据表' ? [x, y] : y.type === 'TaskFlow' && x.type === '数据表' ? [y, x] : null;
    if (!pair) return '';
    const t = tfs.find(o => o.key === pair[0].key);
    const r = t.uses.reads.includes(pair[1].key), w = t.uses.writes.includes(pair[1].key);
    return r && w ? '读、写' : w ? '写' : '读';
  };
  return { objs, dependents, uses, relation };
}

/** 按标识或中文名称找对象；可写成「类:对象」限定类别。返回 { match } 或 { candidates }。 */
export function resolve(decl, target) {
  const { objs } = model(decl);
  const all = [...objs.values()];
  let type = null, text = String(target).trim();
  const m = /^([^:：]+)[:：](.+)$/.exec(text);
  if (m && TYPES.includes(m[1])) [type, text] = [m[1], m[2]];
  const pool = type ? all.filter(o => o.type === type) : all;
  const hits = pool.filter(o => o.key === text || o.name === text);
  if (hits.length === 1) return { match: hits[0] };
  const candidates = hits.length ? hits : pool.filter(o => o.key.includes(text) || o.name.includes(text));
  return { duplicate: hits.length > 1, candidates: candidates.map(o => ({ type: o.type, key: o.key, name: o.name })) };
}

const labelOf = o => (o.key === o.name ? `「${o.name}」` : `「${o.name}」（${o.key}）`);
const plainOf = o => `「${o.name}」`;

/** 沿依赖向外走一遍：返回直接连着的、受影响的（按类）以及受影响对象的 id 集合。 */
// 页面只在它本身是改动对象时才往外走到角色：页面因为其中一件事变了而受影响时，能不能用这一页的角色不变。
function spread(mdl, roots) {
  const seen = new Set(roots), queue = [...roots];
  const next = id => (mdl.objs.get(id).type === '页面' && !roots.includes(id) ? [] : mdl.dependents(id));
  while (queue.length) for (const d of next(queue.shift())) if (!seen.has(d)) { seen.add(d); queue.push(d); }
  return seen;
}

// 要重走的项：涉及受影响 TaskFlow 的全部项；页面、自动任务、角色只在它本身就是改动对象时，才把涉及它的项都算上。
// 只因为页面上的另一件事变了，这一页其余的事不用重走。
function rewalkOf(decl, affected, roots) {
  const tf = k => k !== undefined && affected.has(nid('TaskFlow', k));
  const root = (type, k) => k !== undefined && roots.has(nid(type, k));
  return walkthrough(decl).items.filter(i => tf(i.refs.taskflow) || root('页面', i.refs.page) || root('自动任务', i.refs.automation) || root('角色', i.refs.role)).map(i => i.id);
}

const groupBy = (mdl, ids, types) => Object.fromEntries(types.map(t => [t, ids.filter(id => mdl.objs.get(id).type === t)]).filter(([, v]) => v.length));

/** 改某个对象之前看它连着什么、谁依赖它。target 是标识、中文名称或「类:对象」。 */
export function impact(decl, target) {
  requireOk(decl);
  const r = resolve(decl, target);
  if (!r.match) {
    const list = r.candidates.map(c => `${c.type}:${c.key}（${c.name}）`).join('、');
    if (!r.candidates.length) throw new ValueError(`声明里找不到「${target}」，写标识或中文名称`);
    throw new ValueError(`${r.duplicate ? `「${target}」有重名` : `声明里没有正好叫「${target}」的，相近的有`}：${list}。用「类:标识」写明是哪一个，例如 ${r.candidates[0].type}:${r.candidates[0].key}`);
  }
  const mdl = model(decl), o = r.match, id = nid(o.type, o.key);
  const direct = uniq([...mdl.uses(id), ...mdl.dependents(id)]).filter(x => x !== id);
  const affected = spread(mdl, [id]);
  const rest = [...affected].filter(x => x !== id);
  const show = ids => ids.map(x => { const ob = mdl.objs.get(x), rel = mdl.relation(id, x); return { type: ob.type, key: ob.key, name: ob.name, relation: rel }; });
  const byType = (ids, types) => Object.fromEntries(Object.entries(groupBy(mdl, ids, types)).map(([k, v]) => [k, show(v)]));
  const aff = byType(rest, AFFECTED_TYPES);
  const plainParts = AFFECTED_TYPES.filter(t => aff[t]).map(t => `${aff[t].length} ${{ 数据表: '份数据', TaskFlow: '件事', 页面: '个页面', 自动任务: '个自动任务', 角色: '个角色' }[t]}（${aff[t].map(x => plainOf(x)).join('、')}）`);
  return {
    target: { type: o.type, key: o.key, name: o.name, about: o.about || '' },
    direct: byType(direct, TYPES),
    affected: aff,
    rewalk: rewalkOf(decl, affected, new Set([id])),
    plain: plainParts.length ? `改${plainOf(o)}会波及 ${plainParts.join('、')}。` : `改${plainOf(o)}不会波及别的页面、自动任务和角色。`,
  };
}

const items = list => list.map(x => (x.relation ? `「${x.name}」（${x.key}，${x.relation}）` : labelOf(x))).join('、');

/** impact 结果的 Markdown。 */
export function impactMarkdown(r) {
  const t = r.target;
  const out = [`# 影响范围：${t.type}${labelOf(t)}`, ''];
  if (t.about) out.push(`- 是什么：${t.about}`, '');
  out.push('## 直接连着', '');
  const d = Object.entries(r.direct);
  out.push(...(d.length ? d.map(([k, v]) => `- ${k}：${items(v)}`) : ['没有。']), '');
  out.push('## 沿依赖受影响', '');
  const a = Object.entries(r.affected);
  out.push(...(a.length ? a.map(([k, v]) => `- ${k}：${items(v)}`) : ['没有。']), '');
  out.push('给开发者的一句话：' + r.plain, '');
  out.push(`## 改完要重走的走查项（${r.rewalk.length} 项）`, '', ...(r.rewalk.length ? r.rewalk.map(x => `- ${x}`) : ['没有。']));
  return out.join('\n') + '\n';
}

// diff：按标识比对两份声明
const ENTITY_FIELDS = { roles: FIELDS.roles, resourceControls: FIELDS.resourceControls, tables: FIELDS.tables, taskflows: FIELDS.taskflows, automations: FIELDS.automations, pages: FIELDS.pages };
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const fmt = v => (typeof v === 'string' ? v : Array.isArray(v) && v.every(x => typeof x === 'string') ? (v.length ? v.join('、') : '空') : JSON.stringify(v));

/** 一处改动给开发者看的话：不出现标识和英文字段名。 */
function plainChange(kind, field, c, ctx) {
  const { oldD, newD } = ctx;
  const nm = (d, list, k) => (Array.isArray(d[list]) ? d[list].find(x => x.key === k)?.name : undefined) ?? '';
  const names = (d, list, ks) => ks.map(k => `「${nm(d, list, k)}」`).join('、');
  const addDel = (o, n, show) => {
    const add = n.filter(x => !o.includes(x)), del = o.filter(x => !n.includes(x));
    return [add.length ? `加上${show(add, newD)}` : '', del.length ? `去掉${show(del, oldD)}` : ''].filter(Boolean).join('，');
  };
  const quote = xs => xs.map(x => `「${x}」`).join('、');
  const scopeText = (d, s) => (isNone(s) ? `不按范围限制（${s.none}）` : `按${Object.keys(s).map(k => `「${nm(d, 'resourceControls', k)}」`).join('、')}限制`);
  const partText = (d, p) => (isNone(p) ? `不分开（${p.none}）` : `按「${nm(d, 'resourceControls', p.by)}」分开`);
  const rolesFor = (d, perm) => d.roles.filter(r => r.permissions.includes(perm)).map(r => `「${r.name}」`).join('、') || '没有角色';
  const tfsFor = (d, perms) => d.taskflows.filter(t => perms.includes(t.permission)).map(t => `「${t.name}」`);
  switch (field) {
    case 'name': return `名称从「${c.from}」改成「${c.to}」`;
    case 'summary': case 'description': return `说明改成：${c.to}`;
    case 'doneWhen': return `完成标准从「${c.from}」改成「${c.to}」`;
    case 'effect': return c.to === 'write' ? '从只读改成会改数据' : '从会改数据改成只读';
    case 'permission': return `能做它的角色从 ${rolesFor(oldD, c.from)} 变成 ${rolesFor(newD, c.to)}`;
    case 'scope': return `范围限制从${scopeText(oldD, c.from)}改成${scopeText(newD, c.to)}`;
    case 'input': return '需要提供的信息有变化';
    case 'output': return '产出有变化';
    case 'uses.tools': return `用到的外部工具${addDel(c.from, c.to, xs => quote(xs))}`;
    case 'uses.agents': return `交给模型判断的${addDel(c.from, c.to, xs => quote(xs))}`;
    case 'uses.reads': return `读的数据${addDel(c.from, c.to, (xs, d) => names(d, 'tables', xs))}`;
    case 'uses.writes': return `会改的数据${addDel(c.from, c.to, (xs, d) => names(d, 'tables', xs))}`;
    case 'partition': return `从${partText(oldD, c.from)}改成${partText(newD, c.to)}`;
    case 'permissions': {
      const add = c.to.filter(x => !c.from.includes(x)), del = c.from.filter(x => !c.to.includes(x));
      const a = tfsFor(newD, add), b = tfsFor(oldD, del);
      return [a.length ? `现在能做${a.join('、')}` : add.length ? '多了一项还没有对应事情的权限' : '', b.length ? `不再能做${b.join('、')}` : del.length ? '少了一项没有对应事情的权限' : ''].filter(Boolean).join('，');
    }
    case 'schedule': return `触发时间从「${c.from}」改成「${c.to}」`;
    case 'call': return `改成做「${nm(newD, 'taskflows', c.to)}」（原来做「${nm(oldD, 'taskflows', c.from)}」）`;
    case 'notifyOnIncomplete': return `没做完时通知的人从「${c.from}」改成「${c.to}」`;
    case 'calls': return `页面上能做的事${addDel(c.from, c.to, (xs, d) => names(d, 'taskflows', xs))}`;
    default: return `${kind}有变化`;
  }
}

const NOUN = { roles: '角色', resourceControls: '数据分开管的方式', tables: '数据', taskflows: '事', automations: '自动任务', pages: '页面' };
const APP_PLAIN = { name: '应用名称', problem: '要解决的问题', users: '给谁用', doneWell: '做到什么算做好', scope: '这次做哪些、不做哪些', tradeoffs: '关键取舍' };

/** 比对改前、改后两份声明：改了什么、影响到谁、走查项怎么走。两份都要先过 check。 */
export function diff(oldD, newD) {
  for (const [d, which] of [[oldD, '改前的一份'], [newD, '改后的一份']]) {
    const r = check(d);
    if (!r.ok) throw new ValueError(`${which}声明还有 ${r.must.length} 条必须改，先跑 check 改完：\n` + formatCheck(r));
  }
  const changes = [], plain = [];
  for (const f of FIELDS.app) if (!same(oldD.app[f], newD.app[f])) {
    changes.push({ entity: '应用', kind: '修改', key: '', name: newD.app.name, fields: [{ field: f, label: LABEL[f], from: oldD.app[f], to: newD.app[f] }] });
    plain.push(`${APP_PLAIN[f]}改成：${newD.app[f]}`);
  }
  const roots = { old: [], new: [] };
  const typeOf = { roles: '角色', resourceControls: '资源控制点', tables: '数据表', taskflows: 'TaskFlow', automations: '自动任务', pages: '页面' };
  for (const [list, fields] of Object.entries(ENTITY_FIELDS)) {
    const arr = d => (Array.isArray(d[list]) ? d[list] : []);
    const o = new Map(arr(oldD).map(x => [x.key, x])), n = new Map(arr(newD).map(x => [x.key, x]));
    const entity = ENTITY[list], type = typeOf[list];
    for (const [k, x] of n) if (!o.has(k)) {
      changes.push({ entity, kind: '新增', key: k, name: x.name, fields: [] });
      plain.push(`新增${NOUN[list] === '事' ? '一件事' : NOUN[list]}「${x.name}」${x.summary ? `：${x.summary}` : x.description ? `：${x.description}` : ''}`);
      roots.new.push(nid(type, k));
    }
    for (const [k, x] of o) if (!n.has(k)) {
      changes.push({ entity, kind: '删除', key: k, name: x.name, fields: [] });
      plain.push(`去掉${NOUN[list] === '事' ? '一件事' : NOUN[list]}「${x.name}」`);
      roots.old.push(nid(type, k));
    }
    for (const [k, x] of n) {
      const y = o.get(k);
      if (!y) continue;
      const fs = [];
      for (const f of fields) {
        if (f === 'key') continue;
        if (f === 'uses') { for (const u of FIELDS.uses) if (!same(y.uses[u], x.uses[u])) fs.push({ field: `uses.${u}`, label: LABEL[u], from: y.uses[u], to: x.uses[u] }); continue; }
        if (!same(y[f], x[f])) fs.push({ field: f, label: LABEL[f], from: y[f], to: x[f] });
      }
      if (!fs.length) continue;
      changes.push({ entity, kind: '修改', key: k, name: x.name, fields: fs });
      const said = fs.map(c => plainChange('这一项', c.field, c, { oldD, newD })).filter(Boolean);
      // 只改了划分列这类实现细节，开发者那边不用写
      if (said.some(s => s !== '这一项有变化')) plain.push(`「${x.name}」${said.filter(s => s !== '这一项有变化').join('；')}`);
      // 角色的权限点增减会让对应的权限项预期变化，在「预期变了」里列出，不另把那几件事整件重走
      if (list !== 'roles') roots.new.push(nid(type, k));
      else roots.roleOnly = [...(roots.roleOnly || []), nid(type, k)];
    }
  }
  for (const [list, none] of [['resourceControls', '不按范围分开管'], ['automations', '没有自动任务']]) {
    if (isNone(oldD[list]) !== isNone(newD[list])) changes.push({ entity: ENTITY[list], kind: '修改', key: '', name: '', fields: [{ field: list, label: ENTITY[list], from: oldD[list], to: newD[list] }] });
    if (isNone(newD[list]) && !isNone(oldD[list])) plain.push(`改成${none}：${newD[list].none}`);
  }

  // 影响到谁：新的一份里沿依赖往外走；删掉的对象在旧的一份里走
  const mNew = model(newD), mOld = model(oldD);
  const affNew = spread(mNew, roots.new.filter(id => mNew.objs.has(id)));
  const affOld = spread(mOld, roots.old.filter(id => mOld.objs.has(id)));
  const reach = {};
  for (const [m, set] of [[mNew, new Set([...affNew, ...(roots.roleOnly || [])])], [mOld, affOld]]) for (const id of set) {
    const ob = m.objs.get(id);
    if (!AFFECTED_TYPES.includes(ob.type)) continue;
    (reach[ob.type] ||= new Map()).set(ob.key, { type: ob.type, key: ob.key, name: ob.name });
  }
  const affected = Object.fromEntries(AFFECTED_TYPES.filter(t => reach[t]).map(t => [t, [...reach[t].values()]]));
  // 旧的一份里受影响、新的一份里还在的，也算进新的一份要重走的范围
  const inNew = new Set([...affNew, ...[...affOld].filter(id => mNew.objs.has(id))]);

  const wOld = walkthrough(oldD), wNew = walkthrough(newD);
  const oldMap = new Map(wOld.items.map(i => [i.id, i])), newMap = new Map(wNew.items.map(i => [i.id, i]));
  const added = wNew.items.filter(i => !oldMap.has(i.id)).map(i => i.id);
  const removed = wOld.items.filter(i => !newMap.has(i.id)).map(i => i.id);
  const changed = wNew.items.filter(i => oldMap.has(i.id) && (oldMap.get(i.id).expect !== i.expect || oldMap.get(i.id).how !== i.how)).map(i => i.id);
  const fixed = new Set([...added, ...changed]);
  const rewalk = rewalkOf(newD, inNew, new Set(roots.new)).filter(id => !fixed.has(id));
  const untouched = wNew.items.filter(i => !fixed.has(i.id) && !rewalk.includes(i.id)).map(i => i.id);
  return {
    changes,
    plain,
    affected,
    walkthrough: { added, removed, changed, rewalk, untouched, total: wNew.total },
  };
}

/** diff 结果的 Markdown。 */
export function diffMarkdown(r) {
  const out = ['# 声明改动', '', '## 改了什么', ''];
  if (!r.changes.length) out.push('两份一样，没有改动。');
  for (const c of r.changes) {
    const who = c.key ? `「${c.name}」（${c.key}）` : c.name ? `「${c.name}」` : '';
    const ent = (/^[A-Za-z]/.test(c.entity) ? ' ' : '') + c.entity;
    if (c.kind !== '修改') { out.push(`- ${c.kind}${ent}${who}`); continue; }
    out.push(`- 修改${ent}${who}：` + c.fields.map(f => `${f.label}（${f.field}）从「${fmt(f.from)}」改成「${fmt(f.to)}」`).join('；'));
  }
  out.push('', '可直接放进更新说明的文字：', '', ...(r.plain.length ? r.plain.map(s => `- ${s}。`) : ['- 这次没有改动应用的结构。']), '');
  out.push('## 影响到谁', '');
  const a = Object.entries(r.affected);
  out.push(...(a.length ? a.map(([k, v]) => `- ${k}：${v.map(labelOf).join('、')}`) : ['没有。']), '');
  const w = r.walkthrough;
  const list = (title, ids) => [`- ${title}（${ids.length} 项）：${ids.length ? ids.join('、') : '没有'}`];
  out.push('## 走查项', '', ...list('新增的', w.added), ...list('消失的', w.removed), ...list('预期或做法变了的', w.changed), ...list('因受影响要重走的', w.rewalk));
  out.push(`- 不受影响，可不重走：${w.untouched.length} 项`, '', `改后共 ${w.total} 项，这次要走 ${w.added.length + w.changed.length + w.rewalk.length} 项。`);
  return out.join('\n') + '\n';
}

const USAGE = `用法：
  node declaration.mjs init <declaration.json>          生成空模板（文件已存在则拒绝）
  node declaration.mjs check <declaration.json> [--json]  检查；有「必须改」时退出码 1
  node declaration.mjs confirm <declaration.json>         输出给开发者看的确认单（Markdown）
  node declaration.mjs walkthrough <declaration.json> [--json]  输出走查项清单
  node declaration.mjs impact <declaration.json> <对象> [--json]  改之前看这个对象连着什么、谁依赖它；对象写标识、中文名称或「类:标识」
  node declaration.mjs diff <改前.json> <改后.json> [--json]   改之后比对两份：改了什么、影响到谁、走查项怎么走`;

export function main(argv) {
  const json = argv.includes('--json');
  const args = argv.filter(x => x !== '--json');
  const [cmd, path, second] = args;
  const want = ['impact', 'diff'].includes(cmd) ? 3 : 2;
  if (!['init', 'check', 'confirm', 'walkthrough', 'impact', 'diff'].includes(cmd) || args.length !== want) {
    process.stderr.write(USAGE + '\n');
    return 2;
  }
  try {
    if (cmd === 'init') {
      init(path);
      process.stdout.write(`已生成空模板：${path}。逐项填写后运行 check。\n`);
      return 0;
    }
    const read = p => {
      try {
        return load(p);
      } catch (e) {
        if (e.code === 'ENOENT') throw new ValueError(`找不到 ${p}；先用 init 生成模板`);
        throw e;
      }
    };
    if (cmd === 'diff') {
      const [a, b] = [read(path), read(second)];
      for (const [d, p] of [[a, path], [b, second]]) {
        const r = check(d);
        if (!r.ok) throw new ValueError(`${p} 还有 ${r.must.length} 条必须改，先跑 check 改完：\n` + formatCheck(r));
      }
      const r = diff(a, b);
      process.stdout.write(json ? JSON.stringify(r, null, 2) + '\n' : diffMarkdown(r));
      return 0;
    }
    const decl = read(path);
    if (cmd === 'impact') {
      const r = impact(decl, second);
      process.stdout.write(json ? JSON.stringify(r, null, 2) + '\n' : impactMarkdown(r));
      return 0;
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
