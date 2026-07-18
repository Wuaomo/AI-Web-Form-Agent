"""Read-only MCP tool discovery endpoints."""

from fastapi import APIRouter, HTTPException, status

from app.schemas import McpToolDiscoveryResponse
from app.services.mcp_client_service import discover_mcp_tools

router = APIRouter(prefix="/mcp", tags=["mcp"])


@router.get("/tools", response_model=McpToolDiscoveryResponse)
async def list_mcp_tools(server_id: str | None = None) -> dict[str, object]:
    """List tools exposed by configured MCP servers without executing them."""

    try:
        tools, errors = await discover_mcp_tools(server_id=server_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return {
        "tools": [tool.__dict__ for tool in tools],
        "errors": errors,
    }
