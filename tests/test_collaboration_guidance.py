from pathlib import Path
from zipfile import ZipFile

import pytest

ROOT = Path(__file__).parents[1]
SURFACES = (
    "skills/business-app-creator",
    "claude-code/skills/business-app-creator",
    "codex/skills/business-app-creator",
    "generic",
    "manus/skill",
    "generic/business-app-creator-generic.zip",
    "manus/business-app-creator-skill.zip",
)


@pytest.fixture(params=SURFACES)
def read_skill(request):
    """从唯一源、四个平台和两个安装包读取实际分发的 Skill 文件。"""
    surface = ROOT / request.param

    def read(relative: str) -> str:
        if surface.suffix == ".zip":
            with ZipFile(surface) as archive:
                return archive.read(relative).decode("utf-8")
        return (surface / relative).read_text(encoding="utf-8")

    return read


def _section(text: str, heading: str) -> str:
    return text.split(heading, 1)[1].split("\n### ", 1)[0]


def test_entry_routes_by_collaboration_role(read_skill):
    """先识别任务时按 business_ui_manage 返回的 role 分流，红线写明协作者不上线、不发布。"""
    skill = read_skill("SKILL.md")
    routing = skill.split("## 6. 任务路由", 1)[1].split("## 7.", 1)[0]
    assert "`role` 分流" in routing
    assert "`viewer`（只读协作者）：不管要做什么都走 [tasks/诊断.md](tasks/诊断.md)，不写任何东西" in routing
    assert "`editor`（编辑协作者）：改动按 [tasks/修订.md](tasks/修订.md) 的协作者做法" in routing
    assert "⑤ 改为提请属主上线" in routing
    assert "待接受的邀请时按 [reference/多人协作.md](reference/多人协作.md)「先认角色」告诉他怎么接受" in routing
    roles = _section(read_skill("reference/多人协作.md"), "### 先认角色")
    assert "分享兑换入口输入站内信里的分享码接受邀请" in roles
    red_lines = skill.split("## 4. 红线", 1)[1].split("## 5.", 1)[0]
    assert "上线、发布、下线、删除、再分享应用只有属主能做" in red_lines
    request = _section(read_skill("reference/多人协作.md"), "### 提请属主上线")
    assert "编辑协作者不 `finalize` 应用，⑤ 改为提请属主上线" in request
    assert '`business_ui_manage(action="request_finalize", task_id, business_ui_id)`' in request


def test_viewer_route_stays_read_only(read_skill):
    """只读协作者不派生草稿、不申请写连接、不写 SQL、不跑写流程、不用 dataset_read 读开发库。"""
    route = _section(read_skill("reference/多人协作.md"), "### 只读协作者能读什么")
    diagnose = read_skill("tasks/诊断.md")
    assert "建 read 工单（只读协作者也是 read 工单）" in diagnose
    assert "只读协作者不做的：派生任何草稿" in route
    assert '`dataset_template_workspace(action="connect", mode="reader")`' in route
    assert "`connect` **必须**显式带 `mode=\"reader\"`" in route
    assert "TEMPLATE_WORKSPACE_WRITER_FORBIDDEN" in route
    assert "`connect` 申请写连接" in route
    assert "执行写数据的 SQL 或 DDL" in route
    assert "`ship`、部署、冒泡、真跑这类写流程" in route
    assert "调 `finalize` 或 `request_finalize`" in route
    assert "用 `dataset_read` 读应用开发库" in route
    assert "告诉他自己能查看哪些内容" in diagnose
    assert "改动要请属主或编辑协作者做" in diagnose


