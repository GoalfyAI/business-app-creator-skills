"""R-438 第 3 版（D-3962）：升级任务按升级指南改业务代码、逐条判断与回退、开工判定新建与存量、记录结构。"""

from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
SKILL_ROOT = ROOT / "skills" / "business-app-creator"
SURFACES = (
    "skills/business-app-creator",
    "claude-code/skills/business-app-creator",
    "codex/skills/business-app-creator",
)
# 第 1 版（制作变更日志、Hub 条目、平台游标）已废弃，任何分发文件都不得再出现这些标识。
RETIRED_UPGRADE_TERMS = (
    "maker_changelog",
    "hub_changelog",
    "platform_cursor",
    "platform_release",
    "since_cursor",
    "entries_next",
    "late_guide",
    "entries_truncated",
    "entry_counts",
    "source_key",
    # 第 9 版起指南随 Skill 发布，upgrade_plan 不再返回指南，分页、游标、班车分组与 OA 发布状态一并废弃。
    "next_offset",
    "batch_unresolved",
    "UPGRADE_GUIDES_UNAVAILABLE",
    "UPGRADE_PLAN_CURSOR_INVALID",
    "dependency_unresolved",
    "oa_missing",
    "applied_guides=",
)


@pytest.fixture(params=SURFACES)
def read_skill(request):
    """从唯一源和两个平台（claude-code、codex）读取实际分发的 Skill 文件。"""
    surface = ROOT / request.param

    def read(relative: str) -> str:
        return (surface / relative).read_text(encoding="utf-8")

    return read


def _step(text: str, number: int) -> str:
    """取「从哪一段进」里第 number 步到下一步之前的正文。"""
    body = text.split("## 从哪一段进", 1)[1]
    start = body.index(f"\n{number}. **")
    end = body.find(f"\n{number + 1}. **", start + 1)
    return body[start:] if end == -1 else body[start:end]


def test_upgrade_task_is_routed_and_opening_line_covers_guides(read_skill):
    skill = read_skill("SKILL.md")
    routing = skill.split("## 6. 任务路由", 1)[1].split("## 7.", 1)[0]
    assert "| 升级 | [tasks/升级.md](tasks/升级.md) |" in routing
    upgrade = read_skill("tasks/升级.md")
    signals = upgrade.split("## 识别信号", 1)[1].split("## 先读什么", 1)[0]
    assert "本任务替换脚手架固定层，并按升级指南修改业务代码（workflow 写法、SDK 调用、页面用法等）；指南之外的业务需求变更仍转 [修订.md](修订.md)" in signals
    assert "本任务只换脚手架固定层" not in upgrade


def test_plan_reads_skill_guides_only_when_pulling_a_new_template(read_skill):
    """第 9 版：MCP 只给固定层与两线；候选指南由 Skill 自带脚本按 history.json 算，只在拉新模板时读。"""
    upgrade = read_skill("tasks/升级.md")
    plan = _step(upgrade, 1)
    assert 'business_ui_bundle(action="upgrade_plan", task_id, current_scaffold_version=<version>, skill_version=<有才传>, workspace_id)`' in plan
    assert "`latest.version` 与本地 `version` 不同（本次要拉新模板），或下面「旧路跨主版本」要迁到 SDK 5 时，运行 `python3 <skill目录>/scripts/upgrade_guides.py candidates --app <应用根> --sdk-major <N>`" in plan
    assert "`target` 不带 `sdk_version`（旧路应用跨主版本迁到新路）时不传，按默认 5" in plan
    assert "候选只认脚本输出，**禁止**自己读指南目录另算" in plan
    assert "`latest.version` 等于本地 `version`（上一条旧路要迁移的除外）→ 不读指南" in plan
    assert "脚本退出码不是 0（`status=invalid_guide`" in plan
    assert "`latest.json` 写 `failed(step=plan)` 与错误原文后停止，不改应用文件" in plan
    assert "**禁止**当成没有指南只换固定层" in plan
    signals = upgrade.split("## 识别信号", 1)[1].split("## 先读什么", 1)[0]
    assert "**只在拉了新的 SDK 5 模板之后读**" in signals and "旧路应用改 bug 不重拉模板、不读指南" in signals
    assert "第 1 步脚本输出 `guides` 里的全部指南" in _step(upgrade, 2)


