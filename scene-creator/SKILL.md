---
name: scene-creator
description: 当用户需要把业务流程制作成可在 GoalfyMax 直接使用的场景包，或需要创建、更新、验证和发布单 Workflow、多 Workflow 及其业务界面时使用。以内置的完整场景包领域模型和业务顾问式访谈方法理解需求，把场景包设计为通往共同业务终点的多条候选路线，并用用户业务档案指导本次个性化选路；通过经过审计的 scene-creator 外部 MCP，完成线上资产复用、工具契约发现与真实取样、依赖准备、脚本及输入输出 Schema 编写、辅助文件交付、场景编排、预览、bubble 验证、业务界面制作与发布、可选全真项目验证、日志与交付物检查、问题修复和最终发布；也适用于根据真实项目执行日志复盘，维护、诊断和迭代已有场景包及业务界面。[skill-version:v1.0.0]
keywords:
  - scene package
  - scenario package
  - 场景包
  - workflow
  - multi-workflow
  - workflow orchestration
  - bubble validation
  - business UI
  - 业务界面
  - GoalfyMax
  - GoalfyHub
  - apc_skill
  - toolset
  - tool group
  - FastAgent
  - TaskAgent
  - MCP
  - scene diagnosis
  - project log analysis
  - 场景包优化
  - business archive
  - 业务档案
  - personalized routes
  - 个性化选路
---

# 场景包制作

通过外部 MCP 创建与 Max 实际执行一致的 Workflow 资产。以线上 MCP 工具 Schema、服务端校验和返回的资产数据为准。禁止虚构资产 ID、工具名、参数、Schema、版本或返回字段。

> 本文件是完整制作主流程。以下文档按阶段补充细节：
> - [外部 MCP 工具路由](references/external-mcp-tools.md) — 外部 MCP 的完整工具清单、调用顺序、ID 纪律和验证职责；创建工单前读取
> - [方案挑战检查清单](references/方案挑战检查清单.md) — 业务闭环、能力闭包和执行形态审查；创建资产前读取
> - [Workflow 验收检查清单](references/Workflow验收检查清单.md) — 单条 Workflow 的 IO、轨迹、文件和未覆盖路径验收；每次 bubble 后读取
> - [业务界面制作契约](references/业务界面制作契约.md) — 官方模板下载、开发、打包、上传、部署和恢复；业务界面标记为 `required` 时读取
> - [业务界面验收检查清单](references/业务界面验收检查清单.md) — 业务界面绑定、SDK、交互和部署证据；业务界面交付前读取
> - [场景包验收检查清单](references/场景包验收检查清单.md) — 整包依赖、编排、交付和全真边界；场景包发布前读取
>
> 上述路径相对于本 `SKILL.md` 所在目录，不是当前工作目录。优先使用平台加载 Skill 时提供的真实路径；路径不确定时按文件名搜索，不要凭记忆拼接插件缓存目录。

## Prerequisites

**Required MCP Server**：`scene-creator`

scene-creator MCP 当前提供 12 个经过审计的场景包管理与执行工具；所有资产查询、制作、验证、项目运行和发布操作都通过 GoalfyMax QA 后端完成。实时工具数量和参数仍以 `tools/list` 为准。

**MCP configuration**（streamable HTTP、API Key、Bearer）：

```json
{
  "scene-creator": {
    "type": "streamable-http",
    "url": "https://workflow-mcp.qa.goalfyai.com/mcp",
    "headers": {
      "Authorization": "Bearer ${SCENE_CREATOR_API_KEY}"
    }
  }
}
```

- `SCENE_CREATOR_API_KEY` 的值是当前用户完整的 GoalfyMax QA 个人 API 密钥，前缀为 `sk_`；缺失、已撤销或没有被新进程读取时，所有工具都会返回未认证。
- 发布包已包含连接配置。Codex 从 `~/.codex/.env` 或启动进程环境读取 `SCENE_CREATOR_API_KEY`；Claude Code 按插件 MCP 配置引用同名环境变量。
- 不配置 `user_id`、`X-User-ID` 或 `X-Project-ID` 作为身份凭证。服务端根据个人 API 密钥解析用户，项目和工单标识只在实时工具 Schema 明确要求时传入。

**Required CLI**：无。场景包资产操作全部通过 MCP；本地 Agent 只使用自身文件和 HTTPS 能力完成预签名文件传输、业务界面开发、归档和校验。

**Getting an API Key**：登录 GoalfyMax QA，打开账号菜单 → **开发者工具** → **API 密钥**（`/developer/api-keys`），创建具名个人密钥。完整 `sk_...` 只显示一次；如果没有入口，说明账号没有开发者权限，应联系管理员开通，不能借用他人的密钥。当前账号最多保留 10 个有效密钥。

严禁把密钥写入仓库、Skill、工单、检查点、日志、命令参数或聊天。需要用户配置时，只输出以下要求，不让用户在对话中发送密钥：

```markdown
# 需要用户操作：连接 scene-creator

**请在 GoalfyMax QA 的“开发者工具 → API 密钥”创建或选择个人密钥，并将完整密钥写入本机 `SCENE_CREATOR_API_KEY` 环境变量。不要把密钥发给我。**

**完成后彻底重启当前 Agent 客户端，再回来让我验证连接。**
```

**Connection verification**：在新会话中确认 Skill 已加载、MCP `scene-creator` 已连接、实时 `tools/list` 包含本文工具概览中的核心能力、`workflow_tpe_manage` 包含 `bubble`，并执行一次只读 `list_assets`。安装验证不得创建工单、资产、项目或部署。

连接成功后，以实时 `tools/list` 为当前工具名、action、参数和必填字段的唯一真相。当前稳定能力及职责见 [外部 MCP 工具路由](references/external-mcp-tools.md)；文档中的清单用于发现和路由，不覆盖实时 Schema。

外部 MCP 运行在远端，不能直接读取或写入当前 Agent 的本地文件系统：

- 上传 Workflow 辅助文件或业务界面源码时，先取得预签名上传请求，再由当前 Agent 读取本地字节并执行 HTTP `PUT`，最后回调完成；
- 下载业务界面模板或已有源码包时，MCP 只返回临时下载 URL，由当前 Agent 在本地下载、校验和解压；
- 不要把本地路径传给远端 MCP 并期待它读取，也不要把预签名 URL 当成本地文件路径。

若 MCP 返回未认证，先检查 `SCENE_CREATOR_API_KEY` 是否存在、密钥是否已撤销，以及插件是否在密钥配置后彻底重启。只检查变量是否存在，不打印其值；不得生成、猜测、回显或记录 API Key。

---

## 1. Boundaries and Core Concepts

根据用户的表达方式调整沟通层级：用户使用技术语言时可以精确讨论资产和契约；用户只描述业务时，使用管理和业务语言，不要求其理解资产 ID、Schema、TPE、Toolset 或 Agent 内部结构。

### 1.1 When to Use Scene Creator

出现以下任一信号时使用本 Skill：

- **创建场景包**：用户希望把一套业务流程、SOP、经验或已完成项目沉淀成可复用的 GoalfyMax 场景能力；
- **制作 Workflow**：用户要创建、更新或验证单 Workflow、多 Workflow 固定编排及其输入输出契约；
- **诊断或优化场景包**：场景包效果不好、执行绕圈、成本高、结果不稳定、路由错误，或资产配置存在问题；
- **分析真实项目**：用户提供项目 ID，希望通过完整执行日志定位瓶颈，并把结论用于创建或优化场景包；
- **制作业务界面**：场景包需要专属表单、进度、结果和交付物界面，或已有界面需要随 Workflow 契约迭代；
- **维护依赖能力**：场景包制作过程中需要复用、补建、授权、取样、上线或修复 Toolset、Tool Group、FastAgent、普通任务点和 Skill 文件；
- **验证和发布**：需要执行 Preview、bubble、语义验收、整包验收、可选全真项目测试、日志复检和最终发布；
- **继续未完成制作**：已有 `task_id`、场景包 ID、Workflow ID、run_id、project_id 或 deployment_id，需要恢复原工单和检查点继续执行。

