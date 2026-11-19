from pydantic import BaseModel , Field

class RepositoryAnalysis(BaseModel):
    summary : str = Field(description="Summary of the repository Investigation")

    relevant_files : list[str] = Field(
        description="Repository files relevant to the requested task"
    )
    findings: list[str] = Field(
        description="Important observations based on the supplied code evidence"
    )

    potential_causes: list[str] = Field(
        description="Possible causes of the reported issue"
    )

    recommended_actions: list[str] = Field(
        description="Recommended next investigation or implementation steps"
    )

    confidence: float = Field (
        ge=0,
        le=1,
        description="Confidence in the analysis , between 0 to 1"
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