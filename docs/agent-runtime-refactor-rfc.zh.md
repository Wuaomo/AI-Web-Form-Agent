# AI Web Form Agent 运行时重构 RFC

## 1. 文档目的

这份文档提出一条面向 AI Web Form Agent 的底层重构路线。

当前项目已经不只是一个网页表单填写器。它更适合继续演进为一个“由 Agent 驱动、由系统治理、由浏览器执行、由证据验证”的网页工作流运行时。

目标形态如下：

```text
用户目标
  -> Agent 理解任务并规划步骤
  -> Agent 调用工具读取网页、检索资料、生成建议
  -> 系统对工具调用和拟执行动作做风险治理
  -> 用户只审查关键建议和高风险动作
  -> 浏览器执行已批准动作
  -> 系统验证执行结果
  -> trace、截图、benchmark 记录证据
```

这不是一个普通聊天机器人，也不是一个不受控制的全自动浏览器 Agent。目标产品应该是：

```text
受治理的工具调用型浏览器 Agent
```

也就是：模型负责推理、规划和选择工具；应用系统负责边界、审查、执行、验证、持久化和评估。

## 2. 当前项目定位

当前项目最强的定位不是“AI 自动填表”，而是：

```text
一个审查优先的浏览器工作流助手：
它读取网页，提取字段或问题，从用户资料、历史记忆和依据文档中生成建议，要求用户审查，然后把已批准的值填写到真实浏览器中，并验证 DOM 结果、记录执行证据。
```

已有能力包括：

- FastAPI 后端和 SQLite 持久化。
- React/Vite 前端工作台。
- Playwright 浏览器执行。
- 表单字段提取和字段映射。
- PolicyEngine 和 ApprovalGateService。
- 已审查 workflow memory。
- 本地 knowledge sources 和 source-backed answer suggestions。
- 用于 security questionnaire 的 LangGraph runtime。
- 覆盖提取、映射、安全、检索、浏览器 replay 的 benchmark。
- trace、截图、action logs、verification evidence。

这些都是项目的资产。重构不应该推倒重来，而应该把这些能力抽象到更通用的 Agent runtime 里。

## 3. 核心问题

当前项目的问题不是功能太少，而是底层抽象已经跟不上产品方向。

现在代码结构仍然偏向固定 workflow 应用：

```text
workflow_type
  -> 静态 plan
  -> workflow-specific router 分支
  -> workflow-specific 前端渲染
  -> workflow-specific runtime 行为
```

这会带来一个后果：每新增一个场景，例如 job application、vendor onboarding、policy-backed form、government application、insurance claim、CRM portal update，都需要增加新的 workflow type、后端分支、前端判断和测试路径。

更好的方向是：

```text
workflow template 不再是运行时核心，而是 Agent planner 的提示和默认策略。
```

## 4. 当前结构中的主要问题

### 4.1 workflow_type 过早成为核心分发逻辑

现在 `security_questionnaire`、`vendor_onboarding`、`form_fill`、`web_data_extract`、`job_research_summary` 都是有价值的 demo。但问题在于，`workflow_type` 被用作后端 planning、execution 和前端 presentation 的核心判断条件。

这会限制扩展性：

- 新场景需要新分支。
- 前端需要更多 workflow-specific conditionals。
- runtime 很难根据页面内容动态调整计划。
- 用户体验会越来越像“选择模板”，而不是“告诉 Agent 我的目标”。

重构后应该保留 template，但改变它的角色：

```text
重构前：
workflow type 决定整条流程。

重构后：
workflow template 提供 planning hints、默认工具集、默认风险策略和 demo 入口。
```

### 4.2 Tool Registry 还不是执行层

当前 `ToolRegistry` 已经包含了很好的 metadata：

- tool name
- description
- risk level
- approval requirement
- params schema
- preconditions
- produced artifacts
- failure modes
- recovery hints
- evidence requirements

但它现在更像“工具说明书”，还不是真正的 runtime。实际执行逻辑仍然散落在 routers 和 services 里。

目标是把 tool 变成真正可执行的结构：

```text
ToolDefinition
  + input_schema
  + output_schema
  + risk_metadata
  + execute(context, input) -> ToolResult
```

