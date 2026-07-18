"""Tests for optional MCP client configuration and safe tool discovery."""

import json
import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import mcp_tools
from app.routers.mcp_tools import router
from app.services.mcp_client_service import (
    McpToolInfo,
    discover_mcp_tools,
    load_mcp_server_configs,
)


def test_load_mcp_server_configs_accepts_stdio_object() -> None:
    raw = json.dumps(
        {
            "github": {
                "transport": "stdio",
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-github"],
                "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": "GITHUB_TOKEN"},
            }
        }
    )

    servers = load_mcp_server_configs(raw)

    assert len(servers) == 1
    assert servers[0].id == "github"
    assert servers[0].transport == "stdio"
    assert servers[0].command == "npx"
    assert servers[0].args == ("-y", "@modelcontextprotocol/server-github")
    assert servers[0].env == {"GITHUB_PERSONAL_ACCESS_TOKEN": "GITHUB_TOKEN"}


def test_load_mcp_server_configs_accepts_streamable_http() -> None:
    raw = json.dumps(
        {
            "local": {
                "transport": "streamable_http",
                "url": "http://localhost:8000/mcp",
            }
        }
    )

    servers = load_mcp_server_configs(raw)

    assert servers[0].transport == "streamable_http"
    assert servers[0].url == "http://localhost:8000/mcp"


def test_load_mcp_server_configs_rejects_missing_stdio_command() -> None:
    with pytest.raises(ValueError, match="requires command"):
        load_mcp_server_configs(json.dumps({"broken": {"transport": "stdio"}}))


def test_discover_mcp_tools_reports_unknown_server() -> None:
    with pytest.raises(ValueError, match="Unknown MCP server"):
        asyncio.run(discover_mcp_tools(server_id="missing"))


def test_mcp_tools_endpoint_returns_discovery_payload(monkeypatch) -> None:
    async def fake_discover(server_id=None):
        assert server_id == "github"
        return (
            [
                McpToolInfo(
                    server_id="github",
                    name="github_list_repos",
                    description="List repositories",
                    input_schema={"type": "object"},
                    read_only=True,
                    destructive=False,
                )
            ],
            [],
        )

    monkeypatch.setattr(mcp_tools, "discover_mcp_tools", fake_discover)
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    response = client.get("/mcp/tools?server_id=github")

    assert response.status_code == 200
    payload = response.json()
    assert payload["tools"][0]["server_id"] == "github"
    assert payload["tools"][0]["name"] == "github_list_repos"
    assert payload["tools"][0]["read_only"] is True
    assert payload["errors"] == []
