# 方案里的 Demo 怎么写

写方案、改方案里某个功能的页面示例时读。

方案里每个功能都有一个**完整页面**的可操作示例：开发者看了就知道这个页面长什么样、点了会怎样、得到什么。示例用写好的示例数据，不连真实服务，不真的保存。生成脚本把它套进应用外框（左侧导航、顶栏）并按第三栏宽度缩放，你只写页面主体。

## 文件长什么样

`docs/studio/proposal/demos/<编号>.html`：一段 HTML 片段，最后可以有一个 `<script>`。

- 片段写页面主体：标题（`<h3>`）、一句说明、操作区、结果区。不写 `<html>`、`<head>`、`<body>`，不写导航和顶栏。
- 编号：在要说明的区域外层元素上加 `data-pin="1"`、`data-pin="2"`……，从 1 连续编号，和 `notes` 的条数一样多、顺序一致。编号加在包住输入框的 `div` 上，不加在 `input`、`select` 本身。
- 脚本：只写一段，放在文件最后。脚本里能用的变量是 `root`（这个页面主体的元素），所有查找都用 `root.querySelector`，不用 `document`。点「重置示例」时页面恢复原样、脚本重新运行一次。
- 页面要和 ① 问到的界面答案、④ 要验的条目对得上：页面名、按钮名、字段名用开发者的词；PRD 节点里写了的空态、出错提示要在示例里能点出来。

## 可以用的类名

外壳已经带好样式，只用这些类名，加一点行内 `style` 调间距可以：

| 类名 | 用途 |
|---|---|
| `muted`、`hint` | 灰色说明文字 |
| `block` | 带边框的区块 |
| `fields` | 自动换行的字段网格（里面每个字段一个 `div`，`label` + 输入框） |
| `row` | 横排一行（按钮、筛选） |
| `primary` | 主按钮 |
| `pill`、`pill ok`、`pill warn` | 小标签 |
| `stat` | 数字卡（里面 `small` + `b`） |
| `lanes`、`lane` | 看板列 |
| `notice` | 黄色提示条 |
| `result` | 操作后的结果文字（空的时候不显示） |
| `empty` | 空态 |
| 表格 | 直接写 `table`，表头 `th` |

## 不能做的（生成脚本会拦）

| 不能 | 为什么 |
|---|---|
| `<form>` | Studio 会把整个表单删掉；用 `div` 包住，按钮绑 `click` |
| `fetch`、`XMLHttpRequest`、`WebSocket`、外部网址 | 文档在隔离环境里显示，不能联网；数据写死在页面里 |
| `localStorage`、`sessionStorage`、`cookie` | 示例不存东西 |
| `window.parent`、`window.open`、改 `location` | 不碰宿主窗口、不跳转 |
| `<iframe>`、`<link>`、`<style>`、外部 `<script src>` | 样式只用上面的类名 |

## 样例

```html
<h3>录入进货批次</h3>
<p class="muted">每次进货录一条，到期日由应用算。</p>
<div class="block" data-pin="1">
  <h4>批次信息</h4>
  <div class="fields">
    <div><label for="food">食材</label><select id="food"><option>五花肉（斤）</option><option>西兰花（斤）</option></select></div>
    <div><label for="qty">数量</label><input id="qty" type="number" value="10"></div>
    <div><label for="day">进货日</label><input id="day" type="date" value="2026-11-03"></div>
    <div><label for="keep">保质天数</label><input id="keep" type="number" value="5"></div>
  </div>
</div>
<div class="block" data-pin="2">
  <div class="row"><span>到期日：</span><b id="due">2026-11-08</b><span class="pill">应用自动算</span></div>
</div>
<div class="row" style="margin-top:14px" data-pin="3">
  <button class="primary" id="save">保存批次</button>
</div>
<p class="result" id="msg"></p>
<script>
const $ = s => root.querySelector(s);
function due() {
  const d = new Date($('#day').value);
  if (isNaN(d)) return '—';
  d.setDate(d.getDate() + Number($('#keep').value || 0));
  return d.toISOString().slice(0, 10);
}
['#day', '#keep'].forEach(s => $(s).addEventListener('input', () => { $('#due').textContent = due(); }));
$('#save').addEventListener('click', () => {
  if (Number($('#qty').value) < 0) { $('#msg').textContent = '数量不能为负，没有保存。'; return; }
  $('#msg').textContent = '✓ 已保存：' + $('#food').value + ' ' + $('#qty').value + '，到期日 ' + due() + '（示例，不会真的保存）';
});
</script>
```

## 写完怎么看

生成后截图，按 [检查清单.md](检查清单.md) 看：400px 宽时页面字能看清、编号不遮字；每个按钮点一下有反应；点编号能对上下面的说明；点「重置示例」回到原样。