def test_editor_route_derives_own_drafts_and_requests_finalize(read_skill):
    """编辑协作者只改自己的草稿、change_note 必填、各层自己上线后往上更新引用，④ 部署自己的草稿、页面在本机版上验，⑤ 提请属主上线。"""
    text = read_skill("reference/多人协作.md")
    route = _section(text, "### 编辑协作者的草稿与各层资产")
    assert "`change_note` 必填" in route
    assert "别人创建的草稿不改、不拿来部署" in route
    assert "工具组 → 工具集或 FA → 场景包路线 → 应用挂载" in route
    assert "再自己上线这一层（`finalize_asset_version_online`" in route
    shared = _section(text, "### 共享开发工作集")
    assert "属主绑定在应用上的共享工作集" in shared
    assert "模板当前版本 `template_version`" in shared
    assert "`extract` 抽新版本时带 `expected_base_version=<记下的模板版本>`" in shared
    assert "`extract` 被基线类错误拒绝时按 [报错对照.md](报错对照.md)「应用上线与数据模板」处理" in shared
    assert "TEMPLATE_BASELINE_CHANGED" in _section(text, "### 协作相关报错")
    steps = _section(read_skill("tasks/修订.md"), "### 编辑协作者怎么改")
    assert "④ 和属主一样由你按 [../stages/4-试用验收.md](../stages/4-试用验收.md) 逐条测" in steps
    red_lines = read_skill("SKILL.md").split("## 4. 红线", 1)[1].split("## 5.", 1)[0]
    assert "页面验收只在应用根 `npm run dev:restart` 起的本机版上用无头浏览器做" in red_lines
    assert "部署授权按 [../SKILL.md](../SKILL.md)「红线」" in steps
    assert "`workspace` 真跑前先把自己的草稿 `ship` 到 `success`" in steps
    assert "只有协作者身份才看得到的表现记「未测」" in steps
    limits = _section(text, "### 预览、费用与限制")
    assert "只有协作者身份才看得到的表现，按 [../stages/4-试用验收.md](../stages/4-试用验收.md)「2.4 逐条判定」记「未测」（平台登录身份）" in limits
    assert "登录" not in steps
    request = _section(text, "### 提请属主上线")
    assert '`business_ui_manage(action="request_finalize", task_id, business_ui_id)`' in request
    assert "`draft_asset_id` 可以省略" in request
    assert "`note` 是给属主的补充说明" in request
    assert "「已提请，等属主上线。属主上线后这一版成为属主的正式版，发不发布由属主决定；" in request
    assert "只说已提请，不说已上线，也不为此去 `finalize`、`resolve`" in request
    launch = read_skill("stages/5-上线.md")
    assert "`editor` 在 2.3 改为提请属主上线" in launch
    assert '- `editor`：改为 `business_ui_manage(action="request_finalize")` 提请属主上线' in launch
    assert "做法、说法与报错见 [../reference/多人协作.md](../reference/多人协作.md)「提请属主上线」；不调 `finalize`、`resolve`" in launch


def test_page_items_use_local_headless_browser_not_online_addresses(read_skill):
    """需求责任人 10-27：普通宿主和 Studio 下 AI 都不用浏览器访问线上地址，页面条目在本机版上用无头浏览器验，线上才能验证的标「未测」，不请开发者代测。"""
    skill = read_skill("SKILL.md")
    red_lines = skill.split("## 4. 红线", 1)[1].split("## 5.", 1)[0]
    assert "**禁止**用任何浏览器（含宿主内置浏览器、Playwright）打开正式入口、登录页、在线预览或容器地址" in red_lines
    assert "页面验收只在应用根 `npm run dev:restart` 起的本机版上用无头浏览器做" in red_lines
    assert "**禁止**请开发者在在线预览、演示预览或其他页面代测" in red_lines
    workspace = read_skill("reference/开发者中心与工作区.md")
    local = _section(workspace, "### 本机版页面验收")
    assert "只打开本机版输出里的本机地址（`127.0.0.1` 或 `localhost`）" in local
    # 裁决 D35/总原则 4：不判断环境改为「开工时问开发者在哪个站点开发，答案原样填进参数」，其余文件不写环境判断
    assert "不传 `--environment`：宿主（Studio）提供了环境，脚手架自己读。只有它报「缺少环境」时，才问开发者在哪个 GoalfyMax 站点开发" in skill
    assert "用 Playwright 无头 Chromium 打开 Dev Host 地址" in local
    judging = read_skill("stages/4-试用验收.md").split("### 2.4 逐条判定", 1)[1].split("\n### ", 1)[0]
    online_only = judging.split("**「未测」只用于下面几类**", 1)[1]
    for fact in ("| 依赖平台登录身份", "「只有线上才能验证：平台登录身份」", "| 依赖真实宿主桥接", "「只有线上才能验证：真实宿主桥接」",
                 "其余部分结论「未测」、证据「无」，原因照下表原文写", "测不了的不请开发者代测",
                 "以后开发者自己怎么看", "发布后在正式入口看"):
        assert fact in online_only, fact
    assert "④ 有「未测」条目时单列" in read_skill("stages/5-上线.md")
    studio = _section(workspace, "### Studio 宿主")
    assert "④ 怎么验收" in studio and "和其他宿主相同" in studio
    assert "宿主提供的受限检查能力的机器结果可以作补充，和你在本机版上的操作分开记，不代替页面条目的本机版操作" in judging
    assert "/preview" not in studio
    for name in ("SKILL.md", "stages/4-试用验收.md", "stages/5-上线.md", "reference/开发者中心与工作区.md", "reference/多人协作.md",
                 "checklists/验收清单.md", "design/交接消息.md", "design/验收报告与上线结果.md", "design/方案页.md",
                 "design/开发文档/PRD.md", "design/开发文档/方案.md", "design/开发文档/制作进度.md", "design/开发文档/验收报告.md"):
        text = read_skill(name)
        assert "需要你在在线预览里试" not in text and "开发者未试" not in text, name
        for retired in ("登录好了", "launch(headless=False)", "--isolated", "启动浏览器", "用浏览器验收", "goalfymax.goalfyai.cn",
                        "goalfymax.pre.goalfyai.cn", "/business-ui/<应用 ID>/preview`（打开登录者本人"):
            assert retired not in text, (name, retired)


