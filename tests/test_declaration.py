"""方案段声明文件脚本：检查、确认单、走查项、空模板。夹具是一个线索管理应用。"""
import copy
import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from node_call import NodeValueError, node_call, node_calls, unwrap

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "skills/agenticapp-stage-2-plan/scripts/declaration.mjs"
FIXTURE = json.loads((ROOT / "tests/fixtures/declaration_leads.json").read_text(encoding="utf-8"))
# 改后的一份：加「合同」表和「登记合同」，早报换成企业微信，销售去掉记录跟进的权限
FIXTURE_V2 = json.loads((ROOT / "tests/fixtures/declaration_leads_v2.json").read_text(encoding="utf-8"))
FIXED = "返回数据即完成"


def check(decl):
    return node_call(SCRIPT, "check", decl)


def problems(result, level="must"):
    return [f"{x['entity']} {x['item']} {x['problem']}" for x in result[level]]


def tf(decl, key):
    return next(t for t in decl["taskflows"] if t["key"] == key)


def run_cli(*args):
    return subprocess.run(["node", str(SCRIPT), *args], capture_output=True, text=True, check=False)


class DeclarationCheckTests(unittest.TestCase):
    def setUp(self):
        self.decl = copy.deepcopy(FIXTURE)

    def test_complete_declaration_passes_without_notices(self):
        result = check(self.decl)
        self.assertTrue(result["ok"])
        self.assertEqual(result["must"], [])
        self.assertEqual(result["notice"], [])

    def test_none_forms_pass(self):
        self.decl["automations"] = {"none": "早报由主管自己在页面上点，不需要到点自动跑"}
        tf(self.decl, "dailyDigest")["scope"] = {"none": "早报按主管本人负责的全部区域汇总"}
        self.decl["pages"][0]["calls"].append("dailyDigest")
        result = check(self.decl)
        self.assertTrue(result["ok"], result["must"])
        # 早报读按区域划分的表却不按区域限制：只提醒
        self.assertTrue(any("dailyDigest" in p and "region" in p for p in problems(result, "notice")))

    def test_many_missing_items_are_listed_at_once(self):
        del self.decl["app"]["problem"]
        self.decl["app"]["tradeoffs"] = "   "
        self.decl["roles"][0]["name"] = ""
        del tf(self.decl, "assignLead")["doneWhen"]
        tf(self.decl, "logFollowup")["uses"].pop("agents")
        self.decl["automations"][0]["notifyOnIncomplete"] = ""
        self.decl["pages"][1]["summary"] = ""
        self.decl["tables"][1]["partition"] = {}
        result = check(self.decl)
        text = "\n".join(problems(result))
        self.assertFalse(result["ok"])
        for expected in ("要解决的问题（problem）", "关键取舍（tradeoffs）", "中文名称（name）", "完成标准（doneWhen）",
                         "Agent（agents）", "未完成时通知谁（notifyOnIncomplete）", "功能说明（summary）", "划分（partition）"):
            self.assertIn(expected, text)
        self.assertGreaterEqual(len(result["must"]), 7)

    def test_template_is_rejected_item_by_item(self):
        template = node_call(SCRIPT, "template")
        result = check(template)
        entities = {x["entity"] for x in result["must"]}
        self.assertEqual(entities, {"应用", "角色", "资源控制点", "数据表", "TaskFlow", "自动任务", "页面"})
        # 空数组占位不能当成「没有」放过
        self.assertTrue(any("工具（tools）里有空的一项" in p for p in problems(result)))

    def test_enum_duplicate_and_empty_roles(self):
        tf(self.decl, "listLeads")["effect"] = "readonly"
        self.decl["pages"][1]["key"] = "leadPage"
        self.decl["roles"][0]["permissions"].append("leadread")
        text = "\n".join(problems(check(self.decl)))
        self.assertIn("只能是 read 或 write", text)
        self.assertIn("标识（key）和第 1 项重复", text)
        self.assertIn("不是「资源.动作」的写法", text)
        self.decl["roles"] = []
        self.assertIn("角色（roles）是空数组", "\n".join(problems(check(self.decl))))

    def test_reference_errors(self):
        self.decl["automations"][0]["call"] = "weeklyDigest"
        self.decl["pages"][0]["calls"].append("exportLeads")
        tf(self.decl, "assignLead")["permission"] = "lead.transfer"
        self.decl["tables"][0]["partition"]["by"] = "city"
        tf(self.decl, "logFollowup")["scope"] = {"team": "team_id"}
        tf(self.decl, "listLeads")["uses"]["reads"].append("contracts")
        tf(self.decl, "listLeads")["uses"]["writes"] = ["leads"]
        text = "\n".join(problems(check(self.decl)))
        self.assertIn("「weeklyDigest」不存在", text)
        self.assertIn("「exportLeads」不存在", text)
        self.assertIn("「lead.transfer」不在任何角色里", text)
        self.assertIn("划分用的资源控制点「city」没有定义", text)
        self.assertIn("范围限制用的资源控制点「team」没有定义", text)
        self.assertIn("「contracts」不是已定义的数据表", text)
        self.assertIn("read，却列了写的表", text)

    def test_scope_without_resource_controls_is_rejected(self):
        self.decl["resourceControls"] = {"none": "只有一个团队"}
        text = "\n".join(problems(check(self.decl)))
        self.assertIn("划分用的资源控制点「region」没有定义", text)
        self.assertIn("范围限制用的资源控制点「region」没有定义", text)
        self.decl["resourceControls"] = {"none": ""}
        self.assertIn("没写原因", "\n".join(problems(check(self.decl))))

    def test_fixed_done_value_only_for_plain_reads(self):
        for key, change in (
            ("assignLead", {}),
            ("listLeads", {"tools": ["企业工商信息查询"]}),
            ("listLeads", {"agents": ["线索打分"]}),
        ):
            decl = copy.deepcopy(self.decl)
            flow = tf(decl, key)
            flow["doneWhen"] = FIXED
            flow["uses"].update(change)
            text = "\n".join(problems(check(decl)))
            self.assertIn(f"固定取值「{FIXED}」", text, key)
        self.assertTrue(check(self.decl)["ok"])

    def test_names_must_be_chinese(self):
        self.decl["pages"][0]["name"] = "Leads"
        tf(self.decl, "dailyDigest")["uses"]["tools"] = ["dingtalk_notify"]
        text = "\n".join(problems(check(self.decl)))
        self.assertIn("「Leads」里没有中文", text)
        self.assertIn("「dingtalk_notify」里没有中文", text)

    def test_unknown_items_are_rejected(self):
        self.decl["owner"] = "张三"
        tf(self.decl, "listLeads")["donewhen"] = "拼错了"
        text = "\n".join(problems(check(self.decl)))
        self.assertIn("多出声明里没有的项：owner", text)
        self.assertIn("多出声明里没有的项：donewhen", text)

    def test_each_notice(self):
        self.decl["taskflows"].append({
            "key": "exportLeads", "name": "导出线索", "summary": "把线索导出成表格", "input": ["region"], "output": "表格文件",
            "effect": "read", "permission": "lead.export", "scope": {"none": "导出给主管自己存档"}, "doneWhen": FIXED,
            "uses": {"tools": [], "agents": [], "reads": ["leads"], "writes": []},
        })
        self.decl["roles"][1]["permissions"] += ["lead.export", "lead.delete"]
        self.decl["tables"].append({"key": "contracts", "name": "合同", "description": "成交后的合同",
                                    "partition": {"none": "合同全公司共用"}})
        self.decl["resourceControls"].append({"key": "team", "name": "小组", "description": "区域下的销售小组"})
        self.decl["automations"].append({"key": "dailyList", "name": "每日线索清单", "schedule": "每天 9 点",
                                         "call": "listLeads", "notifyOnIncomplete": "销售本人"})
        result = check(self.decl)
        self.assertTrue(result["ok"], result["must"])
        notices = problems(result, "notice")
        text = "\n".join(notices)
        self.assertIn("exportLeads", text)
        self.assertIn("没有任何页面或自动任务发起它", text)
        self.assertIn("没有任何 TaskFlow 读或写这张表", text)
        self.assertIn("没有任何数据表按它划分", text)
        self.assertIn("权限点「lead.delete」没有任何 TaskFlow 使用", text)
        self.assertIn("范围限制（scope）里却没有「region」", text)
        self.assertIn("完成标准是固定取值", text)
        self.assertEqual(len(notices), 6)
        # 给开发者看的那句不带标识
        for n in result["notice"]:
            self.assertNotRegex(n["plain"], r"[A-Za-z]")

    def test_placeholder_words_must_be_asked_first(self):
        self.decl["app"]["users"] = "待开发者回答（Q1）：三种人里由谁来用"
        tf(self.decl, "assignLead")["doneWhen"] = "待定"
        tf(self.decl, "dailyDigest")["uses"]["tools"] = ["TODO"]
        self.decl["automations"] = {"none": "同上"}
        self.decl["pages"][0]["calls"].append("dailyDigest")
        self.decl["roles"][0]["name"] = "销售（暂无）"
        result = check(self.decl)
        holes = [x for x in result["must"] if "占位字样" in x["problem"]]
        self.assertEqual({x["entity"] for x in holes}, {"应用", "TaskFlow", "自动任务", "角色"})
        self.assertEqual(len(holes), 5)
        self.assertTrue(all(x["fix"] == "这一项还没问清：先问开发者，答完再填" for x in holes))
        text = "\n".join(problems(result))
        self.assertIn("使用对象（users）", text)
        self.assertIn("完成标准（doneWhen）", text)
        self.assertIn("用到的东西（uses.tools）", text)
        self.assertIn("不适用的原因（automations.none）", text)

    def test_quoted_business_words_are_not_placeholders(self):
        tf(self.decl, "assignLead")["doneWhen"] = "线索状态从「待确认」变成「跟进中」，负责人改成选定的销售"
        self.assertTrue(check(self.decl)["ok"])

    def test_gap_is_noticed_and_goes_to_confirm(self):
        self.decl["resourceControls"] = {"none": "要的：两个区域的主管各看各的线索；做不到：平台上每人各用一份，没法按区域分权；替代：每个区域的主管各装一份"}
        for table in self.decl["tables"]:
            table["partition"] = {"none": "跟着上面的做法，每份只有一个区域的数据"}
        for flow in self.decl["taskflows"]:
            flow["scope"] = {"none": "每份只有一个区域的数据"}
        result = check(self.decl)
        self.assertTrue(result["ok"], result["must"])
        gaps = [x for x in result["notice"] if "落差" in x["problem"]]
        self.assertEqual(len(gaps), 1)
        self.assertIn("你要的是两个区域的主管各看各的线索", gaps[0]["plain"])
        self.assertIn("替代做法是每个区域的主管各装一份", gaps[0]["plain"])
        text = node_call(SCRIPT, "confirm", self.decl)
        self.assertIn("数据怎么分：你要的是两个区域的主管各看各的线索", text.split("## 需要你留意的")[1])
        self.decl["app"]["users"] = "要的：销售和主管分开用；做不到：平台没有团队；"
        self.assertIn("缺：替代", "\n".join(problems(check(self.decl))))

    def test_platform_only_reason_is_noticed(self):
        self.decl["resourceControls"] = {"none": "平台上每个使用者用自己的一份数据，不需要划分"}
        for table in self.decl["tables"]:
            table["partition"] = {"none": "只有一个区域"}
        for flow in self.decl["taskflows"]:
            flow["scope"] = {"none": "只有一个区域"}
        result = check(self.decl)
        self.assertTrue(result["ok"])
        self.assertTrue(any("只写了平台怎么做" in x["problem"] for x in result["notice"]))


