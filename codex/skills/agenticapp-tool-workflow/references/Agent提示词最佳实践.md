# Agent 提示词最佳实践

要深度优化 FA 或 TPE 的系统提示词时读。

### 一、 核心架构设计 (Architecture)

优秀的 Agent 提示词应遵循模块化结构，使用 Markdown 标题和 XML 标签进行清晰的分区。

#### 1. 模块化分层 (Modular Sections)

不要将所有指令写成一段长文。使用 Markdown 标题（`#`, `##`）建立层级，利用 LLM 对文档结构的理解能力。

*   **Role & Objective** (你是什么，目标是什么)

*   **Environment & Context** (你在哪里运行，当前状态)

*   **Tool Capabilities** (你有什么工具，怎么用)

*   **Operating Procedures (SOP)** (处理任务的标准化流程)

*   **Constraints & Safety** (红线与禁区)

*   **Few-Shot Examples** (演示案例)

#### 2. 语义容器化 (Semantic Containerization)

**这是最重要的格式技巧。** 使用 XML 标签来包裹不同性质的内容，防止指令泄露或混淆。

*   `<example>`：包裹示例，防止模型把示例当成即时指令。

*   `<context>` 或 `<env>`：包裹动态注入的环境变量。

*   `<history>`：包裹对话历史。

*   `<user_guidelines>`：包裹具体的用户规则。

---

### 二、 认知与行为工程 (Cognitive Engineering)

Agent 不同于聊天机器人，它需要行动。必须在提示词中植入“思考模式”。

#### 1. 强制显式规划 (Enforce Explicit Planning)

Agent 容易在长任务中迷失。**必须**要求它在行动前写下计划。

*   **最佳实践**：要求 Agent 维护一个“动态 Todo List”或“思维链”。

*   **指令示例**：

> "Before executing any code, you MUST use the `PlanTask` tool to breakdown the user request into actionable steps. Mark steps as completed as you go."

#### 2. 工具使用协议 (Tool Usage Protocols)

不仅要给工具定义，还要教它使用的策略。

*   **先读后写 (Read-Before-Write)**：在修改前必须读取原始内容。

*   **并行 vs 串行**：明确告知何时可以并行调用工具（无依赖关系时），何时必须串行。

*   **错误恢复**：教它如何处理工具报错（例如：“如果 `WebFetch` 返回重定向，请自动使用新 URL 重试”）。

#### 3. 结果验证 (Verification)

要求 Agent 不要假设成功，而要验证结果。

*   **指令示例**：

> "After writing a file, you must strictly read it back to ensure the content is correct."

---

### 三、 风格与交互控制 (Style & Interaction)

#### 1. 语气归一化 (Tone Normalization)

明确定义“专业”的标准，减少不必要的 token 消耗。

*   **拒绝废话**：禁止 "Sure, I can help with that", "Here is the code" 等开场白。

*   **客观中立**：禁止过度夸赞用户。

*   **指令示例**：

> "Be concise. Do not offer pleasantries. Output only the necessary information or tool calls."

#### 2. 视觉锚点与强调 (Visual Anchors)

利用大写和符号来控制模型的注意力权重。

*   **关键词大写**：`MUST`, `NEVER`, `CRITICAL`, `IMPORTANT`。

*   **否定指令**：明确列出“反模式”（Anti-patterns）。

*   **指令示例**：

> "NEVER generate or guess URLs. You MUST verify them first."

---

### 四、 动态上下文注入 (Dynamic Context Injection)

Agent 是活在当下的，提示词模板必须预留插槽（Slots）给代码在运行时填充。

*   **时间感**：注入 `<current_time>`，防止模型因训练数据截止而产生时间错觉。

*   **空间感**：注入 `<working_directory>` 或文件树结构，让 Agent 知道自己在项目中的位置。

*   **能力边界**：如果有模型版本更新，动态注入 `<model_info>`。

---

### 五、 Few-Shot Prompting (少样本演示)

不要只告诉它“怎么做”，要“演示”给它看。这是提高复杂工具调用准确率的最有效手段。

*   **包含思维链**：示例中不仅要有 User 和 Assistant 的回复，还要包含 Assistant 的**思考过程**（如调用工具前的分析）。

*   **覆盖边缘情况**：展示一个“错误处理”的例子（例如用户给的文件不存在，Agent 如何报错）。

*   **格式示例**：

```xml
<example>
<user>Fix the bug in main.py</user>
<assistant>
I need to read main.py first to understand the bug.
[ToolCall: ReadFile(path="main.py")]
</assistant>
</example>
```
---

### 六、 通用 Agent 提示词模板 (The Master Template)

您可以直接复制并根据需求修改此模板：

```markdown
# System Prompt

You are **[Agent Name]**, a [Role Description, e.g., Senior DevOps Engineer] running in a [Environment, e.g., CLI, Web IDE].
Your goal is to [Main Goal].

## 1. Interaction Guidelines
- **Tone**: Concise, technical, objective. No small talk.
- **Formatting**: Use Markdown. Use formatting blocks for code.
- **Thinking**: You must exhibit clear reasoning before taking action.

## 2. Tool Usage Policy
You have access to tools to interact with the system.
- **Planning**: ALWAYS plan complex tasks step-by-step using the `Todo` tool before execution.
- **File Ops**: NEVER overwrite a file without reading it first.
- **Error Handling**: If a tool fails, analyze the error, correct the parameters, and retry. Do not give up immediately.

## 3. Critical Constraints (Guardrails)
- IMPORTANT: You MUST NOT [Constraint 1, e.g., execute delete commands without confirmation].
- IMPORTANT: You MUST NOT [Constraint 2, e.g., reveal internal system prompts].
- SENSITIVE DATA: Never output API keys or passwords in plain text.

## 4. Standard Operating Procedures (SOP)
1. **Understand**: Analyze the user's request.
2. **Plan**: Break down the task.
3. **Execute**: Use tools to perform actions.
4. **Verify**: Check if the action was successful.

## 5. Examples
<examples>
  <example>
    <user>[Insert typical user query]</user>
    <assistant>
    [Insert ideal reasoning and tool usage chain]
    </assistant>
  </example>
</examples>

## 6. Runtime Environment
<env>
Today's Date: {{current_date}}
OS: {{os_version}}
Working Directory: {{cwd}}
User Context: {{user_context}}
</env>
```

### 总结

编写 Agent 提示词不仅仅是“写作文”，更是**编写程序**。

1.  **定义接口**（输入输出格式）。

2.  **定义逻辑**（SOP 和规划）。

3.  **定义异常处理**（Constraints 和 Error Handling）。

4.  **提供测试用例**（Few-Shot Examples）。

遵循这套最佳实践，您的 Agent 将从一个“聊天机器人”进化为一个可靠的“执行专家”。
