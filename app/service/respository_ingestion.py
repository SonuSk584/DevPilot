
from pathlib import Path

from app.service.repository_scanner import scan_repository
from app.service.context_builder import build_repository_context


WORKSPACE_ROOT = (
    Path.home() / "devpilot-workspace"
).resolve()


def ingest_repository(repository_name: str) -> dict:

    # Construct the repository path inside our workspace
    repository_path = (
        WORKSPACE_ROOT / repository_name
    ).resolve()

    # Verify that the requested repository stays inside workspace
    if not repository_path.is_relative_to(WORKSPACE_ROOT):
        raise ValueError("Repository is outside the workspace")

    if not repository_path.exists():
        raise FileNotFoundError("Repository does not exist")

    if not repository_path.is_dir():
        raise NotADirectoryError("Repository path is not a directory")

    # Discover all eligible files
    discovered_files = scan_repository(str(repository_path))

    # Build the repository context
    context = build_repository_context(str(repository_path))

    python_files = [
        file for file in discovered_files
        if Path(file).suffix.lower() == ".py"
    ]

    return {
    "repository_name": repository_name,
    "total_files": len(discovered_files),
    "python_files": len(python_files),
    "context_characters": len(context),
    "context_preview": context[:1000],
    "message": "Repository ingested successfully",
    "context": context
    }
