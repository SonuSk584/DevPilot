from langchain_core.messages import AIMessage, AnyMessage

from app.mcp.registry import get_mcp_tools
from app.service.llm import get_llm


AGENT_MCP_TOOLS = {
    "repository_analyst": {
        "github__search_code",
        "github__get_file_contents",
        "github__search_repositories",
        "github__search_commits",
        "github__list_commits",
        "terminal__list_directory",
        "terminal__read_file",
        "terminal__git_status",
        "terminal__run_diagnostic",
    },

    "planner": {
        "github__search_code",
        "github__get_file_contents",
        "github__search_repositories",
        "github__search_commits",
        "github__list_commits",
    },

    "coder": {
        "terminal__run_diagnostic",
    },

    "reviewer": {
        "github__search_code",
        "github__get_file_contents",
        "github__list_commits",
        "terminal__list_directory",
        "terminal__read_file",
        "terminal__git_status",
        "terminal__run_diagnostic",
    },

    "verification": {
        "terminal__run_diagnostic",
        "terminal__git_status",
    },
}


async def request_mcp_tools(
    messages: list[AnyMessage],
    allowed_tools: set[str],
) -> AIMessage:
    """Let an agent request only its permitted MCP tools."""

    tools = await get_mcp_tools()

    selected_tools = [
        tool for tool in tools
        if tool.name in allowed_tools
    ]

    if not selected_tools:
        raise RuntimeError(
            f"No permitted MCP tools found: {allowed_tools}"
        )

    llm = get_llm().bind_tools(selected_tools)

    return await llm.ainvoke(messages)