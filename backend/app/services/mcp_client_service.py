"""Optional MCP client helpers for discovering external business tools."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Literal

from app import config

McpTransport = Literal["stdio", "streamable_http"]


@dataclass(frozen=True)
class McpServerConfig:
    """One configured MCP server without resolved secret values."""

    id: str
    transport: McpTransport
    command: str | None = None
    args: tuple[str, ...] = ()
    env: dict[str, str] = field(default_factory=dict)
    url: str | None = None


@dataclass(frozen=True)
class McpToolInfo:
    """Normalized metadata for one discovered MCP tool."""

    server_id: str
    name: str
    description: str | None
    input_schema: dict[str, object]
    read_only: bool | None = None
    destructive: bool | None = None


def load_mcp_server_configs(raw_json: str | None = None) -> list[McpServerConfig]:
    """Parse optional MCP server config from JSON."""

    raw = config.MCP_SERVERS_JSON if raw_json is None else raw_json
    if not raw.strip():
        return []

    parsed = json.loads(raw)
    if isinstance(parsed, dict):
        items = parsed.items()
    elif isinstance(parsed, list):
        items = ((str(item.get("id", "")), item) for item in parsed)
    else:
        raise ValueError("MCP_SERVERS_JSON must be an object or list")

    servers: list[McpServerConfig] = []
    for server_id, item in items:
        if not isinstance(item, dict):
            raise ValueError(f"MCP server '{server_id}' must be an object")
        server_id = str(server_id).strip()
        if not server_id:
            raise ValueError("MCP server id is required")

        transport = str(item.get("transport", "stdio")).strip()
        if transport not in {"stdio", "streamable_http"}:
            raise ValueError(
                f"MCP server '{server_id}' transport must be stdio or streamable_http"
            )

        command = item.get("command")
        url = item.get("url")
        if transport == "stdio" and not command:
            raise ValueError(f"MCP server '{server_id}' requires command")
        if transport == "streamable_http" and not url:
            raise ValueError(f"MCP server '{server_id}' requires url")

        args = item.get("args", [])
        env = item.get("env", {})
        if not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
            raise ValueError(f"MCP server '{server_id}' args must be a string list")
        if not isinstance(env, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in env.items()
        ):
            raise ValueError(f"MCP server '{server_id}' env must map strings to strings")

        servers.append(
            McpServerConfig(
                id=server_id,
                transport=transport,  # type: ignore[arg-type]
                command=str(command) if command else None,
                args=tuple(args),
                env=env,
                url=str(url) if url else None,
            )
        )
    return servers


def _resolved_env(server: McpServerConfig) -> dict[str, str]:
    """Resolve server env names from local env var names without exposing secrets."""

    return {
        server_env: value
        for server_env, local_env in server.env.items()
        if (value := os.getenv(local_env))
    }


def _tool_schema(tool: object) -> dict[str, object]:
    schema = getattr(tool, "inputSchema", None) or getattr(tool, "input_schema", None)
    return schema if isinstance(schema, dict) else {}


def _tool_annotation_bool(tool: object, name: str) -> bool | None:
    annotations = getattr(tool, "annotations", None)
    value = getattr(annotations, name, None) if annotations is not None else None
    return value if isinstance(value, bool) else None


async def _list_server_tools(server: McpServerConfig) -> list[McpToolInfo]:
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        from mcp.client.streamable_http import streamable_http_client
    except ImportError as exc:
        raise RuntimeError("Install mcp>=1.27,<2 to use MCP tools") from exc

    if server.transport == "stdio":
        assert server.command is not None
        params = StdioServerParameters(
            command=server.command,
            args=list(server.args),
            env=_resolved_env(server),
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                response = await session.list_tools()
    else:
        assert server.url is not None
        async with streamable_http_client(server.url) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                response = await session.list_tools()

    return [
        McpToolInfo(
            server_id=server.id,
            name=str(tool.name),
            description=getattr(tool, "description", None),
            input_schema=_tool_schema(tool),
            read_only=_tool_annotation_bool(tool, "readOnlyHint"),
            destructive=_tool_annotation_bool(tool, "destructiveHint"),
        )
        for tool in response.tools
    ]


async def discover_mcp_tools(
    server_id: str | None = None,
) -> tuple[list[McpToolInfo], list[dict[str, str]]]:
    """Return discovered MCP tools and non-fatal discovery errors."""

    configs = load_mcp_server_configs()
    if server_id is not None:
        configs = [server for server in configs if server.id == server_id]
        if not configs:
            raise ValueError(f"Unknown MCP server: {server_id}")

    tools: list[McpToolInfo] = []
    errors: list[dict[str, str]] = []
    for server in configs:
        try:
            tools.extend(await _list_server_tools(server))
        except Exception as exc:
            errors.append({"server_id": server.id, "error": str(exc)})
    return tools, errors
