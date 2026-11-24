
from typing import TypedDict, NotRequired

from app.schemas.plan import TaskPlan
from app.schemas.repository import RepositoryAnalysis
from app.schemas.coding import CodeProposal
from app.schemas.review import ReviewResult
from typing import Annotated
from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

from app.schemas.retry import RetryAnalysis


class DevPilotState(TypedDict):
    # Initial input
    task: str
    repository_context: str
    workspace_path: str
    file_inventory: str
    original_project_path: NotRequired[str]
    workspace_id: NotRequired[str]
    repository_name: NotRequired[str]

    # Agent outputs
    plan: NotRequired[TaskPlan]
    repository_analysis: NotRequired[RepositoryAnalysis]
    code_proposal: NotRequired[CodeProposal]
    review_result: NotRequired[ReviewResult]

    # Execution outputs
    patch_result: NotRequired[dict]
    diff_result: NotRequired[dict]
    execution_result: NotRequired[dict]
    rag_index_result: NotRequired[dict]


    # Retry management
    revision_count: NotRequired[int]
    review_feedback: NotRequired[str]
    attempt_history: NotRequired[list[dict]]
    retry_analysis: NotRequired[RetryAnalysis]
    verification_result: NotRequired[dict]
    human_feedback: NotRequired[str]
    human_decision: NotRequired[str]
    approval_request: NotRequired[dict]
    application_result: NotRequired[dict]
    human_revision_count: NotRequired[int]

    original_head_commit: NotRequired[str]

    # MCP tool communication
    messages: Annotated[list[AnyMessage], add_messages]
    mcp_return_to: NotRequired[str]
    mcp_round_count: NotRequired[int]
    mcp_tool_call_count: NotRequired[int]
    mcp_disabled: NotRequired[bool]
