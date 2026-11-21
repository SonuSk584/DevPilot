"""

Provides:
- prepare_workspace(): makes a disposable copy of the project per run,
  pinned to the last git commit (HEAD).
- guard_patch_node(): wraps your existing patch_engine_node so that every
  attempt starts from the baseline, and a bad patch (syntax error or files
  outside the plan's allowed_files) fails fast with a precise message that
  goes straight back to the Coder.
"""

import ast
import inspect
import shutil
import subprocess
import uuid
from pathlib import Path

COPY_IGNORE = shutil.ignore_patterns(
    "venv", ".venv", ".devpilot-venv",
    "__pycache__", ".pytest_cache", ".mypy_cache",
)


def _git(workspace: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(workspace), *args],
        check=True, capture_output=True, text=True,
    )


def _is_run_copy(workspace: Path) -> bool:
    return ".devpilot" in workspace.parts and "workspaces" in workspace.parts


def prepare_workspace(source: Path) -> Path:
    """
    Copy the project (with .git) into
    <parent>/.devpilot/workspaces/<name>-<id> and pin it to HEAD.
    Anything uncommitted in the source is discarded in the copy,
    so commit your requirement.txt first.
    """
    source = Path(source).resolve()
    run_dir = (
        source.parent / ".devpilot" / "workspaces"
        / f"{source.name}-{uuid.uuid4().hex[:12]}"
    )
    shutil.copytree(source, run_dir, ignore=COPY_IGNORE)

    _git(run_dir, "reset", "--hard", "HEAD")
    _git(run_dir, "clean", "-fd")

    exclude = run_dir / ".git" / "info" / "exclude"
    exclude.parent.mkdir(parents=True, exist_ok=True)
    with exclude.open("a") as f:
        f.write("\n.devpilot-venv/\n__pycache__/\n.pytest_cache/\n")

    return run_dir


def reset_workspace(workspace_path: str) -> None:
    """Return a run copy to the committed baseline. Refuses real projects."""
    workspace = Path(workspace_path).resolve()
    if not _is_run_copy(workspace):
        raise RuntimeError(
            f"Refusing to reset {workspace}: not a DevPilot run copy. "
            "Use prepare_workspace() first."
        )
    _git(workspace, "reset", "--hard", "HEAD")
    _git(workspace, "clean", "-fd")  # ignored files (.devpilot-venv) survive


def check_syntax(workspace_path: str, files: list[str]) -> str | None:
    for rel in files:
        if not rel.endswith(".py"):
            continue
        try:
            ast.parse((Path(workspace_path) / rel).read_text(), rel)
        except SyntaxError as e:
            return f"{rel}:{e.lineno}: SyntaxError: {e.msg}"
    return None


def guard_patch_node(original_node):
    """Wrap patch_engine_node (sync or async)."""

    async def guarded(state):
        reset_workspace(state["workspace_path"])

        out = original_node(state)
        if inspect.isawaitable(out):
            out = await out

        patch = out["patch_result"]

        if patch.get("status") == "success":
            changed = [
                r["file_path"] for r in patch.get("results", [])
                if r.get("operation") != "delete"
            ]

            plan = state.get("plan")
            allowed = set(plan.allowed_files) if plan else None
            outside = (
                sorted(set(changed) - allowed) if allowed is not None else []
            )

            if outside:
                patch = {
                    "status": "failed",
                    "error": (
                        f"Files outside the allowed scope: {outside}. "
                        f"Allowed files: {sorted(allowed)}."
                    ),
                }
            else:
                syntax_error = check_syntax(state["workspace_path"], changed)
                if syntax_error:
                    patch = {"status": "failed", "error": syntax_error}

            out["patch_result"] = patch

        if patch.get("status") != "success":
            out["review_feedback"] = (
                "Your last proposal was rejected before any tests ran.\n"
                f"Reason: {patch.get('error')}\n"
                "Return the full change set against the original baseline, "
                "with file contents exactly as they should be written to disk."
            )

        return out

    return guarded