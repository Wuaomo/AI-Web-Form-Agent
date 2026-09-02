# AI Web Form Agent 运行时整体重构 RFC

## 1. 结论

AI Web Form Agent 的目标不是继续堆更多 workflow type，也不是做一个无边界的自动浏览器。目标是把现有项目演进为：

```text
受治理的工具调用型浏览器 Agent runtime
```

这个 runtime 的核心路径是：

```text
用户目标
  -> Agent planner 生成 typed plan
  -> Tool Runtime 执行只读或已批准工具
  -> Governance Engine 对每个工具调用和 proposal 做风险判断
  -> Review Queue 暂停需要人工判断的 proposal/action
  -> Browser Executor 只执行已批准的浏览器写入
  -> Verification Service 证明执行结果
  -> Trace Store 和 Benchmark Suite 留下可复现证据
```

当前分支已经完成的是一组薄切片：schemas、tool runtime、tool-level governance、generic proposal review、governed graph skeleton、planner modes、read-only external tool adapters、Run Cockpit / Review Queue 前端入口。这证明方向可行，但不等于整体底层重构完成。

整体重构完成的标准是：主要浏览器工作流都能通过 generic AgentRun / Tool Runtime / Governance / Review Queue / Verification 路径运行，旧 `/tasks` 和 workflow-specific 路径只作为兼容 facade，而不是实际业务中心。

## 2. 产品定位

项目应该被描述为：

```text
一个审查优先的浏览器工作流助手：
它读取网页，提取页面结构和待处理字段，从用户资料、已审查记忆和本地依据文档中生成建议，要求用户审查关键建议和高风险动作，然后把已批准动作执行到真实浏览器中，并用 DOM、截图、trace 和 benchmark 证明结果。
```

短版本：

```text
多数 browser agents 关注如何控制浏览器。
这个项目关注如何可信地完成浏览器工作。
```

简历版本：

```text
Built a governed tool-using browser agent with LangGraph orchestration, typed tool calls, action-level governance, evidence-backed proposals, human review gates, Playwright execution, DOM verification, trace observability, and benchmark evaluation.
```

## 3. 不变边界

这些边界不能被重构稀释：

- 不自动提交最终表单，提交动作必须有明确用户批准。
- 不绕过登录、CAPTCHA、OTP、支付、反机器人或破坏性动作。
- 不把密码、支付信息、OTP、CAPTCHA、一次性同意值存入 profile 或 memory。
- no-key deterministic mode 必须可用，不能因为 LLM provider 未配置而破坏本地 demo。
- security questionnaire demo、vendor onboarding demo、generic form fill demo 必须持续可跑。
- `/tasks` endpoints 在迁移期必须保留兼容。
- advanced trace/debug 默认折叠，主界面只展示用户可读摘要。
- 外部工具先只接 read-only；写入型外部工具必须等 review/governance/verification 全链路成熟后再接。

## 4. 当前资产

已有能力不是要推倒重来，而是要被包进更通用的 runtime：

- FastAPI 后端、React/Vite 前端、SQLite 持久化。
- Playwright 浏览器执行。
- 表单字段提取、字段映射、用户审查、批准门禁。
- `PolicyEngine`、`ApprovalGateService`、安全字段阻断。
- workflow memory 和已审查 mapping 复用。
- knowledge sources 和 source-backed questionnaire answers。
- security questionnaire LangGraph runtime。
- workflow plan、action logs、workflow trace、screenshots、verification results。
- benchmark runner，覆盖 extraction、mapping、questionnaire、memory、full workflow replay。

## 5. 当前未提交薄切片状态

截至 `dev/governed-agent-graph-slice` 当前工作区，已经有这些方向性薄切片：