这样以后 Agent 不是调用散落的 service，而是调用统一的 typed tools。

### 4.3 LangGraph runtime 绑定了单一场景

当前 LangGraph runtime 对 security questionnaire 很有帮助，展示了中断、状态、暂停和恢复。但它还不是通用 Agent runtime。

目标应该是一个通用图：

```text
initialize_run
  -> plan_next_step
  -> select_tool
  -> check_governance
  -> maybe_pause_for_review
  -> execute_tool
  -> verify_if_needed
  -> observe_result
  -> continue_or_finish
```

security questionnaire 应该变成这个通用 runtime 的一个 planning preset，而不是唯一 graph。

### 4.4 数据模型过于 form-centric

当前核心模型更像：

```text
Task
  -> FormField
  -> mapped_profile_key
  -> mapped_value
```

这对表单填写很合适，但对更通用的 Agent 行为不够。一个真正的浏览器 Agent runtime 还需要表达：

- tool calls
- tool results
- proposed browser actions
- answer proposals
- evidence items
- review decisions
- verification results
- observations
- plan revisions

表单字段仍然重要，但它应该只是更通用 proposal/action 模型中的一种 target。

### 4.5 前端页面承担了太多 workflow-specific 逻辑

当前前端已经有不错的页面：Dashboard、Create Run、Task Detail、Review Mapping、Approval Center、Memory、Knowledge Sources、Benchmarks。

但 Task Detail 和 Review Mapping 正在承担太多职责：

- workflow 状态展示
- mapping 操作
- runtime 控制
- screenshot 展示
- verification 展示
- trace 展示
- approval requests
- agent reviews
- LLM usage
- job status
- workflow-specific UI

未来前端应该围绕更通用的两个概念重构：

```text
Run Cockpit
Review Queue
```

而不是为每个 workflow 单独堆 UI。

## 5. 目标架构

重构后的核心运行时概念应该是 `AgentRun`。

```text
AgentRun
  goal
  context
  current_plan
  tool_calls
  proposals
  evidence
  review_decisions
  browser_actions
  verification_results
  trace_spans
  final_result
```

高层模块如下：

```text
React Frontend
  -> FastAPI Backend
    -> Agent Runtime API
    -> Agent Planner
    -> Tool Registry
    -> Tool Runtime
    -> Governance Engine
    -> Review Queue
    -> Browser Executor
    -> Evidence Retrieval
    -> Verification Service
    -> Trace Store
    -> Evaluation Harness
    -> SQLite Persistence
```

用户路径变成：

```text
1. 用户输入目标和目标网页。
2. Agent 检查页面结构。
3. Agent 生成计划。
4. Tool Runtime 执行安全的只读工具。
5. Agent 生成带证据的 proposals。
6. Governance Engine 判断风险。
7. 用户审查需要确认的 proposals。
8. Browser Executor 执行批准后的动作。
9. Verification Service 检查浏览器状态。
10. Trace 和 Benchmark 记录发生了什么。
```

## 6. 核心设计原则

最重要的原则是：

```text
模型驱动行为。
系统治理执行。
```

模型应该真正承担 Agent 工作：

- 理解用户目标。
- 判断网页类型和任务意图。
- 选择下一步工具。
- 检索相关依据。
- 生成候选答案。
- 根据错误调整计划。
- 判断是否已经完成任务。

系统应该承担不可让渡的运行时契约：

- tool schema validation。
- permission boundaries。
- sensitive action classification。
- review interrupts。
- approved-only browser writes。
- final submit approval。
- verification requirements。
- trace and evidence recording。

这仍然是 Agent 项目。区别只是：它不是无边界 Agent，而是可信执行的 Agent。

## 7. LangGraph、LangChain、OpenAI、MCP 和浏览器工具的分工

### 7.1 LangGraph

LangGraph 应该成为主要 orchestration runtime。

适合承担：

- durable run state。
- pause and resume。
- human-in-the-loop interrupts。
- agent loop control。
- retry and recovery paths。
- graph-level observability。
- plan execution state。

不要只把 LangGraph 用在一个 workflow 上。建议新增一个通用 graph：

```text
governed_agent_graph
```

原有 security questionnaire graph 可以先保留，作为兼容路径和 parity test 的对照。