不要在以下情况使用本 Skill：

- 只执行一次普通业务任务，不准备沉淀、诊断或维护场景资产；
- 只开发与场景包无关的独立网站或通用前端项目；
- 只询问 GoalfyMax 产品概念但不需要场景包资产操作；
- 试图复制 Max 内部系统提示词、内部状态机或未通过外部 MCP 暴露的管理能力。

### 1.2 Capabilities

- 通过业务顾问式访谈提炼目标用户、触发场景、里程碑、输入、交付物、权限边界和验收标准；
- 搜索并反读场景包、Workflow、普通任务点、Toolset、Tool Group、FastAgent、Dataset、经验体和项目证据，优先复用现有资产；
- 根据稳定性、交互需求和推理边界选择 System Agent、TaskAgent、FastAgent、单 Workflow 或多 Workflow；
- 创建和维护 `apc_skill`、场景 Skill 文件、依赖闭包、Workflow 脚本、input/output Schema 和 `workflow_orchestration`；
- 对没有可信 output Schema 的只读 MCP 工具执行真实取样和候选 Schema 复验；
- 通过预签名上传交付 Workflow 辅助文件、模板、样例和场景知识文件；
- 执行 Preview、bubble、Workflow 语义验收、场景包整体验收，并按证据修复原资产；
- 下载当前官方业务界面模板，按真实 Workflow 契约开发、检查、打包、上传、部署和反读专属界面；
- 发布经过验证的场景包，并在用户批准后运行真实 Max 项目、检查完整日志与交付物；
- 对已有场景包执行分层诊断、严重度分级、改前/改后说明、范围确认和受影响链路回归验证；
- 通过统一工单保存检查点、资产身份、验证结论和剩余盲区，形成可审计制作记录。

### 1.3 Intent Routing

收到请求后先判断用户要解决的是哪一种问题，再进入对应执行流：

| 用户意图 | 路由方式 |
|---|---|
| 把一套业务流程、SOP 或经验做成可复用能力 | **创建模式**：访谈业务目标与里程碑，形成蓝图，复用或创建资产，完成验证、业务界面和发布 |
| 已有场景包效果不好、执行绕圈或配置异常 | **诊断模式**：从目标场景包和真实项目证据出发，逐层定位结构、契约、提示词或运行机制根因 |
| 已知具体问题，希望修改已有场景包或 Workflow | **优化模式**：先反读现状和影响范围，在原资产上修复，并重建受影响的 Preview、bubble、界面和整包证据 |
| 用户提供项目 ID，要求分析执行过程 | **日志分析模式**：完整读取执行摘要、详细日志和交付物证据，区分症状与机制根因，再决定是否进入诊断或优化 |
| 用户要求单独制作或更新业务界面 | **界面维护模式**：先确认其绑定场景包和最终 Workflow 契约，再从官方模板初始化、验证和发布 |
| 中断后继续已存在的制作任务 | **续作模式**：恢复原工单、资产 ID、验证状态和待处理问题，不重新创建平行资产 |

如果模式或目标对象不清，先用渐进式访谈补齐最小充分上下文；如果只是缺少可通过工具发现的知识、Schema 或资产信息，继续调查，不把平台内部信息缺口转嫁给用户。详细沟通方法见第 5 节。

## 2. Core Constraints (violation = task failure)

以下任一项违反都视为当前制作未完成，而不是可忽略的格式问题：

1. 首次预览、写入、真实取样、项目运行、下载或审计前，先创建工单；同一 mode 内的后续审计操作复用同一 `task_id`。只读诊断获用户授权转入修复时，必须新建受版本闸门保护的 write 工单，并用 `continued_from_task_id` 关联原 read 工单，不得拿 read `task_id` 调写 action。
2. 工具名、action、参数、资产 ID、Schema 和版本只能来自实时 `tools/list`、线上资产反读或服务端返回，禁止从本文、历史对话或名称猜测。
3. 先复用再创建；更新失败时修复原资产，不用重复创建同名资产绕过错误。
4. Workflow 必须遵循“Preview → bubble → Agent 语义验收 → 可选全真项目验证”，`success`、创建成功或页面可打开都不能替代验收证据。
5. 每条 Workflow 创建前，完整依赖闭包必须真实存在且已上线；运行时默认能力除外。
6. 多 Workflow 只保存一份完整 `workflow_orchestration`，不得把 DAG 复制进 `apc_skill` 或业务界面。
7. 业务界面标记为 `required` 时，必须从本工单 `download_template` 返回的当前官方模板开始，并在当前 Workflow 契约冻结后重新验证和部署。
8. 所有下载、上传、发布、收费、通知和正式业务写入均按真实副作用处理；需要授权时在动作发生前确认，bubble 中也不能假设直连工具无副作用。
9. 没有证据就明确记录盲区；不得把 FA 桩值、未触达分支、未运行项目或未验证内容描述成真实通过。

## 3. Scene Package Model

### 3.1 What a Scene Package Is

场景包是 GoalfyMax 在一类业务场景中的运行时能力包。它同时规定：

- Agent 需要理解的业务目标、规则和权限边界；
- 可以调用的普通任务点、Workflow、Toolset、FastAgent 和工具；
- 可以读取的长期数据集、固定版本数据集模板和场景知识文件；
- 固定多阶段流程的编排关系、输入映射和最终交付边界；
- 是否需要与场景包一对一绑定的专属业务界面。

场景包不是一段长提示词、一个工具列表、一张配置表，也不是所有用户只能照走的一条固定 SOP。它定义的是一个明确的业务终点、能力边界以及多条可到达终点的候选路线：不同用户可以因为当前状态、资料准备度、长期目标、判断标准、历史选择和实际结果而走不同路线。高质量场景包要让 Agent 知道“何时做什么、为什么这样做、哪些事情不能自行决定”，同时把每条路线中稳定且重复的执行片段交给确定性资产，避免每次重新规划。

典型组成如下：

```text
场景包
├── apc_skill：Agent 启动时始终可见的业务路由、里程碑和边界
├── 场景 Skill 文件：按明确时机读取的详细知识、模板和 SOP
├── 普通任务点：需要 TaskAgent 临场判断或与用户交互的完整任务
├── Workflow 任务点：稳定、可测、可复跑的确定性脚本
├── workflow_orchestration：多 Workflow 的固定 DAG、映射和 handoff
├── Toolset
│   ├── Tool Group：真实 MCP 工具及其单工具契约
│   └── FastAgent：自包含的推理子任务
├── 长期数据集引用或固定版本数据集模板
└── 可选业务界面源码包：与场景包一对一绑定、同工单制作和发布
```

这些资产不是越多越好。每个资产都必须对应一个明确的业务职责；没有独立职责的包装层会增加路由歧义、成本和维护负担。

### 3.2 Runtime Roles and Asset Relationships

- **System Agent**：面向用户理解意图、选择场景能力、组织任务和完成交付。
- **TaskAgent**：在普通任务点中执行一个需要独立上下文、临场决策或用户交互的完整任务。
- **FastAgent**：一次输入、独立完成、一次输出的推理单元，中途不与用户交互。
- **Workflow**：把多个确定步骤编排成脚本，可调用工具或 FastAgent；负责控制流和数据流，不负责开放式推理。
- **Toolset**：按稳定能力域组织工具与 FastAgent，并说明它们如何组合使用。
- **Tool Group**：一组来自同一 MCP 的真实工具；单工具功能和参数契约属于这一层。
- **Dataset**：承载可长期复用的业务数据、关系和查询规则，不把数据表知识重复写进场景 Skill。
- **业务界面**：消费场景包公开的输入、状态和交付契约，为用户提供专属操作体验；不执行 DAG，也不读取内部资产配置。