def test_resume_reads_pending_finalize_and_stale_baseline_first(read_skill):
    """接续先读待上线清单与基线过期状态，过期时按下载、合并、重新派生、部署、再提请的顺序处理。"""
    resume = read_skill("tasks/接续.md")
    assert "待上线的提请和自己草稿的基线是否过期，处理完再接本轮改动" in resume
    assert "协作者草稿基线过期：先按 [修订.md](修订.md)「基线过期的合并」处理" in resume
    merge = _section(read_skill("tasks/修订.md"), "### 基线过期的合并")
    steps = ["`business_ui_bundle(action=\"download\")`", "用 git 合并", "重新派生自己的应用草稿", "`ship` 到新草稿", "再次提请属主上线"]
    positions = [merge.index(step) for step in steps]
    assert positions == sorted(positions)


def test_owner_collaborator_changes_require_confirmation(read_skill):
    """属主加人改档移人前先确认，编辑档只给指定账号，未接受邀请时提示到分享兑换入口接受。"""
    owner = _section(read_skill("reference/多人协作.md"), "### 属主：加人、改档、移除")
    assert "collaborator_action=…" in owner
    for param in ("`visibility=\"specified\"`", "`recipient_accounts=", "`role=\"viewer\"`", "`collaborator_user_id`"):
        assert param in owner
    assert "开发者明确同意后才带 `confirm_collaborator_change=true` 执行" in owner
    assert "编辑档只给指定账号" in owner
    assert "分享码模式只能发只读档" in owner
    assert "分享兑换入口输入分享码接受" in owner


def test_borrowed_assets_and_preview_limits(read_skill):
    """借来的资产说明分享方与克隆办法；费用只写现状；协作预览不能充值、旧模板需重建。"""
    text = read_skill("reference/多人协作.md")
    borrowed = _section(text, "### 借来的资产")
    assert "把它分享给属主的人" in borrowed
    assert "`clone_asset` 克隆到自己名下再换引用" in borrowed
    assert "找分享方修改" in borrowed
    created = _section(text, "### 协作中新建或克隆的资产")
    assert "**必须**显式带 `collaboration_business_ui_id=<应用家族 ID>`" in created
    for tool in (
        "`create_fast_agent`", "`create_toolset`", "`create_tpe`", "`otpe_manage` 的创建", "`clone_asset`",
        "`register_and_refresh_tool_group` 的创建模式", "`upload_and_register_tool_group`", "`import_skill_package`",
        "`create_derived_scene_package`", '`scene_package_manage(action="create")`',
    ):
        assert tool in created
    assert "资产落在属主名下" in created
    limits = _section(text, "### 预览、费用与限制")
    assert "BUSINESS_UI_RECHARGE_OWNER_ONLY" in limits
    assert "BUSINESS_UI_COLLAB_PREVIEW_SCAFFOLD_OUTDATED" in limits
    assert "只写这个现状，不写成「协作者自付」或「属主承担」这类长期承诺" in limits


