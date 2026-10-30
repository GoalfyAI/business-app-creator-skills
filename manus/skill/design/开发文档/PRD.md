# PRD 版式

① 交给开发者的 PRD 写成这一份 HTML。内容按 [../PRD.md](../PRD.md) 写，这里只规定每一节放在哪、用什么组件；通用写法见 [README.md](README.md)「怎么写一份」。

## 四个版块放什么

| 版块 | 放 PRD 的哪几节 | 组件 |
|---|---|---|
| 01 要做什么 | 你要的是什么（现在怎么做 → 做成后）、谁来用、要做的功能清单、这次不做的 | `.beforeafter`、`.roles`、`.scope`、一段「这次不做：」 |
| 02 怎么用 | 每一步谁来做（人 `human`、模型 `model`、脚本 `rule`，按使用顺序排）、做不成的时候 | `.legend`、`.journey`（`.step`、`.branches`）、`<details>` + `.facts` |
| 03 会得到什么 | 每个刚需一张功能卡：标题带核实结论；中间写在第一段；拿出来放 `.sample`；怎样算做成放 `.standard`；放进去、这样不行、会停下的情况、核实依据、验收预期放折叠的 `.facts`。非刚需放 `.otherfeatures`；界面放最后一个 `<details>` | `.feature`、`.badge`、`.sample`、`.standard`、`.otherfeatures`、`.rulesbody` |
| 04 确认与约定 | 要先对齐的事、花多少（预计、上限、停下确认的线）、费用与副作用和要从外面拿的数据、做不到的和替代、自动发生的事、上线范围、会记下来的东西、要你提供的、按默认补上的 | `.notice`、`.budget`、`.budgetbar`、`.rulegrid`、`<table>`、`.decision` |

- 核实结论的 `.badge` 只用四种：「已试过，能做」「能做」「要新做，没试过」（加 `pending`）、「做不到，见替代」（加 `pending`）。
- `.sample` 放真实拿到的东西；还没做出来的内容在 `.samplelabel` 第二个 `<span>` 写「预期」，不写成已有结果。
- 预算条：`--estimate` 写「预计最高 ÷ 上限」，`--stop` 写「停下确认的线 ÷ 上限」，都用百分数，四舍五入到一位小数。
- 选择题答过的写进对应位置；按推荐定下的在「按默认补上的」里列出。
- 「每一步谁来做」的人只写使用者：步骤主语写「使用者」，图例写「使用者」。

## 骨架