def test_judgement_decides_without_waiting_and_required_cannot_defer(read_skill):
    judge = _step(read_skill("tasks/升级.md"), 6)
    for fact in (
        "不适用记 `not_applicable`；已满足记 `already_done`",
        "暂不做（`deferred`，写理由，下次仍返回）",
        "问了不等回复，先处理其他指南",
        "已有同一个没答的问题时不再问",
        "脚本输出的 `reconsider`",
        "条件没变保持 `not_applicable`",
        "`impact=required` 的只能是不适用、已满足或做，**禁止**暂缓",
        "本条记 `deferred`，理由写「依赖 <did> 未完成」，不执行",
    ):
        assert fact in judge, fact
    closing = _step(read_skill("tasks/升级.md"), 11)
    assert "还没得到答复的 `asked` 一律转 `deferred`，理由写「待开发者确认：<问题摘要>」" in closing


def test_execution_order_commits_and_rollback_granularity(read_skill):
    upgrade = read_skill("tasks/升级.md")
    assert 'git commit --allow-empty -m "upgrade: before <from>→<to>"' in _step(upgrade, 3)
    fixed = _step(upgrade, 4)
    assert "node <模板目录>/scripts/upgrade-scaffold.mjs" in fixed and "不停下等开发者" in fixed
    assert "这时**不跑** `verify`" in _step(upgrade, 5)
    adapt = _step(upgrade, 7)
    assert "`applies_to.layers` 含 `scaffold` 或 `sdk` 的指南，以及全部决定做的 `impact=required` 指南" in adapt
    assert 'git commit -m "upgrade: guide <did>"' in adapt
    assert "其他失败（固定层本身、`required` 指南）→ 整次失败" in _step(upgrade, 8)
    single = _step(upgrade, 9)
    assert "记 `failed`，理由写失败的测试 id 与输出摘要，依赖它的后续指南一并回退并记 `deferred`，接着做下一条" in single
    assert "**禁止**加 `-x` / `-X`" in single
    rollback = _step(upgrade, 13)
    assert "git reset --hard <upgrade: before 提交>" in rollback
    assert "失败检查项涉及的文件与各条 `guide_commits.files` 取交集，按交集文件数由多到少列出" in rollback
    assert "`history.json` 不改" in rollback
    assert 'submit_dev_feedback(blocking="blocked")' in rollback and "`query_dev_feedback`" in rollback
    assert "第 3 次及以后只追加" in rollback
    report = _step(upgrade, 12)
    assert 'business_ui_bundle(action="download_template", task_id, current_scaffold_version, workspace_id, sdk_version, skill_version)' in report


def test_records_are_written_once_at_the_end(read_skill):
    upgrade = read_skill("tasks/升级.md")
    prepare = upgrade.split("## 先读什么", 1)[1].split("## 从哪一段进", 1)[0]
    assert "**禁止**放进应用根或 git，单条回退和整次回滚都不会抹掉它" in prepare
    closing = _step(upgrade, 11)
    assert "删掉脚本输出 `retired` 里的 did" in closing and "2000" not in closing
    template = read_skill("reference/升级手册模板.md")
    for field in ("guide_decisions", "guide_tests", "guide_commits", "suspect_guides", "questions", "feedback"):
        assert f'"{field}"' in template, field
    history = template.split("### history.json", 1)[1].split("## 常见错误", 1)[0]
    assert "`fail_count`" in history and "`deferred` 与 `failed` 必须带 `reason`" in history
    assert "已执行记录缺失，将重新核对全部已发布指南" in history
    assert "history.json.broken-<YYYYMMDDTHHMMSSZ>" in history and "**禁止**在原文件上覆盖" in history


