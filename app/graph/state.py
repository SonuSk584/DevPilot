from typing import TypedDict, NotRequired

from app.schemas.plan import TaskPlan
from app.schemas.repository import RepositoryAnalysis
from app.schemas.coding import CodeProposal
from app.schemas.review import ReviewResult


class DevPilotState(TypedDict):
    task: str
    repository_context : str
    #agent outputs
    plan : TaskPlan
    repository_analysis: RepositoryAnalysis
    code_proposal: CodeProposal
    review_result: ReviewResult

    #retry management

    revision_count = NotRequired[int]
    review_feedback = NotRequired[str]