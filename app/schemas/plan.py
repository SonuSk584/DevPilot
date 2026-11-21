from pydantic import BaseModel, Field


class TaskPlan(BaseModel):
    task_summary: str = Field(
        description="One-sentence summary of the task"
    )
    constraints: list[str] = Field(
        default_factory=list,
        description="Explicit user constraints, copied verbatim. Empty if none."
    )
    allowed_files: list[str] = Field(
        description="Files that may be created or modified. "
                    "Existing files must come from the inventory."
    )
    steps: list[str] = Field(
        max_length=6,
        description="Ordered steps; each names the file and the change"
    )
    risks: list[str] = Field(
        default_factory=list,
        max_length=3,
        description="Risks specific to this repository. Empty if none."
    )
    verification: str = Field(
        description="Test command to run, or 'no tests allowed' if the "
                    "constraints forbid test files"
    )


class PlanRequest(BaseModel):
    task: str = Field(
        min_length=5,
        max_length=5000,
        description="Software engineering task to plan"
    )