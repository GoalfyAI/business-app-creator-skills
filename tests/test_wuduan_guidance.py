"""R-367 五段版：四份开发文档、Studio 接续、平台反馈与七节点遗留反馈、开工环境与结单前保存。

每条都从唯一源、四个平台和两个安装包读实际分发的文件。
"""

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
DOCS = "design/开发文档/"


@pytest.fixture(params=SURFACES)
def surface(request):
    return ROOT / request.param


@pytest.fixture
def read_skill(surface):
    def read(relative: str) -> str:
        if surface.suffix == ".zip":
            with ZipFile(surface) as archive:
                return archive.read(relative).decode("utf-8")
        return (surface / relative).read_text(encoding="utf-8")

    return read


def _names(surface: Path) -> list[str]:
    if surface.suffix == ".zip":
        with ZipFile(surface) as archive:
            return archive.namelist()
    return [p.relative_to(surface).as_posix() for p in surface.rglob("*") if p.is_file()]


def _markdown(surface: Path, read_skill) -> str:
    return "\n".join(read_skill(n) for n in sorted(_names(surface)) if n.endswith(".md"))


def test_development_documents(surface, read_skill):
    """第 27 条：四份开发文档的所属段、时机、documentType、确认登记与版式文件随 Skill 发出。"""
    names = _names(surface)
    for doc in ("README", "PRD", "方案", "制作进度", "验收报告", "样式", "检查清单"):
        assert f"{DOCS}{doc}.md" in names, doc
    readme = read_skill(DOCS + "README.md")
    for fact in (
        "| PRD | ① 按轮问问完、开发者回「对」之后，写第 1 版 |",
        "| 方案 | ② 取舍、验收要求和费用变化问清之后 |",
        "| 制作进度 | ③ 开始时，建任何资产、写代码之前 |",
        "| 验收报告 | ④ 报告过了硬门之后 |",
        "`prd`", "`proposal`", "`progress`", "`acceptance`",
        "还没到的段不写，也不写「暂无」「未开始」的占位页",
        "代替方案页",
        "没有这些工具时写方案页",
        "用 `studio_read_creation` 读这份文档当前的 `artifactId`、`version`、`digest`；调 `studio_confirm_proposal`",
        "不放按钮、输入框、表单",
    ):
        assert fact in readme, fact
    for doc in ("PRD", "方案", "制作进度", "验收报告"):
        assert "## 完整样例" in read_skill(f"{DOCS}{doc}.md"), doc
    progress = read_skill(DOCS + "制作进度.md")
    assert "写更新时间" in progress and "不写「第几次更新」" in progress
    report = read_skill(DOCS + "验收报告.md")
    assert "没通过、通过、要你判断（好不好你说了算）、未测" in report
    assert "「本机版：」或「真跑：」开头" in report
    assert "格做好了" in progress and "不代表验收通过" in progress and "项完成" not in progress
    assert "受影响的格子改回「在做」" in progress
    assert "⑤ 上线后补在最后" in report
    stage_docs = {
        "stages/1-需求确认.md": "开发文档 PRD",
        "stages/2-方案.md": "开发文档「方案」",
        "stages/3-制作.md": DOCS + "制作进度.md",
        "stages/4-试用验收.md": DOCS + "验收报告.md",
    }
    for stage, link in stage_docs.items():
        assert link in read_skill(stage).split("## 4. 产出与落盘", 1)[1], stage
    markdown = _markdown(surface, read_skill)
    for banned in ("需正式版验证", "prd.html", "plan.html", "progress.html", "acceptance.html"):
        assert banned not in markdown, banned

    # 第 32 条：Studio 下接续没有 PRD 的旧应用，通用写法，不点名旧版本号。
    resume = read_skill("tasks/接续.md")
    for fact in (
        "Studio 下用 `studio_read_creation` 读开发文档",
        "做到哪一段以 `workspace.json` 为准，没有工作区的从 ① 开始",
        "Studio 下包括只有方案记录、没有 PRD 记录的",
        "Studio 下按 PRD（`documentType=prd`）交，请开发者确认一次",
        "已有的方案记录不当作 ② 已确认的方案，不凭它跳过 ① ②，也不改写它",
        "工作区已有的方案页不删除、不改写",
        "G6 既没有 ④ 验收报告、也没有开发者「可以上线」原话 checkpoint",
        "算 ④ 未验收，接到 ④ 或 ⑤ 时按 ④ 验收",
        "开发者说预览看过没问题不算验收",
        "开发者说「可以上线」后才上线",
        "已经上线的按 [修订.md](修订.md) 处理",
    ):
        assert fact in resume, fact
    assert "v2026" not in resume and "531fb2" not in resume


