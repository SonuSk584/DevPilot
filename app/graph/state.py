
from typing import TypedDict, NotRequired

from app.schemas.plan import TaskPlan
from app.schemas.repository import RepositoryAnalysis
from app.schemas.coding import CodeProposal
from app.schemas.review import ReviewResult

from app.schemas.retry import RetryAnalysis


class DevPilotState(TypedDict):
    # Initial input
    task: str
    repository_context: str
    workspace_path: str
    file_inventory: str

    # Agent outputs
    plan: NotRequired[TaskPlan]
    repository_analysis: NotRequired[RepositoryAnalysis]
    code_proposal: NotRequired[CodeProposal]
    review_result: NotRequired[ReviewResult]

    # Execution outputs
    patch_result: NotRequired[dict]
    diff_result: NotRequired[dict]
    execution_result: NotRequired[dict]


    # Retry management
    revision_count: NotRequired[int]
    review_feedback: NotRequired[str]
    attempt_history: NotRequired[list[dict]]
    retry_analysis: NotRequired[RetryAnalysis]
    verification_result: NotRequired[dict]