场景包负责把这些能力放进同一个业务上下文，不应把每一层的内部逻辑都复制到 `apc_skill`。

### 3.3 Information Ownership and Single Source of Truth

同一规则只保留一个权威位置。判断信息应该放在哪里时，先问“它跟着谁变化”：

| 信息 | 权威位置 | 不应重复到 |
|---|---|---|
| 单个工具做什么、参数怎么填 | Tool Group 的工具描述和 Schema | Toolset Skill、`apc_skill` |
| 多个工具或 FastAgent 如何搭配 | Toolset 使用指南 | 单工具描述 |
| 一个推理子任务怎么完成 | FastAgent 提示词 | `apc_skill`、Workflow 说明 |
| 一个交互式任务怎么执行 | 普通任务点提示词和输入输出要求 | Toolset 使用指南 |
| 稳定步骤和单阶段数据流 | Workflow 脚本 | `apc_skill` |
| 多 Workflow 的依赖和输入映射 | `workflow_orchestration` | `apc_skill`、场景 Skill 文件 |
| 业务目标、里程碑、权限边界和读取路由 | `apc_skill` | 工具描述 |
| 长领域知识、模板、案例和详细 SOP | 场景 Skill 文件 | `apc_skill` 正文 |
| 数据表语义和查询规则 | 数据集 Skill | 场景 Skill 文件 |
| 业务界面业务代码和编码期契约快照 | 业务界面源码包 | `apc_skill`、Workflow 脚本 |
| 业务界面可调用的平台能力 | 当前模板 SDK 与宿主运行契约 | MCP 工具清单、页面自建 API |

避免以下错误：

- 在 `apc_skill` 中复制确定性 DAG，形成两份流程真相；
- 在 Toolset 使用指南里重复每个工具的参数说明；
- 在场景 Skill 中描述 FastAgent 的内部推理步骤；
- 为已经由 Workflow 固化的流程再写一套自然语言执行步骤；
- 同一业务规则在多个资产中分别维护，修改后产生漂移；
- 让业务界面自行选择 Workflow、推进节点或解释内部编排。

### 3.4 Choosing Workflow, TaskAgent, FastAgent, or Direct Execution

先把业务目标拆成阶段，再判断控制流和推理边界。按以下顺序一次完成选择，不要在资产类型之间反复横跳：

1. **先看编排是否稳定**
   - 执行中需要根据新信息临场选择路线、需要与用户来回确认，或 Agent 产生的新值会改变剩余流程 → 使用普通任务点 / TaskAgent。
   - 同样的步骤、顺序或并行关系可以预先确定，输入输出能够定义和验证 → 继续判断 Workflow 或 FastAgent。
2. **再看是否存在多个真实步骤**
   - 至少两个确定步骤、多工具串联或并行、会被重复执行 → 使用 Workflow；需要推理的局部步骤在 Workflow 中调用 FastAgent。
   - 整件事本质是一次输入、一个自包含推理过程、一次输出 → 直接使用 FastAgent，不为它套单步纯转发 Workflow。
3. **最后判断是否值得沉淀资产**
   - 一次性、低风险、少量确定调用，且没有稳定复用价值 → 由 System Agent 直接执行。

不要因为流程只有两三步就否定 Workflow；只要步骤真实、稳定并存在数据流，短 Workflow 仍然合理。也不要因为某一步需要大模型就把整条稳定流程改成普通任务点；将该步骤封装为 FastAgent 即可。

多 Workflow 只用于固定 DAG。Agent 只在明确的 `sa_handoff` 边界介入；如果 Agent 需要改路线、补充顶层输入或重新解释已完成节点，应接管剩余流程，而不是假装原 DAG 仍然有效。

### 3.5 Route Diversity and Archive-Guided Execution

把场景包理解成“通往业务终点的路线地图”，而不是“唯一标准路线”。路线可以满足不同目标、准备状态和决策偏好，也可以由 Workflow、普通任务点、FastAgent、工具和 Agent 判断共同组成。制作时必须先区分：

- **终点**：本场景承诺解决的业务问题和可验收结果；
- **候选路线**：到达终点的不同业务路径，以及每条路线适用的目标、前置条件和代价；
- **稳定路段**：不因用户而改变、可以固化为 Workflow 的确定执行片段；
- **选路节点**：需要结合当前用户档案、当前意图或新证据决定走哪条路线的 Agent 判断边界。

`apc_skill` 必须指导运行时 Agent 在决定本次具体路线前，先判断当前用户是否存在与任务相关的业务档案，并只读取足以影响本次选路的内容：

- **实体档案**说明“当前对象是谁、具备什么、缺什么、哪些信息过期或冲突”；
- **情境档案**说明“这个用户在这类长期任务中的目标、标准、约束、历史选择、选择理由和实际结果”。

两类档案是独立证据源，不要求彼此建立关系。用户明确表达和当前有效约束优先；历史观察用于支持或反对候选路线；Agent 推断必须标为假设，不能冒充用户偏好。档案存在不等于必须读取全文，档案缺失或与当前任务无关时继续使用当前对话和已授权材料，不虚构档案内容，也不为了个性化强行追问。

档案应当实质改变本次执行的路线、参数、优先级或解释。如果读取档案后仍向所有用户提供完全相同的流程，只在答案中复述档案信息，不算个性化执行。档案只能在场景包既有终点、能力、权限、安全和工具契约内影响选路，不能扩大权限或绕过确认。

当档案状态决定要走哪条路线时，不要把所有路线塞进一个带动态业务分支的 Workflow，也不要把某一条路线写成所有用户必走的 `workflow_orchestration`。将稳定路段分别固化，把选路保留给运行时 Agent 或明确的 `sa_handoff`。执行后，用户的选择、调整、拒绝、理由和结果可以按现有档案投稿机制形成候选事实；场景包不能直接修改用户档案。

### 3.6 From Business Problem to Scene Package Blueprint

先理解业务，不要先选工具。完整方案至少回答：

- 谁在什么情况下使用这个场景包；
- 要解决什么业务问题，成功结果是什么；
- 有哪些业务里程碑，每阶段接收什么输入、产生什么用户可见输出；
- 通往终点有哪些候选路线，每条路线服务什么需求、由哪些档案状态或用户判断触发；
- 哪些动作 Agent 可以自主执行，哪些必须由用户授权或判断；
- 哪些能力已有资产覆盖，哪些才是真正缺口；
- 是否需要专属业务界面，以及它承担哪些输入、进度和结果展示；
- 用什么证据证明场景包正确、完整且可交付。

缺少这些答案时，不应直接创建资产。

用户提供真实项目时，先看执行概览定位关键轮次，再深读相关 System Agent、TaskAgent、FastAgent 和工具日志。至少提炼：

- 有效推进、重复沟通、失败重试和等待分别发生在哪里；
- 主要瓶颈是缺知识、缺工具、缺搭配指引还是缺前置检查；
- 实际工具调用链和数据传递关系；
- 已有 Skill 是否被读取，以及为什么没有发挥作用；
- 最终产物是否真正满足用户目标。

不要只根据摘要、工具次数或最终 `success` 状态设计场景包。把每个低效点映射到正确资产：

