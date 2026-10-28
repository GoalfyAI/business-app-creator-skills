# Studio 表单与卡片

## 适用场景

当前宿主提供 Studio 制作工具（工具列表里有 `studio_*`），要在回复里发表单（写文档前按轮问的一轮、收集参数或文件）或记忆卡（说明这一轮用了开发者偏好）时读。没有这些工具的宿主不输出本文的任何标签（会被原样显示出来），照 [../design/按轮问.md](../design/按轮问.md) 的文字格式发。问什么、一轮问哪些由 [../design/按轮问.md](../design/按轮问.md) 定，本文只管怎么写成表单。

## 规则

### 先跑脚本，再原样粘贴

Studio 只认格式完全正确的 JSON；写错时开发者看到的是一句「表单无法显示」，或者控件被悄悄换成单行文本。所以表单和记忆卡一律由脚本校验并生成，不手写标签、不凭记忆拼 JSON：

1. 按下面「每种控件怎么写」写表单体 JSON（只写 `lang`、`submitLabel`、`questions`，`id` 和 `title` 走参数），用 shell 交给脚本：

   ```bash
   python3 <skill目录>/scripts/studio_card.py form --id round-2 --title "需求确认 · 第 2 轮" - <<'JSON'
   {"lang":"zh-CN","submitLabel":"提交回答","questions":[ … ]}
   JSON
   ```

   记忆卡用 `studio_card.py memory -`，只写 `summary` 和 `used`。
2. 脚本退出码非 0 时，按它列出的每一条改 JSON 再跑，直到输出一整行 `<question-form …>…</question-form>`（或 `<od-card …>…</od-card>`）；脚本通过了才发。
3. 把脚本输出的那一整行**原样**复制进最终回复，一个字符都不改；要改内容，改 JSON 重新跑。
4. 表单是这条最终回复的**最后一段**：前面写交接消息正文（[../design/交接消息.md](../design/交接消息.md)），表单之后不再写任何字、不再调用工具，等开发者提交。记忆卡放在正文开头或交接消息正文之后、表单之前。
5. 表单和记忆卡直接放在正文里，不放进代码块、引用块或列表，不在过程说明（commentary）里发；一条回复最多一张表单、一张记忆卡。

### 按轮问怎么写成表单

| 按轮问的规矩 | 表单里怎么写 |
|---|---|
| 一轮 | 一张表单，标签写 `id`（`round-1`、`round-2`……，同一应用不重复）和 `title`（例如「需求确认 · 第 2 轮」）；JSON 写 `lang: "zh-CN"`、`submitLabel: "提交回答"`、`questions` |
| 一轮超过 5 题 | 一张表单最多 5 题，一条回复只能放一张：先发前 5 题，开发者提交后接着发下一张，剩下的题仍算这一轮，不因换张推迟到下一轮重排 |
| 一道题 | 一个 `questions` 元素：`id` 用题号（`q7`），`label` 写「Q7 从哪开始：……」，`type` 有选项的用 `radio`（多选用 `checkbox`），没有现成选项的用 `textarea` |
| 选项 | `options` 每项写 `label`（给开发者看的话）、`value`（稳定的短英文）、`description`（选了会怎样） |
| 「其他，说说你的想法」 | 不另写选项，用 `allowCustom: true`、`customLabel: "其他，说说你的想法"` |
| 推荐答案 | 写进推荐那项的 `label` 末尾「（推荐）」，并在 `description` 里写为什么推荐；不用 `defaultValue` 预选（见「每种控件怎么写」） |
| 只有开发者知道的事实题 | `textarea`，不标推荐，`placeholder` 写「照实说；拿不准写『不确定』」 |
| 方向题 | 单独一张表单，只这一题 |
| 「我理解的是这些」 | 条目写在表单前的正文里；表单一题 `radio`，选项「对」「有不对的」，`allowCustom: true`、`customLabel: "哪条不对、怎么改"` |

- 表单前的正文照常写「刚做完 / 下一步 / 要你做的 / 花了多少」；「要你做的」写「在下面的表单里答」。
- 开发者不点表单、直接在对话里回「是」或逐题写，照 [../design/按轮问.md](../design/按轮问.md)「什么算定了」算；表单里没有「全部按推荐」的按钮，开发者要一次接受全部推荐，在对话里回「是」。
- ① 的「确认这一版」、② 的「都对，开工」不用表单：用 Studio 交方案的工具交 PRD 或方案，开发者点宿主确认卡或在对话中明确同意，任选其一，读回确认后再往下走；交方案要带的文件和上限以那个工具当前的说明为准，确认怎么登记见 [../design/开发文档/README.md](../design/开发文档/README.md)「确认怎么登记」。

