# 单编排型 TPE 制作契约（二）：工具返回、并发、文件、失败与验证

写脚本里的 `tool()`、`parallel` / `pipeline`、文件产物、失败分支，或判断冒泡和 verify 能证明什么时读；接着 [单编排型TPE契约-脚本Schema与事件.md](单编排型TPE契约-脚本Schema与事件.md)。

本文分 2 份：[单编排型TPE契约-脚本Schema与事件.md](单编排型TPE契约-脚本Schema与事件.md)、[单编排型TPE契约-工具文件失败与验证.md](单编排型TPE契约-工具文件失败与验证.md)。

## WF-SINGLE-04 工具参数与返回

每个 `tool()` 使用当前资产的真实调用名，并带一句非空 `_rationale` 说明本步业务目的。字面参数必须满足工具 `input_schema` 的 required/type/enum；复杂动态值仍以工具运行时校验为准。

结构化消费按以下顺序确定 `_output`：

1. 读取工具正式 `output_schema`；
2. 有正式 Schema 时，只裁出下游真正使用的最小子集；
3. 没有正式 Schema 且工具可独立安全调用时，用代表性输入真实取样；
4. 根据真实结构编写候选 `_output`，再用新样本复验；
5. 无法获得可信结构时，不凭猜测按字段消费。

使用 `_output` 后，Runtime 优先对 MCP `structuredContent` 原对象校验；没有结构化返回时才尝试 JSON 快路和必要的文本抽取，最后仍必须通过 JSON Schema。Provider 已返回但不符合 `_output` 是步骤失败，不得改用另一段 text 静默兜底。

只需整段文本时使用 `_text=True` 并只做字符串处理。`_output` 与 `_text=True` 互斥。两者都未声明时返回值是不透明 `ToolText`，不按字段取值、不调 `.get()` 或 `json.loads()`。忽略返回值的副作用调用不需为了形式而增加返回契约。

一次取样只证明该样本；不根据一个值推导 enum，不把所有观测字段都设为 required，不自动回写工具正式 `output_schema`。

`_output` 的“最小”是指只保留下游实际读取的路径，不是只声明顶层容器。脚本迭代或索引某个数组，并读取元素的 `title/summary/source/value` 等字段时，该数组必须声明 `items.type="object"` 以及实际读取的 `items.properties`；对未做缺省处理的字段还必须列入 `items.required`。例如：

```json
{
  "type": "object",
  "required": ["items"],
  "properties": {
    "items": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["title", "summary"],
        "properties": {
          "title": {"type": "string"},
          "summary": {"type": "string"}
        }
      }
    }
  }
}
```

只写 `{"type":"array"}` 不能为数组元素的任何字段提供契约。

## WF-SINGLE-05 `parallel` 与 `pipeline`

- `parallel([...])` 只并发彼此无数据依赖、无共享可变状态、无共享固定文件路径的步骤。返回顺序与输入位置一致，不依赖完成先后。
- `pipeline(items, *stages)` 对不同 item 并发，对同一 item 按 stage 串行；上一 stage 返回值作为下一 stage 的唯一位置输入。它不提供跨 item 汇总或全局 stage 屏障。
- 数据依赖步骤用显式串行 `await`；跨编排型 TPE 的固定扇出、依赖和汇合使用 2.0 `workflow_orchestration` 中某条路线的无环 DAG。
- `parallel(...)` 和 `pipeline(...)` 都是一次可等待调用，不写成 `parallel(...)(...)` 或 `pipeline(...)(...)`。

## WF-SINGLE-06 Workspace 文件

运行时提供：

```python
ctx.process_dir  # 本次编排型 TPE 的过程目录，自带结尾斜杠
ctx.output_dir   # 本次编排型 TPE 的候选交付目录，自带结尾斜杠，拼文件名不再加 /
ctx.skill_dir    # 随编排型 TPE 资产交付的静态文件目录
ctx.dry_run      # 当前是否处于 Max 运行验证上下文
ctx.run_id       # 本次运行编号，形如 WFR-…；过渡期写应用库时填入 last_run_id
```

