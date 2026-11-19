
from pydantic import BaseModel, Field

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
    plan: TaskPlan
    repository_analysis: RepositoryAnalysis
    code_proposal: CodeProposal
    review_result: ReviewResult
    revision_count: int
    message: str