### 表单体

| 字段 | 写法 |
|---|---|
| `lang` | 必写，开发者用的语言，中文写 `"zh-CN"` |
| `submitLabel` | 可选，按钮上的字，按轮问写 `"提交回答"` |
| `questions` | 必写，1–5 道题 |

每道题都写 `id`（英文字母开头，只含字母、数字、`-`、`_`，同一张表单不重复，按轮问用题号 `q7`）、`label`（题目，≤120 字）、`type`（下表 17 种之一，照写原名，同义词如 `single`、`dropdown`、`slider` 会被拒）；`required: true` 只在这题不答就没法往下做时写。字段只能用下表列出的，多写的字段脚本会拒绝。

### 每种控件怎么写

| type | 用在 | 这种控件另外能写的字段 |
|---|---|---|
| `radio` | 2–7 个选项里选一个 | `options`（必写）、`allowCustom`、`customLabel`、`customPlaceholder` |
| `checkbox` | 2–7 个选项里选多个 | `options`（必写）、`maxSelections`、`allowCustom`、`customLabel`、`customPlaceholder` |
| `select` | 选项多（8–20 个，如语言、城市）时选一个 | `options`（必写，每项可加 `group` 分组、`trailingLabel` 行尾短标记）、`allowCustom`、`customLabel`、`customPlaceholder` |
| `text` | 一行字（名称、关键词） | `placeholder`、`defaultValue` |
| `textarea` | 一段话（目标、说明、改法、事实题） | `placeholder`、`defaultValue` |
| `number` | 一个数 | `min`、`max`、`step`、`placeholder`、`defaultValue` |
| `range` | 在一个区间里拖着选 | `min`、`max`（都必写）、`step`、`defaultValue` |
| `date` | 日期 | `defaultValue`（`YYYY-MM-DD`） |
| `time` | 时刻 | `defaultValue`（`HH:MM`，24 小时） |
| `datetime-local` | 日期加时刻 | `defaultValue`（`YYYY-MM-DDTHH:MM`） |
| `color` | 颜色 | `options`（可选，2–7 个色块，`value` 写颜色）、`defaultValue` |
| `url` | 网址 | `placeholder`、`defaultValue` |
| `email` | 邮箱 | `placeholder`、`defaultValue` |
| `tel` | 电话 | `placeholder`、`defaultValue` |
| `file` | 请开发者上传文件（样例、截图、SOP） | `accept`（如 `".pdf,.png,.jpg"`）、`multiple` |
| `switch` | 开 / 关 | `defaultValue`（`"true"` 或 `"false"`） |
| `direction-cards` | 选界面风格方向 | `cards`（必写，2–4 张卡） |

- `options` 每项写 `label`（给开发者看的话，≤40 字）、`value`（稳定的短英文，字母、数字、`.`、`-`、`_`；`color` 写 `#rrggbb` 小写）、可选 `description`（选了会怎样，≤120 字）。选项写成对象，不写成纯字符串数组。
- `allowCustom: true` 让开发者在选项之外自己填，按轮问的「其他，说说你的想法」就用它，配 `customLabel`；写了 `customLabel` 或 `customPlaceholder` 就同时写 `allowCustom: true`。
- `min`、`max`、`step` 写数字不加引号；`defaultValue` 一律写字符串，数字也加引号（`"20"`）。
- `defaultValue` 只用来回填**已经定了**的值（例如开发者上一轮说过的开始日期），没有就不写，不写空字符串。`radio`、`checkbox`、`select`、`direction-cards` 不写 `defaultValue`：Studio 的表单 10 分钟没人答会自动提交，预选的值会被当成开发者选的；推荐项写在 `label` 末尾「（推荐）」，理由写进 `description`。
- `direction-cards` 每张卡必写 `id`（英文短词）、`label`、`mood`（一两句气质描述）、`references`（1–4 个参照）、`palette`（4–6 个 `#rrggbb` 小写颜色）、`displayFont`、`bodyFont`（字体栈，如 `"Georgia, serif"`）。

例子（一张表单最多 5 题，17 种控件要拆成几轮发，这里每种只列题目本身）：