def test_opening_classifies_new_and_existing_apps(read_skill):
    skill = read_skill("SKILL.md")
    opening = skill.split("## 7. 开工", 1)[1].split("## 8.", 1)[0]
    assert "清单带 `guide_baseline` 时按同文件「新建与存量」判定并删掉它" in opening
    scaffold = read_skill("reference/脚手架与预置件.md")
    section = scaffold.split("#### 新建与存量", 1)[1].split("#### 升级步骤", 1)[0]
    for fact in (
        "同时满足四条才算新建",
        "`git rev-list --count HEAD` 为 1",
        "提交说明「chore(scaffold): 模板基线」、作者 `goalfy-agent <agent@goalfy.local>`",
        "`git status --porcelain` 为空（未跟踪文件也算改动，`.gitignore` 忽略的不算）",
        "`docs/upgrade/history.json` 不存在",
        "`python3 <skill目录>/scripts/upgrade_guides.py baseline`，基线 = 当前 Skill 自带的全部有效指南",
        '`{did, sha, how: "baseline"}` 原样写进 `docs/upgrade/history.json` 的 `applied_guides`',
        "只删标记、不写 `history.json`，按存量处理",
    ):
        assert fact in section, fact


def test_no_retired_upgrade_terms_in_any_surface():
    for relative in SURFACES:
        surface = ROOT / relative
        texts = {str(path): path.read_text(encoding="utf-8") for path in surface.rglob("*") if path.suffix in (".md", ".yaml")}
        for name, text in texts.items():
            for term in RETIRED_UPGRADE_TERMS:
                assert term not in text, (relative, name, term)


def test_review_round1_fixes(read_skill):
    """06B 第 1 轮：回滚点、部署后测试未跑、上限停止、错误处置、只检查保留记录、applied_guides 与 upgrades 分写。"""
    upgrade = read_skill("tasks/升级.md")
    plan = _step(upgrade, 1)
    assert "`SCAFFOLD_POLICY_UNAVAILABLE` 隔几分钟重试一次" in plan
    assert "**禁止**改 `history.json` 的 `sha` 或 `how` 凑数" in plan
    deploy = _step(upgrade, 10)
    assert "指南只要有一条测试没跑，就**禁止**记 `tested`" in deploy
    assert "`required` 指南有测试没跑不算完成，按整次失败处理" in deploy
    prepare = upgrade.split("## 先读什么", 1)[1].split("## 从哪一段进", 1)[0]
    assert "往 `history.json` 的 `upgrades` 追加本次升级记录" in prepare and "只替换这一个字段" in prepare
    template = read_skill("reference/升级手册模板.md")
    assert "**禁止**整份重写" in template and "`failure`、`feedback`、`questions`、`suspect_guides`" in template
    assert '"upgrades"' in template


def test_owner_decisions_1105(read_skill):
    """需求责任人 11-05：要已部署版本的 required 指南提前要部署授权；depends_on 按 MCP 解析后的值判断。"""
    upgrade = read_skill("tasks/升级.md")
    assert "除第 6 步「提前要部署授权」外，整个过程没有等开发者回复的环节" in upgrade
    judge = _step(upgrade, 6)
    assert "**提前要部署授权**：判断完、第 7 步改代码之前" in judge
    assert "按第 13 步整次失败回滚，`step=judge`" in judge
    assert "`depends_on` 已由脚本按替代与撤回解析好" in judge and "`depends_on_declared`" in judge
    assert "理由写「依赖 <did> 未完成」" in judge
    assert "含第 6 步提前问到的" in _step(upgrade, 10)
    rollback = _step(upgrade, 13)
    assert "第 6 步要已部署版本的 `required` 指南得不到部署授权" in rollback
    assert "第 6 步得不到部署授权的失败不算" in rollback


def test_review_round3_followups(read_skill):
    """06B 第 3 轮 S3-O1～O3：无改动不提交、未明确同意部署先回滚、交接消息不写 D 编号。"""
    upgrade = read_skill("tasks/升级.md")
    guide = _step(upgrade, 9)
    assert "**无改动**" in guide and "不提交、不算失败" in guide
    assert '`{"did":"<did>","commit":null,"files":[]}`' in guide
    assert "第 9 步第 4 条「无改动」" in _step(upgrade, 7)
    template = read_skill("reference/升级手册模板.md")
    assert '"commit":null,"files":[]' in template and "写「无改动」" in template
    judge = _step(upgrade, 6)
    assert "拒绝、不回复，或转去说别的事" in judge and "都按不同意处理" in judge
    assert "**禁止**在半升级的工作区上接着做别的任务" in judge
    assert "（列 did 与标题）" not in judge and "不写 D 编号" in judge
    assert "**禁止**写 D 编号、测试 id、命令和报错原文" in upgrade


