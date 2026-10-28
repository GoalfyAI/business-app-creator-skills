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
    routing = skill.split("## 3. 先识别任务", 1)[1].split("## 4.", 1)[0]
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
    assert "用 `dataset_read` 读应用开发库" in route


def test_editor_route_derives_own_drafts_and_requests_finalize(read_skill):
    """编辑协作者只改自己的草稿、change_note 必填、各层自己定版后往上更新引用，G7 提请定版。"""
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
    request = _section(text, "### 提请定版")
    assert '`business_ui_manage(action="request_finalize", task_id, business_ui_id)`' in request
    assert "`draft_asset_id` 可以省略" in request
    assert "`note` 是给属主的补充说明" in request
    assert "「已提请，等属主定版」" in request
    g7 = read_skill("flow/G7-上线交付.md")
    assert "**协作者分支**（`role=editor`）" in g7
    assert "**禁止**调 `finalize`、`resolve` 冒充上线" in g7


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
    g5 = read_skill("flow/G5-数据与应用.md")
    assert "带 `expected_base_version=<这个版本>`" in g5
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
    g7 = read_skill("flow/G7-上线交付.md")
    assert "这时**必须**显式传要定版的那份 `draft_asset_id`" in g7
