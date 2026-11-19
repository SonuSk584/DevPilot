from typing import Literal

from pydantic import BaseModel, Field

class Filechange(BaseModel):
    file_path: str= Field(
        description="Relative path of the file to modify"
    )

    change_type: Literal["create","modify","delete"] = Field(
        description= "type of file operation being proposed"
    )

    proposed_content : str | None = Field(
        default=None,
        description="Complete proposed file content. Null for deletion"
    )

    explanation : str = Field(
        description="explanation of why this file needs to change"
    )

class CodeProposal(BaseModel):
    summary: str = Field(
        description="Summary of the proposed implementation"
    )

    changes: list[Filechange] = Field(
        description="List of proposed file changes "
    )

    tests_to_run: list[str]= Field(
        description= "Tests that should be executed after implementation"
    )

    assumptions: list[str]= Field(
        description= "Assumption made while generating the solution"
    )