- Phase 1：新增 agent runtime schemas。
- Phase 2：新增 executable Tool Runtime，并开始包装现有服务。
- Phase 3：工具执行前加入 action-level governance。
- Phase 4：Review Mapping 开始桥接 generic proposal review。
- Phase 5：新增 governed agent graph skeleton。
- Phase 6：新增 deterministic / template-guided / llm_structured planner mode。
- Phase 7：新增 MCP / OpenAPI read-only external tool adapter 的 allowlist 路径。
- Phase 8A-E：Task Detail / Review Mapping 中加入 Run Cockpit、Review Queue summary、compact tool calls、compact verification evidence。

这些薄切片的价值是“证明架构方向”，不是“完成替换”。后续工作要把它们从并行路径推进为主路径。

## 6. 当前主要问题

### 6.1 workflow_type 仍是业务分发中心

`security_questionnaire`、`vendor_onboarding`、`form_fill` 等 workflow 仍然承担 runtime 边界。新增场景会继续带来 router 分支、前端 conditionals、测试路径复制。

目标状态：

```text
workflow template = planning hint + default policy profile + demo preset
AgentRun = runtime center
```

### 6.2 Tool Runtime 还没有覆盖主要执行路径

现有 Tool Runtime 已有契约，但旧 router 和 service 仍然直接调用 extraction、mapping、fill、verification 等逻辑。

目标状态：

```text
router
  -> Agent Runtime API
    -> Tool Runtime
      -> wrapped existing service
```

### 6.3 Proposal Review 尚未成为唯一审查合同

Review Mapping 已经开始泛化，但很多审查语义仍绑定 form field。

目标状态：

```text
field mapping review
questionnaire answer review
memory write review
browser click review
submit approval
external write review
```

都落到统一 `Proposal` / `ReviewDecision` 合同。

### 6.4 Verification 仍偏 field-centric

字段验证已经有价值，但通用 Agent 还需要验证 page state、navigation、download、saved draft、memory write、external read/write result。

目标状态：verification 是一等 runtime result，不是 debug 附件。

### 6.5 Frontend 已有入口，但还不是主界面

Run Cockpit / Review Queue 已经出现，但 Task Detail 和 Review Mapping 仍混合大量 workflow-specific 逻辑。

目标状态：主路径围绕 Run Cockpit 和 Review Queue 展开；legacy workflow UI 逐步降级为兼容信息。

## 7. 目标架构

```text
React Frontend
  -> Agent Runtime API
    -> Agent Run Store
    -> Agent Planner
    -> Tool Registry
    -> Tool Runtime
      -> Internal Tools
      -> Browser Tools
      -> Read-only MCP Tools
      -> Read-only OpenAPI Tools
    -> Governance Engine
    -> Review Queue
    -> Browser Executor
    -> Evidence Retrieval
    -> Verification Service
    -> Trace Store
    -> Evaluation Harness
    -> SQLite Persistence
```

`Task` 可以在迁移期继续存在，但语义应逐步变成 `AgentRun` 的兼容壳。

## 8. 核心运行时对象

### 8.1 AgentRun

表示一次用户目标和运行状态。

```text
id
legacy_task_id
goal
target_url
profile_id
workflow_hint
status
mode
current_plan_id
pending_review_count
final_result
error
created_at
updated_at
```

### 8.2 AgentPlan

表示当前可审查计划。每个 step 是 planned tool call，不是 hardcoded workflow stage。

```text
id
run_id
version
goal
steps
created_by
created_at
```

### 8.3 PlannedToolCall

```text
step_id
tool_name
reason
input_json
risk_level
expected_evidence
depends_on
```

### 8.4 ToolCall

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

### 8.5 ToolResult

```text
tool_call_id
status
output_json
evidence_items
created_proposals
verification_candidates
error
```

Raw `output_json` 只能进入后端持久化、trace 或 advanced/debug，不应直接进入主 UI。

### 8.6 Proposal