### 7.2 LangChain

LangChain 可以用，但不要把整个项目重写成 LangChain demo。

适合承担：

- model adapters。
- structured output。
- retriever abstraction。
- tool definitions。
- prompt 和 output schema plumbing。

应用系统仍然应该拥有真正的 tool execution、governance、approval flow 和 browser verification。

### 7.3 OpenAI Responses API

OpenAI Responses API 适合用于结构化 planning 和 proposal generation。

可用于生成：

- `AgentPlan`
- `ToolCall`
- answer proposal
- classification output
- structured tool arguments

这很适合当前项目，因为后端仍然可以掌握 runtime loop，不需要把执行权交给模型 SDK。

### 7.4 OpenAI Agents SDK

OpenAI Agents SDK 可以用，但不建议第一阶段直接替换整个 runtime。

适合使用的场景：

- 需要 SDK 管理 model/tool loop。
- 需要多个 specialist agents 之间 handoff。
- 需要 SDK-level tracing。
- 需要 SDK-managed approval pause。
- 你发现自己正在重复实现通用 agent harness。

不建议一开始全量迁移的原因：

- 当前项目需要 no-key local demo。
- 已经有 SQLite run state。
- 已经有 review center。
- 已经有 browser verification。
- 已经有 benchmark suite。
- 已经有项目特定的安全边界。
- 已经有 source-backed answer UX。

更好的第一步是：

```text
把 OpenAI Agents SDK 作为可选 planner 或 specialist sub-agent，
而不是整个 runtime 的唯一 owner。
```

### 7.5 MCP 和 OpenAPI tools

MCP 和 OpenAPI-generated tools 应该作为外部工具来源，而不是绕过系统的捷径。

正确路径：

```text
发现 MCP / OpenAPI tool
  -> 归一化成 ToolDefinition
  -> allowlist 或人工配置
  -> 暴露给 AgentPlanner
  -> 通过 ToolRuntime 执行
  -> 经过 GovernanceEngine 判断
  -> trace 和 verification 记录结果
```

第一阶段应该优先接 read-only tools。写入型工具要等 review/governance 路径成熟后再接。

### 7.6 浏览器工具层

浏览器执行层应该保持可替换。

未来可以支持：

- 现有 Playwright executor。
- browser-use。
- OpenAI computer-use。
- MCP browser tools。
- 自定义 browser automation tools。

项目的身份不应该绑定某一个浏览器自动化库。

可以这样理解：

```text
browser-use 解决 browser control。
AI Web Form Agent 应该解决 trusted browser work。
```

## 8. 核心运行时对象

下面这些对象应该成为下一阶段重构的骨架。

### 8.1 AgentRun

表示一次用户目标和它的执行状态。

字段建议：

```text
id
goal
target_url
profile_id
status
mode
created_at
updated_at
current_plan_id
final_result
error
```

早期可以继续复用现有 `Task` 表。后续再考虑把 `Task` 包装或重命名为 `AgentRun`。

### 8.2 AgentPlan

表示一次 run 当前的计划。

字段建议：

```text
id
run_id
version
goal
steps
created_by
created_at
```

每个 step 应该是 planned tool call，而不是 hardcoded workflow stage。

示例：

```json
{
  "goal": "Use my resume and profile to complete this internship application",
  "steps": [
    {
      "step_id": "inspect_page",
      "tool_name": "extract_page_structure",
      "reason": "Understand what the page asks for"
    },
    {
      "step_id": "retrieve_resume_context",
      "tool_name": "retrieve_evidence",
      "reason": "Find resume evidence for open-ended fields"
    },
    {
      "step_id": "draft_answers",
      "tool_name": "generate_proposals",
      "reason": "Create reviewable answers with evidence"
    },
    {
      "step_id": "fill_approved_values",
      "tool_name": "fill_browser_fields",
      "reason": "Apply approved values after review"
    }
  ]
}
```

### 8.3 ToolCall

表示一次工具调用请求。

字段建议：

```text
id
run_id
plan_step_id
tool_name
input_json
status
risk_level
governance_decision
started_at
completed_at
error
```

### 8.4 ToolResult

表示一次工具调用的输出。

字段建议：

```text
tool_call_id
status
output_json
evidence_items
created_proposals
verification_candidates
error
```