```json
{"id":"q2","label":"Q2 从哪开始（推荐 A）","type":"radio","options":[{"label":"只填店名（推荐）","value":"name-only","description":"门店由应用去查，查到几家时让使用者选"},{"label":"店名、城市、官网都填","value":"full","description":"查得更准，但使用者要先准备好这些"}],"allowCustom":true,"customLabel":"其他，说说你的想法"}
{"id":"modules","label":"需要哪些模块","type":"checkbox","options":[{"label":"客户","value":"customers"},{"label":"订单","value":"orders"},{"label":"报表","value":"reports"}],"maxSelections":2}
{"id":"language","label":"界面语言","type":"select","options":[{"label":"简体中文","value":"zh-CN","group":"常用语言","trailingLabel":"ZH-CN"},{"label":"English","value":"en","group":"更多语言","trailingLabel":"EN"}]}
{"id":"appName","label":"应用名称","type":"text","placeholder":"例如：客户跟进助手","required":true}
{"id":"q1","label":"Q1 谁来用：这个应用给谁用？他们平时做什么、多久会用一次？","type":"textarea","placeholder":"照实说；拿不准写「不确定」"}
{"id":"pageSize","label":"每页条数","type":"number","min":1,"max":100,"step":1,"defaultValue":"20"}
{"id":"density","label":"信息密度","type":"range","min":1,"max":5,"step":1,"defaultValue":"3"}
{"id":"startDate","label":"开始日期","type":"date","defaultValue":"2026-10-22"}
{"id":"startTime","label":"开始时间","type":"time","defaultValue":"09:30"}
{"id":"startsAt","label":"开始时刻","type":"datetime-local","defaultValue":"2026-10-22T09:30"}
{"id":"accent","label":"主色","type":"color","options":[{"label":"蓝色","value":"#3b82f6"},{"label":"绿色","value":"#16a34a"}],"defaultValue":"#3b82f6"}
{"id":"referenceUrl","label":"参考网址","type":"url","placeholder":"https://example.com"}
{"id":"contactEmail","label":"联系邮箱","type":"email","placeholder":"name@example.com"}
{"id":"contactPhone","label":"联系电话","type":"tel","placeholder":"请输入电话号码"}
{"id":"references","label":"参考资料","type":"file","multiple":true,"accept":".pdf,.png,.jpg"}
{"id":"notifications","label":"启用通知","type":"switch","defaultValue":"false"}
{"id":"direction","label":"选择视觉方向","type":"direction-cards","cards":[{"id":"editorial","label":"杂志式排版","mood":"突出文字层级，保持宽松留白。","references":["杂志目录页"],"palette":["#f7f5ef","#181818","#315d4c","#d8cbb5"],"displayFont":"Georgia, serif","bodyFont":"system-ui, sans-serif"},{"id":"minimal","label":"简洁工具界面","mood":"无衬线字体，紧凑的信息层级。","references":["后台管理台"],"palette":["#ffffff","#111827","#2563eb","#e5e7eb"],"displayFont":"system-ui, sans-serif","bodyFont":"system-ui, sans-serif"}]}
```

### 记忆卡

这一轮的做法用到了 `dev_preferences` 里开发者写过的偏好时，可以发一张记忆卡，告诉开发者用了哪几条；没用到就不发。卡片体只写：

| 字段 | 写法 |
|---|---|
| `summary` | 一句话，≤80 字，例如「本轮按你的 2 条开发偏好写」 |
| `used` | 1–10 项，每项写 `type`（`profile`、`project`、`rule`、`feedback`、`reference`、`user` 之一；开发偏好一般写 `project` 或 `rule`）、`name`（这条偏好的一句话，≤40 字）、可选 `id` |

### 答案怎么回来

开发者提交后，下一条用户消息以 `[form answers — <表单 id>]` 开头，下面每题一行 `- <题目>: <答案>`；选择题回的是选项的 `label`，文件题回的是文件名，附件随消息一起到。写着 `(skipped)` 的题按没回答处理，下一轮接着问；整张表单都是 `(skipped)` 时不算开发者答了任何一题。开发者不点表单、直接打字回答，同样算数。

## 常见错误

- 手写标签没跑脚本，JSON 里漏了逗号、引号没转义（例如 `label` 里出现英文双引号），整张表单显示不出来。
- `type` 写成同义词或拼错（`dropdown`、`datetime`、`toggle`），控件被换成单行文本，开发者看不到选项。
- 选项写成字符串数组、`value` 用中文，答案对不上题。
- 给选择题写 `defaultValue` 预选推荐项，10 分钟后被自动提交成开发者的选择。
- 把脚本输出改动后再粘贴（加换行、改引号、套代码块），或在 `</question-form>` 后面继续写「请填写上面的表单」。
- 一条回复发了两张表单，或者表单发在过程说明里、随后又继续调用工具。

## 相关工具与契约主题

- 校验与生成：`scripts/studio_card.py`（`form`、`memory`；`reply` 校验一整条最终回复，排查「为什么没显示」时用）。
- 交方案、方案确认卡不用本文的表单：工具与保存机制见 [开发者中心与工作区.md](开发者中心与工作区.md)「Studio 宿主」，确认登记见 [../design/开发文档/README.md](../design/开发文档/README.md)「确认怎么登记」。