class DeclarationOutputTests(unittest.TestCase):
    def setUp(self):
        self.decl = copy.deepcopy(FIXTURE)

    def test_confirm_uses_business_words_only(self):
        text = node_call(SCRIPT, "confirm", self.decl)
        for heading in ("## 这个应用", "## 谁能用、各能做什么", "## 数据怎么分", "## 有哪些页面、各能做什么",
                        "## 每件事做到什么算完成", "## 自动任务", "## 需要你留意的"):
            self.assertIn(heading, text)
        self.assertIn("- 不能做：「分配线索」、「发每日跟进早报」", text)
        self.assertIn("「线索」（每条线索一行：客户、联系人、负责人、阶段）：按「区域」分开", text)
        self.assertIn("没做完时通知该区域的销售主管", text)
        self.assertIn("- 做到什么算完成：查到并显示出来就算完成", text)
        self.assertNotIn(FIXED, text)
        # 没有标识、英文字段名、权限点、TaskFlow 这类词
        self.assertIsNone(re.search(r"[A-Za-z]", text), re.findall(r"[A-Za-z_.]+", text))

    def test_confirm_lists_notices_in_business_words(self):
        self.decl["roles"][0]["permissions"].append("lead.delete")
        self.decl["automations"] = {"none": "主管自己在页面上看"}
        self.decl["pages"][0]["calls"].append("dailyDigest")
        text = node_call(SCRIPT, "confirm", self.decl)
        self.assertIn("没有自动任务：主管自己在页面上看", text)
        self.assertIn("1. 「销售」有一项权限没有对应任何一件事", text)
        self.assertIsNone(re.search(r"[A-Za-z]", text))

    def test_confirm_and_walkthrough_refuse_when_must_fix(self):
        self.decl["app"]["name"] = ""
        for fn in ("confirm", "walkthrough"):
            with self.assertRaises(NodeValueError) as ctx:
                node_call(SCRIPT, fn, self.decl)
            self.assertIn("必须改", str(ctx.exception))

    def test_walkthrough_items_and_counts(self):
        result = node_call(SCRIPT, "walkthrough", self.decl)
        self.assertEqual(result["counts"], {"功能": 7, "工具": 1, "权限": 9, "自动任务": 2})
        self.assertEqual(result["total"], 19)
        items = {i["id"]: i for i in result["items"]}
        self.assertEqual(len(items), 19, "编号不能重复")
        self.assertEqual(items["权限-sales-assignLead"]["expect"], "被拒绝")
        # 页面上的功能项已用第一个能做的角色走过，这个角色的「能做」不再单列；别的角色照列
        self.assertIn("以「销售主管」的身份", items["功能-leadPage-assignLead"]["how"])
        self.assertNotIn("权限-manager-assignLead", items)
        self.assertNotIn("权限-sales-listLeads", items)
        self.assertEqual(items["权限-manager-listLeads"]["expect"], "能做")
        # 只由自动任务发起的，没有页面功能项证明，「能做」照列
        self.assertEqual(items["权限-manager-dailyDigest"]["expect"], "能做")
        self.assertNotIn("功能-morningDigest-dailyDigest", items)
        self.assertIn("取不到", items["权限-listLeads-region-越界"]["expect"])
        self.assertIn("「销售」身份", items["权限-listLeads-region-越界"]["how"])
        # 写数据或用工具的才有「做不成」；只读不用工具的没有
        fails = sorted(k for k in items if k.endswith("做不成"))
        self.assertEqual(fails, ["功能-assignLead-做不成", "功能-dailyDigest-做不成", "功能-logFollowup-做不成"])
        self.assertIn("下一步该做什么", items["功能-assignLead-做不成"]["expect"])
        # 「做不成」点名实际用到的工具、Agent 和表
        self.assertIn("让「钉钉工作通知」返回失败", items["功能-dailyDigest-做不成"]["how"])
        self.assertIn("让「跟进要点整理」给不出结果", items["功能-logFollowup-做不成"]["how"])
        self.assertIn("写「跟进记录」、「线索」时被拒", items["功能-logFollowup-做不成"]["how"])
        self.assertIn(FIXED, items["功能-leadPage-listLeads"]["expect"])
        self.assertIn("线索的负责人改成选定的销售", items["功能-leadPage-assignLead"]["expect"])
        self.assertIn("返回真实数据", items["工具-dailyDigest-钉钉工作通知"]["expect"])
        self.assertIn("主管在钉钉收到早报", items["自动任务-morningDigest-立即"]["expect"])
        self.assertIn("手动触发", items["自动任务-morningDigest-立即"]["how"])
        self.assertIn("该区域的销售主管", items["自动任务-morningDigest-到点"]["expect"])
        self.assertIn("每个工作日早上 8:30", items["自动任务-morningDigest-到点"]["how"])
        # 编号只由标识组成：同一份声明再跑一次完全一样
        self.assertEqual(node_call(SCRIPT, "walkthrough", self.decl), result)

    def test_walkthrough_without_scope_or_automation(self):
        self.decl["automations"] = {"none": "不需要"}
        self.decl["pages"][0]["calls"].append("dailyDigest")
        for flow in self.decl["taskflows"]:
            flow["scope"] = {"none": "只有一个区域"}
        result = node_call(SCRIPT, "walkthrough", self.decl)
        self.assertEqual(result["counts"], {"功能": 8, "工具": 1, "权限": 4, "自动任务": 0})
        markdown = node_call(SCRIPT, "walkthroughMarkdown", result)
        self.assertIn("| 合计 | 13 |", markdown)

    def test_single_role_has_no_row_of_can_do(self):
        self.decl["roles"] = [{"key": "owner", "name": "使用者", "permissions": ["lead.read", "lead.assign", "followup.write", "report.read"]}]
        result = node_call(SCRIPT, "walkthrough", self.decl)
        expects = [i["expect"] for i in result["items"] if i["category"] == "权限" and not i["id"].endswith("越界")]
        self.assertEqual(expects, ["能做"])  # 只剩只由自动任务发起的那一件


