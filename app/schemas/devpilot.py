
from pydantic import BaseModel, Field
from typing import Any, Literal

from app.schemas.plan import TaskPlan
from app.schemas.repository import RepositoryAnalysis
from app.schemas.coding import CodeProposal
from app.schemas.review import ReviewResult

class DevPilotRequest(BaseModel):
    repository_name: str = Field(
        min_length=1,
        max_length=100,
        pattern=r"^[a-zA-Z0-9_-]+$"
    )

    task: str = Field(
        min_length=5,
        max_length=2000
    )






class DevPilotResponse(BaseModel):
    repository_name: str
    task: str

    thread_id: str

    status: Literal[
        "awaiting_human_approval",
        "completed",
        "rejected",
        "stopped"
    ]

    plan: TaskPlan | None = None
    repository_analysis: RepositoryAnalysis | None = None
    code_proposal: CodeProposal | None = None
    review_result: ReviewResult | None = None

    revision_count: int = 0

    approval_request: dict[str, Any] | None = None
    diff_result: dict[str, Any] | None = None

    message: str



class HumanApprovalRequest(BaseModel):
    decision: Literal[
        "approve",
        "reject",
        "request_changes"
    ]

    feedback: str = Field(
        default="",
        max_length=2000
    )