def test_platform_feedback_written_into_skill(read_skill):
    """第 35 条：FB-240 配额、FB-418 契约误报、FB-241 只改挂载真跑、FB-711 正式使用只认发布。"""
    errors = read_skill("reference/报错对照.md")
    quota = next(line for line in errors.splitlines() if line.startswith("| `BUSINESS_UI_DEPLOYMENT_QUOTA_EXCEEDED`"))
    assert "等开发者指明释放哪个" in quota and "你不自己做，也不原样重试" in quota
    contract = next(line for line in errors.splitlines() if line.startswith("| `BUSINESS_UI_CONTRACT_OUTDATED`"))
    assert "刚 deploy 成功、之后没改过这些仍报的，先看 `tpe_ids` 有没有写 `latest`" in contract
    deploy = read_skill("reference/部署与版本.md")
    assert "只改挂载（编排、`tpe_ids`、模板版本）没重新部署的草稿也会被选中" in deploy
    assert "`business_ui_version_id` 是这次执行用的版本行" in deploy
    skill = read_skill("SKILL.md")
    assert "正式使用（包括开发者本人正式使用、到点自动运行）只认发布" in skill
    materials = read_skill("stages/5-上线.md").split("### 2.6 发布要准备的材料", 1)[1]
    assert "描述、Logo、版本更新说明" in materials
    for path in ("SKILL.md", "stages/4-试用验收.md", "reference/部署与版本.md", "reference/报错对照.md"):
        assert "改挂载后先重新部署" not in read_skill(path), path


def test_seven_node_feedback_written_into_skill(read_skill):
    """第 36 条：FK-367/384/385/387/388 对照补齐的写法。"""
    acceptance = read_skill("stages/4-试用验收.md")
    change = acceptance.split("### 2.6 按反馈改", 1)[1].split("\n## ", 1)[0]
    assert "照他的原话列成编号清单" in change
    assert "「已改，已验证」「已改，未验证（原因）」或「没改（原因）」" in change
    assert "找出用到同一份数据或同一个判断的其他页面和路线一起核对" in change
    assert "要加 PRD 没写的业务条件" in change
    deploy = acceptance.split("### 2.2", 1)[1].split("\n### ", 1)[0]
    assert "部署的必须是本机测过的那份" in deploy and "`source_sha256` 对应最后一次本机测试" in deploy
    skill = read_skill("SKILL.md")
    assert "实现中要加 PRD 没写的业务条件" in skill
    assert "① 第一条回复也一样，四件事和三个数都写" in skill
    assert "刷新或重新打开后找回" in read_skill("design/选择题与判断题.md")
    pages = read_skill("reference/前端页面.md")
    assert "第一次没有数据、资料不全（还缺什么、去哪补）、处理中、失败（原因和下一步）、完成" in pages
    workspace = read_skill("reference/开发者中心与工作区.md")
    assert "改回" in workspace.split("## 三件套与阶段标记", 1)[1].split("\n## ", 1)[0]


