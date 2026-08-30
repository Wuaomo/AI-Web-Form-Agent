# AI Web Form Agent Runtime Refactor RFC

## 1. Purpose

This document proposes a refactor path for AI Web Form Agent.

The goal is to evolve the project from a fixed workflow demo collection into a flexible, agent-first browser automation system:

```text
User goal
  -> agent plans the work
  -> agent calls tools
  -> system checks risk and permissions
  -> user reviews consequential proposals
  -> browser executes approved actions
  -> system verifies the result
  -> traces and benchmarks record evidence
```

The target product is not a generic chatbot and not a fully autonomous browser bot. It should become a governed tool-using browser agent: the model drives reasoning and tool choice, while the application owns execution boundaries, review UX, verification, persistence, and evaluation.

## 2. Current Product Interpretation

The current project is strongest when described as:

```text
A review-first browser workflow assistant that reads webpages, extracts fields or questions, suggests answers from user data and evidence documents, asks for human review, fills approved values in a browser, verifies the DOM result, and records trace evidence.
```

This is already more mature than a simple form filler. Existing strengths include:

- FastAPI backend with SQLite persistence.
- React/Vite workflow console.
- Playwright browser execution.
- Form extraction and field mapping.
- Policy and approval gates.
- Reviewed workflow memory.
- Local knowledge sources and source-backed answer suggestions.
- LangGraph runtime for the security questionnaire workflow.
- Benchmark suite for extraction, mapping, safety, retrieval, and browser replay.
- Trace, screenshots, action logs, and verification evidence.

The project should keep these strengths. The refactor should not rewrite the product from scratch.

## 3. Main Problem

The core issue is that the product concept has outgrown the current architecture.

The project now wants to be an agentic browser runtime, but much of the code still assumes a fixed workflow application:

```text
workflow_type
  -> static plan
  -> workflow-specific router branch
  -> workflow-specific frontend rendering
  -> workflow-specific runtime behavior
```

This creates friction when adding new use cases such as job applications, vendor onboarding, policy-backed applications, government forms, insurance claims, CRM updates, or other browser tasks that need document-backed answers.

The next architecture should make workflow templates optional hints, not the core runtime primitive.

## 4. Problems In The Current Structure

### 4.1 Workflow Types Are Too Central

Current workflows such as `security_questionnaire`, `vendor_onboarding`, `form_fill`, `web_data_extract`, and `job_research_summary` are useful demos. The issue is that `workflow_type` is used as a primary branch point across backend planning, execution, and frontend presentation.

This makes the system harder to extend:

- Every new scenario needs new backend branches.
- Frontend pages need workflow-specific conditionals.
- The runtime cannot easily adapt plans based on page content.
- The user experience becomes a template picker instead of a goal-driven agent.

The refactor should keep templates, but change their role:

```text
Before:
workflow type determines the workflow

After:
workflow template provides planning hints and policy defaults
```

### 4.2 Tool Registry Is Not Yet A Runtime

The existing `ToolRegistry` contains useful metadata:

- tool name
- description
- risk level
- approval requirement
- parameter schema
- preconditions
- produced artifacts
- failure modes
- recovery hints
- evidence requirements

However, the registry is currently closer to documentation than execution. The actual business operations still live inside routers and services.

The refactor should make tools executable:

```text
ToolDefinition
  + input schema
  + output schema
  + risk metadata
  + execute(context, input) -> ToolResult
```

This unlocks agent tool calling without discarding existing services.

### 4.3 LangGraph Runtime Is Scenario-Specific

The current LangGraph runtime is useful, but it is tied to the security questionnaire flow. It demonstrates interrupts and state, but it is not yet a general agent runtime.

The target is a generic graph that can run dynamic tool calls:

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

Security questionnaire should become one planning preset, not the only graph.

### 4.4 Data Model Is Too Form-Centric

The current data model is centered on:

```text
Task
  -> FormField
  -> mapped_profile_key
  -> mapped_value
```

This works for forms, but the broader agent system needs richer concepts:

- tool calls
- tool results
- proposed browser actions
- answer proposals
- evidence items
- review decisions
- verification results
- observations
- agent plan revisions

The new model should still support forms, but forms should become one kind of target inside a more general proposal/action model.

### 4.5 Frontend Pages Encode Too Much Workflow Logic

The current UI has strong pieces: Dashboard, Create Run, Task Detail, Review Mapping, Approval Center, Memory, Knowledge Sources, Benchmarks.

The problem is that pages such as Task Detail and Review Mapping are accumulating many responsibilities:

