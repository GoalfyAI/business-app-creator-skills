from pathlib import Path
from zipfile import ZipFile

import pytest

ROOT = Path(__file__).parents[1]
GUIDANCE = "reference/业务路线.md"
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
def form_guidance(request):
    """从唯一源、四个平台和两个安装包读取实际分发的表单指导。"""
    surface = ROOT / request.param
    if surface.suffix == ".zip":
        with ZipFile(surface) as archive:
            text = archive.read(GUIDANCE).decode("utf-8")
    else:
        text = (surface / GUIDANCE).read_text(encoding="utf-8")
    return text.split("### 表单定义放哪", 1)[1].split("### ", 1)[0]


def test_entry_mapping_forbids_direct_default(form_guidance):
    """入口映射遵循当前字段合同，不再指导提交未知的 default 字段。"""
    assert "`source/node_id/path/transform`" in form_guidance
    assert "来源只能是 `formdata`" in form_guidance
    assert "**禁止**在映射规则里直接写 `default` 字段" in form_guidance
    assert "入口映射里需要默认值的字段用映射的 `default` 声明" not in form_guidance


def test_entry_defaults_are_materialized_before_submission(form_guidance):
    """声明或保存不能替代真实填值，也不能承诺未经核验的入口 transform 能力。"""
    assert "Schema 的 `default` 只是声明，不会自动填充实际输入" in form_guidance
    assert "表单或调用方**必须**在提交前把默认值写入实际表单数据" in form_guidance
    assert "首次路线冒泡用 `workflow_input` 传入已填值的入口数据" in form_guidance
    assert "不要把 `transform` 当作入口运行时自动补默认值的保证" in form_guidance