### 8.5 Proposal

表示 Agent 希望系统或用户接受的一项建议。

常见 proposal：

- 用某个值填写某个字段。
- 用某段答案回答某个网页问题。
- 保存某条可复用 memory。
- 点击某个页面动作。
- 提交表单。
- 调用外部 API 写入数据。

字段建议：

```text
id
run_id
proposal_type
target_type
target_ref
proposed_value
rationale
confidence
risk_level
status
```

### 8.6 EvidenceItem

表示 proposal 的依据来源。

字段建议：

```text
id
run_id
proposal_id
source_type
source_id
source_title
section_title
quote_or_summary
score
created_at
```

UI 应该展示简洁证据，而不是把原始 retrieval output 全部倾倒给用户。

### 8.7 ReviewDecision

表示用户的审查结果。

字段建议：

```text
id
proposal_id
decision
edited_value
reviewer_note
created_at
```

支持的 decision：

```text
approved
edited
rejected
needs_more_evidence
```

### 8.8 VerificationResult

表示系统如何证明动作已经成功执行。

字段建议：

```text
id
run_id
target_ref
expected
actual
status
evidence
screenshot_id
created_at
```

## 9. Tool Runtime 设计

Tool Runtime 应该为内部工具、MCP 工具、OpenAPI 工具和浏览器工具提供统一执行路径。

推荐接口：

```python
class AgentTool:
    name: str
    description: str
    input_schema: dict
    output_schema: dict
    risk_level: str
    mutates_browser: bool
    mutates_external_system: bool

    def execute(self, context: AgentContext, tool_input: dict) -> ToolResult:
        ...
```

Tool Runtime 的职责：

- 校验 tool 是否存在。
- 校验 input 是否符合 schema。
- 创建 trace span。
- 执行前调用 GovernanceEngine。
- 调用 tool handler。
- 归一化 ToolResult。
- 记录 output 和 evidence。
- 把异常转换成结构化 failure。
- 在需要时创建 verification candidate。

第一批内部 tools：

```text
extract_page_structure
extract_form_fields
retrieve_profile_context
retrieve_document_evidence
retrieve_reviewed_memory
generate_answer_proposals
classify_action_risk
create_review_request
fill_browser_fields
click_browser_element
verify_browser_state
capture_screenshot
save_reviewed_memory
```

重点：现有服务应该先被 wrapper 包起来，不要重写。

## 10. Governance Model

Governance 应该是 action-level，而不是 workflow-level。

系统不应该强迫每条任务都经过同一组固定步骤。更好的方式是：每个 tool call 或 proposed action 都拿到一个风险决策。

决策类型：

```text
ALLOW
RECORD_ONLY
REVIEW_REQUIRED
APPROVAL_REQUIRED
BLOCKED
VERIFY_REQUIRED
```

示例：

```text
读取页面标题                         -> ALLOW
提取字段                             -> ALLOW
检索资料证据                         -> ALLOW
基于简历生成答案草稿                  -> RECORD_ONLY
填写可见文本字段                      -> REVIEW_REQUIRED
保存可复用 profile memory             -> REVIEW_REQUIRED
点击 save draft                       -> APPROVAL_REQUIRED
点击 final submit                     -> APPROVAL_REQUIRED
输入 password                         -> BLOCKED
输入 OTP                              -> BLOCKED
输入 payment information              -> BLOCKED
解决 CAPTCHA                          -> BLOCKED
```

Governance 不应该替 Agent 判断业务答案。它只判断拟执行动作是否允许、是否需要审查、是否必须阻止。

这能同时保留灵活性和可信度。

## 11. Agent Planner 设计

Planner 应该分阶段演进。

### 11.1 阶段一：Deterministic Planner

保留当前 deterministic plans，但输出结构改成 `AgentPlan`。

这样可以保留 no-key local demo，也能让现有测试稳定。

### 11.2 阶段二：Template-Guided Planner

template 降级为 planning hint。

示例：

```text
job_application:
  preferred_tools:
    - extract_page_structure
    - retrieve_profile_context
    - retrieve_document_evidence
    - generate_answer_proposals
    - fill_browser_fields
    - verify_browser_state
  policy_defaults:
    submit: approval_required
    password: blocked
```