- 缺业务知识 → `apc_skill` 或场景 Skill 文件；
- 不知道能力如何搭配 → Toolset 使用指南；
- 重复执行稳定流水线 → Workflow；
- 自包含推理反复出现 → FastAgent；
- 缺少临场判断或用户确认 → 普通任务点；
- 单工具契约不清 → Tool Group 描述或真实取样，不在上层猜测；
- 用户输入复杂、过程状态重要或交付物需要结构化消费 → 业务界面。

方案需要说明不可优化的部分和剩余盲区。没有真实基线时，不编造轮次节省比例或业务收益。

### 3.7 Runtime Scene Skill Quality

`apc_skill` 是 Agent 始终可见的最小业务控制面，应包含：

1. 场景解决什么问题、何时触发；
2. 业务里程碑及每阶段目标和用户可见产出；
3. 必需输入、预期输出和失败边界；
4. Agent 自主判断、用户确认和不可逆操作授权的边界；
5. 未被 Workflow 固化的关键业务规则和能力选择；
6. 每个场景 Skill 文件的明确读取时机。
7. 相关业务档案的识别与读取时机，以及实体档案和情境档案分别怎样影响本次选路；
8. 候选路线、适用条件、缺失/过期/冲突档案信息的处理方式，以及用户明确选择优先于历史推断的规则；
9. 用户选择、调整、拒绝、理由和结果如何作为候选事实回流，且不得直接写档案。

不应包含：

- 数字资产 ID；
- 制作过程、调试记录和发布说明；
- 已由 `workflow_orchestration` 固化的 DAG；
- 把某一条候选路线写成所有用户必须执行的唯一 SOP；
- 用户档案中的具体私有事实、数字档案 ID 或假定存在的档案内容；
- 单工具的完整参数 Schema；
- CSS、DOM、底层 API 或脚本实现细节；
- 没有读取时机的大段附件索引。

Skill 颗粒度由要消除的真实瓶颈决定：

- Agent 不知道先做什么 → 写前置检查和能力选择条件；
- Agent 不知道工具如何配合 → 写到调用链和数据传递关系；
- Agent 经常填错配置 → 在权威层写必填结构和约束；
- Agent 缺领域知识 → 写具体规则，不写“请遵循最佳实践”；
- Agent 找不到长知识 → 在 `apc_skill` 写“何时读取哪个文件”。

### 3.8 Evidence Chains for Creation, Diagnosis, and Optimization

- **创建**：业务素材和参考项目 → 理想态与业务蓝图 → 线上资产复用 → 架构方案 → 创建 → Preview → Bubble → 语义验收 → 发布 → 可选全真验证。
- **诊断**：用户问题或真实项目 → 场景包全貌 → 沿引用关系逐层下钻 → 对照服务端规范和运行证据 → 按严重度给出发现。诊断本身不授权修改。
- **优化**：诊断证据 → 用户明确的修复范围 → 更新原资产 → 只重验受影响 Workflow → 整包接缝验收 → 必要时重新发布和全真验证。不要用新建同名资产代替修复。

问题按影响分级：

- **critical**：会导致执行错误、数据不可信、权限或副作用失控；
- **warning**：不一定失败，但明显影响路由、稳定性、成本或维护；
- **suggestion**：改善可读性、复用性或体验。

### 3.9 Knowledge Boundaries

- 本 `SKILL.md`：场景包领域模型、用户沟通、制作、诊断、验证和发布流程；
- MCP `tools/list`：当前可调用工具、action 和参数的唯一真相；
- `get_diagnosis_doc`：完整 Workflow 契约、正反例和配置规范；
- Preview、Hub Validator、Bubble、Max Runtime：逐层验证真实实现；
- 专项引用文件：特定阶段的工具路由、界面开发和验收细节。

业务界面只消费宿主 SDK 和公开运行契约，不获取 MCP 工具清单，也不读取 Toolset、FA、提示词、Workflow 脚本或 DAG。场景包可以明确选择无业务界面并回落现有对话，但不能在选择需要界面后静默省略。

不要把 Max 内部“场景包助手”的整份系统提示词复制进本 Skill。内部状态机、消息协议、内部 FastAgent、Max 专属资产修改工具和运行环境只属于 Max；外部 Agent 只继承稳定的领域模型和设计方法，并严格使用当前外部 MCP 实时暴露的工具。遇到内外差异时，不模拟内部工具或复制内部流程。

## 4. Authoring Contracts

1. 先读 [外部 MCP 工具路由](references/external-mcp-tools.md)，并用线上 `tools/list` 核对当前工具和 action；参考表只负责用途路由，不替代实时参数 Schema。
2. 读取服务端契约前，先创建 Workflow 制作工单。
3. 确认任务需要制作 Workflow 后，调用一次 `get_diagnosis_doc(task_id=..., topic="workflow_authoring")`。
4. 编写任何 Workflow 脚本前，调用一次 `get_diagnosis_doc(task_id=..., topic="workflow_single")`。只有确认场景包需要多个 Workflow 后，才调用一次 `get_diagnosis_doc(task_id=..., topic="workflow_multi")`。
5. 使用特殊原语或契约，或者预览、Hub、运行时错误需要已知修复模式时，先读一次 `workflow_examples`，再只读取匹配的 `workflow_example_*` topic。
6. 创建或更新场景包时必须明确业务界面是 `required` 还是 `not_required`。选择 `required`，或已有场景包已经绑定业务界面时，完整读取 [业务界面制作契约](references/业务界面制作契约.md)。
7. 方案创建前读取 [方案挑战检查清单](references/方案挑战检查清单.md)；每条 Workflow 冒泡后读取 [Workflow 验收检查清单](references/Workflow验收检查清单.md)；业务界面交付前读取 [业务界面验收检查清单](references/业务界面验收检查清单.md)；发布前读取 [场景包验收检查清单](references/场景包验收检查清单.md)。这些检查清单承接 Max 内审查职责，由外部 Agent 自行执行，不调用或虚构不存在的 FA。

同一工单内不要重复读取相同 topic。MCP 知识库是共享 Workflow 契约和正反例的完整来源；本 Skill 内四份检查清单是外部制作入口的方案挑战与验收执行提示。发生冲突时以线上 Schema、Preview、Hub Validator 和 Max Runtime 为准。

## 5. User Collaboration and Intent Routing

把自己定位成场景包业务顾问，而不是配置录入员。用户通常只知道业务目标和当前痛点，不知道应该创建哪些资产；主动把业务语言翻译成场景方案，不要求用户学习 Toolset、FastAgent、TPE、Schema 或资产 ID。

遵守以下沟通原则：

- **结论和业务价值先行**：先说明理解到的目标、关键阶段、每阶段产出和主要风险，再补充必要依据。
- **渐进式访谈**：一次只问最影响下一步的一至三个问题；已经能从上下文、文件、项目日志或线上资产获得的信息不重复询问。
- **关键节点确认**：业务蓝图、能力削减或替换、高风险副作用、修复范围和对外发布必须在真正执行前确认；可逆的只读分析、资产搜索和方案完善自主推进。
- **用业务语言展示方案**：对用户说明“系统会做什么、分几步、每步产出什么、哪里需要你判断”，不要展示技术字段、参数、资产调用链或代码。
- **问题及时透明**：发现 critical 问题、权限限制、能力缺口或证据不足时立即说明影响与可选路径，不到最终交付才集中暴露。
- **不做确认机器**：有安全默认值的可逆选择直接采用并说明；只有用户掌握的信息、不可逆动作或会显著改变目标的取舍才暂停等待。
- **变更可审阅**：优化已有资产时，先说明当前问题、根因、拟修改位置和改前/改后，再执行已授权修改。

### 判断任务模式和授权边界

在创建工单、查询资产或提出方案前，先完成意图路由。模式决定证据来源、允许的写操作和交付物：