- 用户文件路径来自声明了 `format:"file"/"image"` 的 input 字段；
- 模板、辅助脚本和合成样例随资产交付，以 `ctx.skill_dir` 引用；
- 中间文件写 `ctx.process_dir`，交给下游或用户的候选产物写 `ctx.output_dir`；
- 不写 `/tmp`，不假设 `/workspace/output`，不依赖构建项目、个人目录、TPE ID 或 Project ID；
- 跨编排型 TPE 和最终 `output_schema` 传稳定 `/workspace` 绝对路径，文件字段使用 `format:"workspace-file-path"`，不传 URL、base64 或 `file://` URI；
- 返回路径前先真实生成文件。最终成功还必须通过 Schema、路径来源信任和 File Service 存在性校验。
- 路径来源信任只认三类：位于本次 `ctx.output_dir` 下；来自本编排型 TPE input 里声明为 `workspace-file-path` 的字段；本次某个工具或 FastAgent 步骤的返回值里以结构化形式出现（返回值本身是 `/workspace/...` 路径，或返回的 JSON / 对象字段的值是该路径）。说明文字里夹带的路径不算，例如 `file` 工具的写入回执 `File written successfully: <路径>`、shell 回显；三类都不满足即 `WORKSPACE_PATH_UNTRUSTED`。
- 因此 `ctx.process_dir` 里用 `file` / `shell` 写出的中间文件不能作为输出返回；要返回的文件（包括诊断文件）直接写进或复制进 `ctx.output_dir`。仅表示未来写入位置的目标路径、目录也不是交付文件。

Max 编排型 TPE 默认可调用 `file`、`shell`、`send_email`，不需为它们创建 Toolset。它们依赖 Max Runtime 注入的用户、Workspace、沙箱/会话或确认上下文，不能在外部编码 Agent 本机模拟；冒泡服务会为它们提供受控验证上下文，不等于必须创建持久真实项目。

### send_email 的参数与限制

`send_email` 是平台自带工具，`get_asset` 查不到，冒泡和预览也不校验它的参数，参数以本节为准：

| 参数 | 是否必填 | 说明 |
|---|---|---|
| `to` | 必填 | 收件人邮箱列表，至少一个，不设白名单；收件人只能来自使用者的填写或确认，不能自己编 |
| `cc` | 可选 | 抄送邮箱列表 |
| `subject` | 必填 | 标题，不超过 200 字符 |
| `body` | 必填 | 正文按 Markdown 写，发出前由平台转成网页格式 |
| `attachments` | 可选 | `/workspace` 下的文件绝对路径列表，限制见下文 |

发件人由平台注入，应用不用管，也不要在正文里写发件地址。平台对单封邮件没有速率限制，靠邮件服务商的配额兜底。调用时带 `_text=True` 和 `_rationale`，写法同其他工具步骤。

可用范围：所有编排型 TPE 的运行环境都由平台默认装入 `send_email`，路线里的编排型 TPE 和新路应用里一次执行所跑的编排型 TPE 都一样，不需要建工具集。它依赖运行环境注入的使用者与项目信息，所以只能在平台运行时里调用，应用后端自己的代码里没有这个工具，要发邮件就把这一步放进编排型 TPE。

### 用 send_email 把文件作为附件发出

2026-11-23 在 cn-qa 实测：文件放在编排型 TPE 的 `/workspace` 下时，`send_email` 能把原始 Excel 作为附件发出，收到的文件与原文件校验值一致。使用时遵守下面几条：

