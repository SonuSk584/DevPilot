
from typing import TypedDict, NotRequired

from app.schemas.plan import TaskPlan
from app.schemas.repository import RepositoryAnalysis
from app.schemas.coding import CodeProposal
from app.schemas.review import ReviewResult


class DevPilotState(TypedDict):
    # Initial input
    task: str
    repository_context: str

    # Agent outputs
    plan: NotRequired[TaskPlan]
    repository_analysis: NotRequired[RepositoryAnalysis]
    code_proposal: NotRequired[CodeProposal]
    review_result: NotRequired[ReviewResult]

    # Retry management
    revision_count: NotRequired[int]
    review_feedback: NotRequired[str]