Planner 可以在检查页面后调整实际步骤。

### 11.3 阶段三：LLM Planner With Structured Output

使用 OpenAI Responses API 或 LangChain structured output 生成 schema-valid plan。

模型输出：

```text
goal interpretation
planned tool calls
reason for each tool
expected evidence
risk assumptions
completion criteria
```

Runtime 必须先校验模型输出，再允许执行。

### 11.4 阶段四：Agent Loop

Planner 演进成迭代循环：

```text
observe state
choose next tool
execute tool
observe result
revise plan
continue or stop
```

这个循环由 LangGraph 管理。

## 12. Review UX 设计

现有 Review Mapping 应该演进成更通用的 Review Queue。

Review Queue 展示的不是“字段映射”，而是 proposals。

Proposal 类型包括：

```text
field_value
open_ended_answer
memory_write
browser_navigation
browser_click
form_submit
external_api_write
```

每个 review item 应该展示：

- target。
- proposed action 或 proposed value。
- source evidence。
- confidence。
- risk label。
- why review is needed。
- approve / edit / reject / ask for more evidence。

Review UX 的目标不是让用户机械地点击 approve all，而是让用户理解 Agent 为什么建议这样做，以及哪里需要人类判断。

## 13. Verification Model

Verification 不应该只服务于表单字段。

未来 verification 类型可以包括：

```text
field_value_verification
page_state_verification
navigation_verification
download_verification
saved_draft_verification
external_api_result_verification
memory_write_verification
```

浏览器 workflow 的 verification 应该记录：

- selector 或 target reference。
- expected value/state。
- actual value/state。
- screenshot。
- status。
- failure reason。

这是项目最重要的差异化之一。很多 Agent 可以执行动作，但更少的 Agent 能证明自己做了什么、做得对不对。

## 14. 前端重构方向

前端应该从 workflow-specific pages 转向 generic agent run surfaces。

推荐页面：

```text
Runs
Create Agent Run
Run Cockpit
Review Queue
Knowledge Sources
Memory
Evaluation
Settings / Tool Registry
```

### 14.1 Run Cockpit

Run Cockpit 是单个 run 的主界面。

展示：

- user goal。
- current status。
- current plan。
- active tool call。
- pending review count。
- evidence summary。
- execution result。
- verification result。
- compact trace。

### 14.2 Review Queue

Review Queue 替代或泛化 Review Mapping。

展示：

- pending proposals。
- evidence-backed suggested values。
- risk explanations。
- edit controls。
- approve / reject actions。

### 14.3 Tool Registry Page

这个页面可以后做，不要过早建设。

它用于展示：

- internal tools。
- MCP tools。
- OpenAPI tools。
- risk level。
- read/write capability。
- approval policy。
- enabled/disabled state。

前提是底层 ToolRuntime 已经稳定。

## 15. 后端重构方向

推荐服务目录：

```text
backend/app/services/agent_runtime/
  context.py
  schemas.py
  planner.py
  tool_registry.py
  tool_runtime.py
  governance.py
  review_queue.py
  graph.py
  adapters/
    openai_planner.py
    langchain_planner.py
    mcp_tools.py
    openapi_tools.py
    browser_use.py
```

routers 应该变薄：

```text
POST /agent-runs
GET  /agent-runs/{id}
POST /agent-runs/{id}/start
POST /agent-runs/{id}/continue
GET  /agent-runs/{id}/plan
GET  /agent-runs/{id}/tool-calls
GET  /agent-runs/{id}/review-items
POST /agent-runs/{id}/review-items/{item_id}/decision
GET  /agent-runs/{id}/verification-results
GET  /agent-runs/{id}/trace
```

现有 `/tasks` endpoints 可以在迁移期保留。

## 16. 分阶段迁移策略

重构必须渐进。不要做 big-bang rewrite。

### Phase 1：新增 Agent Runtime Schemas

新增 Pydantic models：

```text
AgentRunState
AgentPlan
PlannedToolCall
ToolCall
ToolResult
Proposal
EvidenceItem
ReviewDecision
GovernanceDecision
VerificationCandidate
```

先写 schema tests，不改变用户可见行为。

验收标准：