def test_setup_derivation_requires_change_note(read_skill):
    """setup 需要派生草稿时同样要带 change_note。"""
    deploy = read_skill("reference/部署与版本.md")
    # 裁决 R10：首次 setup 建身份不强制 change_note；派生草稿带 change_note
    assert "应用建草稿（含 update、对已有应用的 `setup`、`ship` 自动派生）带 `change_note` 写这次改了什么，首次 `setup` 建应用身份不用带" in deploy
    drafts = _section(read_skill("reference/多人协作.md"), "### 编辑协作者的草稿与各层资产")
    assert "`update`、`setup`、`ship` 需要从上线版派生草稿时同样要带" in drafts
    errors = read_skill("reference/报错对照.md")
    rows = [line for line in errors.splitlines() if line.startswith("| `CHANGE_NOTE_REQUIRED`")]
    assert len(rows) == 1 and "带 `change_note` 重调" in rows[0]


def test_template_extract_requires_baseline_for_every_route(read_skill):
    """给已有模板抽新版本一律带 expected_base_version，属主路线与报错对照同样写明。"""
    template = read_skill("reference/数据模板.md")
    assert "给已有模板出新版本时传 `template_id`，并带 `expected_base_version`" in template
    assert "开始改结构前先从 `inspect`（或 `open`、`connect` 的返回）读出模板当前版本 `template_version`，原样填入" in template
    making = read_skill("stages/3-制作.md")
    assert "抽出模板版本、挂到应用并绑工作集，见 [../reference/数据模板.md](../reference/数据模板.md)「建表与出版本」" in making
    errors = read_skill("reference/报错对照.md")
    for code in ("TEMPLATE_BASELINE_REQUIRED", "TEMPLATE_BASELINE_CHANGED"):
        rows = [line for line in errors.splitlines() if line.startswith(f"| `{code}`")]
        assert len(rows) == 1
    assert "用新的 `template_version` 作为 `expected_base_version` 重新 `extract`" in errors


def test_collaborators_read_asset_versions_via_get_asset(read_skill):
    """协作者不调 list_asset_versions 查属主名下资产；查询被拒不引导升档。"""
    text = read_skill("reference/多人协作.md")
    viewer = _section(text, "### 只读协作者能读什么")
    assert "协作者看属主名下资产的版本一律用 `get_asset`" in viewer
    assert "`WORKFLOW_TASK_MODE_MISMATCH`" in viewer
    assert "不为此新开 write 工单" in viewer
    editor = _section(text, "### 编辑协作者的草稿与各层资产")
    assert "属主名下资产的现役版本用 `get_asset` 看，草稿以派生返回为准，不用 `list_asset_versions` 查" in editor
    errors = _section(text, "### 协作相关报错")
    query = [line for line in errors.splitlines() if line.startswith("| `PERSONAL_VERSION_NOT_OWNER`（查询时）")]
    assert len(query) == 1 and "不请属主升档" in query[0]
    assert "下线（`offline`）、删除（`delete`）" in errors
    revise = read_skill("tasks/修订.md")
    assert "不调 `list_asset_versions`" in revise


def test_owner_finalize_names_draft_when_family_has_several(read_skill):
    """家族有多份草稿时属主上线必须显式指定 draft_asset_id。"""
    launch = read_skill("stages/5-上线.md")
    assert "显式传要上线的 `draft_asset_id`" in launch
    deploy = _section(read_skill("reference/部署与版本.md"), "### 上线")
    assert "家族里可能同时有多份草稿（有协作者时），所以显式传要上线的那份 `draft_asset_id`" in deploy
    assert "平台不替你挑" in deploy
