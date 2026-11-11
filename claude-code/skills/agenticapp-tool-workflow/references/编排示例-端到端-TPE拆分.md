# 端到端制作参考案例（二）：编排型 TPE 拆分

读完 [编排示例-端到端-业务事实与路线.md](编排示例-端到端-业务事实与路线.md) 后接着读。仅供参考，不是模板，业务字段、资产名称、TPE ID、工具名和 Schema 都不能照抄。

本文分 4 份：[编排示例-端到端-业务事实与路线.md](编排示例-端到端-业务事实与路线.md)、[编排示例-端到端-TPE拆分.md](编排示例-端到端-TPE拆分.md)、[编排示例-端到端-业务路线.md](编排示例-端到端-业务路线.md)、[编排示例-端到端-应用与验收.md](编排示例-端到端-应用与验收.md)。

## 5. 编排型 TPE 拆分

本案例拆成三条编排型 TPE，拆分原因是职责、复用、输入输出和验证边界不同，而不是因为步骤数达到某个阈值。

### 5.1 编排型 TPE 1：`campaign_strategy_prepare`（示意名）

职责：读取本轮门店资料和约束，返回结构化策略，不生成最终文件。

示意输入：

```json
{
  "type": "object",
  "required": ["store_profile", "goal", "budget_yuan", "forbidden_claims"],
  "properties": {
    "store_profile": {"type": "string"},
    "goal": {"type": "string"},
    "budget_yuan": {"type": "integer", "minimum": 1},
    "audience_preferences": {"type": "array", "items": {"type": "string"}},
    "brand_material_path": {"type": "string", "format": "workspace-file-path"},
    "forbidden_claims": {"type": "array", "items": {"type": "string"}}
  },
  "additionalProperties": false
}
```

示意输出：

```json
{
  "type": "object",
  "required": ["strategy", "risk_flags"],
  "properties": {
    "strategy": {
      "type": "object",
      "required": ["positioning", "audiences", "creative_directions", "budget_plan", "schedule"],
      "properties": {
        "positioning": {"type": "string"},
        "audiences": {"type": "array", "items": {"type": "object"}},
        "creative_directions": {"type": "array", "items": {"type": "object"}},
        "budget_plan": {"type": "object"},
        "schedule": {"type": "array", "items": {"type": "object"}}
      }
    },
    "risk_flags": {"type": "array", "items": {"type": "object"}}
  }
}
```

制作要点：

- `brand_material_path` 若由智能应用上传，界面字段使用 `format:file/image`，宿主上传后再把 Workspace 路径提交给路线；
- 调用 FastAgent 时，真实名称、参数和 `_output` 必须来自当前资产和取样；
- FastAgent 返回空数组时，bubble 不能证明数组元素处理路径已经通过；
- 风险项是正式输出的一部分，不能只写日志或自然语言备注。

### 5.2 编排型 TPE 2：`campaign_package_build`（示意名）

职责：消费结构化策略，生成最终可审阅文件。

```json
{
  "input_schema": {
    "type": "object",
    "required": ["strategy", "risk_flags"],
    "properties": {
      "strategy": {"type": "object"},
      "risk_flags": {"type": "array", "items": {"type": "object"}}
    }
  },
  "output_schema": {
    "type": "object",
    "required": ["summary", "package_path", "risk_flags"],
    "properties": {
      "summary": {"type": "string"},
      "package_path": {"type": "string", "format": "workspace-file-path"},
      "risk_flags": {"type": "array", "items": {"type": "object"}}
    }
  }
}
```

脚本把中间内容写入 `ctx.process_dir`，把最终方案写入 `ctx.output_dir`，最终直接返回对象。不得返回 URL、`/tmp`、固定 `/workspace/output` 或构建期文件。

### 5.3 编排型 TPE 3：`campaign_package_revise`（示意名）

职责：读取原方案文件和修改意见，生成新的候选文件。

```json
{
  "input_schema": {
    "type": "object",
    "required": ["source_package_path", "revision_notes"],
    "properties": {
      "source_package_path": {"type": "string", "format": "workspace-file-path"},
      "revision_notes": {"type": "string", "minLength": 1}
    }
  },
  "output_schema": {
    "type": "object",
    "required": ["summary", "package_path", "revision_applied"],
    "properties": {
      "summary": {"type": "string"},
      "package_path": {"type": "string", "format": "workspace-file-path"},
      "revision_applied": {"type": "array", "items": {"type": "string"}}
    }
  }
}
```

修订输出必须写新文件。若原文件不可信、不存在或不属于当前 Workspace，运行应明确失败，不得生成空报告冒充修订成功。
