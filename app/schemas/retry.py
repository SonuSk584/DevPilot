
from typing import Literal

from pydantic import BaseModel, Field


class RetryAnalysis(BaseModel):
    """Structured output produced by the Retry Intelligence node."""

    failure_type: Literal[
        "syntax_error",
        "import_error",
        "dependency_error",
        "test_failure",
        "patch_failure",
        "execution_timeout",
        "infrastructure_error",
        "review_rejection",
        "implementation_error",
        "user_constraint_violation",
        "environment_error",
        "verification_gap",
        "file_operation_error",
        "unknown",
    ]

    decision: Literal[
        "retry",
        "verify",
        "stop",
    ] = Field(
        description=(
            "Whether DevPilot should retry coding, "
            "perform additional verification, or stop."
        )
    )

    root_cause: str

    repeated_failure: bool

    previous_attempt_reference: int | None = None

    correction_strategy: list[str]

    should_retry: bool = Field(
        description=(
            "True only when another coding attempt is required. "
            "False for verification-only actions and stopping."
        )
    )

    confidence: float = Field(ge=0.0, le=1.0)