def test_review_round4_unfinished_upgrade(read_skill):
    """06B 第 4 轮 S4-1～S4-3：等部署授权留等待状态、各入口先处理没做完的升级、依赖口径、第 0 步业务语言。"""
    upgrade = read_skill("tasks/升级.md")
    judge = _step(upgrade, 6)
    assert "`status=awaiting_consent`、`step=judge`" in judge and 'git commit -m "upgrade: awaiting consent"' in judge
    assert "被撤回时去掉" in judge
    prepare = upgrade.split("## 先读什么", 1)[1].split("## 从哪一段进", 1)[0]
    assert "5. 没做完的升级与中断后接续" in prepare
    assert "提交 `upgrade: failed <from>→<to> at judge`" in prepare
    assert "`error`「升级中断没有做完，已回滚」" in prepare
    assert "**禁止**在没做完升级的工作区上做别的任务" in prepare
    precheck = _step(upgrade, 0)
    assert "告诉开发者先按 `doctor` 的 `GIT_ROOT_MISMATCH` 处理" not in precheck and "用白话告诉开发者" in precheck
    # 07 V-565 A9(4)：前置检查不通过只记失败并停止，不能当场 git init 后继续升级
    assert "本次升级**禁止**自己 `git init`" in precheck and "重跑本任务" not in precheck
    template = read_skill("reference/升级手册模板.md")
    assert '"status":"checked|awaiting_consent|done|failed"' in template and '"awaiting":{' in template
    assert "写 `awaiting_consent` 时只改" in template
    assert "「先读什么」第 5 条" in read_skill("SKILL.md").split("## 7. 开工", 1)[1].split("## 8.", 1)[0]
    assert "[升级.md](升级.md)「先读什么」第 5 条" in read_skill("tasks/接续.md")
    assert "[升级.md](升级.md)「先读什么」第 5 条" in read_skill("tasks/修订.md")


def test_review_round5_consent_after_awaiting(read_skill):
    """06B 第 5 轮 S5-1～S5-3：同意部署后留下已同意标记，中断时不按「没同意」回滚；计数与前置检查引用同步。"""
    upgrade = read_skill("tasks/升级.md")
    judge = _step(upgrade, 6)
    assert '`awaiting` 补 `consent`（原话）与 `consented_at`，`git add docs/upgrade/latest.json && git commit -m "upgrade: consent given"` 后再做第 7 步' in judge
    prepare = upgrade.split("## 先读什么", 1)[1].split("## 从哪一段进", 1)[0]
    assert "`upgrade: awaiting consent`、`upgrade: consent given` 不算做完" in prepare
    assert "先读出其中的 `from`、`to`、`awaiting` 再处理" in prepare
    assert prepare.count("`awaiting.consented_at` 为空") == 2
    assert "没有等待状态，或 `awaiting.consented_at` 已填（开发者已同意部署，沿用，不再问）" in prepare
    rollback = _step(upgrade, 13)
    assert "`error` 也不是「升级中断没有做完，已回滚」" in rollback and "「先读什么」第 5 条的中断回滚也不算" in rollback
    assert "「命令行宿主」的「应用工程根是 Git 根」" in _step(upgrade, 0)
    template = read_skill("reference/升级手册模板.md")
    assert '"consent":"","consented_at":""' in template
    assert "`status` 不变，单独提交 `upgrade: consent given`" in template