class DeclarationCliTests(unittest.TestCase):
    def test_init_refuses_to_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "declaration.json"
            calls = node_calls(SCRIPT, [{"fn": "init", "args": [str(path)]}, {"fn": "init", "args": [str(path)]}])
            unwrap(calls[0])
            self.assertEqual(calls[1]["err"], "ValueError")
            self.assertIn("不覆盖", calls[1]["msg"])
            path.write_text('{"version": 1}', encoding="utf-8")
            run = run_cli("init", str(path))
            self.assertEqual(run.returncode, 1)
            self.assertEqual(path.read_text(encoding="utf-8"), '{"version": 1}')

    def test_cli_exit_codes_and_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            good = Path(tmp) / "good.json"
            good.write_text(json.dumps(FIXTURE, ensure_ascii=False), encoding="utf-8")
            run = run_cli("check", str(good), "--json")
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertTrue(json.loads(run.stdout)["ok"])
            run = run_cli("walkthrough", str(good), "--json")
            self.assertEqual(json.loads(run.stdout)["total"], 19)
            self.assertEqual(run_cli("confirm", str(good)).returncode, 0)

            blank = Path(tmp) / "blank.json"
            self.assertEqual(run_cli("init", str(blank)).returncode, 0)
            run = run_cli("check", str(blank))
            self.assertEqual(run.returncode, 1)
            self.assertIn("必须改", run.stdout)
            self.assertEqual(run_cli("confirm", str(blank)).returncode, 1)
            self.assertEqual(run_cli("walkthrough", str(blank)).returncode, 1)

            broken = Path(tmp) / "broken.json"
            broken.write_text("{", encoding="utf-8")
            run = run_cli("check", str(broken))
            self.assertEqual(run.returncode, 1)
            self.assertIn("不是合法 JSON", run.stderr)
            self.assertEqual(run_cli("check").returncode, 2)


