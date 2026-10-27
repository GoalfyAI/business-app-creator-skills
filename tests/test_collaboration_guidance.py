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
    """先识别任务时按 business_ui_manage 返回的 role 分流，红线写明协作者不定版、不发布。"""
    skill = read_skill("SKILL.md")
    routing = skill.split("## 4. 先识别任务", 1)[1].split("## 5.", 1)[0]
    assert "`role` 分流" in routing
    assert "`viewer`（只读协作者）：不管开发者要做什么，只走诊断路线" in routing
    assert "`editor`（编辑协作者）：改动走修订路线" in routing
    assert "分享兑换入口接受" in routing
    red_lines = skill.split("## 0. 红线", 1)[1].split("## 1.", 1)[0]
    assert "协作者**禁止**定版、发布、下线、删除应用" in red_lines
    assert "request_finalize" in red_lines


def test_viewer_route_stays_read_only(read_skill):
    """只读协作者不派生草稿、不申请写连接、不写 SQL、不跑写流程、不用 dataset_read 读开发库。"""
    route = _section(read_skill("reference/多人协作.md"), "### 只读协作者：诊断路线")
    assert "建 read 工单" in route
    assert "派生任何草稿" in route
    assert '`dataset_template_workspace(action="connect", mode="reader")`' in route
    assert "`connect` **必须**显式带 `mode=\"reader\"`" in route
    assert "TEMPLATE_WORKSPACE_WRITER_FORBIDDEN" in route
    assert "`connect` 申请写连接" in route
    assert "执行写数据的 SQL 或 DDL" in route
    assert "`ship`、部署、冒泡、真跑这类写流程" in route
    assert "调 `finalize` 或 `request_finalize`" in route
    assert "用 `dataset_read` 读应用开发库" in route
    assert "告诉他自己能查看哪些内容" in route
    assert "改动要请属主或编辑协作者做" in route


def test_editor_route_derives_own_drafts_and_requests_finalize(read_skill):
    """编辑协作者只改自己的草稿、change_note 必填、各层自己定版后往上更新引用，④ 部署自己的草稿、页面在本机版上验，⑤ 提请定版。"""
    text = read_skill("reference/多人协作.md")
    route = _section(text, "### 编辑协作者：修订路线")
    assert "`change_note` 必填" in route
    assert "别人创建的草稿**禁止**改" in route
    assert "工具组 → 工具集或 FA → 场景包路线 → 应用挂载" in route
    assert "再自己定版" in route
    assert "共享工作集" in route
    assert "模板当前版本 `template_version`" in route
    assert "带 `expected_base_version=<第 1 步记下的模板版本>`" in route
    assert "TEMPLATE_BASELINE_CHANGED" in route
    assert "[开发者中心与工作区.md](开发者中心与工作区.md)「④ 本机版页面验收」在本机版上做" in route
    assert "部署前的授权照 ④ 2.1" in route
    assert "先把自己的草稿 `ship` 到 `success`" in route
    assert "协作者身份下才看得到的表现只有线上才能验证，记「未测」" in route
    assert "登录" not in route
    request = _section(text, "### 提请定版")
    assert '`business_ui_manage(action="request_finalize", task_id, business_ui_id)`' in request
    assert "`draft_asset_id` 可以省略" in request
    assert "`note` 是给属主的补充说明" in request
    assert "「已提请，等属主定版」" in request
    launch = read_skill("stages/5-上线.md")
    assert "`editor` 走第 2 节末尾「协作者分支」" in launch
    assert "**协作者分支**（`role=editor`）" in launch
    assert '换成 `business_ui_manage(action="request_finalize")` 提请属主定版' in launch
    assert "**禁止**调 `finalize`、`resolve` 冒充上线" in launch