def test_doctor_findings_go_to_adaptation_and_verify_is_the_gate(read_skill):
    """需求责任人 11-05 选 A：doctor 失败不整次回滚，记 doctor_findings 交适配；setup 失败仍整次失败；verify 是放行关。"""
    upgrade = read_skill("tasks/升级.md")
    setup = _step(upgrade, 5)
    assert "失败（依赖装不上等）→ 整次失败" in setup and "报 `FAIL` **不回滚**" in setup and "`doctor_findings`" in setup
    adapt = _step(upgrade, 7)
    assert "**固定层升级带来的问题也在这里修**" in adapt and "即使没有指南覆盖" in adapt
    assert 'git commit -m \"upgrade: adapt <检查码或一句话>\"' in adapt
    assert "本次升级的放行关" in _step(upgrade, 8)
    assert "setup/doctor 失败" not in _step(upgrade, 13) and "固定层替换失败、setup 失败、" in _step(upgrade, 13)
    assert "`upgrade: adapt …`" in upgrade.split("## 先读什么", 1)[1].split("## 从哪一段进", 1)[0]
    template = read_skill("reference/升级手册模板.md")
    assert '"step":"precheck|plan|upgrade|setup|judge|adapt|' in template and '"doctor_findings":[' in template
    assert "`failure.did` 为空" in template and "`doctor` 不是失败步骤" in template


def test_review_round6_retryable_doctor_findings_and_reference_sync(read_skill):
    """06B 第 6 次复审机械性小修：retryable=false 不重试；收尾与整次失败都写 doctor_findings；脚手架参考不再说业务代码只按指南改。"""
    upgrade = read_skill("tasks/升级.md")
    assert "`guide_commits`、`doctor_findings`；第 3 步有 wip 提交时加 `pre_upgrade_wip`）" in _step(upgrade, 11)
    assert "`guide_commits`、`doctor_findings`，建了 stash 时加 `rollback_stash`，建了备份分支时加 `rollback_backup`" in _step(upgrade, 13)
    reference = read_skill("reference/脚手架与预置件.md")
    assert "业务代码只按升级指南改" not in reference
    assert "固定层升级带来的 doctor/verify 问题没有指南覆盖时也按" in reference


def test_rollback_stashes_uncommitted_changes_and_dependency_changes_regenerate_lock(read_skill):
    """需求责任人批准：整次回滚前暂存开发者没提交的改动并告知恢复方法；改依赖必须重新生成锁文件并一起提交。"""
    upgrade = read_skill("tasks/升级.md")
    rollback = _step(upgrade, 13)
    assert 'git stash push -u -m \"upgrade-rollback <from>→<to> <时间>\"' in rollback
    assert "工作区干净时不建 stash" in rollback and "`rollback_stash`" in rollback
    assert "回滚前没提交的改动已经暂存，可以恢复" in rollback and "`git stash apply <它的编号>`" in rollback
    assert rollback.index("git stash push") < rollback.index("git reset --hard")
    adapt = _step(upgrade, 7)
    assert "**依赖变了就重新生成锁文件**（第 7、8、9 步都适用）" in adapt
    assert "`npm install --package-lock-only`" in adapt and "与这一条的改动一起提交" in adapt
    assert "按这一条失败处理" in adapt
    template = read_skill("reference/升级手册模板.md")
    assert '"rollback_stash":{"message":"upgrade-rollback ' in template and "没建 stash 时不写" in template


def test_small_review_k1_to_k5(read_skill):
    """小改复核 K-1～K-5：所有回滚路径都告知 stash、stash 失败不 reset、冲突提示、命令例外、适配项锁文件失败记法。"""
    upgrade = read_skill("tasks/升级.md")
    prepare = upgrade.split("## 先读什么", 1)[1].split("## 从哪一段进", 1)[0]
    assert prepare.count("按第 13 步第 7 条告诉开发者备份分支、已暂存的改动与恢复方法") == 2
    assert "（第 13 步第 7 条恢复暂存改动的方法除外）" in upgrade
    rollback = _step(upgrade, 13)
    assert "`git rev-parse stash@{0}`" in rollback
    assert "stash 后 `git status --porcelain` 仍不为空 → **禁止** reset 和 clean" in rollback
    assert rollback.index("**禁止** reset 和 clean") < rollback.index("git reset --hard")
    assert "**禁止**建议他在当前工作区提交" in rollback and "先提交或自己处理" not in rollback
    assert "任何走第 13 步回滚的路径" in rollback and "恢复会冲突，建议让你代他恢复" in rollback
    assert "冲突块里升级后的内容**禁止**带回" in rollback
    adapt = _step(upgrade, 7)
    assert "`upgrade: adapt` 适配项回退这一项的修改" in adapt and "记 `status=open`" in adapt


