from app.mcp.server_config import MCP_SERVER_CONFIGS
from app.mcp.tool_registry import MCPToolRegistry


mcp_registry = MCPToolRegistry(MCP_SERVER_CONFIGS)


async def get_mcp_tools():
    return await mcp_registry.get_tools()