- 现有后端测试通过。
- 现有前端测试通过。
- 新 schema tests 覆盖核心校验。

### Phase 2：把 Tool Registry 变成 Executable Tools

把现有服务包装成 tools：

```text
extract_form_fields -> FormExtractor
generate_field_mappings -> FieldMapper / SuggestionProvider
retrieve_document_evidence -> KnowledgeSource / PolicyRetriever
fill_browser_fields -> BrowserExecutor
verify_browser_state -> ExecutionVerificationService
```

不要删除旧 router。旧路径可以逐步改为调用新 ToolRuntime。

验收标准：

- 现有 form fill demo 继续可用。
- tool calls 能生成 trace spans。
- tool results 符合 schema。

### Phase 3：Tool Execution 前加入 GovernanceEngine

新增 `GovernanceEngine`，在 tool call 执行前做风险判断。

第一批覆盖：

```text
password blocked
OTP blocked
payment blocked
CAPTCHA blocked
submit requires approval
browser write requires review or prior approval
memory write requires filtering
```

验收标准：

- 现有 policy tests 通过。
- 新 tool-level governance tests 通过。
- blocked tool call 无法通过 ToolRuntime 执行。

### Phase 4：Review Mapping 泛化为 Proposal Review

保留现有 Review Mapping UI，但让后端开始返回 generic proposal items。

字段映射变成：

```text
proposal_type = "field_value"
```

安全问卷答案变成：

```text
proposal_type = "answer"
```

memory 写入变成：

```text
proposal_type = "memory_write"
```

验收标准：

- 现有 mapping review path 继续工作。
- UI 可以不依赖 workflow type 渲染 proposals。
- source evidence 对任意 proposal type 可展示。

### Phase 5：用 Governed Agent Graph 替换单场景 Graph

新增通用图：

```text
governed_agent_graph
```

graph nodes：

```text
initialize_run
plan_next_step
prepare_tool_call
check_governance
interrupt_for_review
execute_tool
verify_result
observe_result
decide_next_step
finish
fail
```

旧 security questionnaire graph 先保留，直到新 graph 通过 parity tests。

验收标准：

- security questionnaire 可以通过 generic graph 跑通。
- vendor onboarding 可以通过 generic graph 跑通。
- 现有 browser replay benchmark 继续通过。

### Phase 6：加入 LLM Planner

新增可选 model-driven planning。

Planner modes：

```text
deterministic
template_guided
llm_structured
```

LLM 可以提出 tool calls，但 runtime 必须校验所有 tool calls。

验收标准：

- no-key deterministic mode 继续可用。
- LLM planner output 必须通过 schema validation。
- invalid tools 或 invalid arguments 会被拒绝。
- LLM planner 不能绕过 governance。

### Phase 7：接入外部工具

在内部 ToolRuntime 稳定后，再加入 MCP 和 OpenAPI tools。

先接 read-only tools：

```text
search documents
read CRM record
read file metadata
read knowledge base article
```

后续再接 write tools：

```text
update CRM field
create ticket
send email draft
save portal update
```

验收标准：

- 外部工具必须 allowlisted。
- tool metadata 包含 risk classification。
- write tools 必须走 review 或 approval。
- tool outputs 必须 trace。

### Phase 8：前端改成 Run Cockpit

前端从 workflow-specific conditionals 转成 generic run state。

统一展示：

```text
plan steps
tool calls
proposals
review items
evidence
verification
trace
```

验收标准：

- 用户能理解 Agent 正在做什么。
- 用户能审查有意义的 proposals。
- advanced trace 默认折叠。
- 主路径是 goal -> review -> execute -> verify。

## 17. Backward Compatibility

迁移期间保留：

- 现有 `Task` table。
- 现有 `/tasks` endpoints。
- 现有 benchmark fixtures。
- 现有 demo URLs。
- 现有 profile 和 memory tables。
- 现有 approval endpoints。
- 现有 trace tables。

先并行新增 runtime abstractions，再逐步替换旧路径。

只有在以下条件满足后，才考虑删除或重命名旧概念：

- security questionnaire 通过新 runtime。
- generic form fill 通过新 runtime。
- benchmark 结果稳定。
- 前端已经能用 generic proposal review。

## 18. 测试策略