- 附件必须是 `/workspace` 下的绝对路径，路径要真实存在；过程文件和受限目录不能当附件，多个交付物先打成一个压缩包。
- 平台校验上限：单个文件 10MB，每封邮件最多 10 个附件、合计 25MB，接近上限时不保证送达。11MB 单文件的实测只看到「暂时无法投递」，看不出具体原因，所以脚本在发送前先检查文件大小，超限时把结果写成明确的失败状态。
- 带附件的邮件需要任务带组织身份：任务消息没带组织时按项目记录补齐，项目也没有可用组织时，带附件的邮件会失败，错误信息为 `Organization identity is required`。
- 收件人只能写使用者提供或确认过的邮箱，`to` 至少一个，`cc` 可选，主题不超过 200 字符。
- `send_email` 返回成功只表示邮件已提交，不表示对方已收到；平台没有送达回执，也没有按请求查询发送结果的入口。
- 收件人命中平台的退信抑制名单（曾经退信或投诉的地址）时，`send_email` 返回 HTTP 422、失败码 `recipient_suppressed`，这个地址不会收到邮件，排在它后面的收件人也不再发送。遇到这个错误要换收件人，或请使用者处理这个邮箱，重试不会成功。
- 同一次定时触发重跑，或使用者点重试，会再发一封，平台不按请求去重。外发步骤要自己防重复，例如先在应用库记录已发送的批次。`to` 与 `cc` 的每个收件人各发一封；部分收件人失败时工具返回失败，重试会让已收到的人再收一封。
- 群机器人不能发文件。需要同时通知群和发文件时，群里发摘要，邮件发完整文件。
- 应用后端自己文件空间里的文件，在这个应用实例的项目里挂载在 `/workspace/UserGlobalData/business_ui/{应用编号}/` 下，路径以实际运行时的 `ls` 为准，再交给 `send_email`。冒泡验证环境（2026-11-23 实测）的 `/workspace` 下没有 `UserGlobalData` 目录，这类路径只能在应用实例的真实运行里验证；冒泡里用脚本自己生成的文件验证附件发送。

## WF-SINGLE-07 失败与降级

工具步骤失败时，Runtime 先在 `step_results` 记录 failure，再向脚本抛异常。

- 必需步骤：不捕获，让异常冒泡，整条编排型 TPE failure；
- 文件生成或文件存在性校验失败属于技术失败，禁止捕获后返回 `{"report_path": ""}` 或删除成功分支的必填约束；
- 真正可选步骤：可以小范围捕获，但最终 `output_schema` 必须强制声明 `degraded` 和 `warnings`，并返回真实降级状态；
- 正常空结果是 `degraded=false`；工具正式返回已声明的逐项错误时，才能把成功子项作为显式部分成功；
- 最终输出只放稳定 warning code，不把 Provider 原始异常、内部地址或凭证写给用户；
- 脚本当前没有可靠的结构化 `retryable` 标记，不按错误文案猜测重试；
- 邮件、发布、扣费、创建对象等非幂等副作用不盲重试，响应丢失时先核对业务状态。

只有上层获得明确 `retryable=true`、调用幂等或只读，且仍在用户允许的副作用范围内，才能做有界重试。

## WF-SINGLE-08 验证边界