def test_page_items_use_local_headless_browser_not_online_addresses(read_skill):
    """需求责任人 10-27：普通宿主和 Studio 下 AI 都不用浏览器访问线上地址，页面条目在本机版上用无头浏览器验，线上才能验证的标「未测」，不请开发者代测。"""
    red_lines = read_skill("SKILL.md").split("## 0. 红线", 1)[1].split("## 1.", 1)[0]
    assert "**禁止**用 Codex 内置浏览器、Playwright 或任何浏览器打开 GoalfyMax 正式入口、`passport` 登录页、在线预览地址或容器地址" in red_lines
    assert "在应用根用 `npm run dev:restart` 起的本机版（只访问本机地址）可以用无头浏览器照验收条目操作" in red_lines
    workspace = read_skill("reference/开发者中心与工作区.md")
    local = _section(workspace, "### ④ 本机版页面验收")
    assert "浏览器只打开本机版输出里的本机地址（`127.0.0.1` 或 `localhost`）" in local
    assert "你也不判断应用部署在哪个环境" in local
    assert "用 Playwright 无头 Chromium 打开 Dev Host 地址" in local
    online_only = local.split("#### 只有线上才能验证的", 1)[1].split("\n#### ", 1)[0]
    for fact in ("| 平台登录身份 |", "| 真实宿主桥接 |", "结论写「未测」、证据写「无」，原因写「只有线上才能验证：<依赖哪一项>」",
                 "**禁止**请开发者在在线预览、演示预览或正式入口代测", "⑤ 上线结果单列这些条目，告诉开发者上线后可以自己看"):
        assert fact in online_only, fact
    studio = next(line for line in _section(workspace, "### Studio 宿主").splitlines() if line.startswith("| ④ |"))
    assert "页面条目同样由你在本机版上用无头浏览器验" in studio
    assert "不能代替上面「④ 本机版页面验收」" in studio
    assert "/preview" not in studio
    for name in ("SKILL.md", "stages/4-试用验收.md", "stages/5-上线.md", "reference/开发者中心与工作区.md", "reference/多人协作.md",
                 "checklists/验收清单.md", "design/交接消息.md", "design/开发文档/样例.md", "design/开发文档/验收报告.md"):
        text = read_skill(name)
        assert "需要你在在线预览里试" not in text and "开发者未试" not in text, name
        for retired in ("登录好了", "launch(headless=False)", "--isolated", "启动浏览器", "用浏览器验收", "goalfymax.goalfyai.cn",
                        "goalfymax.pre.goalfyai.cn", "/business-ui/<应用 ID>/preview`（打开登录者本人"):
            assert retired not in text, (name, retired)


def test_resume_reads_pending_finalize_and_stale_baseline_first(read_skill):
    """接续先读待定版清单与基线过期状态，过期时按下载、合并、重新派生、部署、再提请的顺序处理。"""
    resume = read_skill("tasks/接续.md")
    assert "待定版清单和自己草稿的基线是否过期" in resume
    assert "下载新版源码、本地 git 合并、重新派生草稿、上传部署、再提请" in resume
    merge = _section(read_skill("reference/多人协作.md"), "### 基线过期的合并")
    steps = ["`business_ui_bundle(action=\"download\")`", "用 git 合并", "重新派生自己的应用草稿", "`ship` 到新草稿", "再次提请定版"]
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
    assert "**禁止**写成「协作者自付」或「属主承担」这类长期承诺" in limits


def test_setup_derivation_requires_change_note(read_skill):
    """setup 需要派生草稿时同样要带 change_note。"""
    deploy = read_skill("reference/部署与版本.md")
    assert "应用建草稿（含 update、`setup`、`ship` 自动派生）必须带 `change_note`" in deploy
    errors = _section(read_skill("reference/多人协作.md"), "### 协作相关报错")
    assert "`update`、`setup`、`ship` 需要从上线版派生草稿时" in errors


def test_template_extract_requires_baseline_for_every_route(read_skill):
    """给已有模板抽新版本一律带 expected_base_version，属主路线与报错对照同样写明。"""
    template = read_skill("reference/数据模板.md")
    assert "给已有模板出新版本时传 `template_id`，并带 `expected_base_version`" in template
    making = read_skill("stages/3-制作.md")
    assert "带 `expected_base_version=<这个版本>`" in making
    errors = read_skill("reference/报错对照.md")
    for code in ("TEMPLATE_BASELINE_REQUIRED", "TEMPLATE_BASELINE_CHANGED"):
        rows = [line for line in errors.splitlines() if line.startswith(f"| `{code}`")]
        assert len(rows) == 1
    assert "用新的 `template_version` 作为 `expected_base_version` 重新 `extract`" in errors


def test_collaborators_read_asset_versions_via_get_asset(read_skill):
    """协作者不调 list_asset_versions 查属主名下资产；查询被拒不引导升档。"""
    text = read_skill("reference/多人协作.md")
    viewer = _section(text, "### 只读协作者：诊断路线")
    assert "协作者看属主名下资产的版本一律用 `get_asset`" in viewer
    assert "`WORKFLOW_TASK_MODE_MISMATCH`" in viewer
    assert "**禁止**为此新开 write 工单" in viewer
    editor = _section(text, "### 编辑协作者：修订路线")
    assert "**禁止**用 `list_asset_versions` 查属主名下的资产" in editor
    errors = _section(text, "### 协作相关报错")
    query = [line for line in errors.splitlines() if line.startswith("| `PERSONAL_VERSION_NOT_OWNER`（查询时）")]
    assert len(query) == 1 and "不要请属主升档" in query[0]
    assert "下线（`offline`）、删除（`delete`）" in errors
    revise = read_skill("tasks/修订.md")
    assert "不调 `list_asset_versions`" in revise


def test_owner_finalize_names_draft_when_family_has_several(read_skill):
    """家族有多份草稿时属主定版必须显式指定 draft_asset_id。"""
    launch = read_skill("stages/5-上线.md")
    assert "这时**必须**显式传要定版的那份 `draft_asset_id`" in launch
