
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Filechange(BaseModel):
    file_path: str = Field(
        description="Exact repository-relative path of the file to change. No annotations."
    )

    change_type: Literal["create", "modify", "delete"] = Field(
        description="Type of file operation being proposed"
    )

    proposed_content: str | None = Field(
        default=None,
        description="Complete proposed file content. Null only for deletion."
    )

    explanation: str = Field(
        description="Explanation of why this file needs to change"
    )

    @model_validator(mode="after")
    def validate_content(self):
        if self.change_type in ("create", "modify"):
            if self.proposed_content is None:
                raise ValueError(
                    "Create and modify operations require complete file content."
                )

        if self.change_type == "delete":
            if self.proposed_content is not None:
                raise ValueError(
                    "Delete operations must have null proposed_content."
                )

        return self


class CodeProposal(BaseModel):
    summary: str = Field(
        description="Summary of the proposed implementation"
    )

    changes: list[Filechange] = Field(
        description="List of proposed file changes"
    )

    tests_to_run: list[str] = Field(
        description="Tests that should be executed after implementation"
    )

    assumptions: list[str] = Field(
        description="Assumptions made while generating the solution"
    )