def test_review_cwj_rollback_safety_entry_cost_and_plan_change(read_skill):
    """陈汶君评审 !110：回滚保护开发者提交与改动、回滚后 setup、所有入口先查、花费另行授权、计划变更、依赖口径、WIP 提交。"""
    skill = read_skill("SKILL.md")
    assert "任何任务（含用户反馈、能力试用）开始前先查有没有没做完的升级" in skill
    upgrade = read_skill("tasks/升级.md")
    prepare = upgrade.split("## 先读什么", 1)[1].split("## 从哪一段进", 1)[0]
    assert "任何任务（新建、接续、修订、诊断、用户反馈、能力试用" in prepare
    rollback = _step(upgrade, 13)
    assert "<upgrade: before 提交>..HEAD" in rollback and "不以 `upgrade: ` 开头" in rollback
    assert "git branch upgrade-backup/<from>-to-<to>-<YYYYMMDDHHmmss> HEAD" in rollback and "备份分支建不成**禁止** reset" in rollback
    assert rollback.index("git branch upgrade-backup") < rollback.index("git reset --hard")
    assert "**不加任何排除**" in rollback and ":(exclude)" not in rollback
    assert "重新 `npm run setup`" in rollback and "`rollback_setup`" in rollback
    assert rollback.index("git reset --hard") < rollback.index("重新 `npm run setup`")
    assert "回滚点之后你自己做的提交已保存在备份分支" in rollback
    judge = _step(upgrade, 6)
    assert "也不是第 1 步 `history.json` 里已处理过的" in judge
    assert "部署同意不代替花费同意" in judge
    deploy = _step(upgrade, 10)
    assert "**禁止**拿部署授权代替" in deploy and "没有花费授权" in deploy
    checkpoint = _step(upgrade, 3)
    assert 'git commit -m \"wip: 升级前未提交的改动 <时间>\"' in checkpoint and "`pre_upgrade_wip`" in checkpoint
    assert "（有未提交的改动一并提交" not in checkpoint
    template = read_skill("reference/升级手册模板.md")
    for key in ('"rollback_backup":{', '"rollback_setup":{', '"pre_upgrade_wip":{'):
        assert key in template
    assert "`doctor` 不再是失败步骤" not in template and "`doctor` 不是失败步骤" in template


def test_review_r7_partial_stash_backup_notice_cost_trigger_viewer(read_skill):
    """06B 第 7 次复审：stash 后仍不干净先 pop、备份分支告知、已同意部署仍问花费、viewer 只告知、wip 记录。"""
    skill = read_skill("SKILL.md")
    assert "第 5 条处理（`viewer` 只告知、不处理）" in skill
    upgrade = read_skill("tasks/升级.md")
    prepare = upgrade.split("## 先读什么", 1)[1].split("## 从哪一段进", 1)[0]
    assert "只读协作者（`role=viewer`）查到时不回滚、不写文件" in prepare
    assert prepare.count("第 2 条建了备份分支或第 3 条建了 stash 时") == 2
    assert "花费也明确同意" in prepare and "问了花费却只同意了部署" in prepare
    judge = _step(upgrade, 6)
    assert "或其中要花积分的测试（冒泡、真跑、自动化试跑）PRD 没列、开发者也没同意过这笔花费时，现在就问一次" in judge
    assert "部署已同意过的只问花费" in judge and "开发者不同意花费" in judge
    rollback = _step(upgrade, 13)
    assert "已建成 stash 的先 `git stash pop` 把暂存的改动放回工作区" in rollback
    assert rollback.index("git stash pop") < rollback.index("git reset --hard")
    assert "之后的提交都会丢掉" not in rollback
    assert "第 3 步有 wip 提交时加 `pre_upgrade_wip`" in rollback and "第 3 步有 wip 提交时加 `pre_upgrade_wip`" in _step(upgrade, 11)


def test_reconsider_and_retired_come_from_script(read_skill):
    """第 9 版：reconsider 带完整内容直接转候选，不再重取计划；retired 原因只剩替代、撤回、文件已删。"""
    upgrade = read_skill("tasks/升级.md")
    assert "用 `reconsider` 里该条的完整动作与测试按上一条判断" in _step(upgrade, 6)
    closing = _step(upgrade, 11)
    assert "`retired_reasons`" in closing and "`file_deleted` 指南文件已从 Skill 删除" in closing and "`closed`" not in closing


