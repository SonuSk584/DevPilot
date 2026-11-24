
from langchain.mcp import MCPAdapter


class MCPClientManager:
    def __init__(self, server_configs: dict):
        """
        Example:
        {
            "langchain_docs": {
                "url": "https://docs.langchain.com/mcp"
            },
            "another_server": {
                "url": "https://example.com/mcp"
            }
        }
        """
        self.server_config = {
            "mcpServers": server_configs
        }

    async def discover_tools(self):
        async with MCPAdapter(self.server_config) as adapter:
            tools = await adapter.list_tools()

            return [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.args,
                }
                for tool in tools
            ]

    async def get_tools(self):
        async with MCPAdapter(self.server_config) as adapter:
            return await adapter.list_tools()