- workflow state display
- mapping actions
- runtime controls
- screenshots
- verification
- trace
- approval requests
- agent reviews
- LLM usage
- job status
- workflow-specific UI

The target frontend should center around a generic Run Cockpit and Review Queue, not workflow-specific screens.

## 5. Target Architecture

The refactored system should use `AgentRun` as the primary runtime concept.

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

High-level module map:

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

The product loop becomes:

```text
1. User gives a goal and target page.
2. Agent inspects the page.
3. Agent proposes a plan.
4. Tool runtime executes safe read-only tools.
5. Agent generates proposals with evidence.
6. Governance classifies proposed actions.
7. User reviews only consequential proposals.
8. Browser executor applies approved actions.
9. Verification checks the browser state.
10. Trace and benchmark evidence records what happened.
```

## 6. Core Design Principle

The most important principle is:

```text
The model drives behavior.
The system governs execution.
```

The model should do real agent work:

- understand user goals
- inspect page state
- choose tools
- retrieve relevant evidence
- generate answer proposals
- revise plans after errors
- decide when it has enough information

The system should own non-negotiable runtime contracts:

- tool schema validation
- permission boundaries
- sensitive action classification
- review interrupts
- approved-only browser writes
- final submit approval
- verification requirements
- trace and evidence recording

This is still an agent project. It is just not an unbounded agent project.

## 7. Role Of LangGraph, LangChain, OpenAI, MCP, And Browser Tools

### 7.1 LangGraph

LangGraph should become the main orchestration runtime.

Use it for:

- durable run state
- pause and resume
- human-in-the-loop interrupts
- agent loop control
- retry and recovery paths
- graph-level observability
- plan execution state

Do not use LangGraph only for one workflow. The refactor should introduce a generic graph named something like:

```text
governed_agent_graph
```

The security questionnaire graph can be kept temporarily as a compatibility path while the generic graph matures.

Relevant docs:

- https://docs.langchain.com/oss/python/langgraph/overview
- https://docs.langchain.com/oss/python/langgraph/interrupts
- https://docs.langchain.com/oss/python/langgraph/persistence

### 7.2 LangChain

LangChain should be used selectively, not as a full rewrite.

Use it for:

- model adapters
- structured output
- retriever abstractions
- tool definitions
- prompt and output schema plumbing

Do not let LangChain hide the business runtime. The application should still own the actual tool execution, governance decisions, approval flow, and browser verification.

Relevant docs:

- https://docs.langchain.com/oss/python/langchain/agents
- https://docs.langchain.com/oss/python/langchain/tools
- https://docs.langchain.com/oss/python/langchain/structured-output
- https://docs.langchain.com/oss/python/langchain/human-in-the-loop

### 7.3 OpenAI Responses API

The OpenAI Responses API is a good fit for structured planning and proposal generation.

Use it for:

- structured `AgentPlan`
- structured `ToolCall`
- structured answer proposals
- classification outputs
- function calling
- model-generated reasoning summaries

The Responses API fits the existing architecture because your backend can remain the owner of the run loop.

Relevant docs:

- https://developers.openai.com/api/reference/responses/overview
- https://developers.openai.com/api/docs/guides/function-calling
- https://developers.openai.com/api/docs/guides/structured-outputs

### 7.4 OpenAI Agents SDK

The OpenAI Agents SDK can be valuable, but it should not be the first thing to replace the whole runtime.

Use it when:

- you need a managed model/tool loop
- you need handoffs between specialist agents
- you want SDK-level tracing
- you want SDK-managed approval pause behavior
- you find yourself rebuilding a general agent harness

Avoid making it the whole application core at the start because your project already has domain-specific requirements:

- local no-key demo mode
- existing SQLite run state
- existing review center
- existing browser verification
- existing evaluation suite
- project-specific safety boundaries
- source-backed answer UX

Best first use:

```text
Use OpenAI Agents SDK as an optional planner or specialist sub-agent,
not as the only runtime owner.
```

Relevant docs:

- https://developers.openai.com/api/docs/guides/agents
- https://developers.openai.com/api/docs/guides/agents/guardrails-approvals
- https://developers.openai.com/api/docs/guides/agents/integrations-observability

### 7.5 MCP And OpenAPI Tools

MCP and OpenAPI-generated tools should be treated as external tool sources.

They should not bypass your runtime.

Flow:

```text
MCP / OpenAPI tool discovered
  -> normalized into ToolDefinition
  -> reviewed or allowlisted
  -> exposed to AgentPlanner
  -> executed through ToolRuntime
  -> checked by GovernanceEngine
  -> traced and verified when needed
```