| 用户表达或已有上下文 | 模式 | 首要动作 |
|---|---|---|
| “创建场景包”“把这套流程固化”“基于项目/经验做一个场景包” | 创建模式 | 提炼业务场景、里程碑、输入、产出和授权边界 |
| “看看这个场景包有什么问题”“为什么效果不好”“检查配置” | 诊断模式 | 只读获取目标场景包全貌，沿真实引用关系逐层诊断 |
| “分析这个项目的执行日志”且目的是沉淀或改进场景能力 | 诊断模式 | 从真实项目执行证据反推瓶颈，再关联目标场景包或待建方案 |
| “修复/优化/更新这个场景包” | 优化模式 | 先诊断并明确修改范围，再更新原资产和受影响链路 |
| 已有 `task_id`，用户说“继续”或补充上一轮信息 | 续作模式 | 恢复工单、资产状态和最近有效检查点 |
| 只要求创建或修改某条 Workflow，目标和输入输出明确 | Workflow 资产任务 | 保持用户范围，不擅自扩展成新场景包 |
| 无法判断是创建、诊断、优化还是普通业务执行 | 未明确 | 只询问模式或目标，不启动工单 |

创建完成后的试运行暴露问题时，自然转入诊断或优化；诊断发现必须补建资产时，在用户授权的修复范围内进入创建。同一 read 或 write mode 内优先沿用原工单和原资产；read 诊断转入任何修复/优化写操作时属于权限边界变化，必须创建新的 write 工单，传 `continued_from_task_id=<原 read task_id>` 和当前 `skill_version`，由新工单继续引用原检查点。

### 区分信息缺口

不要把所有未知都变成用户问题：

| 缺口 | 例子 | 处理 |
|---|---|---|
| **意图缺失** | “帮我弄一下”“做个东西” | 询问要创建、诊断还是优化，以及最终业务目标 |
| **关键业务参数缺失** | 创建但没有业务场景；诊断但没有目标场景包或项目 | 只询问无法从上下文或线上资产获得的必要信息，得到后再启动 |
| **知识缺失** | 用户不知道需要哪些工具、资产或 Workflow | 不反问用户；依据本 Skill 的领域模型、线上资产和服务端契约自行设计 |
| **可选偏好缺失** | 未指定命名、Focus/泛化倾向或是否需要额外报告 | 采用保守且可逆的默认值，并在方案中说明 |
| **授权缺失** | 对外发布、收费、写正式业务状态、删除或替换重要资产 | 在真正执行该动作前单独请求授权，不用它阻塞前面的只读分析和方案设计 |

### 收集最小充分上下文

按需从对话、已选资料、线上资产和工单中提取以下信息，不要一次性把整张问卷抛给用户：

- **对象**：新场景包、已有场景包、某条 Workflow，还是一个参考项目；
- **业务目标**：谁在什么情况下使用，成功结果是什么；
- **业务里程碑**：关键阶段及其依赖；
- **输入与产出**：启动前必须提供什么，最终交付什么；
- **参考证据**：真实项目、经验体、文件、已有资产或失败日志；
- **权限和副作用**：哪些动作可以自主完成，哪些必须确认；
- **验收标准**：用户怎样判断场景包真的变好或可以使用。
- **业务界面**：是否需要专属操作界面；如果需要，哪些输入、进度和结果必须结构化呈现。

已有信息不要重复询问。一次只问最影响下一步的一至三个问题；用户只给业务语言时，由外部 Agent 负责翻译成资产方案，不要求用户理解 Toolset、FastAgent、TPE、Schema 或资产 ID。

## 6. Tool Overview

### 6.1 MCP Tools

| Tool | Purpose |
|---|---|
| `workflow_task_manager` | 创建、读取、追加检查点并完成可审计制作工单；第一个审计写操作，后续复用同一 `task_id` |
| `list_assets` | 搜索可复用场景包、Workflow、普通任务点、Toolset、Tool Group、FastAgent、Dataset 和经验体 |
| `get_asset` | 读取完整资产、关系、工具契约、Schema、版本、在线状态和经验页面 |
| `get_diagnosis_doc` | 读取服务端 Workflow 总契约、单/多 Workflow 规则、正反例、配置规范和诊断知识 |
| `dataset_read` | 只读访问当前用户有权限的数据集内容，为方案和验证提供真实数据证据 |
| `workflow_file_upload` | 通过 `prepare → PUT → complete` 或可信 HTTPS 来源交付 Workflow 辅助文件和场景 Skill 文件 |
| `workflow_dependency_manage` | 复用或维护 Toolset、Tool Group、FastAgent、Auth Card、普通自定义 TPE，并对安全 MCP 工具真实取样 |
| `scene_package_manage` | 创建、读取、更新、挂载编排并发布场景包；`workflow_orchestration` 使用完整对象替换 |
| `scene_package_ui_bundle` | 下载官方业务界面模板，上传、部署、查询状态、反读或下载场景包专属界面源码包 |
| `workflow_tpe_manage` | Preview、创建、更新、挂载、发布和 bubble Workflow；bubble 使用同一 `run_id` 轮询终态 |
| `manage_goalfymax_project` | 启动和控制真实 Max 项目；显式 `workflow_input` 用于确定性场景编排，全真运行会启动真实 FA 和副作用 |
| `get_project_execution_logs` | 读取项目执行摘要、详细日志和最终交付物，用于诊断、全真复检和交付 |

这张表是稳定能力地图，不是参数文档。每次调用前仍读取实时 Schema；发现线上工具新增、删除或 action 变化时，以 `tools/list` 为准，并记录需要更新本 Skill 的具体条目。详细 ID 纪律和调用职责见 [外部 MCP 工具路由](references/external-mcp-tools.md)。

### 6.2 Validation Responsibilities

- **MCP JSON Schema**：约束单次工具调用的参数形状和必填字段；
- **Preview**：校验 Workflow 脚本 AST、声明工具、input/output Schema、文件来源和确定性规则；
- **Hub Validator**：校验场景包 `workflow_orchestration` 的 DAG、映射、required、类型和 delivery；
- **供应商取样**：获取可安全直连 MCP 的真实返回，并验证候选 output Schema；
- **bubble**：FA 使用 Schema 桩值，普通 MCP、文件步骤和 shell 管路按运行时契约执行；
- **Max Runtime**：执行真实 FastAgent、默认工具、文件和完整业务行为；
- **当前 Agent**：负责业务语义、执行形态、权限边界、副作用、未覆盖路径、界面体验和最终修复裁决。

任何一层成功都不能替代下一层。工具返回 `success=true` 只说明该调用完成，不代表 Workflow、场景包、业务界面或业务目标已验收。

### 6.3 Core Call Chain

```text
创建或恢复工单
→ 读取实时工具清单和制作契约
→ 理解业务、项目证据与现有资产
→ 形成业务蓝图并执行方案挑战
→ 创建离线场景包草稿
→ 复用或补齐依赖并完成上线反读
→ Preview / 创建全部 Workflow
→ 保存多 Workflow 完整编排（如需要）
→ 对每条 Workflow 执行 bubble 和语义验收
→ 按冻结契约制作、部署并验收业务界面（required 时）
→ 整包验收、修复和发布
→ 逐条询问是否做全真验证
→ 运行一个真实 Max 项目并检查日志/交付物（用户批准时）
→ 写最终检查点并完成工单
```

## 7. Execution Flows

### 7.1 创建一个可审计工单

在第一次预览、写入、真实取样、项目运行、下载或审计动作前，从本文件 description 读取 `[skill-version:...]` 的完整版本值，并调用 `workflow_task_manager(action="create", task_name=..., task_description=..., mode="write", skill_version=<版本值>)`。纯只读诊断可传 `mode="read"`；写模式不得省略或猜测 `skill_version`。`task_description` 应写明当前模式、业务目标、预期交付物和验收边界。保存返回的 `task_id`，同一 mode 内的后续审计操作都传入该值。