def names(group):
    return [x["name"] for x in group]


class DeclarationImpactTests(unittest.TestCase):
    def setUp(self):
        self.decl = copy.deepcopy(FIXTURE)

    def impact(self, target):
        return node_call(SCRIPT, "impact", self.decl, target)

    def test_table_reaches_taskflows_pages_automations_roles(self):
        r = self.impact("线索")
        self.assertEqual(r["target"]["type"], "数据表")
        self.assertEqual(names(r["direct"]["资源控制点"]), ["区域"])
        relations = {x["name"]: x["relation"] for x in r["direct"]["TaskFlow"]}
        self.assertEqual(relations, {"查看线索": "读", "分配线索": "读、写", "记录跟进": "读、写", "发每日跟进早报": "读"})
        self.assertEqual(names(r["affected"]["页面"]), ["线索列表", "跟进"])
        self.assertEqual(names(r["affected"]["自动任务"]), ["每日早报"])
        self.assertEqual(names(r["affected"]["角色"]), ["销售", "销售主管"])
        self.assertEqual(len(r["rewalk"]), 19)  # 四件事都读这张表
        self.assertIsNone(re.search(r"[A-Za-z]", r["plain"]))

    def test_tool_reaches_only_its_taskflow(self):
        r = self.impact("钉钉工作通知")
        self.assertEqual(r["target"]["type"], "工具")
        self.assertEqual(names(r["affected"]["TaskFlow"]), ["发每日跟进早报"])
        self.assertEqual(names(r["affected"]["自动任务"]), ["每日早报"])
        self.assertNotIn("页面", r["affected"])
        self.assertEqual(r["rewalk"], ["功能-dailyDigest-做不成", "工具-dailyDigest-钉钉工作通知",
                                       "权限-sales-dailyDigest", "权限-manager-dailyDigest", "权限-dailyDigest-region-越界",
                                       "自动任务-morningDigest-立即", "自动任务-morningDigest-到点"])
        markdown = node_call(SCRIPT, "impactMarkdown", r)
        self.assertIn("## 改完要重走的走查项（7 项）", markdown)

    def test_resource_control_permission_role_and_page(self):
        r = self.impact("区域")
        self.assertEqual(names(r["affected"]["数据表"]), ["线索", "跟进记录"])
        self.assertEqual(len(r["affected"]["TaskFlow"]), 4)
        r = self.impact("lead.assign")
        self.assertEqual(r["target"]["type"], "权限点")
        self.assertEqual(names(r["affected"]["TaskFlow"]), ["分配线索"])
        self.assertEqual(names(r["affected"]["角色"]), ["销售主管"])
        r = self.impact("角色:sales")
        self.assertEqual(r["affected"], {})
        self.assertIn("权限-sales-assignLead", r["rewalk"])
        self.assertIn("功能-followupPage-logFollowup", r["rewalk"])  # 以「销售」身份走的功能项
        self.assertNotIn("功能-leadPage-assignLead", r["rewalk"])
        r = self.impact("跟进")
        self.assertEqual(r["target"]["type"], "页面")
        self.assertEqual(r["rewalk"], ["功能-followupPage-listLeads", "功能-followupPage-logFollowup"])

    def test_ambiguous_or_missing_lists_candidates(self):
        self.decl["pages"][0]["key"] = "leads"
        with self.assertRaises(NodeValueError) as ctx:
            self.impact("leads")
        self.assertIn("有重名", str(ctx.exception))
        self.assertIn("数据表:leads（线索）", str(ctx.exception))
        self.assertIn("页面:leads（线索列表）", str(ctx.exception))
        self.assertEqual(self.impact("页面:leads")["target"]["name"], "线索列表")
        with self.assertRaises(NodeValueError) as ctx:
            self.impact("线")
        self.assertIn("相近的有", str(ctx.exception))
        with self.assertRaises(NodeValueError) as ctx:
            self.impact("报价单")
        self.assertIn("找不到", str(ctx.exception))


