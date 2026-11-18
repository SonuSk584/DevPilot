from pydantic import BaseModel, Field

class TaskPlan(BaseModel):
    task_summary : str = Field(
        description="A short summary of the requested task"
    )
    steps: list[str] = Field(
        description="ordered steps required to complete the task"

    )

    risks: list[str]= Field(
        description="Potentiall risks or challenges"
    )
    requires_repository : bool = Field(
        description="whether respository access is necessary"
    )

class PlanRequest(BaseModel):
    task: str = Field(
        min_length=5,
        max_length=5000,
        description="Software engineering task to plan"
    )