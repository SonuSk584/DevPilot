from pydantic import BaseModel, Field


class RepositoryAnalysis(BaseModel):
    relevant_files: list[str] = Field(
        max_length=8,
        description="Paths from the inventory that matter for this task"
    )
    where_to_change: list[str] = Field(
        max_length=6,
        description="File and function/location to modify or extend"
    )
    conventions: list[str] = Field(
        default_factory=list, max_length=5,
        description="Framework, import style, naming and patterns to follow"
    )
    constraints: list[str] = Field(
        default_factory=list, max_length=5,
        description="Things in the code that could break existing behavior"
    )
    missing_context: list[str] = Field(
        default_factory=list, max_length=4,
        description="What could not be seen. Empty if nothing."
    )
class repositoryAnalysisRequest(BaseModel):
    task: str = Field(
        min_length= 5,
        max_length=5000,
        description="Software engineering task"
    )
    repository_context : str = Field(
        min_length=10,
        max_length=30000,
        description="Repository files and code snippet"
    )



class RepositoryTaskRequest(BaseModel):
    repository_name: str = Field(
        min_length=1,
        max_length=100,
        pattern=r"^[a-zA-Z0-9_-]+$"
    )

    task: str = Field(
        min_length=5,
        max_length=2000
    )