def test_start_environment_and_push_before_closing(read_skill):
    """第 37 条：开工不传 --environment，⑤ 结单前 workspace_push 并列入交棒条件。"""
    skill = read_skill("SKILL.md")
    assert "不传 `--environment`" in skill and "缺少环境" in skill
    assert "--document-mode" not in skill
    launch = read_skill("stages/5-上线.md")
    closing = launch.split("### 2.4 结单", 1)[1].split("\n### ", 1)[0]
    push, g7, complete = (closing.index(k) for k in ("`workspace_push`", "G7", "task_manager(action=\"complete\")"))
    assert push < g7 < complete
    assert "`workspace_push` 成功" in launch.split("## 5. 交棒条件", 1)[1]
    workspace = read_skill("reference/开发者中心与工作区.md")
    line = next(l for l in workspace.splitlines() if l.startswith("- `workspace_push` 是整份覆盖"))
    # 评测 10-29：全量内联太大会写坏参数，清单收窄到换机要用的文件；失败重试一次，仍失败不结单
    for name in ("`app.json`", "`WORKSPACE.md`", "`workspace.json`", "`docs/stages/`", "`docs/proposal/index.html`", "`docs/proposal/history/`"):
        assert name in line, name
    failed = next(l for l in workspace.splitlines() if l.startswith("- 保存失败"))
    for fact in ("改好后再传一次", "第二次还失败的，不写 G7、不结单", "不能因为文件多或内容长而跳过这一步"):
        assert fact in failed, fact
    assert "没拿到成功回执不往下写 G7、不结单" in closing
    assert "只在本地标记不算" in read_skill("stages/2-方案.md").split("## 5. 交棒条件", 1)[1]
    assert "不用上线应用或发布来排查" in read_skill("stages/4-试用验收.md")
    assert "也不为排查另建试探用的 TPE、FA、工具集或应用" in read_skill("stages/4-试用验收.md")
    # 评测第二轮：制作中 TPE 新版本先暂存；TPE 的 online 照做，挂到应用版本靠 update 的 tpe_ids
    deploy = read_skill("reference/部署与版本.md")
    assert "制作中建、改 TPE 不用传 `publish_mode`：缺省 `staged`" in deploy
    assert "`otpe_manage(action=\"online\")` 只启用这条 TPE" in deploy
    assert "TPE 上线不会改应用版本" in deploy
    # ③ 进度不攒到 ④；④ 真跑后补发「我先跑了一遍」进交棒条件
    build = read_skill("stages/3-制作.md")
    assert "进度在做的过程中发出，不攒到 ④" in build
    exit_rules = build.split("## 5. 交棒条件", 1)[1]
    assert "第一版制作进度在第一个建资产、写代码的动作之前就已保存" in exit_rules
    assert "已按 2.3 发过 ③ 的最后一条进度" in exit_rules
    assert "真跑通过后都已按 2.3 第 6 步补发「我先跑了一遍」" in read_skill("stages/4-试用验收.md").split("## 5. 交棒条件", 1)[1]
    entry = build.split("## 1. 进入条件", 1)[1].split("## 2.", 1)[0]
    assert "进入 ③ 的第一个动作是保存第一版制作进度" in entry and "这一步之前不建任何资产、不写代码" in entry
    assert "先按 [stages/3-制作.md](stages/3-制作.md)「进入条件」保存第一版制作进度" in read_skill("SKILL.md")
    assert "| 制作进度 | ③ 开始时，建任何资产、写代码之前 |" in read_skill("design/开发文档/README.md")
    # 失败条目：每个「做不成怎么办」一条，写明怎么造失败；造不出来的归入「未测」
    assert "每个「做不成怎么办」各写一条失败条目" in read_skill("design/选择题与判断题.md")
    assert "每个失败条目都按条目造出一次失败看表现，报告写明失败是怎么造出来的" in read_skill("checklists/验收清单.md")
    assert "「测试中造不出这种失败」，加试过哪些做法" in read_skill("stages/4-试用验收.md")
    # FK-1257：对开发者不提 Skill 与规则出处、不说流程内部词，PRD 说「需求文档」
    skill = read_skill("SKILL.md")
    assert "也不提本 Skill、SKILL.md、段文件、规则出处，不说「交棒」「阶段标记」" in skill
    assert "PRD 对开发者一律说「需求文档」" in skill
    assert "刚做完：需求文档第 2 版" in read_skill("design/交接消息.md")
    assert "依据 PRD" not in read_skill("design/开发文档/方案.md") and "对齐" not in read_skill("design/开发文档/PRD.md")
    # 会原样给开发者看的格子和句子不用「真跑」「基线过期」
    for doc in ("design/交接消息.md", "design/开发文档/制作进度.md", "stages/3-制作.md", "stages/4-试用验收.md"):
        text = read_skill(doc)
        assert "做好了，真跑过" not in text and "做好了，等部署后真跑" not in text, doc
    assert "做好了，用真实数据试过" in read_skill("design/开发文档/制作进度.md")
    assert "基线过期的通知" not in read_skill("reference/多人协作.md")
    # 方案页状态文字写阶段名，不写 G 编号
    page = read_skill("design/方案页.md")
    assert '<div class="pv-state">④ 试用验收</div>' in page and "不写 G1–G7" in page
    # FB-785：会话里没有 business_ui_stage 时的替代记录
    assert "工具列表里没有 `business_ui_stage` 时，把这三件事写进阶段文档和工单 checkpoint" in read_skill("reference/开发者中心与工作区.md")
    # 红线：不读取、打印开发者的 Key 和连接配置
    assert "**禁止**读取、打印或截取开发者的 API Key 和插件连接配置" in read_skill("SKILL.md")
