
import json
from typing import Any, Optional

from fastmcp import Client
from langchain_core.tools import StructuredTool
from pydantic import ConfigDict, Field, create_model


def _python_type(schema: dict[str, Any]) -> type:
    """Convert basic JSON Schema types into Python types."""
    schema_type = schema.get("type", "string")

    if schema_type == "integer":
        return int
    if schema_type == "number":
        return float
    if schema_type == "boolean":
        return bool
    if schema_type == "array":
        return list[Any]
    if schema_type == "object":
        return dict[str, Any]

    return str


def _build_args_model(name: str, schema: dict[str, Any]):
    """Build a Pydantic argument model from an MCP tool schema."""
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))

    fields = {}

    for field_name, field_schema in properties.items():
        field_type = _python_type(field_schema)

        if field_name in required:
            fields[field_name] = (
                field_type,
                Field(..., description=field_schema.get("description", "")),
            )
        else:
            fields[field_name] = (
                Optional[field_type],
                Field(
                    default=None,
                    description=field_schema.get("description", ""),
                ),
            )

    return create_model(
        f"{name.title().replace('_', '')}Arguments",
        __config__=ConfigDict(extra="forbid"),
        **fields,
    )


class MCPToolRegistry:
    """Discover MCP tools and expose them as LangChain tools."""

    def __init__(self, server_configs: dict[str, dict[str, Any]]):
        self.server_configs = server_configs
        self._tools: list[StructuredTool] | None = None

    async def get_tools(self) -> list[StructuredTool]:
        if self._tools is not None:
            return self._tools

        discovered_tools = []

        for server_name, server_config in self.server_configs.items():
            config = {
                "mcpServers": {
                    server_name: server_config,
                }
            }

            async with Client(config) as client:
                mcp_tools = await client.list_tools()

            for mcp_tool in mcp_tools:
                tool_name = f"{server_name}__{mcp_tool.name}"
                args_schema = _build_args_model(
                    tool_name,
                    mcp_tool.input_schema,
                )

                async def execute(
                    _server_config=server_config,
                    _server_name=server_name,
                    _tool_name=mcp_tool.name,
                    **arguments,
                ):
                    call_config = {
                        "mcpServers": {
                            _server_name: _server_config,
                        }
                    }

                    async with Client(call_config) as client:
                        # Populate MCP parameter-header mappings.
                        await client.list_tools()
                        clean_arguments = {
                            key:value
                            for key , value in arguments.items()
                            if value is not None
                        }

                        result = await client.call_tool(
                            _tool_name,
                            clean_arguments,
                            raise_on_error=False,
                        )

                    if result.is_error:
                        raise RuntimeError(
                            f"MCP tool {_tool_name} failed: {result.content}"
                        )

                    if result.structured_content is not None:
                        return json.dumps(result.structured_content)

                    return "\n".join(
                        block.text
                        for block in result.content
                        if hasattr(block, "text")
                    )

                discovered_tools.append(
                    StructuredTool(
                        name=tool_name,
                        description=(
                            f"[{server_name}] "
                            f"{mcp_tool.description or mcp_tool.name}"
                        ),
                        args_schema=args_schema,
                        coroutine=execute,
                    )
                )

        self._tools = discovered_tools
        return self._tools
