from pydantic import BaseModel, Field

class RepositoryIngestionRequest(BaseModel):
    repository_name : str = Field(
        min_length=1,
        max_length=100,
        pattern=r"^[a-zA-Z0-9_-]+$"
    )

class RepositoryIngestionResponse(BaseModel):
    repository_name: str
    total_files: int
    python_files: int
    context_characters: int
    context_preview: str
    message: str
