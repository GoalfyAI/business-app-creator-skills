# Studio 制作与按需上线

## 适用场景

受信宿主实际公布 Studio 目标绑定与方案工具时启用；参数读实际清单和当前合同。产品名、目录或模型自报不是能力证明。方案确认只授权制作，上线沿原对话问答和现有 MCP；没有新发布按钮、向导或自动上线状态机。需要的检查能力缺项时如实报告，不伪造工具或手写状态。

## 规则

### 原生工具与验收声明 v2

只有原生工具清单实际提供以下两个工具时，使用本节；参数以当前工具 JSON Schema 为准。工具的会话、账号、目标、native turn/call 身份由受信宿主注入，不能在 arguments 中自行提交。工具不是外部 MCP 平台的新接口。

1. `studio_write_proposal({version, files:[{name, content}]})`：提交 UTF-8 方案文件，必须包含 `index.html` 和下节定义的 `acceptance.json`，最多 64 个文件、合计 48 KiB（符合当前原生工具单次输入上限；宿主 artifact 存储的 8 MiB 限制不表示工具可一次提交同等大小）。`name` 仅为 artifact 内的相对资源名，禁止绝对路径、`..`、业务源码或命令。宿主分配真实目录、写入文件并计算摘要；原生同一次调用幂等，修改内容必须新版本、新调用。返回后在同一轮输出业务方案说明；宿主根据原轮次内真实完成消息的位置关联确认卡，不读取文字关键词造状态。写入回执只证明方案已保存，不证明确认卡已显示。
2. `studio_read_creation({})`：读取当前方案、原生制作确认和历史交付结果；只核对原操作，不触发检查、部署、定版或发布。只有 `proposal.status=confirmed`，当前 `version`、`digest` 与 `confirmationCommandId` 的精确原生 accepted receipt 匹配，才开始实际工程；draft、旧版确认、工具显示方案已生成或卡已提交均不算确认。业务工程继续在原会话沿本 Skill 的初始化、SDK、能力与测试规则完成。
工程准备好并不自动上线。编辑、批注、撤销、本地检查、轮次结束、只读查询和重启均不派发部署或上线。旧 `studio_deliver` 已退役，不再调用；若旧记录仍在，保留原候选和操作身份，只读核对，不借新版本、新 draft 或新 operation 绕过 unknown。

面向开发者只说明业务范围和当前实际状态，例如「方案已保存，等待确认」。尚未通过 `studio_read_creation` 读到当前方案的卡片时，不说「本条消息已挂确认卡」或让用户点击尚未核实的按钮。`version`、`digest`、`status`、`confirmationCommandId` 和验收声明 v2 用于内部核对，不逐条列入用户说明。确认入口缺失或读取失败时，保留原方案并说明具体受阻；不重复写入方案，不用普通「可以」、通用提问或模型总结替代原生确认。

宿主的角色、CRUD、TPE 与权限检查来自受信检查器。模型不得提供“passed”字段、证据对象、Token、浏览器脚本或任意 URL 来替代。真实检查开始前保存意图，未知时只查询原检查回执。历史 `delivery.status=published` 仅表示原发布证据匹配，不是新一轮发布授权；当前正式版本、在线页 ready 与真实业务仍分别核实。

缺少或无效的 `acceptance.json` 会在方案阶段拒绝保存和挂确认卡；旧方案缺声明或仅有 v1 声明时保留原文件，提交完整的新版本并等待新的原生确认，不在执行时补批准范围。工具失败若返回 `code/stage/retry:false`，按该固定诊断报告具体受阻；读取工具失败不再循环调用读取，写入结果未知不重发。不得绕过为直接写宿主状态文件。

### 绑定可判定验收内容

`acceptance.json` 随方案提交并纳入同一摘要，内容是业务要求，不是检查结果。方案页用业务语言展示相同的使用角色、保存/刷新回读与适用修改/还原、每条业务路线；不得用隐藏声明减少用户确认的范围。结构如下：