```html
<article class="sheet prd">
<div class="kicker">需求文档 / 【填：应用名】</div>
<h1>【填：一句话说清做成后能干什么，可用 <br> 分两行】</h1>
<p class="intro">【填：给谁用、串起哪几件事】<br>先确认做什么，再一起确定具体方案。</p>
<nav class="contents" aria-label="PRD 章节"><a href="#prd-goal">01 要做什么</a><a href="#prd-flow">02 怎么用</a><a href="#prd-results">03 会得到什么</a><a href="#prd-agreement">04 确认与约定</a></nav>

<section id="prd-goal"><div class="sectionhead"><em>01</em><h2>要做什么</h2></div>
<div class="beforeafter"><div><strong>现在</strong>【填：现在人工怎么做】</div><i aria-hidden="true">→</i><div class="after"><strong>做成后</strong>【填：做成后使用者怎么做】</div></div>
<div class="roles">【填：给谁用、多久用一次】<small>【填：在应用里做什么、看到什么】</small></div>
<div class="scope"><span>【填：功能名】</span><!-- 重复：每个要做的功能一个 span --></div>
<p>这次不做：【填：明确排除的东西，以及放到哪一期】</p>
</section>

<section id="prd-flow"><div class="sectionhead"><em>02</em><h2>怎么用</h2></div>
<div class="legend"><span><i class="human"></i>使用者</span><span><i class="model"></i>AI 判断或生成</span><span><i class="rule"></i>应用自动处理</span></div>
<div class="journey" role="group" aria-label="【填：一句话复述整条流程】">
<div class="step human">【填：步骤】<small>【填：补充说明，可省略这个 small】</small></div>
<span class="connector" aria-hidden="true">↓</span>
<!-- 重复：每一步一个 .step，类名按谁来做选 human / model / rule，步骤之间放上面那个 connector -->
<!-- 有分支时：<div class="branches"><div class="branch">【填：情况】<b>【填：这时怎么做】</b><span class="connector" aria-hidden="true">↓</span></div>（每种情况一个 .branch）</div> -->
<p class="flowcaption">【填：流程之外要知道的一句话，比如能不能接着上次做】</p>
</div>
<details><summary>如果中途遇到问题</summary><dl class="facts">
<div><dt>【填：情况】</dt><dd>【填：使用者会看到什么、应用怎么做】</dd></div><!-- 重复 -->
</dl></details>
</section>

<section id="prd-results"><div class="sectionhead"><em>03</em><h2>会得到什么</h2></div>
<p>先看结果是不是你要的，再展开检查具体规则。</p>
<!-- 重复：每个刚需一张 .feature -->
<div class="feature"><div class="featurehead"><h3>【填：序号. 功能名】</h3><span class="badge">【填：核实结论】</span></div>
<p>【填：中间：怎么开始、做了什么、怎么结束】</p>
<div class="sample"><div class="samplelabel"><span>【填：样例对象】</span><span>【填：真实结果 / 预期】</span></div>【填：拿出来的样例，组件见下面「样例里能用的写法」】</div>
<div class="standard">做好标准：【填：怎样算做成】</div>
<details><summary>查看规则与核实依据</summary><dl class="facts">
<div><dt>放进去</dt><dd>【填】</dd></div>
<div><dt>不能出现</dt><dd>【填：这样不行】</dd></div>
<div><dt>会停下的情况</dt><dd>【填，没有就删掉这一行】</dd></div>
<div><dt>核实依据</dt><dd>【填：真调拿回了什么、实测用时】</dd></div>
<div><dt>验收预期</dt><dd>【填：照着做、应该看到什么】</dd></div>
</dl></details></div>
<div class="otherfeatures"><p class="keypoint">还有【填：数量】项，让日常使用更完整</p>
<!-- 重复：每个非刚需一个 details -->
<details><summary><strong>【填：序号. 功能名】<span class="summarysub">【填：一句话】</span></strong><span class="badge pending">【填：核实结论】</span></summary><div class="rulesbody"><p>输入：【填】输出：【填】</p><p>做好标准：【填】</p></div></details>
</div>
<details><summary>界面方向：【填：一句话】</summary><p>【填：参考、第一眼看到什么、整体感觉、各页面放什么】</p></details>
</section>

<section id="prd-agreement"><div class="sectionhead"><em>04</em><h2>确认与约定</h2></div>
<div class="notice"><strong>【填：要先对齐的事】</strong>【填：为什么要对齐、你要定什么】</div><!-- 没有要先对齐的事就删掉这一块 -->
<div class="budget"><div><small>制作与测试预计 · 积分</small><strong>【填：预计范围】</strong></div><div><small>以后每次使用约 · 积分</small><strong>【填】</strong></div></div>
<div class="budgetbar" style="--estimate:【填】%;--stop:【填】%" role="img" aria-label="【填：预计最高、停下确认的线、上限】"></div>
<div class="budgetlabels"><span>预计最高【填】</span><span>【填】停下确认</span><span>上限【填】</span></div>
<p>【填：上线后每周大概用多少、花多少】</p>
<details><summary>费用依据与不能直接承诺的能力</summary><dl class="facts">
<div><dt>估算来源</dt><dd>【填】</dd></div>
<div><dt>外部调用</dt><dd>【填：从哪个平台拿什么、每次多少积分；会写入或发送什么，没有写「不会向外发送任何东西」】</dd></div>
<div><dt>替代范围</dt><dd>【填：做不到的和替代，没有就删掉这一行】</dd></div>
</dl></details>
<div class="rulegrid">
<div><strong>【填：约定标题】</strong>【填：一句话】</div><!-- 重复：数据归属、自动发生的事、上线范围、试用数据不带入正式版，各一格 -->
</div>
<details><summary>查看数据保存与编辑权限</summary><table><thead><tr><th>保存什么</th><th>谁写入</th><th>能否修改</th></tr></thead><tbody>
<tr><td>【填】</td><td>【填】</td><td>【填】</td></tr><!-- 重复：每张表一行 -->
</tbody></table></details>
<div class="decision"><span>○</span><div><strong>【填：要你提供的东西】</strong>【填：用在哪一步、缺了影响什么】</div></div><!-- 重复；没有就删掉 -->
<details><summary>按默认补上的选择</summary><p>【填：哪些按推荐定下；没有写「没有，都由你答过」】</p></details>
<div class="prdfoot"><strong>怎么确认这份需求</strong><p>在聊天里回「确认这一版」，或直接说哪一块、哪里要改。确认之后这一页不再改动，是否已确认以 Studio 显示的确认状态为准。</p></div>
<div class="source">第【填：版本号】版 · 【填：这一版改了什么；第 1 版写「首版」】</div>
</section>
</article>
```

## 样例里能用的写法

`.sample` 里按功能的结果选一种，不另造样式：

```html
<div class="store-row"><strong>◉ 【填：选中的一项】</strong><small>【填：补充】</small></div>
<div class="store-row"><strong>○ 【填：其他候选】</strong><small>【填】</small></div>

<div class="sample report">……<h4>【填：标题】</h4><div class="reportmeta">【填】</div>
<div class="reportstat"><div><b>【填：数字】</b><span>【填：含义】</span></div></div>
<p>【填：一两句结论】</p><div class="missing">数据缺口：【填】</div></div>

<div class="sampletitle">【填：生成的标题】</div><div class="sampletags">【填：标签】</div>
```

## 完整样例