def test_v565_round3_platform_rollback_and_step_times(read_skill):
    """07 V-565 第 3 轮：E11 整次回滚要恢复平台草稿并如实记录；A13 steps.at 记各步实际结束时间。"""
    upgrade = read_skill("tasks/升级.md")
    adapt = _step(upgrade, 7)
    assert "改平台上的应用配置前先记原值" in adapt and "第 13 步整次回滚时按这份记录逆序恢复" in adapt
    rollback = _step(upgrade, 13)
    assert "恢复平台上的应用配置" in rollback and "`rollback_platform`" in rollback
    assert "**禁止**说成回滚已全部完成" in rollback
    template = read_skill("reference/升级手册模板.md")
    assert '"rollback_platform":[{' in template and "`rollback_platform`：" in template
    assert "`steps[].at` 是该步实际结束的时间" in template


def test_v565_round4_upgrade_caused_is_decided_by_rollback_point(read_skill):
    """07 V-565 第 4 轮：新数据集检查时修时不修。「是否升级带来」按回滚点旧模板判断，不凭业务代码观感。"""
    adapt = _step(read_skill("tasks/升级.md"), 7)
    assert "只看这项检查在回滚点" in adapt and "`DATASET_TABLE_UNDECLARED`" in adapt
    assert "**禁止**因为业务代码看起来早就这样" in adapt


def test_v565_pre_round_deploy_does_not_report_early(read_skill):
    """07 V-565 PRE 轮：第 10 步部署前按「部署」第 1 条带三个版本调 download_template，提前形成 local_report，随后整次失败工单版本与应用不符。"""
    upgrade = read_skill("tasks/升级.md")
    deploy = _step(upgrade, 10)
    assert "「部署」第 1 条核门槛的 `download_template` 这里不调" in deploy and "只在第 12 步调一次" in deploy
    rollback = _step(upgrade, 13)
    assert "把申报更正为实际版本" in rollback and "最新一条 `local_report`" in rollback and "缺的不传" in rollback
    assert "`git worktree add <临时目录> <upgrade: before 提交>`" in _step(upgrade, 7) and "**禁止**在应用根里 checkout 或 reset 到回滚点" in _step(upgrade, 7)