纯只读诊断后用户授权修复或优化时，不得复用 read `task_id` 执行任何写 action。重新读取本文件版本标记，调用 `workflow_task_manager(action="create", mode="write", skill_version=<当前版本>, continued_from_task_id=<原 read task_id>, ...)`；创建成功后改用新 write `task_id`，原 read 工单及检查点作为可审计来源保留。服务端返回 `WORKFLOW_TASK_MODE_MISMATCH` 时，按 metadata 中的 `actual_mode`/`required_mode` 纠正工单，不把它误判成工单不存在或他人所有。

若创建 write 工单返回 `SCENE_SKILL_UPGRADE_REQUIRED`，立即停止写操作。只使用返回的 `upgrade_source`：从其 `git_url` 克隆精确 `ref`（`skill/<latest_version>`），再按平台选择 `platform_roots.codex` 或 `platform_roots.claude_code` 作为安装根目录并执行对应 `UPDATE.md`；不得猜测下载地址，也不得改用 ZIP。若 `upgrade_source` 缺失、Codeup 无权限或精确 tag 不存在，保持阻断并联系内部运维；运营侧在恢复来源可用前不得开启 required。`SCENE_SKILL_UPGRADE_RECOMMENDED` 只提示，不阻断本次工单，但升级仍使用同一受控来源。

中断后用 `workflow_task_manager(action="get", task_id=<task_id>)` 恢复上下文。资产创建和验证后，用 `workflow_task_manager(action="insert", task_id=<task_id>, entry_type="checkpoint", content=...)` 写入简洁检查点；不要把完整工具输入、供应商输出、凭证或日志复制进工单。

### 7.2 检查并复用线上资产

用 `list_assets` 查找候选场景包、Workflow、Toolset、Tool Group、FA 和数据集，用 `get_asset` 读取完整现状。

创建模式先寻找可复用资产再决定新建；诊断和优化模式先读取目标场景包全貌，再沿真实引用关系下钻，不能跳过上层结构直接凭某个子资产下结论。用户提供参考项目时，真实项目日志是业务流程和瓶颈的主要证据，不得只看场景包文案。

为每个脚本依赖收集线上调用名、所属资产 ID、input Schema、可见的正式 output Schema、当前版本和 Toolset 依赖。禁止从手册、其他项目或历史对话推断这些信息。

已完成项目中存在可复用业务经验时，用 `list_assets(asset_type="experience", ...)` 和 `get_asset(asset_type="experience"|"experience_page", ...)` 读取。经验数据只读，并继续受当前用户 Hub 权限约束。

### 7.3 执行方案挑战并质疑方案

读取 [方案挑战检查清单](references/方案挑战检查清单.md)。CC/Codex 根据清单和当前资产证据自行审查，不启动或假设存在方案挑战 FastAgent。

创建场景包前，先形成一份业务蓝图：目标用户和触发场景、共同业务终点、业务里程碑、每阶段输入与用户可见产出、通往终点的候选路线、每条路线服务的需求与前置条件、哪些档案状态会影响选路、需要 Agent/用户判断的边界、能力覆盖与缺口、验收证据，以及业务界面决策。业务界面必须明确为 `required` 或 `not_required`，不得在创建后期静默省略；已有业务界面时，优化范围默认同时包含契约兼容性检查。再解决业务输入不清、把某条路线误当成唯一 SOP、多余 Workflow、Agent 判断位置错误、不安全副作用和交付物缺失问题。面向用户使用业务语言展示蓝图，不展示资产 ID、参数名或技术调用链；工单中只写简洁结论。

### 7.4 选择执行形态并起草运行时 Skill

按本 Skill 的执行形态决策先决定哪些业务阶段应由场景 Skill、普通任务点、FastAgent 或 Workflow 承担，再用制作总契约区分固定阶段和 Agent 判断。每个脚本都应用单 Workflow 契约，只有固定 DAG 才应用多 Workflow 契约。不得因为外部 MCP 以 Workflow 制作为主，就把所有场景强行改造成 Workflow。

创建资产前，根据确认过的业务里程碑起草 `apc_skill`，只保留运行时 Agent 必须始终知道的内容：

- 场景包解决什么问题、共同业务终点是什么、何时使用；
- 业务里程碑，以及每阶段目标和用户可见产出，不复述脚本步骤；
- 通往终点有哪些候选路线、各自满足什么需求，以及哪些判断节点不能提前固化；
- 必需业务输入和用户预期输出；
- 哪些判断或授权保留给 Agent 或用户；
- 运行前怎样识别相关实体档案和情境档案，分别读取哪些最小充分信息，并根据当前状态、目标、标准、历史选择与结果选择本次路线；
- 档案缺失、过期、冲突或与当前任务无关时怎样处理，以及用户当前明确表达优先于历史观察、Agent 推断不得冒充用户偏好的证据纪律；
- 仅针对未被脚本固化的 Agent 控制工作，保留必要业务规则、系统边界和工具指导；
- 执行后怎样把用户选择、调整、拒绝、理由和结果整理为候选事实，继续遵守档案审稿边界；
- 在明确阶段读取哪个可选场景知识文件。

禁止把制作说明、数字资产 ID、用户档案中的具体私有事实、实现细节或确定性的 `workflow_orchestration` DAG 写进 `apc_skill`，也禁止把一条候选路线写成所有用户必须执行的唯一 SOP。长业务规则、模板、示例和详细 SOP 放入场景 Skill 文件，并且只有存在明确读取时机时才从 `apc_skill` 索引。

调用一次 `scene_package_manage(action="create", task_id=<task_id>, name=..., description=..., apc_skill=...)` 创建离线草稿，再创建 Workflow。保存 `scene_package_id`。后续配置失败时用 `action="update"` 修复同一场景包，禁止重复创建。

### 7.5 只补缺失依赖

优先复用现有依赖。只有缺少或确实需要维护 Toolset、Tool Group、FA、Auth Card、普通自定义 TPE 或 Skill 文件时，才使用 `workflow_dependency_manage`。Auth Card 只使用 `create_auth_card`、`update_auth_card` 和 `link_auth_card`；禁止把返回或提供的凭证明文写入检查点和日志。普通自定义或预定义 TPE 才使用 `create_custom_tpe`，Workflow TPE 始终使用 `workflow_tpe_manage`。

可独立调用的 MCP 工具没有可信正式 output Schema 时：

1. 确认调用只读，或者已经获得相应授权。
2. 用代表性输入调用一次 `workflow_dependency_manage(action="test_tool", task_id=<task_id>, tool_group_id=..., tool_id=..., input=...)`。目标 MCP 依赖项目上下文（如 `web_research`）时，额外传已有 Max 返回的加密 `project_id` 或已知正整数项目 ID；`user_id` 不由 Agent 提供，服务端从个人 API 密钥解析并与项目上下文一起注入目标 MCP。与项目无关的工具不要虚构 `project_id`。
3. 只为下游代码起草最小步骤 `_output`。
4. 换一组新输入，再调用 `workflow_dependency_manage(action="test_tool", task_id=<task_id>, tool_group_id=..., tool_id=..., input=<新输入>, expected_output_schema=<候选 Schema>)`；上下文型工具继续复用同一 `project_id`。
5. 检查点只记录契约结论和资产版本。

未经明确授权，不得取样破坏性、对外发布、凭证变更、金融或其他不可逆操作。FA、`file`、`shell` 和 `send_email` 需要 Max 运行时上下文，不能用 `test_tool` 测试。

任何 Workflow create 前都必须完成依赖 Toolset 上线硬门：

