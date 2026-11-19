
import asyncio
from pathlib import Path

from app.graph.workflow import build_devpilot_graph


# --------------------------------------------------
# Configuration
# --------------------------------------------------

WORKSPACE = (
    Path.home()
    / "DEV AI"
    / "devpilot-workspace"
    / ".devpilot"
    / "workspaces"
    / "sample-project-9510158bbf4f"
)


TASK = """
Add a GET endpoint /health/details to the existing FastAPI
application.

Requirements:
1. Return application status as "healthy".
2. Include an API version in the response.
3. Add appropriate pytest tests for the endpoint.
4. Preserve all existing functionality.
5. Avoid unnecessary files and modifications.
"""


IGNORED_DIRS = {
    ".git",
    ".devpilot",
    ".devpilot-venv",
    "__pycache__",
    "node_modules",
    ".pytest_cache",
    ".mypy_cache",
    "venv",
    ".venv",
    "build",
    "dist"
}

MAX_FILE_SIZE = 100_000
MAX_CONTEXT_CHARS = 100_000

def should_ignore(path: Path, workspace: Path) -> bool:
    """
    Check ignored directories relative to the repository root,
    not the absolute filesystem path.
    """

    relative_path = path.relative_to(workspace)

    return any(
        part in IGNORED_DIRS
        for part in relative_path.parts
    )


# --------------------------------------------------
# Repository File Inventory
# --------------------------------------------------

def build_file_inventory(workspace: Path) -> str:
    """
    Return the actual file inventory of the repository.
    """

    files = []

    for path in workspace.rglob("*"):

        if should_ignore(path, workspace):
            continue

        if path.is_symlink() or not path.is_file():
            continue

        if path.stat().st_size > MAX_FILE_SIZE:
            continue

        relative_path = path.relative_to(workspace)

        files.append(relative_path.as_posix())

    return "\n".join(sorted(set(files)))


# --------------------------------------------------
# Repository Context Builder
# --------------------------------------------------

def build_repository_context(workspace: Path) -> str:
    """
    Collect relevant source code and project configuration.
    """

    context_parts = []
    total_chars = 0

    relevant_extensions = {
        ".py",
        ".toml",
        ".ini",
        ".cfg"
    }

    important_files = {
        "readme.md",
        "requirements.txt",
        "requirement.txt",
        "pyproject.toml",
        "setup.py",
        "setup.cfg"
    }

    for file_path in sorted(workspace.rglob("*")):

        if should_ignore(file_path, workspace):
            continue

        if file_path.is_symlink() or not file_path.is_file():
            continue

        if file_path.stat().st_size > MAX_FILE_SIZE:
            continue

        if (
            file_path.suffix.lower() not in relevant_extensions
            and file_path.name.lower() not in important_files
        ):
            continue

        try:
            content = file_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        relative_path = file_path.relative_to(workspace)

        section = (
            f"\n--- FILE: {relative_path.as_posix()} ---\n"
            f"{content}\n"
        )

        if total_chars + len(section) > MAX_CONTEXT_CHARS:
            break

        context_parts.append(section)
        total_chars += len(section)

    return "\n".join(context_parts)


# --------------------------------------------------
# Repository Validation
# --------------------------------------------------

def validate_workspace(workspace: Path):
    """
    Verify that the workspace is ready for DevPilot.
    """

    if not workspace.exists() or not workspace.is_dir():
        raise FileNotFoundError(
            f"Workspace not found: {workspace}"
        )

    if not (workspace / ".git").exists():
        raise ValueError("Workspace is not a Git repository")

    venv_python = (
        workspace
        / ".devpilot-venv"
        / "bin"
        / "python"
    )

    if not venv_python.is_symlink() and not venv_python.is_file():
        raise FileNotFoundError(
            "Project virtual environment not found"
        )


# --------------------------------------------------
# Main Workflow
# --------------------------------------------------

async def main():

    print("\n========== DEVPILOT AUTONOMOUS CODING ==========\n")

    # 1. Validate workspace
    validate_workspace(WORKSPACE)

    print("[1/5] Workspace validation successful")

    # 2. Build repository inventory
    file_inventory = build_file_inventory(WORKSPACE)

    print("[2/5] Repository inventory generated")

    # 3. Build repository context
    repository_context = build_repository_context(WORKSPACE)

    print("[3/5] Repository context generated")

    print("\nRepository files:")
    print(file_inventory)

    # 4. Build LangGraph
    graph = build_devpilot_graph()

    print("\n[4/5] DevPilot graph initialized")

    if not file_inventory.strip():
        raise ValueError(
        "Repository inventory is empty. Check workspace filtering."
    )

    if not repository_context.strip():
        raise ValueError(
        "Repository context is empty. No readable source files found."
    )

    # 5. Prepare initial state
    initial_state = {
        "task": TASK,
        "repository_context": repository_context,
        "file_inventory": file_inventory,
        "workspace_path": str(WORKSPACE),
        "revision_count": 0,
        "attempt_history": []
    }

    print("\n[5/5] Starting autonomous coding workflow...\n")

    print("\n[5/5] Starting autonomous coding workflow...\n")

    # Debug: Inspect initial LangGraph state
    print("[DEBUG] Initial state:", list(initial_state.keys()))
    print("[DEBUG] Inventory length:", len(initial_state["file_inventory"]))

    # Execute workflow
    result = await graph.ainvoke(initial_state)

    # --------------------------------------------------
    # Final Report
    # --------------------------------------------------

    print("\n========== DEVPILOT FINAL REPORT ==========\n")

    print("Task:")
    print(TASK)

    print("\nRevision count:")
    print(result.get("revision_count", 0))

    print("\nPatch result:")
    print(result.get("patch_result"))

    print("\nDiff result:")
    diff_result = result.get("diff_result", {})
    print(diff_result)

    print("\nExecution result:")
    print(result.get("execution_result"))

    print("\nReview result:")
    print(result.get("review_result"))

    print("\n========== ATTEMPT HISTORY ==========\n")

    for attempt in result.get("attempt_history", []):

        print(f"\nAttempt #{attempt['attempt_number']}")

        print("Patch status:",
          attempt["patch_result"].get("status"))

        print("Execution status:",
          attempt["execution_result"].get("status"))

        review = attempt.get("review_result")

        if review:
            print("Reviewer approved:", review.get("approved"))
            print("Reviewer summary:", review.get("summary"))

    # Final status
    patch_result = result.get("patch_result", {})
    execution_result = result.get("execution_result", {})
    review_result = result.get("review_result")

    if (
        patch_result.get("status") == "success"
        and execution_result.get("status") == "success"
        and review_result is not None
        and review_result.approved
    ):
        final_status = "COMPLETED"
    else:
        final_status = "NOT APPROVED"

    print("\n-------------------------------------------")
    print("FINAL STATUS:", final_status)
    print("-------------------------------------------\n")


if __name__ == "__main__":
    asyncio.run(main())
