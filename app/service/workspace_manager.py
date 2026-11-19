
import shutil
import uuid
from pathlib import Path

from git import Repo, InvalidGitRepositoryError


WORKSPACE_ROOT = (
    Path.home() / "DEV AI" / "devpilot-workspace"
).resolve()

DEVPILOT_ROOT = (
    WORKSPACE_ROOT / ".devpilot" / "workspaces"
).resolve()


def create_workspace(repository_name: str) -> dict:
    """
    Create an isolated copy of a repository for DevPilot.

    The original repository remains unchanged.
    """

    source_path = (WORKSPACE_ROOT / repository_name).resolve()

    # Ensure the source repository is inside the allowed workspace.
    if not source_path.is_relative_to(WORKSPACE_ROOT):
        raise ValueError("Invalid repository path")

    if not source_path.exists() or not source_path.is_dir():
        raise FileNotFoundError("Repository not found")

    try:
        repo = Repo(source_path, search_parent_directories=False)
    except InvalidGitRepositoryError:
        raise ValueError("The selected directory is not a Git repository")

    # Generate a unique workspace directory.
    workspace_id = uuid.uuid4().hex[:12]

    DEVPILOT_ROOT.mkdir(parents=True, exist_ok=True)

    destination_path = DEVPILOT_ROOT / f"{repository_name}-{workspace_id}"

    try:
        # Create a local Git clone.
        Repo.clone_from(source_path, destination_path, local=True)

        return {
            "workspace_id": workspace_id,
            "repository_name": repository_name,
            "workspace_path": str(destination_path),
            "message": "Workspace created successfully"
        }

    except Exception:
        # Remove incomplete workspace if cloning fails.
        if destination_path.exists():
            shutil.rmtree(destination_path)

        raise