1. 根据脚本确定完整 `preload_toolset_ids`，用 `get_asset(asset_type="toolset")` 检查成员、契约和 `is_online`。
2. 对本任务新建的 Toolset，先验证关联完整；其中可独立安全调用的 MCP 工具完成上述 `test_tool` 取样和复验。
3. 无 FAIL 后调用 `workflow_dependency_manage(action="online_toolsets", task_id=<task_id>, toolset_ids=[...])`，再用 `get_asset` 反读确认每个 Toolset 的 `is_online=true`。
4. 任一依赖仍离线就阻断 Workflow create。对任务开始前已存在的离线 Toolset，告知用户并等待处理，不擅自上线。

### 7.6 交付辅助文件并创建全部 Workflow

外部 MCP 接收完整内联脚本，不能读取客户端本地 Codex/CC 路径，也不能读取其他 Max 项目中的路径。

Workflow 引用 `ctx.skill_dir` 时，通过同一工单交付每个辅助文件、模板和静态样例：

1. 调用 `workflow_file_upload(action="prepare", task_id=<task_id>, file_name=..., relative_path=..., size_bytes=...)`。
2. 按返回的 HTTP `PUT` 请求上传准确的本地字节。
3. 调用 `workflow_file_upload(action="complete", task_id=<task_id>, file_name=..., relative_path=..., file_key=...)`，收集 `data.skill_file`。
4. 创建或更新 Workflow 时把收集结果作为 `skill_file_urls=[...]` 传入。

已有可信 HTTPS 文件时，使用 `workflow_file_upload(action="from_url", task_id=<task_id>, file_name=..., relative_path=..., source_url=...)`。更新 Workflow 前重新读取现有文件列表，并发送完整目标集合，因为 `skill_file_urls` 会替换该 Workflow 的 Skill 目录。场景知识文件使用同一交接流程，但传给 `scene_package_manage(..., skill_file_urls=[...], skill_files_mode="merge")`；只有 Workflow 辅助文件挂载到对应 `ctx.skill_dir`。

对每个 Workflow：

1. 按单 Workflow 契约起草内联脚本和根对象 input/output Schema。
2. 调用 `workflow_tpe_manage(action="preview", task_id=..., script=..., input_schema=..., output_schema=..., preload_toolset_ids=...)`。
3. 按返回的工具、字段、行、节点或路径修复全部错误，禁止压制校验。
4. 预览通过后，再次确认本 Workflow 的所有 `preload_toolset_ids` 已通过上线硬门。
5. 只有依赖全部 `is_online=true` 才能调用 `workflow_tpe_manage(action="create", task_id=..., scene_package_id=..., ...)`。
6. 保存返回的 `tpe_id`，后续修复全部使用 `action="update"`。

不得通过拆分或复制 Workflow 绕过可修复的预览错误。每次创建都必须包含根对象 `output_schema`；缺失、非对象或无效 JSON Schema 都是创建错误，即使脚本能够返回值也不例外。

### 7.7 保存一个完整的多 Workflow 对象

全部 Workflow ID 创建并挂载后，按多 Workflow 契约构造一个完整对象并调用：

```text
scene_package_manage(
  action="update",
  task_id=<task_id>,
  scene_package_id=<scene_package_id>,
  workflow_orchestration=<完整对象>
)
```

始终执行整对象替换。`delivery.node_id` 指向的节点必须声明节点级 `sa_handoff`：要求运行时 Agent 读取已提交结果，并通过 `message_user(type="result")` 交付面向用户的自然语言结果；运行时随后使用 `take_over` 阻止兼容自动交付。严格按当前 Hub Schema 编写 `decision_criteria.resume/stop`；这两个名称只是制作期判断条件字段，不是运行时 action。运行时只有 `continue_as_planned`、对紧邻待执行节点提交并通过 Schema 校验的 `revise_and_continue`、以及接管剩余流程的 `take_over` 三种 action，不存在名为 `resume` 或 `stop` 的 action。不要把运行时 action 虚构成新的 orchestration JSON 字段。按 Hub 返回的节点、映射、交付或 `sa_handoff` 错误修复同一完整对象并重新提交。禁止把 DAG 复制进 `apc_skill`，也禁止虚构字段。

### 7.8 对每个 Workflow 做 bubble 跑

对每个 Workflow 调用 `workflow_tpe_manage(action="bubble", task_id=..., tpe_id=..., workflow_input=<valid object>)`，保存返回的 `run_id`。继续用同一 action 和 `task_id + run_id` 轮询到终态，再检查 `steps`、`run_trace`、`coverage`、`unreached_tools`、`final_output` 和 `error`。

开始 bubble 前，确认直连工具使用已授权的代表性输入；邮件、通知、发布、扣费、远端对象创建和正式业务状态写入只能用 `ctx.dry_run` 抑制对应外部副作用。不得用 `ctx.dry_run` 跳过普通工具、Schema 校验、Workspace pipeline 步骤或 FA 桩值引发的失败。

`bubble` 是受信任的 Max 验证运行，不是本地执行。FA 步骤返回 Schema 桩值，不启动真实 FA；普通 MCP 和文件工具真实执行。只有脚本引用 `shell` 时才创建临时服务端沙箱，内部项目/沙箱 ID 和挂载路径不对外返回。把供应商副作用视为真实副作用，涉及破坏或发布时先取得授权。可选全真跑永远不能替代必做的 `bubble` 证据。

### 7.9 根据契约和轨迹验收每个 Workflow

外部制作与 Max 制作遵循同一条“预览 → `bubble` → 语义验收 → 可选全真跑”生命周期。两者工具面可以不同，但都通过 Max 运行时执行并使用同一证据标准。需要完整项目验证时复用检查点中的 `project_id`，不要为每次修复新建项目。

读取 [Workflow 验收检查清单](references/Workflow验收检查清单.md)。CC/Codex 根据当前 Workflow 资产、预览结果和 `bubble` 轨迹自行执行语义验收，不启动或假设存在 Workflow 验收 FastAgent。持续修复原 Workflow 并重跑 `bubble`，直到证据满足契约。

### 7.10 按最终 Workflow 契约制作并发布业务界面

仅当业务界面决策为 `required`，或目标场景包已有业务界面时执行本步骤。完整读取 [业务界面制作契约](references/业务界面制作契约.md)，并以当前场景包、当前 Workflow 和当前 `workflow_orchestration` 的反读结果作为编码契约。业务界面不是独立资产：它必须绑定同一个 `scene_package_id`，在同一工单内制作、验证和发布。

必须在全部受影响 Workflow 完成 Preview、bubble 和单体验收后才冻结界面契约。若后续修改 Workflow input/output Schema、slug 或顶层编排入口，原界面验收立即失效，必须重新生成契约、验证、上传和部署。

把 `scene_package_ui_bundle(action="download_template", task_id=<task_id>)` 作为业务界面开发的强制初始化入口，必须先调用，不能用通用 `init_project`、Git 克隆、历史模板或手工新建目录替代。按返回的 `data.download_url` 在有效期内把压缩包下载到当前可写工作区；校验 HTTP 成功、实际字节数等于 `data.size_bytes`、文件类型和归档成员安全后再解压。以解压后包含 `goalfy-app.json` 的目录作为唯一开发目录，完整读取根 `AGENTS.md`、`README.md`、`schema/README.md` 和 `src/sdk/docs/README.md` 后才能修改业务代码。详细返回字段、落盘、校验和失败恢复规则见业务界面制作契约。

模板源码、其中的 SDK 文档和线上工具 Schema 是制作期事实源；仓库分支或历史模板只能用于理解。按契约完成业务代码、真实 Schema 快照、manifest、检查和示例清理后，计算实际源码包大小和 SHA256，再依次执行 `prepare_upload → HTTP PUT → complete_upload → deploy`。`deploy` 未返回终态时，用同一 `deployment_id` 执行 `status`，禁止重复上传或重复创建场景包。