「小红书商家分析报告」确认过的第 2 版（节选 02–04 的一部分：一条流程、一张功能卡、预算与费用依据；其余版块照骨架同样写法）。对照它的密度：每张功能卡一段话加一个样例，规则收在折叠里；预算条按预计最高 9,800、停下确认 12,000、上限 15,000 算出 `--estimate:65.3%;--stop:80%`。门店和数字只用来示意。

```html
<article class="sheet prd">
<div class="kicker">需求文档 / 小红书商家分析</div><h1>从一个店名，<br>到一份可用的商家报告。</h1><p class="intro">给做商家建联和探店视频的人用，串起查店、分析与内容创作。<br>先确认做什么，再一起确定具体方案。</p>
<section id="prd-flow"><div class="sectionhead"><em>02</em><h2>怎么用</h2></div><div class="legend"><span><i class="human"></i>使用者</span><span><i class="model"></i>AI 判断或生成</span><span><i class="rule"></i>应用自动处理</span></div>
<div class="journey" role="group" aria-label="填写店名、搜索核实、选择或补充门店、确认后生成报告，再按需创作内容"><div class="step human">填写店名<small>城市、官网可选填</small></div><span class="connector" aria-hidden="true">↓</span><div class="step rule">搜索门店和账号</div><span class="connector" aria-hidden="true">↓</span><div class="step model">核实是否为这家门店</div><span class="connector" aria-hidden="true">↓</span><div class="branches"><div class="branch">找到合适候选<b>使用者选一家门店</b><span class="connector" aria-hidden="true">↓</span></div><div class="branch">没找到 / 候选不对<b>使用者手动补资料</b><span class="connector" aria-hidden="true">↓</span></div></div><span class="connector" aria-hidden="true">↓</span><div class="step human">确认门店和官方账号<small>由使用者决定，不自动选第一条</small></div><p class="flowcaption">项目自动保存，下次回来可以接着做。</p></div></section>
<section id="prd-results"><div class="sectionhead"><em>03</em><h2>会得到什么</h2></div><p>先看结果是不是你要的，再展开检查具体规则。</p>
<div class="feature"><div class="featurehead"><h3>1. 找准门店与官方账号</h3><span class="badge">已试过，能做</span></div><p>输入店名和可选的城市，得到可以核对、修改和确认的候选门店。</p><div class="sample"><div class="samplelabel"><span>海底捞火锅 · 北京</span><span>真实结果</span></div><div class="store-row"><strong>◉ 王府井丹耀店</strong><small>东城区王府井大街 176 号</small></div><div class="store-row"><strong>○ 崇文门新世界百货店</strong><small>新世界百货 1 期 5 层</small></div></div><div class="standard">做好标准：候选是真实门店；选填留空也能提交；找错或找不到时能手填。</div><details><summary>查看规则与核实依据</summary><dl class="facts"><div><dt>放进去</dt><dd>店名必填；城市、官网选填。</dd></div><div><dt>不能出现</dt><dd>把帖子标题、景点或无关网站当成门店；替使用者默认确认。</dd></div><div><dt>会停下的情况</dt><dd>一个可靠候选都没有时，停在手填这一步等使用者补资料。</dd></div><div><dt>核实依据</dt><dd>试跑「海底捞火锅 · 北京」返回 3 家门店；「清水缘和服租 · 京都」核实后没有候选，转手填。</dd></div><div><dt>验收预期</dt><dd>7 家测试店都能进入选候选或手填。</dd></div></dl></details></div>
</section>
<section id="prd-agreement"><div class="sectionhead"><em>04</em><h2>确认与约定</h2></div><div class="notice"><strong>有一处需要先对齐</strong>报告目标是 25 分钟内，试跑最长用了 29.5 分钟。要保留完整内容，就需要你定：优化到 25 分钟，还是把目标放宽到 30 分钟。</div>
<div class="budget"><div><small>制作与测试预计 · 积分</small><strong>9,050–9,800</strong></div><div><small>以后每份报告约 · 积分</small><strong>750</strong></div></div><div class="budgetbar" style="--estimate:65.3%;--stop:80%" role="img" aria-label="预计最高 9,800 积分，12,000 积分停下确认，上限 15,000 积分"></div><div class="budgetlabels"><span>预计最高 9,800</span><span>12,000 停下确认</span><span>上限 15,000</span></div><p>按每周 6 份报告、12 篇内容算，上线后每周约 5,000 积分。</p>
<details><summary>费用依据与不能直接承诺的能力</summary><dl class="facts"><div><dt>估算来源</dt><dd>你在第 2 轮同意试跑一份后的实测：一份报告 730–782 积分、20–29.5 分钟；页面和存数据按功能数估算。</dd></div><div><dt>外部调用</dt><dd>小红书数据每次 10 积分，每份最多 35 次。不会向外发送任何东西。</dd></div></dl></details>
<div class="prdfoot"><strong>怎么确认这份需求</strong><p>在聊天里回「确认这一版」，或直接说哪一块、哪里要改。确认之后这一页不再改动，是否已确认以 Studio 显示的确认状态为准。</p></div>
<div class="source">第 2 版 · 改了报告时间目标和预算</div></section></article>
```