```json
{"version":2,"roles":["owner"],"crud":[{"id":"record-save","description":"管理员登记测试记录，刷新后仍可读取相同内容","lifecycle":"create_read"}],"tpes":[{"id":"main-route","description":"运行已确认的主要业务路线并核对最终结果"}]}
```

`crud` 每项必须在确认前明确 `lifecycle`：`create_read` 为保存及刷新回读（2 阶段），`update_read` 另含单向修改及刷新回读（4 阶段），`restore_read` 另含恢复原值及刷新回读（6 阶段）。逐项与可见业务方案一致；缺失、旧 v1 或含糊描述不能由工程自行推断，须提交 v2 新方案并重新确认。工程保留相同 ID 和 lifecycle，实际探针阶段必须精确对应，不能减少或增加批准范围。

`roles` 仅列方案实际需要的宿主角色（`owner/edit/view` 的非空集合）。仅当前管理员使用时可以是 `owner`；需要协作者的方案必须保留相应角色。只用当前账号真实拥有的权限，不能假造用户或把 Passport 登录角色当应用角色。现有 owner 预览不能证明 edit/view；缺少实际身份时明确阻断，不缩减方案。业务自定义角色及其规则仍逐项列入验收要求，不能仅凭宿主角色通过就声称业务角色规则通过。

工程完成后在实际应用根生成 `studio.acceptance.json`，随源码冻结。保留相同角色和全部 CRUD/TPE 项 ID，填入已确认 `proposalDigest`，不要修改原方案来写工程状态：

- 固定顶层为 `version:2, proposalDigest, roles, steps, crud, tpes, network`；不加 `passed`、证据对象或任意脚本。单文件不超过 48 KiB。
- `steps` 最多 100 条，只接受 `fill(selector,value)`、`click(selector)`、`wait(selector,text?)`、`read(selector,expectedText)`、`reload`、`screenshot`。动作以 JSON 对象 `{action,...}` 表达。截图须有宿主现有许可。
- `crud` 每项为 `{id,lifecycle,writeStep,reloadStep,readStep}`，lifecycle 原样取自已确认声明；步骤为零基序号，按 click → reload → read 的顺序绑定真实 UI。最多 32 项。
- `tpes` 每项为 `{id,scenarioPackageId,tpeId,submitData:{business_id,form_id,orchestration_id,formdata}}`，最多 64 项。物理 ID 从已创建的真实场景包/路线读取，formdata 只放有界 JSON 标量。必须覆盖候选实际挂载包的完整适用 TPE 集；不能用 null 隐去真实场景版本，也不自造成功记录。平台要求的场景包及编排型 TPE 仍须真实准备并回读版本，但依赖存在不代表有适用业务路线。已确认纯 CRUD 且 `tpes=[]` 时保持空集合，不为通过宿主检查增加用户路线，也不伪造 TPE 通过；已确认非空集合不能删项或缩成空集合。
- `network` 定义真实后端回读谓词，格式见下。前端正常通过 `sdk.api.request` 发请求，宿主只观察实际 Max api-proxy 网络响应；不会替模型执行任意 URL/API，也不接受 DOM 文字作为持久证据。候选的 `frontend/schema/api/<operationId>.yaml` 必须先定义实际请求/响应合同；路径、字段和预期按它填写。

最小网络声明示意（须替换成该应用实际 API、字段及步骤；这里的保存 click 位于步骤 1，刷新位于步骤 2，之前的 fill 填入同一测试标记）：

```json
{"marker":"studio-test-0123456789abcdef","probes":[
  {"id":"create","caseId":"record-save","step":1,"phase":"create","request":{"method":"POST","path":"/records","body":{"/name":"studio-test-0123456789abcdef"}},"response":{"recordPath":"/record","keyPath":"/id","values":{"/name":"studio-test-0123456789abcdef"}}},
  {"id":"read","caseId":"record-save","step":2,"phase":"read","recordFrom":"create","request":{"method":"GET","path":"/records/{{record}}","body":{}},"response":{"recordPath":"/record","keyPath":"/id","values":{"/name":"studio-test-0123456789abcdef"}}}
]}
```