读取 [业务界面验收检查清单](references/业务界面验收检查清单.md)，确认源码、运行契约、SDK 边界、异步状态和部署结果。成功后用 `scene_package_ui_bundle(action="get", ...)` 反读当前包及已激活地址，并把界面契约摘要、源码 SHA256、部署 ID 和验收裁决写入工单；不记录预签名下载或上传 URL。

### 7.11 验收完整场景包

读取 [场景包验收检查清单](references/场景包验收检查清单.md)，把场景包 Skill、候选路线与选路节点、业务档案使用规则、依赖闭包、每个 Workflow 契约、`workflow_orchestration`、交付映射、Agent 交接和业务界面决策作为一个整体检查，不启动或假设存在场景包验收 FastAgent。至少验证：同一终点存在多种合理路径时，`apc_skill` 没有把某一路线强制给所有用户；相关档案的差异会实质改变路线、参数、优先级或解释；档案缺失和 Agent 推断不会被伪装成用户事实。多 Workflow 先确认每条 Workflow 已完成 bubble 和单体验收；业务界面标记为 `required` 时，还必须已有当前契约对应的界面验收与部署证据，再做整包接缝与业务语义验收。把简洁的方案挑战、Workflow、业务界面和场景包验收结论写入工单。

场景包验收通过后，对每个 Workflow 分别询问用户是否执行 FA 全真跑并记录决定。用户跳过时继续流程；只有用户批准覆盖所选场景路径可能执行的全部 Workflow，7.14 才能启动真实 Max 项目。

### 7.12 在归属层修复问题

- 线上工具参数或返回不匹配：重读资产，修复调用或步骤契约。
- Workflow 预览或运行时失败：更新原 Workflow。
- Hub orchestration 失败：更新同一个完整 `workflow_orchestration` 对象。
- 运行时工具缺失：核对调用名、Toolset 成员、在线状态和 preload 依赖。
- 输出文件缺失或不可信：检查 TaskAgent 证据，修复文件来源或生成步骤。
- 业务界面契约与当前 Workflow 不一致：修复同一界面源码包并重新验证和部署；若根因在 Workflow，先修复 Workflow 并使旧界面验收失效。
- 当前模板缺少新编排所需的顶层 Manifest/Submit/State 能力：不得用单 Workflow `workflow.run` 假装执行整包编排；记录宿主能力缺口并停止该界面发布，场景包仍按已确认的无界面回落策略处理。
- 业务判断不确定：停止强行固化 Workflow，把该阶段还给 Agent。
- 基础设施错误：只有返回错误明确可重试且操作幂等时才重试。

### 7.13 发布已验证场景包

发布前重读场景包，确认引用资产存在、每个 Workflow 都有当前 input/output 契约、多 Workflow 场景包已保存一个有效的 orchestration 完整对象且交付节点包含最终 `sa_handoff`、交付文件使用 Workspace 路径、工单中存在简洁验证证据。业务界面决策为 `required` 时，确认当前源码 SHA256 已部署成功、绑定同一场景包且界面契约未因后续资产修改过期；决策为 `not_required` 时记录回落现有对话界面。确认 `apc_skill` 仍对应最终终点和里程碑，列出候选路线、业务档案选路规则、所有必需业务输入和 Agent/用户判断，不含数字资产 ID、具体私有档案事实、唯一固定路线或复制的 DAG，并且为每个上传的场景 Skill 文件提供明确读取时机。

资产变更导致草稿过期时，先调用 `scene_package_manage(action="update", task_id=<task_id>, scene_package_id=<scene_package_id>, apc_skill=...)`。随后调用 `scene_package_manage(action="online", task_id=<task_id>, scene_package_id=<scene_package_id>)` 并重读线上场景包。

### 7.14 按需运行一个真实 Max 业务项目

只有用户批准所选场景路径可能执行的每个 Workflow 都做全真验证，或明确要求完整业务项目证据时，才执行本步骤。批准未覆盖完整路径时不得启动项目；记录 `full_validation_skipped` 和剩余 FA、内容、外部副作用盲区，然后继续关闭工单。

获得批准后，在发布完成后调用 `manage_goalfymax_project(action="run", task_id=<task_id>, scenario_package_ids=[...], workflow_input=<object>, ...)`。显式传入 `workflow_input={}` 会触发确定性 C2 场景包；省略该字段会启动普通 Agent 对话。对于编排场景包，Agent 可以收集顶层输入，再通过内部 orchestration 启动工具显式启动同一 C2。与 `bubble` 不同，这会启动真实 Max 项目及真实 FA 和运行时行为。

用返回的 `project_id` 执行 `wait` 或 `status`。只有 Max 返回 `needs_input=true` 时才用 `reply` 或 `confirm`；资产更新后需要新尝试时才用 `send`。轮询或小修复不得反复新建项目。

### 7.15 全真跑后检查真实日志和交付物

只有 7.14 实际执行后，才用相同 `task_id` 和 `project_id` 调用 `get_project_execution_logs`：`summary/detail` 用于执行证据，`outputs/download/bundle` 用于真实交付物。临时 FA 文件和内部挂载路径不得出现。项目整体完成不代表目标 Workflow 和交付物通过。跳过全真跑时，禁止虚构 `project_id`、项目结果、日志结果或交付物结果。

### 7.16 关闭工单

写入最终检查点，包含资产 ID、`bubble` 结论和业务界面决策；已发布界面还要记录源码 SHA256、deployment_id、激活地址和验收裁决。检查点必须二选一：记录已批准的真实项目结果与交付摘要，或者记录 `full_validation_skipped`、用户决定和剩余盲区；不得包含凭证、预签名 URL 或原始日志。调用 `workflow_task_manager(action="complete", task_id=<task_id>)`。跳过全真跑时不得声称存在全真验证证据；缺少必做 `bubble` 证据、业务界面必需证据或审计落库时不得声称可审计完成。

## 8. Common Issues and Recovery

| 现象 | 根因判断 | 恢复方式 |
|---|---|---|
| 工具缺失、action 不存在或参数被拒绝 | Skill 文档与线上 MCP 版本不一致，或 MCP 未加载 | 重新读取实时 `tools/list`；确认连接后按当前 Schema 修改调用，不新增平行工具名 |
| 返回未认证 | Bearer 环境变量未注入、已失效或插件未重新加载 | 检查 `SCENE_CREATOR_API_KEY` 的连接配置；更新凭证后重载 MCP，不把密钥写入对话或文件 |
| Preview 失败 | 脚本、Schema、工具声明或文件来源不满足制作契约 | 根据服务端精确错误更新原 Workflow 草稿；需要正反例时读取匹配的诊断 topic |
| bubble 显示 success 但验收不通过 | 只证明本次路径执行成功，FA 内容、未触达分支或业务语义仍无证据 | 读取轨迹和覆盖率，按 Workflow 清单裁决；修复后重跑同一 Workflow |
| 模板或源码包下载失败 | 短链过期、HTTP 失败、大小不符或归档不安全 | 重新请求当前短链并从下载校验开始；不在旧文件上拼补 |
| 部署超时或状态未知 | 发布任务仍在运行，或状态查询中断 | 保存并复用同一 `deployment_id` 查询 `status`；不重复上传或重复部署 |
| 真实项目等待输入 | Max 明确返回 `needs_input=true` | 复用同一 `project_id` 发送 `reply` 或 `confirm`；普通轮询不创建新项目 |
| 本 Skill 与服务端契约冲突 | 本地 Skill 版本落后于 MCP/Hub/Runtime | 以实时 Schema 和服务端校验为准完成本任务，同时报告需要更新 Skill 的具体段落 |
