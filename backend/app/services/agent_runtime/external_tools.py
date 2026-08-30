"""Read-only external tool adapters for the governed agent runtime."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal, Protocol
from urllib.parse import quote, urlencode
from urllib.request import urlopen

from app import config
from app.services.agent_runtime.tool_runtime import (
    AgentTool,
    ToolExecutionContext,
    ToolRuntime,
)

ExternalToolSource = Literal["mcp", "openapi"]
McpDiscover = Callable[[], Awaitable[tuple[list[object], list[dict[str, str]]]]]


class ExternalConnectorUnavailable(RuntimeError):
    """Raised when an allowlisted external connector cannot be reached."""

    def __init__(self, connector_id: str) -> None:
        super().__init__(f"External connector unavailable: {connector_id}")


@dataclass(frozen=True)
class ExternalToolSpec:
    """Normalized metadata for one discovered external tool."""

    source: ExternalToolSource
    connector_id: str
    name: str
    description: str
    input_schema: dict[str, object]
    output_schema: dict[str, object]
    read_only: bool
    destructive: bool = False

    def __post_init__(self) -> None:
        if not self.connector_id.strip() or not self.name.strip():
            raise ValueError("connector_id and name are required")

    @property
    def runtime_name(self) -> str:
        """Return the stable AgentTool name exposed to planners."""

        return f"{self.source}.{self.connector_id}.{self.name}"


@dataclass(frozen=True)
class OpenAPIToolSpec(ExternalToolSpec):
    """Small OpenAPI operation adapter spec for read-only Phase 7 tools."""

    method: str = "GET"
    path: str = ""

    def __init__(
        self,
        *,
        connector_id: str,
        operation_id: str,
        method: str,
        path: str,
        description: str,
        input_schema: dict[str, object],
        output_schema: dict[str, object],
    ) -> None:
        object.__setattr__(self, "source", "openapi")
        object.__setattr__(self, "connector_id", connector_id)
        object.__setattr__(self, "name", operation_id)
        object.__setattr__(self, "description", description)
        object.__setattr__(self, "input_schema", input_schema)
        object.__setattr__(self, "output_schema", output_schema)
        object.__setattr__(self, "read_only", method.upper() == "GET")
        object.__setattr__(self, "destructive", method.upper() != "GET")
        object.__setattr__(self, "method", method.upper())
        object.__setattr__(self, "path", path)
        ExternalToolSpec.__post_init__(self)


class ExternalToolExecutor(Protocol):
    """Execution boundary implemented by MCP/OpenAPI connector clients."""

    async def execute(
        self,
        spec: ExternalToolSpec,
        tool_input: dict[str, object],
    ) -> dict[str, object]:
        """Execute one external read-only tool and return JSON-like output."""


class McpReadOnlyToolExecutor:
    """Read-only MCP executor backed by the optional MCP client service."""

    def __init__(
        self,
        *,
        call_mcp_tool: Callable[
            [str, str, dict[str, object]], Awaitable[dict[str, object]]
        ]
        | None = None,
    ) -> None:
        self._call_mcp_tool = call_mcp_tool

    async def execute(
        self,
        spec: ExternalToolSpec,
        tool_input: dict[str, object],
    ) -> dict[str, object]:
        """Call one MCP tool through the project MCP client boundary."""

        if spec.source != "mcp":
            raise ValueError("McpReadOnlyToolExecutor only supports MCP specs")

        call_mcp_tool = self._call_mcp_tool
        if call_mcp_tool is None:
            from app.services.mcp_client_service import call_mcp_tool as default_call

            call_mcp_tool = default_call
        return await call_mcp_tool(spec.connector_id, spec.name, tool_input)


GetJson = Callable[[str, dict[str, object]], Awaitable[dict[str, object]]]


class OpenAPIReadOnlyToolExecutor:
    """Minimal read-only OpenAPI executor for allowlisted GET operations."""

    def __init__(
        self,
        *,
        base_urls: dict[str, str],
        get_json: GetJson | None = None,
    ) -> None:
        self._base_urls = base_urls
        self._get_json = get_json or _get_json

    async def execute(
        self,
        spec: ExternalToolSpec,
        tool_input: dict[str, object],
    ) -> dict[str, object]:
        """Execute one OpenAPI GET operation with path and query parameters."""

        if not isinstance(spec, OpenAPIToolSpec):
            raise ValueError("OpenAPIReadOnlyToolExecutor only supports OpenAPI specs")
        if spec.method != "GET":
            raise ValueError(f"OpenAPI tool {spec.runtime_name} must be read-only")

        base_url = self._base_urls.get(spec.connector_id)
        if not base_url:
            raise ExternalConnectorUnavailable(spec.connector_id)

        path, query = _render_openapi_path(spec.path, tool_input)
        return await self._get_json(f"{base_url.rstrip('/')}{path}", query)


async def _get_json(url: str, query: dict[str, object]) -> dict[str, object]:
    full_url = url if not query else f"{url}?{urlencode(query)}"
    with urlopen(full_url, timeout=config.LLM_REQUEST_TIMEOUT_SECONDS) as response:
        parsed = json.loads(response.read().decode("utf-8"))
    return parsed if isinstance(parsed, dict) else {"result": parsed}


def _render_openapi_path(
    path_template: str,
    tool_input: dict[str, object],
) -> tuple[str, dict[str, object]]:
    path = path_template if path_template.startswith("/") else f"/{path_template}"
    consumed: set[str] = set()
    for name, value in tool_input.items():
        placeholder = "{" + name + "}"
        if placeholder in path:
            path = path.replace(placeholder, quote(str(value), safe=""))
            consumed.add(name)
    query = {name: value for name, value in tool_input.items() if name not in consumed}
    return path, query


def external_spec_from_mcp_tool(tool: object) -> ExternalToolSpec:
    """Convert discovered MCP tool metadata into a runtime adapter spec."""

    description = getattr(tool, "description", None) or "External MCP read-only tool."
    return ExternalToolSpec(
        source="mcp",
        connector_id=str(getattr(tool, "server_id")),
        name=str(getattr(tool, "name")),
        description=description,
        input_schema=dict(getattr(tool, "input_schema")),
        output_schema={"type": "object"},
        read_only=getattr(tool, "read_only", None) is True,
        destructive=getattr(tool, "destructive", None) is True,
    )


def register_external_readonly_tools(
    runtime: ToolRuntime,
    specs: list[ExternalToolSpec],
    *,
    allowlist: set[str] | None = None,
    executor: ExternalToolExecutor,
) -> list[str]:
    """Register allowlisted read-only external tools as AgentTool objects."""

    allowed_names = load_external_tool_allowlist() if allowlist is None else allowlist
    registered: list[str] = []
    for spec in specs:
        if spec.runtime_name not in allowed_names:
            continue
        runtime.register(_to_agent_tool(spec, executor))
        registered.append(spec.runtime_name)
    return registered


async def register_configured_mcp_readonly_tools(
    runtime: ToolRuntime,
    *,
    allowlist: set[str] | None = None,
    discover_mcp_tools: McpDiscover | None = None,
    executor: ExternalToolExecutor | None = None,
) -> tuple[list[str], list[dict[str, str]]]:
    """Discover and register allowlisted MCP read-only tools."""

    if discover_mcp_tools is None:
        from app.services.mcp_client_service import discover_mcp_tools as discover

        discover_mcp_tools = discover

    tools, errors = await discover_mcp_tools()
    registered = register_external_readonly_tools(
        runtime,
        [external_spec_from_mcp_tool(tool) for tool in tools],
        allowlist=allowlist,
        executor=executor or McpReadOnlyToolExecutor(),
    )
    return registered, errors


def register_configured_openapi_readonly_tools(
    runtime: ToolRuntime,
    *,
    allowlist: set[str] | None = None,
    executor: ExternalToolExecutor | None = None,
) -> list[str]:
    """Register configured allowlisted read-only OpenAPI operations."""

    return register_external_readonly_tools(
        runtime,
        load_openapi_tool_specs(),
        allowlist=allowlist,
        executor=executor
        or OpenAPIReadOnlyToolExecutor(base_urls=load_openapi_base_urls()),
    )


def load_external_tool_allowlist(raw_value: str | None = None) -> set[str]:
    """Load the external runtime tool allowlist from config or a raw value."""

    raw = config.EXTERNAL_TOOL_ALLOWLIST if raw_value is None else raw_value
    raw = raw.strip()
    if not raw:
        return set()

    if raw.startswith("["):
        parsed = json.loads(raw)
        if not isinstance(parsed, list) or not all(
            isinstance(item, str) for item in parsed
        ):
            raise ValueError("EXTERNAL_TOOL_ALLOWLIST must contain strings")
        return {item.strip() for item in parsed if item.strip()}

    return {item.strip() for item in raw.split(",") if item.strip()}


def load_openapi_base_urls(raw_value: str | None = None) -> dict[str, str]:
    """Load OpenAPI connector base URLs from JSON config."""

    raw = config.OPENAPI_BASE_URLS_JSON if raw_value is None else raw_value
    raw = raw.strip()
    if not raw:
        return {}

    parsed = json.loads(raw)
    if not isinstance(parsed, dict) or not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in parsed.items()
    ):
        raise ValueError("OPENAPI_BASE_URLS_JSON must be an object of strings")
    return {key.strip(): value.strip() for key, value in parsed.items() if key.strip()}


def load_openapi_tool_specs(raw_value: str | None = None) -> list[OpenAPIToolSpec]:
    """Load configured OpenAPI operations as external tool specs."""

    raw = config.OPENAPI_TOOL_SPECS_JSON if raw_value is None else raw_value
    raw = raw.strip()
    if not raw:
        return []

    parsed = json.loads(raw)
    if not isinstance(parsed, list):
        raise ValueError("OPENAPI_TOOL_SPECS_JSON must be an array")

    specs: list[OpenAPIToolSpec] = []
    for item in parsed:
        if not isinstance(item, dict):
            raise ValueError("OPENAPI_TOOL_SPECS_JSON entries must be objects")
        specs.append(
            OpenAPIToolSpec(
                connector_id=str(item.get("connector_id", "")),
                operation_id=str(item.get("operation_id", "")),
                method=str(item.get("method", "GET")),
                path=str(item.get("path", "")),
                description=str(item.get("description", "")),
                input_schema=_object_schema(item.get("input_schema")),
                output_schema=_object_schema(item.get("output_schema")),
            )
        )
    return specs


def _to_agent_tool(
    spec: ExternalToolSpec,
    executor: ExternalToolExecutor,
) -> AgentTool:
    if not spec.read_only or spec.destructive:
        raise ValueError(f"External tool {spec.runtime_name} must be read-only")

    async def handler(
        _context: ToolExecutionContext,
        tool_input: dict[str, object],
    ) -> dict[str, object]:
        return await executor.execute(spec, tool_input)

    return AgentTool(
        name=spec.runtime_name,
        description=spec.description,
        input_schema=spec.input_schema,
        output_schema=spec.output_schema,
        risk_level="low",
        mutates_browser=False,
        mutates_external_system=False,
        trace_phase="external_tool",
        handler=handler,
    )


def _object_schema(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {"type": "object"}


__all__ = [
    "ExternalConnectorUnavailable",
    "ExternalToolExecutor",
    "ExternalToolSource",
    "ExternalToolSpec",
    "McpReadOnlyToolExecutor",
    "OpenAPIToolSpec",
    "OpenAPIReadOnlyToolExecutor",
    "external_spec_from_mcp_tool",
    "load_openapi_base_urls",
    "load_openapi_tool_specs",
    "load_external_tool_allowlist",
    "register_configured_mcp_readonly_tools",
    "register_configured_openapi_readonly_tools",
    "register_external_readonly_tools",
]