def test_bugfix_does_not_repull_and_repull_migrates_by_guides(read_skill):
    """R-683 第 4 版第 5 项（D-4133，本人 11-10 11:13）：修 bug、加功能不重新拉脚手架、不迁移；一旦重新拉到 SDK 5 模板，按 Skill 自带的指南迁完（R-438 第 9 版），不问开发者。"""
    scaffold = read_skill("reference/脚手架与预置件.md")
    section = scaffold.split("#### 修 bug 不迁移与重新拉脚手架", 1)[1].split("#### 新建与接续", 1)[0]
    for fact in (
        "返回里的 `scaffold_route` 是应用所在的路（`legacy` 旧路、`new` 新路），`route_source` 是判路依据",
        "**禁止**自己按版本串、`executor` 或日期另判",
        "`fixed_layer.base_source=current_is_latest`（`latest.version` 等于本地 `version`、不带下载地址）表示模板已是最新，**禁止**另找模板下载，按已是最新结束、不读指南",
        "同时 `scaffold_route=legacy`（旧路应用，最新模板是 SDK 5）时**不是**已是最新",
        "`scaffold_route` 不是 `legacy`（新路主版本不同或确认不了）时按已是最新结束",
        "在现有工程上直接改、验证、部署，不重新下载模板、不迁移",
        "只在开发记录写「建议升级脚手架版本」，改完照常部署",
        "**禁止**把升级 SDK、换模板或迁到新路当成修 bug 的前提",
        "按《升级》运行本 Skill 自带的 `scripts/upgrade_guides.py candidates` 取升级指南（含旧应用迁到新路的指南），按指南完成迁移",
        "**禁止**问开发者要不要迁（指南要求告知的影响照常告知，发布时间由开发者定），**禁止**只换固定层不迁，**禁止**为了不迁另找旧版模板",
    ):
        assert fact in section, fact
    assert "修 bug、加功能的会话不因建议线升级" in scaffold.split("#### 升级步骤", 1)[1]
    signals = read_skill("tasks/升级.md").split("## 识别信号", 1)[1].split("## 先读什么", 1)[0]
    assert "[../reference/新路应用.md](../reference/新路应用.md)「旧应用迁到新路」" in signals
    assert "**禁止**问开发者要不要迁" in signals
    assert "开发者只要修 bug 或加功能时不进本任务，`upgrade_recommended=true` 也不进" in signals
    assert "例如 SDK 4→5 后的页面接口与路由" in _step(read_skill("tasks/升级.md"), 7)
    plan = _step(read_skill("tasks/升级.md"), 1)
    assert "或下面「旧路跨主版本」要迁到 SDK 5 时，运行" in plan
    legacy = plan.split("   - 旧路跨主版本：", 1)[1].split("\n", 1)[0]
    for fact in (
        "`scaffold_upgrade_notice` 里「本次不替换固定层，不要重试，也不要自行换模板」说的是一键升级不替换固定层，接下来按这一条做",
        "**不是**已是最新，也**禁止**问开发者要不要迁（指南要求告知的影响照常告知，发布时间由开发者定）：照上一条运行脚本取候选",
        "第 4 步记 `skipped`，固定层与 SDK 在第 7 步按迁移指南的动作迁",
        "`sdk_major_skipped` 而 `scaffold_route` 不是 `legacy`（新路主版本不同或确认不了）时按下一条已是最新结束",
    ):
        assert fact in legacy, fact
    assert "level=migrate" not in plan and "guides` 照常返回" not in plan
    assert "或返回 `fixed_layer.base_source=sdk_major_skipped` 且 `scaffold_route=legacy`" in scaffold.split("#### 升级步骤", 1)[1]
    revise = read_skill("tasks/修订.md").split("## 识别信号", 1)[1].split("## 先读什么", 1)[0]
    assert "不重新拉脚手架，**禁止**把升级 SDK、换模板或迁到新路当成前提" in revise
    assert "按 [升级.md](升级.md) 重新拉脚手架，按本 Skill 自带的迁移指南做完" in revise
    migrate = read_skill("reference/新路应用.md").split("### 旧应用迁到新路", 1)[1]
    assert "动作和测试以本 Skill 自带的迁移指南为准" in migrate
    assert "场景包挂载与编排挂载互斥" in migrate


def test_no_feature_not_open_reply_in_any_surface():
    """D-4133 第 4 版：取消「只回复功能尚未开放」与「不迁到另一条路」的规则；指南随 Skill 发布后不再按 MCP 的 level=migrate 迁移。任何分发文件都不得再出现。"""
    for relative in SURFACES:
        for path in (ROOT / relative).rglob("*.md"):
            text = path.read_text(encoding="utf-8")
            for term in ("功能尚未开放", "同路升级", "迁到另一条路", "无感", "level=migrate"):
                assert term not in text, (relative, path.name, term)


def test_v565_round14_wrap_up_fills_version_record_when_script_skipped(read_skill):
    """07 V-565 第 14 轮条目 17：旧路按迁移指南手工迁移、没跑升级脚本时，scaffold-release.json 只有 version，上报 sdk/skill 版本为空。"""
    wrap_up = _step(read_skill("tasks/升级.md"), 11)
    assert "`sdk_version` 等于目标模板 `scaffold-fixed-layer.json` 的 `sdk_version`" in wrap_up
    assert "没跑升级脚本的" in wrap_up and "`{from, to, sdk_version, skill_version, upgraded_at, conflicts}`" in wrap_up
    assert "第 12 步上报读的就是这里" in wrap_up
    # 陈汶君 !120 评审：旧路手工迁移时拷贝固定层清单、不重复追加升级记录。
    assert "应用根有目标模板的 `scaffold-fixed-layer.json`" in wrap_up
    assert "从目标模板根目录拷贝 `scaffold-fixed-layer.json`" in wrap_up
    assert "`upgrades` 最后一条不是本次 `from`→`to` 时才追加" in wrap_up