- Preview 通过：证明脚本满足当前静态规则，不证明 Provider 可用、真实返回匹配或产物存在。
- 可独立调用的 MCP 边界：用真实低副作用样本验证参数和候选 `_output`。
- Preview 通过后，Max 和 External 制作入口都必须通过 Max Runtime 对目标编排型 TPE 做冒泡运行，并对返回轨迹做语义验证；入口只改变调用适配，不改变冒泡语义和通过标准。
- 当前 Max 冒泡语义是 `dry_run=true` 且未开启 `full_run`：FA 不真起，按步骤 `_output` 生成桩值；`shell`、`file` 和直连工具真实执行；`ctx.dry_run=true`。使用代表性业务输入逐条运行，未提供输入时 Runtime 可能按 Schema 合成空值，但合成输入不能代替真实样例验收。
- 冒泡前必须检查副作用：邮件、通知、发布、扣费、创建远端对象、写正式业务状态等步骤使用 `ctx.dry_run` 只隔离该对外副作用，并返回满足最终 `output_schema` 的明确“未执行验证态”；Workspace 内用于验证管路的过程文件和候选产物仍应真实生成。不得用 `ctx.dry_run` 跳过普通工具、Schema 校验、文件管路，或绕过 FA 桩值导致的下游失败。
- FA 桩产出是按 `_output` 生成的空值，字段写了 `examples` 时取样例值；下游把它当真实路径、URL 或业务值时可能失败。这是冒泡覆盖边界，不得为得到假绿灯添加 `if ctx.dry_run` 绕过该下游。需要验证真实 FA 数据流时，用 `full_run=true` 重跑同一冒泡（`otpe_manage(bubble)` 或路线级 `scene_package_manage(bubble)`）：FA 实际跑；路线级全真运行通过的结果（`fa_stubbed=false`）即该路线的冒泡证据。要不要先问开发者见 [编排型TPE总契约.md](编排型TPE总契约.md) 的全真运行规则。
- FA 桩返回空数组时，只证明数组容器通过了本次 Schema 校验；循环体、元素字段访问及其后续分支都没有执行，不得记为路径覆盖。给数组加单元素 `examples` 能让桩走到元素取值（[制作反例集.md](制作反例集.md) 第 7 节）。若 `_output` 连 `items` 元素 Schema 都缺失，属于必须修正的契约缺陷，不是可放行的冒泡盲区。
- 每条冒泡轨迹必须交给语义验证，核对逐步状态、错误和实际覆盖；轨迹只能证明本次输入触达的管路和非桩步骤，不能冒充 FA 内容正确或未触达分支已通过。External 的直接 `otpe_tool_test` 样本也不能冒充整条编排型 TPE 已运行。
- Bubble 的 `run_evidence.business_events` 必须返回已声明事件、已持久化事件、缺失必需事件、未触达事件、顺序和持久化裁决。本次路径缺少 `stage_started`、缺少 `stage_result/stage_failed` 终态，或事件顺序错误时，Bubble 必须失败。单条编排型 TPE Bubble 只核验脚本自有事件；Runtime 自有的 `artifact_ready` 与 `delivery_ready` 分别在路线级 Bubble 的 Artifact 登记与 Delivery 冻结后核验。实时推送成功不是证据，只有数据库持久化成功的事件才能计入。
- 单条编排型 TPE 的 Preview、bubble 和语义验证自动完成。端到端全真运行按业务路线做，覆盖该路线可能执行的全部编排型 TPE、Fast Agent、用户/Agent 介入、Delivery 和 Review；要不要先问开发者、不同意时怎么记录，见 [编排型TPE总契约.md](编排型TPE总契约.md) 的全真运行规则。
- 运行证据必须确认实际命中了目标编排型 TPE，不只看项目最终状态。
- 参数、Schema、路径或脚本可修复错误修改原资产，不重复创建副本规避校验。

## WF-SINGLE-09 作为图节点的就绪条件

编排型 TPE 进入 2.0 图业务路线前，除本契约前述要求外，还必须满足：

- `input_schema` 和 `output_schema` 都是根 `type=object`，required 与脚本真实读取、返回一致；
- 名称和描述能够单独说明该节点完成的稳定业务阶段，不依赖图中位置才能理解职责；
- 输入只来自运行期用户输入、上游真实 `TaskPoint.output.data`、路线静态配置或随资产交付的 Skill 文件，不依赖创建者沙箱；
- 输出是下游和 Delivery 真正消费的稳定对象，不把自然语言日志、COT 或 WorkflowRun 汇总当正式事实；
- 来源型输出的每条结论都带上它的证据引用（来源编号或链接），跨节点后不能只保留结论文本；
- 跨节点文件同时在上游 output 和下游 input 声明 `format:"workspace-file-path"`，值位于真实 TaskPoint Workspace；
- 脚本内部不询问用户、不决定下一条业务路线、不调用最终交付 Gate；结构化补参、Agent 介入和最终审阅由 [多编排型 TPE 制作契约](多编排型TPE契约-图模型与标准对象.md) 的路线契约声明；
- 节点可独立 Preview 和 bubble，当前版本的轨迹与语义验收已记录。图保存通过不能补偿某个节点没有单体验收。

单条编排型 TPE 场景在 2.0 控制器中等价于“一条 orchestration 内一个编排型 TPE 节点”。这不改变脚本契约，也不要求为了形式拆出额外编排型 TPE。没有编排型 TPE 的场景包继续使用 SA 或普通任务点，不创建空节点、空 DAG 或伪装的编排型 TPE。