每候选生成新的 `studio-test-` 加 16–80 位字母数字/下划线/短横线标记，只写隔离开发工作集内的授权测试记录。`body` 是待观察请求体的 JSON Pointer → 预期标量映射，不是由宿主发出的写请求；`values` 相对真实响应 `data` 中 `recordPath` 选出的记录检查字段，`keyPath` 指向其稳定主键。读请求仅 GET，`query` 可给 SDK 已编码的完整查询串；路径/查询只允许 `{{record}}` 引用 `recordFrom` 的真实主键，不支持表达式。列表接口可用真实记录位置，如 `/items/0`，但必须同主键和标记匹配，不能把首条任意记录算通过。

每项严格按已确认 lifecycle 列探针：`create_read` 仅列 `create,read`。`update_read` 已确认单向修改（例如仅归还、不撤销归还）列 `create,read,update,read_updated`，不得为凑阶段增加撤销业务；`restore_read` 方案有修改与还原时完整列 `create,read,update,read_updated,restore,read_restored`，不得降成四阶段。每次写用 click，每次后端回读绑定一次新的 reload。创建之后各项 `recordFrom` 都绑定该项原 create，步骤严格递增；更新/还原必须走实际 POST/PUT/PATCH 写接口。创建与首次回读的字段谓词一致；四/六阶段均检查同一组字段，修改后至少一项不同且测试标记在原字段保持不变，修改回读与修改响应一致；六阶段还原响应与最后回读都恢复创建时的原值。响应须有可判定记录键与字段；缺协议时说明具体缺口，不能改成空谓词、只看 HTTP200 或直接填回执。每次实际请求只能对应一个探针，原 request_id 不可跨探针或用例复用。登记、查询、归还等多项验收须安排各自实际请求步骤和测试记录，不让同一步同一请求命中多项。宿主保存原 request_id、候选及响应摘要；超时/未知不重放写入。

### 方案先于工程

先通过宿主 artifact 能力在已验证项目 `runtime/studio-v1/proposals/<artifactId>/` 生成方案；路径由宿主分配，模型/网页不提交任意文件路径。未确认当前方案前不 scaffold:init、不建业务资产、不改业务源文件。方案版本、内容摘要、选择结果与原生 confirmationCommandId 绑定；只认当前原生会话的 accepted receipt，不凭“已发送”、HTTP200 或模型总结确认。改动方案后旧确认失效。业务确认不替代原生权限审批。

确认后初始化工程并沿现有脚手架、SDK、模板和能力流程制作。右侧只有方案、演示预览、在线预览；不生成发布按钮或阶段进度面板。演示显示当前真实 React/Dev Host，不要求先生成旧完成副本；不把 HTML 原型当生产智能应用。

### 候选与真实检查

本地制作按已确认范围完成能力制作、冒泡与验证。需要草稿部署预览时先核对该范围已获授权；需要上线时按下节取得本次明确同意，再由 Agent 调现有 MCP。以下证据要求继续适用；宿主若实际提供候选检查能力可按其合同使用，否则记录未验证项并走已有人工验收路径，不伪造宿主工具。