测试应该自底向上。

### 18.1 Unit Tests

覆盖：

- schema validation。
- tool registry lookup。
- tool input validation。
- tool result normalization。
- governance decisions。
- proposal creation。
- review decision application。
- verification result formatting。

### 18.2 Integration Tests

覆盖：

- deterministic agent run。
- review-required browser write。
- blocked sensitive tool call。
- approved fill execution。
- verification failure。
- LLM planner invalid output rejection。

### 18.3 Benchmark Tests

扩展现有 benchmark modes：

```text
rules
llm
rag_llm
runtime
full_workflow
agent_runtime
```

新增指标：

```text
plan_validity_rate
tool_call_success_rate
governance_block_rate
review_intervention_rate
proposal_acceptance_rate
verification_pass_rate
agent_recovery_rate
```

## 19. 重构后的产品定位

重构后项目可以这样描述：

```text
AI Web Form Agent 是一个面向证据驱动网页工作流的受治理浏览器 Agent runtime。
它让 Agent 检查网页、调用工具、检索依据文档、生成可审查建议、在必要时请求人工确认、执行批准后的浏览器动作、验证结果，并记录可追溯证据。
```

短版本：

```text
多数 browser agents 关注如何控制浏览器。
这个项目关注如何可信地完成浏览器工作。
```

简历版本：

```text
Built a governed tool-using browser agent with LangGraph orchestration, structured tool calls, evidence-backed proposals, human review gates, Playwright execution, DOM verification, trace observability, and benchmark evaluation.
```

## 20. 非目标

这次重构不应该加入：

- production auth。
- multi-tenant account management。
- cloud browser fleet management。
- CAPTCHA solving。
- payment automation。
- broad scraping。
- invisible auto-submit behavior。
- 在主流程清晰前增加大量 dashboard。

这些会稀释 portfolio story，也会把项目带向不必要的复杂度。

## 21. 关键架构决策

### Decision 1：AgentRun 成为运行时核心

`workflow_type` 继续存在，但降级为 hint。真正运行时围绕 `AgentRun`。

### Decision 2：Tools 必须 typed 且 executable

每个 tool 都必须有输入 schema、输出 schema、risk metadata、trace 行为和执行 handler。

### Decision 3：Governance 是 action-level

治理层判断每个 tool call 和 proposal，而不是锁死整条 workflow。

### Decision 4：Human Review 只拦截关键动作

写网页、提交、保存 memory、低置信度 proposal、外部系统写入等需要 review。只读动作不应该频繁打断用户。

### Decision 5：Verification 是一等能力

系统必须能证明浏览器执行后的状态。Verification 不只是 debug，而是 trust layer。

### Decision 6：LLM Planning 必须结构化

模型可以规划和选择工具，但输出必须是 schema-valid，并且只能通过 runtime 执行。

### Decision 7：现有 demo 不能被重构破坏

security questionnaire、vendor onboarding、generic form fill 和 benchmark evidence 都应该在迁移期保持可运行。

## 22. 推荐的第一个实施切片

第一个切片应该尽量小：

```text
1. 新增 agent runtime schemas。
2. 新增 ToolRuntime。
3. 把 extract_form_fields 包成第一个 executable tool。
4. 把 generate_field_mappings 包成第二个 executable tool。
5. 把 ToolCall 和 ToolResult 写入现有 trace/checkpoint storage。
6. 前端行为暂时不变。
```

第二个切片包装：

```text
fill_browser_fields
verify_browser_state
```

第三个切片加入：

```text
GovernanceEngine before ToolRuntime execution
```

只有这些稳定后，再引入通用 LangGraph agent loop。

## 23. 最终目标状态

重构完成后，系统应该支持这样的交互：

```text
User:
Use my resume and saved profile to complete this application page.

Agent:
I will inspect the page, identify required fields, retrieve relevant resume evidence, draft answers, ask you to review fields that change the page, fill approved values, verify the browser state, and stop before final submission.

Runtime:
Creates a plan, executes read-only tools, creates evidence-backed proposals, pauses for review, executes approved browser actions, verifies results, and records trace evidence.
```

最终项目不只是一个浏览器自动化 demo，而是一套可复用的可信 Agentic Web Workflow 架构。