Agent 建议系统或用户接受的一项动作或值。

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
evidence
```

支持类型：

```text
field_value
open_ended_answer
answer
memory_write
browser_navigation
browser_click
form_submit
external_api_write
```

### 8.7 EvidenceItem

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

UI 展示 `source_title / section_title: quote_or_summary` 这样的 compact 摘要，不倾倒 retrieval raw output。

### 8.8 ReviewDecision

```text
id
proposal_id
decision
edited_value
reviewer_note
created_at
```

支持：

```text
approved
edited
rejected
needs_more_evidence
```

### 8.9 GovernanceDecision

```text
decision
reason
risk_level
requires_review
requires_approval
requires_verification
blocked_reason
```

支持：

```text
ALLOW
RECORD_ONLY
REVIEW_REQUIRED
APPROVAL_REQUIRED
BLOCKED
VERIFY_REQUIRED
```

### 8.10 VerificationResult

```text
id
run_id
tool_call_id
target_type
target_ref
verification_type
expected
actual
status
reason
evidence_items
screenshot_id
created_at
```

支持类型：

```text
field_value
page_state
navigation
download
saved_draft
external_api_result
memory_write
```

## 9. Backend 目标目录

目标不是一次性重排，而是让新代码逐渐集中到：

```text
backend/app/services/agent_runtime/
  schemas.py
  context.py
  planner.py
  tool_registry.py
  tool_runtime.py
  governance.py
  review_queue.py
  graph.py
  state_store.py
  adapters/
    internal_tools.py
    browser_tools.py
    mcp_tools.py
    openapi_tools.py
    openai_planner.py
