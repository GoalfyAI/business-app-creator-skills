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
        self.assertEqual(result["counts"], {"功能": 8, "工具": 1, "权限": 12, "自动任务": 1})
        self.assertEqual(result["total"], 22)
        items = {i["id"]: i for i in result["items"]}
        self.assertEqual(len(items), 22, "编号不能重复")
        self.assertEqual(items["权限-sales-assignLead"]["expect"], "被拒绝")
        self.assertEqual(items["权限-manager-assignLead"]["expect"], "能做")
        self.assertIn("取不到", items["权限-listLeads-region-越界"]["expect"])
        self.assertIn("「销售」身份", items["权限-listLeads-region-越界"]["how"])
        # 写数据或用工具的才有「做不成」；只读不用工具的没有
        fails = sorted(k for k in items if k.endswith("做不成"))
        self.assertEqual(fails, ["功能-assignLead-做不成", "功能-dailyDigest-做不成", "功能-logFollowup-做不成"])
        self.assertIn("下一步该做什么", items["功能-assignLead-做不成"]["expect"])
        self.assertIn(FIXED, items["功能-leadPage-listLeads"]["expect"])
        self.assertIn("线索的负责人改成选定的销售", items["功能-leadPage-assignLead"]["expect"])
        self.assertIn("返回真实数据", items["工具-dailyDigest-钉钉工作通知"]["expect"])
        self.assertIn("该区域的销售主管", items["自动任务-morningDigest"]["expect"])
        # 编号只由标识组成：同一份声明再跑一次完全一样
        self.assertEqual(node_call(SCRIPT, "walkthrough", self.decl), result)

    def test_walkthrough_without_scope_or_automation(self):
        self.decl["automations"] = {"none": "不需要"}
        self.decl["pages"][0]["calls"].append("dailyDigest")
        for flow in self.decl["taskflows"]:
            flow["scope"] = {"none": "只有一个区域"}
        result = node_call(SCRIPT, "walkthrough", self.decl)
        self.assertEqual(result["counts"], {"功能": 8, "工具": 1, "权限": 8, "自动任务": 0})
        markdown = node_call(SCRIPT, "walkthroughMarkdown", result)
        self.assertIn("| 合计 | 17 |", markdown)


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
            self.assertEqual(json.loads(run.stdout)["total"], 22)
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


if __name__ == "__main__":
    unittest.main()