- 固定本次待部署候选：当前目标/账号/环境/原生会话、方案确认、源内容摘要、实际上传 tar 的 SHA256/大小、Skill/模板/场景包/数据模板版本和精确 task/draft 身份。部署前 deploymentId 为 null，不造空编号。
- 在冻结副本完成 `npm run verify:release`，只上传该次生成的原字节。失败不上传；不能用单独 pack 或重打包后的新字节配旧 hash。继续编辑的源码属于下一候选，不能污染正在检查的候选；冻结内容/依赖变化则旧证据失效。
- 在已明确授权的预览或上线范围内，由 Agent 沿现有 business_ui_bundle ship/upload/status 和 business_ui_manage get 记录原 bundle/deployment/hash。回执未知先只读查询；不能去掉 deployment_id 再 ship“试一下”，无 ID 的 ship 可能新部署。
- 宿主检查器只执行受限 click/fill/wait/read/screenshot/reload 检查能力，绑定精确候选、真实账号/角色、开发工作集与宿主 frame。此能力不是任意浏览器/JS/CDP/URL 接口，不取得 Token，不借用开发者登录会话。
- 对可判定验收项取得保存→刷新→再读及适用修改/还原记录。读写应用库的真跑使用 business_ui_data_space="workspace"；保留真实 route_runs succeeded、workflow_trace、每条 TPE verify(project_id) 和实际数据回读。HTTP200、页面 load、截图、本地 Mock、模板冒烟均不能单独算真实业务通过。
- 只写隔离开发工作集和已授权测试数据。费用、对外发送、正式用户数据等超出已有授权的动作按原对话处理。权限、身份、未验证项或检查结论不完整时不发布；不得写成开发者已亲自试用或伪造 checkpoint。

### 按需上线与未知恢复

需要上线时，在当前原生对话说明本次应用和修改范围，询问是否上线；只有用户明确同意本次范围才由 Agent 调用现有 MCP。用户已明确要求本次上线时直接沿用，不重复询问。方案确认、编辑批注完成、检查通过、上一版同意或历史自动授权都不替代本次上线意愿；未答复、拒绝、含糊或接收未知均不发布。不是每次改动都要上线，用户可保留本地制作结果。答复后目标或内容实质变化需先说明差异。

按当前工具 Schema 使用 business_ui_bundle 的 ship/status、business_ui_manage 的 finalize/get/resolve 等既有能力，精确使用本次 task/draft/deployment 身份、原包字节和实际版本；满足适用验收后才定版。目录发布同样复用当前原会话实际公布的 MCP 能力；未暴露动作时如实报告具体缺口，不编造 action=publish，不新造平台接口，也不回退宿主自动 HTTP 发布。

部署、定版、目录当前 published release、正式 ready、真实 CRUD 分别记录。只有 finalize 或历史 release 不等于当前正式可用。现有平台读回缺少 operation_id 或源码 hash 时，用保存的原候选证据关联，不凭文本推断。unknown 只查原记录，不换 operation/draft、不重放写请求；没有证据继续未知。已有原操作只读恢复，未派发的旧自动步骤停止。

旧卡/请求/摘要/receipt 原样保留，旧 allowedActions/requested/phase 不重新获得上线效力。结单门、角色、真实业务证据要求保持；无需新授权数据库或专用发布确认卡。

### 正式在线预览

在线预览只用已发布正式宿主入口，不显示草稿部署或只有 finalize 的版本；仍允许正常业务 CRUD，禁止设计编辑桥。V2 制作、批注、未答复、拒绝上线、失败或结果未知时保留 V1 已加载实例。只有本次明确同意且实际正式发布的新版本才进入既有更新发现。应用报告 dirty 时等保存，clean 时可自动切换，unknown 时让用户确认已保存；新版本实际 ready 前保留旧 iframe 和输入，新加载/续期失败继续旧实例。切页不重载，不抢用户当前分页。账号/权限失效仍按宿主隔离规则撤销。

报告区分机器检查、开发者人工操作、本地测试、真实宿主、目录发布和正式运行证据。没有发生的事不写通过，不把材料检查或 Skill 静态测试当行为评测。

## 常见错误

- 把品牌名或模型文字当可信能力回执，跳过当前方案确认。
- 把 finalize、历史 release、HTTP200 或机器检查写成当前正式可用、开发者已试用。
- 丢 deployment_id 后重新 ship，或换 operation_id 重复未知发布。
- 新页面尚未 ready 就销毁旧实例、丢掉未保存输入。

## 相关工具与契约主题

宿主实际公布的方案/候选/受限检查能力与现有 MCP 上线能力（参数读其实际契约）；现有 business_ui_bundle、business_ui_manage、manage_goalfymax_project、otpe_manage、get_project_execution_logs。不得自造工具、平台接口或按 operation_id 查询接口。
