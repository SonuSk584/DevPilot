
import os
import subprocess
import sys
from pathlib import Path

from fastmcp import FastMCP


mcp = FastMCP("DevPilot Terminal")

WORKSPACE_ROOT = Path(
    os.getenv(
        "DEVPILOT_TERMINAL_ROOT",
        "/home/sonu/DEV AI/devpilot-workspace",
    )
).resolve()

MAX_FILE_SIZE = 100_000
MAX_OUTPUT_SIZE = 12_000
COMMAND_TIMEOUT = 10


def resolve_workspace_path(path: str) -> Path:
    """Resolve a path while preventing workspace escapes."""

    target = (WORKSPACE_ROOT / path).resolve()

    if not target.is_relative_to(WORKSPACE_ROOT):
        raise ValueError("Access outside the configured workspace is forbidden.")

    return target


def truncate_output(value: str) -> str:
    if len(value) > MAX_OUTPUT_SIZE:
        return value[:MAX_OUTPUT_SIZE] + "\n...[output truncated]"
    return value


@mcp.tool
def list_directory(path: str = ".") -> str:
    """List files and directories inside the permitted workspace."""

    target = resolve_workspace_path(path)

    if not target.is_dir():
        raise ValueError("The requested path is not a directory.")

    entries = sorted(target.iterdir(), key=lambda item: item.name)

    return "\n".join(
        f"{'[DIR] ' if item.is_dir() else '[FILE] '}{item.name}"
        for item in entries
    ) or "Directory is empty."


@mcp.tool
def read_file(path: str) -> str:
    """Read a text file inside the permitted workspace."""

    target = resolve_workspace_path(path)

    if not target.is_file():
        raise ValueError("The requested file does not exist.")

    if target.stat().st_size > MAX_FILE_SIZE:
        raise ValueError("File exceeds the maximum permitted size.")

    try:
        return target.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Only UTF-8 text files are supported.") from exc


@mcp.tool
def git_status(path: str = ".") -> str:
    """Inspect Git status without modifying the repository."""

    target = resolve_workspace_path(path)

    if not target.is_dir():
        raise ValueError("The requested path is not a directory.")

    result = subprocess.run(
        ["git", "status", "--short", "--branch"],
        cwd=target,
        capture_output=True,
        text=True,
        timeout=COMMAND_TIMEOUT,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr or "Git status failed.")

    return truncate_output(result.stdout)


@mcp.tool
def run_diagnostic(check: str) -> str:
    """Run one of the predefined, read-only diagnostic checks."""

    commands = {
        "python_version": [sys.executable, "--version"],
        "git_version": ["git", "--version"],
    }

    if check not in commands:
        raise ValueError(
            f"Unsupported diagnostic. Allowed checks: {', '.join(commands)}"
        )

    result = subprocess.run(
        commands[check],
        cwd=WORKSPACE_ROOT,
        capture_output=True,
        text=True,
        timeout=COMMAND_TIMEOUT,
        check=False,
    )

    output = result.stdout + result.stderr

    if result.returncode != 0:
        raise RuntimeError(output or "Diagnostic failed.")

    return truncate_output(output)


if __name__ == "__main__":
    mcp.run(transport="stdio")