```

迁移规则：

- 先 wrapper，后搬迁。
- 先让旧 endpoint 调新 runtime，后新增干净 endpoint。
- 先读工具，后写工具。
- 每次只迁一条用户路径，迁完跑 demo 和 benchmark。

## 10. Agent Runtime API

最终推荐 API：

```text
POST /agent-runs
GET  /agent-runs/{run_id}
POST /agent-runs/{run_id}/start
POST /agent-runs/{run_id}/continue
GET  /agent-runs/{run_id}/plan
GET  /agent-runs/{run_id}/tool-calls
GET  /agent-runs/{run_id}/review-items
POST /agent-runs/{run_id}/review-items/{item_id}/decision
GET  /agent-runs/{run_id}/verification-results
GET  /agent-runs/{run_id}/trace
```

迁移期保留：

```text
/tasks/*
/workflows/*
```

兼容策略：

- `/tasks/{id}` 返回 legacy task，同时可带 `agent_run_id`。
- `/workflows/{task_id}/governed` 可继续作为过渡 endpoint。
- 当前前端先复用 Task Detail / Review Mapping 页面，不新建大 dashboard。

## 11. Tool Runtime 设计

标准接口：

```python
class AgentTool:
    name: str
    description: str
    input_schema: dict
    output_schema: dict
    risk_level: str
    mutates_browser: bool
    mutates_external_system: bool
    trace_phase: str

    async def execute(context: ToolExecutionContext, tool_input: dict) -> ToolResult:
        ...
```

职责：

- 校验 tool 是否存在。
- 校验 input schema。
- 创建 `ToolCall`。
- 执行前调用 `GovernanceEngine`。
- 对 BLOCKED / REVIEW_REQUIRED / APPROVAL_REQUIRED 做暂停或拒绝。
- 调用 tool handler。
- 归一化 `ToolResult`。
- 提取 evidence、proposal、verification candidate。
- 写入 trace span。
- 把异常转换为结构化 failure。

第一批内部工具：

```text
extract_page_structure
extract_form_fields
map_fields
retrieve_profile_context
retrieve_reviewed_memory
retrieve_document_evidence
generate_answer_proposals
create_review_items
fill_browser_fields
click_browser_element
verify_browser_state
capture_screenshot
save_reviewed_memory
```

## 12. Governance Model

Governance 是 action-level，不是 workflow-level。

示例：

```text
读取页面结构                         -> ALLOW
提取字段                             -> ALLOW
检索本地知识源                       -> ALLOW
生成答案草稿                         -> RECORD_ONLY
填写可见文本字段                     -> REVIEW_REQUIRED
保存可复用 memory                    -> REVIEW_REQUIRED
点击 save draft                      -> APPROVAL_REQUIRED
点击 final submit                    -> APPROVAL_REQUIRED
输入 password                        -> BLOCKED
输入 OTP                             -> BLOCKED
输入 payment information             -> BLOCKED
解决 CAPTCHA                         -> BLOCKED
外部系统 read                        -> ALLOW 或 RECORD_ONLY
外部系统 write                       -> REVIEW_REQUIRED 或 APPROVAL_REQUIRED
```

治理层不判断业务答案是否正确；它判断动作是否允许、是否要审查、是否必须阻止。

## 13. Review Queue 设计

Review Queue 替代“只审字段映射”的概念。

每个 review item 展示：

- target：字段、页面动作、memory item、submit action、external operation。
- proposed value/action：用户要审的建议。
- evidence：最多展示 compact source evidence。
- confidence：没有分数就显示 Not scored。
- risk label：low / medium / high / blocked。
- reason：为什么需要 review。
- controls：approve / edit / reject / needs more evidence。

旧 Review Mapping 的迁移方式：

```text
FormField.mapped_value
  -> Proposal(type=field_value, target_type=form_field)
```

security questionnaire：

```text
source-backed answer
  -> Proposal(type=answer, target_type=form_field)
```

memory write：

```text
reviewed correction
  -> Proposal(type=memory_write)
```

submit：

```text
submit button action
  -> Proposal(type=form_submit, risk_level=high)
```

## 14. Verification Model

Verification 是 trust layer。

每个会改变浏览器或外部状态的动作都应该产生 verification candidate：

```text
fill_browser_fields -> field_value verification candidates
click save draft    -> saved_draft or page_state candidate
navigation          -> navigation candidate
memory write        -> memory_write candidate
external write      -> external_api_result candidate
```

Verification UI 只展示：

- status label。
- mismatch count。
- 最多 3 条 mismatch。
- 最多 3 条 evidence。
- screenshot link 或 compact reference。

完整 raw result、trace JSON 和 output_json 只放 advanced/debug。

## 15. Planner 设计

Planner 分三层演进。

### 15.1 deterministic

默认 no-key 路径。根据 workflow hint 和页面状态生成稳定计划。

用途：

- 本地 demo。
- benchmark baseline。
- CI regression。
- LLM 不可用时 fallback。

### 15.2 template_guided

workflow template 不再决定整条流程，只提供：

- preferred tools。
- default policy profile。
- demo copy。
- known fixture behavior。
- recommended evidence requirements。

Planner 可根据页面观察结果跳过或增加步骤。

### 15.3 llm_structured

LLM 只输出 schema-valid plan/proposals，不直接执行动作。

要求：

- output 必须通过 Pydantic schema validation。
- unknown tool 直接拒绝。
- invalid args 直接拒绝。
- planner 不能绕过 governance。
- no-key mode 不受影响。

## 16. LangGraph 设计

目标通用 graph：

```text
initialize_run
  -> plan_next_step
  -> prepare_tool_call
  -> check_governance
  -> interrupt_for_review
  -> execute_tool
  -> observe_result
  -> verify_result
  -> decide_next_step
  -> finish | fail
```

行为：

- ALLOW / RECORD_ONLY：直接执行。
- REVIEW_REQUIRED：暂停到 Review Queue。
- APPROVAL_REQUIRED：暂停到 Approval Center 或 Review Queue 的 high-risk item。
- BLOCKED：记录 blocked result，停止或让 planner 重新规划。
- VERIFY_REQUIRED：执行后必须创建 VerificationResult。

旧 security questionnaire graph 保留到以下条件满足：

- generic graph 跑通 security questionnaire。
- generic graph 跑通 vendor onboarding。
- generic graph 跑通 generic form fill。
- parity tests 覆盖主要状态和 failure path。
- benchmark 结果没有退化。

## 17. Frontend 目标

不要新增大型 dashboard。先复用现有页面：

```text
Task Detail
  -> Run Cockpit
  -> compact plan
  -> compact tool calls
  -> compact governance decision
  -> compact verification evidence
  -> advanced trace collapsed

Review Mapping
  -> Review Queue summary
  -> proposal-backed field rows
  -> compact source evidence
```

后续再逐步改名：

```text
Task Detail       -> Run Detail / Run Cockpit
Review Mapping    -> Review Queue
Create Task       -> Create Run
Benchmarks        -> Evaluation
```

只有当主路径稳定后，才新建 Tool Registry 页面。

## 18. 持久化策略

迁移期继续使用 SQLite。

这里的 SQLite 持久化首先保存的是 runtime state，不是 agent
长期记忆。`agent_runs` / `agent_plans` 用来回答“这个 task 对应哪次
governed run、当前计划是什么、服务重启后 Run Cockpit 能否恢复 compact
状态”。它们不应该承担 RAG memory、用户偏好、policy evidence 复用或
答案复用的职责。

新增表建议：

```text
agent_runs
agent_plans
agent_tool_calls
agent_tool_results
agent_proposals
agent_evidence_items
agent_review_decisions
agent_verification_results
```

兼容关系：

```text
tasks.id -> agent_runs.legacy_task_id
form_fields.id -> proposals.target_ref when target_type=form_field
workflow_traces.task_id -> agent_runs.legacy_task_id during migration
approval_requests.task_id -> agent_runs.legacy_task_id during migration
```

先双写关键 runtime records，再让 UI 读取新表，最后减少旧表职责。

Memory layer 应该作为后续独立迁移处理。当前 `workflow_memory_items`
已经能保守保存 reviewed mapping / answer 复用信息，并带有敏感值跳过、
stale/disabled 等早期治理字段；但它仍偏 workflow-specific。更合理的
演进顺序是：先完成 AgentRun/AgentPlan 持久化，再持久化 Proposal /
ReviewDecision，然后把 memory write 变成一种需要人工 approve/edit/reject
的 proposal，最后把 `workflow_memory_items` 泛化为 RAG memory layer，
统一管理 evidence、review lineage、sensitivity classification、retention
和 deletion policy。不要在 Phase 1 里直接重做 memory layer，否则容易把
运行恢复和长期记忆两个生命周期不同的问题混在一起。

## 19. 分阶段实施计划

### Phase 0：稳定当前分支

目标：把当前 Phase 1-8 薄切片变成可合并基线。

工作：

- 保留当前 schemas、Tool Runtime、governed graph、planner、external read-only tools、Run Cockpit、Review Queue summary。
- 跑前后端测试。
- 推送 PR，合并到主分支。

验收：

- frontend `npm test` 通过。
- frontend `npm run build` 通过。
- backend Docker pytest 通过。
- README 或 RFC 清楚说明“薄切片完成，整体替换未完成”。

### Phase 1：AgentRun 持久化

目标：让 generic runtime state 不只存在内存 checkpointer。

工作：

- 第一刀只新增 `agent_runs`、`agent_plans` 表；`agent_tool_calls`、
  `agent_tool_results` 放到后续持久化扩展。
- `POST /workflows/{task_id}/governed/start` 同步写入 run/plan。
- `GET /workflows/{task_id}/governed` 从持久化恢复 compact state。
- 保留 LangGraph checkpointer，但不再作为唯一恢复来源。

验收：

- 刷新后 Run Cockpit 状态可恢复。
- 服务重启后已持久化状态仍可查询。
- 不破坏 `/tasks`。

### Phase 2：内部工具覆盖主读路径

目标：页面读取、字段提取、证据检索、mapping 通过 Tool Runtime。

工作：

- 包装 `FormExtractor` 为 `extract_form_fields`。
- 包装 page extraction 为 `extract_page_structure`。
- 包装 reviewed memory retrieval。
- 包装 knowledge source retrieval。
- 包装 field mapping / answer proposal generation。
- 旧 router 改为调用 Tool Runtime wrapper。

验收：

- generic form fill analyze/map 路径可跑。
- security questionnaire source-backed answer 仍可跑。
- vendor onboarding 仍可跑。
- tool calls 和 results 持久化。

### Phase 3：Proposal Review 成为主审查合同

目标：Review Mapping 不再直接依赖 `FormField.mapped_value` 作为唯一审查对象。

工作：

- mapping 输出写入 `agent_proposals`。
- Review Mapping rows 从 proposal 派生。
- approve/edit/reject 写 `agent_review_decisions`。
- 兼容同步回 `FormField`，让旧 fill path 不断。

验收：

- 现有字段审查 UI 行为不退化。
- source evidence 对任意 proposal type 可展示。
- memory write proposal 需要 review。

### Phase 4：浏览器写入工具化

目标：fill/click/submit 都通过 Tool Runtime + Governance。

工作：

- 包装 `BrowserExecutor.fill_browser_fields`。
- 浏览器写入工具默认 `REVIEW_REQUIRED` 或 `APPROVAL_REQUIRED`。
- submit proposal 必须 high risk 且 approval required。
- approved review decision 才能解锁 execution。

验收：

- 未审查 proposal 不能被写入浏览器。
- final submit 不能自动执行。
- 敏感字段继续 blocked。

### Phase 5：Verification 泛化

目标：verification 从字段结果扩展为通用 runtime result。

工作：

- 新增 `agent_verification_results`。
- `fill_browser_fields` 产生 field verification candidates。
- `verify_browser_state` 写 generic VerificationResult。
- Run Cockpit 读取 generic verification compact summary。
- legacy field verification results 继续兼容展示。

验收：

- DOM verification 可证明 approved values 已写入。
- mismatch 有 compact user-facing summary。
- raw details 默认折叠。

当前状态（2026-09-01）：Phase 5 verification 泛化薄切片已收口。
`agent_verification_results`、fill verification candidates、
`verify_browser_state` generic VerificationResult 持久化、Run Cockpit
compact summary、legacy field verification 兼容路径都有回归测试覆盖。
这不表示整体 runtime refactor 完成；Phase 6 仍需要把主要 demo 收敛到
generic governed graph 主路径。

### Phase 6：通用 governed graph 成为主路径

目标：security questionnaire、vendor onboarding、generic form fill 都走 generic graph。

工作：

- 把旧 security graph 行为迁移成 planner preset。
- 为三条 demo 建 parity tests。
- graph 支持 review resume、approval resume、verification failure recovery。
- 旧 graph 保留一段时间作为 fallback。

验收：

- 三条 demo 在 generic graph 下通过。
- benchmark 不退化。
- 旧 graph 可以标记 deprecated。

### Phase 7：LLM planner 完整接入

目标：LLM 可以生成计划和 proposals，但不能越权。

工作：

- `OpenAIStructuredPlannerAdapter` 输出完整 AgentPlan。
- 结构校验失败进入 FAILED 或 deterministic fallback。
- unknown tool / invalid args 有明确错误。
- LLM proposal generation 必须带 rationale/evidence requirement。

验收：

- no-key deterministic mode 继续通过。
- LLM planner 不能调用未注册工具。
- LLM planner 不能跳过 review/governance。

当前状态（2026-09-02）：Phase 7 LLM planner 接入薄切片可收尾。
`llm_structured` 只生成 schema-valid `AgentPlan`，并且 unknown tool、
invalid args、malformed/missing planner output 都会被拒绝；registered
tool metadata 会传给 planner，实际执行仍只走 Tool Runtime 和 Governance。
浏览器写入仍暂停在 review，submit 仍暂停在 explicit approval；失败的 LLM
planner 不会覆盖已有持久化 compact run/plan；no-key deterministic path 和
runtime benchmark path 仍走本地 deterministic governed runtime。整体 runtime
refactor 仍未完成，旧 `/tasks` 和 workflow-specific 兼容路径仍保留。

### Phase 8：只读外部工具成熟

目标：MCP / OpenAPI read-only tools 可以进入 planner 和 Tool Runtime。

工作：

- 完善 allowlist 配置。
- tool metadata 标明 read/write、risk、source。
- tool output 归一化为 compact evidence。
- trace 记录外部 tool call summary。

验收：

- 未 allowlist 的外部工具不可用。
- write tools 默认拒绝注册或 blocked。
- 外部 raw output 不进入主 UI。

当前状态（2026-09-02）：Phase 8 只读外部工具薄切片可收尾。
MCP / OpenAPI read-only tools 通过 allowlist 注册到同一个 Tool Runtime；
未 allowlist 的工具不可用，write-capable external tools 会拒绝注册。
planner-visible metadata 和 trace metadata 都标明 source、read_only、risk
和 mutation flags；外部工具执行仍经过 Governance，并把 read output 提炼成
compact `EvidenceItem`，主 UI 只拿 compact tool-call/evidence 摘要。
外部写工具仍未接入，整体 runtime refactor 仍未完成。

### Phase 9：Evaluation Harness 升级

目标：benchmark 衡量 agent runtime，而不只衡量 extraction/mapping。

新增指标：

```text
plan_validity_rate
tool_call_success_rate
governance_block_rate
review_intervention_rate
proposal_acceptance_rate
verification_pass_rate
agent_recovery_rate
unsafe_action_prevention_rate
```

验收：

- `runtime` benchmark mode 可跑。
- full workflow replay 继续可跑。
- 报告能说明 memory、governance、verification 的价值。

当前状态（2026-09-02）：Phase 9 Evaluation Harness 升级薄切片可收尾。
`runtime` benchmark mode 仍是 no-key deterministic 路径，不使用 LLM planner；
它通过 governed graph 和 Tool Runtime 记录 plan validity、tool call success、
governance block、review intervention、proposal acceptance、verification pass、
agent recovery、unsafe action prevention 等 runtime 指标。`full_workflow`
benchmark replay 继续可跑；Markdown benchmark report 会展示 runtime 指标。
这不表示整体 runtime refactor 完成，旧 `/tasks` 和 workflow-specific 兼容路径
仍然保留。

### Phase 10：旧路径收敛和命名清理

目标：旧 workflow-specific 代码降级为 compatibility layer。

工作：

- router 变薄。
- frontend conditionals 减少。
- 文档统一为 AgentRun / Review Queue / Run Cockpit。
- 删除不再使用的 helper 和 old phase docs。

验收：

- 没有破坏 demo。
- 没有删除仍被 benchmark 覆盖的路径。
- README、architecture、safety docs 和 RFC 互相一致。

当前状态（2026-09-02）：Phase 10 旧路径收敛和命名清理薄切片可收尾。
`/tasks/{id}` 和 `/tasks` 列表都会作为 legacy facade 暴露 compact
`agent_run_id` / `agent_runtime`，且不暴露 raw `tool_results`；Run Cockpit
优先读取 `/workflows/{task_id}/governed`，失败时回退 task facade；Task Detail
在已有 Run Cockpit state 时隐藏旧 security-only runtime 面板；unsupported
workflow 的被动 governed-state probe 返回 404，不再打断 legacy Task Detail；
README、architecture、demo script 已同步 AgentRun / Review Queue / Run Cockpit
表述。旧 `/tasks`、workflow-specific endpoint、security questionnaire graph
仍作为兼容路径保留，整体 runtime refactor 仍未完成。

当前补充状态（2026-09-02）：internal legacy read/write Tool Runtime
convergence phase 已完成。legacy analyze、login-and-analyze、同步 rules
mapping、worker rules mapping、page extraction、job-summary prerequisite
extraction、fill、submit 和 verification 持久化路径都会记录 compact
`AgentToolCall` / `AgentToolResult` 或 generic verification state，且 task
facade 不暴露 raw `tool_results`。剩余 gap 进入下一 phase：generic graph
成为主 demo 路径、Review Queue 成为 primary contract，以及第 21 节整体完成
定义的最终验证。

## 20. 测试策略

每阶段至少有：

- unit tests：schema、governance、tool validation、presentation helper。
- integration tests：run start/resume、review decision、browser write、verification failure。
- API tests：兼容 `/tasks` 和新增 `/agent-runs`。
- frontend tests：Run Cockpit、Review Queue、advanced collapsed behavior。
- benchmark tests：no-key deterministic full workflow。

后端本机 Python 不可用时使用 Docker：

```bash
docker compose run --rm \
  -v "<repo>/backend/app:/app/app:ro" \
  -v "<repo>/backend/tests:/app/tests:ro" \
  backend python -m pytest -q
```

前端：

```bash
cd frontend
npm test
npm run build
```

## 21. 完成定义

整体 agent 底层重构只有在以下条件都满足后才算完成：

- `AgentRun`、`AgentPlan`、`ToolCall`、`ToolResult`、`Proposal`、`EvidenceItem`、`ReviewDecision`、`GovernanceDecision`、`VerificationResult` 都有持久化路径。
- 主要 demo 通过 generic governed graph，而不是 workflow-specific graph。
- 内部浏览器读写都通过 Tool Runtime。
- 所有浏览器写入和 submit 都经过 governance 和 review/approval。
- Review Queue 是 proposal 审查主入口。
- Run Cockpit 能展示 plan、tool calls、review state、evidence、verification、compact trace。
- no-key deterministic demo、security questionnaire、vendor onboarding、benchmark replay 均通过。
- read-only external tools 经过 allowlist、trace、governance。
- write external tools 未接入，或已完整通过 review/approval/verification。
- 文档、README、demo script、benchmark report 与实际行为一致。

## 22. 不算完成的状态

以下状态不能称为“整体重构完成”：

- 只有 schemas，没有主路径使用。
- 只有 Tool Runtime，但 router 仍直接调旧 service。
- 只有 governed graph skeleton，但 demo 仍依赖旧 graph。
- 只有 Review Queue summary，但实际审查仍是 form-only。
- 只有 Run Cockpit UI，但 state 不可持久恢复。
- LLM planner 能生成 plan，但 governance 可被绕过。
- external tools 能注册，但没有 allowlist 或 risk classification。
- benchmark 没覆盖 agent runtime path。

## 23. 回滚策略

每个阶段必须可以独立回滚：

- 新表先只双写，不立刻删除旧字段。
- 新 endpoint 先并行，不立刻替换 `/tasks`。
- 前端先读取 compact state，失败时隐藏新区块。
- generic graph 失败时保留旧 security graph fallback。
- LLM planner 失败时回 deterministic planner。
- external tools 配置为空时系统行为不变。

## 24. 推荐下一步

当前分支合并后，下一步应该是：

```text
Phase 1：AgentRun 持久化
```

这是最重要的收敛点。没有持久化，Run Cockpit 和 governed graph 仍然更像 demo state；有了持久化，后续 Tool Runtime、Review Queue、Verification、Benchmark 都能落到同一个 runtime contract 上。

第一刀建议：

1. 新增最小 `agent_runs` 和 `agent_plans` 表。
2. governed start 双写 `Task -> AgentRun` 和 `plan -> AgentPlan`。
3. governed get 从持久化返回 compact state。
4. 前端行为不变。
5. Docker backend pytest + frontend test/build 全跑。
