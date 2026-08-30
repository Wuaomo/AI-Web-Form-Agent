"""Tests for read-only external tool adapters in the governed runtime."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Profile, Task
from app.services.agent_runtime.external_tools import (
    ExternalConnectorUnavailable,
    ExternalToolExecutor,
    ExternalToolSpec,
    McpReadOnlyToolExecutor,
    OpenAPIToolSpec,
    OpenAPIReadOnlyToolExecutor,
    config as external_tool_config,
    external_spec_from_mcp_tool,
    load_openapi_base_urls,
    load_openapi_tool_specs,
    load_external_tool_allowlist,
    register_configured_mcp_readonly_tools,
    register_configured_openapi_readonly_tools,
    register_external_readonly_tools,
)
from app.services.agent_runtime.governed_agent_graph import run_allowed_tool_once
from app.services.agent_runtime.tool_runtime import ToolExecutionContext, ToolRuntime
from app.services.mcp_client_service import McpToolInfo
from app.services.workflow_trace_service import list_spans_for_task


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class FakeExternalExecutor(ExternalToolExecutor):
    def __init__(self, output=None, error: Exception | None = None) -> None:
        self.calls = []
        self._output = output or {"ok": True}
        self._error = error

    async def execute(
        self,
        spec: ExternalToolSpec,
        tool_input: dict[str, object],
    ) -> dict[str, object]:
        self.calls.append((spec, tool_input))
        if self._error:
            raise self._error
        return self._output


def make_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return Session(engine)


def mcp_search_spec(**overrides) -> ExternalToolSpec:
    values = {
        "source": "mcp",
        "connector_id": "kb",
        "name": "search_documents",
        "description": "Search reviewed knowledge documents.",
        "input_schema": {
            "type": "object",
            "required": ["query"],
            "properties": {"query": {"type": "string"}},
        },
        "output_schema": {"type": "object"},
        "read_only": True,
        "destructive": False,
    }
    values.update(overrides)
    return ExternalToolSpec(**values)


@pytest.mark.anyio
async def test_readonly_mcp_tool_executes_through_runtime_governance_and_trace() -> None:
    """Verify allowlisted MCP tools become normal governed runtime tools."""

    session = make_session()
    try:
        profile = Profile(profile_name="Trace profile")
        task = Task(url="https://example.com/form", profile=profile)
        session.add(task)
        session.commit()

        executor = FakeExternalExecutor(
            {"documents": [{"title": "SOC2 policy"}], "count": 1}
        )
        runtime = ToolRuntime()
        registered = register_external_readonly_tools(
            runtime,
            [mcp_search_spec()],
            allowlist={"mcp.kb.search_documents"},
            executor=executor,
        )

        result = await runtime.execute(
            tool_call_id="call-1",
            tool_name="mcp.kb.search_documents",
            tool_input={"task_id": task.id, "query": "encryption"},
            context=ToolExecutionContext(metadata={"db": session}),
        )

        assert registered == ["mcp.kb.search_documents"]
        assert result.status == "SUCCEEDED"
        assert result.governance_decision is not None
        assert result.governance_decision.decision == "ALLOW"
        assert result.output_json["count"] == 1
        assert executor.calls[0][0].connector_id == "kb"
        assert executor.calls[0][1]["query"] == "encryption"

        spans = list_spans_for_task(session, task.id)
        assert len(spans) == 1
        assert spans[0].phase == "external_tool"
        assert spans[0].name == "mcp.kb.search_documents"
        assert spans[0].status == "SUCCESS"
        assert spans[0].span_metadata["mutates_external_system"] is False
        assert spans[0].span_metadata["governance_decision"]["decision"] == "ALLOW"
    finally:
        session.close()


@pytest.mark.anyio
async def test_external_tool_allowlist_controls_runtime_exposure() -> None:
    """Verify discovered external tools do not exist until allowlisted."""

    executor = FakeExternalExecutor()
    runtime = ToolRuntime()

    registered = register_external_readonly_tools(
        runtime,
        [mcp_search_spec()],
        allowlist=set(),
        executor=executor,
    )
    result = await runtime.execute(
        tool_call_id="call-1",
        tool_name="mcp.kb.search_documents",
        tool_input={"query": "security"},
    )

    assert registered == []
    assert result.status == "FAILED"
    assert result.error == "Unknown runtime tool: mcp.kb.search_documents"
    assert executor.calls == []


def test_external_adapter_rejects_write_capable_mcp_tools() -> None:
    """Verify Phase 7 does not register external write tools."""

    runtime = ToolRuntime()

    with pytest.raises(ValueError, match="read-only"):
        register_external_readonly_tools(
            runtime,
            [mcp_search_spec(read_only=False, destructive=True)],
            allowlist={"mcp.kb.search_documents"},
            executor=FakeExternalExecutor(),
        )


def test_external_spec_rejects_empty_connector_or_tool_name() -> None:
    """Verify external tools cannot expose ambiguous runtime names."""

    with pytest.raises(ValueError, match="connector_id and name are required"):
        mcp_search_spec(connector_id=" ")


def test_mcp_discovery_tool_info_normalizes_to_external_tool_spec() -> None:
    """Verify existing MCP discovery metadata can enter the runtime adapter."""

    spec = external_spec_from_mcp_tool(
        McpToolInfo(
            server_id="github",
            name="search_repos",
            description="Search repositories.",
            input_schema={"type": "object"},
            read_only=True,
            destructive=False,
        )
    )

    assert spec.source == "mcp"
    assert spec.connector_id == "github"
    assert spec.name == "search_repos"
    assert spec.runtime_name == "mcp.github.search_repos"
    assert spec.read_only is True


def test_external_tool_allowlist_defaults_to_empty() -> None:
    """Verify external tools stay unavailable unless explicitly configured."""

    assert load_external_tool_allowlist(raw_value="") == set()


def test_external_tool_allowlist_parses_json_array() -> None:
    """Verify configured external tool names become an allowlist set."""

    assert load_external_tool_allowlist(
        raw_value='["mcp.kb.search_documents", "openapi.crm.read_account"]'
    ) == {"mcp.kb.search_documents", "openapi.crm.read_account"}


def test_external_tool_allowlist_parses_comma_separated_list() -> None:
    """Verify simple env-style allowlists are accepted for local demos."""

    assert load_external_tool_allowlist(
        raw_value="mcp.kb.search_documents, openapi.crm.read_account"
    ) == {"mcp.kb.search_documents", "openapi.crm.read_account"}


def test_external_tool_allowlist_rejects_non_string_json_entries() -> None:
    """Verify malformed allowlist config fails closed."""

    with pytest.raises(ValueError, match="strings"):
        load_external_tool_allowlist(raw_value='["mcp.kb.search_documents", 42]')


def test_load_openapi_base_urls_parses_json_object() -> None:
    """Verify OpenAPI connector base URLs can be configured without code."""

    assert load_openapi_base_urls(
        raw_value='{"crm": "https://crm.example.test/api"}'
    ) == {"crm": "https://crm.example.test/api"}


def test_load_openapi_tool_specs_parses_readonly_operations() -> None:
    """Verify configured OpenAPI GET operations become external specs."""

    specs = load_openapi_tool_specs(
        raw_value=(
            "[{"
            '"connector_id":"crm",'
            '"operation_id":"read_account",'
            '"method":"GET",'
            '"path":"/accounts/{account_id}",'
            '"description":"Read account.",'
            '"input_schema":{"type":"object"},'
            '"output_schema":{"type":"object"}'
            "}]"
        )
    )

    assert len(specs) == 1
    assert specs[0].runtime_name == "openapi.crm.read_account"
    assert specs[0].read_only is True


def test_load_openapi_tool_specs_rejects_non_array_config() -> None:
    """Verify malformed OpenAPI tool config fails closed."""

    with pytest.raises(ValueError, match="array"):
        load_openapi_tool_specs(raw_value='{"connector_id": "crm"}')


def test_register_configured_openapi_readonly_tools_uses_config_specs(monkeypatch) -> None:
    """Verify configured OpenAPI specs can populate the governed runtime."""

    monkeypatch.setattr(
        external_tool_config,
        "OPENAPI_TOOL_SPECS_JSON",
        (
            "[{"
            '"connector_id":"crm",'
            '"operation_id":"read_account",'
            '"method":"GET",'
            '"path":"/accounts/{account_id}",'
            '"description":"Read account.",'
            '"input_schema":{"type":"object"},'
            '"output_schema":{"type":"object"}'
            "}]"
        ),
    )
    runtime = ToolRuntime()

    registered = register_configured_openapi_readonly_tools(
        runtime,
        allowlist={"openapi.crm.read_account"},
        executor=FakeExternalExecutor(),
    )

    assert registered == ["openapi.crm.read_account"]
    assert runtime.get_tool("openapi.crm.read_account") is not None


def test_external_tool_registration_uses_config_allowlist_by_default(monkeypatch) -> None:
    """Verify registration reads the configured allowlist when none is passed."""

    monkeypatch.setattr(
        external_tool_config,
        "EXTERNAL_TOOL_ALLOWLIST",
        '["mcp.kb.search_documents"]',
    )
    runtime = ToolRuntime()

    registered = register_external_readonly_tools(
        runtime,
        [mcp_search_spec()],
        executor=FakeExternalExecutor(),
    )

    assert registered == ["mcp.kb.search_documents"]
    assert runtime.get_tool("mcp.kb.search_documents") is not None


@pytest.mark.anyio
async def test_register_configured_mcp_readonly_tools_uses_discovery_and_allowlist() -> None:
    """Verify MCP discovery can populate the runtime through the adapter boundary."""

    async def fake_discover():
        return (
            [
                McpToolInfo(
                    server_id="kb",
                    name="search_documents",
                    description="Search docs.",
                    input_schema={"type": "object"},
                    read_only=True,
                    destructive=False,
                ),
                McpToolInfo(
                    server_id="kb",
                    name="update_document",
                    description="Write docs.",
                    input_schema={"type": "object"},
                    read_only=False,
                    destructive=True,
                ),
            ],
            [{"server_id": "offline", "error": "connection refused"}],
        )

    runtime = ToolRuntime()
    registered, errors = await register_configured_mcp_readonly_tools(
        runtime,
        allowlist={"mcp.kb.search_documents"},
        discover_mcp_tools=fake_discover,
        executor=FakeExternalExecutor(),
    )

    assert registered == ["mcp.kb.search_documents"]
    assert errors == [{"server_id": "offline", "error": "connection refused"}]
    assert runtime.get_tool("mcp.kb.search_documents") is not None
    assert runtime.get_tool("mcp.kb.update_document") is None


def test_runtime_tool_metadata_includes_allowlisted_external_tools() -> None:
    """Verify planners can see registered external tools without special cases."""

    runtime = ToolRuntime()
    register_external_readonly_tools(
        runtime,
        [mcp_search_spec()],
        allowlist={"mcp.kb.search_documents"},
        executor=FakeExternalExecutor(),
    )

    metadata = runtime.list_tool_metadata()

    assert metadata == [
        {
            "name": "mcp.kb.search_documents",
            "description": "Search reviewed knowledge documents.",
            "risk_level": "low",
            "mutates_browser": False,
            "mutates_external_system": False,
            "input_schema": mcp_search_spec().input_schema,
        }
    ]


@pytest.mark.anyio
async def test_mcp_readonly_executor_calls_mcp_tool() -> None:
    """Verify MCP executor delegates to the existing MCP client boundary."""

    calls = []

    async def fake_call_mcp_tool(server_id, tool_name, arguments):
        calls.append((server_id, tool_name, arguments))
        return {"content": [{"type": "text", "text": "SOC2"}]}

    executor = McpReadOnlyToolExecutor(call_mcp_tool=fake_call_mcp_tool)
    output = await executor.execute(mcp_search_spec(), {"query": "encryption"})

    assert output == {"content": [{"type": "text", "text": "SOC2"}]}
    assert calls == [("kb", "search_documents", {"query": "encryption"})]


@pytest.mark.anyio
async def test_mcp_readonly_executor_rejects_non_mcp_specs() -> None:
    """Verify MCP executor cannot accidentally run OpenAPI specs."""

    executor = McpReadOnlyToolExecutor(
        call_mcp_tool=lambda *_args: {"ok": True},
    )

    with pytest.raises(ValueError, match="MCP"):
        await executor.execute(
            OpenAPIToolSpec(
                connector_id="crm",
                operation_id="read_account",
                method="GET",
                path="/accounts/{account_id}",
                description="Read account.",
                input_schema={"type": "object"},
                output_schema={"type": "object"},
            ),
            {},
        )


@pytest.mark.anyio
async def test_openapi_readonly_executor_performs_get_request() -> None:
    """Verify OpenAPI GET operations execute through an injectable HTTP boundary."""

    calls = []

    async def fake_get_json(url, query):
        calls.append((url, query))
        return {"account_name": "Acme"}

    spec = OpenAPIToolSpec(
        connector_id="crm",
        operation_id="read_account",
        method="GET",
        path="/accounts/{account_id}",
        description="Read account.",
        input_schema={
            "type": "object",
            "required": ["account_id"],
            "properties": {
                "account_id": {"type": "string"},
                "include": {"type": "string"},
            },
        },
        output_schema={"type": "object"},
    )
    executor = OpenAPIReadOnlyToolExecutor(
        base_urls={"crm": "https://crm.example.test/api"},
        get_json=fake_get_json,
    )

    output = await executor.execute(
        spec,
        {"account_id": "acct_123", "include": "contacts"},
    )

    assert output == {"account_name": "Acme"}
    assert calls == [
        (
            "https://crm.example.test/api/accounts/acct_123",
            {"include": "contacts"},
        )
    ]


@pytest.mark.anyio
async def test_openapi_readonly_executor_reports_unavailable_connector() -> None:
    """Verify missing OpenAPI connector config fails with structured runtime error."""

    executor = OpenAPIReadOnlyToolExecutor(base_urls={})

    with pytest.raises(ExternalConnectorUnavailable, match="crm"):
        await executor.execute(
            OpenAPIToolSpec(
                connector_id="crm",
                operation_id="read_account",
                method="GET",
                path="/accounts/{account_id}",
                description="Read account.",
                input_schema={"type": "object"},
                output_schema={"type": "object"},
            ),
            {},
        )


@pytest.mark.anyio
async def test_external_tool_invalid_args_fail_before_connector_call() -> None:
    """Verify external tool arguments are validated by ToolRuntime."""

    executor = FakeExternalExecutor()
    runtime = ToolRuntime()
    register_external_readonly_tools(
        runtime,
        [mcp_search_spec()],
        allowlist={"mcp.kb.search_documents"},
        executor=executor,
    )

    result = await runtime.execute(
        tool_call_id="call-1",
        tool_name="mcp.kb.search_documents",
        tool_input={"query": 123},
    )

    assert result.status == "FAILED"
    assert result.error == "query must be a string"
    assert executor.calls == []


@pytest.mark.anyio
async def test_external_tool_unavailable_connector_is_structured_failure() -> None:
    """Verify connector outages do not leak exceptions from ToolRuntime."""

    runtime = ToolRuntime()
    register_external_readonly_tools(
        runtime,
        [mcp_search_spec()],
        allowlist={"mcp.kb.search_documents"},
        executor=FakeExternalExecutor(error=ExternalConnectorUnavailable("kb")),
    )

    result = await runtime.execute(
        tool_call_id="call-1",
        tool_name="mcp.kb.search_documents",
        tool_input={"query": "security"},
    )

    assert result.status == "FAILED"
    assert result.error == "External connector unavailable: kb"
    assert result.governance_decision is not None
    assert result.governance_decision.decision == "ALLOW"


@pytest.mark.anyio
async def test_openapi_get_operation_executes_as_readonly_external_tool() -> None:
    """Verify read-only OpenAPI operations use the same adapter boundary."""

    executor = FakeExternalExecutor({"account_name": "Acme"})
    runtime = ToolRuntime()
    registered = register_external_readonly_tools(
        runtime,
        [
            OpenAPIToolSpec(
                connector_id="crm",
                operation_id="read_account",
                method="GET",
                path="/accounts/{account_id}",
                description="Read CRM account details.",
                input_schema={
                    "type": "object",
                    "required": ["account_id"],
                    "properties": {"account_id": {"type": "string"}},
                },
                output_schema={"type": "object"},
            )
        ],
        allowlist={"openapi.crm.read_account"},
        executor=executor,
    )

    result = await runtime.execute(
        tool_call_id="call-1",
        tool_name="openapi.crm.read_account",
        tool_input={"account_id": "acct_123"},
    )

    assert registered == ["openapi.crm.read_account"]
    assert result.status == "SUCCEEDED"
    assert result.output_json == {"account_name": "Acme"}
    assert executor.calls[0][0].source == "openapi"


def test_external_adapter_rejects_write_capable_openapi_operations() -> None:
    """Verify non-GET OpenAPI operations stay outside Phase 7 runtime tools."""

    runtime = ToolRuntime()

    with pytest.raises(ValueError, match="read-only"):
        register_external_readonly_tools(
            runtime,
            [
                OpenAPIToolSpec(
                    connector_id="crm",
                    operation_id="update_account",
                    method="POST",
                    path="/accounts/{account_id}",
                    description="Update CRM account details.",
                    input_schema={"type": "object"},
                    output_schema={"type": "object"},
                )
            ],
            allowlist={"openapi.crm.update_account"},
            executor=FakeExternalExecutor(),
        )


@pytest.mark.anyio
async def test_governed_graph_runs_allowlisted_external_readonly_tool() -> None:
    """Verify external tools cannot bypass the generic graph governance path."""

    executor = FakeExternalExecutor({"matches": ["SOC2 policy"]})
    runtime = ToolRuntime()
    register_external_readonly_tools(
        runtime,
        [mcp_search_spec()],
        allowlist={"mcp.kb.search_documents"},
        executor=executor,
    )

    state = await run_allowed_tool_once(
        {
            "run_id": "task-external",
            "task_id": 12,
            "goal": "Find policy evidence.",
            "target_url": "https://example.com/form",
            "profile_id": 7,
            "plan_steps": [
                {
                    "step_id": "search_policy",
                    "tool_name": "mcp.kb.search_documents",
                    "reason": "Search reviewed policy docs.",
                    "input_json": {"query": "encryption"},
                    "risk_level": "low",
                }
            ],
        },
        runtime=runtime,
    )

    assert state["governance_decision"]["decision"] == "ALLOW"
    assert state["tool_results"][0]["status"] == "SUCCEEDED"
    assert state["tool_results"][0]["output_json"]["matches"] == ["SOC2 policy"]
