
import difflib
from pathlib import Path

from git import Repo, InvalidGitRepositoryError


MAX_DIFF_FILE_SIZE = 1_000_000  # 1 MB


def get_workspace_diff(workspace_path: str) -> dict:
    """
    Inspect a Git workspace and generate a report of its changes.

    Includes:
    - Modified tracked files
    - Deleted tracked files
    - Newly created untracked files
    """

    root = Path(workspace_path).resolve()

    if not root.is_dir():
        raise FileNotFoundError("Workspace does not exist")

    try:
        repo = Repo(root, search_parent_directories=False)
    except InvalidGitRepositoryError:
        raise ValueError("Workspace is not a Git repository")

    if repo.bare:
        raise ValueError("Bare repositories are not supported")

    # Get tracked file changes compared with the latest commit.
    git_diff = repo.git.diff("HEAD", "--")

    # Get changed file names and statuses.
    name_status = repo.git.diff(
        "HEAD",
        "--name-status"
    )

    files = []

    for line in name_status.splitlines():
        if not line.strip():
            continue

        parts = line.split("\t")

        status_code = parts[0]

        if status_code.startswith("R") and len(parts) >= 3:
            files.append({
                "file_path": parts[2],
                "change_type": "renamed",
                "status": status_code
            })

        elif len(parts) >= 2:
            status_map = {
                "A": "added",
                "M": "modified",
                "D": "deleted"
            }

            files.append({
                "file_path": parts[1],
                "change_type": status_map.get(
                    status_code,
                    "unknown"
                ),
                "status": status_code
            })

    # Handle untracked files separately.
    untracked_files = repo.untracked_files
    untracked_diffs = []

    for relative_path in untracked_files:
        file_path = root / relative_path

        # Do not follow symbolic links.
        if file_path.is_symlink() or not file_path.is_file():
            continue

        if file_path.stat().st_size > MAX_DIFF_FILE_SIZE:
            untracked_diffs.append(
                f"\nSkipped oversized file: {relative_path}\n"
            )
            continue

        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            untracked_diffs.append(
                f"\nSkipped binary file: {relative_path}\n"
            )
            continue

        diff_lines = difflib.unified_diff(
            [],
            content.splitlines(keepends=True),
            fromfile="/dev/null",
            tofile=f"b/{relative_path}"
        )

        untracked_diffs.extend(diff_lines)

        files.append({
            "file_path": relative_path,
            "change_type": "added",
            "status": "??"
        })

    complete_diff = git_diff

    if untracked_diffs:
        complete_diff += "\n" + "".join(untracked_diffs)

    summary = {
        "added": sum(
            item["change_type"] == "added" for item in files
        ),
        "modified": sum(
            item["change_type"] == "modified" for item in files
        ),
        "deleted": sum(
            item["change_type"] == "deleted" for item in files
        ),
        "renamed": sum(
            item["change_type"] == "renamed" for item in files
        )
    }

    return {
        "workspace_path": str(root),
        "total_changed_files": len(files),
        "summary": summary,
        "files": files,
        "diff": complete_diff
    }
