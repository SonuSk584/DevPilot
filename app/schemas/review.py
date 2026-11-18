from typing import Literal

from pydantic import BaseModel, Field


class ReviewFinding(BaseModel):

    severity: Literal["low", "medium", "high", "critical"]

    file_path: str | None = None

    issue: str = Field(
        description="Description of the identified problem"
    )

    suggestion: str = Field(
        description="Recommended correction"
    )


class ReviewResult(BaseModel):

    approved: bool = Field(
        description="Whether the proposed code changes are acceptable"
    )

    summary: str = Field(
        description="Overall review summary"
    )

    findings: list[ReviewFinding] = Field(
        description="Problems identified during review"
    )

    required_changes: list[str] = Field(
        description="Changes required before approval"
    )

    tests_to_run: list[str] = Field(
        description="Tests recommended before accepting the changes"
    )

class ReviewRequest(BaseModel):

    task: str = Field(
        min_length=5,
        max_length=5000
    )

    repository_analysis: str = Field(
        min_length=10,
        max_length=20000
    )

    repository_context: str = Field(
        min_length=10,
        max_length=30000
    )

    code_proposal: str = Field(
        min_length=10,
        max_length=30000
    )