Start with read-only tools. Add write tools only after the review and governance path is mature.

### 7.6 Browser Tools

The browser execution layer should remain swappable.

Supported future backends:

- existing Playwright executor
- browser-use
- OpenAI computer-use
- MCP browser tools
- custom browser automation tools

The product should not depend on one browser automation library for its identity.

Browser-use solves browser control. This project should solve trusted browser workflows.

## 8. Proposed Runtime Objects

The following objects should become the backbone of the refactor.

### 8.1 AgentRun

Represents one user goal and its execution state.

Fields:

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

Early implementation can reuse the existing `Task` table. Later, `Task` can be renamed or wrapped as `AgentRun`.

### 8.2 AgentPlan

Represents the current plan for a run.

Fields:

```text
id
run_id
version
goal
steps
created_by
created_at
```

Each step should be a planned tool call, not a hardcoded workflow stage.

Example:

```json
{
  "goal": "Fill this internship application using my resume and profile",
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

Represents one requested tool invocation.

Fields:

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

Represents the output of a tool invocation.

Fields:

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

Represents something the agent wants the user or system to accept.

Examples:

- fill this field with this value
- use this answer for this question
- save this reusable memory item
- click this page action
- submit this form

Fields:

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

Represents source support for a proposal.

Fields:

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

The UI should show concise evidence. It should not overwhelm the user with raw retrieval output.

### 8.7 ReviewDecision

Represents human judgment.

Fields:

```text
id
proposal_id
decision
edited_value
reviewer_note
created_at
```

Supported decisions:

```text
approved
edited
rejected
needs_more_evidence
```

### 8.8 VerificationResult

Represents proof that a browser action worked.

Fields:

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

## 9. Tool Runtime Design

The tool runtime should provide a single execution path for all internal, MCP, OpenAPI, and browser tools.

Interface:

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

Tool runtime responsibilities:

- validate input against schema
- check tool exists
- create trace span
- call governance before execution
- execute tool handler
- normalize result
- record output and evidence
- convert errors into structured failures
- request verification when needed

Initial internal tools:

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

Existing services should be wrapped, not rewritten.

## 10. Governance Model

Governance should be action-level, not workflow-level.

The system should not force every workflow through the same fixed sequence. Instead, every tool call or proposed action receives a risk decision.

Decision types:

```text
ALLOW
RECORD_ONLY
REVIEW_REQUIRED
APPROVAL_REQUIRED
BLOCKED
VERIFY_REQUIRED
```

Example policy behavior:

```text
Read page title                       -> ALLOW
Extract fields                        -> ALLOW
Retrieve document evidence            -> ALLOW
Draft answer from resume              -> RECORD_ONLY
Fill visible text field                -> REVIEW_REQUIRED
Save reusable profile memory          -> REVIEW_REQUIRED
Click save draft                       -> APPROVAL_REQUIRED
Click final submit                     -> APPROVAL_REQUIRED
Input password                         -> BLOCKED
Input OTP                              -> BLOCKED
Input payment information              -> BLOCKED
Solve CAPTCHA                          -> BLOCKED
```

Governance should not decide the business answer. It should decide whether the proposed action is allowed, reviewable, or blocked.

This keeps the agent flexible while preserving product-level safety.

## 11. Agent Planner Design

The planner should evolve in stages.

### Stage 1: Deterministic Planner

Keep current deterministic plans, but output them as `AgentPlan`.

This preserves the no-key local demo and keeps existing tests stable.

### Stage 2: Template-Guided Planner

Templates become planning hints.

Example:

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

The planner can still change the exact plan after inspecting the page.

### Stage 3: LLM Planner With Structured Output

Use OpenAI Responses API or LangChain structured output to produce schema-valid plans.

The model should output:

```text
goal interpretation
planned tool calls
reason for each tool
expected evidence
risk assumptions
completion criteria
```

The runtime must validate the output before execution.

### Stage 4: Agent Loop

The planner becomes iterative:

```text
observe state
choose next tool
execute tool
observe result
revise plan
continue or stop
```

LangGraph should manage this loop.

## 12. Review UX Model

The current Review Mapping page should evolve into a generic Review Queue.

Review Queue shows proposals, not just fields.

Proposal examples:

```text
Field value proposal
Open-ended answer proposal
Memory write proposal
Navigation proposal
Submit proposal
External API write proposal
```

Each review item should show:

- target
- proposed action or value
- source evidence
- confidence
- risk label
- why review is needed
- approve, edit, reject, ask for more evidence

The UI should make human review meaningful. It should avoid turning approval into a blind "approve all" ritual.

## 13. Verification Model

Verification should not be limited to forms.

Verification types:

```text
field_value_verification
page_state_verification
navigation_verification
download_verification
saved_draft_verification
external_api_result_verification
memory_write_verification
```

For browser workflows, verification should capture:

- selector or target reference
- expected value or state
- actual value or state
- screenshot if useful
- status
- failure reason

This is one of the project's strongest differentiators. Many agents can act. Fewer can prove what they did.

## 14. Frontend Refactor Direction

The frontend should shift from workflow-specific pages to generic agent run surfaces.

Recommended pages:

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

### Run Cockpit

Primary surface for one run.

Shows:

- user goal
- current status
- current plan
- active tool call
- pending review count
- evidence summary
- execution result
- verification result
- compact trace

### Review Queue

Replaces or generalizes Review Mapping.

Shows:

- pending proposals
- evidence-backed suggested values
- risk explanations
- edit controls
- approve/reject actions

### Tool Registry Page

Optional later page.

Shows:

- internal tools
- MCP tools
- OpenAPI tools
- risk level
- read/write capability
- approval policy
- enabled/disabled state

Do not build this before the runtime exists.

## 15. Backend Refactor Direction

Recommended service layout:

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

Routers should become thinner:

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

Existing `/tasks` endpoints can remain during migration.

## 16. Migration Strategy

The refactor should be incremental. Do not perform a big-bang rewrite.

### Phase 1: Add Agent Runtime Schemas

Add Pydantic models for:

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

Use them in tests first. Do not change user-facing behavior.

Success criteria:

- Existing backend tests pass.
- Existing frontend tests pass.
- New schema tests cover validation.

### Phase 2: Convert Tool Registry Into Executable Tools

Wrap current services as tools:

```text
extract_form_fields -> FormExtractor
generate_field_mappings -> FieldMapper / SuggestionProvider
retrieve_document_evidence -> KnowledgeSource / PolicyRetriever
fill_browser_fields -> BrowserExecutor
verify_browser_state -> ExecutionVerificationService
```

Do not delete old router paths yet. Route old behavior through the new tool runtime where possible.

Success criteria:

- Existing form fill demo still works.
- Tool calls produce trace spans.
- Tool results are schema-valid.

### Phase 3: Add Governance Before Tool Execution

Introduce a `GovernanceEngine` that classifies tool calls and proposals.

Start with existing safety rules:

```text
password blocked
OTP blocked
payment blocked
CAPTCHA blocked
submit requires approval
browser write requires review or prior approval
memory write requires filtering
```

Success criteria:

- Current policy tests still pass.
- New tool-level governance tests pass.
- Blocked tools cannot execute through ToolRuntime.

### Phase 4: Generalize Review Mapping Into Proposal Review

Keep the existing Review Mapping UI, but make the backend return generic proposal items.

Fields become one proposal type:

```text
proposal_type = "field_value"
```

Security answers become:

```text
proposal_type = "answer"
```

Memory writes become:

```text
proposal_type = "memory_write"
```

Success criteria:

- Existing mapping review path still works.
- UI can render proposals without knowing the workflow type.
- Evidence display works for any proposal type.

### Phase 5: Replace Scenario Graph With Governed Agent Graph

Create a new generic graph:

```text
governed_agent_graph
```

Graph nodes:

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

Keep the old security questionnaire graph until the new graph passes parity tests.

Success criteria:

- Security questionnaire can run through the generic graph.
- Vendor onboarding can run through the generic graph.
- Existing browser replay benchmark still passes.

### Phase 6: Add LLM Planner

Add optional model-driven planning.

Use structured output. The model may propose tool calls, but the runtime validates every tool call before execution.

Planner modes:

```text
deterministic
template_guided
llm_structured
```

Success criteria:

- No-key deterministic mode remains available.
- LLM planner output is schema-validated.
- Invalid tools or invalid arguments are rejected.
- LLM planner cannot bypass governance.

### Phase 7: Add External Tool Sources

Add MCP and OpenAPI tools after the internal tool runtime is stable.

Start with read-only tools:

```text
search documents
read CRM record
read file metadata
read knowledge base article
```

Only later add write tools:

```text
update CRM field
create ticket
send email draft
save portal update
```

Success criteria:

- External tools are allowlisted.
- Tool metadata includes risk classification.
- Write tools require review or approval.
- Tool outputs are traced.

### Phase 8: Frontend Run Cockpit

Refactor frontend around generic run state.

Replace workflow-specific conditionals with:

```text
plan steps
tool calls
proposals
review items
evidence
verification
trace
```

Success criteria:

- User can understand what the agent is doing.
- User can review meaningful proposals.
- Advanced trace remains collapsed by default.
- The main path is goal -> review -> execute -> verify.

## 17. Backward Compatibility

Keep these during migration:

- existing `Task` table
- existing `/tasks` endpoints
- existing benchmark fixtures
- existing demo URLs
- existing profile and memory tables
- existing approval endpoints
- existing trace tables

Add new runtime abstractions beside existing behavior first.

Only remove or rename older concepts after:

- security questionnaire passes through new runtime
- generic form fill passes through new runtime
- benchmark results remain stable
- frontend has generic proposal review

## 18. Testing Strategy

Test from the bottom up.

### Unit Tests

Cover:

- schema validation
- tool registry lookup
- tool input validation
- tool result normalization
- governance decisions
- proposal creation
- review decision application
- verification result formatting

### Integration Tests

Cover:

- deterministic agent run
- review-required browser write
- blocked sensitive tool call
- approved fill execution
- verification failure
- LLM planner invalid output rejection

### Benchmark Tests

Extend existing benchmark modes:

```text
rules
llm
rag_llm
runtime
full_workflow
agent_runtime
```

New metrics:

```text
plan_validity_rate
tool_call_success_rate
governance_block_rate
review_intervention_rate
proposal_acceptance_rate
verification_pass_rate
agent_recovery_rate
```

## 19. Product Positioning After Refactor

The project should be described as:

```text
AI Web Form Agent is a governed browser agent runtime for evidence-backed web workflows. It lets an agent inspect pages, call tools, retrieve supporting documents, propose actions, request human review when needed, execute approved browser operations, verify outcomes, and record traceable evidence.
```

Short version:

```text
Most browser agents focus on controlling the browser.
This project focuses on trusted browser work.
```

Resume-ready version:

```text
Built a governed tool-using browser agent with LangGraph orchestration, structured tool calls, evidence-backed proposals, human review gates, Playwright execution, DOM verification, trace observability, and benchmark evaluation.
```

## 20. Non-Goals

The refactor should not add:

- production auth
- multi-tenant account management
- cloud browser fleet management
- CAPTCHA solving
- payment automation
- broad scraping
- invisible auto-submit behavior
- large new dashboards before the main run UX is clear

These are outside the product boundary and would dilute the portfolio story.

## 21. Key Architectural Decisions

### Decision 1: AgentRun Becomes The Runtime Primitive

`workflow_type` remains as a hint, but `AgentRun` becomes the actual runtime concept.

### Decision 2: Tools Become Executable And Typed

Tools must have validated inputs, normalized outputs, risk metadata, and trace behavior.

### Decision 3: Governance Is Action-Level

Governance should classify tool calls and proposals, not force every run through the same fixed workflow.

### Decision 4: Human Review Is For Consequential Actions

Human review should happen when the agent proposes writes, sensitive actions, final submission, memory writes, or low-confidence changes.

### Decision 5: Verification Is A First-Class Product Feature

The system should prove browser state after execution. Verification is not only debugging; it is part of trust.

### Decision 6: LLM Planning Must Be Structured

The model can plan and call tools, but outputs must be schema-valid and executable only through the runtime.

### Decision 7: Existing Working Demos Stay Working

The refactor should preserve the current local demo and benchmark evidence throughout migration.

## 22. Recommended First Implementation Slice

The first implementation slice should be deliberately small:

```text
1. Add agent runtime schemas.
2. Add ToolRuntime.
3. Wrap extract_form_fields as the first executable tool.
4. Wrap generate_field_mappings as the second executable tool.
5. Record ToolCall and ToolResult into existing trace/checkpoint storage.
6. Keep existing frontend behavior unchanged.
```

This creates the foundation without risking the current demo.

The second slice should wrap:

```text
fill_browser_fields
verify_browser_state
```

The third slice should add:

```text
GovernanceEngine before ToolRuntime execution.
```

Only after those are stable should the project introduce the generic LangGraph agent loop.

## 23. Final Target State

At the end of the refactor, the system should support this interaction:

```text
User:
Use my resume and saved profile to complete this application page.

Agent:
I will inspect the page, identify required fields, retrieve relevant resume evidence, draft answers, ask you to review fields that change the page, fill approved values, verify the browser state, and stop before final submission.

Runtime:
Creates a plan, executes read-only tools, creates evidence-backed proposals, pauses for review, executes approved browser actions, verifies results, and records trace evidence.
```

The result is not just a browser automation demo. It becomes a reusable architecture for trustworthy agentic web workflows.