class DeclarationDiffTests(unittest.TestCase):
    def setUp(self):
        self.result = node_call(SCRIPT, "diff", FIXTURE, FIXTURE_V2)

    def test_what_changed(self):
        kinds = {(c["kind"], c["entity"], c["key"]) for c in self.result["changes"]}
        self.assertEqual(kinds, {
            ("修改", "角色", "sales"), ("修改", "角色", "manager"), ("新增", "数据表", "contracts"),
            ("新增", "TaskFlow", "signContract"), ("修改", "TaskFlow", "dailyDigest"), ("修改", "页面", "leadPage"),
        })
        digest = next(c for c in self.result["changes"] if c["key"] == "dailyDigest")
        tools = next(f for f in digest["fields"] if f["field"] == "uses.tools")
        self.assertEqual((tools["from"], tools["to"]), (["钉钉工作通知"], ["企业微信消息"]))
        plain = "\n".join(self.result["plain"])
        self.assertIn("「销售」不再能做「记录跟进」", plain)
        self.assertIn("「销售主管」现在能做「登记合同」", plain)
        self.assertIn("新增一件事「登记合同」", plain)
        self.assertIn("用到的外部工具加上「企业微信消息」，去掉「钉钉工作通知」", plain)
        self.assertIn("「线索列表」页面上能做的事加上「登记合同」", plain)
        self.assertIsNone(re.search(r"[A-Za-z]", plain))

    def test_who_is_affected(self):
        a = self.result["affected"]
        self.assertEqual(sorted(names(a["TaskFlow"])), sorted(["登记合同", "发每日跟进早报"]))
        self.assertEqual(names(a["页面"]), ["线索列表"])
        self.assertEqual(names(a["自动任务"]), ["每日早报"])
        self.assertEqual(sorted(names(a["角色"])), sorted(["销售", "销售主管"]))

    def test_walkthrough_buckets(self):
        w = self.result["walkthrough"]
        # 销售去掉记录跟进后，记录跟进的功能项改由销售主管走：销售那一项变成「被拒绝」新列出，主管的「能做」不再单列
        self.assertEqual(sorted(w["added"]), sorted(["功能-leadPage-signContract", "功能-signContract-做不成", "工具-dailyDigest-企业微信消息",
                                                     "权限-sales-logFollowup", "权限-sales-signContract", "权限-signContract-region-越界"]))
        self.assertEqual(sorted(w["removed"]), sorted(["工具-dailyDigest-钉钉工作通知", "权限-manager-logFollowup"]))
        self.assertEqual(sorted(w["changed"]), sorted(["功能-followupPage-logFollowup", "功能-dailyDigest-做不成",
                                                       "权限-logFollowup-region-越界", "自动任务-morningDigest-立即"]))
        self.assertEqual(sorted(w["rewalk"]), sorted(["功能-leadPage-listLeads", "功能-leadPage-assignLead", "权限-sales-dailyDigest",
                                                      "权限-manager-dailyDigest", "权限-dailyDigest-region-越界", "自动任务-morningDigest-到点"]))
        self.assertEqual(len(w["untouched"]), 7)
        self.assertEqual(w["total"], 23)
        self.assertIn("功能-followupPage-listLeads", w["untouched"])
        markdown = node_call(SCRIPT, "diffMarkdown", self.result)
        for heading in ("## 改了什么", "可直接放进更新说明的文字：", "## 影响到谁", "## 走查项"):
            self.assertIn(heading, markdown)
        self.assertIn("- 不受影响，可不重走：7 项", markdown)

    def test_same_declaration_has_no_changes(self):
        r = node_call(SCRIPT, "diff", FIXTURE, FIXTURE)
        self.assertEqual(r["changes"], [])
        self.assertEqual(r["walkthrough"]["rewalk"], [])
        self.assertEqual(len(r["walkthrough"]["untouched"]), 19)

    def test_removed_taskflow_reaches_old_entries(self):
        new = copy.deepcopy(FIXTURE)
        new["taskflows"] = [t for t in new["taskflows"] if t["key"] != "assignLead"]
        new["pages"][0]["calls"] = ["listLeads"]
        new["roles"][1]["permissions"].remove("lead.assign")
        r = node_call(SCRIPT, "diff", FIXTURE, new)
        self.assertIn(("删除", "assignLead"), {(c["kind"], c["key"]) for c in r["changes"]})
        self.assertIn("去掉一件事「分配线索」", r["plain"])
        self.assertIn("功能-leadPage-assignLead", r["walkthrough"]["removed"])
        self.assertIn("线索列表", names(r["affected"]["页面"]))

    def test_diff_refuses_when_either_side_must_fix(self):
        bad = copy.deepcopy(FIXTURE_V2)
        bad["app"]["name"] = ""
        with self.assertRaises(NodeValueError) as ctx:
            node_call(SCRIPT, "diff", FIXTURE, bad)
        self.assertIn("改后的一份", str(ctx.exception))
        with self.assertRaises(NodeValueError) as ctx:
            node_call(SCRIPT, "diff", bad, FIXTURE)
        self.assertIn("改前的一份", str(ctx.exception))

    def test_cli(self):
        old, new = ROOT / "tests/fixtures/declaration_leads.json", ROOT / "tests/fixtures/declaration_leads_v2.json"
        run = run_cli("diff", str(old), str(new), "--json")
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(len(json.loads(run.stdout)["walkthrough"]["untouched"]), 7)
        run = run_cli("impact", str(old), "钉钉工作通知")
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("# 影响范围：工具「钉钉工作通知」", run.stdout)
        run = run_cli("impact", str(old), "线")
        self.assertEqual(run.returncode, 1)
        self.assertIn("相近的有", run.stderr)
        self.assertEqual(run_cli("impact", str(old)).returncode, 2)
        with tempfile.TemporaryDirectory() as tmp:
            blank = Path(tmp) / "blank.json"
            run_cli("init", str(blank))
            run = run_cli("diff", str(old), str(blank))
            self.assertEqual(run.returncode, 1)
            self.assertIn(str(blank), run.stderr)


if __name__ == "__main__":
    unittest.main()
